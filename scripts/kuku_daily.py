#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: KukuAI 每日积分
# cron: 0 8 * * *
# License: MIT
# 原始项目与作者：L0NE-6/KukuAI-Daily
# https://github.com/L0NE-6/KukuAI-Daily/blob/6912419c6b29365bb7b3172cc3c18bf7b763812d/kuku_daily.py
"""KukuAI（百度文库 · 库库 AI / GenFlowPro）每日积分，Python 3.8+ 标准库。

每日依次查询积分面板、领取 LOGIN 和 CHAT 奖励；不会实际发送对话、发布文本或消费积分。
KUKU_ACCOUNTS（推荐）：每个非空行一个账号，格式 产品作用域STOKEN|完整Cookie。
只在第一个 | 处分割，Cookie 后续内容完整保留。Cookie 支持请求头、单行编辑器 JSON、
{BDUSS,PTOKEN} 对象。BDUSS 与 genflowpro 作用域 STOKEN 必须来自同一账号。

获取：自行登录官方库库 AI 客户端，在可查看的官方业务请求中复制 kuku.baidu.com 的
Cookie 和产品作用域 STOKEN；网页通行证 STOKEN 不一定可用于该业务。没有该令牌时
本脚本不能换发，不要使用第三方获取服务。不要把凭据粘贴到日志或公开仓库。
旧输入仍支持 KUKU_COOKIES + KUKU_STOKEN（单账号），或 KUKU_TOKENS 多行
备注|BDUSS|PTOKEN|STOKEN；不会用 & 分隔账号，也不使用本机令牌缓存或 DLL。
KUKU_PROXY：可选 HTTP/HTTPS 代理；标准库不支持 SOCKS。
KUKU_DRY_RUN=1：仅解析参数并模拟阶段，不访问网络、缓存或客户端文件。
QINGLONG_NOTIFY 默认开启；KUKU_NO_NOTIFY=1 兼容旧关闭开关。
通知经青龙 notify.py；断网预演仅展示拟发送摘要，不调用可能联网的通知模块。
python candidate.py --only 1：仅处理第一个账号；--token 已安全停用，不输出令牌。
"""
import contextlib
import datetime
import importlib
import importlib.util
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = 'https://kuku.baidu.com'
WEB_QUERY = 'clienttype=400&app_id=123971023&web=1&channel=chunlei&version=1.4.4'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36')
DAILY_TASKS = (('LOGIN', '每日登录奖励'), ('CHAT', '对话任务奖励'))
DISABLED = {'0', 'false', 'no', 'off'}
SECRETS = []


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() not in DISABLED | {''}


def stamp():
    return datetime.datetime.now().strftime('%H:%M:%S')


def redact(value):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[凭据已隐藏]')
    return text.replace('\r', ' ').replace('\n', ' ')


def log(text):
    print('[%s] %s' % (stamp(), redact(text)), flush=True)


class TaskError(Exception):
    pass


def parse_cookie(raw):
    raw = raw.strip()
    if raw.startswith(('{', '[')):
        try:
            obj = json.loads(raw)
        except ValueError:
            raise TaskError('Cookie JSON 格式错误')
        if isinstance(obj, dict):
            obj = obj.get('cookies', obj.get('cookie', obj))
        if isinstance(obj, dict):
            pairs = list(obj.items())
        elif isinstance(obj, list):
            pairs = [(item.get('name', item.get('Name', '')),
                      item.get('value', item.get('Value', '')))
                     for item in obj if isinstance(item, dict)]
        else:
            raise TaskError('Cookie JSON 必须是对象或数组')
    else:
        pairs = [seg.strip().split('=', 1) for seg in raw.split(';') if '=' in seg]
    result = {}
    for name, value in pairs:
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        name, value = name.strip(), value.strip()
        if not name or not value:
            continue
        SECRETS.append(value)
        if any(ch in name for ch in '\r\n;=') or any(ch in value for ch in '\r\n;'):
            raise TaskError('Cookie 字段包含不允许的控制字符或分隔符')
        result[name.lower()] = (name, value)
    return result


