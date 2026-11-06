# -*- coding: utf-8 -*-
# name: 尚香书苑签到
# cron: 4 10 * * *
# SPDX-License-Identifier: MIT
# 上游作者 zephyr_xiao，来源 zephyr-xiao/qinglong-script，保留原始署名。
"""
new Env('尚香书苑签到');
cron: 4 10 * * *

尚香书苑 Discuz! X3.5 论坛 k_misign 插件每日签到。
站点主域名不定期更换（旧域名 301 到"最新地址"导航页），脚本启动时自动探测可用域名：
先试内置候选，再解析导航页里站点自维护的最新域名。
登录强制图片验证码（Discuz seccode，idhash 固定为 cS），本地 ddddocr 自动识别；
k_misign 签到需通过算术验证（"签到验证：A - B = ?"），脚本解析后自动计算二次请求；
登录 Cookie JSON 缓存复用，失效自动重新登录。
网络默认直连（本站国内可达，走境外代理会被 Cloudflare 当数据中心 IP 发人机质询）；
站点偶发 Cloudflare 522（回源超时）等瞬时错误页会自动退避重试，不会误判成改版或掉登录；
Cloudflare 人机质询页（403 "Just a moment..."）单独识别，按出口 IP 风控处理，不清 Cookie 缓存。

环境变量：
  SXSY_ACCOUNTS          账号列表：用户名#密码，多账号仅用换行分隔（每行一个账号）；
                         也支持直接填 Cookie 字符串（不含 # 时按 Cookie 处理，不参与缓存）
  SXSY_DRY_RUN           true/false 断网预演，默认 false
  QINGLONG_NOTIFY        auto 按名单、true 全开、false 全关
  QINGLONG_NOTIFY_SCRIPTS 逗号、分号或空白分隔的通知名单
  SXSY_NOTIFY            true/false 兼容通知开关，默认 true（受全局策略约束）
  SXSY_NOTIFY_ONLY_FAIL  true/false 仅失败时推送，默认 false
  SXSY_TIMEOUT           秒    请求超时，默认 30
  SXSY_DEBUG             true/false 调试模式，默认 false
  SXSY_PROXY             HTTP 代理（可选）；**默认直连**，不读全局 HTTPS_PROXY。
                         填 URL 走代理，填 direct/none/off 同样强制直连
依赖：requests 必装；ddddocr 仅账密登录时需要（Cookie 模式无需安装）
作者: zephyr_xiao
"""
from __future__ import annotations
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
        _ql_notify_identities = ('fccba94cf57739f4', 'scripts/sxsy45_checkin.py', 'sxsy45_checkin.py', 'sxsy45_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import json
import os
import re
import sys
import time
import fnmatch
import tempfile
import contextlib
import fcntl
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit, urljoin

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import requests
except ImportError:
    requests = None  # 断网预演仅使用标准库，实跑缺依赖时仍输出完整汇总。


# ---------------- 站点常量（均为 2026-10-30 实测） ----------------
# 站点主域名会不定期更换：旧域名 301 到一个纯 JS 的"最新地址"导航页（不是新站），
# 跟随重定向只会拿到导航页。所以 BASE 仅作默认值，运行时由 resolve_base() 探测后覆盖。
DEFAULT_BASE = "https://sxsy33.com"
DOMAIN_CANDIDATES = ("https://sxsy33.com", "https://sxsy45.com")
NAV_URL = "https://sxsy.pw"     # "最新地址"导航页：旧域名 301 的落点，页面内写着当前主域名
BASE = DEFAULT_BASE
SITE_NAME = "尚香书苑"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MODID = "member::logging"       # Discuz seccode 的 modid
SIGN_URL = f"{BASE}/plugin.php?id=k_misign:sign"
LOGIN_URL = f"{BASE}/member.php?mod=logging&action=login"
FORUM_URL = f"{BASE}/forum.php"

# 命名须匹配仓库 .gitignore 的 *_cookie.json 规则（含真实凭证，严禁入库）
COOKIE_CACHE = Path(__file__).resolve().parent / "sxsy45_cookie.json"
LOGIN_MAX_TRIES = 3             # 验证码 OCR 识别重试上限（含首次）

# 致命登录错误关键词：出现即停止重试（避免反复触发风控/封禁计数）
_LOGIN_FATAL_KEYWORDS = ("密码错误", "密码不正确", "登录失败次数过多", "账户被", "帐号被", "被锁定", "被禁止")

# 站点间歇性返回 Cloudflare 522（回源超时）等错误页，属于瞬时故障：
# 必须退避重试，不能当成"Cookie 失效"或"站点改版"，否则会白白丢掉有效会话。
_SITE_ERROR_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504,
                                520, 521, 522, 523, 524, 525, 526})
HTTP_TRIES = 3                  # 单个 GET 请求最大尝试次数（含首次）
HTTP_BACKOFF = (5, 15)          # 各次重试前等待秒数，末项复用

# Cloudflare 托管质询（403 "Just a moment..." / 503 challenge-platform）：
# 判定依据是出口 IP 被风控，与账号密码、Cookie 都无关。刷重试只会加重风控，
# 也不能据此认定"Cookie 失效"，所以单独一类、只给一次重试机会（代理节点有机会切换）。
CF_CHALLENGE_MARK = "Cloudflare 人机质询"
CF_CHALLENGE_TITLE_MARKERS = ("Just a moment", "Attention Required",
                              "Checking your browser", "Verify you are human")
CF_CHALLENGE_TRIES = 2          # 同一出口最多尝试次数（含首次）
CF_CHALLENGE_BACKOFF = 15       # 两次尝试之间的等待秒数


