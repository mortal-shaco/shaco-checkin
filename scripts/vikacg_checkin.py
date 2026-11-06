# -*- coding: utf-8 -*-
# name: 维咔VikACG签到
# cron: 59 9 * * *
# SPDX-License-Identifier: MIT
# 上游作者 zephyr_xiao，来源 zephyr-xiao/qinglong-script
# 上游文件 vikacg_checkin/vikacg_checkin.py，保留原作者署名。
"""
new Env('维咔VikACG签到');
cron: 59 9 * * *

维咔VikACG（www.vikacg.cc，V站）每日钱包签到领积分，纯 API 免验证码。
流程：账密登录换 JWT 双 token（30 天）→ 每日签到（userMission）→ 青龙 notify.py 推送。
登录态（token + 设备指纹）按账号本地缓存复用：缓存有效直接签到；401 先用 refreshToken
静默续期、失败才重新账密登录（缓存只存凭证不存密码，原子写 + 0600 收口）。设备指纹
（X-Device-Code）与 token 绑定且随缓存持久化，避免每次运行换设备触发风控。
连接类网络异常（超时/被掐/代理失败）与 Cloudflare 人机校验页自动重试 2 次并分类报错；
业务 4xx/5xx 不重试。挑战页重试有效的原因：出口 IP 被风控才触发挑战，换一条 TCP 连接
可能落到代理组里另一个干净出口（实测同一代理交替出现 403 挑战与 200）。

接口探测结论（2026-10-07，源自前端 Nuxt bundle 逆向 + 真机验证）：
  POST /api/vikacg/v1/login          {"account","password","platform":"web"} → data.token/refreshToken
  POST /api/vikacg/v1/userMission    {} + Bearer → 200 签到成功 / 409「用户今天已签到」（幂等）
                                     幂等判定为双门槛：HTTP 409 且命中已签关键词才算已签，
                                     避免未来成功文案含「已签」时被误判（关键词只做辅助证据）
  POST /api/vikacg/v1/refreshToken   {"refreshToken":...} → 换发新双 token
  服务端校验浏览器特征头（Sec-Fetch-* 等），缺失报「非法的客户端，请下载官方版本」——
  因此请求头必须完整模拟浏览器（含 Sec-Fetch-Site/Mode/Dest、Sec-Ch-Ua*、X-Client-Name 等）。

环境变量：
  VIKACG_ACCOUNTS        账号：邮箱#密码（多账号仅用换行分隔）
  VIKACG_NOTIFY          true/false 是否推送，兼容保留；通知事件由 QINGLONG_NOTIFY 统一控制
  VIKACG_NOTIFY_ONLY_FAIL true/false 兼容保留的旧开关；通知事件由 QINGLONG_NOTIFY 统一控制
  VIKACG_TIMEOUT         HTTP 超时秒数，默认 30
  VIKACG_DEBUG           true/false 输出调试细节，默认 false
  VIKACG_PROXY           可选代理，如 http://172.17.0.1:7890。默认直连（强制 IPv4），设
                         none/direct 也表示直连；直连被掐断时自动用全局 HTTPS_PROXY 等
                         作备用出口（全局变量不参与主路由选择）
  VIKACG_INSECURE        true/false 跳过 TLS 证书校验（自签代理场景），默认 false
  VIKACG_BASE_URL        站点地址，默认 https://www.vikacg.cc（备用域名时改）
参数获取：在维咔官网正常注册并设置登录密码，使用本人登录邮箱与密码。
在青龙面板“环境变量”中新建 VIKACG_ACCOUNTS，每个非空行写一个邮箱#密码。
密码只在首个 # 后切分，后续 #、&、@ 保持原样；旧的 & 分账号方式不再支持。
VIKACG_DRY_RUN=1 完全断网预演，不读取缓存、不进行登录或签到、不调用通知模块。
QINGLONG_NOTIFY=auto 默认列入通知；1/true/yes/on 强制启用，0/false/no/off 关闭。
QINGLONG_NOTIFY_SCRIPTS 设置时替换默认列表，支持目录路径、文件名、目录编号和通配符，
以逗号、分号或空白分隔，空值关闭全部；QINGLONG_NOTIFY_DIR 指定公开青龙通知模块目录。
旧 VIKACG_NOTIFY 与 VIKACG_NOTIFY_ONLY_FAIL 仅保留名称说明，统一通知策略优先。
副作用仅包含会话登录/续期、钱包签到，以及脚本目录中私密凭据缓存和通知发送。
作者: zephyr_xiao

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
        _ql_notify_identities = ('6eade06114ebb48c', 'scripts/vikacg_checkin.py', 'vikacg_checkin.py', 'vikacg_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import json
import os
import re
import socket
import sys
import time
import tempfile
import importlib.util
import contextlib
import io
import fnmatch
from urllib.parse import urlsplit
import uuid
from datetime import datetime
from pathlib import Path

# 1. UTF-8 强制重配（解决 Windows GBK / 部分容器 locale 问题）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# requests 仅在真实执行阶段加载，断网预演无需第三方依赖。
requests = None

TITLE = "维咔VikACG签到"
DRY_RUN = os.getenv("VIKACG_DRY_RUN", "").lower() in ("1", "true", "yes", "on")


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}")


def send_notify(summary, dry_run):
    """通知只包含固定状态及数字，屏蔽通知模块自身的输出。"""
    enabled = {"1", "true", "yes", "on"}
    disabled = {"0", "false", "no", "off"}
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    selectors = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    identities = ("6eade06114ebb48c", "candidate.py", "vikacg_checkin.py",
                  "vikacg_checkin/vikacg_checkin.py", Path(__file__).name)
    selected = True  # 本脚本列入默认通知列表。
    if selectors is not None:
        selected = any(fnmatch.fnmatch(identity, pattern)
                       for pattern in re.split(r"[,;\s]+", selectors.strip()) if pattern
                       for identity in identities)
    if switch in disabled or (switch not in enabled and not selected):
        return "已关闭"
    body = (f"状态 {summary['status']}，账号总数 {summary['total']}，"
            f"成功 {summary['success']}，失败 {summary['failed']}，"
            f"预演 {summary['dryRunCount']}")
    if dry_run:
        log("通知阶段已生成脱敏预演摘要，断网模式跳过发送")
        return "断网预演"
    paths = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
    try:
        # 不记录第三方通知模块的异常、配置、返回值或标准输出。
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                from notify import send
            except ImportError:
                send = None
                for path in paths:
                    if path.is_file():
                        spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        send = module.send
                        break
            if send is None:
                return "通知模块不可用"
            for attempt in range(3):
                try:
                    result = send(TITLE, body)
                    if result is False:
                        raise RuntimeError("通知失败")
                    return "已调用通知模块"
                except Exception:
                    if attempt == 2:
                        return "通知发送失败"
                    time.sleep(3)
    except Exception:
        return "通知发送失败"


# ============ 常量与环境变量 ============

BASE_URL = os.getenv("VIKACG_BASE_URL", "https://www.vikacg.cc").rstrip("/")
API_BASE = BASE_URL + "/api/vikacg/v1"
TOKEN_CACHE_FILE = Path(__file__).resolve().parent / "vikacg_token.json"

# 站点直连可达：真正的问题是 IPv6（AAAA 记录在大陆常被 reset）和代理出口被 CF 风控。
# 因此默认直连并强制 IPv4，不再回退 HTTPS_PROXY 之类全局代理变量（青龙常给任务注入），
# 只有显式设置 VIKACG_PROXY 才走代理。
DIRECT_ALIASES = ("none", "direct", "off", "0", "false")
# 全局代理变量只在「直连被掐断」时作为备用出口，不参与主路由选择
GLOBAL_PROXY_KEYS = (
    "HTTPS_PROXY", "https_proxy",
    "HTTP_PROXY", "http_proxy",
    "ALL_PROXY", "all_proxy",
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

ALREADY_SIGNED_IN_KEYWORDS = [
    "已签到", "已经签到", "今日已签", "您已签到", "您今日已",
    "签到过", "重复签到",
    "already signed", "already checked",
]
# ⚠️ 不要把"签到成功""签到完成"放入此列表（首次成功标志，不是幂等提示）；
#    英文关键词用组合词，避免裸 "signed in" 误伤英文成功文案


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
    """每个非空行独立校验，密码中的 #、&、@ 原样保留。"""
    accounts = []
    for line in env_value.splitlines():
        if not line.strip():
            continue
        account, separator, password = line.partition("#")
        account = account.strip()
        accounts.append((account, password) if separator and account and password else None)
    return accounts


