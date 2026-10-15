#!/usr/bin/env python3
# name: PSNINE 每日祈祷
# cron: 16 0 * * *
# SPDX-License-Identifier: GPL-3.0
# 原始来源：nuthx/auto-sign，src/special/psnine.py
# https://github.com/nuthx/auto-sign (commit a8d2c229bac693daebe1535bca4cfd49733b632d)
# 保留上游 GPL-3.0 授权；本维护版本沿用 GPL-3.0。
"""PSNINE 每日祈祷。PSNINE_ACCOUNTS 每行 psnid|shell，仅分割首个 |。
登录 https://psnine.com 后，在浏览器开发者工具中读取本站 Cookie 的
__Psnine_psnid 和 __Psnine_shell，按上述顺序填写，勿分享凭据。
兼容单账号 PSNID 与 SHELL；规范变量非空时优先使用规范变量。
PSNINE_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
预演只打印通知摘要，不加载可能联网的通知模块。实时模式尝试青龙 notify.py。
上游未声明定时计划，本版本建议每日北京时间 08:00（调度器时区需自行配置）。
"""
import datetime
import importlib
import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

TITLE = 'PSNINE 每日祈祷'
URL = 'https://psnine.com/set/qidao/ajax'
MAX_BYTES = 262144
DISABLED = {'0', 'false', 'no', 'off'}


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


class TaskError(Exception):
    """仅包含可公开的固定错误说明。"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向，未转发凭据')


class ResultHTML(HTMLParser):
    """提取可见文本和上游 div b:nth-child(5) 对应节点。"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.visible = []
        self.days = []
        self.identities = []

    def handle_starttag(self, tag, attrs):
        parent = self.stack[-1] if self.stack else None
        if parent:
            parent['children'] += 1
        attributes = dict(attrs)
        href = attributes.get('href', '')
        identity = tag == 'a' and re.fullmatch(r'(?:https://psnine\.com)?/psnid/[^/?#]+', href) is not None
        self.stack.append({'tag': tag, 'children': 0, 'text': [],
                           'day': bool(tag == 'b' and parent and parent['tag'] == 'div' and parent['children'] == 5),
                           'identity': identity})
        if tag in {'br', 'hr', 'img', 'input', 'meta', 'link', 'wbr', 'area', 'base', 'embed', 'source', 'track', 'param', 'col'}:
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]['tag'] == tag:
                nodes = self.stack[index:]
                del self.stack[index:]
                for node in nodes:
                    value = ''.join(node['text']).strip()
                    if node['day']:
                        self.days.append(value)
                    if node['identity'] and value:
                        self.identities.append(value)
                break

    def handle_data(self, data):
        if any(node['tag'] in {'script', 'style'} for node in self.stack):
            return
        self.visible.append(data)
        for node in self.stack:
            node['text'].append(data)


def parse_result(body):
    parser = ResultHTML()
    parser.feed(body)
    visible = ''.join(parser.visible)
    if any(word in visible for word in ('请登录', '请先登录', '登录后', '签到失败', '祈祷失败')):
        raise TaskError('服务未确认成功，可能登录失效')
    identities = parser.identities
    if '已经签过' in visible:
        return 'alreadyComplete', None, identities
    # 不把任意 HTML、登录页或仅有数字的页面认作业务成功。
    days = [value for value in parser.days if re.fullmatch(r'\d{1,9}', value)]
    if len(days) == 1 and int(days[0]) > 0 and re.search(r'(祈祷|签到)', visible):
        return 'success', int(days[0]), identities
    raise TaskError('接口响应未包含可验证的祈祷成功信息')


def validate_credentials(psnid, shell):
    if not psnid or not shell or any(c in psnid + shell for c in '\r\n;\x00'):
        raise TaskError('账号格式错误：需填写 psnid|shell，字段不能含换行或分号')
    if any(ord(c) < 32 or ord(c) > 126 for c in psnid + shell):
        raise TaskError('Cookie 字段须为可打印的 ASCII 字符')