# ---------------- 通用工具 ----------------
def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except Exception:
        return default


def parse_credentials(env_value: str):
    """每个非空行保留一个账号，密码仅按第一个 # 分割。"""
    accounts = []
    for raw in env_value.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        if "#" in raw:
            user, password = raw.split("#", 1)
            accounts.append((user.strip(), password))
        else:
            accounts.append(raw)
    return accounts


def parse_cookie_str(s: str) -> dict:
    """'a=1; b=2' -> {'a':'1','b':'2'}"""
    jar = {}
    for part in s.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        jar[k.strip()] = v.strip()
    return jar


def solve_math(question: str):
    """解析 k_misign 算术验证题 '签到验证：9 + 15 = ?'，返回整数答案；解析失败返回 None。"""
    m = re.search(r"(\d+)\s*([+\-×xX*/÷])\s*(\d+)", question or "")
    if not m:
        return None
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op in ("×", "x", "X", "*"):
        return a * b
    if op in ("÷", "/"):
        if b == 0:
            return None
        return a // b if a % b == 0 else a / b
    return None


def fetch_sign_stats(html: str) -> str:
    """从签到页提取统计（连续天数/等级/奖励/累计天数），无统计返回空串。"""
    parts = []
    m = re.search(r'id="lxdays"\s+value="(\d+)"', html)
    if m:
        parts.append(f"连续 {m.group(1)} 天")
    m = re.search(r'id="lxlevel"\s+value="(\d+)"', html)
    if m:
        parts.append(f"Lv.{m.group(1)}")
    m = re.search(r'id="lxreward"\s+value="(\d+)"', html)
    if m:
        parts.append(f"积分+{m.group(1)}")
    m = re.search(r'id="lxtdays"\s+value="(\d+)"', html)
    if m:
        parts.append(f"累计 {m.group(1)} 天")
    return "  │  ".join(parts)


# 本站国内可直连；走境外代理反而会被 Cloudflare 当成数据中心 IP 发人机质询，
# 所以默认直连。需要代理时显式设 SXSY_PROXY=<url>，或设 SXSY_PROXY=direct 强制直连。
DIRECT_PROXY_VALUES = ("direct", "none", "off", "0", "false", "-")

def resolve_proxy() -> tuple:
    """解析网络出口，返回 (代理地址, 来源说明)；地址为空表示直连。

    与通用约定的差异：**默认直连，不回退全局 HTTPS_PROXY**。原因是本站套 Cloudflare，
    经境外代理节点访问会被判为可疑数据中心 IP 而返回 403 质询（2026-10-28 实测），
    直连家庭宽带出口才稳定。
    """
    value = (os.getenv("SXSY_PROXY") or "").strip()
    if value:
        if value.lower() in DIRECT_PROXY_VALUES:
            return "", "SXSY_PROXY=直连"
        return value, "SXSY_PROXY"
    ignored = next(
        (name for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy",
                           "ALL_PROXY", "all_proxy")
         if (os.getenv(name) or "").strip()),
        "",
    )
    return "", (f"默认直连，已忽略 {ignored}" if ignored else "默认直连")


def trusted_url(url):
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and bool(re.fullmatch(r"sxsy(?:[0-9]+\.com|\.pw)", parsed.hostname or "")))


def build_session(proxy: str, timeout: int):
    if requests is None:
        raise RuntimeError("缺少 requests，请在青龙 Python 依赖中安装")

    class SiteSession(requests.Session):
        def request(self, method, url, **kwargs):
            if not trusted_url(url):
                raise ValueError("拒绝非站点 HTTPS 地址")
            kwargs.setdefault("timeout", timeout)
            return super().request(method, url, **kwargs)

        def get_redirect_target(self, response):
            target = super().get_redirect_target(response)
            if target and not trusted_url(urljoin(response.url, target)):
                raise ValueError("拒绝不受信任的重定向")
            return target

    s = SiteSession()
    s.headers.update({"User-Agent": UA, "Referer": BASE + "/",
                      "Accept-Language": "zh-CN,zh;q=0.9"})
    s.trust_env = False
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    s._timeout = timeout
    s.identity_seen = set()
    return s


def show_identity(session, text):
    # Discuz 的公开 UID 直接展示。只读数字 UID，不读取 Cookie 中的身份字段。
    match = re.search(r"discuz_uid\s*=\s*['\"]([1-9][0-9]*)['\"]", text)
    if match and match.group(1) not in session.identity_seen:
        session.identity_seen.add(match.group(1))
        print(f"公开 UID {match.group(1)}")


# ---------------- HTTP 重试层 ----------------
def page_title(html: str) -> str:
    """提取页面标题（用于错误诊断，截断避免刷屏）。"""
    m = re.search(r"<title>(.*?)</title>", html or "", re.S | re.I)
    return m.group(1).strip()[:60] if m else ""


def is_site_error(resp) -> bool:
    """是否为 CDN/源站临时错误页。

    Cloudflare 回源超时会返回 520~526（本站实测 522），状态码是首要判据；
    个别 CDN 用 200 包装错误页，再按标题兜底识别。
    """
    if resp.status_code in _SITE_ERROR_STATUS:
        return True
    return bool(re.search(
        r"\b5\d{2}:\s*(Connection timed out|Web server is down|Origin is unreachable)",
        page_title(resp.text), re.I))


