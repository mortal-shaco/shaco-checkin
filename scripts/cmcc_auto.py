# -*- coding: utf-8 -*-
# name: 中国移动签到有礼
# cron: 29 10 * * *
# SPDX-License-Identifier: MIT
"""中国移动 wx.10086.cn 签到有礼；Python 3 标准库。

来源：jian1098/cmcc_auto_checkin / cmcc_auto.py
上游提交：0a568c516ea675fdd928289c5e65d7ef46bb684e，许可 MIT。
提供的原始文件没有额外版权或许可证正文；保留原作者归属。

CMCC_COOKIE 必填：在微信打开中国移动官方“签到有礼”并登录，使用本人
授权的浏览器开发者工具或 HTTPS 抓包工具，找到 wx.10086.cn 的
/qwhdhub/api/mark/do/mark 请求，复制完整 Cookie 请求头值（不含 Cookie:）。
每个非空行一个账号，Cookie 内的分号、&、@ 原样保留；不要分享凭据。
CMCC_DRY_RUN=1：只验证配置并模拟执行，不联网、不写结果文件、不发送通知。
FEISHU_WEBHOOK 可选：飞书自定义机器人 HTTPS Webhook；沿用原版无需签名的
卡片推送接口，不支持需要签名的机器人。地址作为秘密保存，不输出。
RESULT_FILE 可选：指定本机摘要文件；仅显式配置时覆盖写入，请使用专用文件。
QINGLONG_NOTIFY=auto|1|0：自动选择、强制开启或关闭青龙通知；auto 默认选择
本任务，QINGLONG_NOTIFY_SCRIPTS 设置后替换选择列表，支持目录相对路径、
文件名、通配符或目录编号，逗号/分号/空白分隔，空串禁用全部。
QINGLONG_NOTIFY_DIR 可选：青龙 notify.py 或 sendNotify.js 所在目录。
推荐每天北京时间 09:00；原始 Actions 定时时刻未随输入提供。
签到会改变签到及奖励状态；推送及文件写入均为显式可选操作。
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
        _ql_notify_identities = ('c4106d0130339343', 'scripts/cmcc_auto.py', 'cmcc_auto.py', 'cmcc_auto')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = '中国移动签到有礼'
CATALOG_ID = 'c4106d0130339343'
SIGN_URL = 'https://wx.10086.cn/qwhdhub/api/mark/do/mark'
TIMEOUT = 15
MAX_BYTES = 131072
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


def stamp():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def log(message):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), message), flush=True)


def load_cookies(raw):
    return [line.strip() for line in raw.splitlines() if line.strip()]


def safe_text(value):
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ''
    text = str(value)
    secrets = load_cookies(os.environ.get('CMCC_COOKIE', ''))
    for cookie in secrets:
        secrets_parts = [cookie] + [part.split('=', 1)[1].strip() for part in cookie.split(';') if '=' in part]
        for secret in secrets_parts:
            if secret:
                text = text.replace(secret, '[已脱敏]')
    webhook = os.environ.get('FEISHU_WEBHOOK', '').strip()
    if webhook:
        text = text.replace(webhook, '[已脱敏]')
    text = re.sub(r'(?i)(?:cookie|token|session|authorization|device[ _-]?id)\s*[:=]\s*\S+', '[已脱敏]', text)
    text = re.sub(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(c for c in text if c.isprintable())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_json(url, headers, payload=None):
    # 登录态绝不转发到跳转地址；证书校验始终开启。
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    data = json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with opener.open(req, timeout=TIMEOUT) as resp:
                content = resp.read(MAX_BYTES + 1)
                if len(content) > MAX_BYTES:
                    return resp.status, None, '响应超出大小限制'
                try:
                    body = json.loads(content.decode('utf-8'))
                except (ValueError, UnicodeError):
                    return resp.status, None, '响应不是有效 JSON'
                if not isinstance(body, dict):
                    return resp.status, None, '响应结构异常'
                return resp.status, body, ''
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if status < 500 or attempt == 3:
                return status, None, 'HTTP 请求失败'
            log('请求返回 HTTP %d，准备第 %d 次重试' % (status, attempt))
        except (OSError, ValueError, urllib.error.URLError):
            if attempt == 3:
                return -1, None, '网络或请求异常，重试耗尽'
            log('网络或请求异常，准备第 %d 次重试' % attempt)
        time.sleep(attempt * 2)
    return -1, None, '重试耗尽'


def sign_headers(cookie):
    return {
        'Cookie': cookie,
        'Content-Type': 'application/json',
        'User-Agent': ('Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36 MicroMessenger/8.0.47'),
        'Referer': 'https://wx.10086.cn/',
        'Origin': 'https://wx.10086.cn',
    }


def do_sign(cookie):
    status, body, error = post_json(SIGN_URL, sign_headers(cookie))
    if status != 200 or body is None:
        return 'failed', '%s（HTTP %s）' % (error or '请求失败', status)
    data = body.get('data')
    data = data if isinstance(data, dict) else {}
    for obj in (body, data):
        for field in ('nickname', 'nickName', 'username', 'displayName', 'publicUid', 'uid'):
            identity = safe_text(obj.get(field))
            if identity:
                log('官方账号身份：%s' % identity)
    if body.get('success') is True:
        cat = data.get('categoryOverview')
        cat = cat if isinstance(cat, dict) else {}
        prize = safe_text(data.get('prizeName')) or '未返回奖品'
        total = safe_text(cat.get('valueDesc')) or (safe_text(cat.get('totalValue')) + safe_text(cat.get('unit'))) or '未返回累计'
        return 'success', '签到成功，获得「%s」，本月累计 %s' % (prize, total)
    if body.get('code') == 'TODAY_MARKED':
        return 'alreadyComplete', '今日已签到（官方重复签到状态）'
    if body.get('code') == 'ALL_MARKED':
        return 'failed', '官方返回 ALL_MARKED，名额领完不能证明本账号今日签到成功'
    # 未知 code/msg 可能回显凭据，不输出原始响应或业务消息。
    return 'failed', '官方未确认签到成功；请检查本人登录状态或接口契约'


def push_feishu(webhook, sections, overall_ok):
    parsed = urllib.parse.urlsplit(webhook)
    if (parsed.scheme != 'https' or parsed.hostname != 'open.feishu.cn'
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not parsed.path.startswith('/open-apis/bot/v2/hook/')):
        return False
    lines = ['**%s**\n%s' % item for item in sections]
    payload = {'msg_type': 'interactive', 'card': {
        'config': {'wide_screen_mode': True},
        'header': {'template': 'green' if overall_ok else 'red',
                   'title': {'tag': 'plain_text', 'content': TITLE + (' · 成功' if overall_ok else ' · 有失败项')}},
        'elements': [{'tag': 'div', 'text': {'tag': 'lark_md', 'content': '\n\n'.join(lines)}}]}}
    status, body, _ = post_json(webhook, {'Content-Type': 'application/json'}, payload)
    return status == 200 and isinstance(body, dict) and type(body.get('code')) is int and body['code'] == 0


def notification_selected():
    mode = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    if mode in FALSE:
        return False
    if mode in TRUE:
        return True
    if 'QINGLONG_NOTIFY_SCRIPTS' not in os.environ:
        return True
    selectors = re.split(r'[,;\s]+', os.environ['QINGLONG_NOTIFY_SCRIPTS'].strip())
    path = Path(__file__).as_posix()
    names = {CATALOG_ID, Path(__file__).name, 'cmcc_auto.py', 'candidate.py', path}
    if '/scripts/' in path:
        names.add(path.split('/scripts/', 1)[1])
    return any(s and any(fnmatch.fnmatchcase(n, s) for n in names) for s in selectors)


# 通知适配器在隔离子进程中运行；抑制外部通知模块的原始输出。
NOTIFY_CODE = r'''
import importlib.util, pathlib, sys
path, kind, title, body = sys.argv[1:]
if kind == 'python':
    if path:
        sys.path.insert(0, str(pathlib.Path(path).parent))
        spec = importlib.util.spec_from_file_location('ql_notify_adapter', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        import notify as module
    module.send(title, body)
else:
    raise RuntimeError('invalid adapter')
'''


def notify(summary, dry_run):
    if dry_run:
        return '演练跳过（未联网）'
    if not notification_selected():
        return '配置关闭'
    body = '%s；账号总数 %d，成功 %d，失败 %d；子任务成功 %d，已完成 %d，跳过 %d，失败 %d' % (
        summary['status'], summary['accounts'], summary['succeeded'], summary['failed'],
        summary['tasks']['success'], summary['tasks']['alreadyComplete'], summary['tasks']['skipped'], summary['tasks']['failed'])
    directories = []
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        directories.append(Path(os.environ['QINGLONG_NOTIFY_DIR']).resolve())
    directories.extend([Path(__file__).resolve().parent, Path('/ql/data/scripts'), Path('/ql/scripts')])
    commands = [[sys.executable, '-c', NOTIFY_CODE, '', 'python', TITLE, body]]
    for directory in directories:
        py = directory / 'notify.py'
        js = directory / 'sendNotify.js'
        if py.is_file():
            commands.append([sys.executable, '-c', NOTIFY_CODE, str(py), 'python', TITLE, body])
        if js.is_file():
            commands.append(['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(js), TITLE, body])
    for command in commands:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
            if result.returncode == 0:
                return '发送成功'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return '不可用或发送失败（保留业务退出码）'


def main():
    started = time.monotonic()
    dry_run = os.environ.get('CMCC_DRY_RUN', '').strip().lower() in TRUE
    cookies = load_cookies(os.environ.get('CMCC_COOKIE', ''))
    log('========== %s ==========' % TITLE)
    log('开始时间：%s；模式：%s；账号数：%d' % (stamp(), '断网演练' if dry_run else '正式执行', len(cookies)))
    stage_start = time.monotonic()
    log('阶段 1/3 配置检查')
    totals = dict(success=0, alreadyComplete=0, skipped=0, failed=0)
    sections = []
    succeeded = failed = 0
    config_error = not cookies
    if config_error:
        log('❌ 缺少必填 CMCC_COOKIE：每个非空行填写一个账号的完整 Cookie')
    log('阶段 1/3 配置检查结束；耗时 %.2f 秒' % (time.monotonic() - stage_start))
    stage_start = time.monotonic()
    log('阶段 2/3 逐账号签到')
    for index, cookie in enumerate(cookies, 1):
        account_start = time.monotonic()
        label = '账号 %d' % index
        log('%s 阶段 1/1 签到开始' % label)
        try:
            if any(ord(c) < 32 or ord(c) == 127 for c in cookie) or '=' not in cookie:
                outcome, message = 'failed', 'Cookie 格式错误，需要完整请求头值'
            elif dry_run:
                outcome, message = 'skipped', 'DRY_RUN_OK 配置可解析，未发送签到请求'
            else:
                outcome, message = do_sign(cookie)
        except Exception:
            outcome, message = 'failed', '账号处理异常（详情已抑制，继续其他账号）'
        totals[outcome] += 1
        failed += outcome == 'failed'
        succeeded += outcome in ('success', 'alreadyComplete')
        log('%s：%s' % (label, message))
        sections.append((label, message))
        log('%s 统计：总任务 1，成功 %d，已完成 %d，跳过 %d，失败 %d；阶段耗时 %.2f 秒' % (
            label, outcome == 'success', outcome == 'alreadyComplete', outcome == 'skipped', outcome == 'failed', time.monotonic() - account_start))
    exit_code = 1 if config_error else 2 if failed else 0
    status = 'configuration-error' if config_error else 'partial-failure' if failed and succeeded else 'failure' if failed else 'dry-run' if dry_run else 'success'
    if config_error:
        sections.append(('配置检查', '缺少 CMCC_COOKIE'))
    log('阶段 2/3 逐账号签到结束；耗时 %.2f 秒' % (time.monotonic() - stage_start))
    stage_start = time.monotonic()
    log('阶段 3/3 汇总及通知')
    result_file = os.environ.get('RESULT_FILE', '').strip()
    if result_file and not dry_run:
        try:
            with open(result_file, 'w', encoding='utf-8') as handle:
                for name, line in sections:
                    handle.write('- %s：%s\n' % (name, line))
            log('摘要文件写入成功')
        except (OSError, ValueError):
            log('摘要文件写入失败（保留业务退出码）')
    webhook = os.environ.get('FEISHU_WEBHOOK', '').strip()
    feishu = '未配置' if not webhook else '演练跳过'
    if webhook and not dry_run:
        try:
            feishu = '发送成功' if push_feishu(webhook, sections, exit_code == 0) else '发送失败'
        except Exception:
            feishu = '发送失败'
    summary = {'status': status, 'mode': 'dry-run' if dry_run else 'live', 'accounts': len(cookies),
               'succeeded': succeeded, 'failed': failed, 'tasks': totals, 'exitCode': exit_code}
    try:
        notification = notify(summary, dry_run)
    except Exception:
        notification = '通知异常（保留业务退出码）'
    log('阶段 3/3 汇总及通知结束；耗时 %.2f 秒' % (time.monotonic() - stage_start))
    summary.update(notification=notification, feishu=feishu, durationSeconds=round(time.monotonic() - started, 2), finishTime=stamp())
    log('----------------------------------------')
    log('账号统计：总数 %d，成功 %d，失败 %d，演练跳过 %d' % (len(cookies), succeeded, failed, totals['skipped']))
    log('子任务统计：总数 %d，成功 %d，已完成 %d，跳过 %d，失败 %d' % (sum(totals.values()), totals['success'], totals['alreadyComplete'], totals['skipped'], totals['failed']))
    log('青龙通知：%s；飞书通知：%s' % (notification, feishu))
    log('结束时间：%s；总耗时 %.2f 秒；最终状态：%s；退出码 %d' % (summary['finishTime'], summary['durationSeconds'], status, exit_code))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
