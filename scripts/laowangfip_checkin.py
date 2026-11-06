# -*- coding: utf-8 -*-
# name: 老王FIP签到
# cron: 7 10 * * *
# SPDX-License-Identifier: MIT
# 上游 zephyr-xiao/qinglong-script，作者 zephyr_xiao，MIT 许可。
"""
new Env('老王FIP签到');
cron: 7 10 * * *

老王论坛（laowangfip372.vip）Discuz 论坛 k_misign 插件每日签到。
站点被墙，必须挂代理；登录/签到均需通过 tncode 滑块校验。

为什么可以纯 requests（2026-10-10 实测）：
  站点的 tncode 是未混淆的经典实现（/captcha/tn_code.js 带中文注释，HMAC 密钥明文
  硬编码）。所谓 sign/track 只是：轨迹统计 -> JSON -> 与密钥逐字节 XOR -> base64，
  再用 FNV-1a 对 trackStr+ts+offset+密钥 求签名。全部可在 Python 复现，因此无需
  浏览器：直接取 /captcha/tncode.php 的三联图（带缺口背景 / 拼图块 / 完整背景），
  用 OpenCV 差异法解出缺口位置，再按 JS 算法构造 payload 提交 /captcha/check.php
  即可拿到 `<token>_ok`。服务端行为风控对"正常点数的人类轨迹"放行。

环境变量：
  LWFIP_ACCOUNTS          必填 用户名#密码，多账号仅用换行分隔，密码中的 #、&、@ 保留
  LWFIP_PROXY             可选 HTTP 代理（站点被墙，建议配置），如 http://172.17.0.1:7890；
                          留空时自动回退青龙全局代理（HTTPS_PROXY/HTTP_PROXY/ALL_PROXY）
  LWFIP_PROXY_REQUIRED    可选 默认 false，true 时缺代理直接报错退出
  LWFIP_BASE_URL          可选 默认 https://laowangfip372.vip
  LWFIP_NOTIFY            可选 默认 true
  LWFIP_NOTIFY_ONLY_FAIL  可选 默认 false，true 时仅在有失败时推送
  LWFIP_TIMEOUT           可选 默认 30（秒）
  LWFIP_DEBUG             可选 默认 false，输出调试日志
  LWFIP_MAX_CAPTCHA_RETRY 可选 默认 5，单次滑块识别失败重试次数
  LWFIP_MAX_RETRY         可选 默认 5，账号级任务重试次数（仅可重试错误触发）
  LWFIP_RETRY_INTERVAL    可选 默认 60（秒），账号级重试间隔
  LWFIP_COOKIE_CACHE      可选 默认 false，显式启用后会话 Cookie 以 0600 权限原子落盘复用，
                          后续任务/重试直通签到跳过滑块；false 关闭

依赖：requests、opencv-python-headless、numpy
参数获取：在站点注册并确认可登录，使用本人用户名及密码，填入青龙环境变量
LWFIP_ACCOUNTS，每行 用户名#密码。代理由本人代理服务获取，勿公开含认证的地址。
LWFIP_DRY_RUN=1 完全离线预演，不登录、不签到、不读写缓存、不导入通知模块。
QINGLONG_NOTIFY=auto/1/0 控制通知，QINGLONG_NOTIFY_SCRIPTS 可选择任务。
作者: zephyr_xiao
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
        _ql_notify_identities = ('91d3322eb735e2d2', 'scripts/laowangfip_checkin.py', 'laowangfip_checkin.py', 'laowangfip_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import hashlib
import json
import math
import os
import random
import re
import sys
import time
import builtins
import fnmatch
import subprocess
import tempfile
from urllib.parse import urlsplit
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 第三方业务依赖仅在实跑阶段加载，预演只用标准库。
requests = cv2 = np = None


def print(*args, **kwargs):
    builtins.print(f"[{datetime.now():%H:%M:%S}]", *args, **kwargs)


# ---------------- 站点常量（2026-10-10 实测） ----------------
DEFAULT_BASE_URL = "https://laowangfip372.vip"
LOGIN_PAGE_PATH = "/member.php?mod=logging&action=login"
SIGN_PAGE_PATH = "/plugin.php?id=k_misign:sign"
CAPTCHA_IMG_PATH = "/captcha/tncode.php"
CAPTCHA_CHECK_PATH = "/captcha/check.php"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# tncode 前端加密密钥（站点 /captcha/tn_code.js 明文硬编码）
TNCODE_SECRET = "GWDiugh398huiw0ioOYGd0934hew"

# 会话 Cookie 缓存（命名须匹配仓库 .gitignore 的 cookie_*.json 规则，含真实凭证严禁入库）
COOKIE_CACHE_DIR = Path(__file__).resolve().parent
COOKIE_CACHE_SCOPE = DEFAULT_BASE_URL

# 青龙面板「配置文件 / 环境变量」里配置的全局代理变量
GLOBAL_PROXY_KEYS = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")

# 账号级重试默认值
MAX_RETRY = 5
RETRY_INTERVAL_SEC = 60


# ---------------- 通用工具 ----------------
def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def resolve_proxy(*specific_keys: str) -> tuple:
    """
    解析代理地址，返回 (代理地址, 来源变量名)，两者均可能为空字符串。
    优先级：脚本专属变量 > 青龙全局代理变量 > 空（直连）。
    requests 的 Session.proxies 需显式赋值，不读环境变量，故此处统一取值。
    """
    for name in (*specific_keys, *GLOBAL_PROXY_KEYS):
        value = (os.getenv(name) or "").strip()
        if value:
            return value, name
    return "", ""


def is_retryable_error(err_text: str) -> bool:
    """
    判断错误是否可重试。
    可重试：网络/超时/代理类、滑块验证码类、签到流程类（页面加载不完整/跳转结果未知）。
    不可重试：密码错误、用户名不存在等业务错误（重试无意义，且会加剧风控）。
    """
    retry_keywords = [
        "timeout", "timed out", "超时",
        "proxy", "代理",
        # 收窄到具体网络异常名，避免页面正文里的 "connect"/"network" 等普通词误触发重试
        "connectionerror", "connection refused", "connection reset", "connection aborted",
        "newconnectionerror", "max retries", "sslerror", "read timed out",
        "connectionpool", "remotedisconnected", "incompleteread",
        "网络连接", "http 状态",
        # 滑块验证码类
        "验证码", "滑块", "captcha", "tncode",
        # 签到流程类
        "未到达验证页", "提交后仍在验证页", "签到结果未知", "找不到签到",
    ]
    lower = err_text.lower()
    return any(kw in lower for kw in retry_keywords)


def compact_error(err: BaseException, limit: int = 160) -> str:
    """异常只输出固定类型，避免请求 URL、响应和凭据进入日志。"""
    if requests is not None and isinstance(err, requests.exceptions.Timeout):
        return "网络超时"
    if requests is not None and isinstance(err, requests.exceptions.RequestException):
        return "网络连接或 HTTP 状态错误"
    return "处理失败（已隐藏异常详情）"


def parse_credentials(env_value: str):
    """一行一账号，首个 # 之后的密码保持原样，错误行也参与失败统计。"""
    accounts = []
    for raw in env_value.splitlines():
        if not raw.strip():
            continue
        username, separator, password = raw.partition("#")
        username = username.strip()
        accounts.append((username, password) if separator and username and password else None)
    return accounts


