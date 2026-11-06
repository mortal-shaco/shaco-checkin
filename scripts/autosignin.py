#!/usr/bin/env python3
# name: E-Hentai 自动签到
# cron: 18 */6 * * *
# 来源: AkiyaKiko/EhentaiAutoSignIn, autosignin.py
# 上游提交: eee89e605d9a2a4312d5b8466388fa19e5c8b8a0
# 合并来源: zephyr_xiao（基于 AkiyaKiko/EhentaiAutoSignIn 改写），MIT
# 归档目录 ID: e083167c5e868b00，上游镜像 zephyr-xiao/qinglong-script
# 归档上游提交: 8117361cd9a9cfaa93ffe93b9ccc90016c12e422
# 许可证: MIT（任务提供的 effectiveLicense；输入未附单独版权声明）
"""E_COOKIE 每个非空行填写一个账号的完整 Cookie，保留分号内各字段。
登录 E-Hentai 后从浏览器开发者工具 news.php 请求头获取 Cookie，至少包含
ipb_member_id 与 ipb_pass_hash。E_PROXY、E_USER_AGENT 保持上游兼容。
E_DRY_RUN=1 完全断网预演；不请求服务或通知提供方。默认不写回 Cookie。E_COOKIE_CACHE=1 显式启用私密缓存；
E_COOKIE_FILE 指定路径，默认脚本旁 ehentai_cookie.txt；环境变量优先。
仅成功核验且白名单字段变化时原子写入权限 600 的缓存；预演不读写。
QINGLONG_NOTIFY=auto|1|0；auto 时仅 QINGLONG_NOTIFY_SCRIPTS 命中本脚本才推送。

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
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('7919605278826396', 'scripts/autosignin.py', 'autosignin.py', 'autosignin', 'e083167c5e868b00', 'scripts/akiyakiko_ehentaiautosignin.py', 'akiyakiko_ehentaiautosignin.py', 'akiyakiko_ehentaiautosignin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import email.utils
import fnmatch
import html.parser
import http.cookies
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import ssl
import stat
import tempfile
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

URL = 'https://e-hentai.org/news.php'
TITLE = 'E-Hentai 自动签到'
CATALOG_ID = '7919605278826396'
SOURCE_PATH = 'AkiyaKiko/EhentaiAutoSignIn/autosignin.py'
COOKIE_FIELDS = ('ipb_member_id', 'ipb_pass_hash', 'sk', 'hath_perks', 'nw', 'event')
ENABLED = {'1', 'true', 'yes', 'on'}
DISABLED = {'0', 'false', 'no', 'off'}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36')
ACCEPT = ('text/html,application/xhtml+xml,application/xml;q=0.9,'
          'image/avif,image/webp,image/apng,*/*;q=0.8,'
          'application/signed-exchange;v=b3;q=0.7')


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.event_depth = None
        self.events = []
        self.parts = []
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
                and re.search(r'(?:\?|&)showuser=\d+(?:&|$)', href)
                and re.search(r'logged (?:in|on) as\s*:?\s*$', ' '.join(self.parts[-4:]), re.I)):
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
        self.parts.append(data)
        if self.event_depth is not None:
            self.events.append(data)
        if self.identity_depth is not None:
            self.identities.append(data)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不把凭据传给重定向目标。
        return None


def validate_cookie(line):
    if any(ord(c) < 32 or ord(c) > 126 for c in line):
        raise ValueError("Cookie 必须是单行可打印 ASCII 请求头")
    values = {}
    for field in line.split(";"):
        field = field.strip()
        if not field:
            continue
        key, sep, value = field.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) or not value:
            raise ValueError("Cookie 格式错误，请复制完整请求 Cookie")
        if key in values:
            raise ValueError("Cookie 存在重复字段，请重新复制单个账号 Cookie")
        values[key] = value
    if not all(values.get(k) for k in ("ipb_member_id", "ipb_pass_hash")):
        raise ValueError("Cookie 缺少 ipb_member_id 或 ipb_pass_hash")
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
                raise ValueError("缓存必须是当前用户所有、权限 600 的普通文件")
            value = handle.read(131073)
            if len(value) > 131072:
                raise ValueError("Cookie 缓存过大")
            return value
    except ValueError:
        raise
    except (OSError, UnicodeError):
        raise ValueError("无法安全读取 Cookie 缓存，请配置 E_COOKIE") from None


def write_cache(path, lines):
    temp_path = None
    try:
        if path.is_symlink():
            raise ValueError("不允许写入符号链接缓存")
        fd, temp_path = tempfile.mkstemp(prefix=".ehentai-cookie-", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        log("私密 Cookie 缓存已原子更新（权限 600；未修改环境变量）")
    except (OSError, ValueError):
        log("⚠️ Cookie 缓存保存失败，业务结果不变；请检查路径与权限")
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


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
                'User-Agent': user_agent, 'Accept': ACCEPT,
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
        if not tls12:
            log('⚠️ 默认 TLS 连续失败，回退到 TLS 1.2')
    raise ValueError('默认 TLS 与 TLS 1.2 请求均失败')


def safe_identity(value, cookie):
    value = " ".join(value.split())
    for key, secret in cookie.items():
        if secret:
            value = value.replace(secret, "[敏感信息已隐藏]")
    value = re.sub(r"(?<!\w)\+?\d[\d ()-]{5,}\d(?!\w)", "[号码已隐藏]", value)
    if re.search(r"cookie|token|session|pass_hash|device|bearer", value, re.I):
        return ""
    return "".join(c for c in value if c.isprintable())[:160]


def inspect_page(body, set_cookies, fields):
    page = Page()
    page.feed(body)
    full = ' '.join(' '.join(page.parts).split())
    text = ' '.join(' '.join(page.events).split())
    low = full.lower()
    # 只输出官方身份字段，绝不输出事件原文或响应。
    identity_match = re.search(
        r'\b(?:you are )?logged (?:in|on) as\s*:?\s*([^|\r\n]{1,160}?)'
        r'(?:\s*(?:\[|\(|\||log\s*out|sign\s*out)|$)', full, re.I)
    identity = safe_identity(''.join(page.identities), fields)
    if not identity and identity_match:
        identity = safe_identity(identity_match.group(1), fields)
    if identity and not any(fields.get(key) and fields[key] in identity for key in ('ipb_pass_hash', 'sk')):
        log('官方账号身份：' + json.dumps(identity, ensure_ascii=False))
    if any(marker in low for marker in (
            'please log in', 'not logged in', 'you are not logged',
            'verify you are human', 'checking your browser',
            'temporarily banned', 'your ip address has been', 'captcha')):
        raise ValueError('页面提示未登录、访问限制或人机验证')
    renewed = False
    for raw in set_cookies:
        parsed = http.cookies.SimpleCookie()
        try:
            parsed.load(raw)
        except http.cookies.CookieError:
            continue
        for key, morsel in parsed.items():
            if key in COOKIE_FIELDS and fields.get(key) != morsel.value:
                renewed = True
            if key in COOKIE_FIELDS and key != 'event' and morsel['expires']:
                try:
                    expiry = email.utils.parsedate_to_datetime(morsel['expires']).isoformat()
                    log(f'Cookie 到期提醒：{key}，{expiry}')
                except (ValueError, TypeError, OverflowError):
                    log('⚠️ Cookie 到期时间无法解析')
    if renewed:
        log('⚠️ 服务返回更新 Cookie，请在浏览器重新获取；不写回环境变量')
    if re.search(r'\b(?:random\s+)?encounter\b', text, re.I):
        raise ValueError('出现 Random Encounter，请手动处理或等待事件结束，签到未确认')
    # 相关源测例使用 “You gain … EXP/Credits”；兼容 “You have gained” 与 Hath。
    dawn = re.search(r'\bdawn of a new day\b', text, re.I)
    reward = re.search(
        r'\b(?:you\s+(?:have\s+)?(?:gain(?:ed)?|receiv(?:e|ed))|'
        r'(?:gain(?:ed)?|receiv(?:e|ed))\s+\d)[^.!?]{0,180}'
        r'\b(?:credits?|gp|experience|exp|hath)\b',
        text, re.I)
    # HTTP 200、无事件区或任意段落均不足以证明签到成功。
    if dawn and reward:
        log('✅ 签到成功：事件区返回明确奖励')
        return 'success'
    if re.search(
            r'\b(?:already (?:claimed|received|completed|collected)|'
            r'have already (?:claimed|received|collected))\b', text, re.I) and re.search(
            r'\b(?:dawn|daily|reward)\b', text, re.I):
        log('☑️ 今日已完成：事件区明确确认')
        return 'already-complete'
    if re.search(r'\blogged (?:in|on) as\b', full, re.I) and re.search(
            r'\b(?:already (?:claimed|received|collected)[^.!?]{0,100}(?:today|daily|dawn)|'
            r'(?:daily|dawn)[^.!?]{0,100}already (?:claimed|received|collected))\b', full, re.I):
        log('☑️ 今日已完成：事件区明确确认（兼容已登录的页面提示）')
        return 'already-complete'
    if not page.has_event:
        raise ValueError('未找到事件面板且无明确已领取证据，无法确认签到')
    raise ValueError('页面未提供明确签到或已完成证据，可能未登录或响应变化')


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
                raise ValueError("服务端撤销会话 Cookie，请重新登录获取凭据")
            if result.get(name) != morsel.value:
                result[name] = morsel.value
                changed += 1
    serialized = serialize_cookie(result)
    validate_cookie(serialized)
    return serialized, changed, expiry_count


def notification_selected():
    mode = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if mode in DISABLED:
        return False
    if mode in ENABLED:
        return True
    if mode and mode != 'auto':
        log('⚠️ QINGLONG_NOTIFY 无效，按 auto 处理')
    if 'QINGLONG_NOTIFY_SCRIPTS' not in os.environ:
        return False
    raw = os.environ.get('QINGLONG_NOTIFY_SCRIPTS', '')
    if not raw.strip():
        return False
    selectors = [item for item in re.split(r'[,;\s]+', raw.strip()) if item]
    names = {
        CATALOG_ID,
        SOURCE_PATH,
        'autosignin.py',
        'scripts/autosignin.py',
        'e083167c5e868b00',
        'AkiyaKiko_EhentaiAutoSignIn/autosignin.py',
        'scripts/akiyakiko_ehentaiautosignin.py',
        'akiyakiko_ehentaiautosignin.py',
        'akiyakiko_ehentaiautosignin',
        Path(__file__).name,
    }
    return any(
        selector == '*' or any(fnmatch.fnmatchcase(name, selector) for name in names)
        for selector in selectors
    )


def notify_summary(body, dry):
    if dry:
        return '断网预演：已生成通知摘要，跳过外部投递'
    if not notification_selected():
        return '未启用或未命中脚本名单'
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
                subprocess.run(
                    ['node', '-e',
                     'require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])',
                     str(path), TITLE, body],
                    check=True, timeout=30,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return '已发送'
        return '通知模块不可用'
    except Exception:
        return '通知失败（业务退出码保持不变）'


def main():
    start = time.monotonic()
    dry = os.getenv('E_DRY_RUN', '0').strip().lower() in ENABLED
    use_cache = os.getenv('E_COOKIE_CACHE', '0').strip().lower() in ENABLED
    cache_error = None
    raw = os.getenv('E_COOKIE', '')
    if not raw.strip() and use_cache and not dry:
        try:
            raw = read_cache(cache_path())
        except ValueError as exc:
            cache_error = str(exc)
    accounts = account_lines(raw)
    renewed = list(accounts)
    cache_changed = False
    log(f'===== {TITLE} =====')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；'
        f'模式：{"断网预演" if dry else "正式运行"}；账号数：{len(accounts)}')
    results = []
    if cache_error:
        log('❌ ' + cache_error)
    if not accounts:
        log('❌ 配置错误：必须提供 E_COOKIE，每个非空行一个账号')
    for index, cookie in enumerate(accounts, 1):
        account_start = time.monotonic()
        status = 'failure'
        try:
            stage_start = time.monotonic()
            log(f'账号 {index} 阶段 1：校验配置')
            cache_mode = os.getenv('E_COOKIE_CACHE', '0').strip().lower()
            if cache_mode not in ENABLED | DISABLED:
                raise ValueError('E_COOKIE_CACHE 仅支持 1/0、true/false、yes/no、on/off')
            fields = validate_cookie(cookie)
            proxy = os.getenv('E_PROXY', '')
            if proxy:
                try:
                    parsed = urllib.parse.urlsplit(proxy)
                    valid_proxy = (parsed.scheme in {'http', 'https'} and parsed.hostname
                                   and parsed.port != 0 and not parsed.query and not parsed.fragment
                                   and parsed.path in ('', '/')
                                   and all(33 <= ord(c) <= 126 for c in proxy))
                except ValueError:
                    valid_proxy = False
                if not valid_proxy:
                    raise ValueError('E_PROXY 必须为有效的 HTTP 或 HTTPS 代理地址')
            ua = os.getenv('E_USER_AGENT') or UA
            if any(ord(c) < 32 or ord(c) > 126 for c in ua):
                raise ValueError('E_USER_AGENT 含非法控制字符')
            log(f'✅ 阶段 1 完成，耗时 {time.monotonic() - stage_start:.2f} 秒；'
                f'代理：{"已配置" if proxy else "未配置"}')
            stage_start = time.monotonic()
            log(f'账号 {index} 阶段 2：访问新闻页与核验签到')
            if dry:
                log('⏭️ DRY_RUN_OK：配置通过，跳过 HTTP、Cookie 更新与通知外部投递')
                status = 'dry-run'
            else:
                body, cookies = request_page(cookie, proxy, ua)
                status = inspect_page(body, cookies, fields)
                if use_cache and status in ('success', 'already-complete'):
                    renewed[index - 1], changed, expires = refreshed_cookie(fields, cookies)
                    cache_changed |= bool(changed)
            log(f'阶段 2 完成，耗时 {time.monotonic() - stage_start:.2f} 秒')
        except ValueError as exc:
            status = 'failure'
            log(f'❌ 账号 {index}：{exc}')
        except Exception:
            status = 'failure'
            log(f'❌ 账号 {index}：运行错误，详情已脱敏')
        stats = {
            'account': index, 'status': status, 'total': 1,
            'success': int(status == 'success'),
            'alreadyComplete': int(status == 'already-complete'),
            'skipped': int(status == 'dry-run'),
            'failed': int(status == 'failure'),
            'durationSeconds': round(time.monotonic() - account_start, 2),
        }
        results.append(stats)
        log(f'账号 {index} 统计：总任务 1，成功 {stats["success"]}，'
            f'已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，'
            f'失败 {stats["failed"]}，耗时 {stats["durationSeconds"]} 秒')
    if use_cache and cache_changed and not dry:
        try:
            write_cache(cache_path(), renewed)
        except Exception:
            log('⚠️ Cookie 缓存保存失败，业务结果不变（详情已脱敏）')
    failed = sum(r['failed'] for r in results)
    passed = len(results) - failed
    exit_code = int(not accounts or failed > 0)
    final_status = (
        'configuration-error' if not accounts else
        'partial-failure' if failed and passed else
        'failure' if failed else
        'dry-run' if dry else 'success'
    )
    summary = {
        'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': final_status,
        'accounts': len(accounts), 'success': passed if not dry else 0, 'failed': failed,
        'skipped': passed if dry else 0, 'results': results, 'exitCode': exit_code,
    }
    text = (f'状态：{final_status}；账号总数：{len(accounts)}；'
            f'成功：{summary["success"]}；失败：{failed}；预演：{summary["skipped"]}')
    log('阶段 3：发送脱敏任务通知')
    notification_start = time.monotonic()
    notification = notify_summary(text, dry)
    log(f'阶段 3 完成：{notification}，耗时 {time.monotonic() - notification_start:.2f} 秒')
    summary.update(
        notification=notification,
        durationSeconds=round(time.monotonic() - start, 2),
        finishTime=datetime.datetime.now().isoformat(timespec='seconds'),
    )
    log('----------------------------------------')
    log(text)
    log(f'子任务：总数 {len(results)}，成功 {sum(r["success"] for r in results)}，'
        f'已完成 {sum(r["alreadyComplete"] for r in results)}，'
        f'跳过 {summary["skipped"]}，失败 {failed}')
    log(f'总耗时：{summary["durationSeconds"]} 秒；完成时间：{summary["finishTime"]}；'
        f'通知：{notification}；最终状态：{final_status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