def make_account(cookie, stoken):
    fields = parse_cookie(cookie)
    SECRETS.append(stoken)
    bduss = fields.get('bduss', ('', ''))[1]
    if len(bduss) < 8:
        raise TaskError('缺少完整 BDUSS')
    if not stoken:
        raise TaskError('缺少 genflowpro 产品作用域 STOKEN；不支持本机自动换发')
    if any(ch in stoken for ch in '\r\n;'):
        raise TaskError('STOKEN 格式错误')
    parts = ['BDUSS=' + bduss, 'STOKEN=' + stoken]
    parts += [name + '=' + value for key, (name, value) in fields.items()
              if key not in {'bduss', 'stoken', 'gfprotpl', 'ptoken'}]
    parts.append('gfprotpl=genflowpro')
    return {'cookie': '; '.join(parts)}


def load_accounts():
    accounts = []
    canonical = os.getenv('KUKU_ACCOUNTS', '').strip()
    legacy = os.getenv('KUKU_TOKENS', '').strip()
    if canonical or legacy:
        for line in (canonical or legacy).splitlines():
            if not line.strip():
                continue
            try:
                if canonical:
                    if '|' not in line:
                        raise TaskError('应为 STOKEN|Cookie，每行一个账号')
                    stoken, cookie = line.strip().split('|', 1)
                    account = make_account(cookie, stoken.strip())
                else:
                    parts = line.strip().split('|', 3)
                    if len(parts) != 4:
                        raise TaskError('旧 KUKU_TOKENS 应为 备注|BDUSS|PTOKEN|STOKEN')
                    # 备注不作为官方身份输出，避免用户把敏感信息写入备注。
                    SECRETS.extend(parts[1:])
                    account = make_account('BDUSS=' + parts[1].strip() + '; PTOKEN=' + parts[2].strip(),
                                           parts[3].strip())
                accounts.append(account)
            except TaskError as exc:
                accounts.append({'error': str(exc)})
    elif os.getenv('KUKU_COOKIES', '').strip():
        try:
            accounts.append(make_account(os.environ['KUKU_COOKIES'],
                                         os.getenv('KUKU_STOKEN', '').strip()))
        except TaskError as exc:
            accounts.append({'error': str(exc)})
    return accounts


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不将带凭据的请求重定向至未知目标。
        raise TaskError('业务接口发生重定向，已停止以保护凭据')


class Client:
    def __init__(self, cookie):
        proxy = os.getenv('KUKU_PROXY', '').strip()
        if proxy:
            try:
                parsed = urllib.parse.urlsplit(proxy)
            except ValueError:
                raise TaskError('KUKU_PROXY 格式错误')
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
                raise TaskError('KUKU_PROXY 仅支持有效的 HTTP/HTTPS 代理')
        handler = urllib.request.ProxyHandler({'http': proxy, 'https': proxy} if proxy else {})
        self.opener = urllib.request.build_opener(handler, NoRedirect())
        self.headers = {'Cookie': cookie, 'User-Agent': USER_AGENT,
                        'Referer': BASE_URL + '/genflowpro', 'Origin': BASE_URL,
                        'Accept-Language': 'zh-CN,zh;q=0.9'}

    def request(self, path, task=None):
        if enabled('KUKU_DRY_RUN'):
            raise TaskError('预演禁止网络访问')
        headers = dict(self.headers)
        body = None
        if task:
            body = urllib.parse.urlencode({'task_type': task}).encode('utf-8')
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        req = urllib.request.Request(BASE_URL + path + '?' + WEB_QUERY,
                                     data=body, headers=headers, method='POST' if task else 'GET')
        try:
            with self.opener.open(req, timeout=30) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态不成功')
                raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('业务响应超出大小限制')
            value = json.loads(raw.decode('utf-8'))
        except TaskError:
            raise
        except Exception:
            # 不打印异常文本、响应正文或请求 URL，避免带出凭据。
            raise TaskError('网络、HTTP 或 JSON 响应异常')
        if not isinstance(value, dict) or type(value.get('errno')) is not int:
            raise TaskError('响应缺少有效业务状态码')
        if value['errno'] != 0:
            if value['errno'] == -6:
                raise TaskError('业务未登录：请更新同账号产品作用域 STOKEN')
            raise TaskError('业务返回非成功状态码')
        return value