def resolve_proxy() -> tuple:
    """解析代理配置，返回 (代理地址, 来源说明)。默认返回直连。

    只认 VIKACG_PROXY：青龙常给任务注入全局 HTTPS_PROXY，撞上被 Cloudflare 风控的
    数据中心出口就整站 403 挑战，所以这里刻意不回退全局代理变量。
    值为 none/direct/off 等也按直连处理，方便在面板里显式声明。
    """
    value = (os.getenv("VIKACG_PROXY") or "").strip()
    if not value or value.lower() in DIRECT_ALIASES:
        return "", "直连"
    return value, "VIKACG_PROXY"


def resolve_env_proxy() -> tuple:
    """读取环境里的代理（仅作直连失败时的备用出口），返回 (代理地址, 变量名)。

    青龙常给任务注入全局 HTTPS_PROXY，直连被掐断（大陆到 Cloudflare 的瞬时 reset
    是成片出现的）时用它兜底，比整轮任务失败强；主路由仍是直连。
    """
    for name in GLOBAL_PROXY_KEYS:
        value = (os.getenv(name) or "").strip()
        if value:
            return value, name
    return "", ""


def force_ipv4():
    """直连时只解析 IPv4：站点 A 记录稳定可用，AAAA 记录在大陆常被 reset。

    urllib3 在建立连接时调用 allowed_gai_family()，替换它就等于全局禁用 IPv6，
    只影响当前进程，不动系统配置。
    """
    try:
        from urllib3.util import connection as urllib3_connection
        urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
    except Exception:
        pass


