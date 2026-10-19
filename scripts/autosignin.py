#!/usr/bin/env python3
# name: E-Hentai 自动签到
# cron: 42 */6 * * *
# 来源: AkiyaKiko/EhentaiAutoSignIn, autosignin.py
# 上游提交: c00c3d42a61b7f526dd41b8df157444380898e57
# 许可证: MIT（任务提供的 effectiveLicense；输入未附单独版权声明）
"""E_COOKIE 每个非空行填写一个账号的完整 Cookie，保留分号内各字段。
登录 E-Hentai 后从浏览器开发者工具 news.php 请求头获取 Cookie，至少包含
ipb_member_id 与 ipb_pass_hash。E_PROXY、E_USER_AGENT 保持上游兼容。
E_DRY_RUN=1 完全断网预演；不请求服务或通知提供方。不会写回 Cookie。

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
        _ql_notify_identities = ('7919605278826396', 'scripts/autosignin.py', 'autosignin.py', 'autosignin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import email.utils
import html.parser
import http.cookies
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

URL = 'https://e-hentai.org/news.php'
TITLE = 'E-Hentai 自动签到'
DISABLED = {'0', 'false', 'no', 'off'}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36')


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.event_depth = None
        self.events = []
        self.identities = []
        self.identity_depth = None
        self.has_event = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'br', 'img', 'meta', 'link', 'input', 'hr', 'area', 'base', 'embed', 'source', 'wbr'}:
            return
        self.depth += 1
        if tag == 'div' and attrs.get('id') == 'eventpane':
            self.event_depth = self.depth
            self.has_event = True
        href = attrs.get('href', '')
        parsed = urllib.parse.urlparse(href)
        if (tag == 'a' and parsed.hostname == 'forums.e-hentai.org'
                and re.search(r'(?:\?|&)showuser=\d+(?:&|$)', href)):
            self.identity_depth = self.depth

    def handle_endtag(self, tag):
        if tag in {'br', 'img', 'meta', 'link', 'input', 'hr', 'area', 'base', 'embed', 'source', 'wbr'}:
            return
        if self.event_depth == self.depth:
            self.event_depth = None
        if self.identity_depth == self.depth:
            self.identity_depth = None
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if self.event_depth is not None:
            self.events.append(data)
        if self.identity_depth is not None:
            self.identities.append(data)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不把凭据传给重定向目标。
        return None


def validate_cookie(line):
    fields = {}
    for part in line.split(';'):
        if '=' in part:
            key, value = part.strip().split('=', 1)
            fields[key] = value
    if any(c in line for c in '\r\n\x00'):
        raise ValueError('Cookie 含非法控制字符')
    if not all(fields.get(key) for key in ('ipb_member_id', 'ipb_pass_hash')):
        raise ValueError('Cookie 缺少 ipb_member_id 或 ipb_pass_hash')
    return fields


def request_page(cookie, proxy, user_agent):
    for tls12 in (False, True):
        for attempt in range(1, 4):
            log(f'阶段 2 请求：{"TLS 1.2" if tls12 else "默认 TLS"} 第 {attempt}/3 次')
            context = ssl.create_default_context()
            if tls12:
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.maximum_version = ssl.TLSVersion.TLSv1_2
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({'http': proxy, 'https': proxy} if proxy else {}),
                urllib.request.HTTPSHandler(context=context), NoRedirect())
            req = urllib.request.Request(URL, headers={
                'User-Agent': user_agent, 'Accept': 'text/html,application/xhtml+xml',
                'Upgrade-Insecure-Requests': '1', 'Cookie': cookie})
            try:
                with opener.open(req, timeout=30) as response:
                    if response.status != 200:
                        raise ValueError('服务未返回 HTTP 200')
                    if 'html' not in response.headers.get('Content-Type', '').lower():
                        raise ValueError('服务返回非 HTML 内容')
                    body = response.read(2 * 1024 * 1024 + 1)
                    if len(body) > 2 * 1024 * 1024:
                        raise ValueError('响应超过安全大小限制')
                    charset = response.headers.get_content_charset() or 'utf-8'
                    return body.decode(charset, errors='replace'), response.headers.get_all('Set-Cookie', [])
            except (urllib.error.URLError, TimeoutError, OSError):
                log('⚠️ 请求失败，错误详情已脱敏')
                if attempt < 3:
                    time.sleep(2)
    raise ValueError('默认 TLS 与 TLS 1.2 请求均失败')


def inspect_page(body, set_cookies, fields):
    page = Page()
    page.feed(body)
    # 只输出官方身份字段，绝不输出事件原文或响应。
    identity = ''.join(page.identities).strip()
    if identity and not any(fields.get(key) and fields[key] in identity for key in ('ipb_pass_hash', 'sk')):
        log('官方账号身份：' + json.dumps(identity, ensure_ascii=False))
    renewed = False
    for raw in set_cookies:
        parsed = http.cookies.SimpleCookie()
        try:
            parsed.load(raw)
        except http.cookies.CookieError:
            continue
        for key, morsel in parsed.items():
            if key in fields and fields[key] != morsel.value:
                renewed = True
            if key in fields and key != 'event' and morsel['expires']:
                try:
                    expiry = email.utils.parsedate_to_datetime(morsel['expires']).isoformat()
                    log(f'Cookie 到期提醒：{key}，{expiry}')
                except (ValueError, TypeError, OverflowError):
                    log('⚠️ Cookie 到期时间无法解析')
    if renewed:
        log('⚠️ 服务返回更新 Cookie，请在浏览器重新获取；不写回环境变量')
    text = ' '.join(' '.join(page.events).split())
    if 'encounter' in text.lower():
        raise ValueError('出现 Random Encounter，请手动处理或等待事件结束，签到未确认')
    # HTTP 200、无事件区或任意段落均不足以证明签到成功。
    if re.search(r'\b(?:Dawn of a new day|You have gained)\b', text, re.I) and re.search(
            r'\b\d[\d,]*\s+(?:EXP|Credits?|Hath)\b', text, re.I):
        log('✅ 签到成功：事件区返回明确奖励')
        return 'success'
    if re.search(r'\b(?:already (?:claimed|received|completed)|have already (?:claimed|received))\b', text, re.I) and re.search(r'\b(?:dawn|daily|reward)\b', text, re.I):
        log('☑️ 今日已完成：事件区明确确认')
        return 'already-complete'
    raise ValueError('页面未提供明确签到或已完成证据，可能未登录或响应变化')


def notify_summary(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    if dry:
        return '断网预演：已生成通知摘要，跳过外部投递'
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            module = None
        if module is not None and callable(getattr(module, 'send', None)):
            module.send(TITLE, body)
            return '已发送'
        directories = []
        if os.getenv('QINGLONG_NOTIFY_DIR'):
            directories.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
        directories.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
        for directory in directories:
            path = directory / 'notify.py'
            if path.is_file():
                spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.send(TITLE, body)
                return '已发送'
            path = directory / 'sendNotify.js'
            if path.is_file():
                subprocess.run(['node', '-e', 'require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])',
                                str(path), TITLE, body], check=True, timeout=30,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return '已发送'
        return '通知模块不可用'
    except Exception:
        return '通知失败（业务退出码保持不变）'


def main():
    start = time.monotonic()
    dry = os.getenv('E_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    accounts = [line.strip() for line in os.getenv('E_COOKIE', '').splitlines() if line.strip()]
    log(f'===== {TITLE} =====')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "正式运行"}；账号数：{len(accounts)}')
    results = []
    if not accounts:
        log('❌ 配置错误：必须提供 E_COOKIE，每个非空行一个账号')
    for index, cookie in enumerate(accounts, 1):
        account_start = time.monotonic()
        status = 'failure'
        try:
            stage_start = time.monotonic()
            log(f'账号 {index} 阶段 1：校验配置')
            fields = validate_cookie(cookie)
            proxy = os.getenv('E_PROXY', '')
            if proxy and urllib.parse.urlparse(proxy).scheme not in {'http', 'https'}:
                raise ValueError('E_PROXY 必须为 HTTP 或 HTTPS 代理地址')
            ua = os.getenv('E_USER_AGENT') or UA
            if any(c in ua for c in '\r\n\x00'):
                raise ValueError('E_USER_AGENT 含非法控制字符')
            log(f'✅ 阶段 1 完成，耗时 {time.monotonic() - stage_start:.2f} 秒；代理：{"已配置" if proxy else "未配置"}')
            stage_start = time.monotonic()
            log(f'账号 {index} 阶段 2：访问新闻页与核验签到')
            if dry:
                log('⏭️ DRY_RUN_OK：配置通过，跳过 HTTP、Cookie 更新与通知外部投递')
                status = 'dry-run'
            else:
                body, cookies = request_page(cookie, proxy, ua)
                status = inspect_page(body, cookies, fields)
            log(f'阶段 2 完成，耗时 {time.monotonic() - stage_start:.2f} 秒')
        except ValueError as exc:
            log(f'❌ 账号 {index}：{exc}')
        except Exception:
            log(f'❌ 账号 {index}：运行错误，详情已脱敏')
        stats = {'account': index, 'status': status, 'total': 1,
                 'success': int(status == 'success'), 'alreadyComplete': int(status == 'already-complete'),
                 'skipped': int(status == 'dry-run'), 'failed': int(status == 'failure'),
                 'durationSeconds': round(time.monotonic() - account_start, 2)}
        results.append(stats)
        log(f'账号 {index} 统计：总任务 1，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["durationSeconds"]} 秒')
    failed = sum(r['failed'] for r in results)
    passed = len(results) - failed
    exit_code = int(not accounts or failed > 0)
    final_status = ('configuration-error' if not accounts else 'partial-failure' if failed and passed
                    else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': final_status,
               'accounts': len(accounts), 'success': passed if not dry else 0, 'failed': failed,
               'skipped': passed if dry else 0, 'results': results, 'exitCode': exit_code}
    text = f'状态：{final_status}；账号总数：{len(accounts)}；成功：{summary["success"]}；失败：{failed}；预演：{summary["skipped"]}'
    log('阶段 3：发送脱敏任务通知')
    notification_start = time.monotonic()
    notification = notify_summary(text, dry)
    log(f'阶段 3 完成：{notification}，耗时 {time.monotonic() - notification_start:.2f} 秒')
    summary.update(notification=notification, durationSeconds=round(time.monotonic()-start, 2),
                   finishTime=datetime.datetime.now().isoformat(timespec='seconds'))
    log('----------------------------------------')
    log(text)
    log(f'子任务：总数 {len(results)}，成功 {sum(r["success"] for r in results)}，已完成 {sum(r["alreadyComplete"] for r in results)}，跳过 {summary["skipped"]}，失败 {failed}')
    log(f'总耗时：{summary["durationSeconds"]} 秒；完成时间：{summary["finishTime"]}；通知：{notification}；最终状态：{final_status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
