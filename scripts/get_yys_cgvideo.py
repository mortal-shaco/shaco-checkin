#!/usr/bin/env python3
# name: 阴阳师官网视频与原画
# cron: 11 9 * * 0
# SPDX-License-Identifier: MIT
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
# 原始来源：qluser-alan/some_scripts，阴阳师/get_yys_cgvideo.py、get_yys_imagelinks.py
# 原始版本：f62b50fe0a961ea8a8707682723b080c0a5d1142；保留 MIT 授权。
# 必填 YYS_OUTPUT_DIR：自行选择的本地保存目录，无需登录或凭据。
# YYS_TASKS=video（默认）/image/video,image；YYS_DOWNLOAD=1 才写入资源。
# YYS_LIMIT=0 为全部，每项任务独立限额；YYS_DRY_RUN=1 完全断网且不写资源。
# 原脚本没有定时声明；此处建议每周日 09:00 检查。安装仅需 Python 3 标准库。

# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('8edbbefea99ad1fb', 'scripts/get_yys_cgvideo.py', 'get_yys_cgvideo.py', 'get_yys_cgvideo')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import contextlib
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

TITLE = '阴阳师官网视频与原画'
BASE = 'https://yys.163.com/media/'
FALSE = {'0', 'false', 'no', 'off'}


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children, self.texts = tag, dict(attrs), [], []

    def find(self, cls=None, tag=None):
        result = []
        for child in self.children:
            if (cls is None or cls in (child.attrs.get('class') or '').split()) and (tag is None or child.tag == tag):
                result.append(child)
            result.extend(child.find(cls, tag))
        return result

    def text(self):
        return ''.join(x if isinstance(x, str) else x.text() for x in self.texts)


class Document(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        self.stack[-1].texts.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].texts.append(data)


def safe_url(url, base):
    value = urljoin(base, url)
    parts = urlsplit(value)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise ValueError('资源链接不是无凭据 HTTPS 链接')
    return value


def extract(html, task):
    page = BASE + ('video.html' if task == 'video' else 'picture.html')
    containers = Document(html).root.find('tab-cont')
    items = []
    if task == 'video':
        for container in containers:
            for entry in container.find('item2'):
                links, titles = entry.find('item'), entry.find('title')
                if not links or not titles or not links[0].attrs.get('data-src'):
                    raise ValueError('视频条目字段缺失')
                title = titles[0].text().strip()
                if not title:
                    raise ValueError('视频标题为空')
                items.append((title, safe_url(links[0].attrs['data-src'], page)))
    elif containers:
        for mask in containers[0].find('mask'):
            anchors = mask.find(tag='a')
            if len(anchors) == 6:
                href = anchors[2].attrs.get('href')
                if not href:
                    raise ValueError('原画条目链接缺失')
                url = safe_url(href, page)
                match = re.search(r'/(\d+/\d+)/', url)
                title = match.group(1).replace('/', '_') if match else 'unknown_filename'
                items.append((title, url))
    if not items:
        raise ValueError('页面未解析到资源，不能确认接口成功')
    unique, seen = [], set()
    for title, url in items:
        key = title if task == 'video' else url
        if key not in seen:
            seen.add(key)
            unique.append((title, url))
    return unique


def request(url):
    response = urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'identity'}), timeout=20)
    if response.status != 200 or urlsplit(response.geturl()).scheme != 'https':
        response.close()
        raise ValueError('HTTP 状态或跳转协议异常')
    return response


def page_text(task):
    with request(BASE + ('video.html' if task == 'video' else 'picture.html')) as response:
        content = response.read(4 * 1024 * 1024 + 1)
        if len(content) > 4 * 1024 * 1024:
            raise ValueError('页面超过大小限制')
        return content.decode('utf-8-sig')


def filename(title, url, task):
    clean = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', title).strip(' .')[:90] or 'resource'
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f'{clean}_{digest}.{"mp4" if task == "video" else "jpg"}'


