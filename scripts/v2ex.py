# name: V2EX 每日签到
# cron: 0 9 * * *
"""V2EX 独立维护版，来源 Sitoi/dailycheckin，MIT。

V2EX_COOKIE：浏览器登录 https://www.v2ex.com 后，在开发者工具 Network
中复制该站请求的完整 Cookie 请求头值；一行一个账号，保留值中的等号。
V2EX_PROXY：可选 HTTP/HTTPS 代理地址。V2EX_DRY_RUN=1 完全断网预演。
运行依赖：requests（公开 PyPI 包）。不读取上游 config.json。

MIT License (upstream license: Sitoi/dailycheckin)
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

import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

BASE = "https://www.v2ex.com"
TITLE = "V2EX 每日签到"


def stamp():
    return datetime.now().strftime("%H:%M:%S")


def log(message):
    print(f"[{stamp()}] {message}", flush=True)


class TaskError(Exception):
    pass


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.claim = None
        self.complete = False
        self.username = None
        self.identity_depth = 0
        self.identity_parts = []
        self.feed(text)
        self.plain = " ".join(html.unescape(re.sub(r"<[^>]*>", " ", text)).split())
        self.days = re.search(r"(?:已)?连续(?:登录|签到)\s*(\d+)\s*天", self.plain)
        self.balance = re.search(r'<td\b[^>]*class=[\"\']d[\"\'][^>]*style=[\"\'][^\"\']*text-align:\s*right;?[^\"\']*[\"\'][^>]*>\s*(\d+(?:\.\d+)?)\s*</td>', text)
        self.today = re.search(r'<td\b[^>]*class=[\"\']d[\"\'][^>]*>\s*<span\b[^>]*class=[\"\']gray[\"\'][^>]*>(.*?)</span>', text, re.S)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href", "").startswith("/member/") and "top" in attrs.get("class", "").split():
            self.identity_depth = 1
            self.identity_parts = []
        elif self.identity_depth:
            self.identity_depth += 1
        if tag == "input" and attrs.get("type", "").lower() == "button":
            match = re.search(r"location\.href\s*=\s*(['\"])(.*?)\1", attrs.get("onclick", ""))
            if match:
                target = match.group(2)
                if target == "/balance":
                    self.complete = True
                elif urlsplit(target).path == "/mission/daily/redeem":
                    self.claim = target

    def handle_data(self, data):
        if self.identity_depth:
            self.identity_parts.append(data)

    def handle_endtag(self, tag):
        if self.identity_depth:
            self.identity_depth -= 1
            if self.identity_depth == 0:
                self.username = "".join(self.identity_parts).strip()


def safe_target(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "www.v2ex.com" or parsed.username or parsed.password:
        raise TaskError("拒绝非本站 HTTPS 地址")
    if parsed.path not in ("/mission/daily", "/mission/daily/redeem", "/balance") or parsed.fragment:
        raise TaskError("拒绝非签到或余额端点，登录状态可能已失效")
    return url


def fetch(session, path, referer=None):
    url = safe_target(urljoin(BASE, path))
    headers = {"Referer": referer} if referer else {}
    for _ in range(6):
        with session.get(url, headers=headers, timeout=(10, 20), allow_redirects=False, stream=True) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                target = response.headers.get("Location")
                if not target:
                    raise TaskError("重定向缺少目标")
                url = safe_target(urljoin(url, target))
                continue
            if response.status_code != 200:
                raise TaskError(f"HTTP 状态异常：{response.status_code}")
            chunks = []
            size = 0
            for chunk in response.iter_content(16384):
                size += len(chunk)
                if size > 2 * 1024 * 1024:
                    raise TaskError("页面超出大小限制")
                chunks.append(chunk)
            return Page(b"".join(chunks).decode("utf-8", errors="replace"))
    raise TaskError("重定向次数超限")


def cookies(line):
    result = {}
    for field in line.split(";"):
        if not field.strip():
            continue
        key, sep, value = field.strip().partition("=")
        if not sep or not key or not value or re.search(r"[\s\x00-\x1f\x7f]", key) or re.search(r"[\x00-\x1f\x7f]", value):
            raise TaskError("Cookie 格式无效，请复制完整请求头值")
        result[key] = value
    if not result:
        raise TaskError("Cookie 为空")
    return result


def stage(number, name, action):
    started = time.monotonic()
    log(f"阶段 {number}：{name}")
    try:
        result = action()
    except Exception:
        log(f"阶段 {number}：失败，耗时 {time.monotonic() - started:.2f} 秒")
        raise
    log(f"阶段 {number}：完成，耗时 {time.monotonic() - started:.2f} 秒")
    return result


def account(line, dry):
    credential = stage(1, "校验账号参数", lambda: cookies(line))
    if dry:
        log("阶段 2：DRY_RUN_OK，模拟签到、身份、奖励、余额及连续天数查询；网络请求为零")
        return "skipped"
    import requests
    with requests.Session() as session:
        session.trust_env = False
        proxy = os.environ.get("V2EX_PROXY", "").strip()
        if proxy:
            if urlsplit(proxy).scheme not in ("http", "https"):
                raise TaskError("代理必须为 HTTP 或 HTTPS 地址")
            session.proxies.update({"http": proxy, "https": proxy})
        for key, value in credential.items():
            session.cookies.set(key, value, domain="www.v2ex.com", path="/", secure=True)
        session.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "text/html", "Accept-Language": "zh-CN,zh;q=0.9"})
        daily = stage(2, "查询签到状态", lambda: fetch(session, "/mission/daily"))
        if not daily.username:
            raise TaskError("未取得登录身份，Cookie 可能过期或页面契约变化")
        log(f"帐号信息: {daily.username}")
        already = daily.complete
        if not already:
            if not daily.claim:
                raise TaskError("未找到有效签到入口")
            target = safe_target(urljoin(BASE, daily.claim))
            query = parse_qs(urlsplit(target).query)
            if set(query) != {"once"} or len(query["once"]) != 1 or not query["once"][0].isdigit():
                raise TaskError("签到入口参数不符合契约")
            stage(3, "领取每日奖励", lambda: fetch(session, target, BASE + "/mission/daily"))
        else:
            log("阶段 3：☑️ 今日已领取奖励")
        verified = stage(4, "复核签到结果", lambda: fetch(session, "/mission/daily"))
        if not verified.complete or verified.username != daily.username:
            raise TaskError("签到后未验证已领取状态或身份不一致")
        balance = stage(5, "查询奖励和余额", lambda: fetch(session, "/balance"))
        if balance.username != daily.username or not balance.balance or not balance.today or not verified.days:
            raise TaskError("已确认签到，但奖励、余额或连续天数信息不完整")
        # 仅输出奖励相关描述，避免显示余额页面的其他交易内容。
        today = " ".join(html.unescape(re.sub(r"<[^>]*>", " ", balance.today.group(1))).split())
        reward = re.search(r"(?:每日登录奖励|每日签到奖励)[^\r\n]{0,80}", today)
        log(f"今日签到: {reward.group(0) if reward else '已验证领取；最新交易描述未显示'}")
        log(f"帐号余额: {balance.balance.group(1)}")
        log(f"签到天数: {verified.days.group(1)}天")
        log("☑️ V2EX_ALREADY_COMPLETE" if already else "✅ V2EX_CHECKIN_OK")
        return "alreadyComplete" if already else "success"


def notify(summary, dry):
    if os.environ.get("QINGLONG_NOTIFY", "1").lower() in ("0", "false", "no", "off"):
        return "已关闭"
    # 子进程隔离通知输出及故障，断网预演阻止通知插件进行网络通信。
    runner = '''import importlib.util, os, socket, sys
if sys.argv[1] == "1":
    def deny(*a, **k): raise OSError("dry-run network disabled")
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.socket.sendto = deny
    if hasattr(socket.socket, "sendmsg"): socket.socket.sendmsg = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
paths = []
try:
    spec = importlib.util.find_spec("notify")
    if spec and spec.origin: paths.append(spec.origin)
except Exception: pass
directory = os.environ.get("QINGLONG_NOTIFY_DIR")
if directory: paths.append(os.path.join(directory, "notify.py"))
paths += ["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"]
for path in dict.fromkeys(paths):
    if not os.path.isfile(path): continue
    try:
        spec = importlib.util.spec_from_file_location("ql_task_notify", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.send(sys.argv[2], sys.argv[3])
        sys.exit(0)
    except Exception: continue
sys.exit(1)
'''
    body = f"模式：{'断网预演' if dry else '正常运行'}；账号总数：{summary['accounts']}；成功：{summary['success']}；失败：{summary['failed']}；跳过：{summary['skipped']}；状态：{summary['status']}"
    try:
        result = subprocess.run([sys.executable, "-c", runner, "1" if dry else "0", TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
        return "已调用通知模块（预演禁止网络）" if dry and result.returncode == 0 else "已发送" if result.returncode == 0 else "不可用或发送失败（预演禁止网络）" if dry else "不可用或发送失败"
    except Exception:
        return "不可用或发送失败"


def main():
    started = time.monotonic()
    dry = os.environ.get("V2EX_DRY_RUN", "0").lower() in ("1", "true", "yes", "on")
    lines = [line.strip() for line in os.environ.get("V2EX_COOKIE", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.now().isoformat(timespec='seconds')}；模式：{'断网预演' if dry else '正常运行'}；账号数：{len(lines)}")
    counts = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    if not lines:
        log("❌ 配置错误：必须提供 V2EX_COOKIE，每个账号占一行")
    for index, line in enumerate(lines, 1):
        before = time.monotonic()
        log(f"---------- 账号 {index} ----------")
        try:
            outcome = account(line, dry)
        except TaskError as exc:
            log(f"❌ {exc}")
            outcome = "failed"
        except Exception:
            log("❌ 网络、依赖或执行错误，已隐藏异常内容以保护凭据")
            outcome = "failed"
        counts[outcome] += 1
        log(f"账号 {index} 统计：总任务 1；成功 {int(outcome == 'success')}；已完成 {int(outcome == 'alreadyComplete')}；跳过 {int(outcome == 'skipped')}；失败 {int(outcome == 'failed')}；耗时 {time.monotonic() - before:.2f} 秒")
    code = int(not lines or counts["failed"] > 0)
    status = "configuration-error" if not lines else "partial-failure" if counts["failed"] and counts["failed"] < len(lines) else "failure" if code else "dry-run" if dry else "success"
    summary = {"accounts": len(lines), "success": counts["success"] + counts["alreadyComplete"], "failed": counts["failed"], "skipped": counts["skipped"], "alreadyComplete": counts["alreadyComplete"], "status": status, "exitCode": code}
    summary["notification"] = notify(summary, dry)
    summary["elapsedSeconds"] = round(time.monotonic() - started, 2)
    log("----------------------------------------")
    log(f"任务统计：账号 {len(lines)}；子任务 {len(lines)}；成功 {summary['success']}；已完成 {counts['alreadyComplete']}；跳过 {counts['skipped']}；失败 {counts['failed']}；耗时 {summary['elapsedSeconds']} 秒")
    log(f"完成时间：{datetime.now().isoformat(timespec='seconds')}；通知：{summary['notification']}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
