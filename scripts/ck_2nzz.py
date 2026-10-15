# -*- coding: utf-8 -*-
# name: 咔叽网单签到
# cron: 40 1 * * *
# Upstream: yuxian158/check, dailycheckin_scripts/ck_2nzz.py
# Commit: 723c834f121ff4eef2dec7afe521071a7efff1a9; License: MIT
# 原文件没有额外版权声明；保留上游署名及 MIT 许可。
"""咔叽网单每日签到（Python 3 标准库，无私有框架依赖）。

NZZ_COOKIE 必填：在 https://www.2nzz.com 登录后，从浏览器开发者工具
网络面板的本站请求中复制完整 Cookie 请求头值（不要带 Cookie:）。
每个非空行代表一个账号；分号分隔 Cookie 字段，字段只按首个等号拆分。
旧框架的 check_item.cookie 内容可直接放入此变量，不再读取私有配置文件。
NZZ_DRY_RUN=1 仅校验配置并预演，绝不访问网络或调用通知模块。
QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭通知。
原文件无 cron；新增每日 08:30 的青龙默认调度，可在面板修改。
只签到，不发帖、不评论、不分享、不消费。TLS 或业务校验失败不降级。

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

import contextlib
import datetime
import html
from html.parser import HTMLParser
import http.cookiejar
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import time
import urllib.parse
import urllib.request

BASE = "https://www.2nzz.com"
TITLE = "咔叽网单签到"
DISABLED = {"0", "false", "no", "off"}


class TaskError(Exception):
    pass


def log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {message}", flush=True)


def parse_cookie(line):
    result = {}
    for field in line.split(";"):
        if not field.strip():
            continue
        key, sep, value = field.strip().partition("=")
        if not sep or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key):
            raise TaskError("Cookie 格式错误，须为名称=值的分号列表")
        if not value or any(ord(c) < 32 or ord(c) > 126 for c in value):
            raise TaskError("Cookie 值为空或含非法字符")
        result[key] = value
    if not result:
        raise TaskError("Cookie 不能为空")
    return result


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hashes = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "formhash":
            value = attrs.get("value", "")
            if re.fullmatch(r"[A-Za-z0-9]{1,64}", value):
                self.hashes.append(value)


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if (parsed.scheme != "https" or parsed.hostname != "www.2nzz.com"
                or parsed.port not in (None, 443) or parsed.username or parsed.password):
            raise TaskError("已阻止跨站或非 HTTPS 重定向")
        # 签到 POST 不自动重放或转换为 GET，防止重复变更及误判。
        if req.get_method() != "GET":
            raise TaskError("签到接口重定向，无法验证结果")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, cookies):
        jar = http.cookiejar.CookieJar()
        for key, value in cookies.items():
            jar.set_cookie(http.cookiejar.Cookie(
                0, key, value, None, False, "www.2nzz.com", False, False,
                "/", True, True, None, True, None, None, {}, False))
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), SafeRedirect(),
            urllib.request.HTTPCookieProcessor(jar))

    def request(self, path, data=None):
        req = urllib.request.Request(BASE + path, data=data, headers={
            "User-Agent": "Mozilla/5.0", "Referer": BASE + "/index.php",
            "Origin": BASE, "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml"})
        try:
            with self.opener.open(req, timeout=15) as response:
                if response.status != 200:
                    raise TaskError("HTTP 状态不是 200")
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise TaskError("接口响应超过大小限制")
                encoding = response.headers.get_content_charset()
                if not encoding:
                    match = re.search(br'charset\s*=\s*["\x27]?([\w-]+)', raw[:8192], re.I)
                    encoding = match.group(1).decode("ascii") if match else "utf-8"
                return raw.decode(encoding, errors="strict")
        except TaskError:
            raise
        except Exception:
            # urllib 异常可能包含 URL、响应和请求信息，不输出原始异常。
            raise TaskError("请求失败（网络、TLS、HTTP 或编码异常），未验证成功") from None


def classify_sign(page):
    blocks = re.findall(r'<div\b[^>]*class\s*=\s*["\']c["\'][^>]*>(.*?)</div>', page, re.S | re.I)
    if len(blocks) != 1:
        raise TaskError("签到响应缺少唯一结果区，未验证成功")
    text = html.unescape(re.sub(r"<[^>]*>", "", blocks[0]))
    if "您今天已经签到过了或者签到时间还未开始" in text:
        raise TaskError("接口混合提示已签到或时间未开始，无法确认今日签到")
    if any(word in text for word in ("签到失败", "未登录", "请先登录", "登录后", "非法", "错误", "未开始")):
        raise TaskError("签到业务拒绝或登录态失效")
    if "签到成功" in text or "恭喜你签到成功" in text:
        return "success"
    if "今日已签到" in text or "今天已经签到过了" in text:
        return "alreadyComplete"
    raise TaskError("未识别到明确签到成功标志")


def run_account(index, line, dry):
    started = time.monotonic()
    stats = {"total": 3, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    log(f"账号 {index} 开始")
    stages = ("配置与签到令牌", "公开账号信息", "每日签到")
    state = "failure"
    for number, name in enumerate(stages, 1):
        tick = time.monotonic()
        log(f"账号 {index} 阶段 {number}/3：{name}")
        try:
            if number == 1:
                cookies = parse_cookie(line)
            if dry:
                if number == 1:
                    log("✅ Cookie 格式校验通过；令牌获取仅预演")
                    stats["success"] += 1
                else:
                    log("⏭️ 无网络预演，跳过 HTTP 请求")
                    stats["skipped"] += 1
                state = "dry-run"
                continue
            if number == 1:
                client = Client(cookies)
                parser = FormParser()
                parser.feed(client.request("/index.php"))
                if len(set(parser.hashes)) != 1:
                    raise TaskError("缺失或冲突的 formhash，请重新获取登录 Cookie")
                formhash = parser.hashes[0]
                log("✅ 已获取签到令牌（不显示令牌）")
            elif number == 2:
                page = client.request("/home.php")
                uid = re.search(r'uid=(\d+)["\x27]', page)
                if not uid:
                    raise TaskError("未获取公开 UID，不能确认登录态")
                log(f"账号信息: {uid.group(1)}")
            else:
                query = urllib.parse.urlencode({"id": "dsu_paulsign:sign", "operation": "qiandao",
                    "infloat": "1", "sign_as": "1", "inajax": "1"})
                data = urllib.parse.urlencode({"formhash": formhash, "qdxq": "kx", "qdmode": "2",
                    "todaysay": "", "fastreply": "0"}).encode("ascii")
                state = classify_sign(client.request("/plugin.php?" + query, data))
                if state == "alreadyComplete":
                    stats["alreadyComplete"] += 1
                    log("☑️ 签到信息: 今日已签到（明确响应）")
                    continue
                log("✅ 签到信息: 签到成功（明确响应）")
            stats["success"] += 1
        except TaskError as exc:
            log(f"❌ {exc}")
            stats["failed"] += 1
            stats["skipped"] += 3 - number
            break
        except Exception:
            log("❌ 处理异常，未验证业务成功")
            stats["failed"] += 1
            stats["skipped"] += 3 - number
            break
        finally:
            log(f"账号 {index} 阶段 {number} 耗时 {time.monotonic() - tick:.2f} 秒")
    elapsed = round(time.monotonic() - started, 2)
    log(f"账号 {index} 统计：总任务 3，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，"
        f"跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {elapsed:.2f} 秒")
    return {"account": index, "status": state, "tasks": stats, "elapsedSeconds": elapsed}


def notify(body, dry):
    if os.environ.get("QINGLONG_NOTIFY", "1").lower() in DISABLED:
        log("⏭️ 通知已关闭")
        return "disabled"
    if dry:
        log("通知预演（无网络）：" + body)
        return "dry-run-preview"
    try:
        # 隔离通知模块输出并限制总耗时，通知故障不改变业务结果。
        helper = "import runpy,sys; runpy.run_path(sys.argv[1])['deliver_notify'](sys.stdin.read())"
        completed = subprocess.run([sys.executable, "-c", helper, str(Path(__file__).resolve())],
                                   input=body, text=True, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=20, check=False)
        if completed.returncode != 0:
            raise TaskError("通知失败")
        log("✅ 脱敏通知已提交")
        return "sent"
    except Exception:
        log("⚠️ 通知不可用或发送失败，保留业务退出码")
        return "unavailable-or-failed"


def deliver_notify(body):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            module = importlib.import_module("notify")
        except ImportError:
            directory = os.environ.get("QINGLONG_NOTIFY_DIR")
            paths = ([Path(directory) / "notify.py"] if directory else [])
            paths += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                raise ImportError
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.send(TITLE, body)


def main():
    started = time.monotonic()
    dry = os.environ.get("NZZ_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}
    lines = [line.strip() for line in os.environ.get("NZZ_COOKIE", "").splitlines() if line.strip()]
    log("========== 咔叽网单签到 ==========")
    log(f"开始时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    log(f"模式：{'无网络预演' if dry else '正式执行'}；账号数：{len(lines)}")
    results = [run_account(i, line, dry) for i, line in enumerate(lines, 1)]
    failed = sum(item["status"] == "failure" for item in results)
    good = len(lines) - failed
    code = 1 if failed or not lines else 0
    status = ("configuration-error" if not lines else "partial-failure" if failed and good
              else "failure" if failed else "dry-run" if dry else "success")
    if not lines:
        log("❌ 配置错误：必须填写 NZZ_COOKIE")
    body = f"状态 {status}；账号总数 {len(lines)}，成功 {good if not dry else 0}，失败 {failed}，预演通过 {good if dry else 0}"
    notification = notify(body, dry)
    totals = {key: sum(r["tasks"][key] for r in results)
              for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log("----------------------------------------")
    log(body)
    log("子任务统计：" + json.dumps(totals, ensure_ascii=False))
    finish = datetime.datetime.now().isoformat(timespec="seconds")
    elapsed = round(time.monotonic() - started, 2)
    log(f"完成时间：{finish}；总耗时 {elapsed:.2f} 秒；通知状态 {notification}；最终状态 {status}")
    print("TASK_SUMMARY=" + json.dumps({"status": status, "mode": "dry-run" if dry else "live",
        "accounts": len(lines), "success": good if not dry else 0, "failed": failed,
        "dryRunPassed": good if dry else 0, "tasks": totals, "results": results,
        "notification": notification, "finishedAt": finish, "elapsedSeconds": elapsed,
        "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