def file_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path, data):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def download(url, destination, task):
    if destination.exists():
        raise ValueError('目标文件已存在但未经清单验证，保留文件并停止该资源')
    tmp = None
    try:
        with request(url) as response, tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            tmp = Path(stream.name)
            length = response.headers.get('Content-Length')
            mime = response.headers.get('Content-Type', '').split(';')[0].lower()
            if mime in {'text/html', 'application/json'}:
                raise ValueError('资源接口返回非媒体内容')
            count, first = 0, b''
            for chunk in iter(lambda: response.read(65536), b''):
                if not first:
                    first = chunk[:64]
                count += len(chunk)
                if count > 2 * 1024 ** 3:
                    raise ValueError('资源超过 2 GiB 限制')
                stream.write(chunk)
            if not count or (length and count != int(length)):
                raise ValueError('资源为空或传输不完整')
            valid = b'ftyp' in first[:32] if task == 'video' else first.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'GIF8')) or (first[:4] == b'RIFF' and first[8:12] == b'WEBP')
            if not valid:
                raise ValueError('媒体文件签名校验失败')
            stream.flush()
            os.fsync(stream.fileno())
        # 硬链接原子创建，拒绝覆盖同名文件。
        os.link(tmp, destination)
        return {'bytes': count, 'sha256': file_digest(destination)}
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def notify(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').lower() in FALSE:
        return '已关闭'
    if dry:
        return '预演已模拟通知；未调用外部通知模块'
    body = f"模式：{summary['mode']}；账号总数：0（公开资源任务）；成功数：{summary['success']}；失败数：{summary['failed']}；跳过数：{summary['skipped']}；状态：{summary['status']}"
    # 捕获通知模块输出，防止第三方通知配置意外泄漏。
    try:
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            try:
                module = importlib.import_module('notify')
            except ImportError:
                paths = [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
                if os.getenv('QINGLONG_NOTIFY_DIR'):
                    paths.insert(0, Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
                path = next((p for p in paths if p.is_file()), None)
                if path is None:
                    return '通知模块不可用，保留业务退出码'
                spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            module.send(TITLE, body)
        return '已调用青龙通知'
    except Exception:
        return '通知失败，保留业务退出码'


def main():
    started = time.monotonic()
    dry = os.getenv('YYS_DRY_RUN', '0') == '1'
    writing = os.getenv('YYS_DOWNLOAD', '0') == '1'
    summary = dict(mode='断网预演' if dry else ('下载' if writing else '仅列出'), accounts=0, success=0, failed=0, skipped=0, alreadyComplete=0)
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{datetime.now().isoformat(timespec="seconds")}；模式：{summary["mode"]}；账号数：0（无需账号）')
    try:
        log('阶段 1：检查参数')
        output = os.getenv('YYS_OUTPUT_DIR', '').strip()
        if not output:
            raise ValueError('必须设置 YYS_OUTPUT_DIR 为本地保存目录')
        tasks = list(dict.fromkeys(os.getenv('YYS_TASKS', 'video').split(',')))
        if not tasks or any(t not in {'video', 'image'} for t in tasks):
            raise ValueError('YYS_TASKS 仅支持 video、image 或 video,image')
        limit = int(os.getenv('YYS_LIMIT', '0'))
        if limit < 0:
            raise ValueError('YYS_LIMIT 必须为非负整数')
        root = Path(output).expanduser().resolve()
        for number, task in enumerate(tasks, 2):
            begin = time.monotonic()
            before = {k: summary[k] for k in ('success', 'failed', 'skipped')}
            log(f'阶段 {number}：{"视频" if task == "video" else "原画"}资源')
            try:
                if dry:
                    html = '<div class="tab-cont"><div class="item2"><a class="item" data-src="https://yys.163.com/demo.mp4"></a><span class="title">预演视频</span></div></div>' if task == 'video' else '<div class="tab-cont"><div class="mask">' + ''.join('<a href="https://yys.163.com/2026/10/demo.jpg" target="_blank">原画</a>' for _ in range(6)) + '</div></div>'
                    entries = extract(html, task)
                else:
                    entries = extract(page_text(task), task)
                log(f'资源页面解析成功：{len(entries)} 条')
                folder = root / task
                manifest_path = folder / 'downloaded_resources.json'
                manifest = {}
                if writing and not dry:
                    folder.mkdir(parents=True, exist_ok=True)
                    if manifest_path.exists():
                        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                        if not isinstance(manifest, dict):
                            raise ValueError('下载清单格式错误')
                downloaded = 0
                for index, (title, url) in enumerate(entries, 1):
                    if limit and downloaded >= limit:
                        break
                    try:
                        name = filename(title, url, task)
                        public_title = re.sub(r'[\x00-\x1f\x7f]', ' ', title)[:120]
                        log(f'资源 {index} 标题：{public_title}')
                        if dry or not writing:
                            log(f'资源 {index}：{"DRY_RUN_OK 参数与解析验证通过" if dry else "HTTPS 链接已解析；未开启下载"}')
                            summary['success'] += 1
                            downloaded += 1
                            continue
                        destination = folder / name
                        record = manifest.get(name)
                        if record and destination.is_file() and destination.stat().st_size == record.get('bytes') and file_digest(destination) == record.get('sha256'):
                            log(f'资源 {index}：☑️ 文件大小与摘要已验证，跳过')
                            summary['skipped'] += 1
                            summary['alreadyComplete'] += 1
                            continue
                        manifest[name] = download(url, destination, task)
                        atomic_json(manifest_path, manifest)
                        log(f'资源 {index}：✅ 下载完整且媒体签名验证通过')
                        summary['success'] += 1
                        downloaded += 1
                        if task == 'video':
                            time.sleep(2)
                    except Exception:
                        log(f'资源 {index}：❌ 下载或清单校验失败（隐藏链接及异常原文）')
                        summary['failed'] += 1
            except Exception:
                log('❌ 资源任务失败：网络、页面结构或本地清单异常（未输出原始响应）')
                summary['failed'] += 1
            log(f'阶段 {number} 统计：成功 {summary["success"]-before["success"]}；跳过 {summary["skipped"]-before["skipped"]}；失败 {summary["failed"]-before["failed"]}；耗时 {time.monotonic()-begin:.2f} 秒')
    except Exception:
        log('❌ 配置错误：请检查必填目录、任务开关和非负整数数量参数')
        summary['failed'] += 1
        summary['configurationError'] = True
    code = 1 if summary['failed'] else 0
    summary['status'] = 'configuration-error' if summary.get('configurationError') else ('partial-failure' if code and summary['success'] else 'failure' if code else 'dry-run' if dry else 'success')
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['notification'] = notify(summary, dry)
    summary['finishTime'] = datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log(f'任务统计：账号 0；成功 {summary["success"]}；已完成 {summary["alreadyComplete"]}；跳过 {summary["skipped"]}；失败 {summary["failed"]}；总耗时 {summary["elapsedSeconds"]} 秒')
    log(f'完成时间：{summary["finishTime"]}；通知：{summary["notification"]}；最终状态：{summary["status"]}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