def show_identity(value):
    # 只读取明确的非敏感身份字段，不输出任意响应对象。
    if not isinstance(value, dict):
        return
    for key in ('nickname', 'username', 'display_name', 'displayName', 'uid', 'public_uid'):
        identity = value.get(key)
        if isinstance(identity, (str, int)) and not isinstance(identity, bool) and str(identity):
            if key not in {'uid', 'public_uid'} and re.fullmatch(r'(?:\+?86[- ]?)?1[3-9]\d{9}', str(identity)):
                log('官方身份字段为手机号，已隐藏')
            else:
                log('官方账号身份（%s）：%s' % (key, identity))
    for key in ('data', 'user', 'user_info', 'userinfo', 'account'):
        if isinstance(value.get(key), dict):
            show_identity(value[key])


def run_account(index, account, dry):
    started = time.monotonic()
    counts = dict(total=3, success=0, alreadyComplete=0, skipped=0, failed=0)
    log('账号 %d 开始' % index)
    client = None
    for stage, label in enumerate(('参数与积分面板',) + tuple(x[1] for x in DAILY_TASKS), 1):
        tick = time.monotonic()
        log('账号 %d · 阶段 %d/3 · %s' % (index, stage, label))
        result = 'failure'
        if stage > 1 and client is None:
            counts['skipped'] += 1
            result = 'skipped'
            log('⏭️ 前置检查失败，未发起领取')
        else:
            try:
                if stage == 1:
                    if 'error' in account:
                        raise TaskError(account['error'])
                    client = Client(account['cookie'])
                    if dry:
                        log('✅ 预演：凭据格式检查通过；未查询面板')
                    else:
                        show_identity(client.request('/api/genflowpro/freepoint/homenew'))
                        log('✅ 积分面板 HTTP 与业务状态检查通过')
                    counts['success'] += 1
                    result = 'success'
                elif dry:
                    counts['skipped'] += 1
                    result = 'skipped'
                    log('⏭️ 预演：将以 POST 领取 %s 奖励；未执行业务操作' % DAILY_TASKS[stage - 2][0])
                else:
                    value = client.request('/api/genflowpro/freepoint/taskComplete', DAILY_TASKS[stage - 2][0])
                    show_identity(value)
                    data = value.get('data')
                    if not isinstance(data, dict) or str(data.get('complete_status', '')).upper() != 'SUCCESS':
                        raise TaskError('奖励接口没有明确的 SUCCESS 完成状态')
                    reward = data.get('reward_point')
                    if isinstance(reward, str) and reward.isascii() and reward.isdigit():
                        reward = int(reward)
                    if type(reward) is not int or reward < 0:
                        raise TaskError('奖励积分字段缺失或无效')
                    if reward == 0:
                        counts['alreadyComplete'] += 1
                        result = 'alreadyComplete'
                        log('☑️ 已完成，无新增积分（业务状态 SUCCESS）')
                    else:
                        counts['success'] += 1
                        result = 'success'
                        log('✅ 领取成功，积分 +%d' % reward)
            except TaskError as exc:
                counts['failed'] += 1
                log('❌ ' + str(exc))
                if stage == 1:
                    client = None
        log('阶段结果：%s；耗时 %.2f 秒' % (result, time.monotonic() - tick))
    counts['seconds'] = round(time.monotonic() - started, 2)
    log(('账号 %d 统计：' % index) + ('总任务 %(total)d，成功 %(success)d，已完成 %(alreadyComplete)d，'
        '跳过 %(skipped)d，失败 %(failed)d，耗时 %(seconds).2f 秒' % counts))
    return counts


