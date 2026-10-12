# -*- coding: utf-8 -*-
# name: HiFiTi与HiFiHi签到
# cron: 30 6 * * *
"""
原始说明与署名：
 cron: 30 6 * * *
 new Env('HiFiTi与HiFiHi签到')
 来源: https://github.com/anduinnn/HiFiNi-Auto-CheckIn
 支持 HiFiTi 和 HiFiHi 平台的自动签到、消息推送
维护来源：agluo/ql-script-hub，HiFiti_checkin.py；许可：MIT。

参数：浏览器登录对应站点，在开发者工具“网络”中复制该站点请求的完整
Cookie 请求头（不含 Cookie: 前缀）；不得复制其他站点的 Cookie。
HiFiTi_COOKIE：HiFiTi 完整 Cookie，每个非空行一个账号。
HIFIHI_COOKIE：HiFiHi 完整 Cookie，每个非空行一个账号。
两者至少配置一项；兼容旧版仅填写 cloudmusic.net 的值。
RANDOM_SIGNIN=true、MAX_RANDOM_DELAY=3600：保留原随机等待配置，
多账号启动时随机等待不超过 3600 秒，同站点账号间等待 1 至 3 秒。
HIFITI_DRY_RUN=1：完全断网，验证配置并模拟阶段和通知，不等待、不签到。
QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭。QINGLONG_NOTIFY_DIR 可指定
青龙通知模块目录；通知不可用不会改变业务退出码。
仅签到，不自动发帖、评论、分享或修改其他账号数据。

MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import html
import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from http.cookiejar import Cookie, CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, Request, build_opener

TITLE = "HiFiTi与HiFiHi签到"
SITES = (("HiFiTi", "HiFiTi_COOKIE", "https://www.hifiti.com/"),
         ("HiFiHi", "HIFIHI_COOKIE", "https://hifihi.com/"))
FALSE = {"0", "false", "no", "off"}
TRUE = {"1", "true", "yes", "on"}
MAX_BYTES = 2 * 1024 * 1024


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def flag(name, default):
    value = os.getenv(name, default).strip().lower()
    if value not in TRUE | FALSE:
        raise ValueError(f"{name} 必须为 1/0、true/false、yes/no 或 on/off")
    return value in TRUE


class SafeFailure(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafeFailure("接口发生重定向，请核对站点或登录状态")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0
        self.formhash = ""
        self.identity = ""
        self.identity_tag = None
        self.identity_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "input" and attrs.get("name") == "formhash":
            self.formhash = attrs.get("value", "")
        if not self.hidden and not self.identity_tag:
            classes = set(attrs.get("class", "").split())
            if classes & {"username", "nickname", "display-name"}:
                self.identity_tag = tag
                self.identity_parts = []

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if self.identity_tag == tag:
            self.identity = "".join(self.identity_parts).strip()
            self.identity_tag = None

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.identity_tag:
                self.identity_parts.append(data)


def parse_cookie(line):
    if any(ord(c) < 32 or ord(c) == 127 for c in line):
        raise SafeFailure("Cookie 含控制字符，请重新复制请求头")
    if "=" not in line:
        return "cloudmusic.net=" + line
    for field in line.split(";"):
        if not field.strip():
            continue
        name, separator, value = field.strip().partition("=")
        if not separator or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
            raise SafeFailure("Cookie 格式错误，应填写完整 Cookie 请求头或旧版值")
    return line


def account_opener(cookie, base):
    jar = CookieJar()
    for field in cookie.split(";"):
        if not field.strip():
            continue
        name, _, value = field.strip().partition("=")
        jar.set_cookie(Cookie(0, name, value, None, False, urlsplit(base).hostname,
                              False, False, "/", True, True, None, True,
                              None, None, {}, False))
    return build_opener(NoRedirect(), HTTPCookieProcessor(jar))


def request(opener, url, cookie, base, data=None):
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36",
               "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
               "Accept-Language": "zh-CN,zh;q=0.9", "Referer": base}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urlencode(data).encode("utf-8")
    try:
        with opener.open(Request(url, data=data, headers=headers), timeout=15) as response:
            if response.status != 200:
                raise SafeFailure("HTTP 状态不符合预期")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise SafeFailure("响应超过大小限制")
            return body.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    except HTTPError as error:
        raise SafeFailure(f"HTTP 请求失败，状态码 {error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise SafeFailure("网络请求失败或超时") from None


def safe_identity(value, cookie):
    if not isinstance(value, (str, int)):
        return ""
    value = str(value)
    # 身份字段按官方原值显示；若疑似含凭据、手机号或控制字符则不输出该字段。
    secrets = [part.partition("=")[2].strip() for part in cookie.split(";")]
    if (not value or any(ord(c) < 32 for c in value)
            or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value)
            or re.search(r"cookie|token|session|device", value, re.I)
            or any(secret and secret in value for secret in secrets)):
        return ""
    return value


def inspect_page(body, cookie):
    page = Page()
    page.feed(body)
    identity = page.identity
    try:
        obj = json.loads(body)
    except (ValueError, TypeError):
        obj = None
    if isinstance(obj, dict):
        for record in (obj, obj.get("data"), obj.get("user")):
            if isinstance(record, dict):
                for key in ("nickname", "username", "display_name", "public_uid"):
                    if record.get(key) is not None:
                        identity = record[key]
                        break
        # 只使用明确的消息字段，不把整个 JSON 当作业务成功证据。
        text = " ".join(str(obj[k]) for k in ("message", "msg")
                        if isinstance(obj.get(k), str))
    else:
        text = " ".join(page.parts)
    return page, text, safe_identity(identity, cookie)


def wait(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        left = end - time.monotonic()
        log(f"随机等待：剩余 {left:.0f} 秒")
        time.sleep(min(30, left))


def run_account(site, index, cookie, base, dry):
    started = time.monotonic()
    label = f"{site} 账号{index}"
    result = {"site": site, "account": index, "status": "failure", "tasks": 1,
              "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 1}
    stage = time.monotonic()
    log(f"{label} 阶段1/2：验证凭据并获取表单")
    try:
        cookie = parse_cookie(cookie)
        if dry:
            log(f"{label} 阶段1/2：✅ 配置格式通过；预演跳过 HTTP，耗时 {time.monotonic()-stage:.2f} 秒")
            log(f"{label} 阶段2/2：⏭️ DRY_RUN_OK，模拟签到流程，耗时 0.00 秒")
            result.update(status="dry-run", skipped=1, failure=0)
        else:
            # 每个账号新建连接管理器，Cookie 在获取表单之前传入，不共享会话。
            opener = account_opener(cookie, base)
            body = request(opener, base, cookie, base)
            page, _, identity = inspect_page(body, cookie)
            if identity:
                log(f"{label} 官方账号身份：{identity}")
            formhash = page.formhash
            if not formhash:
                for pattern in (r"formhash=([a-zA-Z0-9]+)", r'"formhash"\s*:\s*"([^\"]+)"'):
                    match = re.search(pattern, body)
                    if match:
                        formhash = html.unescape(match.group(1))
                        break
            if not formhash or len(formhash) > 256:
                raise SafeFailure("未获取有效 formhash，请检查 Cookie 或站点响应")
            log(f"{label} 阶段1/2：✅ 获取表单成功，耗时 {time.monotonic()-stage:.2f} 秒")
            stage = time.monotonic()
            log(f"{label} 阶段2/2：提交签到并验证业务结果")
            body = request(opener, base + "plugin.php?id=sign", cookie, base,
                           {"formhash": formhash, "submit": "1"})
            _, text, identity = inspect_page(body, cookie)
            if identity:
                log(f"{label} 官方账号身份：{identity}")
            if any(word in text for word in ("签到失败", "请先登录", "登录失效", "未登录")):
                raise SafeFailure("服务拒绝签到或登录状态失效")
            if "已签到" in text or "您今日签到已领取" in text:
                result.update(status="already-complete", alreadyComplete=1, failure=0)
                message = "☑️ 今日已签到"
            elif "签到成功" in text:
                result.update(status="success", success=1, failure=0)
                message = "✅ 签到成功"
            else:
                raise SafeFailure("未发现明确的签到成功或今日已签到结果")
            log(f"{label} 阶段2/2：{message}，耗时 {time.monotonic()-stage:.2f} 秒")
    except SafeFailure as error:
        log(f"{label} ❌ {error}，阶段耗时 {time.monotonic()-stage:.2f} 秒")
    except Exception:
        log(f"{label} ❌ 处理失败，异常详情已脱敏；阶段耗时 {time.monotonic()-stage:.2f} 秒")
    result["seconds"] = round(time.monotonic() - started, 2)
    log(f"{label} 统计：总任务1 成功{result['success']} 已完成{result['alreadyComplete']} "
        f"跳过{result['skipped']} 失败{result['failure']} 耗时{result['seconds']:.2f}秒")
    return result


def notify(summary, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in FALSE:
        return "已关闭"
    if dry:
        return "断网预演：已生成脱敏通知，未调用通知网络"
    body = (f"状态：{summary['status']}\n账号总数：{summary['accounts']}；"
            f"成功：{summary['success']}；已完成：{summary['alreadyComplete']}；"
            f"失败：{summary['failure']}；跳过：{summary['skipped']}")
    # 青龙通知是可选集成，独立运行不依赖其存在；子进程隔离输出与异常并限时。
    code = '''import importlib.util, json, os, pathlib, sys
title, body = json.loads(sys.stdin.read())
paths = []
if os.getenv("QINGLONG_NOTIFY_DIR"):
    paths.append(pathlib.Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
paths.extend([pathlib.Path("/ql/data/scripts/notify.py"), pathlib.Path("/ql/scripts/notify.py")])
try:
    from notify import send
except ImportError:
    send = None
    for path in paths:
        if path.is_file():
            sys.path.insert(0, str(path.parent))
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = module.send
            break
if send is not None:
    send(title, body)
    sys.exit(0)
js_paths = [p.with_name("sendNotify.js") for p in paths]
for path in js_paths:
    if path.is_file():
        import subprocess
        js = "const fs=require('fs'); const p=JSON.parse(fs.readFileSync(0,'utf8')); Promise.resolve(require(p[0]).sendNotify(p[1],p[2])).catch(()=>process.exit(1));"
        sys.exit(subprocess.run(["node", "-e", js], input=json.dumps([str(path), title, body]), text=True, timeout=20).returncode)
sys.exit(2)
'''
    try:
        completed = subprocess.run([sys.executable, "-c", code],
                                   input=json.dumps([TITLE, body]), text=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   timeout=30)
        return "已发送" if completed.returncode == 0 else "不可用或发送失败（保留业务退出码）"
    except Exception:
        return "不可用或发送超时（保留业务退出码）"


def main():
    started = time.monotonic()
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}")
    accounts = [(site, index, line.strip(), base)
                for site, env, base in SITES
                for index, line in enumerate([v for v in os.getenv(env, "").splitlines() if v.strip()], 1)]
    results = []
    error = ""
    # 无效 dry-run 值也禁止意外进入联网路径。
    dry = os.getenv("HIFITI_DRY_RUN", "0").strip().lower() not in FALSE
    log(f"运行模式：{'断网预演' if dry else '真实签到'}；账号数：{len(accounts)}")
    log("阶段0/2：检查账号与运行配置")
    try:
        dry = flag("HIFITI_DRY_RUN", "0")
        random_signin = flag("RANDOM_SIGNIN", "true")
        delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
        if delay < 0:
            raise ValueError("MAX_RANDOM_DELAY 必须为非负整数")
        if not accounts:
            raise ValueError("必须配置 HiFiTi_COOKIE 或 HIFIHI_COOKIE，非空行对应一个账号")
    except ValueError as exc:
        # 不输出用户提交的配置值，例如 int() 异常中可能包含秘密。
        error = (str(exc) if str(exc).startswith(("必须配置", "MAX_RANDOM_DELAY 必须", "RANDOM_SIGNIN 必须", "HIFITI_DRY_RUN 必须"))
                 else "配置错误：MAX_RANDOM_DELAY 必须为非负整数")
        log(f"❌ {error}")
    if not error:
        if random_signin and len(accounts) > 1 and not dry:
            wait(random.randint(0, min(delay, 3600)))
        for position, (site, index, cookie, base) in enumerate(accounts):
            results.append(run_account(site, index, cookie, base, dry))
            if not dry and position + 1 < len(accounts) and accounts[position + 1][0] == site:
                wait(random.uniform(1, 3))
    failed = sum(r["failure"] for r in results)
    exit_code = 1 if error or failed else 0
    status = ("configuration-error" if error else "partial-failure" if failed and failed < len(accounts)
              else "failure" if failed else "dry-run" if dry else "success")
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "status": status,
               "accounts": len(accounts), "success": sum(r["success"] for r in results),
               "alreadyComplete": sum(r["alreadyComplete"] for r in results),
               "failure": failed if not error else len(accounts),
               "skipped": sum(r["skipped"] for r in results), "configurationErrors": int(bool(error)),
               "results": results, "exitCode": exit_code}
    summary["notification"] = notify(summary, dry)
    summary["seconds"] = round(time.monotonic() - started, 2)
    summary["finishedAt"] = datetime.now().isoformat(timespec="seconds")
    log("--------------------------------------------------")
    log(f"任务统计：账号{len(accounts)} 成功{summary['success']} 已完成{summary['alreadyComplete']} "
        f"跳过{summary['skipped']} 失败{summary['failure']} 配置错误{summary['configurationErrors']}")
    log(f"子任务统计：总数{len(results)} 成功{summary['success']} 已完成{summary['alreadyComplete']} "
        f"跳过{summary['skipped']} 失败{failed}")
    log(f"通知状态：{summary['notification']}")
    log(f"完成时间：{summary['finishedAt']}；总耗时：{summary['seconds']:.2f}秒；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
