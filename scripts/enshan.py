#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 恩山无线论坛积分查询
# cron: 0 2 * * *
# 上游原定时：0 0 2 * * *（含秒字段，每天 02:00）
# 来源：cloudcranes/some_scripts，enshan.py
# 上游标识：const $ = new Env('恩山无线论坛积分查询')
# License: MIT; attribution: cloudcranes/some_scripts contributors
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
"""enshanck：每个非空行放一个登录 Cookie，保持整条 Cookie，不使用 & 或 @ 分隔。
在浏览器登录 https://www.right.com.cn/forum/，开发者工具的网络面板中
打开积分页请求，复制请求头 Cookie；请勿复制 Set-Cookie 或发给他人。
ENSHAN_DRY_RUN=1：仅校验配置并预演，不访问论坛、文本服务或通知网络。
QINGLONG_NOTIFY 默认开启；设为 0/false/no/off 可关闭。
仅查询原积分页面，不额外发帖、修改资料或调用未经证实的签到接口。
服务器访问页面产生的登录奖励等由论坛自身规则决定。
"""

import html
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "恩山无线论坛积分查询"
URL = "https://www.right.com.cn/forum/home.php?mod=spacecp&ac=credit&showcredit=1"
DISABLED = {"0", "false", "no", "off"}


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlparse(newurl)
        if target.scheme != "https" or target.hostname != "www.right.com.cn" or target.port not in (None, 443):
            raise ValueError("拒绝向其他站点或非 HTTPS 地址转发凭据")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("br", "p", "li", "div", "em", "span"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def parse_page(page):
    parser = PageText()
    parser.feed(page)
    text = " ".join("".join(parser.parts).split())
    values = []
    for label in ("恩山币", "积分"):
        match = re.search(r"(?:^|\s)" + label + r"\s*[:：]\s*(-?\d+(?:,\d{3})*(?:\.\d+)?)(?=\s|$)", text)
        if not match:
            raise ValueError("未找到完整积分数据：Cookie 可能失效或页面结构改变")
        values.append(match.group(1))
    # Discuz 登录账号链接通常位于 um 区域的 strong 标签内。
    identity = None
    area = re.search(r'<(?:div|nav)\b[^>]*\bid=[\"\']um[\"\'][^>]*>(.*?)(?:</div>|</nav>)', page, re.S | re.I)
    if area:
        anchor = re.search(r'<strong\b[^>]*>\s*<a\b[^>]*href=[\"\'][^\"\']*(?:uid=|space-uid-)[^\"\']*[\"\'][^>]*>(.*?)</a>', area.group(1), re.S | re.I)
        if anchor:
            identity = html.unescape(re.sub(r"<[^>]+>", "", anchor.group(1))).strip()
            if re.search(r"[\x00-\x1f\x7f]|\d{11}|(?:cookie|token|session)\s*[=:]", identity, re.I):
                identity = None
    return values[0], values[1], identity


def query(cookie):
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.5359.125 Safari/537.36",
        "Cookie": cookie,
    })
    opener = urllib.request.build_opener(SafeRedirect())
    with opener.open(req, timeout=20) as response:
        if response.status != 200:
            raise ValueError("论坛未返回 HTTP 200")
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("论坛页面超过大小限制")
        charset = response.headers.get_content_charset() or "utf-8"
        return parse_page(raw.decode(charset, errors="replace"))


def notify(body, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in DISABLED:
        log("⏭️ 通知已通过 QINGLONG_NOTIFY 关闭")
        return "disabled"
    if dry:
        log("⏭️ 已生成脱敏通知摘要；断网预演不调用通知模块")
        return "dry-run"
    try:
        try:
            import notify as module
        except ImportError:
            paths = []
            if os.getenv("QINGLONG_NOTIFY_DIR"):
                paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
            paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                raise ImportError("通知模块不存在")
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        # 禁止通知模块将异常或调试信息（可能含通知凭据）写入任务日志。
        import contextlib
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            module.send(TITLE, body)
        log("✅ 通知模块调用完成")
        return "sent"
    except Exception:
        log("⚠️ 通知不可用或发送失败，保留业务退出码")
        return "unavailable"


def main():
    started = time.monotonic()
    start_time = time.strftime("%Y-%m-%d %H:%M:%S")
    dry = os.getenv("ENSHAN_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}
    accounts = [line.strip() for line in os.getenv("enshanck", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{start_time}；模式：{'断网预演' if dry else '正式查询'}；账号数：{len(accounts)}")
    results = []
    configuration_error = not accounts
    if configuration_error:
        log("❌ 阶段 1 配置检查：请设置 enshanck，每个非空行一个完整登录 Cookie")
    for index, cookie in enumerate(accounts, 1):
        account_start = time.monotonic()
        success = False
        error = None
        log(f"账号 {index} 阶段 1：检查 Cookie 格式")
        try:
            if "=" not in cookie or any(ord(c) < 32 or ord(c) > 126 for c in cookie):
                raise ValueError("Cookie 应为可打印 ASCII 请求头，包含键值对，不含控制字符")
            log(f"✅ 账号 {index} 阶段 1 完成；耗时 {time.monotonic()-account_start:.2f} 秒")
            step_start = time.monotonic()
            log(f"账号 {index} 阶段 2：{'预演积分查询' if dry else '请求积分页并核验恩山币和积分'}")
            if dry:
                log(f"✅ 账号 {index} DRY_RUN_OK：配置有效，未发起网络请求；阶段耗时 {time.monotonic()-step_start:.2f} 秒")
            else:
                coin, point, identity = query(cookie)
                if identity:
                    log(f"账号 {index} 官方用户名：{identity}")
                log(f"✅ 账号 {index} 积分查询成功；恩山币：{coin}；积分：{point}；阶段耗时 {time.monotonic()-step_start:.2f} 秒")
            success = True
        except ValueError as exc:
            error = str(exc)
        except urllib.error.HTTPError as exc:
            error = f"HTTP 请求失败（状态码 {exc.code}）"
        except Exception:
            error = "请求或解析失败，请检查网络、Cookie 和页面兼容性（敏感错误详情已隐藏）"
        if error:
            log(f"❌ 账号 {index}：{error}")
        log(f"账号 {index} 统计：总任务 1，成功 {int(success)}，已完成 0，跳过 0，失败 {int(not success)}；耗时 {time.monotonic()-account_start:.2f} 秒")
        results.append({"account": index, "success": success})
    succeeded = sum(item["success"] for item in results)
    failed = len(accounts) - succeeded
    code = 1 if configuration_error or failed else 0
    status = "configuration-error" if configuration_error else ("partial-failure" if failed and succeeded else "failure" if failed else "dry-run" if dry else "success")
    body = f"模式：{'断网预演（非业务成功）' if dry else '正式查询'}\n账号总数：{len(accounts)}\n成功数：{succeeded}\n失败数：{failed}\n状态：{status}"
    notification = notify(body, dry)
    finish = time.strftime("%Y-%m-%d %H:%M:%S")
    log("----------------------------------------")
    log(f"任务统计：账号 {len(accounts)}，成功 {succeeded}，失败 {failed}；子任务 {len(accounts)}，成功 {succeeded}，已完成 0，跳过 0，失败 {failed}")
    log(f"完成时间：{finish}；总耗时：{time.monotonic()-started:.2f} 秒；通知状态：{notification}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "mode": "dry-run" if dry else "live", "status": status, "accounts": len(accounts), "success": succeeded, "failed": failed, "configurationError": configuration_error, "notification": notification, "exitCode": code, "results": results}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