# ---------------- 会话 Cookie 缓存 ----------------
def cookie_cache_path(username: str) -> Path:
    """缓存文件路径：脚本同目录，文件名用用户名 hash（不含明文）。"""
    digest = hashlib.sha256((COOKIE_CACHE_SCOPE + "\0" + username).encode("utf-8")).hexdigest()[:24]
    return COOKIE_CACHE_DIR / f"cookie_{digest}.json"


def save_cookies_to_cache(session, username: str) -> bool:
    """把会话 Cookie 落盘，供后续任务/重试直通签到（跳过滑块）。"""
    try:
        cookies = [
            {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
            for c in session.cookies
        ]
        target = cookie_cache_path(username)
        fd, temporary = tempfile.mkstemp(prefix=".cookie_", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(cookies, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print(f"🍪 已保存会话 Cookie 缓存（{len(cookies)} 条）")
        return True
    except Exception as e:
        print(f"⚠️ 保存 Cookie 缓存失败: {e}")
        return False


def load_cookies_from_cache(username: str):
    """读取 Cookie 缓存；缺失或损坏返回 None。"""
    try:
        data = json.loads(cookie_cache_path(username).read_text(encoding="utf-8"))
        if (isinstance(data, list) and data and
                all(isinstance(c, dict) and isinstance(c.get("name"), str)
                    and isinstance(c.get("value"), str) for c in data)):
            return data
    except Exception:
        pass
    return None


def remove_cookie_cache(username: str) -> None:
    """删除失效缓存，避免反复复用坏 Cookie。"""
    try:
        cookie_cache_path(username).unlink(missing_ok=True)
    except Exception:
        pass


# ---------------- 浏览器指纹（复刻 /captcha/dz_fp.js） ----------------
def _fnv1a32(text: str) -> str:
    """FNV-1a 32 位哈希，返回 8 位十六进制（与 dz_fp.js 的 h32 一致）。"""
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return format(h, "08x")


def compute_fingerprint() -> str:
    """复刻 dz_fp.js：对 collect() 拼接串做四段 FNV-1a 组合指纹。"""
    raw = "||".join([
        UA, "zh-CN,zh", "1280x800x24", "-480", "8", "8", "Win32", "nc", "nc",
    ])
    a = _fnv1a32(raw)
    b = _fnv1a32(a + raw[:len(raw) >> 1])
    c = _fnv1a32(b + raw[len(raw) >> 1:])
    d = _fnv1a32(c + str(len(raw)))
    return a + b + c + d


# ---------------- tncode 滑块求解 ----------------
def solve_slider_candidates(img_bytes: bytes, debug: bool = False):
    """
    从 /captcha/tncode.php 的三联图求缺口左沿 x 的候选列表（按可能性降序）。

    三联图布局（各 240x150）：块0=带缺口背景，块1=拼图碎片，块2=完整背景。

    站点用"双缺口"反爬：块0 里有时会画两个同尺寸拼图形缺口，只有一个是真的。
    判别依据——拼图只做水平拖动，真缺口必然与拼图碎片同一行（y 对齐），故把
    y 与拼图最接近的候选排在最前。注意不能用形态学闭运算，否则相邻缺口会被
    合并成一个轮廓而无法区分。

    返回 x 候选列表（去重）；无候选返回 []。
    """
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        if debug:
            print("   [captcha] 验证码图解码失败")
        return []

    h = img.shape[0] // 3
    if h <= 0:
        return []
    panel_gap = cv2.cvtColor(img[:h], cv2.COLOR_BGR2GRAY)             # 带缺口背景
    panel_piece = cv2.cvtColor(img[h:2 * h], cv2.COLOR_BGR2GRAY)      # 拼图碎片
    panel_full = cv2.cvtColor(img[2 * h:3 * h], cv2.COLOR_BGR2GRAY)   # 完整背景

    ys, _ = np.where(panel_piece > 20)
    if len(ys) == 0:
        if debug:
            print("   [captcha] 未找到拼图碎片")
        return []
    piece_y0 = int(ys.min())
    piece_h = int(ys.max()) - piece_y0 + 1

    # 缺口 = 完整背景 与 带缺口背景 的差异区（不做形态学，避免相邻缺口合并）
    diff = cv2.absdiff(panel_full, panel_gap)
    _, binary = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for c in contours:
        x, y, w, hh = cv2.boundingRect(c)
        if not (25 <= w <= 90 and 20 <= hh <= 90):
            continue
        if not (0.5 <= w / max(1, hh) <= 2.0):
            continue
        candidates.append((x, y, w, hh))
    if not candidates:
        if debug:
            print("   [captcha] 差异图未找到合格缺口轮廓")
        return []

    # y 对齐的排前，其次尺寸接近拼图块
    candidates.sort(key=lambda c: (abs(c[1] - piece_y0), abs(c[3] - piece_h)))
    xs = []
    for x, _y, _w, _hh in candidates:
        if x not in xs:
            xs.append(x)
    if debug:
        print(f"   [captcha] 缺口候选 x={xs}（拼图 y={piece_y0}）")
    return xs


def solve_slider_from_sprite(img_bytes: bytes, debug: bool = False):
    """取最可能的缺口左沿 x（候选列表首个）；失败返回 None。"""
    xs = solve_slider_candidates(img_bytes, debug)
    return xs[0] if xs else None


def make_human_track(distance: int, start_x: int = 200, start_y: int = 300):
    """
    生成一条人类观感轨迹（余弦缓动 + 微抖动 + 时间递增）。

    服务端行为风控（error_track）会拒绝"点数过少/瞬移"的轨迹，故用约 40 个点、
    每点 12~20ms 的节奏。距离为负时退化为最小轨迹。
    """
    distance = max(1, int(distance))
    points = [{"x": start_x, "y": start_y, "t": 0}]
    t = 0
    steps = 40
    for i in range(1, steps + 1):
        ratio = i / steps
        eased = 0.5 * (1 - math.cos(math.pi * ratio))
        t += int(12 + 8 * math.sin(ratio * math.pi))
        points.append({
            "x": int(start_x + distance * eased),
            "y": start_y + (i % 3 - 1),
            "t": t,
        })
    return points


def _track_info(track_data: list) -> dict:
    """复刻 JS generateSecurePayload 的 trackInfo 统计（键顺序必须一致）。"""
    valid = len(track_data) >= 2
    total_time = track_data[-1]["t"]
    total_dist = 0.0
    speeds, directions = [], []
    for i in range(1, len(track_data)):
        dx = track_data[i]["x"] - track_data[i - 1]["x"]
        dy = track_data[i]["y"] - track_data[i - 1]["y"]
        dt = track_data[i]["t"] - track_data[i - 1]["t"]
        if dt > 0:
            dist = math.hypot(dx, dy)
            total_dist += dist
            speeds.append(dist / dt)
            directions.append(math.atan2(dy, dx))
    avg_speed = sum(speeds) / len(speeds) if speeds else 0
    speed_var = (sum((s - avg_speed) ** 2 for s in speeds) / len(speeds)) if speeds else 0
    dir_changes = sum(1 for i in range(1, len(directions))
                      if abs(directions[i] - directions[i - 1]) > math.pi / 4)
    return {
        "valid": valid,
        "points": len(track_data),
        "totalTime": total_time,
        "totalDist": total_dist,
        "avgSpeed": avg_speed,
        "maxSpeed": max(speeds) if speeds else 0,
        "minSpeed": min(speeds) if speeds else 0,
        "speedVar": speed_var,
        "dirChanges": dir_changes,
        "finalX": track_data[-1]["x"] - track_data[0]["x"],
    }


def build_tncode_payload(track_data: list, mark_offset: float, ts: int) -> str:
    """
    复刻 JS generateSecurePayload，返回 check.php 的 POST body。
    XOR(密钥) -> base64 -> FNV-1a 签名。
    """
    track_str = json.dumps(_track_info(track_data), separators=(",", ":"), ensure_ascii=False)
    normalized = f"{mark_offset:.2f}"
    xored = "".join(
        chr(ord(c) ^ ord(TNCODE_SECRET[i % len(TNCODE_SECRET)]))
        for i, c in enumerate(track_str)
    )
    encrypted = base64.b64encode(xored.encode("utf-8")).decode("ascii")
    combined = track_str + str(ts) + normalized + TNCODE_SECRET
    h = 0x811C9DC5
    for ch in combined:
        h ^= ord(ch)
        h = (h + (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24)) & 0xFFFFFFFF
    sign = format(h, "x")
    return (f"tn_r={normalized}&track={quote(encrypted, safe='')}"
            f"&ts={ts}&sign={sign}")


def pass_tncode(session, base_url: str, debug: bool, max_retry: int = 5):
    """
    取三联图 -> 解缺口候选 -> 逐个候选构造 payload 提交 check.php。
    每张图可提交多次（实测同一张图连续提交不会作废），因此把双缺口的候选都试一遍；
    全部失败才换新图。成功返回服务端 `<token>_ok` 字符串；失败返回 None。
    """
    for attempt in range(1, max_retry + 1):
        try:
            resp = session.get(
                base_url + CAPTCHA_IMG_PATH,
                params={"t": f"{random.random()}"},
                timeout=session._timeout,
            )
            candidates = solve_slider_candidates(resp.content, debug)
            if not candidates:
                if debug:
                    print(f"   [captcha] 第 {attempt}/{max_retry} 次未解出缺口，换图重试")
                continue

            for gap_x in candidates:
                payload = build_tncode_payload(
                    make_human_track(gap_x), gap_x, int(time.time() * 1000))
                r = session.post(
                    base_url + CAPTCHA_CHECK_PATH,
                    data=payload,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    timeout=session._timeout,
                )
                text = r.text.strip()
                if re.fullmatch(r"[A-Za-z0-9_-]+_ok", text):
                    if debug:
                        print(f"   [captcha] 第 {attempt} 张图、候选 x={gap_x} 通过")
                    return text
                if debug:
                    print("   [captcha] 服务端未返回有效通过标记")
            if debug:
                print(f"   [captcha] 第 {attempt}/{max_retry} 张图全部候选未过，换图重试")
        except Exception as e:
            if debug:
                print(f"   [captcha] 第 {attempt} 次异常: {compact_error(e)}")
    return None


# ---------------- HTML 表单解析 ----------------
class _FormParser(HTMLParser):
    """提取指定 id 的 <form>：action 与全部 input 的 name/value。"""

    def __init__(self, form_id: str):
        super().__init__()
        self.form_id = form_id
        self.depth = 0          # 进入目标 form 后 >0
        self.found = False
        self.action = ""
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            if not self.found and a.get("id") == self.form_id:
                self.found = True
                self.action = a.get("action", "")
                self.depth = 1
            elif self.found:
                self.depth += 1
        elif tag == "input" and self.depth > 0:
            name = a.get("name")
            if name:
                self.fields[name] = a.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form" and self.depth > 0:
            self.depth -= 1


def parse_form(html: str, form_id: str):
    """解析页面中指定 id 的 form，返回 (action, {name: value})；未找到返回 (None, {})。"""
    p = _FormParser(form_id)
    try:
        p.feed(html)
    except Exception:
        return None, {}
    if not p.found:
        return None, {}
    return p.action, p.fields


# ---------------- 登录 ----------------
def check_logged_in(session, base_url: str, debug: bool = False) -> bool:
    """GET forum.php，按 discuz_uid>0 / 退出链接判定登录态。"""
    try:
        r = session.get(base_url + "/forum.php", timeout=session._timeout)
        visible = parse_visible(r.text)
        identity = "".join(visible.identity).strip()
        if identity and not re.search(r"\d{7,}|@|[\r\n]", identity):
            print("官方账号名称 " + identity)
        m = re.search(r"discuz_uid\s*=\s*[\"'](\d+)[\"']", r.text)
        if m and int(m.group(1)) > 0:
            session.public_uid = m.group(1)
            print(f"官方账号公开 UID {session.public_uid}")
            return True
        if visible.logout and "退出" in " ".join(visible.text):
            return True
    except Exception as e:
        if debug:
            print(f"   [login] 登录态检查异常: {compact_error(e)}")
    return False


def login_with_requests(session, base_url: str, username: str, password: str,
                        debug: bool, max_captcha_retry: int):
    """浏览器登录页 -> 过 tncode -> 提交登录表单。返回 (success: bool, msg: str)。"""
    try:
        r = session.get(base_url + LOGIN_PAGE_PATH, timeout=session._timeout)
        fh = re.search(r'name="formhash" value="([0-9a-f]+)"', r.text)
        lh = re.search(r"loginhash=([A-Za-z0-9]+)", r.text)
        if not fh or not lh:
            return False, "登录页解析失败（未取到 formhash/loginhash）"
        formhash, loginhash = fh.group(1), lh.group(1)

        token = pass_tncode(session, base_url, debug, max_captcha_retry)
        if not token:
            return False, "验证码识别失败（滑块多次未通过）"

        action = (f"{base_url}/member.php?mod=logging&action=login"
                  f"&loginsubmit=yes&loginhash={loginhash}&inajax=1")
        data = {
            "formhash": formhash,
            "referer": base_url + "/./",
            "username": username,
            "password": password,
            "cookietime": "2592000",
            "clicaptcha-submit-info": token,
            "fingerprint": compute_fingerprint(),
            "loginfield": "username",
            "answer": "",
        }
        r = session.post(
            action, data=data,
            headers={"Referer": base_url + LOGIN_PAGE_PATH,
                     "X-Requested-With": "XMLHttpRequest"},
            timeout=session._timeout,
        )
        # 失败信息提取（Discuz 登录错误提示）
        for kw in ("密码错误", "密码不正确", "用户名不存在", "用户不存在", "验证码"):
            if kw in r.text:
                return False, f"登录失败: {kw}"
        if check_logged_in(session, base_url, debug):
            return True, "登录成功"
        return False, "登录失败（未检测到有效登录态）"
    except requests.exceptions.RequestException as e:
        return False, f"登录网络异常: {compact_error(e)}"
    except Exception as e:
        if debug:
            print("调试信息已脱敏，未输出异常堆栈")
        return False, f"登录异常: {compact_error(e)}"


# ---------------- 签到 ----------------
def fetch_sign_stats(session, base_url: str, debug: bool = False) -> dict:
    """读取签到页 countqian 统计（连续签到/签到等级/积分奖励/总天数）。失败返回 {}。"""
    wanted = {"连续签到": "天", "签到等级": "级", "积分奖励": "分", "总天数": "天"}
    try:
        r = session.get(base_url + SIGN_PAGE_PATH, timeout=session._timeout)
        block = re.search(r'<ul class="countqian[^"]*"[^>]*>(.*?)</ul>', r.text, re.S)
        if not block:
            return {}
        stats = {}
        for li in re.findall(r"<li>(.*?)</li>", block.group(1), re.S):
            h4 = re.search(r"<h4>(.*?)</h4>", li, re.S)
            if not h4:
                continue
            label = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", h4.group(1)))
            if label not in wanted:
                continue
            # 先定位含 hidnum 的整个 <input> 标签，再在标签内取 value，不依赖属性顺序/引号
            tag = re.search(r"<input[^>]*hidnum[^>]*>", li)
            if not tag:
                continue
            val = re.search(r"""value=["']([^"']*)["']""", tag.group(0))
            if val and re.fullmatch(r"\d+(?:\.\d+)?", val.group(1).strip()):
                stats[label] = f"{val.group(1).strip()} {wanted[label]}"
        return stats
    except Exception as e:
        if debug:
            print(f"   [stats] 统计读取失败: {compact_error(e)}")
        return {}


def sign_with_requests(session, base_url: str, debug: bool, max_captcha_retry: int) -> dict:
    """
    签到流程：签到页 -> 已签判定 -> 找 qiandao 链接 -> 验证页过 tncode -> 提交表单。
    返回 {"success": bool, "message"/"error": str}。
    """
    try:
        r = session.get(base_url + SIGN_PAGE_PATH, timeout=session._timeout)
        html = r.text

        # 已签到：span.btn.btnvisted（k_misign 的"已签到"标记）
        if already_signed(html):
            return {"success": True, "message": "今日已签到（btnvisted）"}

        # 找签到按钮链接（href 含 operation=qiandao，formhash 随机仅做存在性判断）
        m = re.search(r'href="([^"]*operation=qiandao[^"]*)"', html)
        if not m:
            if sign_success_message(html, already_only=True):
                return {"success": True, "message": "今日已签到（页面状态）"}
            return {"success": False, "error": "找不到签到按钮（可能页面结构变化或未登录）"}

        qiandao_url = urljoin(base_url + "/", m.group(1).replace("&amp;", "&"))
        r = session.get(qiandao_url, timeout=session._timeout)
        page = r.text

        # 签到验证页：解析 #v2_captcha_form 的 action 与全部字段
        action, fields = parse_form(page, "v2_captcha_form")
        if not action:
            # 无验证表单：可能已直接签到成功，或弹了错误页
            if already_signed(page):
                return {"success": True, "message": "今日已签到（btnvisted）"}
            for kw in ("签到成功", "签到完成", "您今日已签到"):
                if sign_success_message(page) == kw:
                    return {"success": True, "message": kw}
            return {"success": False, "error": "未到达验证页"}

        token = pass_tncode(session, base_url, debug, max_captcha_retry)
        if not token:
            return {"success": False, "error": "签到验证码识别失败（滑块多次未通过）"}

        fields["clicaptcha-submit-info"] = token
        submit_url = urljoin(qiandao_url, action)
        r = session.post(submit_url, data=fields,
                         headers={"Referer": qiandao_url,
                                  "Content-Type": "application/x-www-form-urlencoded"},
                         timeout=session._timeout)
        result = r.text

        # 失败守卫优先：仍在验证页 -> 判定失败
        # （不能靠"连续签到"等静态标签判成功：签到页本身就含该标签，会把失败误报为成功）
        if "v2_captcha_form" in result:
            return {"success": False, "error": "提交后仍在验证页（验证码可能未真正通过）"}

        # 权威成功信号：重新拉签到页，k_misign 在已签到时渲染 span.btnvisted
        try:
            verify_text = session.get(base_url + SIGN_PAGE_PATH, timeout=session._timeout).text
        except Exception:
            verify_text = result
        if already_signed(verify_text):
            return {"success": True, "message": "签到成功"}

        # 次级成功信号：仅真正的成功提示语（排除"连续签到"这类静态统计标签）
        for kw in ("签到成功", "签到完成", "您今日已签到", "今日已经签到", "今天已经签到"):
            if sign_success_message(verify_text) == kw:
                return {"success": True, "message": kw}

        err = re.search(r"(失败|错误|请重试)[^<\n]{0,40}", verify_text)
        if err:
            return {"success": False, "error": "签到失败（服务端错误提示）"}
        return {"success": False, "error": "签到结果未知（提交后未检测到已签到标记）"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"签到网络异常: {compact_error(e)}"}
    except Exception as e:
        if debug:
            print("调试信息已脱敏，未输出异常堆栈")
        return {"success": False, "error": f"签到异常: {compact_error(e)}"}


# ---------------- 安全请求与单账号编排 ----------------
class VisiblePage(HTMLParser):
    """只读取页面文本及可见的已签到标签，忽略脚本和样式。"""
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.text = []
        self.signed = False
        self.logout = False
        self.identity_depth = 0
        self.identity = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in ("script", "style"):
            self.hidden += 1
        if self.hidden:
            return
        if tag in ("span", "a", "button") and "btnvisted" in attributes.get("class", "").split():
            self.signed = True
        if tag == "a" and "action=logout" in attributes.get("href", ""):
            self.logout = True
        if tag == "strong" and "vwmy" in attributes.get("class", "").split():
            self.identity_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if tag == "strong" and self.identity_depth:
            self.identity_depth -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)
            if self.identity_depth:
                self.identity.append(data)


def parse_visible(html):
    page = VisiblePage()
    page.feed(html)
    return page


def sign_success_message(html, already_only=False):
    text = " ".join(parse_visible(html).text)
    if any(word in text for word in ("签到失败", "未签到成功", "未完成签到", "签到未完成", "签到错误")):
        return ""
    messages = ("您今日已签到", "今日已经签到", "今天已经签到")
    if not already_only:
        messages = ("签到成功", "签到完成") + messages
    return next((message for message in messages if message in text), "")


def already_signed(html):
    return parse_visible(html).signed


def build_session(base_url, proxy, timeout):
    origin = urlsplit(base_url)

    class SiteSession(requests.Session):
        def request(self, method, url, **kwargs):
            # 手动处理重定向，在下一跳发送任何 Cookie/密码/表单前检查源站。
            kwargs.pop("allow_redirects", None)
            kwargs.setdefault("timeout", timeout)
            for _ in range(6):
                destination = urlsplit(url)
                if (destination.scheme, destination.netloc) != (origin.scheme, origin.netloc):
                    raise ValueError("拒绝跨站请求")
                response = super().request(method, url, allow_redirects=False, **kwargs)
                response.raise_for_status()
                if response.status_code not in (301, 302, 303, 307, 308):
                    return response
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("重定向缺少目标")
                url = urljoin(response.url, location)
                kwargs.pop("params", None)
                if response.status_code == 303 or (response.status_code in (301, 302) and method.upper() == "POST"):
                    method = "GET"
                    kwargs.pop("data", None)
                    kwargs.pop("json", None)
            raise ValueError("重定向过多")

    session = SiteSession()
    session.trust_env = False
    session.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
                            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})
    session._timeout = timeout
    return session


