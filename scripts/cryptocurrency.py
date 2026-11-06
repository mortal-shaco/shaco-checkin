#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 加密货币 INR 报价监控
# cron: */5 * * * *
# 来源 https://gitlab.com/imdineshsingh/Cryptocurrency
# 原文件 cryptocurrency.py，提交 d5d3dbf7ddfa711a61739ee9b0df87ecd0eafbcb
# MIT License
# Copyright (c) 2017-2018 Dinesh Singh
#
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
"""公开行情任务，无需账号。

CRYPTO_CURRENCY 必填，BTC/BCH/LTC/DASH/DGB/ZEC 之一。
CRYPTO_TARGET_INR 必填，自行设置大于零的 INR 提醒阈值。
CRYPTO_SAMPLES 默认 1，最多 120 次。可选位置参数为旧版轮询间隔秒数，
也可使用 CRYPTO_REFRESH_SECONDS，默认 60，范围 1 至 3600 秒。
每次启动重新使用配置阈值，同次运行中上涨后抬高阈值，严格大于才提醒。
CRYPTO_DRY_RUN=1 完全断网预演，使用明确标注的固定样例行情。
QINGLONG_NOTIFY=auto|1|0，auto 默认选中此任务，可通过
QINGLONG_NOTIFY_SCRIPTS 的目录路径、文件名、通配符或目录编号筛选。
QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。预演只演示通知，不调用模块。
仅访问上游 https://www.coinome.com/exchange，不执行交易或修改账号。
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
        _ql_notify_identities = ('321f71ffb2ef28ff', 'scripts/cryptocurrency.py', 'cryptocurrency.py', 'cryptocurrency')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import contextlib
from decimal import Decimal, InvalidOperation
import fnmatch
from html.parser import HTMLParser
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request

__author__ = ['Dinesh Singh']
__version__ = '1.0.0'
__copyright__ = 'Copyright (c) 2017-2018 Dinesh Singh'
__license__ = 'MIT'

TITLE = '加密货币 INR 报价监控'
CATALOG_ID = '321f71ffb2ef28ff'
COINS = ('BTC', 'BCH', 'LTC', 'DASH', 'DGB', 'ZEC')
URL = 'https://www.coinome.com/exchange'
MAX_BYTES = 2 * 1024 * 1024
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    """仅包含允许公开的错误描述。"""


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def positive_price(value):
    try:
        price = Decimal(value)
    except (InvalidOperation, ValueError):
        raise TaskError('价格必须为有效正数') from None
    if not price.is_finite() or price <= 0:
        raise TaskError('价格必须为有限正数')
    return price


def integer(value, minimum, maximum, label):
    try:
        result = int(value)
    except ValueError:
        raise TaskError(f'{label}必须为整数') from None
    if not minimum <= result <= maximum:
        raise TaskError(f'{label}超出允许范围 {minimum} 至 {maximum}')
    return result


def configuration(argv):
    if len(argv) > 1:
        raise TaskError('仅支持一个旧版位置参数，表示轮询间隔秒数')
    coin = os.environ.get('CRYPTO_CURRENCY', '').strip().upper()
    if coin not in COINS:
        raise TaskError('请配置 CRYPTO_CURRENCY，可选 BTC/BCH/LTC/DASH/DGB/ZEC')
    threshold = positive_price(os.environ.get('CRYPTO_TARGET_INR', '').strip())
    interval = integer(argv[0] if argv else os.environ.get('CRYPTO_REFRESH_SECONDS', '60'),
                       1, 3600, '轮询间隔')
    samples = integer(os.environ.get('CRYPTO_SAMPLES', '1'), 1, 120, '采样次数')
    return coin, threshold, interval, samples


class RatesParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.parts = []
        self.rates = []

    def handle_starttag(self, tag, attrs):
        if tag == 'span':
            classes = dict(attrs).get('class', '') or ''
            if 'last-market-rate-b' in classes.split():
                if self.capture:
                    raise TaskError('行情页面存在嵌套价格字段')
                self.capture = True
                self.parts = []

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'span' and self.capture:
            text = ''.join(self.parts).strip()
            # 不接受货币符号、脚本片段或非数字内容。
            if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?', text):
                raise TaskError('行情价格字段格式变化')
            self.rates.append(positive_price(text.replace(',', '')))
            self.capture = False


def parse_rates(html):
    parser = RatesParser()
    parser.feed(html)
    parser.close()
    if parser.capture or len(parser.rates) != len(COINS):
        raise TaskError('行情页面不符合上游六币种价格契约，停止判断')
    return dict(zip(COINS, parser.rates))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('行情地址发生跳转，需核验上游接口')


def fetch_rates():
    request = urllib.request.Request(URL, headers={
        'User-Agent': 'Qinglong-Cryptocurrency/1.0',
        'Accept': 'text/html',
        'Accept-Encoding': 'identity',
    })
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            if response.status != 200:
                raise TaskError('行情接口未返回 HTTP 200')
            if response.headers.get_content_type() != 'text/html':
                raise TaskError('行情接口返回类型异常')
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise TaskError('行情响应超过大小限制')
            html = data.decode(response.headers.get_content_charset() or 'utf-8', errors='strict')
        return parse_rates(html)
    except TaskError:
        raise
    except Exception:
        # 异常可能携带地址、代理凭据或原始响应，统一脱敏。
        raise TaskError('行情请求或解析失败，检查网络和上游接口') from None


def notification_selected():
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    if switch != 'auto':
        raise TaskError('QINGLONG_NOTIFY 仅支持 auto 或布尔开关值')
    selectors = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    if selectors is None:
        return True
    names = (CATALOG_ID, Path(__file__).name, str(Path(__file__)), 'cryptocurrency.py')
    return any(fnmatch.fnmatchcase(name, pattern)
               for pattern in re.split(r'[,;\s]+', selectors.strip()) if pattern
               for name in names)


def load_notify():
    try:
        module = importlib.import_module('notify')
        if callable(getattr(module, 'send', None)):
            return module.send
    except Exception:
        pass
    directories = [os.environ.get('QINGLONG_NOTIFY_DIR'), '/ql/data/scripts', '/ql/scripts']
    for directory in directories:
        if not directory:
            continue
        path = Path(directory) / 'notify.py'
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location('qinglong_notify', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if callable(getattr(module, 'send', None)):
            return module.send
    return None


def send_notification(body, dry_run, selected):
    if not selected:
        log('通知已关闭或未被选择')
        return 'disabled'
    if dry_run:
        log('通知预演完成，断网模式未加载或调用通知模块')
        return 'dry-run'
    try:
        # 通知插件可能输出第三方配置或错误内容，阻止其直接写入任务日志。
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            send = load_notify()
            if send is None:
                log_result = 'unavailable'
            else:
                send(TITLE, body)
                log_result = 'sent'
        log('通知已提交' if log_result == 'sent' else '通知模块不可用，保留业务退出码')
        return log_result
    except Exception:
        log('通知发送失败，保留业务退出码')
        return 'failed'


def main(argv=None):
    started = time.monotonic()
    dry_run = os.environ.get('CRYPTO_DRY_RUN', '').strip().lower() in TRUE
    summary = {'task': TITLE, 'mode': 'dry-run' if dry_run else 'live',
               'accounts': 0, 'success': 0, 'failed': 0, 'samples': 0,
               'alerts': 0, 'status': 'configuration-error'}
    lines = []
    exit_code = 1
    selected = True
    log(f'=== {TITLE} ===')
    log(f'开始时间 {time.strftime("%Y-%m-%d %H:%M:%S")}')
    log(f'运行模式 {summary["mode"]}，账号总数 0，公开行情无需账号')
    try:
        stage_started = time.monotonic()
        log('阶段 1/3 校验参数与通知设置')
        coin, threshold, interval, samples = configuration(sys.argv[1:] if argv is None else argv)
        selected = notification_selected()
        summary['status'] = 'failure'
        log(f'阶段 1/3 完成，币种 {coin}，初始阈值 {threshold} INR，采样 {samples} 次，'
            f'耗时 {time.monotonic() - stage_started:.2f} 秒')
        for index in range(samples):
            sample_started = time.monotonic()
            log(f'阶段 2/3 行情采样 {index + 1}/{samples}')
            if dry_run:
                rates = dict(zip(COINS, map(Decimal, ('100', '50', '25', '10', '2', '5'))))
                log('使用固定模拟行情，未执行 HTTP 请求')
            else:
                rates = fetch_rates()
            price_line = ', '.join(f'{symbol}: {rates[symbol]}' for symbol in COINS)
            log(f'{"模拟" if dry_run else "已验证"}报价 (INR) {price_line}')
            lines.append(price_line)
            summary['samples'] += 1
            if rates[coin] > threshold:
                threshold = rates[coin]
                summary['alerts'] += 1
                message = f'*{coin} price increased to {threshold}'
                log(message)
                lines.append(message)
            else:
                log(f'{coin} 未超过当前阈值 {threshold} INR')
            log(f'阶段 2/3 本次成功，耗时 {time.monotonic() - sample_started:.2f} 秒')
            if index + 1 < samples and not dry_run:
                time.sleep(interval)
        summary['success'] = summary['samples']
        summary['status'] = 'dry-run' if dry_run else 'success'
        exit_code = 0
    except TaskError as error:
        log(f'❌ {error}')
        lines.append(str(error))
        summary['failed'] = 1
        if summary['samples']:
            summary['status'] = 'partial-failure'
        elif summary.get('status') != 'configuration-error':
            summary['status'] = 'failure'
    except KeyboardInterrupt:
        log('❌ 任务中断')
        summary['status'] = 'failure'
        summary['failed'] = 1
        exit_code = 130
    except Exception:
        log('❌ 运行异常，已隐藏异常详情')
        summary['status'] = 'failure'
        summary['failed'] = 1
    summary['success'] = summary['samples']
    stage_started = time.monotonic()
    log('阶段 3/3 统计与通知')
    body = (f'账号总数 0，公开行情任务。成功采样 {summary["success"]}，'
            f'失败 {summary["failed"]}，阈值提醒 {summary["alerts"]}，状态 {summary["status"]}\n'
            + '\n'.join(lines))
    summary['notification'] = send_notification(body, dry_run, selected)
    log(f'阶段 3/3 完成，耗时 {time.monotonic() - stage_started:.2f} 秒')
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['finishedAt'] = time.strftime('%Y-%m-%d %H:%M:%S')
    log('----------------------------------------')
    log('账号结果 不适用，公开行情无需凭据')
    log(f'子任务总数 {summary["samples"] + summary["failed"]}，成功 {summary["success"]}，'
        f'已完成 0，跳过 0，失败 {summary["failed"]}')
    log(f'总耗时 {summary["elapsedSeconds"]:.2f} 秒，完成时间 {summary["finishedAt"]}')
    log(f'最终状态 {summary["status"]}，通知状态 {summary["notification"]}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
