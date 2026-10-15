#!/usr/bin/env python3
# name: Wallhaven最新壁纸下载
# cron: 0 2 * * *
# 来源: cloudcranes/some_scripts / Download_wallhaven/main.py
# 上游提交: f62b50fe0a961ea8a8707682723b080c0a5d1142
# 许可: MIT（按任务 effectiveLicense）；输入源码未附版权声明。
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
# 保留上游说明：图片 ID 为六位，前两位用于目录，图片后缀有 jpg 和 png。
"""Wallhaven 最新壁纸下载（Python 3，仅标准库）。
在青龙环境变量中设置 WALLHAVEN_SAVE_DIR 为自己有写权限的壁纸目录；
原脚本目录为 /ql/data/downloads/local-website/img，脚本仍按日期创建子目录。
WALLHAVEN_PAGES 默认 5；上游未定义 cron，此版本提供每天 08:00 的建议计划。
无需 Cookie、Token 或账号；不处理 AList 参数。已有有效图片跳过，绝不覆盖。
WALLHAVEN_DRY_RUN=1 完全断网，不创建目录或图片，也不调用通知模块。
QINGLONG_NOTIFY 默认 1；通知不可用不改变下载退出码。
"""
import datetime as dt
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import time
from html.parser import HTMLParser
from urllib.request import Request, urlopen

TITLE = 'Wallhaven最新壁纸下载'
FALSE = {'0', 'false', 'no', 'off'}


def log(message):
    print(f'[{dt.datetime.now():%H:%M:%S}] {message}', flush=True)


class ListingParser(HTMLParser):
    """沿用上游 thumb-info 的 ID 与 PNG 标记，不猜测业务 API。"""
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.block = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div':
            self.depth += 1
            if 'thumb-info' in attrs.get('class', '').split():
                if self.block is not None:
                    raise ValueError('列表结构不受支持')
                self.block = [self.depth, [], []]
        if self.block is not None:
            self.block[2].extend(str(value or '') for value in attrs.values())
            href = attrs.get('href', '')
            match = re.search(r'(?:/tags/|/wallpaper/)([a-z0-9]{6})(?:[/?#]|$)', href)
            if match:
                self.block[1].append(match.group(1))

    def handle_data(self, data):
        if self.block is not None:
            self.block[2].append(data)

    def handle_endtag(self, tag):
        if tag == 'div':
            if self.block is not None and self.block[0] == self.depth:
                ids = set(self.block[1])
                if len(ids) != 1:
                    raise ValueError('壁纸 ID 缺失或存在歧义')
                ext = 'png' if re.search(r'\bpng\b', ' '.join(self.block[2]), re.I) else 'jpg'
                self.items.append((ids.pop(), ext))
                self.block = None
            self.depth -= 1


def parse_listing(content):
    parser = ListingParser()
    parser.feed(content.decode('utf-8', errors='strict'))
    parser.close()
    if parser.block is not None or not parser.items:
        raise ValueError('壁纸列表为空或结构变化')
    unique = {}
    for image_id, ext in parser.items:
        if image_id in unique and unique[image_id] != ext:
            raise ValueError('图片类型存在歧义')
        unique[image_id] = ext
    return list(unique.items())


def fetch(url, limit, expected):
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Wallhaven scheduled downloader)'})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError('HTTP 状态异常')
        final = response.geturl()
        allowed = ('https://wallhaven.cc/',) if expected == 'text/html' else ('https://w.wallhaven.cc/',)
        if not final.startswith(allowed):
            raise ValueError('响应来源异常')
        content_type = response.headers.get_content_type()
        if content_type != expected:
            raise ValueError('响应类型异常')
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError('响应超出大小限制')
        return content


def valid_image(content, ext):
    if ext == 'png':
        return len(content) > 32 and content.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in content[-16:]
    return len(content) > 16 and content.startswith(b'\xff\xd8\xff') and content.endswith(b'\xff\xd9')


def save_image(folder, image_id, ext):
    destination = folder / f'{image_id}.{ext}'
    if destination.is_symlink():
        raise ValueError('目标为符号链接')
    if destination.exists():
        if not destination.is_file() or destination.stat().st_size > 50 * 1024 * 1024:
            raise ValueError('已有目标无效，拒绝覆盖')
        if not valid_image(destination.read_bytes(), ext):
            raise ValueError('已有图片校验失败，拒绝覆盖')
        return 'alreadyComplete'
    url = f'https://w.wallhaven.cc/full/{image_id[:2]}/wallhaven-{image_id}.{ext}'
    content = fetch(url, 50 * 1024 * 1024, 'image/png' if ext == 'png' else 'image/jpeg')
    if not valid_image(content, ext):
        raise ValueError('图片内容校验失败')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder, prefix='.wallhaven-', delete=False) as handle:
            temporary = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        # 原子发布且禁止覆盖已存在文件。
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            os.unlink(temporary)
    return 'success'


