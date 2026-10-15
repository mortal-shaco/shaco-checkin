#!/usr/bin/env python3
# name: 阴阳师官网原画与CG素材
# cron: 28 9 * * 0
# SPDX-License-Identifier: MIT
# 来源：cloudcranes/some_scripts，阴阳师/get_yys_imagelinks.py、get_yys_cgvideo.py
# 上游两个源文件未包含额外版权或许可声明；保留来源归属。
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
"""公开素材任务，无账号或凭据。默认只列出官网原画，不写入文件。

依赖：仅 Python 3 标准库（建议 Python 3.9 或更新版本）。
YYS_TASKS=images（默认）、videos 或 images,videos；YYS_DOWNLOAD=1 才下载。
YYS_IMAGE_DIR 默认 ./yys原画；YYS_VIDEO_DIR 默认 ./yys视频。
视频目录内 downloaded_videos.txt 保留已下载标题记录；实际文件也须通过格式检查。
YYS_VIDEO_LIMIT 默认 0（全部未下载视频），YYS_VIDEO_INTERVAL 默认 2 秒。
YYS_DRY_RUN=1 完全断网，不创建目录，不调用实际通知服务。
QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭通知。可用 QINGLONG_NOTIFY_DIR
指定青龙自带 notify.py 目录。预演时输出脱敏通知摘要。
上游无 cron；本维护版采用每周日 09:00，可在青龙修改。
"""

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import tempfile
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener


TITLE = "阴阳师官网原画与CG素材"
PAGES = {"images": "https://yys.163.com/media/picture.html",
         "videos": "https://yys.163.com/media/video.html"}
DISABLED = {"0", "false", "no", "off"}
ENABLED = {"1", "true", "yes", "on"}
TIMEOUT = 20
PAGE_LIMIT = 4 * 1024 * 1024
MEDIA_LIMIT = 512 * 1024 * 1024


class TaskError(Exception):
    pass


class Element:
    def __init__(self, tag="", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def get(self, key):
        return self.attrs.get(key)

    def __getitem__(self, key):
        return self.attrs[key]

    def descendants(self):
        for child in self.children:
            if isinstance(child, Element):
                yield child
                yield from child.descendants()

    def find_all(self, tag):
        return [node for node in self.descendants() if node.tag == tag]

    def select(self, selector):
        tag, _, css_class = selector.partition(".")
        return [node for node in self.descendants()
                if (not tag or node.tag == tag)
                and (not css_class or css_class in (node.get("class") or "").split())]

    def select_one(self, selector):
        return next(iter(self.select(selector)), None)

    def get_text(self, strip=False):
        pieces = []
        for child in self.children:
            value = child.get_text(strip) if isinstance(child, Element) else child
            pieces.append(value.strip() if strip else value)
        return "".join(pieces)


class PageParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def flag(name, default="0"):
    value = os.environ.get(name, default).strip().lower()
    if value not in DISABLED | ENABLED:
        raise TaskError(f"{name} 必须为 1/0 或 true/false")
    return value in ENABLED


def safe_url(value, base=None):
    value = urljoin(base, value) if base else value
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.port not in (None, 443)):
        raise TaskError("素材链接必须是无凭据的 HTTPS 地址")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


class SecureRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def request(url):
    url = safe_url(url)
    response = build_opener(SecureRedirect()).open(
        Request(url, headers={"User-Agent": "Mozilla/5.0 Qinglong-YYS-Media/1.0"}),
        timeout=TIMEOUT)
    if response.status != 200:
        response.close()
        raise TaskError("HTTP 状态不是 200")
    safe_url(response.geturl())
    return response


def page_text(url):
    with request(url) as response:
        data = response.read(PAGE_LIMIT + 1)
    if not data or len(data) > PAGE_LIMIT:
        raise TaskError("页面为空或超过大小限制")
    try:
        return data.decode("utf-8")
    except UnicodeError:
        raise TaskError("页面编码不是 UTF-8") from None


def public_title(value):
    return re.sub(r"[\x00-\x1f\x7f]", " ", value).strip()[:100]


def filename(url, kind, title, used):
    digest = hashlib.sha256(url.encode()).hexdigest()[:12]
    if kind == "images":
        match = re.search(r"/(\d+/\d+)/", urlsplit(url).path)
        stem = match.group(1).replace("/", "_") if match else "image_" + digest
        extension = ".jpg"
    else:
        stem = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", title).strip(" .")[:100]
        stem = stem or "video_" + digest
        extension = ".mp4"
    name = stem + extension
    if name in used and used[name] != url:
        name = stem + "_" + digest + extension
    used[name] = url
    return name