def is_cf_challenge(resp) -> bool:
    """是否为 Cloudflare 人机质询页（出口 IP 被风控）。

    质询页既没有 formhash 也没有 discuz_uid，若当成正常页面处理，会被误读成
    "Cookie 失效/站点改版"，进而清掉有效缓存去登录，而登录同样会被拦。
    """
    if resp is None:
        return False
    headers = getattr(resp, "headers", None) or {}
    if str(headers.get("cf-mitigated") or "").lower() == "challenge":
        return True
    if resp.status_code not in (403, 429, 503):
        return False
    if any(mark in page_title(resp.text) for mark in CF_CHALLENGE_TITLE_MARKERS):
        return True
    return "challenge-platform" in (resp.text or "")


def _is_challenge_err(err: str) -> bool:
    """get_retry 的错误描述是否来自 CF 人机质询。"""
    return CF_CHALLENGE_MARK in (err or "")


def get_retry(session: requests.Session, url: str, headers: dict = None,
              debug: bool = False, label: str = "请求",
              tries: int = HTTP_TRIES) -> tuple:
    """GET 带退避重试，返回 (响应, 错误描述)；成功时错误描述为空串。

    网络异常与 CDN/源站 5xx（Cloudflare 522 等）都重试——这类故障通常持续几秒
    到几十秒，一次成功请求就能继续流程，比直接判失败划算得多。
    CF 人机质询单独处理：绑定出口 IP，同一出口连打只会加重风控，故最多试
    CF_CHALLENGE_TRIES 次；仍被拦则返回带 CF_CHALLENGE_MARK 的错误，交调用方定性。
    """
    last_err = ""
    cf_hits = 0
    for attempt in range(1, tries + 1):
        try:
            r = session.get(url, timeout=session._timeout, headers=headers)
        except Exception as e:
            last_err = f"网络异常（{type(e).__name__}）"
        else:
            if is_cf_challenge(r):
                cf_hits += 1
                last_err = f"{CF_CHALLENGE_MARK}（HTTP {r.status_code}）"
                if debug:
                    print(f"    [debug] {label} 命中 CF 质询页（第 {cf_hits} 次）")
                if cf_hits >= CF_CHALLENGE_TRIES or attempt >= tries:
                    print(f"    ⛔ {label} 命中 {last_err}，停止重试")
                    return None, last_err
                print(f"    ⏳ {label} 命中 {last_err}，{CF_CHALLENGE_BACKOFF}s 后重试")
                time.sleep(CF_CHALLENGE_BACKOFF)
                continue
            if not is_site_error(r):
                if 200 <= r.status_code < 300:
                    show_identity(session, r.text)
                    return r, ""
                # 4xx（以及未列入瞬时故障的 5xx）不是可重试的临时错误：原样报出状态码与标题，
                # 避免调用方把 WAF 拦截页/404 误读成"未登录/页面改版"
                title = ""
                last_err = f"HTTP {r.status_code}" + (f"「{title}」" if title else "")
                print(f"    ⛔ {label} 返回 {last_err}，不是可用页面")
                return None, last_err
            title = ""
            last_err = f"HTTP {r.status_code}" + (f"「{title}」" if title else "")
            if debug:
                print(f"    [debug] {label} 第 {attempt}/{tries} 次返回错误页: {last_err}")
        if attempt < tries:
            delay = HTTP_BACKOFF[min(attempt - 1, len(HTTP_BACKOFF) - 1)]
            print(f"    ⏳ {label} 暂时不可用（{last_err}），{delay}s 后重试（{attempt}/{tries}）")
            time.sleep(delay)
    return None, last_err


# ---------------- 域名发现 ----------------
# 站点换域名时旧域名会 301 到"最新地址"导航页：HTTP 200、标题正常，但没有 formhash。
# requests 默认跟随重定向，于是登录流程拿到的是导航页，报出来是"登录页无 formhash"，
# 看着像改版或风控，实际只是域名换了。运行前先探测可用域名，避免整轮签到白跑。
def apply_base(base: str) -> None:
    """切换站点根地址，并同步所有派生 URL。"""
    global BASE, SIGN_URL, LOGIN_URL, FORUM_URL
    BASE = base.rstrip("/")
    SIGN_URL = f"{BASE}/plugin.php?id=k_misign:sign"
    LOGIN_URL = f"{BASE}/member.php?mod=logging&action=login"
    FORUM_URL = f"{BASE}/forum.php"


_PROBE_TIMEOUT = 15             # 域名探测超时上限（秒）：站点响应不稳，探测不必等满用户配置


def _login_page_probe(session: requests.Session, base: str,
                      debug: bool = False) -> tuple:
    """探测 base 是否为可用站点，返回 (状态, 说明, 页面文本)。

    状态语义：True 可用；False 不可用；None 出口 IP 被 CF 质询（换域名同样会被拦）。
    只对网络异常重试一次（本站偶发读超时很常见）；HTTP 层结果不重试，
    4xx/5xx 的语义要原样保留，且逐个别重试比单点长等更快出结果。
    """
    url = f"{base.rstrip('/')}/member.php?mod=logging&action=login"
    timeout = min(session._timeout, _PROBE_TIMEOUT)
    r, last_err = None, ""
    for attempt in (1, 2):
        try:
            r = session.get(url, timeout=timeout)
            break
        except Exception as e:
            last_err = f"网络异常（{type(e).__name__}）"
            if debug:
                print(f"    [debug] 探测 {base} 第 {attempt} 次异常: {last_err}")
            if attempt == 1:
                time.sleep(2)
    if r is None:
        return False, last_err, ""
    if is_cf_challenge(r):
        return None, f"{CF_CHALLENGE_MARK}（HTTP {r.status_code}）", ""
    if r.status_code >= 400:
        return False, f"HTTP {r.status_code}", ""
    if re.search(r'name="formhash"\s+value="[a-f0-9]+"', r.text):
        return True, f"HTTP {r.status_code}", r.text
    return False, f"HTTP {r.status_code} 无 formhash", r.text


