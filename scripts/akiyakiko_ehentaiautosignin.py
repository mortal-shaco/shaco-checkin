#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: E-Hentai 自动签到
# cron: 0 */6 * * *
# SPDX-License-Identifier: MIT
# 脚本来源: https://github.com/AkiyaKiko/EhentaiAutoSignIn
# 作者: zephyr_xiao（基于原项目改写）
# 上游镜像: zephyr-xiao/qinglong-script/AkiyaKiko_EhentaiAutoSignIn/autosignin.py
"""E-Hentai 新闻页签到，使用 Python 3.9+ 标准库，无需下载其他项目。

E_COOKIE（必需）：浏览器登录 https://e-hentai.org，开发者工具的网络面板
复制访问 news.php 的请求 Cookie。每个非空行是一个账号的完整 Cookie，至少含
ipb_member_id 与 ipb_pass_hash；分号分隔同账号字段，每个字段仅按首个等号拆分。
不要复制 Cookie: 前缀，不使用 & 或 @ 分隔账号。
E_PROXY：可选 HTTP/HTTPS 代理地址；E_USER_AGENT：可选浏览器请求头。
E_DRY_RUN=1：完全断网，只检查配置，不读取/写入缓存，不加载通知模块。
E_COOKIE_CACHE=1：显式启用私密 Cookie 续期缓存（默认关闭）。E_COOKIE_FILE
可指定路径，默认脚本旁 ehentai_cookie.txt；每行一个账号，与 E_COOKIE 顺序一致。
未设置 E_COOKIE 时可用该缓存兼容旧脚本；设置 E_COOKIE 时始终以环境变量为准。
新增或删去账号后应更新 E_COOKIE；缓存仅在业务验证通过后更新，不修改环境变量。
QINGLONG_NOTIFY=auto|1|0，auto 仅通知 QINGLONG_NOTIFY_SCRIPTS 中匹配的脚本；
未配置名单时无默认选中脚本。名单以逗号、分号或空白分隔，可用目录路径、文件名、
catalogId 或文件名通配符。QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
所有模式均生成脱敏通知总结；断网预演只展示通知预演，不实际推送。

默认 TLS 失败三次后尝试 TLS 1.2 三次，单次请求超时 30 秒，禁止携带凭据重定向。
仅明确的黎明奖励或今日已领证据视为成功；随机事件提示人工处理并非零退出。
缺少事件面板、登录证据或已完成证据时失败闭合，不将 HTTP 200 视为签到成功。
不发布帖子/评论，不消费积分；访问新闻页可能领取每日奖励、刷新会话或触发随机事件。

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
        _ql_notify_identities = ('e083167c5e868b00', 'scripts/akiyakiko_ehentaiautosignin.py', 'akiyakiko_ehentaiautosignin.py', 'akiyakiko_ehentaiautosignin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import contextlib
import fnmatch
import http.cookies
import json
import os
import re
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

TITLE = "E-Hentai 自动签到"
CATALOG_ID = "e083167c5e868b00"
SOURCE_PATH = "AkiyaKiko_EhentaiAutoSignIn/autosignin.py"
URL = "https://e-hentai.org/news.php"
CRON = "1 */6 * * *"
TIMEOUT = 30
MAX_BYTES = 2 * 1024 * 1024
COOKIE_FIELDS = ("ipb_member_id", "ipb_pass_hash", "sk", "hath_perks", "nw", "event")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class TaskError(Exception):
    """只携带固定脱敏错误消息。"""


def stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


@contextlib.contextmanager
def stage(number, title):
    began = time.monotonic()
    log(f"阶段 {number} · {title}：开始")
    try:
        yield
    finally:
        log(f"阶段 {number} · {title}：结束，耗时 {time.monotonic() - began:.2f} 秒")


def switch(name, default="0"):
    value = os.getenv(name, default).strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise TaskError(f"{name} 仅支持 1/0、true/false、yes/no、on/off")


def parse_cookie(line):
    if any(ord(c) < 32 or ord(c) > 126 for c in line):
        raise TaskError("Cookie 必须是单行可打印 ASCII 请求头")
    values = {}
    for field in line.split(";"):
        field = field.strip()
        if not field:
            continue
        key, sep, value = field.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) or not value:
            raise TaskError("Cookie 格式错误，请复制完整请求 Cookie")
        if key in values:
            raise TaskError("Cookie 存在重复字段，请重新复制单个账号 Cookie")
        values[key] = value
    if not all(values.get(k) for k in ("ipb_member_id", "ipb_pass_hash")):
        raise TaskError("Cookie 缺少 ipb_member_id 或 ipb_pass_hash")
    return values


def serialize_cookie(values):
    return "; ".join(f"{key}={value}" for key, value in values.items())


def account_lines(raw):
    return [line.strip() for line in raw.splitlines() if line.strip()]


def cache_path():
    return Path(os.getenv("E_COOKIE_FILE", str(Path(__file__).with_name("ehentai_cookie.txt"))))


def read_cache(path):
    try:
        # 兼容旧缓存；只接受当前用户的私密普通文件，禁止符号链接。
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
                raise TaskError("缓存必须是当前用户所有、权限 600 的普通文件")
            value = handle.read(131073)
            if len(value) > 131072:
                raise TaskError("Cookie 缓存过大")
            return value
    except TaskError:
        raise
    except (OSError, UnicodeError):
        raise TaskError("无法安全读取 Cookie 缓存，请配置 E_COOKIE") from None


def write_cache(path, lines):
    temp_path = None
    try:
        if path.is_symlink():
            raise TaskError("不允许写入符号链接缓存")
        fd, temp_path = tempfile.mkstemp(prefix=".ehentai-cookie-", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        log("私密 Cookie 缓存已原子更新（权限 600；未修改环境变量）")
    except (OSError, TaskError):
        log("⚠️ Cookie 缓存保存失败，业务结果不变；请检查路径与权限")
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("新闻页发生重定向，已阻止携带 Cookie 跳转；请检查登录状态")


def request_page(cookie, proxy, user_agent):
    for tls12 in (False, True):
        tls_name = "TLS 1.2" if tls12 else "默认 TLS"
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        if tls12:
            context.maximum_version = ssl.TLSVersion.TLSv1_2
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {}),
            urllib.request.HTTPSHandler(context=context), NoRedirect(),
        )
        for attempt in range(1, 4):
            log(f"{tls_name} 请求 {attempt}/3，超时 {TIMEOUT} 秒")
            request = urllib.request.Request(URL, headers={
                "User-Agent": user_agent, "Cookie": cookie,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1",
            })
            try:
                with opener.open(request, timeout=TIMEOUT) as response:
                    if response.status != 200:
                        raise TaskError("新闻页 HTTP 状态异常")
                    if response.headers.get_content_type() not in ("text/html", "application/xhtml+xml"):
                        raise TaskError("新闻页响应类型异常")
                    raw = response.read(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES:
                        raise TaskError("新闻页超过安全大小限制")
                    encoding = response.headers.get_content_charset() or "utf-8"
                    try:
                        page = raw.decode(encoding, errors="strict")
                    except (LookupError, UnicodeError):
                        raise TaskError("新闻页编码无法解析") from None
                    log("HTTP 200，已收到新闻页；继续核验业务证据")
                    return page, response.headers.get_all("Set-Cookie", [])
            except urllib.error.HTTPError as exc:
                code = exc.code
                exc.close()
                log(f"⚠️ HTTP 请求失败，状态码 {code}（未输出响应）")
                if code not in (408, 429, 500, 502, 503, 504):
                    raise TaskError("HTTP 请求被拒绝，请检查凭据、代理或站点状态") from None
            except (urllib.error.URLError, OSError, TimeoutError):
                log("⚠️ 网络或 TLS 请求失败（详情已脱敏）")
            if attempt < 3:
                time.sleep(2)
        if not tls12:
            log("⚠️ 默认 TLS 三次失败，回退 TLS 1.2；仍验证证书")
    raise TaskError("默认 TLS 与 TLS 1.2 均请求失败")


class NewsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []
        self.event = []
        self.identity = []
        self.identity_link = False
        self.event_found = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        event = attrs.get("id") == "eventpane"
        href = urllib.parse.urlsplit(attrs.get("href", ""))
        identity = (tag == "a" and href.hostname == "forums.e-hentai.org"
                    and bool(urllib.parse.parse_qs(href.query).get("showuser"))
                    and bool(re.search(r"logged (?:in|on) as\s*:?\s*$", " ".join(self.parts[-4:]), re.I)))
        self.identity_link |= identity
        if event:
            self.event_found = True
        if tag not in {"br", "hr", "img", "input", "meta", "link", "wbr", "area", "base", "col", "embed", "param", "source", "track"}:
            self.stack.append((tag, event, identity))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if any(item[0] in ("script", "style") for item in self.stack):
            return
        self.parts.append(data)
        if any(item[1] for item in self.stack):
            self.event.append(data)
        if any(item[2] for item in self.stack):
            self.identity.append(data)


def safe_identity(value, cookie):
    value = " ".join(value.split())[:160]
    for key, secret in cookie.items():
        if key in ("ipb_member_id", "ipb_pass_hash", "sk", "event"):
            value = value.replace(secret, "[敏感信息已隐藏]")
    value = re.sub(r"(?<!\w)\+?\d[\d ()-]{5,}\d(?!\w)", "[号码已隐藏]", value)
    if re.search(r"cookie|token|session|pass_hash|device|bearer", value, re.I):
        return ""
    return "".join(c for c in value if c.isprintable())


def verify_page(page, cookie):
    parser = NewsParser()
    parser.feed(page)
    text = " ".join(" ".join(parser.parts).split())
    event = " ".join(" ".join(parser.event).split())
    # 只提取服务端明确的当前登录身份，绝不把任意用户资料链接当成本账号。
    identity_match = re.search(r"\b(?:you are )?logged (?:in|on) as\s*:?\s*([^|\r\n]{1,160}?)(?:\s*(?:\[|\(|\||log\s*out|sign\s*out)|$)", text, re.I)
    identity = safe_identity("".join(parser.identity), cookie) if parser.identity_link else (
        safe_identity(identity_match.group(1), cookie) if identity_match else "")
    if identity:
        log(f"官方账号身份：{identity}")
    low = text.lower()
    if any(marker in low for marker in ("please log in", "not logged in", "you are not logged", "verify you are human", "checking your browser", "temporarily banned", "your ip address has been", "captcha")):
        raise TaskError("页面提示未登录、访问限制或人机验证")
    if re.search(r"\b(?:random\s+)?encounter\b", event, re.I):
        return "encounter", "出现 Random Encounter！请手动处理或等待事件结束"
    # 上游只凭存在段落就报成功；维护版必须同时有黎明与奖励的明确证据。
    dawn = re.search(r"\bdawn of a new day\b", event, re.I)
    reward = re.search(r"\b(?:you\s+(?:have\s+)?(?:gain(?:ed)?|receiv(?:e|ed))|(?:gain(?:ed)?|receiv(?:e|ed))\s+\d)[^.!?]{0,180}\b(?:credits?|gp|experience|exp)\b", event, re.I)
    already = re.search(r"\b(?:already (?:claimed|received|collected)[^.!?]{0,100}(?:today|daily|dawn)|(?:daily|dawn)[^.!?]{0,100}already (?:claimed|received|collected))\b", text, re.I)
    if dawn and reward:
        return "success", "签到成功：已验证黎明事件及奖励领取提示"
    if (parser.identity_link or identity_match) and already:
        return "already-complete", "今日已完成：已验证登录身份与已领取提示"
    if not parser.event_found:
        raise TaskError("未找到事件面板且无明确已领取证据，无法确认签到；请人工核对")
    raise TaskError("事件内容不符合明确签到成功条件，可能为接口变化；未输出原始响应")


def refreshed_cookie(cookie, headers):
    result = dict(cookie)
    changed = 0
    expiry_count = 0
    for header in headers:
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(header)
        except http.cookies.CookieError:
            log("⚠️ 忽略无法解析的续期 Cookie")
            continue
        for name in COOKIE_FIELDS:
            if name not in jar:
                continue
            morsel = jar[name]
            if morsel["expires"] and name != "event":
                expiry_count += 1
            if not morsel.value or morsel["max-age"] == "0":
                raise TaskError("服务端撤销会话 Cookie，请重新登录获取凭据")
            if result.get(name) != morsel.value:
                result[name] = morsel.value
                changed += 1
    serialized = serialize_cookie(result)
    parse_cookie(serialized)
    return serialized, changed, expiry_count


def notification_selected():
    mode = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if mode in FALSE_VALUES:
        return False
    if mode in TRUE_VALUES:
        return True
    if mode != "auto":
        log("⚠️ QINGLONG_NOTIFY 无效，按 auto 处理")
    selectors = re.split(r"[,;\s]+", os.getenv("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    names = {CATALOG_ID, SOURCE_PATH, "autosignin.py", Path(__file__).name}
    return any(fnmatch.fnmatchcase(name, selector) for selector in selectors if selector for name in names)


def send_notification(body, dry_run):
    if dry_run:
        log("⏭️ 断网通知预演：" + body.replace("\n", "；"))
        return "dry-run"
    if not notification_selected():
        log("⏭️ 通知未启用或未命中脚本名单；脱敏总结已生成")
        return "disabled-or-unselected"
    # 在子进程中导入标准青龙通知，隔离其日志和异常，限制总耗时。
    # 推送实现来自部署环境，可缺失；签到本身完全独立。
    worker = '''
import importlib, importlib.util, json, sys
title, body, path, script_dir = json.load(sys.stdin)
sys.path.insert(0, script_dir)
try:
    if path:
        sys.path.insert(0, str(__import__('pathlib').Path(path).parent))
        spec = importlib.util.spec_from_file_location('_ql_task_notify', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module('notify')
    send = module.send
except (ImportError, AttributeError, OSError):
    sys.exit(3)
try:
    send(title, body)
except Exception:
    sys.exit(2)
print('QL_NOTIFY_SENT')
'''
    roots = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        roots.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]))
    roots.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    choices = [("python", None)]
    choices.extend(("python", str(root / "notify.py")) for root in roots if (root / "notify.py").is_file())
    choices.extend(("javascript", str(root / "sendNotify.js")) for root in roots if (root / "sendNotify.js").is_file())
    notify_env = dict(os.environ)
    for key in ("E_COOKIE", "E_PROXY", "E_USER_AGENT"):
        notify_env.pop(key, None)
    notify_env["HITOKOTO"] = "false"
    for kind, path in choices:
        if kind == "python":
            command = [sys.executable, "-c", worker]
        else:
            command = ["node", "-e", "let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',async()=>{try{const [t,b,p]=JSON.parse(s);await require(p).sendNotify(t,b);console.log('QL_NOTIFY_SENT')}catch(e){process.exitCode=1}})"]
        try:
            result = subprocess.run(command, input=json.dumps([TITLE, body, path, str(Path(__file__).resolve().parent)]), text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    env=notify_env, timeout=25, check=False)
            if result.returncode == 0 and "QL_NOTIFY_SENT" in result.stdout.splitlines():
                log("✅ 青龙通知模块已调用")
                return "sent"
            # 模块已开始推送但失败时不转其他通道，避免重复推送。
            if result.returncode != 3:
                break
        except subprocess.TimeoutExpired:
            log("⚠️ 青龙通知超时；保留业务退出码")
            return "failed"
        except OSError:
            continue
    log("⚠️ 青龙通知不可用或调用失败；保留业务退出码")
    return "unavailable-or-failed"


def main():
    began = time.monotonic()
    started = stamp()
    dry_run = False
    results = []
    lines = []
    config_error = None
    exit_code = 1
    log("========== " + TITLE + " ==========")
    log("开始时间：" + started)
    try:
        with stage(1, "配置与账号清单"):
            dry_run = switch("E_DRY_RUN")
            log("运行模式：" + ("完全断网预演" if dry_run else "正式运行"))
            use_cache = switch("E_COOKIE_CACHE")
            raw = os.getenv("E_COOKIE", "")
            if not raw.strip() and use_cache and not dry_run:
                raw = read_cache(cache_path())
                log("使用显式启用的私密 Cookie 缓存")
            lines = account_lines(raw)
            log(f"账号数量：{len(lines)}")
            if not lines:
                raise TaskError("未配置 E_COOKIE；每个非空行填写一个账号的完整 Cookie")
            proxy = os.getenv("E_PROXY", "").strip()
            if proxy:
                try:
                    parsed = urllib.parse.urlsplit(proxy)
                    valid = (parsed.scheme in ("http", "https") and parsed.hostname
                             and parsed.port != 0 and not parsed.query and not parsed.fragment
                             and parsed.path in ("", "/")
                             and not any(ord(c) < 33 or ord(c) > 126 for c in proxy))
                except ValueError:
                    valid = False
                if not valid:
                    raise TaskError("E_PROXY 必须是有效的 HTTP/HTTPS 代理地址")
            user_agent = os.getenv("E_USER_AGENT", "") or USER_AGENT
            if any(ord(c) < 32 or ord(c) > 126 for c in user_agent):
                raise TaskError("E_USER_AGENT 必须是单行可打印 ASCII 请求头")
            log("代理：" + ("已配置（地址隐藏）" if proxy else "未配置；不使用系统代理"))
            log("Cookie 持久化：" + ("已显式启用" if use_cache else "默认关闭"))
        renewed = list(lines)
        cache_changed = False
        for number, line in enumerate(lines, 1):
            account_began = time.monotonic()
            outcome = "failure"
            message = "账号执行失败"
            with stage(2, f"账号 {number} · 登录与签到核验"):
                try:
                    cookie = parse_cookie(line)
                    log(f"账号 {number}：必需凭据字段校验通过（不输出值）")
                    if dry_run:
                        outcome, message = "dry-run", "DRY_RUN_OK：配置有效，未请求网站、读写缓存或调用通知模块"
                    else:
                        page, cookies = request_page(serialize_cookie(cookie), proxy, user_agent)
                        outcome, message = verify_page(page, cookie)
                        if outcome in ("success", "already-complete"):
                            renewed[number - 1], changed, expires = refreshed_cookie(cookie, cookies)
                            cache_changed |= bool(changed)
                            log(f"账号 {number}：续期字段变化 {changed} 个；服务端过期提示 {expires} 项（值隐藏）")
                            if changed and not use_cache:
                                log("⏭️ Cookie 持久化未启用；仅在本轮内使用续期结果")
                    log(f"账号 {number}：{message}")
                except TaskError as exc:
                    outcome, message = "failure", str(exc)
                    log(f"❌ 账号 {number}：{message}")
                except Exception:
                    outcome, message = "failure", "未预期的解析或运行错误（详情已脱敏）"
                    log(f"❌ 账号 {number}：{message}")
            failed = int(outcome in ("failure", "encounter"))
            row = {"account": number, "status": outcome, "total": 1,
                   "success": int(outcome == "success"),
                   "alreadyComplete": int(outcome == "already-complete"),
                   "skipped": int(outcome == "dry-run"), "failed": failed,
                   "seconds": round(time.monotonic() - account_began, 3)}
            results.append(row)
            log(f"账号 {number} 统计：总任务 1，成功 {row['success']}，已完成 {row['alreadyComplete']}，跳过 {row['skipped']}，失败 {failed}，耗时 {row['seconds']:.2f} 秒")
        if use_cache and cache_changed and not dry_run:
            with stage(3, "保存已验证账号的续期缓存"):
                write_cache(cache_path(), renewed)
        exit_code = int(any(row["failed"] for row in results))
    except TaskError as exc:
        config_error = str(exc)
        log("❌ 配置错误：" + config_error)
    except Exception:
        config_error = "初始化发生未预期错误（详情已脱敏）"
        log("❌ " + config_error)
    successful = sum(row["status"] in ("success", "already-complete") for row in results)
    failed = sum(row["failed"] for row in results)
    skipped = sum(row["skipped"] for row in results)
    status = ("configuration-error" if config_error else
              "partial-failure" if failed and (successful or skipped) else
              "failure" if failed else "dry-run" if dry_run else "success")
    body = f"状态：{status}\n账号总数：{len(lines)}；成功：{successful}；失败：{failed}；预演：{skipped}"
    if config_error:
        body += "\n配置错误：" + config_error
    try:
        with stage(4, "脱敏总结与青龙通知"):
            notification = send_notification(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("⚠️ 通知调用异常；保留业务退出码")
    summary = {
        "task": TITLE, "status": status, "mode": "dry-run" if dry_run else "live",
        "accounts": len(lines), "success": successful, "failed": failed,
        "skipped": skipped, "configurationErrors": int(config_error is not None),
        "tasks": {key: sum(row[key] for row in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")},
        "results": results, "notification": notification, "startedAt": started,
        "finishedAt": stamp(), "seconds": round(time.monotonic() - began, 3), "exitCode": exit_code,
    }
    log("----------------------------------------")
    log(f"任务统计：账号 {len(lines)}，成功 {successful}，失败 {failed}，预演 {skipped}，配置错误 {summary['configurationErrors']}")
    log(f"子任务统计：{json.dumps(summary['tasks'], ensure_ascii=False)}")
    log(f"通知状态：{notification}；总耗时：{summary['seconds']:.2f} 秒")
    log("完成时间：" + summary["finishedAt"])
    log(f"最终状态：{status}；退出码：{exit_code}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