def notify_summary(body, dry_run):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in FALSE:
        return '已关闭'
    if dry_run:
        return '预演：已生成通知摘要，未调用通知以保证断网'
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            paths = []
            if os.getenv('QINGLONG_NOTIFY_DIR'):
                paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
            if module is None:
                return '不可用（未找到 notify.py）'
        module.send(TITLE, body)
        return '已发送'
    except Exception:
        return '发送失败（保持业务退出码）'


def main():
    started = time.monotonic()
    dry_run = os.getenv('WALLHAVEN_DRY_RUN', '0').strip().lower() not in FALSE
    counts = {'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failure': 0}
    account_count = 0  # 公共壁纸下载没有账号契约。
    code = 0
    status = 'dry-run' if dry_run else 'success'
    log(f'===== {TITLE} =====')
    log(f'开始时间：{dt.datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if dry_run else "正式下载"}；账号总数：0（公共任务）')
    try:
        stage = time.monotonic()
        log('阶段 1：参数检查')
        setting = os.getenv('WALLHAVEN_SAVE_DIR', '').strip()
        if not setting:
            raise ValueError('请设置 WALLHAVEN_SAVE_DIR 为有写权限的绝对目录')
        root = Path(setting)
        if not root.is_absolute():
            raise ValueError('WALLHAVEN_SAVE_DIR 必须是绝对目录')
        pages = int(os.getenv('WALLHAVEN_PAGES', '5'))
        if not 1 <= pages <= 100:
            raise ValueError('WALLHAVEN_PAGES 必须是 1 至 100 的整数')
        folder = root / dt.datetime.now().strftime('%Y-%m-%d')
        log(f'✅ 参数检查通过；页数：{pages}；耗时：{time.monotonic() - stage:.2f} 秒')
    except Exception:
        log('❌ 参数错误：需提供 WALLHAVEN_SAVE_DIR 绝对目录及合法 WALLHAVEN_PAGES；未执行下载')
        counts['failure'] += 1
        code, status = 1, 'configuration-error'
    else:
        if dry_run:
            stage = time.monotonic()
            log('阶段 2：断网解析与图片校验预演')
            fixture = b'<div class="thumb-info"><a href="/tags/abc123"><i class="icon"></i></a><span>PNG</span></div>'
            try:
                if parse_listing(fixture) != [('abc123', 'png')]:
                    raise ValueError('解析失败')
                if not valid_image(b'\xff\xd8\xff' + b'fixture' * 3 + b'\xff\xd9', 'jpg'):
                    raise ValueError('校验失败')
                counts['success'] += 1
                log(f'✅ DRY_RUN_OK：列表解析与图片校验通过；未联网、未创建文件；耗时：{time.monotonic() - stage:.2f} 秒')
            except Exception:
                counts['failure'] += 1
                code, status = 1, 'failure'
                log('❌ 预演校验失败')
        else:
            seen = set()
            for page in range(1, pages + 1):
                stage = time.monotonic()
                log(f'阶段 {page + 1}：下载最新壁纸第 {page} 页')
                try:
                    items = parse_listing(fetch(f'https://wallhaven.cc/latest?page={page}', 4 * 1024 * 1024, 'text/html'))
                    # 仅在有效列表返回后创建显式指定目录。
                    folder.mkdir(parents=True, exist_ok=True)
                    log(f'✅ 第 {page} 页列表通过：{len(items)} 张')
                except Exception:
                    counts['failure'] += 1
                    log('❌ 列表请求、解析或目录检查失败；继续其他页（未输出原始响应）')
                    continue
                for image_id, ext in items:
                    if image_id in seen:
                        counts['skipped'] += 1
                        log(f'⏭️ 图片 {image_id}：跨页重复，跳过')
                        continue
                    seen.add(image_id)
                    try:
                        result = save_image(folder, image_id, ext)
                        counts[result] += 1
                        log(f'{"✅" if result == "success" else "☑️"} 图片 {image_id}：{"已下载并校验" if result == "success" else "已有有效图片"}')
                    except Exception:
                        counts['failure'] += 1
                        log(f'❌ 图片 {image_id}：下载或保存校验失败，未覆盖原文件')
                log(f'第 {page} 页结束；耗时：{time.monotonic() - stage:.2f} 秒')
            if counts['failure']:
                code = 1
                status = 'partial-failure' if counts['success'] or counts['alreadyComplete'] else 'failure'
    elapsed = round(time.monotonic() - started, 2)
    total = sum(counts.values())
    body = f'状态：{status}；账号总数：{account_count}；账号成功：0；账号失败：0；子任务总数：{total}；成功：{counts["success"]}；已完成：{counts["alreadyComplete"]}；跳过：{counts["skipped"]}；失败：{counts["failure"]}'
    notification = notify_summary(body, dry_run)
    log('--------------------')
    log(body)
    log(f'通知：{notification}；总耗时：{elapsed} 秒；完成时间：{dt.datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'mode': 'dry-run' if dry_run else 'live', 'status': status, 'accounts': 0, 'tasks': total, **counts, 'elapsedSeconds': elapsed, 'notification': notification, 'exitCode': code}, ensure_ascii=False), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