def parse_media(html, kind):
    parser = PageParser()
    parser.feed(html)
    parser.close()
    soup = parser.root
    tabs = soup.select("div.tab-cont" if kind == "images" else ".tab-cont")
    if not tabs:
        raise TaskError("页面结构变化：未找到 tab-cont")
    raw = []
    if kind == "images":
        for mask in tabs[0].select("div.mask"):
            links = mask.find_all("a")
            if len(links) == 6 and links[2].get("href"):
                raw.append((links[2]["href"], "原画"))
    else:
        for tab in tabs:
            for item in tab.select(".item2"):
                media, title = item.select_one(".item"), item.select_one(".title")
                if media is None or not media.get("data-src") or title is None:
                    raise TaskError("页面结构变化：视频缺少链接或标题")
                raw.append((media["data-src"], public_title(title.get_text(strip=True))))
    if not raw:
        raise TaskError("未提取到素材，不能判定成功")
    seen, used, result = set(), {}, []
    for link, title in raw:
        url = safe_url(link, PAGES[kind])
        if url not in seen:
            seen.add(url)
            result.append((url, title, filename(url, kind, title, used)))
    return result


def valid_media(prefix, kind):
    if kind == "images":
        return (prefix.startswith(b"\xff\xd8\xff") or prefix.startswith(b"\x89PNG\r\n\x1a\n")
                or (prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"))
    return len(prefix) >= 12 and prefix[4:8] == b"ftyp"


def download(url, path, kind):
    if path.is_symlink():
        raise TaskError("目标为符号链接，拒绝写入")
    if path.exists():
        with path.open("rb") as stream:
            if not valid_media(stream.read(32), kind):
                raise TaskError("已有文件未通过素材格式检查，请人工检查")
        return "alreadyComplete"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with request(url) as response:
            length = response.headers.get("Content-Length")
            expected = int(length) if length else None
            if expected is not None and not 0 < expected <= MEDIA_LIMIT:
                raise TaskError("素材大小超出限制")
            prefix = response.read(32)
            if not valid_media(prefix, kind):
                raise TaskError("响应不是预期的图片或 MP4 视频")
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".yys-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(prefix)
                total = len(prefix)
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MEDIA_LIMIT:
                        raise TaskError("素材超过大小限制")
                    stream.write(chunk)
                if expected is not None and total != expected:
                    raise TaskError("素材传输不完整")
                stream.flush()
                os.fsync(stream.fileno())
        # 硬链接发布完整文件，不覆盖并发任务或用户已有文件。
        os.link(temporary, path)
        return "success"
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def video_history(folder):
    path = folder / "downloaded_videos.txt"
    if path.is_symlink():
        raise TaskError("视频历史文件为符号链接，拒绝读写")
    names = set(path.read_text(encoding="utf-8").splitlines()) if path.exists() else set()
    return path, names


def record_video(path, names, title):
    if title in names:
        return
    if path.is_symlink():
        raise TaskError("视频历史文件为符号链接，拒绝写入")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(title + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    names.add(title)


def notify_summary(body, dry):
    if os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in DISABLED:
        log("通知：已关闭")
        return "disabled"
    if dry:
        log("通知预演（未联网）：" + body)
        return "dry-run"
    helper = '''import importlib, importlib.util, json, os, sys
from pathlib import Path
try:
    module = importlib.import_module("notify")
except ImportError:
    paths = []
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    path = next((p for p in paths if p.is_file()), None)
    if path is None:
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
title, body = json.load(sys.stdin)
module.send(title, body)
'''
    try:
        subprocess.run([sys.executable, "-c", helper],
                       input=json.dumps([TITLE, body]), text=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=30, check=True)
        log("通知：已发送")
        return "sent"
    except Exception:
        log("⚠️ 通知不可用或发送失败，保留业务退出码")
        return "unavailable"


def main():
    started = time.monotonic()
    counts = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
    dry = os.environ.get("YYS_DRY_RUN", "0").strip().lower() in ENABLED
    status, exit_code = "failure", 1
    log("=== " + TITLE + " ===")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry else '正式'}；账号数：0（公开素材，无需登录）")
    try:
        config_start = time.monotonic()
        log("阶段 1：参数检查")
        dry = flag("YYS_DRY_RUN")
        enabled = flag("YYS_DOWNLOAD")
        tasks = list(dict.fromkeys(os.environ.get("YYS_TASKS", "images").split(",")))
        if not tasks or any(t not in PAGES for t in tasks):
            raise TaskError("YYS_TASKS 仅支持 images、videos 或 images,videos")
        try:
            limit = int(os.environ.get("YYS_VIDEO_LIMIT", "0"))
            interval = float(os.environ.get("YYS_VIDEO_INTERVAL", "2"))
            if limit < 0 or not 0 <= interval <= 3600:
                raise ValueError()
        except ValueError:
            raise TaskError("视频数量须为非负整数，间隔须为 0 至 3600 秒") from None
        folders = {"images": Path(os.environ.get("YYS_IMAGE_DIR", "./yys原画")),
                   "videos": Path(os.environ.get("YYS_VIDEO_DIR", "./yys视频"))}
        log("阶段 1 完成；下载写入：" + ("开启" if enabled else "关闭，仅列出素材")
            + f"；耗时 {time.monotonic()-config_start:.2f} 秒")
        for index, kind in enumerate(tasks, 2):
            stage_start = time.monotonic()
            before = counts.copy()
            label = "原画" if kind == "images" else "CG 视频"
            log(f"阶段 {index}：{label} 读取与处理")
            try:
                if dry:
                    fixture = ('<div class="tab-cont"><div class="mask">' +
                               '<a></a><a></a><a href="https://yys.163.com/2026/10/test.jpg"></a>' +
                               '<a></a><a></a><a></a></div></div>') if kind == "images" else (
                               '<div class="tab-cont"><div class="item2"><div class="item" '
                               'data-src="https://yys.163.com/test.mp4"></div>'
                               '<div class="title">CG预演素材</div></div></div>')
                    media = parse_media(fixture, kind)
                    for _, _, name in media:
                        log(f"⏭️ 断网预演解析通过：{name}；不检查或写入本地素材")
                        counts["skipped"] += 1
                else:
                    media = parse_media(page_text(PAGES[kind]), kind)
                    log(f"页面与结构核验通过；发现 {len(media)} 项{label}")
                    downloaded = 0
                    history, history_names = video_history(folders[kind]) if kind == "videos" and enabled else (None, set())
                    for url, title, name in media:
                        step_start = time.monotonic()
                        if not enabled:
                            log(f"✅ 素材已确认：{name}")
                            counts["success"] += 1
                            continue
                        if kind == "videos" and limit and downloaded >= limit:
                            counts["skipped"] += 1
                            log(f"⏭️ 达到视频数量限制：{name}")
                            continue
                        try:
                            result = download(url, folders[kind] / name, kind)
                            if kind == "videos":
                                record_video(history, history_names, title)
                            counts[result] += 1
                            log(f"{'☑️ 已存在，跳过下载' if result == 'alreadyComplete' else '✅ 下载成功'}：{name}；耗时 {time.monotonic()-step_start:.2f} 秒")
                            if kind == "videos" and result == "success":
                                downloaded += 1
                                time.sleep(interval)
                        except Exception as exc:
                            counts["failure"] += 1
                            message = str(exc) if isinstance(exc, TaskError) else "请求或文件操作失败（详情已脱敏）"
                            log(f"❌ 素材处理失败：{name}；{message}")
            except Exception as exc:
                counts["failure"] += 1
                message = str(exc) if isinstance(exc, TaskError) else "页面请求或解析失败（详情已脱敏）"
                log("❌ " + label + "：" + message)
            delta = {k: counts[k] - before[k] for k in counts}
            log(f"阶段 {index} 统计：总任务 {sum(delta.values())}；成功 {delta['success']}；已完成 {delta['alreadyComplete']}；跳过 {delta['skipped']}；失败 {delta['failure']}；耗时 {time.monotonic()-stage_start:.2f} 秒")
        if counts["failure"]:
            status = "partial-failure" if counts["success"] or counts["alreadyComplete"] else "failure"
        else:
            status, exit_code = ("dry-run" if dry else "success"), 0
    except Exception as exc:
        counts["failure"] += 1
        status = "configuration-error"
        message = str(exc) if isinstance(exc, TaskError) else "配置或运行环境错误（详情已脱敏）"
        log("❌ " + message)
    log("----------------------------------------")
    body = (f"账号总数 0，成功账号 0，失败账号 0（无需账号）；任务状态 {status}；"
            f"成功 {counts['success']}，已完成 {counts['alreadyComplete']}，"
            f"跳过 {counts['skipped']}，失败 {counts['failure']}")
    notification = notify_summary(body, dry)
    finished = datetime.now().isoformat(timespec="seconds")
    elapsed = round(time.monotonic() - started, 3)
    log(body)
    log(f"总任务 {sum(counts.values())}；总耗时 {elapsed} 秒；完成时间 {finished}；最终状态 {status}；通知状态 {notification}")
    summary = dict(task=TITLE, status=status, accounts=0, successfulAccounts=0,
                   failedAccounts=0, totalTasks=sum(counts.values()), **counts,
                   durationSeconds=elapsed, finishedAt=finished, notification=notification,
                   exitCode=exit_code)
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