def mask(s: str) -> str:
    """账号脱敏：保留前 2 后 2，邮箱保留 @ 之后。"""
    if not s:
        return ""
    if "@" in s:
        head, tail = s.split("@", 1)
        if len(head) <= 2:
            return head[0] + "*@" + tail
        return head[:2] + "*" * (len(head) - 2) + "@" + tail
    if len(s) <= 2:
        return s[0] + "*"
    if len(s) <= 4:
        # 短串头尾切片会重叠导致字符重复出现，直接中间打码
        return s[0] + "*" * (len(s) - 1)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


def _is_already_signed_in(msg: str) -> bool:
    if not isinstance(msg, str) or not msg:
        return False
    return any(kw.lower() in msg.lower() for kw in ALREADY_SIGNED_IN_KEYWORDS)


def jwt_exp(token: str) -> int:
    """解析 JWT payload 的 exp（Unix 秒）。非标准 JWT / 解析失败返回 0，由调用方回退 TTL。"""
    try:
        parts = (token or "").split(".")
        if len(parts) != 3:
            return 0
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        return int(data.get("exp") or 0)
    except Exception:
        return 0


# ============ 请求层 ============

class NetworkError(RuntimeError):
    """网络请求重试耗尽后的失败，message 已含分类与排查指引。"""


# 重试间隔（秒）：连接类异常与 CF 挑战页/网关页共用；正常业务响应（含 4xx/5xx）不重试
NETWORK_RETRY_DELAYS = (3, 6)


def describe_network_error(e: Exception) -> str:
    """把 requests 异常翻译成可排查的人话。判断顺序必须从特殊到一般：
    ConnectTimeout/ProxyError/SSLError 都是 ConnectionError 的子类，反着判会被吞。"""
    if isinstance(e, requests.exceptions.ConnectTimeout):
        return "连接超时"
    if isinstance(e, requests.exceptions.ReadTimeout):
        return "响应超时"
    if isinstance(e, requests.exceptions.ProxyError):
        return "代理连接失败（检查 VIKACG_PROXY 是否可用）"
    if isinstance(e, requests.exceptions.SSLError):
        return "TLS 握手失败（直连被掐断或代理异常）"
    if isinstance(e, requests.exceptions.ConnectionError):
        return "连接失败（直连与备用代理均不可达，检查网络或设 VIKACG_PROXY）"
    return "网络请求异常"