def _domain_from_nav(html: str) -> str:
    """从"最新地址"导航页解析站点当前主域名（站点自己维护的 CONFIG）。"""
    m = (re.search(r'websiteUrl\s*:\s*"([^"]+)"', html or "")
         or re.search(r'latestDomain\s*:\s*"([^"]+)"', html or ""))
    if not m:
        return ""
    url = m.group(1).strip().rstrip("/")
    url = url if url.startswith("http") else "https://" + url
    return f"https://{urlsplit(url).hostname}" if trusted_url(url) else ""


def resolve_base(session: requests.Session, debug: bool = False) -> tuple:
    """确定本次运行使用的站点域名，返回 (base, 说明)；找不到返回 ("", 原因汇总)。

    顺序：候选域名逐个探测 -> 探测中若落到导航页则解析其最新域名 -> 主动再取一次导航页。
    命中 CF 质询时立即返回该域名：同一出口换域名一样被拦，继续探测只是徒增风控。
    """
    notes, nav_domains = [], []

    def _try(base: str):
        state, note, html = _login_page_probe(session, base, debug)
        if state is True:
            return base, note
        if state is None:
            return base, note
        notes.append(f"{base} {note}")
        found = _domain_from_nav(html)
        if found:
            nav_domains.append(found)
        return None

    for base in DOMAIN_CANDIDATES:
        hit = _try(base)
        if hit:
            return hit

    # 候选都不可用：导航页是站点自维护的最新域名来源，主动再取一次
    r, err = get_retry(session, NAV_URL, debug=debug, label="最新地址页", tries=2)
    if r is not None:
        found = _domain_from_nav(r.text)
        if found:
            nav_domains.append(found)
    else:
        notes.append(f"{NAV_URL} {err}")

    tried = {b.rstrip("/").lower() for b in DOMAIN_CANDIDATES}
    for base in dict.fromkeys(nav_domains):
        if base.rstrip("/").lower() in tried:
            continue
        hit = _try(base)
        if hit:
            return hit
    return "", "；".join(notes)