def stage(number, title, operation):
    started = time.monotonic()
    print(f"阶段 {number} {title} 开始")
    try:
        return operation()
    finally:
        print(f"阶段 {number} {title} 结束，耗时 {time.monotonic() - started:.2f} 秒")


def run_one_account(username, password, base_url, proxy, timeout, debug, captcha_retry, cache):
    with build_session(base_url, proxy, timeout) as session:
        def authenticate():
            if cache:
                cached = load_cookies_from_cache(username)
                if cached:
                    try:
                        for cookie in cached:
                            session.cookies.set(cookie["name"], cookie["value"],
                                                domain=cookie.get("domain") or "", path=cookie.get("path") or "/")
                        if check_logged_in(session, base_url, debug):
                            print("☑️ 有效 Cookie 缓存，跳过密码登录")
                            return True, "会话复用成功"
                    except Exception:
                        print("⚠️ 缓存无法使用，重新登录")
                    session.cookies.clear()
                    remove_cookie_cache(username)
            ok, message = login_with_requests(session, base_url, username, password, debug, captcha_retry)
            if ok and cache:
                save_cookies_to_cache(session, username)
            return ok, message

        ok, message = stage(1, "验证会话与登录", authenticate)
        print(("✅ " if ok else "❌ ") + message)
        if not ok:
            return {"success": False, "error": message, "tasks": 3, "failed": 1, "skipped": 2}
        result = stage(2, "每日签到与结果核验",
                       lambda: sign_with_requests(session, base_url, debug, captcha_retry))
        print(("✅ " if result["success"] else "❌ ") + result.get("message", result.get("error", "未知结果")))
        result.update(tasks=3, passed=1, failed=0 if result["success"] else 1, skipped=1)
        if result["success"]:
            result["already"] = int("已签到" in result.get("message", ""))
            result["passed"] = 2 - result["already"]
            stats = stage(3, "读取签到统计", lambda: fetch_sign_stats(session, base_url, debug))
            result["stats"] = stats
            result["tasks"] = 3
            if stats:
                result["passed"] += 1
                result["skipped"] = 0
                for name, value in stats.items():
                    print(f"{name} {value}")
            else:
                print("⚠️ 统计暂不可读，签到业务结果已独立核验")
        return result