def do(forum):
    """保留上游 do({psnid, shell}) 入口；返回已核验结果，失败抛出脱敏错误。"""
    psnid, shell = forum.get('psnid', ''), forum.get('shell', '')
    validate_credentials(psnid, shell)
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko',
        'Cookie': f'__Psnine_psnid={psnid}; __Psnine_shell={shell}; __Psnine_qidaodate={int(time.time())}',
    }
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(urllib.request.Request(URL, headers=headers), timeout=15) as response:
            if response.status != 200:
                raise TaskError('接口 HTTP 状态异常')
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise TaskError('接口响应超过大小限制')
            body = data.decode('utf-8', errors='strict')
        return parse_result(body)
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError(f'接口 HTTP 错误：{exc.code}') from None
    except Exception:
        raise TaskError('接口网络、超时或响应编码错误') from None


def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    if dry:
        log('⏭️ 断网预演通知摘要：' + body)
        return '预演仅本地摘要'
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            paths = []
            if os.getenv('QINGLONG_NOTIFY_DIR'):
                paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('qinglong_notification', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
            if module is None:
                return '通知不可用（未找到 notify.py）'
        module.send(TITLE, body)
        return '通知已发送'
    except Exception:
        return '通知失败（业务退出码保持不变）'


def main():
    started = time.monotonic()
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}')
    dry = os.getenv('PSNINE_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    log('模式：' + ('断网预演' if dry else '实时签到'))
    raw = os.getenv('PSNINE_ACCOUNTS', '')
    if raw.strip():
        accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    elif os.getenv('PSNID'):
        accounts = [os.getenv('PSNID', '') + '|' + os.getenv('SHELL', '')]
    else:
        accounts = []
    log(f'账号数量：{len(accounts)}')
    totals = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
    config_error = not accounts
    if config_error:
        log('❌ 阶段 1 配置检查：缺少 PSNINE_ACCOUNTS，耗时 0.00 秒')
    for index, line in enumerate(accounts, 1):
        tick = time.monotonic()
        status = 'failure'
        try:
            log(f'账号 {index} 阶段 1/2 配置检查')
            if '|' not in line:
                raise TaskError('账号格式错误：缺少首个 | 分隔符')
            psnid, shell = line.split('|', 1)
            validate_credentials(psnid, shell)
            log(f'账号 {index} 阶段 1/2 配置有效，耗时 {time.monotonic()-tick:.2f} 秒')
            stage = time.monotonic()
            log(f'账号 {index} 阶段 2/2 每日祈祷')
            if dry:
                status = 'skipped'
                log(f'账号 {index} DRY_RUN_OK：凭据格式通过，未执行网络请求或签到')
            else:
                status, days, identities = do({'psnid': psnid, 'shell': shell})
                for identity in identities:
                    # 身份来自官方公开用户链接，不输出凭据或未验证的响应内容。
                    if shell not in identity and not re.search(r'\d{11,}|[\r\n]', identity):
                        log(f'账号 {index} 官方公开用户名：{identity}')
                log(f'账号 {index} ☑️ 今天已经签过了' if status == 'alreadyComplete' else f'账号 {index} ✅ 已祈祷{days}天')
            log(f'账号 {index} 阶段 2/2 耗时 {time.monotonic()-stage:.2f} 秒')
        except TaskError as exc:
            log(f'账号 {index} ❌ {exc}，阶段耗时 {time.monotonic()-tick:.2f} 秒')
        except Exception:
            log(f'账号 {index} ❌ 执行异常，详情已脱敏，阶段耗时 {time.monotonic()-tick:.2f} 秒')
        totals[status] += 1
        log(f'账号 {index} 统计：总任务 1，成功 {int(status=="success")}，已完成 {int(status=="alreadyComplete")}，跳过 {int(status=="skipped")}，失败 {int(status=="failure")}，耗时 {time.monotonic()-tick:.2f} 秒')
    failed = totals['failure']
    successful = totals['success'] + totals['alreadyComplete']
    exit_code = 1 if config_error or failed else 0
    final = '配置错误' if config_error else ('部分失败' if failed and successful else '失败') if failed else '预演完成' if dry else '成功'
    body = f'状态：{final}；账号总数 {len(accounts)}；成功数 {successful}；失败数 {failed}；预演跳过 {totals["skipped"]}'
    notification = notify(body, dry)
    log('----------------------------------------')
    log(body)
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log('通知状态：' + notification)
    log(f'总耗时：{time.monotonic()-started:.2f} 秒；完成时间：{datetime.datetime.now().isoformat(timespec="seconds")}；最终状态：{final}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'accounts': len(accounts), 'successfulAccounts': successful, 'failedAccounts': failed, 'tasks': totals, 'configurationError': config_error, 'status': final, 'notification': notification, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