# ---------------- Cookie 缓存（仅账密模式使用） ----------------
@contextlib.contextmanager
def cache_lock():
    # 同目录锁保护整段读改写，临时文件创建时即为 0600。
    fd = os.open(str(COOKIE_CACHE) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def read_cookie_cache() -> dict:
    try:
        with cache_lock():
            data = json.loads(COOKIE_CACHE.read_text(encoding="utf-8"))
            accounts = data.get("accounts", {})
            return accounts if isinstance(accounts, dict) else {}
    except Exception:
        return {}


def write_cookie_cache(username: str, cookie_str: str):
    temporary = None
    try:
        with cache_lock():
            try:
                data = json.loads(COOKIE_CACHE.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            if not isinstance(data, dict) or not isinstance(data.get("accounts"), dict):
                data = {"accounts": {}}
            data["accounts"][username] = {
                "cookies": cookie_str,
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            fd, temporary = tempfile.mkstemp(prefix=".sxsy_cookie_", dir=COOKIE_CACHE.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, COOKIE_CACHE)
    except Exception:
        print("⚠️ Cookie 缓存写入失败，本次签到继续")
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


# ---------------- 登录层 ----------------
def check_cookie_valid(session: requests.Session, debug: bool = False):
    """GET forum.php 判登录态：discuz_uid > 0 即有效。

    返回 True/False；站点临时故障（重试后仍拿不到正常页面）返回 None，
    调用方据此保留缓存而不是误判为"Cookie 失效"。
    """
    r, err = get_retry(session, FORUM_URL, debug=debug, label="论坛首页")
    if r is None:
        if _is_challenge_err(err):
            print(f"    ⚠️ 论坛首页被拦截（{err}）：出口 IP 被风控，与 Cookie 无关，保留缓存先试签到")
        else:
            print(f"    ⚠️ 论坛首页暂时不可用（{err}）")
        return None
    m = re.search(r"discuz_uid\s*=\s*'(\d+)'", r.text)
    uid = m.group(1) if m else "0"
    if debug:
        print(f"    [debug] forum.php uid={uid}, HTTP {r.status_code}")
    show_identity(session, r.text)
    return (uid != "0") if m else None


def _ocr(session: requests.Session, idhash: str, ocr, debug: bool) -> str:
    """下载 seccode 图片并识别一次，返回识别文本；图片拿不到时返回空串（交给登录重试）。"""
    r, err = get_retry(
        session,
        f"{BASE}/misc.php?mod=seccode&update={time.time()}&idhash={idhash}",
        debug=debug, label="验证码图片", tries=2)
    if r is None:
        print(f"    ⚠️ 验证码图片暂时不可用（{err}）")
        return ""
    if debug:
        print(f"    [debug] 验证码图片 HTTP {r.status_code}, {len(r.content)}B")
    return ocr.classification(r.content)


def discuz_login(session: requests.Session, username: str, password: str,
                 debug: bool = False) -> tuple:
    """账密登录（含 seccode OCR）。返回 (是否成功, 消息)。成功时会话已带登录 Cookie。"""
    try:
        import ddddocr
        ocr = ddddocr.DdddOcr(old=False)
    except ImportError:
        return False, "缺少 ddddocr 库：账密登录需要它识别验证码，请在「依赖管理」-「Python」安装 ddddocr（或改用 Cookie 模式）"

    login_referer = LOGIN_URL
    last_reason = "未知原因"
    for attempt in range(1, LOGIN_MAX_TRIES + 1):
        r, err = get_retry(session, login_referer, debug=debug,
                           label="登录页", tries=2)
        if r is None:
            if _is_challenge_err(err):
                # 质询绑定出口 IP：再打只会加重风控，也不该耗掉登录重试次数
                return False, (f"登录页被拦截（{err}）：出口 IP 被 Cloudflare 风控，"
                               f"与账号密码无关；稍后重试，或用 SXSY_PROXY=direct 强制直连")
            last_reason = f"登录页暂时不可用（{err}）"
            print(f"    ⚠️ 第 {attempt}/{LOGIN_MAX_TRIES} 次 {last_reason}，重试...")
            time.sleep(2)
            continue

        m = re.search(r'name="formhash"\s+value="([a-f0-9]+)"', r.text)
        formhash = m.group(1) if m else ""
        m = re.search(r"updateseccode\('([a-zA-Z0-9]+)'", r.text)
        idhash = m.group(1) if m else ""
        if not formhash:
            # 排除瞬时错误页后仍无 formhash，才可能是改版或风控页；带上状态码与标题便于定位
            last_reason = (f"登录页无 formhash（HTTP {r.status_code}"
                           f"，页面结构不符）")
            print(f"    ⚠️ 第 {attempt}/{LOGIN_MAX_TRIES} 次 {last_reason}，重试...")
            time.sleep(3)
            continue

        data = {
            "formhash": formhash,
            "referer": FORUM_URL,
            "loginfield": "username",
            "username": username,
            "password": password,
            "questionid": "0",
            "answer": "",
            "cookietime": "2592000",
        }
        if idhash:
            # seccode 链路：update 接口拿 seccodehash -> 取图 -> OCR
            ru, err = get_retry(
                session,
                f"{BASE}/misc.php?mod=seccode&action=update&idhash={idhash}"
                f"&{time.time()}&modid={MODID}&inajax=1",
                debug=debug, label="验证码接口", tries=2,
            )
            if ru is None:
                if _is_challenge_err(err):
                    return False, (f"验证码接口被拦截（{err}）：出口 IP 被 Cloudflare 风控，"
                                   f"与账号密码无关；稍后重试，或用 SXSY_PROXY=direct 强制直连")
                last_reason = f"验证码接口暂时不可用（{err}）"
                print(f"    ⚠️ 第 {attempt}/{LOGIN_MAX_TRIES} 次 {last_reason}，重试...")
                time.sleep(2)
                continue
            hm = re.search(r'name="seccodehash"\s+type="hidden"\s+value="([a-zA-Z0-9]+)"', ru.text)
            seccodehash = hm.group(1) if hm else ""
            if not seccodehash:
                last_reason = "验证码 update 接口未返回 seccodehash（站点可能改版）"
                print(f"    ⚠️ 第 {attempt}/{LOGIN_MAX_TRIES} 次 {last_reason}，重试...")
                time.sleep(2)
                continue
            try:
                code = _ocr(session, idhash, ocr, debug)
            except Exception as e:
                return False, "验证码识别异常，请检查 ddddocr 安装"
            if debug:
                print(f"    [debug] 第 {attempt} 次 OCR 完成，不记录验证码")
            if code:
                data["seccodehash"] = seccodehash
                data["seccodemodid"] = MODID
                data["seccodeverify"] = code
        # 无 idhash 说明站点关闭验证码，直接裸登录

        try:
            r2 = session.post(
                f"{LOGIN_URL}&loginsubmit=yes",
                data=data,
                timeout=session._timeout,
                headers={"Referer": login_referer},
                allow_redirects=False,
            )
        except Exception as e:
            return False, f"登录请求失败（{type(e).__name__}）"

        body = r2.text
        if r2.status_code == 200 and ("succeedhandle" in body or "succeedlocation" in body):
            return True, "登录成功"

        if is_cf_challenge(r2):
            # POST 同样会被质询：继续重试只会被拦，直接如实报出
            return False, (f"登录接口被拦截（{CF_CHALLENGE_MARK}，HTTP {r2.status_code}）："
                           f"出口 IP 被 Cloudflare 风控，与账号密码无关；稍后重试，或用 SXSY_PROXY=direct 强制直连")

        if is_site_error(r2):
            last_reason = f"登录接口返回错误页（HTTP {r2.status_code}）"
            print(f"    ⚠️ 第 {attempt}/{LOGIN_MAX_TRIES} 次 {last_reason}，重试...")
            time.sleep(3)
            continue

        # 失败原因分类
        if any(kw in body for kw in _LOGIN_FATAL_KEYWORDS):
            err = re.search(r"show_error\('([^']{0,120})", body)
            return False, "账号密码错误或账号受限，停止重试"
        if "验证码" in body:
            last_reason = "验证码识别错误"
            print(f"    ⚠️ 第 {attempt}/{LOGIN_MAX_TRIES} 次验证码识别错误，重试...")
            time.sleep(2)
            continue
        err = re.search(r"show_error\('([^']{0,120})", body)
        last_reason = "登录未成功，响应未包含成功标志"
        print(f"    ⚠️ 第 {attempt}/{LOGIN_MAX_TRIES} 次{last_reason}，重试...")
        time.sleep(2)

    return False, f"登录失败（{last_reason}）"


# ---------------- 签到层 ----------------
def _get_sign_page(session: requests.Session, debug: bool = False) -> tuple:
    """GET 签到页，返回 (HTML, 错误描述)；成功时错误描述为空串。"""
    r, err = get_retry(session, SIGN_URL, headers={"Referer": FORUM_URL},
                       debug=debug, label="签到页")
    if r is None:
        print(f"⚠️ 签到页请求失败: {err}")
        return "", err
    if debug:
        print(f"    [debug] 签到页 HTTP {r.status_code}, {len(r.text)}B")
    return r.text, ""


def do_signin(session: requests.Session, debug: bool = False) -> dict:
    """
    k_misign 签到。流程（均为实测）：
      1. GET 签到页：有 id="JD_sign" -> 今天未签；无 -> 已签/未登录
      2. GET ...&operation=qiandao&formhash=<fh>&format=text -> 算术题 XML
      3. 计算答案后 GET ...&mathverify_answer=<ans> -> 结果 XML（CDATA 文本）
      4. 回查签到页确认 JD_sign 消失
    返回 {"state": signed_today|success|failed, "message": str, "stats": str}
    """
    html, err = _get_sign_page(session, debug)
    if not html:
        return {"state": "failed", "message": f"签到页请求失败：{err}", "stats": ""}

    if re.search(r"discuz_uid\s*=\s*['\"]0['\"]", html):
        return {"state": "failed", "message": "登录态失效（签到页未登录）", "stats": ""}

    if 'id="JD_sign"' not in html:
        # 无签到按钮：区分「已签」与「Cookie 失效被踢回登录页」
        if re.search(r'id="lxdays"\s+value="\d+"', html):
            return {"state": "signed_today", "message": "今日已签到", "stats": fetch_sign_stats(html)}
        if "member.php?mod=logging" in html or re.search(r"discuz_uid\s*=\s*'0'", html):
            return {"state": "failed", "message": "登录态失效（签到页被跳转登录）", "stats": ""}
        return {"state": "failed", "message": "签到页无签到按钮且无统计信息（页面结构可能变化）", "stats": ""}

    m = re.search(
        r'id="JD_sign"\s+href="plugin\.php\?id=k_misign:sign&operation=qiandao'
        r'&formhash=([a-f0-9]+)&format=text"', html)
    if not m:
        return {"state": "failed", "message": "未解析到 JD_sign 签到链接", "stats": ""}
    formhash = m.group(1)

    sign_headers = {"Referer": SIGN_URL, "X-Requested-With": "XMLHttpRequest"}
    r, err = get_retry(
        session,
        f"{SIGN_URL}&operation=qiandao&formhash={formhash}&format=text",
        headers=sign_headers, debug=debug, label="签到接口", tries=2)
    if r is None:
        return {"state": "failed", "message": f"签到接口请求失败：{err}", "stats": ""}

    q = re.search(r'var q="([^"]*)"', r.text)
    response = r
    if q:
        answer = solve_math(q.group(1))
        if answer is None:
            return {"state": "failed", "message": "算术验证题解析失败", "stats": ""}
        response, err = get_retry(
            session,
            f"{SIGN_URL}&operation=qiandao&formhash={formhash}&format=text"
            f"&mathverify_answer={quote(str(answer))}",
            headers=sign_headers, debug=debug, label="签到确认接口", tries=2)
        if response is None:
            return {"state": "failed", "message": f"签到确认请求失败：{err}", "stats": ""}

    # 支持不开启算术验证的插件，必须由回查或明确业务文案确认。
    cdata = re.search(r"<!\[CDATA\[(.*?)\]\]>", response.text, re.S)
    result_text = cdata.group(1).strip() if cdata else response.text
    confirmed = bool(re.search(r"^(?:今日)?(?:您)?(?:已经|已)?签到成功[！!。.]?$|^(?:您)?(?:今日|今天)?已(?:经)?签到[！!。.]?$", result_text.strip()))
    page, recheck_err = _get_sign_page(session, debug)
    if page:
        if 'id="JD_sign"' not in page and re.search(r'id="lxdays"\s+value="\d+"', page):
            return {"state": "success", "message": "签到成功（回查已确认）", "stats": fetch_sign_stats(page)}
        if re.search(r"discuz_uid\s*=\s*['\"]0['\"]", page):
            return {"state": "failed", "message": "登录态失效（回查未登录）", "stats": ""}
        return {"state": "failed", "message": "签到未生效或回查页面结构变化", "stats": ""}
    if confirmed:
        return {"state": "success", "message": "签到成功（接口明确确认，回查暂不可用）", "stats": ""}
    return {"state": "failed", "message": f"签到结果未确认；{recheck_err}", "stats": ""}


# ---------------- 单账号执行 ----------------
def run_one_account(cred, proxy: str, timeout: int, debug: bool) -> dict:
    """
    cred: (username, password) tuple（账密模式，带缓存）或整段 Cookie 字符串（直签模式）。
    返回 {"success": bool, "message": str, "label": str}
    """
    if isinstance(cred, tuple):
        username, password = cred
        label = "账密账号"
        session = build_session(proxy, timeout)

        # 1) Cookie 缓存优先
        cached = read_cookie_cache().get(username, {}).get("cookies", "")
        if cached:
            for k, v in parse_cookie_str(cached).items():
                session.cookies.set(k, v, domain=urlsplit(BASE).hostname, path="/")
            valid = check_cookie_valid(session, debug)
            if valid is True:
                print("    💾 缓存 Cookie 有效，跳过登录")
            elif valid is False:
                print("    ⚠️ 缓存 Cookie 失效，重新登录")
                session.cookies.clear()
            else:
                # 站点瞬时故障或出口被 CF 质询、无法判断登录态：保留缓存先试签到，避免白白丢会话
                print("    ⚠️ 无法确认 Cookie 状态（站点临时故障/出口被拦），先按缓存继续")

        # 2) 缓存缺失/失效 -> 账密登录
        if not session.cookies:
            ok, msg = discuz_login(session, username, password, debug)
            if not ok:
                return {"success": False, "message": msg, "label": label}
            write_cookie_cache(username, "; ".join(f"{c.name}={c.value}" for c in session.cookies))

        result = do_signin(session, debug)

        # 3) 登录态失效则重登一次再签（只重试一次，防死循环）
        if result["state"] == "failed" and "登录态失效" in result["message"]:
            print("    🔄 登录态失效，重新登录后重试一次")
            session.cookies.clear()
            ok, msg = discuz_login(session, username, password, debug)
            if not ok:
                return {"success": False, "message": msg, "label": label}
            write_cookie_cache(username, "; ".join(f"{c.name}={c.value}" for c in session.cookies))
            result = do_signin(session, debug)
    else:
        # Cookie 直签模式：不缓存、不自动登录
        label = "Cookie"
        session = build_session(proxy, timeout)
        for k, v in parse_cookie_str(cred).items():
            session.cookies.set(k, v, domain=urlsplit(BASE).hostname, path="/")
        result = do_signin(session, debug)
        if result["state"] == "failed" and "登录态失效" in result["message"]:
            result["message"] += "；Cookie 模式失效请重新抓取 Cookie 更新环境变量"

    success = result["state"] in ("success", "signed_today")
    icon = "✅" if result["state"] == "success" else "🔁" if result["state"] == "signed_today" else "❌"
    message = f"{icon} {result['message']}"
    if result.get("stats"):
        message += f"\n      📊 {result['stats']}"
    return {"success": success, "state": result["state"], "message": message, "label": label}


# ---------------- 时间轴、通知与主流程 ----------------
import builtins
import subprocess


def print(*values, **kwargs):
    text = " ".join(str(value) for value in values)
    for line in text.splitlines() or [""]:
        builtins.print(f"[{datetime.now():%H:%M:%S}] {line}", **kwargs)


_stage_number = 0


@contextlib.contextmanager
def stage(name):
    global _stage_number
    _stage_number += 1
    number = _stage_number
    started = time.monotonic()
    print(f"阶段 {number} · {name} · 开始")
    try:
        yield
    finally:
        print(f"阶段 {number} · {name} · 结束，耗时 {time.monotonic() - started:.2f} 秒")


def timed_action(name, action):
    def run(*args, **kwargs):
        with stage(name):
            return action(*args, **kwargs)
    return run


resolve_base = timed_action("候选域名及导航页探测", resolve_base)
check_cookie_valid = timed_action("缓存登录态检查", check_cookie_valid)
discuz_login = timed_action("账密登录与验证码识别", discuz_login)
do_signin = timed_action("签到、算术验证与结果回查", do_signin)


def notify_summary(body, dry_run, status):
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in ("0", "false", "no", "off"):
        return "全局关闭"
    forced = switch in ("1", "true", "yes", "on")
    selectors = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    identities = ("fccba94cf57739f4", Path(__file__).name,
                  "sxsy45_checkin.py", "sxsy45_checkin/sxsy45_checkin.py",
                  "scripts/sxsy45_checkin.py")
    selected = selectors is not None and any(
        fnmatch.fnmatchcase(identity, pattern)
        for pattern in re.split(r"[,;\s]+", selectors.strip()) if pattern
        for identity in identities)
    if not forced and not selected:
        return "按名单关闭"
    if not forced and not env_bool("SXSY_NOTIFY", True):
        return "兼容开关关闭"
    if not forced and env_bool("SXSY_NOTIFY_ONLY_FAIL", False) and status == "success":
        return "兼容仅失败通知"
    if dry_run:
        print("通知预演 · 已生成脱敏摘要，断网模式模拟发送")
        return "预演模拟发送"
    title = "尚香书苑签到"
    # 子进程隔离第三方模块输出并限定通知时长，不改变业务退出码。
    code = """
import importlib.util, pathlib, sys
try:
    if sys.argv[1]:
        spec = importlib.util.spec_from_file_location('_sxsy_notify', sys.argv[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        import notify as module
    sender = getattr(module, 'send', None)
    if not callable(sender):
        sys.exit(3)
except Exception:
    sys.exit(3)
try:
    sender(sys.argv[2], sys.argv[3])
except Exception:
    sys.exit(1)
"""
    directories = [os.getenv("QINGLONG_NOTIFY_DIR", ""),
                   "/ql/data/scripts", "/ql/scripts"]
    candidates = [""] + [str(Path(directory) / "notify.py") for directory in directories
                          if directory and (Path(directory) / "notify.py").is_file()]
    try:
        for path in candidates:
            result = subprocess.run([sys.executable, "-c", code, path, title, body],
                                    capture_output=True, timeout=30, check=False)
            if result.returncode == 0:
                return "已调用 notify.py"
            if result.returncode != 3:
                return "发送失败"
        for directory in directories:
            path = Path(directory) / "sendNotify.js" if directory else None
            if path and path.is_file():
                result = subprocess.run(
                    ["node", "-e", "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).catch(()=>process.exit(1))",
                     str(path), title, body], capture_output=True, timeout=30, check=False)
                return "已调用 sendNotify.js" if result.returncode == 0 else "发送失败"
        return "通知模块不可用"
    except Exception:
        return "发送失败或超时"


def validate_credential(credential):
    if isinstance(credential, tuple):
        if not credential[0] or not credential[1]:
            raise ValueError("账密格式错误，需要非空用户名#密码")
    elif not parse_cookie_str(credential) or any(
            "=" not in part for part in credential.split(";") if part.strip()):
        raise ValueError("Cookie 格式错误，需要完整请求 Cookie")


def main():
    started = time.monotonic()
    dry_run = env_bool("SXSY_DRY_RUN", False)
    accounts = parse_credentials(os.getenv("SXSY_ACCOUNTS", ""))
    print("=" * 60)
    print("尚香书苑签到")
    print(f"开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"运行模式 {'断网预演' if dry_run else '正式执行'} · 账号数 {len(accounts)}")
    results = []
    config_error = ""
    try:
        with stage("配置检查"):
            if not accounts:
                raise ValueError("缺少 SXSY_ACCOUNTS，每个非空行配置用户名#密码或 Cookie")
            try:
                timeout = int(os.getenv("SXSY_TIMEOUT", "30"))
            except ValueError:
                raise ValueError("SXSY_TIMEOUT 必须为整数") from None
            if not 1 <= timeout <= 300:
                raise ValueError("SXSY_TIMEOUT 需在 1 至 300 秒之间")
            proxy, proxy_source = resolve_proxy()
            try:
                valid_proxy = not proxy or (urlsplit(proxy).scheme in ("http", "https")
                                            and bool(urlsplit(proxy).hostname))
            except ValueError:
                valid_proxy = False
            if not valid_proxy:
                raise ValueError("SXSY_PROXY 需要有效 HTTP 或 HTTPS 代理地址")
            print(f"网络出口 {'显式代理（隐藏地址）' if proxy else '直连'}")
            print("配置检查完成")
    except ValueError as exc:
        config_error = str(exc)
        print(f"❌ {config_error}")
    debug = env_bool("SXSY_DEBUG", False)
    domain_error = False
    if not config_error and not dry_run:
        try:
            with build_session(proxy, timeout) as probe:
                base, note = resolve_base(probe, debug)
            if not base:
                print("❌ 未确认可用站点，停止账号请求")
                domain_error = True
            else:
                apply_base(base)
                print(f"站点 {BASE} · 已完成域名探测")
        except Exception as exc:
            print(f"❌ 域名探测失败（{type(exc).__name__}）")
            domain_error = True
    if not config_error:
        for index, credential in enumerate(accounts, 1):
            account_started = time.monotonic()
            print(f"账号 {index}/{len(accounts)} · 开始")
            try:
                with stage("账号参数验证"):
                    validate_credential(credential)
                    print("账号格式有效，不输出凭据")
                if dry_run:
                    with stage("断网预演"):
                        print("DRY_RUN_OK · 已验证配置，模拟域名探测、登录、签到与回查；无网络和缓存写入")
                    result = {"success": True, "state": "dry-run", "message": "断网预演通过"}
                elif domain_error:
                    result = {"success": False, "state": "failed", "message": "域名或运行依赖不可用"}
                else:
                    result = run_one_account(credential, proxy, timeout, debug)
            except ValueError:
                result = {"success": False, "state": "failed", "message": "账号参数格式错误"}
            except Exception as exc:
                result = {"success": False, "state": "failed", "message": f"执行异常（{type(exc).__name__}）"}
            elapsed = round(time.monotonic() - account_started, 2)
            state = result.get("state", "success" if result["success"] else "failed")
            counts = {"total": 1, "success": int(state == "success"),
                      "alreadyComplete": int(state == "signed_today"),
                      "skipped": int(state == "dry-run"), "failed": int(not result["success"])}
            print(result["message"])
            print(f"账号 {index} 统计 · 总任务 1，成功 {counts['success']}，已完成 {counts['alreadyComplete']}，"
                  f"跳过 {counts['skipped']}，失败 {counts['failed']}，耗时 {elapsed:.2f} 秒")
            results.append({"account": index, "success": result["success"], "state": state,
                            "tasks": counts, "elapsedSeconds": elapsed})
            if not dry_run and index < len(accounts):
                time.sleep(2)
    success = sum(item["success"] for item in results)
    failed = len(accounts) - success
    if config_error:
        status, exit_code = "configuration-error", 2
    elif failed:
        status, exit_code = ("partial-failure" if success else "failure"), 1
    else:
        status, exit_code = ("dry-run" if dry_run else "success"), 0
    task_counts = {key: sum(item["tasks"][key] for item in results)
                   for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    report = (f"尚香书苑签到 · 状态 {status}\n账号总数 {len(accounts)}，成功 {success}，失败 {failed}\n"
              f"子任务总数 {task_counts['total']}，成功 {task_counts['success']}，已完成 {task_counts['alreadyComplete']}，"
              f"跳过 {task_counts['skipped']}，失败 {task_counts['failed']}")
    notification = notify_summary(report, dry_run, status)
    print("-" * 60)
    print(report)
    print(f"通知状态 {notification}")
    finished = datetime.now().isoformat(timespec="seconds")
    elapsed = round(time.monotonic() - started, 2)
    print(f"完成时间 {finished} · 总耗时 {elapsed:.2f} 秒 · 最终状态 {status}")
    summary = {"status": status, "mode": "dry-run" if dry_run else "live", "accounts": len(accounts),
               "success": success, "failed": failed, "tasks": task_counts, "results": results,
               "notification": notification, "elapsedSeconds": elapsed, "finishedAt": finished,
               "exitCode": exit_code}
    # 单行机器记录不附加时间戳。
    builtins.print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

# MIT License (effectiveLicense supplied by source catalog)
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