# ---------------- 青龙通知 ----------------
def notify_selected(status):
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in ("0", "false", "no", "off"):
        return False
    if switch in ("1", "true", "yes", "on"):
        return True
    selection = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selection is not None:
        selectors = re.split(r"[,;\s]+", selection.strip())
        identities = ("91d3322eb735e2d2", Path(__file__).name,
                      "laowangfip_checkin.py", "laowangfip_checkin/laowangfip_checkin.py")
        return any(fnmatch.fnmatch(identity, selector) for selector in selectors if selector for identity in identities)
    return env_bool("LWFIP_NOTIFY", True) and (
        not env_bool("LWFIP_NOTIFY_ONLY_FAIL", False) or status not in ("success", "dry-run"))


def send_summary(summary, dry):
    if not notify_selected(summary["status"]):
        return "已关闭"
    body = (f"状态 {summary['status']}，账号总数 {summary['accounts']}，"
            f"成功 {summary['success']}，失败 {summary['failed']}，预演 {summary['dryRunAccounts']}")
    if dry:
        print("⏭️ 离线预演通知，" + body)
        return "离线预演，未发送"
    # 隔离执行通知，吞掉插件输出与异常，避免插件泄漏配置，限制最长耗时。
    python_code = '''import importlib.util, json, sys
p = json.loads(sys.stdin.read())
if p['path']:
    sys.path.insert(0, p['directory'])
    spec = importlib.util.spec_from_file_location('_ql_notify', p['path'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(p['title'], p['body'])
'''
    directories = [os.getenv("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]
    candidates = [("python", "", "")]
    for directory in directories:
        if directory:
            for language, filename in (("python", "notify.py"), ("javascript", "sendNotify.js")):
                path = Path(directory) / filename
                if path.is_file():
                    candidates.append((language, str(path.resolve()), str(path.parent.resolve())))
    for language, path, directory in candidates:
        payload = json.dumps(dict(title="老王FIP签到", body=body, path=path, directory=directory))
        command = [sys.executable, "-c", python_code]
        if language == "javascript":
            command = ["node", "-e", "let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',async()=>{try{const p=JSON.parse(s);await require(p.path).sendNotify(p.title,p.body);}catch(e){process.exitCode=1;}});"]
        try:
            completed = subprocess.run(command, input=payload, text=True, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=30, check=False)
            if completed.returncode == 0:
                return "已发送"
        except (OSError, subprocess.TimeoutExpired):
            pass
    print("⚠️ 青龙通知不可用或发送失败，保留业务退出码")
    return "不可用或失败"


def positive_integer(name, default, minimum=1):
    try:
        value = int(os.getenv(name) or default)
    except ValueError:
        raise ValueError(name + " 必须为整数") from None
    if value < minimum:
        raise ValueError(name + " 超出有效范围")
    return value


def main():
    global requests, cv2, np, COOKIE_CACHE_SCOPE
    started = time.monotonic()
    dry = env_bool("LWFIP_DRY_RUN", False)
    accounts = parse_credentials(os.getenv("LWFIP_ACCOUNTS", ""))
    print("=" * 60)
    print("老王FIP签到")
    print(f"开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"运行模式 {'离线预演' if dry else '实跑'}，账号数 {len(accounts)}")
    summary = dict(status="configuration-error", accounts=len(accounts), success=0, failed=0,
                   dryRunAccounts=0, tasks=0, passed=0, already=0, skipped=0, taskFailures=0)
    exit_code = 1
    print("阶段 0 配置与依赖检查开始")
    try:
        if not accounts:
            raise ValueError("请配置 LWFIP_ACCOUNTS，每行 用户名#密码")
        base_url = (os.getenv("LWFIP_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise ValueError("LWFIP_BASE_URL 必须为不含认证、路径、查询和片段的 HTTPS 站点地址")
        COOKIE_CACHE_SCOPE = base_url
        timeout = positive_integer("LWFIP_TIMEOUT", 30)
        captcha_retry = positive_integer("LWFIP_MAX_CAPTCHA_RETRY", 5)
        max_retry = positive_integer("LWFIP_MAX_RETRY", 5)
        interval = positive_integer("LWFIP_RETRY_INTERVAL", 60, 0)
        proxy, proxy_source = resolve_proxy("LWFIP_PROXY")
        if env_bool("LWFIP_PROXY_REQUIRED", False) and not proxy:
            raise ValueError("代理必需但未配置 LWFIP_PROXY 或全局代理")
        print(f"代理 {'已配置，来源 ' + proxy_source if proxy else '未配置，直连'}，超时 {timeout} 秒")
        if not dry:
            try:
                import requests as requests_module
                import cv2 as cv2_module
                import numpy as numpy_module
                requests, cv2, np = requests_module, cv2_module, numpy_module
            except ImportError:
                raise ValueError("缺少依赖，请在青龙 Python 依赖中安装 requests、opencv-python-headless、numpy") from None
        print(f"阶段 0 配置与依赖检查结束，耗时 {time.monotonic() - started:.2f} 秒")
        for index, account in enumerate(accounts, 1):
            account_start = time.monotonic()
            print(f"账号 {index}/{len(accounts)} 开始")
            if account is None:
                result = dict(success=False, error="账号格式错误，必须为 用户名#密码", tasks=3, failed=1, skipped=2)
            elif dry:
                stage(1, "检查账号格式", lambda: print("✅ 账号格式有效，未输出凭据"))
                stage(2, "预演登录、滑块及签到", lambda: print("⏭️ 不发送请求，不读写 Cookie"))
                stage(3, "预演统计读取", lambda: print("⏭️ 不读取远端统计"))
                summary["dryRunAccounts"] += 1
                result = dict(success=True, tasks=3, passed=1, skipped=2)
            else:
                for attempt in range(1, max_retry + 1):
                    if attempt > 1:
                        print(f"账号重试 {attempt}/{max_retry}，等待 {interval} 秒")
                        time.sleep(interval)
                    try:
                        result = run_one_account(*account, base_url, proxy, timeout,
                                                 env_bool("LWFIP_DEBUG", False), captcha_retry,
                                                 env_bool("LWFIP_COOKIE_CACHE", False))
                    except Exception as error:
                        result = dict(success=False, error=compact_error(error), tasks=1, failed=1)
                    if result["success"] or not is_retryable_error(result.get("error", "")):
                        break
            ok = result["success"]
            if not ok:
                summary["failed"] += 1
                print("❌ " + result.get("error", "账号失败"))
            elif not dry:
                summary["success"] += 1
            for source, target in (("tasks", "tasks"), ("passed", "passed"), ("already", "already"),
                                   ("skipped", "skipped"), ("failed", "taskFailures")):
                summary[target] += result.get(source, 0)
            print(f"账号 {index} 统计，总任务 {result.get('tasks', 0)}，成功 {result.get('passed', 0)}，"
                  f"已完成 {result.get('already', 0)}，跳过 {result.get('skipped', 0)}，"
                  f"失败 {result.get('failed', 0)}，耗时 {time.monotonic() - account_start:.2f} 秒")
            if index < len(accounts) and not dry:
                time.sleep(random.uniform(3, 8))
        exit_code = int(summary["failed"] > 0)
        summary["status"] = ("partial-failure" if summary["failed"] and summary["success"] else
                             "failure" if exit_code else "dry-run" if dry else "success")
    except ValueError as error:
        print(f"阶段 0 配置与依赖检查失败，耗时 {time.monotonic() - started:.2f} 秒")
        print("❌ 配置错误，" + str(error))
        summary["failed"] = len(accounts)
    except KeyboardInterrupt:
        print("❌ 任务中断")
        summary["status"] = "failure"
        summary["failed"] = max(1, len(accounts) - summary["success"])
        exit_code = 2
    except Exception as error:
        print("❌ " + compact_error(error))
        summary["status"] = "failure"
        summary["failed"] = max(1, len(accounts) - summary["success"])
    try:
        summary["notification"] = send_summary(summary, dry)
    except Exception:
        print("⚠️ 通知失败，保留业务退出码")
        summary["notification"] = "失败"
    summary["elapsedSeconds"] = round(time.monotonic() - started, 3)
    summary["finishedAt"] = datetime.now().isoformat(timespec="seconds")
    summary["exitCode"] = exit_code
    print("-" * 60)
    print(f"账号结果，总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}，预演 {summary['dryRunAccounts']}")
    print(f"子任务统计，总任务 {summary['tasks']}，成功 {summary['passed']}，已完成 {summary['already']}，跳过 {summary['skipped']}，失败 {summary['taskFailures']}")
    print(f"总耗时 {summary['elapsedSeconds']} 秒，通知状态 {summary['notification']}")
    print(f"完成时间 {summary['finishedAt']}，最终状态 {summary['status']}")
    builtins.print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