def _notify_summary(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1') or os.getenv('KUKU_NO_NOTIFY', '').strip() == '1':
        log('通知：已按环境开关关闭')
        return 'disabled'
    if dry:
        log('通知：断网预演，拟发送摘要：' + body)
        return 'dry-run'
    sender = None
    try:
        module = importlib.import_module('notify')
        sender = getattr(module, 'send', None)
    except Exception:
        pass
    if not callable(sender):
        paths = ['/ql/data/scripts/notify.py', '/ql/scripts/notify.py']
        directory = os.getenv('QINGLONG_NOTIFY_DIR', '').strip()
        if directory:
            paths.insert(0, os.path.join(directory, 'notify.py'))
        for path in paths:
            if not os.path.isfile(path):
                continue
            try:
                spec = importlib.util.spec_from_file_location('_qinglong_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                sender = getattr(module, 'send', None)
                if callable(sender):
                    break
            except Exception:
                continue
    if not callable(sender):
        log('⚠️ 通知模块不可用，保留业务退出码')
        return 'unavailable'
    try:
        sender('KukuAI 每日积分', body)
        log('通知：已调用青龙通知模块')
        return 'sent'
    except Exception:
        log('⚠️ 通知发送失败，保留业务退出码')
        return 'failed'


def notify_summary(body, dry):
    if dry or not enabled('QINGLONG_NOTIFY', '1') or os.getenv('KUKU_NO_NOTIFY', '').strip() == '1':
        return _notify_summary(body, dry)
    # 第三方通知模块可能输出发送地址或自身配置，禁止其日志进入业务输出。
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = _notify_summary(body, dry)
    except (Exception, SystemExit):
        result = 'failed'
    log('通知状态：%s（保留业务退出码）' % result)
    return result


def main():
    start = time.monotonic()
    dry = enabled('KUKU_DRY_RUN')
    log('========== KukuAI 每日积分 ==========')
    log('开始时间：' + datetime.datetime.now().isoformat(timespec='seconds'))
    log('运行模式：' + ('断网预演' if dry else '正式领取'))
    accounts = load_accounts()
    selected = list(enumerate(accounts, 1))
    error = ''
    args = sys.argv[1:]
    if args:
        if len(args) == 2 and args[0] == '--only' and args[1].isdigit() and 1 <= int(args[1]) <= len(accounts):
            selected = [(int(args[1]), accounts[int(args[1]) - 1])]
        else:
            error = ('--token 换发及令牌输出已停用，请显式配置 STOKEN' if '--token' in args
                     else '参数错误：仅支持 --only 和有效账号序号')
    if not accounts:
        error = '未配置 KUKU_ACCOUNTS 或兼容凭据输入'
    log('账号数量：配置 %d，本次选择 %d' % (len(accounts), len(selected)))
    results = []
    if error:
        log('❌ 配置错误：' + error)
    else:
        for index, account in selected:
            results.append(run_account(index, account, dry))
    failed = sum(item['failed'] > 0 for item in results)
    success = len(results) - failed
    code = 1 if error or failed else 0
    status = ('configuration-error' if error else 'partial-failure' if failed and success
              else 'failure' if failed else 'dry-run' if dry else 'success')
    totals = {key: sum(item[key] for item in results)
              for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    body = '状态：%s；账号总数 %d，成功 %d，失败 %d；子任务成功 %d，已完成 %d，跳过 %d，失败 %d' % (
        status, len(selected), success, failed + (len(selected) if error else 0), totals['success'],
        totals['alreadyComplete'], totals['skipped'], totals['failed'])
    notification = notify_summary(body, dry)
    finish = datetime.datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log('最终任务统计：' + body)
    log('总耗时：%.2f 秒；完成时间：%s；通知状态：%s；最终状态：%s' % (
        time.monotonic() - start, finish, notification, status))
    summary = {'task': 'kukuai', 'status': status, 'mode': 'dry-run' if dry else 'live',
               'accounts': len(selected), 'success': success,
               'failed': failed + (len(selected) if error else 0), 'configurationError': bool(error),
               'stages': totals, 'notification': notification, 'exitCode': code,
               'seconds': round(time.monotonic() - start, 2), 'finishedAt': finish}
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