def clean_error_text(text: str, limit: int = 200) -> str:
    """非 JSON 响应的错误文本清洗：去标签、压空白、截断，避免拦截页 HTML 原文进推送。"""
    if not text:
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", text)
    collapsed = re.sub(r"\s+", " ", no_tags).strip()
    if len(collapsed) > limit:
        collapsed = collapsed[:limit] + "…"
    return collapsed


def looks_like_intercept_page(text: str) -> bool:
    """检测 Cloudflare 挑战页 / 网关错误页特征，命中时给用户明确提示而非一坨 HTML。"""
    if not text:
        return False
    head = text[:2000].lower()
    markers = (
        "just a moment", "cloudflare", "cf-browser-verification", "cf_chl",
        "attention required", "checking your browser",
        "bad gateway", "gateway timeout", "service temporarily unavailable",
    )
    return any(m in head for m in markers)


def is_cf_challenge(resp) -> bool:
    """是否命中 Cloudflare 人机校验（站点被挑战时整站返回该响应头）。"""
    return (resp.headers.get("Cf-Mitigated") or "").strip().lower() == "challenge"


def is_transient_intercept(resp) -> bool:
    """响应是否是 CF 人机校验页 / 网关错误页（换连接重试有意义的那一类）。

    挑战由出口 IP 风控触发，整站（含 API）都会返回 403 HTML；代理组有多个节点/IP 时，
    重连可能换个出口就通，所以这类响应值得重试，而业务 4xx/5xx 不该重试。
    判定顺序：CF 专属响应头（最准）→ Content-Type 是 JSON 直接排除 → 正文特征兜底。
    """
    if is_cf_challenge(resp):
        return True
    if "application/json" in (resp.headers.get("Content-Type") or "").lower():
        return False
    body = getattr(resp, "text", "") or ""
    return isinstance(body, str) and looks_like_intercept_page(body)


# 服务端校验浏览器特征头（Sec-Fetch-* 等），缺失报「非法的客户端」，
# 因此必须完整模拟 Chrome 浏览器请求；X-Client-Name/Architecture 来自前端 bundle 硬编码。
BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="126", "Google Chrome";v="126", "Not?A_Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Client-Name": "VikACG Moonlight",
    "Architecture": "AixPot",
    "Referer": BASE_URL + "/",
    "Origin": BASE_URL,
}


