# -*- coding: utf-8 -*-
# name: Hax 与 Woiden 可开通区域监控
# cron: 21 */6 * * *
# Upstream: OreosLab/checkinpanel, api_hax.py
# License: MIT (upstream license retained)
"""公开信息监控，无需账号、Cookie 或 Token。
设置 HAX=1 启用（兼容上游 HAX 开关）；HAX_DRY_RUN=1 完全断网预演。
QINGLONG_NOTIFY=0 可关闭通知，QINGLONG_NOTIFY_DIR 可指定青龙通知目录。

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
"""
import datetime
import importlib
import importlib.util
import json
import os
import re
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

TITLE = 'Hax 与 Woiden 可开通区域监控'
FALSE_VALUES = {'0', 'false', 'no', 'off', ''}
MAX_BYTES = 2 * 1024 * 1024


def enabled(name, default='0'):
    return os.environ.get(name, default).strip().lower() not in FALSE_VALUES


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


class Page(HTMLParser):
    """收集卡片、选项及其嵌套文本，无第三方依赖。"""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.entries = []
        self.has_select = False
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'select':
            self.has_select = True
        # HTML permits omission of the closing option tag.
        if tag == 'option' and self.stack and self.stack[-1]['tag'] == 'option':
            self.stack.pop()
        node = {'tag': tag, 'attrs': attrs, 'text': []}
        if tag in {'h5', 'h1', 'option'}:
            self.entries.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]['tag'] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for node in self.stack:
            if node['tag'] in {'h5', 'h1', 'option'}:
                node['text'].append(data)

    def values(self, tag, classes=()):
        return [''.join(n['text']).strip() for n in self.entries
                if n['tag'] == tag and set(classes).issubset(
                    n['attrs'].get('class', '').split())]


class Hax:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run

    def check(self, url):
        if self.dry_run:
            if url.endswith('/data-center'):
                return ('<h5 class="card-title mb-4">SG-KVM</h5>'
                        '<h1 class="card-text">2 VPS</h1>')
            return '<select><option value="SG-KVM">新加坡 (KVM)</option></select>'
        request = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 Qinglong-Hax-Monitor/1.0',
            'Accept': 'text/html',
        })
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200 or not response.geturl().startswith('https://'):
                raise ValueError('HTTP 状态或协议异常')
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('页面超过大小上限')
            return raw.decode(response.headers.get_content_charset() or 'utf-8',
                              errors='strict')

    def get_server_info(self, url):
        page = Page(self.check(url))
        zones = page.values('h5', ('card-title', 'mb-4'))
        counts = page.values('h1', ('card-text',))
        if not zones or len(zones) != len(counts):
            raise ValueError('库存页面结构不匹配')
        groups = {}
        for label, count in zip(zones, counts):
            match = re.fullmatch(r'\s*(\d+)\s*VPS\s*', count)
            if not match or not label:
                raise ValueError('库存字段格式不匹配')
            parts = label.split('-', 1)
            zone = parts[0].lstrip('./')
            value = f'{parts[1]}({match.group(1)}♝)' if len(parts) == 2 else count
            groups.setdefault(zone, []).append(value)
        return ''.join(f'>>{key}-' + ', '.join(values) + '\n'
                       for key, values in groups.items())

    def get_data_center(self, url, vir=False):
        page = Page(self.check(url))
        if not page.has_select:
            raise ValueError('区域页面缺少选择列表')
        centers = [''.join(n['text']).strip() for n in page.entries
                   if n['tag'] == 'option' and re.match(
                       r'^[A-Z]{2,}-', n['attrs'].get('value', ''))]
        if any(not center for center in centers):
            raise ValueError('区域名称为空')
        if not centers:
            return '当前没有可开通区域\n'
        if not vir:
            return '\n'.join(centers) + '\n'
        groups = {}
        for center in centers:
            match = re.fullmatch(r'(.*?)\s+\(([^()]+)\)', center)
            region, kind = match.groups() if match else (center, '未标注类型')
            groups.setdefault(kind, []).append(region)
        return ''.join(f'★{kind}★ ' + ', '.join(regions) + '\n'
                       for kind, regions in groups.items())


