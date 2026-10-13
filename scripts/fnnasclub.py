#!/usr/bin/env python3
# name: 飞牛Nas论坛签到
# cron: 0 8 * * *
"""独立维护版本，来源 Sitoi/dailycheckin dailycheckin/fnnasclub/main.py。
上游提交：135cc236e59ac4f14bcddc44acb3cbb3ed6010b5；许可：MIT。
FNNASCLUB_COOKIE：登录 https://club.fnnas.com 后，从浏览器开发者工具的
网络面板复制该站已登录请求的 Cookie 请求头值。每个账号独占一行，保留分号。
FNNASCLUB_DRY_RUN=1 完全断网预演。签到会改变论坛签到记录及相关奖励。
上游未提供 cron，维护版本建议每天 08:00（青龙面板时区）。

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
import html
import importlib.util
import json
import os
import re
import sys
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path

TITLE = "飞牛Nas论坛签到"
BASE = "https://club.fnnas.com/"
PAGE = BASE + "plugin.php?id=zqlj_sign"
DISABLED = {"0", "false", "no", "off"}


def log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {message}", flush=True)


def plain(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value)).split())


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.active = [dict(attrs).get("href", ""), ""]

    def handle_data(self, data):
        if self.active is not None:
            self.active[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.active is not None:
            self.anchors.append(self.active)
            self.active = None


class LocalRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != "https" or target.netloc != "club.fnnas.com":
            raise ValueError("拒绝跨站重定向")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, cookie):
        self.cookie = cookie
        self.opener = urllib.request.build_opener(
            LocalRedirect(), urllib.request.HTTPCookieProcessor(CookieJar()))

    def get(self, url):
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0", "Accept": "text/html",
            "Referer": BASE + "portal.php", "Cookie": self.cookie})
        with self.opener.open(req, timeout=15) as response:
            if response.status != 200:
                raise ValueError("HTTP 状态异常")
            data = response.read(2 * 1024 * 1024 + 1)
            if len(data) > 2 * 1024 * 1024:
                raise ValueError("响应过大")
            return data.decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def identity(page, cookie):
    # Discuz 登录用户区域中的公开昵称；不从 Cookie 推导身份。
    match = re.search(r'<div\b[^>]*\bid=["\']um["\'][^>]*>(.*?)</div>', page, re.S)
    if not match:
        return None
    parser = PageParser()
    parser.feed(match.group(1))
    for href, label in parser.anchors:
        if "mod=space" in href and "uid=" in href:
            name = plain(label)
            if name and not re.search(r"\d{11}|cookie|token|session", name, re.I) and name not in cookie:
                return name
    return None


def sign_link(page):
    parser = PageParser()
    parser.feed(page)
    for href, label in parser.anchors:
        url = urllib.parse.urljoin(BASE, href)
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parsed.query)
        if (parsed.scheme == "https" and parsed.netloc == "club.fnnas.com"
                and parsed.path == "/plugin.php" and query.get("id") == ["zqlj_sign"]
                and label.strip() in {"点击打卡", "今日已打卡"}):
            token = query.get("sign", [""])[0]
            if re.fullmatch(r"[0-9a-fA-F]+", token):
                return PAGE + "&sign=" + token, label.strip() == "今日已打卡"
    raise ValueError("未找到有效签到按钮，请检查登录状态或页面接口")


def info(page, cookie):
    block = re.search(r"<strong>\s*我的打卡动态\s*</strong>.*?<div[^>]*class=[\"']bm_c[\"'][^>]*>(.*?)</div>", page, re.S)
    if not block:
        raise ValueError("未找到我的打卡动态")
    rows = []
    for row in re.split(r"</li\s*>", block.group(1)):
        text = plain(row)
        parts = re.split(r"[：:]", text, maxsplit=1)
        if len(parts) != 2:
            continue
        key, value = parts
        if re.search(r"cookie|token|session|手机|电话|设备|签名|密码", key, re.I):
            continue
        # 保留上游所有动态字段，同时脱敏凭据、手机号及长令牌。
        for pair in cookie.split(";"):
            secret = pair.partition("=")[2].strip()
            if len(secret) >= 4:
                value = value.replace(secret, "[已脱敏]")
                key = key.replace(secret, "[已脱敏]")
        value = re.sub(r"(?<!\d)1\d{10}(?!\d)|[A-Za-z0-9_+/=-]{24,}", "[已脱敏]", value)
        rows.append({"name": key, "value": value})
    if not rows:
        raise ValueError("打卡动态未包含可核验的安全统计字段")
    return rows


def notify(body, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in DISABLED:
        return "已关闭"
    if dry:
        log("通知摘要已生成；断网预演禁止执行可能联网的通知模块")
        return "断网预演已跳过发送"
    paths = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    try:
        try:
            import notify as module
        except ImportError:
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, "send", None)):
            js_paths = [path.with_name("sendNotify.js") for path in paths]
            for path in js_paths:
                if path.is_file():
                    result = subprocess.run(["node", "-e", "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))", str(path), TITLE, body], timeout=20, capture_output=True)
                    return "已发送" if result.returncode == 0 else "通知发送失败（业务退出码保留）"
            return "通知模块不可用"
        outcome = []
        def deliver():
            try:
                module.send(TITLE, body)
                outcome.append(True)
            except Exception:
                outcome.append(False)
        worker = threading.Thread(target=deliver, daemon=True)
        worker.start()
        worker.join(20)
        if not outcome or not outcome[0]:
            return "通知发送失败或超时（业务退出码保留）"
        return "已发送"
    except Exception:
        return "通知发送失败（业务退出码保留）"


def main():
    started = time.monotonic()
    dry = os.getenv("FNNASCLUB_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}
    accounts = [line.strip() for line in os.getenv("FNNASCLUB_COOKIE", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.datetime.now().isoformat(timespec='seconds')}；模式：{'断网预演' if dry else '正式运行'}；账号数：{len(accounts)}")
    results = []
    if not accounts:
        log("❌ 配置错误：请设置 FNNASCLUB_COOKIE，每行一个账号 Cookie")
    for index, cookie in enumerate(accounts, 1):
        begin = time.monotonic()
        stats = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        messages = []
        stage = 1
        try:
            if "=" not in cookie or any(ord(char) < 32 or ord(char) > 255 for char in cookie):
                raise ValueError("Cookie 格式错误")
            for stage in (1, 2, 3):
                tick = time.monotonic()
                name = {1: "读取签到页及账号身份", 2: "执行签到", 3: "读取我的打卡动态"}[stage]
                log(f"账号 {index} 阶段 {stage}/3：{name}")
                if dry:
                    stats["skipped"] += 1
                    log(f"⏭️ 参数及流程有效，未发送请求；耗时 {time.monotonic()-tick:.2f} 秒")
                    continue
                if stage == 1:
                    client = Client(cookie)
                    page = client.get(PAGE)
                    nickname = identity(page, cookie)
                    if nickname:
                        log(f"账号 {index} 官方昵称：{nickname}")
                    url, already = sign_link(page)
                elif stage == 2:
                    if already:
                        stats["alreadyComplete"] += 1
                        messages.append({"name": "签到结果", "value": "您已签到，请勿重复签到"})
                        log("☑️ 页面确认今日已打卡")
                    else:
                        response = client.get(url)
                        if "恭喜您，打卡成功！" in response:
                            messages.append({"name": "签到结果", "value": "签到成功"})
                        elif "您今天已经打过卡了，请勿重复操作！" in response:
                            stats["alreadyComplete"] += 1
                            messages.append({"name": "签到结果", "value": "您已签到，请勿重复签到"})
                        else:
                            raise ValueError("响应未明确确认签到成功或今日已签到")
                else:
                    messages.extend(info(client.get(PAGE), cookie))
                if stage != 2 or not stats["alreadyComplete"]:
                    stats["success"] += 1
                log(f"✅ 阶段完成；耗时 {time.monotonic()-tick:.2f} 秒")
            for item in messages:
                log(f"{item['name']}: {item['value']}")
            ok = True
        except Exception as exc:
            stats["failed"] += 1
            stats["skipped"] += 3 - stage
            # 不输出异常字符串：HTTP 异常可能含签到签名或其他敏感地址。
            log(f"❌ 账号 {index} 阶段 {stage} 失败（{type(exc).__name__}）；请核对登录状态及页面契约")
            ok = False
        log(f"账号 {index} 统计：总任务 3，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {time.monotonic()-begin:.2f} 秒")
        results.append({"account": index, "ok": ok, **stats})
    succeeded = sum(result["ok"] for result in results)
    failed = len(accounts) - succeeded
    status = ("configuration-error" if not accounts else "failure" if failed == len(accounts)
              else "partial-failure" if failed else "dry-run" if dry else "success")
    code = 1 if failed or not accounts else 0
    body = f"模式：{'断网预演' if dry else '正式运行'}；账号总数：{len(accounts)}；成功：{succeeded}；失败：{failed}；最终状态：{status}"
    delivery = notify(body, dry)
    log("----------------------------------------")
    log(body)
    totals = {key: sum(result[key] for result in results) for key in ("success", "alreadyComplete", "skipped", "failed")}
    log(f"子任务统计：{json.dumps(totals, ensure_ascii=False)}")
    log(f"完成时间：{datetime.datetime.now().isoformat(timespec='seconds')}；总耗时 {time.monotonic()-started:.2f} 秒；通知状态：{delivery}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "mode": "dry-run" if dry else "live", "status": status, "accounts": len(accounts), "success": succeeded, "failed": failed, "statistics": totals, "notification": delivery, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