def build_headers(device_code: str, client_code: str, token: str = "") -> dict:
    headers = dict(BASE_HEADERS)
    headers["X-Device-Code"] = device_code
    headers["X-Client-Code"] = client_code
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def api_post(session: "requests.Session", path: str, payload: dict, device_code: str,
             client_code: str, token: str = "", timeout: int = 30) -> dict:
    """POST JSON 并返回 {http_code, json}。

    两类情况按 NETWORK_RETRY_DELAYS 重试，耗尽后抛 NetworkError（连接类异常）或
    返回带拦截提示的失败 JSON（挑战页）：连接类网络异常，以及 CF 人机校验/网关拦截页。
    其余 HTTP 响应（含业务 4xx/5xx）不重试，交由调用方按业务语义处理。
    """
    for attempt in range(1 + len(NETWORK_RETRY_DELAYS)):
        try:
            resp = session.post(
                API_BASE + path,
                json=payload,
                headers=build_headers(device_code, client_code, token),
                timeout=timeout,
                allow_redirects=False,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt >= len(NETWORK_RETRY_DELAYS):
                raise NetworkError(f"网络请求失败：{describe_network_error(e)}") from e
            delay = NETWORK_RETRY_DELAYS[attempt]
            log(f"⚠️ 网络异常（{describe_network_error(e)}），"
                  f"{delay}s 后重试（{attempt + 1}/{len(NETWORK_RETRY_DELAYS)}）")
            time.sleep(delay)
            continue
        # 挑战页重试：新连接可能落到代理组里另一个没被风控的出口
        if attempt < len(NETWORK_RETRY_DELAYS) and is_transient_intercept(resp):
            delay = NETWORK_RETRY_DELAYS[attempt]
            log(f"⚠️ 命中 Cloudflare 人机校验/网关拦截页，"
                  f"{delay}s 后换连接重试（{attempt + 1}/{len(NETWORK_RETRY_DELAYS)}）")
            time.sleep(delay)
            continue
        break
    try:
        data = resp.json()
    except Exception:
        data = {"status": "fail", "message": "响应格式错误或网关拦截"}
    return {"http_code": resp.status_code, "json": data if isinstance(data, dict) else {}}


# ============ 会话与双路由 ============

def make_session(proxy: str = "") -> "requests.Session":
    """构造会话：proxy 为空即直连（强制 IPv4）。

    trust_env 一律关闭，代理只由入参决定；否则 requests 会自己从环境变量里读代理，
    绕过这里的主/备路由设计。
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    # 默认校验 TLS 证书（登录请求含明文密码，禁校验有 MITM 风险）；
    # 自签代理等场景用 VIKACG_INSECURE=true 显式放开
    session.verify = not env_bool("VIKACG_INSECURE", False)
    session.trust_env = False
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})
    else:
        force_ipv4()
    return session


class FailoverSession:
    """主路由优先、连接类失败自动切备用路由的会话包装。

    主路由默认直连（强制 IPv4，不会被 CF 风控），但大陆到 Cloudflare 的 reset 是
    成片出现的，可能连续十几秒全部失败；此时用备用代理重发同一个请求，避免整轮任务
    因瞬时网络抖动失败。主路由是代理时备用路由为直连，同理兜底。
    只接管 post()，其余行为由内层 Session 决定。
    """

    def __init__(self, primary, fallback=None, primary_desc: str = "", fallback_desc: str = ""):
        self.primary = primary
        self.fallback = fallback
        self.primary_desc = primary_desc
        self.fallback_desc = fallback_desc
        self.switched = False

    def post(self, url, **kwargs):
        try:
            return self.primary.post(url, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if self.fallback is None:
                raise
            if not self.switched:
                self.switched = True
                log(f"🔀 {self.primary_desc}不可用，本次运行改用{self.fallback_desc}")
            return self.fallback.post(url, **kwargs)


# ============ 凭证缓存（只存凭证与设备指纹，绝不存密码） ============

def read_token_cache() -> dict:
    try:
        if TOKEN_CACHE_FILE.is_symlink():
            raise RuntimeError("缓存路径不能是符号链接")
        data = json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
        accounts = data.get("accounts", {}) if isinstance(data, dict) else {}
        return {key: value for key, value in accounts.items() if isinstance(value, dict)} if isinstance(accounts, dict) else {}
    except (OSError, ValueError):
        return {}


def write_token_cache(account: str, entry: dict):
    """独立锁文件串行更新，临时文件创建即 0600，原子替换。"""
    import fcntl  # 青龙 Linux / macOS 标准库。
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    lock_fd = os.open(str(TOKEN_CACHE_FILE) + ".lock", flags, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        accounts = read_token_cache()
        entry = dict(entry)
        entry.pop("from", None)
        entry["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        accounts[account] = entry
        fd, temporary = tempfile.mkstemp(prefix=".vikacg-", dir=TOKEN_CACHE_FILE.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"accounts": accounts}, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, TOKEN_CACHE_FILE)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def cached_token_usable(entry: dict) -> bool:
    """缓存 token 是否可直接复用：设备指纹必须完整，优先 JWT exp（留 12h 余量），
    解不出按 14 天 TTL 兜底。"""
    token = entry.get("token") or ""
    if not token:
        return False
    # 缺设备指纹的缓存带空 X-Device-Code 请求必吃 403「非法的客户端」，
    # 直接判无效，走续期/重登链补齐
    if not entry.get("deviceCode") or not entry.get("clientCode"):
        return False
    exp = jwt_exp(token)
    if exp > 0:
        return time.time() < exp - 12 * 3600
    saved = entry.get("update_time") or ""
    try:
        saved_ts = datetime.strptime(saved, "%Y-%m-%d %H:%M:%S").timestamp()
        return time.time() - saved_ts < 14 * 24 * 3600
    except Exception:
        return False


# ============ 认证链 ============

def new_device_identity() -> tuple:
    """生成新设备指纹（站点前端即为随机 UUIDv4，持久化后复用以稳定风控画像）。"""
    return str(uuid.uuid4()), str(uuid.uuid4())


def do_login(session, account: str, password: str, timeout: int) -> dict:
    """账密登录。成功返回缓存 entry，失败返回 {"error": ...}（含网络重试耗尽）。"""
    device_code, client_code = new_device_identity()
    try:
        r = api_post(session, "/login",
                     {"account": account, "password": password, "platform": "web"},
                     device_code, client_code, timeout=timeout)
    except NetworkError as e:
        return {"error": str(e)}  # e 的 message 已含「网络请求失败：」前缀，别再叠加
    data = r["json"]
    if not isinstance(data.get("data"), dict):
        data["data"] = {}
    if r["http_code"] == 200 and data.get("status") == "success" and (data.get("data") or {}).get("token"):
        d = data["data"]
        return {
            "token": d["token"],
            "refreshToken": d.get("refreshToken") or "",
            "deviceCode": device_code,
            "clientCode": client_code,
            "nickname": (d["user"].get("name") if isinstance(d.get("user"), dict) else ""),
        }
    msg = data.get("message") or data.get("statusMessage") or ""
    return {"error": f"登录失败 (HTTP {r['http_code']})，业务认证未通过"}


def do_refresh(session, entry: dict, timeout: int) -> dict:
    """用 refreshToken 静默续期。成功返回更新后的 entry，业务失败返回 None。

    网络重试耗尽的 NetworkError 上抛：同一 session 同一站点，网络不可达时
    重登也必然失败，让调用方快速失败而不是再白跑一轮登录重试。
    """
    refresh_token = entry.get("refreshToken") or ""
    device_code = entry.get("deviceCode") or ""
    client_code = entry.get("clientCode") or ""
    if not refresh_token or not device_code or not client_code:
        return None  # 指纹任一缺失都会带空头吃 403，直接短路走重登
    try:
        r = api_post(session, "/refreshToken", {"refreshToken": refresh_token},
                     device_code, client_code, timeout=timeout)
    except NetworkError:
        raise
    except Exception:
        return None
    data = r["json"]
    if not isinstance(data.get("data"), dict):
        data["data"] = {}
    if r["http_code"] == 200 and data.get("status") == "success" and (data.get("data") or {}).get("token"):
        d = data["data"]
        entry["token"] = d["token"]
        entry["refreshToken"] = d.get("refreshToken") or refresh_token
        return entry
    return None


def ensure_token(session, account: str, password: str, timeout: int) -> dict:
    """三级降级链：缓存 token → refreshToken 续期 → 重新账密登录。返回 {"token",...} 或 {"error"}。"""
    cache = read_token_cache()
    entry = cache.get(account) or {}
    if cached_token_usable(entry):
        return {**entry, "from": "cache"}

    # 缓存过期 → 先尝试 refreshToken 静默续期（不触碰登录流程，对风控友好）；
    # 网络不可达时直接快速失败，不再走重登白跑一轮重试
    if entry.get("refreshToken"):
        try:
            refreshed = do_refresh(session, entry, timeout)
        except NetworkError as e:
            return {"error": str(e)}
        if refreshed:
            refreshed.pop("from", None)
            write_token_cache(account, refreshed)
            return {**refreshed, "from": "refresh"}

    # 续期失败 / 无缓存 → 完整账密登录
    result = do_login(session, account, password, timeout)
    if result.get("error"):
        return result
    write_token_cache(account, result)
    return {**result, "from": "login"}


# ============ 签到执行 ============

def run_one_task(session, account: str, password: str, timeout: int, debug: bool) -> dict:
    """单账号签到：取 token → userMission（401 续期/重登后仅重试一次）→ 解析结果。

    幂等判定为双门槛（HTTP 409 且命中关键词），关键词不做全局匹配：
    实测站点契约为 409+「用户今天已签到」，全局关键词匹配会在未来成功文案
    含「已签」字样时误判成已签、丢失余额等数据。
    """
    phase_start = time.monotonic()
    log("阶段 2.1 获取登录态（缓存、续期、账密登录）")
    auth = ensure_token(session, account, password, timeout)
    log(f"阶段 2.1 {'失败' if auth.get('error') else '成功'}，耗时 {time.monotonic() - phase_start:.2f} 秒")
    log("阶段 2.2 请求每日钱包签到")
    if auth.get("error"):
        return {"success": False, "error": auth["error"]}
    if debug:
        log(f"🔍 token 来源: {auth.get('from')}")

    def do_mission(token: str):
        return api_post(session, "/userMission", {},
                        auth.get("deviceCode") or "", auth.get("clientCode") or "",
                        token=token, timeout=timeout)

    try:
        result = do_mission(auth["token"])
    except NetworkError as e:
        return {"success": False, "error": str(e)}
    data = result["json"]
    if not isinstance(data.get("data"), dict):
        data["data"] = {}

    # token 失效 → 走续期/重登链路后重试一次（防 401 死循环，只重试一次）
    # 注意：403 不进降级链——它通常是「非法的客户端」这类头校验拒绝，重登必然同样失败
    if result["http_code"] == 401:
        log("🔄 登录态失效，尝试续期/重新登录...")
        try:
            refreshed = do_refresh(session, auth, timeout)
        except NetworkError as e:
            return {"success": False, "error": str(e)}
        if refreshed:
            refreshed.pop("from", None)
            write_token_cache(account, refreshed)
            auth = refreshed
        else:
            auth = do_login(session, account, password, timeout)
            if auth.get("error"):
                return {"success": False, "error": "续期失败且重登失败: " + auth["error"]}
            write_token_cache(account, auth)
        try:
            result = do_mission(auth["token"])
        except NetworkError as e:
            return {"success": False, "error": str(e)}
        data = result["json"]
    if not isinstance(data.get("data"), dict):
        data["data"] = {}

    nickname = auth.get("nickname")
    if isinstance(nickname, str) and nickname:
        print_identity(nickname)
    http_code = result["http_code"]
    message = data.get("message") or data.get("statusMessage") or ""

    # 幂等双门槛：HTTP 409 且命中已签关键词（见函数 docstring）
    if http_code == 409 and _is_already_signed_in(message):
        return {"success": True, "message": "今日已签到"}

    if http_code == 200 and data.get("status") == "success":
        d = data.get("data") or {}
        balance = d.get("count")
        sign_days = d.get("sign_days")
        sign_count = d.get("sign_count")
        parts = []
        if sign_days is not None:
            if is_safe_number(sign_days):
                parts.append(f"连续签到 {sign_days} 天")
        if sign_count is not None:
            if is_safe_number(sign_count):
                parts.append(f"累计 {sign_count} 次")
        if balance is not None:
            if is_safe_number(balance):
                parts.append(f"积分余额 {balance}")
        nickname = auth.get("nickname") or ""
        summary = "，".join(parts) if parts else ""
        who = ""
        # 成功文案自带已签语义时（如「今日已签到，连续 3 天」）如实呈现，不冒充首次成功
        verdict = "今日已签到" if _is_already_signed_in(message) else "签到成功"
        return {"success": True, "message": verdict + who + ("：" + summary if summary else "")}

    if http_code == 401:
        return {"success": False, "error": "未登录或登录已过期 (HTTP 401)"}
    if http_code >= 500:
        return {"success": False, "error": f"服务器内部错误 (HTTP {http_code})"}
    return {"success": False, "error": f"签到失败 (HTTP {http_code})，业务签到未通过"}


# ============ 主流程 ============


def is_safe_number(value):
    return not isinstance(value, bool) and bool(re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", str(value)))


def print_identity(value):
    # 公开昵称直接展示，只有实际包含凭据、手机号、邮箱时才抑制该字段。
    secrets = []
    for item in parse_credentials(os.getenv("VIKACG_ACCOUNTS", "")):
        if item:
            secrets.extend(item)
    if any(secret and secret in value for secret in secrets) or re.search(r"[\w.+-]+@[\w.-]+|(?<!\d)1[3-9]\d{9}(?!\d)", value):
        log("官方身份字段含敏感信息，已抑制显示")
        return
    log("官方昵称 " + json.dumps(value, ensure_ascii=False))


def validate_settings():
    parsed = urlsplit(BASE_URL)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("VIKACG_BASE_URL 必须为无凭据、路径或查询参数的 HTTPS 站点")
    timeout = int(os.getenv("VIKACG_TIMEOUT") or "30")
    if not 1 <= timeout <= 120:
        raise ValueError("VIKACG_TIMEOUT 必须为 1 至 120 秒")
    return timeout


def main():
    global requests
    started = time.monotonic()
    accounts = parse_credentials(os.getenv("VIKACG_ACCOUNTS", ""))
    log("=" * 60)
    log(TITLE + " 开始时间 " + datetime.now().isoformat(timespec="seconds"))
    log(f"运行模式 {'断网预演' if DRY_RUN else '真实执行'}，账号数 {len(accounts)}")
    results = []
    config_error = False
    try:
        log("阶段 1 参数与依赖检查")
        timeout = validate_settings()
        if not accounts:
            raise ValueError("请设置 VIKACG_ACCOUNTS，每行一个邮箱#密码，密码按第一个 # 后原样读取")
        if not DRY_RUN:
            import requests as requests_library
            requests = requests_library
        log(f"阶段 1 检查完成，耗时 {time.monotonic() - started:.2f} 秒")
    except (ValueError, ImportError):
        config_error = True
        log("❌ 配置或依赖检查失败，请核对 HTTPS 站点、超时、账号及 requests 依赖")
    for index, item in enumerate(accounts, 1):
        account_started = time.monotonic()
        log(f"账号 {index}/{len(accounts)} 阶段 2 认证与每日签到")
        if config_error or item is None:
            result = {"success": False, "error": "配置错误，账号行需要邮箱#密码"}
        elif DRY_RUN:
            result = {"success": True, "dryRun": True, "message": "DRY_RUN_OK 参数有效；未请求接口、未读写缓存、未发送通知"}
        else:
            proxy, _ = resolve_proxy()
            env_proxy, _ = resolve_env_proxy()
            primary = make_session(proxy)
            fallback = make_session() if proxy else (make_session(env_proxy) if env_proxy else None)
            session = FailoverSession(primary, fallback, "主路由", "备用路由")
            try:
                result = run_one_task(session, item[0], item[1], timeout, env_bool("VIKACG_DEBUG", False))
            except Exception:
                result = {"success": False, "error": "执行异常，请检查网络、依赖或缓存权限"}
            finally:
                primary.close()
                if fallback:
                    fallback.close()
        already = result.get("success", False) and "今日已签到" in result.get("message", "")
        dry = bool(result.get("dryRun"))
        stats = {"total": 1, "success": int(result.get("success", False) and not already and not dry),
                 "alreadyComplete": int(already), "skipped": int(dry),
                 "failed": int(not result.get("success")), "elapsedSeconds": round(time.monotonic() - account_started, 3)}
        results.append({"account": index, **stats})
        log(f"账号 {index} 阶段 2 {'✅' if result.get('success') else '❌'} {result.get('message') or result.get('error')}")
        log(f"账号 {index} 统计 {json.dumps(stats, ensure_ascii=False)}")
        if not DRY_RUN and index < len(accounts) and not config_error:
            time.sleep(2)
    failed = sum(result["failed"] for result in results)
    success = sum(result["success"] + result["alreadyComplete"] for result in results)
    dry_count = sum(result["skipped"] for result in results)
    exit_code = int(config_error or failed > 0)
    status = "配置错误" if config_error else ("部分失败" if failed and success else "失败" if failed else "预演完成" if DRY_RUN else "成功")
    summary = {"task": TITLE, "status": status, "dryRun": DRY_RUN, "total": len(accounts),
               "success": success, "failed": failed, "dryRunCount": dry_count,
               "accounts": results, "exitCode": exit_code}
    log("阶段 3 汇总与通知")
    summary["notification"] = send_notify(summary, DRY_RUN)
    summary["elapsedSeconds"] = round(time.monotonic() - started, 3)
    summary["finishTime"] = datetime.now().isoformat(timespec="seconds")
    log("-" * 60)
    log(f"账号统计 总数 {len(accounts)}，成功 {success}，失败 {failed}，预演 {dry_count}")
    log(f"子任务统计 总数 {len(accounts)}，成功 {sum(r['success'] for r in results)}，已完成 {sum(r['alreadyComplete'] for r in results)}，跳过 {dry_count}，失败 {failed}")
    log(f"通知状态 {summary['notification']}，总耗时 {summary['elapsedSeconds']} 秒")
    log(f"完成时间 {summary['finishTime']}，最终状态 {status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