def notify(body, dry_run):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    if dry_run:
        log('⏭️ 预演通知：不加载通知模块，不发送网络请求')
        return '预演成功'
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            paths = []
            if os.environ.get('QINGLONG_NOTIFY_DIR'):
                paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                raise ImportError('未找到青龙通知模块')
            spec = importlib.util.spec_from_file_location('qinglong_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.send(TITLE, body)
        return '已发送'
    except Exception:
        log('⚠️ 通知模块不可用或发送失败；保留业务退出码')
        return '不可用或失败'


def main():
    start = time.monotonic()
    dry_run = enabled('HAX_DRY_RUN')
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'运行模式：{"断网预演" if dry_run else "正式查询"}；账号数：0（公开信息任务）')
    client = Hax(dry_run)
    succeeded = failed = skipped = 0
    results = []
    configured = enabled('HAX')
    stages = [
        ('Hax 开通数量', lambda: '[🛰Hax Stats / Hax 开通数据]\n' +
         client.get_server_info('https://hax.co.id/data-center')),
        ('Hax 可开通区域', lambda: '[🚩Available Centers / 可开通区域]\n'
         '---------- <a href="https://hax.co.id/create-vps">Hax</a> ----------\n' +
         client.get_data_center('https://hax.co.id/create-vps', True)),
        ('Woiden 可开通区域', lambda:
         '---------- <a href="https://woiden.id/create-vps">Woiden</a> ----------\n' +
         client.get_data_center('https://woiden.id/create-vps')),
    ]
    if not configured:
        log('❌ 配置错误：请设置非敏感开关 HAX=1')
    for index, (name, action) in enumerate(stages, 1):
        stage_start = time.monotonic()
        log(f'阶段 {index}/3：{name}')
        if not configured:
            skipped += 1
            log('⏭️ 配置未启用，跳过查询')
            continue
        try:
            result = action()
            results.append(result)
            succeeded += 1
            log(f'✅ {name}：页面解析与字段校验通过')
            # Only validated public inventory/region fields, never a raw page.
            print(result, flush=True)
        except Exception:
            failed += 1
            log(f'❌ {name}：网络、HTTP 或页面结构校验失败（不输出原始响应）')
        log(f'阶段耗时：{time.monotonic() - stage_start:.2f} 秒')
    exit_code = 0 if configured and failed == 0 and succeeded == 3 else 1
    status = ('configuration-error' if not configured else
              'partial-failure' if failed and succeeded else
              'failure' if failed else 'dry-run' if dry_run else 'success')
    body = (f'账号总数：0；成功账号：0；失败账号：0（公开信息任务）\n'
            f'子任务：成功 {succeeded}，失败 {failed}，跳过 {skipped}\n'
            f'最终状态：{status}\n' + '\n'.join(results))
    notification = notify(body, dry_run)
    print('----------------------------------------')
    log(f'账号统计：总数 0；成功 0；失败 0；公开查询无需账号')
    log(f'任务统计：总数 3；成功 {succeeded}；已完成 0；跳过 {skipped}；失败 {failed}')
    log(f'总耗时：{time.monotonic() - start:.2f} 秒；通知状态：{notification}')
    log(f'完成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}')
    if exit_code == 0:
        log('HAX_DRY_RUN_OK' if dry_run else 'HAX_MONITOR_SUCCESS')
    print('TASK_SUMMARY=' + json.dumps({
        'status': status, 'mode': 'dry-run' if dry_run else 'live',
        'accounts': 0, 'successAccounts': 0, 'failedAccounts': 0,
        'tasks': 3, 'success': succeeded, 'failed': failed, 'skipped': skipped,
        'alreadyComplete': 0, 'notification': notification, 'exitCode': exit_code,
        'elapsedSeconds': round(time.monotonic() - start, 2),
    }, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
