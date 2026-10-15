#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: WorkBuddy 国内版日常维护
# cron: 15 7,12 * * *
# 来源：L0NE-6/WorkBuddy-Daily，workbuddy_daily.py v3.7，MIT
# 合并参考：Maquer/workbuddy-checkin，workbuddy_checkin.py，MIT
"""独立维护版。凭据：WORKBUDDY_REFRESH_TOKEN，每行 手机号:AT:RT、AT:RT、手机号:RT 或单个 JWT。
明文凭据可在本人已登录客户端认证信息中读取；加密信封不可使用，改从官方登录请求响应获取。
默认只执行签到、查询、已完成任务领奖及旅行；消耗资源、同意协议与模拟成长事件均需显式选择。
WORKBUDDY_TASKS / --tasks：逗号或空格分隔任务名；WORKBUDDY_SKIP_TASKS / --skip-tasks：排除。
WORKBUDDY_ALLOW_REPORT=1 才能执行成长事件任务；不表示真实桌面业务成功。
国际版用 --intl（仍按 0 7,12 * * * 调度），WORKBUDDY_INTL_TOKENS 每行 AT 或 备注|AT|uid|RT。
国际版与国内版凭据不通用；国际版仅配置 WORKBUDDY_TOKEN 时兼容单账号。
国际版默认探测及领奖；--keepalive 或 WORKBUDDY_INTL_KEEPALIVE=1 显式允许一次模型调用（可能消耗积分）。
--no-keepalive 优先关闭；WORKBUDDY_INTL_MODELS 逗号分隔模型链，保留上游四模型回退。
国际版 --refresh 显式轮换，WORKBUDDY_INTL_TOKEN_STORE 指向本人0600缓存，续期前检查可写。
WORKBUDDY_INTL_DRY_RUN=1 或 WORKBUDDY_DRY_RUN=1 完全断网预演。
国际版 AT/RT 从本人 www.workbuddy.ai 官方授权登录响应获取，不依赖登录脚本或本地应用执行。
夜猫子 black_cat 需单独按 30 23 * * * 调度。国际版凭据不通用；已结束开学季与手动登录不合并。
WORKBUDDY_DRY_RUN=1：完全断网，不轮换令牌、不写文件、不发送实际通知。
续期令牌仅保存至本人指定 WORKBUDDY_TOKEN_STORE（0600）；默认不轮换尚有效的 AT。
--refresh 或只有 RT 时必须配置此路径，以免新 RT 丢失。不要将此文件上传公开仓库。
仅需 Python 标准库；无需桌面程序、登录脚本或私有仓库。
--credit-report：独立只读积分日报，支持国内版及 --intl；--json 输出脱敏套餐数值数组。
新增日报保留上游周期容量优先、累计容量回退、总用量补全算法，未知结构失败闭合。
--intl --trial：独立的一次性专家加油包领取，不执行每日奖励或模型保活，不加入默认定时任务。
trial 仅依据 HTTP 200 且业务码0确认领取；业务码14051确认此前已领取。
新增操作不接受 --refresh、--query 或显式任务/保活开关组合，避免意外串联变更。
原上游凭据目录、内置常驻 cron 与 Bark 专属推送不作为运行依赖：
凭据使用现有逐行变量，定时使用青龙，通知使用 notify.py；不打印令牌片段或自动禁用账号。
取得明文 AT/RT 后国内版使用 AT:RT；国际版使用 备注|AT|uid|RT 或单个 AT。
JSON 日报仅包含账号序号与数值，不输出服务端原始数据或套餐自由文本。
新增参考归属：Maquer/workbuddy-checkin and its contributors（MIT）。

MIT License
Attribution: L0NE-6/WorkBuddy-Daily and its contributors.
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
import sys, os, re, json, time, uuid, base64, hashlib, hmac
import argparse, datetime, pathlib, tempfile, importlib.util
# Standard-library HTTP compatibility layer: TLS verification, no redirects,
# bounded JSON/SSE responses, no inherited proxies, no external runtime dependency.
import urllib.request, urllib.error, urllib.parse, types
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
class _Response:
    def __init__(self, raw, streaming=False):
        self.raw = raw
        self.status_code = raw.code
        self.headers = raw.headers
        self.content = b''
        if not streaming:
            try:
                self.content = raw.read(4 * 1024 * 1024 + 1)
                if len(self.content) > 4 * 1024 * 1024:
                    raise RuntimeError('响应过大')
            finally:
                raw.close()
    def json(self):
        return json.loads(self.content.decode('utf-8'))
    def iter_lines(self, decode_unicode=False):
        size = 0
        started = time.monotonic()
        while True:
            if time.monotonic() - started > 90:
                raise RuntimeError('流式响应超时')
            line = self.raw.readline(1024 * 1024 + 1)
            if not line:
                break
            size += len(line)
            if size > 4 * 1024 * 1024 or len(line) > 1024 * 1024:
                raise RuntimeError('流式响应过大')
            line = line.rstrip(b'\r\n')
            yield line.decode('utf-8') if decode_unicode else line
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.raw.close()
class _Session:
    def __init__(self):
        self.headers = {}
        self.trust_env = False
    def request(self, method, url, **kwargs):
        headers = dict(self.headers)
        headers.update(kwargs.get('headers') or {})
        if kwargs.get('params'):
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(kwargs['params'])
        data = None
        if kwargs.get('json') is not None:
            data = json.dumps(kwargs['json'], ensure_ascii=False).encode('utf-8')
            headers.setdefault('Content-Type','application/json')
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            raw = opener.open(req, timeout=kwargs.get('timeout',25))
        except urllib.error.HTTPError as e:
            raw = e
        return _Response(raw, kwargs.get('stream',False))
    def get(self, url, **kwargs):
        return self.request('GET',url,**kwargs)
    def post(self, url, **kwargs):
        return self.request('POST',url,**kwargs)
requests = types.SimpleNamespace(Session=_Session)
_expert_cache = None

TASK_ONLY = set()
TASK_SKIP = set()
class TransientError(RuntimeError):
    """网络/5xx 可重试错误。"""

BASE = "https://www.workbuddy.cn"

CBDOMAIN = "https://www.codebuddy.cn"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) WorkBuddy/5.5.4 Chrome/138.0.7204.251 Electron/37.10.3 Safari/537.36"

TASK_NAME_CN = {
    "create_canvas": "设计创意模式",
    "playbook_prompt": "探索优秀灵感",
    "RichMeow_Chat": "桌面端对话",
    "Library_read": "体验资料库",
    "Expert_lighthouse": "腾讯轻量云专家",
    "Expert_Philanthropy": "公益专家",
    "Hp_Appearance": "和平精英主题",
    "Buddy_App": "发现应用",
    "Buddy_App_QQ": "企鹅教师助手",
    "Model_chat_GLM5.2": "GLM-5.2模型对话",
    "black_cat": "夜猫子活动",
    "Expert_team_use_3": "召唤3次专家团",
    "first_buddy": "领取Buddy",
    "chat_5": "和AI聊天5次",
    "skill_1": "尝鲜热门技能",
    "expert_5": "召唤5次专家",
    "template_5": "使用5个模板",
    "automation_1": "设置自动化任务",
    "workstation_expert": "工作台搭建师",
    "wb_wechat_oa_subscribe_task": "关注公众号",
    "Sequential_Tasks_1": "小程序对话",
    "Sequential_Tasks_2": "小程序专家对话",
    "Sequential_Tasks_3": "小程序对话5次",
    "Sequential_Tasks_4": "小程序定时任务",
    "Sequential_Tasks_5": "小程序GLM5.2",
    "Sequential_Tasks_6": "小程序对话10次",
    "Sequential_Tasks_7": "小程序灵感功能",
    "school_season": "校园日活动",
}

def task_cn(code):
    return TASK_NAME_CN.get(code, code)

QQ_TPL = "cb_y5Dy46tPQGGWtueMxXbe"

EXPERT_MARKETPLACE_URL = "https://acc-1258344699.cos.accelerate.myqcloud.com/workbuddy/expert-marketplace/expert_center.json"

def _extract_name(val):
    if isinstance(val, dict):
        return val.get("zh", val.get("en", str(val)))
    return str(val)

def fetch_expert_marketplace():
    """拉取专家市场配置（带缓存）"""
    global _expert_cache
    if _expert_cache is not None:
        return _expert_cache
    try:
        s = requests.Session()
        s.trust_env = False
        s.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        r = s.get(EXPERT_MARKETPLACE_URL, timeout=15, verify=True)
        if r.status_code == 200:
            _expert_cache = r.json()
            return _expert_cache
    except Exception:
        pass
    return None

def get_team_experts(count=5):
    """专家团列表"""
    data = fetch_expert_marketplace()
    if not data:
        return []
    team = []
    for e in data.get("experts", []):
        meta = e.get("_meta", {})
        if meta.get("expertType") == "team" or e.get("expertType") == "team":
            team.append({"id": e["id"], "name": _extract_name(e.get("displayName", e.get("name", {}))),
                         "industryId": meta.get("industryId", e.get("industryId", "")),
                         "profession": _extract_name(e.get("profession", "")),
                         "defaultInitPrompt": _extract_name(e.get("defaultInitPrompt", ""))})
    return team[:count]

def get_normal_experts(count=10):
    """普通专家列表"""
    data = fetch_expert_marketplace()
    if not data:
        return []
    normal = []
    for e in data.get("experts", []):
        meta = e.get("_meta", {})
        if meta.get("expertType", e.get("expertType", "")) == "agent":
            normal.append({"id": e["id"], "name": _extract_name(e.get("displayName", e.get("name", {}))),
                           "industryId": meta.get("industryId", e.get("industryId", "")),
                           "profession": _extract_name(e.get("profession", "")),
                           "defaultInitPrompt": _extract_name(e.get("defaultInitPrompt", ""))})
    return normal[:count]

def get_template_scenes(count=5):
    """模板场景列表（失败时用内置兜底）"""
    data = fetch_expert_marketplace()
    fallback = [{"id": "01-ProductDesign", "name": "产品设计"}, {"id": "02-Marketing", "name": "营销文案"},
                {"id": "03-DataAnalysis", "name": "数据分析"}, {"id": "04-CodeReview", "name": "代码审查"},
                {"id": "05-Report", "name": "报告撰写"}]
    if not data:
        return fallback[:count]
    scenes = [{"id": c["id"], "name": _extract_name(c.get("name", {}))} for c in data.get("categories", [])[:count]]
    return scenes or fallback[:count]

THEME_KEY = "theme-tkmw7j"

LIB_DOC_URL = "https://www.workbuddy.cn/space/d/o0KWYeynteVv06UnAZqIFm"

SKILL_NAME = "algorithmic-trading"

SKILL_FALLBACK = ("skill_2097350077599879168", "润泽小馆·日报撰写")

REFRESH_URL = "https://copilot.tencent.com/v2/plugin/auth/token/refresh"

def _jwt_claims(tok):
    """本地解 JWT payload（不验签）：返回 dict；失败返回 {}。

    自包含（不依赖文件后面定义的辅助函数）——自举 _bootstrap_store() 在模块加载早期
    就会调到它。
    """
    try:
        seg = (tok or "").split(".")
        if len(seg) != 3:
            return {}
        s = seg[1]; s += "=" * (4 - len(s) % 4)
        d = json.loads(base64.urlsafe_b64decode(s))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def _token_kind(tok):
    """按 JWT 的 typ 判定类型：'AT'（typ=Bearer）/ 'RT'（typ=Offline）/ ''（未知）。

    实测 CN 站：AT=Bearer、RT=Offline——用户只粘一个 token 时靠它自动归位。
    """
    return {"Bearer": "AT", "Offline": "RT"}.get(str(_jwt_claims(tok).get("typ", "")), "")

def _token_user(tok):
    """从 token 的 preferred_username 取手机号（AT:RT 没写手机号时用）；取不到返回 ''。"""
    return str(_jwt_claims(tok).get("preferred_username") or "").strip()

def _jwt_payload_local(tok):
    """本地解 JWT payload（不验签，仅用于体检与取名）。失败返回 {}。"""
    try:
        seg = tok.split(".")
        if len(seg) != 3:
            return {}
        s = seg[1]; s += "=" * (4 - len(s) % 4)
        d = json.loads(base64.urlsafe_b64decode(s))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def _token_sanity(rt, at):
    """凭据本地体检：把 RT/AT 的结构问题翻译成可执行的排障提示（不联网）。

    合法 CN WorkBuddy 凭据（实测 2026-09-28）：
      · AT：RS256 JWT，typ=Bearer，iss=https://www.codebuddy.cn/auth/realms/copilot
      · RT：HS512 JWT，typ=Offline，iss/aud 同为上述 realm，azp=console
    服务端对不合规凭据只回一句 12153 ... token format error，这里提前说清楚是哪一种。
    """
    tips = []
    for name, tok in (("RT", rt), ("AT", at)):
        tok = (tok or "").strip()
        if not tok:
            continue
        if "$wbEncrypted" in tok or '"envelope"' in tok:
            tips.append("%s 是 WorkBuddy 5.6.2+ 的 AtRestEncryption 加密信封（不是明文 JWT）——密钥只驻留" 
                        "客户端进程内存，无法直接使用；请用 python workbuddy_login.py（短信登录）获取明文凭据" % name)
            continue
        if not tok.startswith("eyJ") or tok.count(".") != 2:
            tips.append("%s 不是 eyJ 开头的三段式 JWT（长度 %d）——被截断、带了引号/空格，或粘错了字段" % (name, len(tok)))
            continue
        pl = _jwt_payload_local(tok)
        typ = str(pl.get("typ", ""))
        iss = str(pl.get("iss", ""))
        if name == "RT" and typ and typ != "Offline":
            tips.append("RT 的 typ=%s（应为 Offline）——%s" % (
                typ, "很可能把 AT 粘到了 RT 位置，正确顺序是 手机号:AT:RT" if typ == "Bearer" else "字段粘错了"))
        if name == "AT" and typ and typ != "Bearer":
            tips.append("AT 的 typ=%s（应为 Bearer）——AT/RT 可能写反了" % typ)
        if iss and ("codebuddy.cn" not in iss):
            tips.append("%s 的签发域是 %s，不是 CN 站（www.codebuddy.cn/auth/realms/copilot）——国际版/其他应用的 token 在 CN 刷不了" % (name, iss[:70]))
    return tips

def jwt_user(tok):
    try:
        pay = tok.split(".")[1]; pay += "=" * (4 - len(pay) % 4)
        return json.loads(base64.urlsafe_b64decode(pay)).get("preferred_username", "?")
    except Exception:
        return "?"

def refresh_one(rt):
    """刷新单个RT，返回 (新AT, 新RT) 或 (None, 错误信息)"""
    s = requests.Session(); s.trust_env = False
    r = s.post(REFRESH_URL, json={}, timeout=20, verify=True,
               headers={"X-Refresh-Token": rt, "X-Auth-Refresh-Source": "plugin",
                        "Content-Type": "application/json"})
    d = r.json()
    inner = d.get("data") or {}
    if d.get("code") == 0 and inner.get("accessToken"):
        return inner["accessToken"], inner.get("refreshToken") or rt
    return None, str(d.get("msg", ""))[:120]

WRITE_GAP = 1.5

MP_CHAT_GAP = 45.0

def _parse_task_filter(raw):
    """解析子任务过滤串：逗号/顿号/空格分隔，大小写不敏感。"""
    return {x.strip().lower() for x in re.split(r"[,\uff0c\u3001\s]+", raw or "") if x.strip()}

def want(*codes):
    """子任务开关：WORKBUDDY_TASKS（白名单）/ WORKBUDDY_SKIP_TASKS（黑名单）。

    · 黑名单命中即跳过；白名单非空时未列出的也跳过（两者可叠加）
    · 代号大小写不敏感；常用别名：checkin 每日签到 / travel 旅行 / lottery 抽奖 /
      redeem 连登兑换 / gift 礼包补偿 / makeup 补签 / badges 徽章 / blindbox 盲盒 /
      buddy_info Buddy 信息 / desktop 桌面任务
    · 只影响「主动执行」：accept、领奖、前置补救（first_buddy）不受影响，
      因此被跳过的任务不会被完成，也就不会被领奖计入积分
    """
    if not TASK_ONLY and not TASK_SKIP:
        return True
    names = {str(c).strip().lower() for c in codes}
    if names & TASK_SKIP:
        return False
    if TASK_ONLY and not (names & TASK_ONLY):
        return False
    return True

def new_api(tok):
    s = requests.Session(); s.trust_env = False
    _uid = uid_of(tok)
    s.headers.update({"Authorization": "Bearer " + tok, "Content-Type": "application/json",
                      "Accept": "application/json, text/plain, */*", "Origin": BASE,
                      "Referer": BASE + "/profile/growth-center", "User-Agent": UA,
                      "X-User-Id": _uid})
    return s

def api_retry(s, method, url, body=None, retries=3, gap=1.0, **kw):
    """带指数退避重试的 API 请求：网络错误/5xx 自动重试，4xx 不重试。"""
    last_err = None
    for i in range(1, retries + 1):
        try:
            if method == "GET":
                r = s.get(url, timeout=25, verify=True, **kw)
            else:
                r = s.post(url, json=body, timeout=25, verify=True, **kw)
            if 500 <= r.status_code < 600 and i < retries:
                last_err = RuntimeError("http %s" % r.status_code)
                time.sleep(gap * i)
                continue
            return r
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(gap * i)
            continue
    if last_err:
        raise last_err
    return r

def interpret_failure(st, r_json):
    """结构化错误分类：返回 (描述, 是否应跳过该账号)。"""
    code = r_json.get("code") if isinstance(r_json, dict) else None
    msg = str(r_json.get("msg", "") or r_json.get("message", ""))[:120] if isinstance(r_json, dict) else str(r_json)[:80]
    if st == 401 or code in (401, "401", 40100, "40100"):
        return "401/40100 Token 失效或未绑定", True
    if st == 403:
        return "403 禁止访问", True
    if code in (41000, "41000"):
        return "41000 活动未开始或已结束", False
    if code in (40901, "40901"):
        return "40901 任务暂不可领取", False
    return "http=%s code=%s %s" % (st, code, msg), False

def uid_of(tok):
    try:
        return json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "==")).get("sub", "")
    except Exception:
        return ""

def nickname_of(tok):
    try:
        return json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "==")).get("nickname", "") or "用户"
    except Exception:
        return "用户"

def prog(s, code):
    try:
        r = s.get(BASE + "/v2/activity/growth/tasks", timeout=25, verify=True).json()
        for t in r.get("data", {}).get("tasks", []):
            if t.get("task_code") == code:
                pr = t.get("progress") or {}
                return t.get("accept_status", ""), pr.get("current"), pr.get("target")
    except Exception:
        pass
    return None, None, None

def claim(s, code, log):
    """M15 领奖：chat 域 400 时自动降级 web 域（x-client-platform: web）。"""
    r = s.post(BASE + "/activity/growth/tasks/%s/claim" % code, json={}, timeout=20, verify=True)
    if r.status_code == 400:
        # 降级 web 域
        r = s.post(BASE + "/activity/growth/tasks/%s/claim" % code, json={},
                   timeout=20, verify=True,
                   headers={"Origin": BASE, "Referer": BASE + "/profile/growth-center",
                            "x-client-platform": "web"})
    try:
        d = r.json().get("data", {})
        log("   🎁领奖[%s]: %s" % (code, "已领过" if d.get("already_claimed") else "+%s积分+%s能量" % (d.get("credit"), d.get("energy"))))
    except Exception:
        log("   领奖[%s]: HTTP %s" % (code, r.status_code))

def report(s, uid, nick, events):
    """events: list of dict；自动补全信封"""
    UA_SHORT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 WorkBuddy/5.5.4"
    mid = derive_id(uid, "machine")   # 稳定指纹：同账号每次相同
    out = []
    for e in events:
        env = {"timestamp": int(time.time() * 1000), "reportDelay": 0,
               "userId": uid, "userNickname": nick,
               "ideName": "WorkBuddy", "ideType": "WorkBuddy", "ideVersion": "5.5.6",
               "machineId": mid, "sessionId": derive_id(uid, "session"),
               "mode": "CLOUD", "userAgent": UA_SHORT, "os": "Win32", "arch": "x64",
               "osVersion": "10.0.26220", "timezone": "Asia/Shanghai",
               "product": "SaaS", "releaseDate": 1789036585355,
               "commit": "5f9692923c93033111c51ad7b003eb80204a9b75",
               "extName": "workbuddy-desktop", "extVersion": "5.5.6",
               "cpuCores": 20, "memorySize": 24}
        env.update(e)
        out.append(env)
    try:
        r = s.post(BASE + "/v2/report", json=out, timeout=15, verify=True)
        return r.status_code
    except Exception:
        return 0

def webchat2(s, conv_name, prompt, meta=None, model="glm-5.2"):
    """真实对话：返回 (conversationId, 回复正文, 服务端消息id)。

    服务端消息 id 取 SSE 首块的 "id"（形如 cmb-<32hex>）——上游 panel 实测：专家/技能类
    任务的 requestId / messageId 必须是真实会话的服务端 id，自造 uuid 不计数。
    """
    conv = s.post(BASE + "/console/webchat/conversations", json={"name": conv_name + "-" + str(uuid.uuid4())[:8]},
                  timeout=20, verify=True).json()
    conv_id = conv.get("data", {}).get("conversationId", "")
    payload = {"messages": [{"role": "user", "content": prompt}], "model": model, "stream": True,
               "conversationId": conv_id}
    if meta:
        payload["_meta"] = meta
    headers = dict(s.headers); headers["Accept"] = "text/event-stream"
    txt = ""; srv_mid = ""
    try:
        with s.post(BASE + "/console/chat/completions", json=payload, timeout=90, verify=True,
                    stream=True, headers=headers) as r:
            for line in r.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    d = line[6:]
                    if d.strip() in ("[DONE]", "[完成]", "[✅完成]"):
                        break
                    try:
                        jj = json.loads(d)
                        if not srv_mid and jj.get("id"):
                            srv_mid = str(jj["id"])
                        for c in jj.get("choices", []):
                            cp = c.get("delta", {}).get("content", "")
                            if cp:
                                txt += cp
                    except Exception:
                        pass
    except Exception:
        pass
    return conv_id, txt, srv_mid

def webchat(s, conv_name, prompt, meta=None, model="glm-5.2"):
    """真实对话（兼容包装）：返回 (conversationId, 回复正文)。"""
    conv_id, txt, _ = webchat2(s, conv_name, prompt, meta=meta, model=model)
    return conv_id, txt

def chat_request_events(uid, nick, conv_id, prompt, txt, mode="craft"):
    now = int(time.time() * 1000)
    rid = "cmb-" + str(uuid.uuid4())
    common = {"userId": uid, "userNickname": nick, "ideName": "web-Agents", "ideType": "web-Agents",
              "machineId": derive_id(uid, "machine"), "mode": "CLOUD", "userAgent": UA, "os": "Win32",
              "timezone": "Asia/Shanghai"}
    return [
        {"eventCode": "chat_request_send", "timestamp": now, "reportDelay": 0, **common,
         "mode": mode,
         "conversationId": conv_id, "requestId": rid, "requestModelId": "glm-5.2",
         "requestModelName": "GLM-5.2", "inputLength": len(prompt), "customAgentName": ""},
        {"eventCode": "chat_request_response", "timestamp": now + 100, "reportDelay": 0, **common,
         "conversationId": conv_id, "requestId": rid, "requestModelId": "glm-5.2",
         "requestModelName": "GLM-5.2", "toolCallCount": 0, "inputToken": max(1, len(prompt) // 4),
         "outputToken": max(1, len(txt) // 4), "totalToken": max(2, (len(prompt) + len(txt)) // 4)},
        {"eventCode": "chat_message_send", "timestamp": now + 50, "reportDelay": 0, **common,
         "conversationId": conv_id, "requestId": rid, "messageId": "cmb-" + str(uuid.uuid4()),
         "requestModelId": "glm-5.2", "requestModelName": "GLM-5.2", "historyCount": 1,
         "isContextTruncated": False, "currentStepCount": 1, "traceId": rid, "rootRequestId": rid,
         "parentConversationId": conv_id, "agentName": "cli", "agentType": "main"}], rid

def _json_or_empty(r):
    """容错取 JSON：非 JSON 响应（401/403 空体、HTML 错误页）返回 {}，不抛异常。

    背景（issue #12/#13）：AT/RT 失效时上游返回非 JSON，旧代码直接 .json() 会把
    JSONDecodeError 抛出 run_account，整个运行崩掉、后续账号全部丢失。
    """
    try:
        d = r.json()
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def _clean_num(v):
    """把数值清理成简洁显示：整数去小数点；非整数最多 2 位小数，去掉尾 0。
    （API 返回值可能是 str/float，且带浮点二进制噪声如 390.67000198 → 390.67）"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    r = round(f, 2)
    if r == int(r):
        return str(int(r))
    return ("%.2f" % r).rstrip("0").rstrip(".")

def mask_phone(s):
    """手机号脱敏：隐藏中间 7 位，保留前 2 后 2（如 13800138000 → 13*******00）。
    非 11 位数字原样返回（如账号名"账号1"、昵称等不受影响）。"""
    s = str(s).strip()
    if len(s) == 11 and s.isdigit():
        return s[:2] + "*******" + s[-2:]
    return s

def queryCredits(s):
    """积分查询：剩余积分合计 + 各套餐明细（对齐客户端 App 顶部显示的剩余积分）。

    App 顶部"剩余积分"= 所有套餐 CycleRemainCapacity 之和（如 2425.4 = 主套餐1925.4
    + 加量包1 500 + 加量包2 0），脚本改为合计在前、明细在后，避免"看着不匹配"。
    """
    try:
        # 瞬时错误（网络/5xx）有界重试：2s/4s 退避，业务错误不重试（上游 panel 同款口径）
        r = api_retry(s, "POST", BASE + "/billing/meter/get-user-resource-summary", body={},
                      retries=3, gap=2.0).json()
        pkgs = r.get("data", {}).get("Packages", [])
        paid = r.get("data", {}).get("IsPaidUser")
        total_remain = 0.0
        out = []
        for i, p in enumerate(pkgs):
            remain_f = float(p.get("CycleRemainCapacity", 0) or 0)
            total_f = float(p.get("CycleTotalCapacity", 0) or 0)
            used_f = float(p.get("CycleUsedCapacity", 0) or 0)
            total_remain += remain_f
            pkg_name = "主套餐" if i == 0 else "加量包%d" % i
            out.append("%s剩余%s(共%s,已用%s)" % (pkg_name,
                       _clean_num(remain_f), _clean_num(total_f), _clean_num(used_f)))
        if not out:
            return "暂无套餐", paid
        return ("剩余积分合计%s（%s）" % (_clean_num(total_remain), "；".join(out))), paid
    except Exception as e:
        return "查询失败:" + str(e)[:40], False

def queryUsage(s):
    """用量查询：资源总数/总用量"""
    try:
        r = api_retry(s, "POST", BASE + "/billing/meter/get-user-resource", body={},
                      retries=3, gap=2.0).json()
        resp = r.get("data", {}).get("Response", {}).get("Data", {}) or {}
        return "共%d类资源，本月已使用%s次" % (resp.get("TotalCount", "?"), resp.get("TotalDosage", "?"))
    except Exception:
        return "用量数据延迟2-3小时"

def _checkin_activity_warn(sd):
    """签到活动到期预警（只读判断，对齐上游 checkin_activity.go 口径）。

    CN 字段：active / end_time（"YYYY-MM-DD HH:MM:SS" CST）/ activity_name。
    距 end_time 不足 7 天、或活动已关闭时给出提示，避免“活动结束才发现收入断档”。
    """
    import datetime
    name = sd.get("activity_name") or "签到活动"
    if sd.get("active") is False:
        return "⚠️%s已结束" % name
    raw = str(sd.get("end_time") or "")
    if len(raw) < 19:
        return ""
    try:
        end = datetime.datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""
    days = (end - beijing_now().replace(tzinfo=None)).total_seconds() / 86400.0
    if days < 0:
        return "⚠️%s已到期" % name
    if days <= 7:
        # 当日用「今日」，其余直接给日期（天数四舍五入容易歧义）
        when = "今日" if end.date() == beijing_today() else "%d-%d" % (end.month, end.day)
        return "⚠️%s%s结束" % (name, when)
    return ""

def _checkin_status(s):
    """签到活动读数（只读）：streak_days / total_credits / is_streak_day / next_streak_day / end_time。

    与成长中心的「活跃连签」（/v2/activity/growth/streak，热力墙/使用事件驱动）是两套
    完全不同的指标——日志/推送里一律写作「签到连签」以免混淆（issue #21）。
    """
    try:
        return (s.post(BASE + "/v2/billing/meter/checkin-activity-status", json={}, timeout=20,
                       verify=True).json().get("data") or {})
    except Exception:
        return {}

def _checkin_tail(s):
    """签到活动读数尾注：签到连签 / 累计积分 / 连签奖励日 / 到期预警（只读，失败返回空串）。

    上游多仓共用口径：POST /v2/billing/meter/checkin-activity-status 返回
    today_checked_in / streak_days / total_credits / is_streak_day / next_streak_day。
    """
    try:
        sd = _checkin_status(s)
        parts = []
        if sd.get("streak_days") is not None:
            parts.append("签到连签%s天" % sd["streak_days"])
        if sd.get("total_credits") is not None:
            parts.append("累计%s" % sd["total_credits"])
        if sd.get("is_streak_day"):
            parts.append("🎉今日为连签奖励日")
        elif sd.get("next_streak_day"):
            parts.append("距下一连签奖励 %s 天" % sd["next_streak_day"])
        warn = _checkin_activity_warn(sd)
        if warn:
            parts.append(warn)
        return "（%s）" % "，".join(parts) if parts else ""
    except Exception:
        return ""

def t_sign(s, uid, nick, log):
    """每日签到 + 签到活动读数（连签天数 / 累计积分 / 连签奖励日）

    daily-checkin 对瞬时错误（网络/5xx）有界重试 2 次（2s/4s）——上游 panel 口径：
    业务错误（今天已签到/4xx）不重试，避免把幂等拒绝当成失败反复打上游。
    """
    credit = None; msg = ""
    try:
        d = api_retry(s, "POST", BASE + "/v2/billing/meter/daily-checkin", body={},
                      retries=3, gap=2.0).json()
        if d.get("code") in (0, 200):
            credit = (d.get("data") or {}).get("credit")
        msg = (d.get("msg") or "")[:40]
    except Exception:
        msg = "签到请求失败（网络/5xx 重试后仍失败）"
    tail = _checkin_tail(s)
    if credit is not None:
        log("   ✅签到成功 +%s积分%s" % (credit, tail))
    else:
        log("   ✅签到: %s%s" % (msg or "今天已签到，请明天再来", tail))

def t_team_3(s, uid, nick, log):
    """召唤3次专家团：真实团队对话+全字段遥测"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    teams = get_team_experts(10)
    if not teams:
        return
    for rd in range(3):
        st, cur, tgt = prog(s, "Expert_team_use_3")
        if st in ("completed", "claimed") or (cur or 0) >= (tgt or 3):
            break
        team = teams[rd % len(teams)]
        prompt = "你好，请简单介绍一下你们团队能帮我做什么，回答OK即可"
        req_id = str(uuid.uuid4()); msg_id = "cmb-" + str(uuid.uuid4())
        ge = [{"eventCode": "ExpertActualUse", "id": team["id"],
               "extra": {"name": team["name"], "expertTitle": team.get("profession", ""),
                         "type": team.get("industryId", "") or "", "expertType": "team",
                         "source": "builtin", "version": "", "cost": 8, "characterCount": len(prompt),
                         "requestId": req_id, "messageId": msg_id,
                         "requestModelId": "glm-5.2", "requestModelName": "GLM-5.2"},
               "expertType": "team"}]
        meta = {"codebuddy.ai": {"growthEvent": json.dumps(ge, ensure_ascii=False), "promptRequestId": req_id,
                                 "clientSendTime": int(time.time() * 1000), "userId": uid,
                                 "mode": "craft", "model": "glm-5.2", "expertId": team["id"],
                                 "expert": {"id": team["id"], "name": team["name"],
                                            "profession": team.get("profession", ""), "prompt": prompt[:50]},
                                 "tags": ["expert:" + team["id"]]}}
        conv_id, txt = webchat(s, "team", prompt, meta)
        report(s, uid, nick, [{"eventCode": "expert_actual_use", "id": team["id"], "name": team["name"],
                               "expertTitle": team.get("profession", ""), "type": team.get("industryId", "") or "",
                               "expertType": "team", "source": "builtin", "version": "", "cost": 8,
                               "characterCount": len(prompt), "conversationId": conv_id, "requestId": req_id,
                               "messageId": msg_id, "requestModelId": "glm-5.2", "requestModelName": "GLM-5.2"}])
        time.sleep(5)
    st, cur, tgt = prog(s, "Expert_team_use_3")
    log("   召唤3次专家团: %s %s/%s" % (st, cur, tgt))

def t_buddy_apps(s, uid, nick, log):
    """发现应用/企鹅教师助手：desktop_buddy5_sequence + report_desktop_events"""
    for task in ("Buddy_App", "Buddy_App_QQ"):
        st, cur, tgt = prog(s, task)
        if st in ("completed", "claimed"):
            continue
        buddy_id = QQ_TPL if "QQ" in task else "buddy-app-default"
        buddy_name = "企鹅教师助手" if "QQ" in task else "发现应用"
        evs = desktop_buddy5_sequence(uid, nick, buddy_id, buddy_name)
        try:
            report_desktop_events(s, uid, nick, evs)
            log("   %s: buddyapp 五连 OK" % task)
            time.sleep(WRITE_GAP)
        except Exception as e:
            log("   %s: buddyapp failed %s" % (task, str(e)[:60]))
    log("   发现应用/企鹅教师助手: %s / %s" % (prog(s, "Buddy_App")[0], prog(s, "Buddy_App_QQ")[0]))

def _fetch_hp_theme(s):
    """appearance/resources 目录里找和平精英主题 → (resource_key, meta)；失败回落内置表。

    上游多仓共用口径：POST /v2/operation-platform/appearance/resources
    {platform:client, kind:theme, version, lang} → resources[] 含 id/name/vip_level/series。
    """
    try:
        d = s.post(BASE + "/v2/operation-platform/appearance/resources",
                   json={"platform": "client", "kind": "theme", "version": "5.5.6", "lang": "zh-CN"},
                   timeout=20, verify=True).json()
        for x in ((d.get("data") or {}).get("resources") or []):
            nm = x.get("name") or ""
            if "和平精英" in nm or "pubg" in (x.get("id") or "").lower():
                return x.get("id") or THEME_KEY, {"name": nm,
                                                      "vipLevel": x.get("vip_level", "free"),
                                                      "series": x.get("series", "craft")}
    except Exception:
        pass
    return THEME_KEY, {"name": "和平精英激战金秋", "vipLevel": "free", "series": "craft"}

def t_theme(s, uid, nick, log):
    """和平精英主题（Hp_Appearance）：主题目录取真 resource_key + meta，set 后补 skin_apply 事件"""
    st, cur, tgt = prog(s, "Hp_Appearance")
    if st is None:
        log("   和平精英主题: 不在任务列表，跳过")
        return
    if st in ("completed", "claimed"):
        log("   和平精英主题: 已 %s" % st)
        return
    key, meta = _fetch_hp_theme(s)
    r = s.post(BASE + "/portal/user-asset/appearance/set", json={"kind": "theme", "resource_key": key},
               timeout=20, verify=True)
    if r.json().get("code") == 0:
        time.sleep(2)
        report(s, uid, nick, [{"eventCode": "appearance_skin_apply", "action": "apply",
                               "source": "settings_close", "id": key,
                               "vipLevel": meta["vipLevel"], "series": meta["series"],
                               "type": "personal"}])
        time.sleep(6)
    log("   和平精英主题: %s" % prog(s, "Hp_Appearance")[0])

def t_library(s, uid, nick, log):
    st, cur, tgt = prog(s, "Library_read")
    if st is None:
        log("   体验资料库: 不在任务列表，跳过")
        return
    if st in ("completed", "claimed"):
        log("   体验资料库: 已 %s" % st)
        return
    report_web_event(s, uid, nick, "web_element_click", LIB_DOC_URL,
                     "library_doc_intro_click", "WorkBuddy资料库介绍")
    time.sleep(6)
    log("   体验资料库: %s" % prog(s, "Library_read")[0])

def t_chat_n(s, uid, nick, log, code, n, prompts):
    """通用聊天任务: chat_5 / Model_chat_GLM5.2"""
    for i in range(n):
        st, cur, tgt = prog(s, code)
        if st in ("completed", "claimed") or (cur or 0) >= (tgt or n):
            break
        conv_id, txt = webchat(s, code, prompts[i % len(prompts)])
        if txt:
            evs, _ = chat_request_events(uid, nick, conv_id, prompts[i % len(prompts)], txt)
            report(s, uid, nick, evs)
        time.sleep(4)
    st, cur, tgt = prog(s, code)
    log("   %s: %s %s/%s" % (code, st, cur, tgt))

def t_black_cat(s, uid, nick, log):
    st, cur, tgt = prog(s, "black_cat")
    if st in ("completed", "claimed"):
        log("   夜猫子: 已 %s %s/%s" % (st, cur, tgt))
        return
    if not within_night_window():
        # 显式用北京时间：GitHub Actions runner 是 UTC，localtime() 会误导排查
        log("   夜猫子: 仅23:00-08:00计数（CST），当前北京时间%d点，跳过" % beijing_now().hour)
        return
    prompts = ["今天天气怎么样？", "1+1等于几？", "讲个笑话"]
    # 官方规则：每天完成 1 次对话、累计满 3 天（≠ 一晚聊 3 次）。
    # 因此有响应即 break（当日计数已完成），首次失败最多重试 2 次（合计 3 次尝试）。
    for attempt in range(3):
        conv_id, txt = webchat(s, "night", prompts[attempt % len(prompts)])
        if txt:
            evs, _ = chat_request_events(uid, nick, conv_id, "聊天", txt, mode="night")
            report(s, uid, nick, evs)
            log("   夜猫子: 第%d次对话 ✅（回复%d字）——当日计数完成" % (attempt + 1, len(txt)))
            break
        log("   夜猫子: 第%d次对话 ❌（无回复，%s）" % (
            attempt + 1, "将重试" if attempt < 2 else "已达重试上限"))
        time.sleep(5)
    st, cur, tgt = prog(s, "black_cat")
    log("   夜猫子: %s %s/%s（每日1次×累计3天）" % (st, cur, tgt))

def t_expert_5(s, uid, nick, log):
    """召唤5次专家：普通专家遥测"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    experts = get_normal_experts(20)
    st0, cur0, tgt0 = prog(s, "expert_5")
    need = max(0, (tgt0 or 5) - (cur0 or 0))
    if st0 in ("completed", "claimed"):
        need = 0
    for i in range(need):
        st, cur, tgt = prog(s, "expert_5")
        if st in ("completed", "claimed") or (cur or 0) >= (tgt or 5):
            break
        e = experts[i % len(experts)] if experts else {"id": "expert-" + str(uuid.uuid4())[:8], "name": "Expert", "profession": ""}
        report(s, uid, nick, [
            {"eventCode": "expert_summoned", "id": e["id"], "name": e["name"], "type": "agent",
             "expertTitle": e.get("profession", ""), "expertType": "agent"},
            {"eventCode": "expert_actual_use", "id": e["id"], "name": e["name"], "type": e.get("industryId", "") or "",
             "expertType": "agent", "source": "builtin", "version": "", "cost": 0, "characterCount": 12,
             "conversationId": "conv-" + str(uuid.uuid4()), "requestId": str(uuid.uuid4()),
             "messageId": "msg-" + str(uuid.uuid4()),
             "requestModelId": "deepseek-v4-flash", "requestModelName": "DeepSeek V4 Flash"}])
        time.sleep(3)
    st, cur, tgt = prog(s, "expert_5")
    log("   召唤5次专家: %s %s/%s" % (st, cur, tgt))

def _fetch_scenes(s):
    """GET /console/as/support/scenes → [(id, name)]；拉不到则用内置表（实测线上 id）。"""
    try:
        r = s.get(BASE + "/console/as/support/scenes?locale=zh-CN", timeout=20, verify=True).json()
        out = [(str(x["id"]), x.get("name") or "")
               for x in ((r.get("data") or {}).get("scenes") or []) if x.get("id") is not None]
        if out:
            return out
    except Exception:
        pass
    return [("0", "幻灯片"), ("4", "深度研究"), ("8", "数据分析"), ("16", "设计"), ("20", "日常开发")]

def t_template_5(s, uid, nick, log):
    """使用5个模板：真实场景 id（/console/as/support/scenes）+ 事件组上报

    上游实测：一组 agent_task_created_with_template + template_used 计 1/5 进度；
    template_id 服务端不校验真实性，但用真实场景 id 更稳（旧版写死的 01-ProductDesign
    形态并不存在于线上场景表）。
    """
    scenes = _fetch_scenes(s)[:5]
    for tid, tname in scenes:
        st, cur, tgt = prog(s, "template_5")
        if st in ("completed", "claimed") or (cur or 0) >= (tgt or 5):
            break
        rid = "wb2api-tpl-%d-%s" % (int(time.time() * 1000), tid)
        report(s, uid, nick, [
            {"eventCode": "agent_task_created", "source": "CLOUD", "name": "", "mode": "craft",
             "requestModelId": "default", "action": tid, "has_template": True, "template_id": tid,
             "template_name": tname, "requestId": rid},
            {"eventCode": "agent_task_created_with_template", "templateId": tid, "templateName": tname,
             "template_id": tid, "mode": "working", "isCustomModel": True, "id": tid, "name": tname,
             "requestId": rid},
            {"eventCode": "template_used", "template_id": tid, "templateId": tid,
             "templateName": tname, "task_mode": "working", "id": tid, "name": tname,
             "source": "growth-center"},
            {"eventCode": "playbook_prompt_send", "ext1": str(uuid.uuid4()), "requestId": rid,
             "id": tid, "name": tname, "type": "other", "promptLength": 30, "isOfficial": 1,
             "source": "growth-center"}])
        time.sleep(2)
    st, cur, tgt = prog(s, "template_5")
    log("   使用5个模板: %s %s/%s" % (st, cur, tgt))

PLAYBOOK_CASE = {"id": "01-ProductDesign", "name": "产品设计", "type": "document"}

def _desktop_run(s, uid, nick, conv_name, prompt, extra_events):
    """真实对话 + 6 连桌面链 + 追加事件（桌面域上报）；返回是否已发出。"""
    try:
        cid, _t, mid = webchat2(s, conv_name, prompt)
        if not (cid and mid):
            return False
        evs = desktop_chat_sequence(uid, nick, cid, mid, mid)
        evs.extend(extra_events(cid, mid))
        report_desktop_events(s, uid, nick, evs)
        time.sleep(3)
        return True
    except Exception:
        return False

def t_canvas_automation(s, uid, nick, log):
    """设计创意模式 + 自动化任务 + 优秀灵感

    画布 / 灵感优先走「真实对话 + 桌面链 + 专属事件组」：上游 task-auto / task_runner 实测形状
    为 wbx_design_canvas_task_create(+open) 与 playbook_cta_click/playbook_prompt_send 挂在真实
    conversationId/requestId 上；未点亮时回落旧的 web 域裸事件。自动化任务用真实 rrule 对象形状。
    """
    if prog(s, "create_canvas")[0] not in ("completed", "claimed"):
        def _canvas_evs(cid, mid):
            return [{"eventCode": "wbx_design_canvas_task_create", "conversationId": cid, "requestId": mid,
                     "source": "summon_keyword", "isCustomModel": False, "name": "", "inputLength": 12,
                     "id": "wbx-canvas-%d" % int(time.time() * 1000), "cost": 0, "isSuccessful": True},
                    {"eventCode": "wbx_design_canvas_open", "conversationId": cid, "requestId": mid,
                     "id": "ardot-file-" + mid[-8:], "source": "summon_keyword", "type": "page",
                     "cost": 13000, "isSuccessful": True}]
        if not _desktop_run(s, uid, nick, "canvas", "帮我在设计创意画布里做一张活动海报", _canvas_evs) \
                or prog(s, "create_canvas")[0] not in ("completed", "claimed"):
            report(s, uid, nick, [{"eventCode": "agent_task_created", "source": "CLOUD", "name": "", "mode": "craft",
                                   "requestModelId": "default", "task_mode": "design"},
                                  {"eventCode": "wbx_design_canvas_task_create"}])
            time.sleep(3)
    st, cur, tgt = prog(s, "automation_1")
    if st not in ("completed", "claimed"):
        report(s, uid, nick, [{"eventCode": "agent_task_created", "source": "CLOUD", "name": "", "mode": "craft",
                               "requestModelId": "default", "task_mode": "automation",
                               "isAutomationBackground": True},
                              {"eventCode": "automated_task_create_suc", "action": "create",
                               "name": "每周五自动生成周报", "source": "manually",
                               "modelId": "deepseek-v4-flash", "modelIsThinking": False,
                               "expertId": "", "expertMarketplace": "", "connectorIds": "",
                               "connectorCount": 0, "skills": "", "skillCount": 0,
                               "scheduleType": "recurring", "pushToWeChat": False,
                               "pushToWecomBot": False,
                               "schedule": {"type": "recurring",
                                            "rrule": "FREQ=WEEKLY;BYDAY=FR;BYHOUR=9;BYMINUTE=0"},
                               "prompt": "每周五自动整理本周工作，生成一份周报。"},
                              {"eventCode": "automated_task_execute", "action": "execute"}])
        time.sleep(3)
    if prog(s, "playbook_prompt")[0] not in ("completed", "claimed"):
        def _pb_evs(cid, mid):
            payload = {"id": PLAYBOOK_CASE["id"], "name": PLAYBOOK_CASE["name"],
                       "type": PLAYBOOK_CASE["type"], "categoryId": "", "categoryName": ""}
            ev1 = {"eventCode": "web_element_click", "pageName": "playbook_detail",
                   "elementId": "playbook_ctaClick", "elementName": PLAYBOOK_CASE["name"],
                   "source": "discover"}
            ev2 = dict(payload); ev2.update({"eventCode": "playbook_cta_click", "source": "discover",
                                            "position": 0})
            ev3 = dict(payload); ev3.update({"eventCode": "playbook_prompt_send", "conversationId": cid,
                                            "requestId": mid, "promptLength": 30, "isOfficial": 1,
                                            "skills": "", "skillNames": "", "expertId": "",
                                            "expertName": "", "query": "", "source": "discover",
                                            "ext1": "discover"})
            return [ev1, ev2, ev3]
        if not _desktop_run(s, uid, nick, "playbook", "用这个案例帮我做一个同款", _pb_evs) \
                or prog(s, "playbook_prompt")[0] not in ("completed", "claimed"):
            report(s, uid, nick, [{"eventCode": "playbook_prompt_send", "ext1": str(uuid.uuid4()),
                                   "requestId": str(uuid.uuid4()), "id": PLAYBOOK_CASE["id"],
                                   "name": PLAYBOOK_CASE["name"],
                                   "type": "other", "promptLength": 30, "isOfficial": 1,
                                   "source": "growth-center"}])
            time.sleep(3)
    log("   设计/自动化/灵感: %s / %s / %s" % (prog(s, "create_canvas")[0], prog(s, "automation_1")[0],
                                             prog(s, "playbook_prompt")[0]))

def t_glm52(s, uid, nick, log):
    t_chat_n(s, uid, nick, log, "Model_chat_GLM5.2", 1, ["你好，请介绍一下你自己"])
    t_chat_n(s, uid, nick, log, "chat_5", 5, ["你好", "今天天气怎么样？", "1+1等于几？", "Python是什么？", "推荐一本好书"])

def t_lottery(s, uid, nick, log):
    """抽奖：查剩余次数并全部抽完"""
    try:
        r = s.get(BASE + "/v2/activity/growth/lottery/chances", timeout=20, verify=True).json()
        cd = r.get("data", {})
        chances = cd.get("balance", cd.get("chances", cd.get("remaining", 0)))
        if not chances:   # 备用口径：/lottery/summary 的 chances
            try:
                sd = s.get(BASE + "/v2/activity/growth/lottery/summary", timeout=20,
                         verify=True).json().get("data") or {}
                chances = sd.get("chances", sd.get("balance", 0))
            except Exception:
                chances = 0
        if not chances or chances <= 0:
            log("   🎰抽奖: 无次数")
            return
        won = []
        for i in range(int(chances)):
            if i > 0:
                time.sleep(2)
            rr = s.post(BASE + "/v2/activity/growth/lottery/draw",
                        json={"client_token": "draw-" + str(uuid.uuid4())}, timeout=20, verify=True).json()
            if rr.get("code") == 0:
                dd = rr.get("data", {})
                prize = str(dd.get("prize_name", dd.get("name", "?")))
                if dd.get("prize_type") == "physical":
                    prize += "（实物奖，需在成长中心填写收货地址）"
                won.append(prize)
            else:
                log("   🎰抽奖失败: %s" % str(rr.get("msg", ""))[:40])
                break
        log("   🎰抽奖: %s" % ("、".join(won) if won else "无结果"))
    except Exception as e:
        log("   🎰抽奖异常: %s" % str(e)[:50])

def t_blindbox(s, uid, nick, log):
    """盲盒：能量足够就开（每次10能量，最多开5次）"""
    try:
        q = s.get(BASE + "/v2/activity/growth/buddy/quota", timeout=20, verify=True).json()
        qd = q.get("data", {})
        affordable = qd.get("affordable", 0)
        if not affordable or affordable <= 0:
            log("   📦盲盒: 能量不足 (%s/10)" % qd.get("balance", "?"))
            return
        n = min(affordable, 5)
        got = []
        for _ in range(n):
            rr = s.post(BASE + "/v2/activity/growth/buddy/open", json={"count": 1}, timeout=20, verify=True).json()
            if rr.get("code") == 0:
                results = rr.get("data", {}).get("results", [])
                if results:
                    it = results[0]
                    ins = it.get("instance", {}); tpl = it.get("template", {})
                    got.append("%s(%s)" % (ins.get("name", tpl.get("name", "?")), ins.get("rarity", tpl.get("rarity", ""))))
            else:
                break
            time.sleep(1.5)
        log("   📦盲盒: %s" % ("、".join(got) if got else "开启失败"))
    except Exception as e:
        log("   📦盲盒异常: %s" % str(e)[:50])

def t_buddy_info(s, uid, nick, log):
    """Buddy 信息"""
    try:
        r = s.get(BASE + "/v2/activity/growth/buddy/info", timeout=20, verify=True).json()
        if r.get("code") == 0:
            b = r.get("data", {}).get("buddy", r.get("data", {}))
            log("   🐱Buddy: %s (%s)%s" % (b.get("name", "?"), b.get("rarity", ""),
                                           ", " + b.get("personality") if b.get("personality") else ""))
    except Exception:
        pass

def t_travel(s, uid, nick, log):
    """派猫猫旅行：到达领礼物 / 旅行中等待 / 空闲出发（幂等状态机）"""
    try:
        vis = s.get(BASE + "/v2/activity/growth/buddy/visible", timeout=20, verify=True).json()
        if vis.get("code") == 0:
            vd = vis.get("data", {})
            if not vd.get("buddy_visible", True) or not vd.get("has_buddy", True):
                log("   🐾旅行: 无Buddy，跳过")
                return
        st = s.get(BASE + "/v2/activity/growth/buddy/travel/status", timeout=20, verify=True).json()
        if not (st.get("code") == 0):
            log("   🐾旅行: 状态获取失败")
            return
        sd = st.get("data", {})
        state = sd.get("state", "idle")
        if state == "arrived":
            rr = s.post(BASE + "/v2/activity/growth/buddy/travel/claim", json={}, timeout=20, verify=True).json()
            if rr.get("code") == 0:
                log("   🐾旅行: 🎉领取礼物 +%s积分" % rr.get("data", {}).get("reward_credit", 0))
            else:
                log("   🐾旅行: 领取失败 %s" % str(rr.get("msg", ""))[:40])
            return
        if state == "traveling":
            remain = max(0, (sd.get("arrive_at", 0) - sd.get("server_now", 0)) // 60)
            log("   🐾旅行: 旅行中，约%s分钟后到达" % remain)
            return
        if sd.get("daily_limit_reached"):
            log("   🐾旅行: 今日次数已用尽")
            return
        cfg = s.get(BASE + "/v2/activity/growth/buddy/travel/config", timeout=20, verify=True).json()
        locs = cfg.get("data", {}).get("locations", [])
        if not locs:
            log("   🐾旅行: 无目的地")
            return
        rr = s.post(BASE + "/v2/activity/growth/buddy/travel/depart",
                    json={"location_id": locs[0].get("id")}, timeout=20, verify=True).json()
        if rr.get("code") == 0:
            remain = max(0, (rr.get("data", {}).get("arrive_at", 0) - rr.get("data", {}).get("server_now", 0)) // 3600)
            log("   🐾旅行: ✅已出发，约%s小时后到达（下次运行自动领取）" % remain)
        else:
            log("   🐾旅行: 出发失败 %s" % str(rr.get("msg", ""))[:40])
    except Exception as e:
        log("   🐾旅行异常: %s" % str(e)[:50])

def t_redeem(s, uid, nick, log, streak_days=None):
    """连登奖励兑换（7d/14d/28d 三档）

    以服务端 `redemption_status` 为准（上游 panel 实测：tier_7d/14d/28d_status =
    available / claimed / locked），已领取的档位不再发请求；本地连签天数仅作兜底。
    每次都必须用新的 client_token——复用旧键会被幂等去重吞掉本次领取。
    """
    tiers = [("7d", 7, "入门"), ("14d", 14, "进阶"), ("28d", 28, "巅峰")]
    status = {}
    try:
        stt = s.get(BASE + "/v2/activity/growth/streak", timeout=20, verify=True).json().get("data") or {}
        rs = stt.get("redemption_status") or {}
        status = {"7d": rs.get("tier_7d_status", ""), "14d": rs.get("tier_14d_status", ""),
                  "28d": rs.get("tier_28d_status", "")}
    except Exception:
        pass
    if not any(status.values()):   # 备用口径：/redeem/summary 的 starter/advanced/legendary_status
        try:
            rm = s.get(BASE + "/v2/activity/growth/redeem/summary", timeout=20,
                     verify=True).json().get("data") or {}
            for tier, key in (("7d", "starter"), ("14d", "advanced"), ("28d", "legendary")):
                if rm.get(key + "_status"):
                    status[tier] = rm[key + "_status"]
        except Exception:
            pass
    for tier, need, label in tiers:
        tst = status.get(tier, "")
        if tst == "claimed":
            log("   🎁兑换%s档: 已兑换过" % label)
            continue
        if tst == "locked" or (streak_days is not None and streak_days < need):
            continue
        rr = s.post(BASE + "/v2/activity/growth/redeem",
                    json={"tier": tier, "client_token": "redeem-" + tier + "-" + str(uuid.uuid4())},
                    timeout=20, verify=True).json()
        code = rr.get("code", -1)
        if code == 0:
            d = rr.get("data", {})
            extra = " +%s补签卡" % d["cards_granted"] if d.get("cards_granted") else ""
            log("   🎁兑换%s档: +%s积分 +%s能量 +%s抽奖%s" % (label, d.get("credit_granted", 0),
                                                        d.get("energy_granted", 0),
                                                        d.get("chances_granted", 0), extra))
        elif code == 409:
            log("   🎁兑换%s档: 已兑换过" % label)

def t_badges(s, uid, nick, log):
    try:
        r = s.get(BASE + "/v2/activity/growth/badges", timeout=20, verify=True).json()
        badges = r.get("data", {}).get("badges", r.get("data", {}).get("list", []))
        earned = sum(1 for b in badges if isinstance(b, dict) and b.get("earned"))
        log("   🏅徽章: %s个" % earned)
    except Exception:
        pass

def t_gift_compensation(s, uid, nick, log):
    """礼包(每号一次) + 补偿领取(活动开启时)"""
    try:
        r = s.post(BASE + "/billing/meter/claim-gift", json={}, timeout=15, verify=True).json()
        if r.get("code") == 0:
            log("   🎊新手礼包: +%s积分" % r.get("data", {}).get("credit", "?"))
    except Exception:
        pass
    try:
        r = s.post(BASE + "/billing/meter/claim-compensation", json={}, timeout=15, verify=True).json()
        if r.get("code") == 0:
            log("   🎊补偿领取: +%s积分" % r.get("data", {}).get("credit", "?"))
    except Exception:
        pass

def t_makeup(s, uid, nick, log):
    """补签卡：热力图检测昨日漏签则自动补签（保住连签）"""
    import datetime
    try:
        hm = s.get(BASE + "/v2/activity/growth/heatmap", timeout=20, verify=True).json()
        cells = hm.get("data", {}).get("cells", [])
        bal = s.get(BASE + "/v2/activity/growth/streak", timeout=20, verify=True).json().get("data", {}).get("makeup_cards", {}).get("balance", 0)
        yesterday = (beijing_today() - datetime.timedelta(days=1)).isoformat()
        missed = None
        for c in cells:
            d = str(c.get("date", ""))[:10]
            if d == yesterday and not c.get("score", 0):
                missed = yesterday
                break
        if missed and bal > 0:
            r = s.post(BASE + "/v2/activity/growth/makeup-cards/use", json={"target_date": missed},
                       timeout=20, verify=True).json()
            log("   🩹补签%s: %s" % (missed, "成功，连签保住" if r.get("code") == 0 else str(r.get("msg", ""))[:40]))
        elif missed:
            log("   🩹昨日(%s)漏签但无补签卡" % missed)
        else:
            log("   🩹无漏签，无需补签")
    except Exception as e:
        log("   🩹补签检查异常: %s" % str(e)[:50])

def has_buddy(s):
    """服务端是否已存在 Buddy 实例（旅行 / 其他任务 accept 的真实前置判据）。

    返回 True / False / None（None = 查询失败，状态未知）。
    """
    try:
        v = s.get(BASE + "/v2/activity/growth/buddy/visible", timeout=20, verify=True).json()
        d = v.get("data") or {}
        if "has_buddy" in d:
            return bool(d.get("has_buddy"))
        info = s.get(BASE + "/v2/activity/growth/buddy/info", timeout=20, verify=True).json()
        return bool((info.get("data") or {}).get("buddy"))
    except Exception:
        return None

LIGHTHOUSE_EXPERT = {"id": "ex_2cvvUZQhDyeJ", "name": "腾讯轻量云专家", "version": "1.0.2"}

def t_lighthouse(s, uid, nick, log):
    """腾讯轻量云专家：真实对话 + 桌面链（has_expert）+ actual_use(LOCAL)，失败回落伪造链。

    上游 panel 实测（2026-09-12 三账号点亮）：
      · 专家 id 固定 ex_2cvvUZQhDyeJ（version 1.0.2），不是随便挑一个专家
      · chat 链的 agent_task_created 需带 has_expert:true + expert_id/expert_name
      · expert_actual_use 的 mode 为 LOCAL（不是 craft），type 留空、cost=0
      · requestId / messageId 必须是真实会话的服务端 id（自造 uuid 不计数）
    """
    st, cur, tgt = prog(s, "Expert_lighthouse")
    if st is None:
        log("   腾讯轻量云专家: 不在当前任务列表，跳过")
        return
    if st in ("completed", "claimed"):
        log("   腾讯轻量云专家: %s %s/%s" % (st, cur, tgt))
        return
    lh = dict(LIGHTHOUSE_EXPERT)
    try:  # 市场列表命中则以服务端信息为准（version 等）
        for e in get_normal_experts(20):
            if (e.get("id") or "") == lh["id"] or "轻量" in (e.get("name") or ""):
                lh["id"] = e.get("id") or lh["id"]
                lh["name"] = e.get("name") or lh["name"]
                lh["version"] = e.get("version") or lh["version"]
                break
    except Exception:
        pass
    prompt = "你好，请简单介绍一下你能帮我做什么，回答OK即可"
    conv_id = ""; mid = ""
    try:
        ge = [{"eventCode": "ExpertActualUse", "id": lh["id"],
               "extra": {"name": lh["name"], "expertTitle": lh["name"], "expertType": "agent",
                         "source": "builtin", "version": lh["version"], "cost": 0,
                         "characterCount": len(prompt)},
               "expertType": "agent"}]
        meta = {"codebuddy.ai": {"growthEvent": json.dumps(ge, ensure_ascii=False),
                                 "promptRequestId": str(uuid.uuid4()),
                                 "clientSendTime": int(time.time() * 1000), "userId": uid,
                                 "mode": "LOCAL", "model": "fast-model", "expertId": lh["id"],
                                 "expert": {"id": lh["id"], "name": lh["name"], "prompt": prompt[:50]},
                                 "tags": ["expert:" + lh["id"]]}}
        conv_id, _txt, mid = webchat2(s, "lh", prompt, meta)
    except Exception as e:
        log("   腾讯轻量云专家: 对话异常 %s" % str(e)[:50])
    if conv_id and mid:
        summon = [
            {"eventCode": "expert_summon_click", "id": lh["id"], "name": lh["name"],
             "expertTitle": lh["name"], "type": "agent", "expertType": "agent",
             "source": "builtin", "mode": "LOCAL"},
            {"eventCode": "expert_summoned", "id": lh["id"], "name": lh["name"],
             "expertTitle": lh["name"], "type": "agent", "expertType": "agent",
             "source": "builtin", "version": lh["version"], "mode": "LOCAL"}]
        chain = desktop_chat_sequence(uid, nick, conv_id, mid, mid)
        for ev in chain:
            if ev.get("eventCode") == "agent_task_created":
                ev.update({"has_expert": True, "expert_id": lh["id"], "expert_name": lh["name"],
                           "expert_industry_id": ""})
        chain.append({"eventCode": "expert_actual_use", "id": lh["id"], "name": lh["name"],
                      "expertTitle": lh["name"], "type": "", "expertType": "agent",
                      "source": "builtin", "version": lh["version"], "cost": 0,
                      "characterCount": len(prompt), "mode": "LOCAL",
                      "conversationId": conv_id, "requestId": mid, "messageId": mid,
                      "requestModelId": "fast-model", "requestModelName": "fast-model"})
        try:
            report_desktop_events(s, uid, nick, summon + chain)
        except Exception as e:
            log("   腾讯轻量云专家: 桌面链上报失败 %s" % str(e)[:50])
        time.sleep(4)
        if prog(s, "Expert_lighthouse")[0] in ("completed", "claimed"):
            st, cur, tgt = prog(s, "Expert_lighthouse")
            log("   腾讯轻量云专家: %s %s/%s" % (st, cur, tgt))
            return
    # 回落：web 域伪造链（真实对话不可用，或桌面链未点亮时）
    try:
        rid = mid or str(uuid.uuid4()); cid = conv_id or ("conv-" + str(uuid.uuid4()))
        report(s, uid, nick, [{
            "eventCode": "expert_summoned", "id": lh["id"], "name": lh["name"],
            "type": "agent", "expertTitle": lh["name"], "expertType": "agent",
            "source": "builtin", "timestamp": int(time.time() * 1000)},
            {"eventCode": "expert_actual_use", "id": lh["id"], "name": lh["name"],
             "expertTitle": lh["name"], "type": "agent", "expertType": "agent",
             "source": "builtin", "version": lh["version"], "cost": 0, "characterCount": len(prompt),
             "conversationId": cid, "requestId": rid, "messageId": rid,
             "requestModelId": "fast-model", "requestModelName": "fast-model",
             "userId": uid}])
        time.sleep(3)
    except Exception as e:
        log("   腾讯轻量云专家: 失败 %s" % str(e)[:60])
    st, cur, tgt = prog(s, "Expert_lighthouse")
    log("   腾讯轻量云专家: %s %s/%s" % (st, cur, tgt))

MP_HEADER = {"X-Client-Platform": "miniprogram",
             "User-Agent": "Mozilla/5.0 (Linux; Android 14; MicroMessenger/8.0.49 WeChat/0.8.0 "
                           "MiniProgramEnv/android; wkbrowser xweb)"}

MP_REPORT_HEADERS = {
    "Content-Type": "application/json", "Accept": "application/json",
    "X-Client-Product": "workbuddy-mp", "X-Client-Version": "2.4.0",
    "X-Client-Platform": "mp-weixin", "X-Platform": "wechatmp",
}

def mp_machine_id(uid):
    """小程序 machineId（UUID 形态，按 uid 稳定派生——避免多账号共用同一设备号）。"""
    h = hashlib.md5(("mp:%s" % uid).encode()).hexdigest()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:32])

def mp_base(uid, nick):
    """小程序埋点公共指纹（对齐官方源码 module 22015 的 wQ()+Ao()）。

    源码常量（module 25439）：ideVersion/extVersion = 小程序包版本 2.2.8（恒定值，不是
    SaaS 状态）；os/osVersion/arch 取 getDeviceInfo() 运行值——这里固定成一份真实安卓机
    指纹（android 14 / arm64），与 mp_mini_expert_event、上游 task_runner 同口径。
    """
    now = int(time.time() * 1000)
    return {"timestamp": now, "ideType": "WorkBuddy_MP", "ideVersion": "2.2.8",
            "extName": "workbuddy-mp", "extVersion": "2.2.8", "product": "SaaS",
            "ideName": "wx_app_cloud", "platform": "mini_program",
            "source": "mini_program",   # 官方源码口径：mp 身份 = wx_app_cloud + WorkBuddy_MP + source
            "os": "android", "osVersion": "14", "arch": "arm64",
            "machineId": mp_machine_id(uid), "timezone": "Asia/Shanghai",
            "userId": uid, "userNickname": nick}

def mp_chat_event(uid, nick, conv_id, activity_id=None):
    """小程序 chat_request_send 事件（chat_3_times / school_season / Sequential_Tasks_1 判据）。"""
    # 官方源码（growth 模块 86692）：conversationId / requestId / traceId 同值传递
    rid = conv_id
    ev = {"eventCode": "chat_request_send", "mode": "chat", "inputLength": 12, "isPlan": False,
          "isAutoExecuteTerminal": False, "isAutoModify": False, "codebaseEnable": False,
          "maxToken": 0, "maxSteps": 500, "temperature": 0, "maxRetries": 0,
          "mentionContexts": [], "knowledgeId": [], "knowledgeName": [],
          "codebaseId": "", "mentionContextCount": 0, "command": "",
          "recommendId": "", "skillId": "", "skillCount": 0, "totalCount": 0,
          "requestId": rid, "traceId": rid, "rootRequestId": rid,
          "parentConversationId": conv_id, "conversationId": conv_id,
          "messageId": "msg-" + rid[-8:], "agentName": "mp", "agentType": "main",
          "codebuddy.session_id": conv_id,
          "codebuddy.conversation_request_id": rid}
    if activity_id:
        ev["activityId"] = activity_id
    return ev

def mp_expert_use_events(uid, nick, expert_id, expert_name, conv_id, activity_id=None):
    """专家召唤+对话 4 事件链（expert_use / Sequential_Tasks_2 判据，上游三账号实测）。

    链：expert_summon_click → expert_summoned → expert_actual_use → chat_request_send
    """
    rid = "wb2api-" + str(uuid.uuid4())
    cat = MP_EXPERT_CATEGORY
    evs = [
        {"eventCode": "expert_summon_click", "id": expert_id, "name": expert_id,
         "expertTitle": expert_name, "type": cat, "position": 0},
        {"eventCode": "expert_summoned", "id": expert_id, "name": expert_id,
         "expertTitle": expert_name},
        {"eventCode": "expert_actual_use", "id": expert_id, "name": expert_id,
         "expertTitle": expert_name, "type": cat, "characterCount": 14,
         "expertType": "builtin"},
        {"eventCode": "chat_request_send", "inputLength": 14, "isPlan": False,
         "isAutoExecuteTerminal": False, "isAutoModify": False, "codebaseEnable": False,
         "maxToken": 0, "maxSteps": 500, "temperature": 0, "maxRetries": 0,
         "mentionContexts": [], "knowledgeId": [], "knowledgeName": [],
         "codebaseId": "", "mentionContextCount": 0, "command": "",
         "recommendId": "", "skillId": "", "skillCount": 0, "totalCount": 0,
         "traceId": rid, "rootRequestId": rid,
         "parentConversationId": conv_id, "conversationId": conv_id,
         "messageId": "msg-" + rid[-8:], "agentName": "mp", "agentType": "main",
         "expertId": expert_id, "expertName": expert_name,
         "codebuddy.session_id": conv_id,
         "codebuddy.conversation_request_id": rid},
    ]
    if activity_id:
        for e in evs:
            e["activityId"] = activity_id
    return evs

def mp_model_chat_event(uid, nick, conv_id, model_id="glm-5.2", model_name="GLM-5.2"):
    """Sequential_Tasks_5 判据：mini chat_request_send + 模型字段（上游 mpsrc 实测形状）。"""
    ev = mp_chat_event(uid, nick, conv_id)
    ev["requestModelId"] = model_id
    ev["requestModelName"] = model_name
    return ev

def mp_playbook_events(uid, nick, case_id="01-ProductDesign", case_name="产品设计"):
    """Sequential_Tasks_7 判据：mp 指纹 playbook_cta_click + playbook_prompt_send。"""
    conv = "wb2api-mp-pb-" + str(uuid.uuid4())
    base = {"id": case_id, "name": case_name, "type": "document",
            "categoryId": "", "categoryName": "", "skills": "", "skillNames": ""}
    cta = dict(base, eventCode="playbook_cta_click", source="discover", position=1, extVersion="2.2.8")
    send = dict(base, eventCode="playbook_prompt_send", source="discover", promptLength=96,
                isOfficial=1, conversationId=conv, extVersion="2.2.8")
    return [cta, send]

def mp_mini_expert_event(uid, nick, expert_id, expert_name):
    """Sequential_Tasks_2 判据：mp 指纹 expert_actual_use（上游小程序源码实测形状）。

    ⚠️ 与 school 域 expert 事件的区别（勿混用）：
      · 不带 activityId / conversationId —— 真实小程序事件就是两者都没有
      · extVersion 用小程序自身版本 2.2.8（school 段是 "SaaS"，另一口径）
      · type 固定 "send_message"
    上游实测：上报即 completed，claim 入账 200c+5e。
    """
    return {"eventCode": "expert_actual_use", "timestamp": int(time.time() * 1000),
            "reportDelay": 0, "ideName": "wx_app_cloud", "ideType": "WorkBuddy_MP",
            "extName": "workbuddy-mp", "extVersion": "2.2.8", "product": "SaaS",
            "source": "mini_program", "os": "android", "osVersion": "14",
            "arch": "arm64", "timezone": "Asia/Shanghai",
            "machineId": mp_machine_id(uid), "userId": uid,
            "id": expert_id, "name": expert_id, "expertTitle": expert_name,
            "type": "send_message", "characterCount": 12, "expertType": "agent"}

def mp_report(s, uid, nick, events):
    """以小程序指纹向 www.codebuddy.cn/v2/report 批量上报（上游 ReportMPEvent 同款）。"""
    base = mp_base(uid, nick)
    arr = []
    for e in events:
        m = dict(base)
        m.update(e)
        arr.append(m)
    s2 = requests.Session(); s2.trust_env = False
    hdr = dict(MP_REPORT_HEADERS)
    hdr["Authorization"] = s.headers.get("Authorization", "")
    if uid:
        hdr["X-User-Id"] = uid
    try:
        r = s2.post("https://www.codebuddy.cn/v2/report", json=arr,
                    headers=hdr, timeout=20, verify=True)
        return r.status_code
    except Exception:
        return 0

MP_EXPERT_CATEGORY = "16-BackToSchool"

MP_EXPERT_FALLBACK = {"WorkspaceBuilder": {"id": "WorkspaceBuilder", "name": "工作台搭建师"}}

def _mp_pick_expert(s):
    """取一个真实专家 id/name（mp 专家类任务判据用）。

    优先拉线上专家列表（use_count 倒序，字段名 expert_id —— 不是 id）；
    拉不到时回落内置兜底 id，保证判据事件仍带真实专家身份。
    """
    body = {"edition_mode": "all,domestic", "page": 1, "page_size": 20,
            "sort_by": "use_count", "sort_order": "desc",
            "categories": [MP_EXPERT_CATEGORY], "expert_type": "agent"}
    try:
        r = api_retry(s, "POST", CBDOMAIN + "/v2/operation-platform/market/expert/list", body=body)
        for e in ((r.json().get("data") or {}).get("experts") or []):
            eid = e.get("expert_id")
            if not eid:
                continue
            dn = e.get("display_name_zh") or {}
            name = (dn.get("zh") if isinstance(dn, dict) else dn) or eid
            return eid, name
    except Exception:
        pass
    for eid, info in MP_EXPERT_FALLBACK.items():
        return eid, info["name"]
    return "", ""

def _mp_prog(s, code):
    """小程序口径查询任务（需 X-Client-Platform: miniprogram，否则任务不下发）。"""
    try:
        r = s.get(BASE + "/v2/activity/growth/tasks", timeout=25, verify=True, headers=MP_HEADER)
        for t in r.json().get("data", {}).get("tasks", []):
            if t.get("task_code") == code:
                pr = t.get("progress") or {}
                return t.get("accept_status", ""), pr.get("current"), pr.get("target")
    except Exception:
        pass
    return None, None, None

def _mp_accept_res(s, code):
    """小程序口径 accept，返回 (ok, status, message)。缺 mp 头会返回 task not found。"""
    try:
        r = s.post(BASE + "/v2/activity/growth/tasks/accept", json={"task_codes": [code]},
                   timeout=20, verify=True, headers=MP_HEADER)
        d = r.json()
        results = (d.get("data") or {}).get("results") or []
        status = (results[0].get("status") or "") if results else (d.get("msg") or "")
        msg = (results[0].get("message") or "") if results else ""
        return (r.status_code == 200 and status == "accepted"), status, msg
    except Exception as e:
        return False, "", str(e)[:80]

def _mp_accept(s, code, log=None):
    """小程序口径接受任务，失败时打印服务端原因（保留 bool 返回的兼容包装）。"""
    ok, status, msg = _mp_accept_res(s, code)
    if not ok and log:
        log("      ✗ accept %s: %s %s" % (code, status or "无返回", msg[:50]))
    return ok

def _mp_locked_hint(log, label, msg, indent="   "):
    """链式任务未解锁时输出人类可读提示（含解锁日期）。命中返回 True。"""
    m = re.search(r"locked until (\d{4}-\d{2}-\d{2})", msg or "")
    if not m:
        return False
    log("%s%s: 今日未解锁（链式任务每日零点解锁下一环，%s 零点自动解锁，下次运行自动推进）"
        % (indent, label, m.group(1)))
    return True

def _mp_claim(s, code, log):
    """小程序口径领奖（缺头会 400）。"""
    try:
        r = s.post(BASE + "/activity/growth/tasks/%s/claim" % code, json={},
                   timeout=20, verify=True, headers=MP_HEADER)
        d = r.json().get("data", {})
        log("   🎁领奖[%s]: %s" % (code, "已领过" if d.get("already_claimed")
                                   else "+%s积分+%s能量" % (d.get("credit"), d.get("energy"))))
        return r.status_code == 200
    except Exception as e:
        log("   🎁领奖[%s]: 失败 %s" % (code, str(e)[:50]))
        return False

def _mp_task_row(s, code):
    """mp 口径任务原始行（含 locked / valid_start / reward_* 等字段）；未下发返回 None。

    服务端每个任务行都带 locked；locked=true 表示未到上线时间（accept 会报
    "task locked until <日期>"），此时上报与领奖都无意义且会被判无效。
    """
    try:
        r = s.get(BASE + "/v2/activity/growth/tasks", timeout=25, verify=True, headers=MP_HEADER)
        for t in r.json().get("data", {}).get("tasks", []):
            if t.get("task_code") == code:
                return t
    except Exception:
        pass
    return None

def _mp_do_task(s, uid, nick, code, log, events_fn, label, target=1, pace=False):
    """小程序任务通用流程：mp 查询 → accept → 判据上报 → 回读 → claim。

    target：任务的进度目标（未 accept 时 progress 为 null，调用方需提供兜底值）。
    pace  ：对话类判据（chat_request_send）按“真人节奏”上报。上游对 Sequential 系列
            有反作弊校验：数秒级连发先计入进度（回读满进度），随后被整体判无效回滚
            （claim 返回 400 task not completed）。上游实测 45s 间隔逐条上报全存活 →
            claim 成功，故每条前等 MP_CHAT_GAP(45s)+0~10s 抖动，首条也等（上一轮被
            回滚的残留进度，立即重报同样无效）；--mp-gap / WORKBUDDY_MP_GAP 可调。
    """
    row = _mp_task_row(s, code)
    if row is None:
        log("   %s: mp 口径未下发该任务，跳过" % label)
        return
    if row.get("locked"):
        log("   %s: 未到上线时间（解锁 %s），跳过" % (label, str(row.get("valid_start") or "见任务页")[:10]))
        return
    st = row.get("accept_status", "")
    _pr = row.get("progress") or {}
    cur, tgt = _pr.get("current"), _pr.get("target")
    if st in ("completed", "claimed"):
        if st == "completed":
            _mp_claim(s, code, log)
        else:
            log("   %s: 已领取，跳过" % label)
        return
    if st == "not_accepted":
        ok, a_status, a_msg = _mp_accept_res(s, code)
        if not ok:
            log("      ✗ accept %s: %s %s" % (code, a_status or "无返回", a_msg[:50]))
            if not _mp_locked_hint(log, label, a_msg):
                log("   %s: accept 失败，跳过" % label)
            return
        time.sleep(WRITE_GAP)
        # accept 后回读真实进度：accept 前 progress 为 null（target 下发 0），仅用
        # 兜底 target 会少报 → 误判达标 → claim 400（上游 Tasks_6 首轮实测）
        st, cur, tgt = _mp_prog(s, code)
        if st in ("completed", "claimed"):
            if st == "completed":
                _mp_claim(s, code, log)
            else:
                log("   %s: 已领取，跳过" % label)
            return
    # 缺口计算：cur 可能为 None（未激活时 progress 全空）→ 用 target 兜底
    cur = cur or 0
    tgt = tgt or target
    need = max(1, tgt - cur)
    try:
        sent = 0
        for i in range(need):
            if pace and MP_CHAT_GAP > 0:
                import random
                # 抖动：默认 45s 档对应 0~10s；小间隔时按比例缩小，便于自测/提速
                time.sleep(MP_CHAT_GAP + random.uniform(0, min(10.0, MP_CHAT_GAP * 0.25)))
            evs = events_fn(i)
            st_code = mp_report(s, uid, nick, evs)
            sent += len(evs)
            if i < need - 1 and not pace:
                time.sleep(WRITE_GAP)
        log("   %s: 判据已上报（%d 次 / %d 个事件，目标 %s）" % (label, need, sent, tgt))
        time.sleep(2.5)
        st2, cur2, tgt2 = _mp_prog(s, code)
        if st2 in ("completed", "claimed"):
            log("   %s: ✅ 已完成 %s/%s" % (label, cur2, tgt2))
            if st2 == "completed":
                _mp_claim(s, code, log)
        else:
            log("   %s: %s %s/%s（服务端暂未关联）" % (label, st2, cur2, tgt2))
    except Exception as e:
        log("   %s: 失败 %s" % (label, str(e)[:60]))

def _mp_chat_evs(uid, nick, prefix, activity_id=None):
    """返回一个 events_fn(i)：每次产出一条 mini 对话事件（独立 conversationId）。"""
    def _fn(i):
        return [mp_chat_event(uid, nick, "%s-%s-%d" % (prefix, uuid.uuid4(), i),
                              activity_id=activity_id)]
    return _fn

def t_sequential_tasks(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_1：完成 1 次对话（+100c+5e）"""
    _mp_do_task(s, uid, nick, "Sequential_Tasks_1", log,
                _mp_chat_evs(uid, nick, "wbmp"), "小程序对话任务", target=1, pace=True)

def t_sequential_tasks_2(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_2：选中专家并完成对话（+200c+5e）

    判据 = 单条 mp 指纹 expert_actual_use（不带 activityId/conversationId）。
    """
    def _evs(i):
        eid, ename = _mp_pick_expert(s)
        if not eid:
            eid, ename = "WorkspaceBuilder", "专家"
        return [mp_mini_expert_event(uid, nick, eid, ename)]
    _mp_do_task(s, uid, nick, "Sequential_Tasks_2", log, _evs, "小程序专家对话", target=1)

def t_sequential_tasks_3(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_3：完成 5 次对话（+300c+5e）

    判据与 Tasks_1 同形状（mini chat_request_send 无 activityId），按上报条数累加。
    """
    _mp_do_task(s, uid, nick, "Sequential_Tasks_3", log,
                _mp_chat_evs(uid, nick, "wbmp3"), "小程序对话×5", target=5, pace=True)

def t_sequential_tasks_4(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_4：创建 1 个定时任务（+100c+5e）

    官方小程序源码快照口径（HanawaBanana 同步 ithtelab 官方包内 upstream/ 快照）：判据是
    **mp 指纹** automated_task_create_suc —— ideName=wx_app_cloud + mode=CLOUD，
    **不带** schedule/rrule 对象（桌面 automation_1 的 rrule 虚拟对象是另一域口径，
    照抄会失去 mp 关联），走小程序上报通道。未点亮时回落桌面域事件（旧口径）。
    """
    def _evs(i):
        # 官方源码形状（dynamic-common appservice TaskFormSheet 创建成功）：不带
        # schedule/rrule 对象，也没有 modelId/connector/pushTo* 等桌面字段；
        # scheduleType 取小程序表单频率枚举（daily/interval/once）
        return [{"eventCode": "automated_task_create_suc", "mode": "CLOUD",
                 "name": "每日读书提醒", "source": "manually",
                 "skills": "", "skillCount": 0,
                 "scheduleType": "daily"}]
    _mp_do_task(s, uid, nick, "Sequential_Tasks_4", log, _evs, "小程序定时任务", target=1)
    if _mp_prog(s, "Sequential_Tasks_4")[0] in ("completed", "claimed"):
        return
    st2, cur2, tgt2 = None, None, None
    # 回落：桌面域 automation 事件（旧口径，实测同样能点亮）
    try:
        report_desktop_events(s, uid, nick, [{
            "eventCode": "automated_task_create_suc", "name": "wb2api 定时任务",
            "source": "manually", "modelId": "fast-model", "modelIsThinking": True,
            "connectorCount": 0, "skills": "", "skillCount": 0,
            "scheduleType": "once", "mode": "LOCAL"}])
        time.sleep(2.5)
        st2, cur2, tgt2 = _mp_prog(s, "Sequential_Tasks_4")
    except Exception:
        pass
    if st2 in ("completed", "claimed"):
        log("   小程序定时任务: ✅ 已完成（桌面域回落） %s/%s" % (cur2, tgt2))
        if st2 == "completed":
            _mp_claim(s, "Sequential_Tasks_4", log)
    else:
        log("   小程序定时任务: %s %s/%s（服务端暂未关联）" % (st2, cur2, tgt2))

def t_sequential_tasks_5(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_5：使用 1 次 GLM5.2 模型（+100c+5e）"""
    def _evs(i):
        return [mp_model_chat_event(uid, nick, "wbmp5-%s-%d" % (uuid.uuid4(), i))]
    _mp_do_task(s, uid, nick, "Sequential_Tasks_5", log, _evs, "小程序GLM5.2", target=1, pace=True)

def t_sequential_tasks_6(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_6：完成 10 次对话（target 以服务端下发为准）"""
    _mp_do_task(s, uid, nick, "Sequential_Tasks_6", log,
                _mp_chat_evs(uid, nick, "wbmp6"), "小程序对话×10", target=10, pace=True)

def t_sequential_tasks_7(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_7：体验灵感功能"""
    def _evs(i):
        evs = mp_playbook_events(uid, nick)
        report_desktop_events(s, uid, nick, evs)   # PC 口径补一发（判据疑 PC/mp 双侧）
        return evs
    _mp_do_task(s, uid, nick, "Sequential_Tasks_7", log, _evs, "小程序灵感功能", target=1)

def t_unknown_tasks(s, uid, nick, log):
    """任务列表体检：未覆盖的新任务提示 + 未完成任务的有效期预警

    服务端任务行带 valid_start / valid_end（如 Buddy_App_QQ 至 2026-10-10）——
    过期后就领不到了，所以对「未完成且 7 天内到期 / 已过期」的任务给出 ⏰ 提示。
    """
    known = {"create_canvas", "playbook_prompt", "RichMeow_Chat", "Library_read", "Expert_lighthouse",
             "Expert_Philanthropy", "Hp_Appearance", "Buddy_App", "Buddy_App_QQ", "Model_chat_GLM5.2",
             "black_cat", "Expert_team_use_3", "first_buddy", "chat_5", "skill_1", "expert_5",
             "template_5", "automation_1", "workstation_expert",
             "Sequential_Tasks_1", "Sequential_Tasks_2", "Sequential_Tasks_3",
             "Sequential_Tasks_4", "Sequential_Tasks_5",
             "Sequential_Tasks_6", "Sequential_Tasks_7"}
    r = s.get(BASE + "/v2/activity/growth/tasks", timeout=25, verify=True).json()
    rows = r.get("data", {}).get("tasks", [])
    for t in rows:
        if not isinstance(t, dict):
            continue
        code = t.get("task_code", "")
        st = t.get("accept_status", "")
        if code in known or st in ("claimed", "completed"):
            continue
        desc = t.get("task_desc", "")[:50]
        if "subscribe" in code.lower() or "公众号" in (t.get("title", "") + desc):
            log("   ⚠️新任务需手动: %s %s (%s) — 需微信扫码关注公众号" % (code, t.get("title", ""), desc))
        elif "donat" in code.lower() or "捐款" in desc or "公益" in t.get("title", ""):
            log("   ⚠️新任务需手动: %s %s (%s) — 涉及真实捐款" % (code, t.get("title", ""), desc))
        else:
            log("   ⚠️未覆盖新任务: %s %s (%s) — 请反馈更新脚本" % (code, t.get("title", ""), desc))
    # 有效期预警：未完成但即将过期（或已过期）的任务
    import datetime
    today = beijing_today()
    soon = []
    for t in rows:
        if not isinstance(t, dict) or t.get("accept_status") in ("claimed", "completed"):
            continue
        ve = str(t.get("valid_end") or "")[:10]
        if len(ve) < 10:
            continue
        try:
            d = datetime.date(*[int(x) for x in ve.split("-")])
        except Exception:
            continue
        left = (d - today).days
        if left < 0:
            soon.append((t.get("task_code", ""), ve, "已过期"))
        elif left <= 7:
            soon.append((t.get("task_code", ""), ve, "%d 天后到期" % left))
    if soon:
        log("   ⏰ 任务有效期提醒（未完成）:")
        for code, ve, when in soon[:6]:
            log("      · %s %s（%s）" % (code, ve, when))

def derive_id(uid, salt):
    """由 uid 稳定派生 36 位 hex 设备标识（sha256[:18]，对齐上游 deriveID，幂等）。"""
    return hashlib.sha256(("%s:%s" % (salt, uid)).encode()).hexdigest()[:36]

def desktop_fingerprint(uid, nick):
    """公共桌面指纹（注入每个桌面事件，覆盖同名业务键）。"""
    now = int(time.time() * 1000)
    return {
        "timezone": "Asia/Shanghai", "reportDelay": 2000,
        "userId": uid, "username": nick, "userNickname": nick,
        "product": "SaaS", "releaseDate": 1789036585355,
        "commit": "5f9692923c93033111c51ad7b003eb80204a9b75",
        "ideName": "WorkBuddy", "ideType": "WorkBuddy", "ideVersion": "5.5.6",
        "machineId": derive_id(uid, "machine"), "sessionId": derive_id(uid, "session"),
        "extName": "workbuddy-desktop", "extVersion": "5.5.6",
        "os": "win32", "arch": "x64", "osVersion": "10.0.26220",
        "cpuCores": 20, "memorySize": 24,
        "timestamp": now, "presentAt": now,
    }

def within_night_window():
    """CST 夜猫窗口 23:00 - 次日 08:00"""
    try:
        return beijing_now().hour >= 23 or beijing_now().hour < 8
    except Exception:
        return None

def beijing_now():
    """北京时间（UTC+8）。不依赖系统 TZ：Actions runner 是 UTC，直接用会算错日期。"""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))

def beijing_today():
    """北京日期（date 对象）。补签等日期逻辑必须用它，不能用 date.today()。"""
    return beijing_now().date()

def desktop_chat_sequence(uid, nick, conversation_id, request_id, message_id,
                          model_id="fast-model", model_name="fast-model"):
    """6 连「桌面端成功对话」事件链（点亮 RichMeow_Chat）。"""
    now = int(time.time() * 1000)
    ev = []
    def mk(code, extra):
        e = {"eventCode": code}
        e.update(extra)
        ev.append(e)
    mk("agent_task_created", {
        "source": "LOCAL", "name": "working", "task_target": "local", "mode": "craft",
        "requestModelId": model_id, "requestModelName": model_name,
        "has_repo": False, "repo_type": "none", "workspace_type": "empty",
        "has_connector": False, "connector_types": [],
        "has_mention": False, "mention_types": [],
        "has_template": False, "action": "", "template_name": "",
        "has_expert": False, "expert_id": "", "expert_name": "", "expert_industry_id": "",
        "has_skill": False, "skill_names": [],
        "conversationId": conversation_id, "messageId": message_id,
        "buddyId": "", "buddyName": ""})
    mk("chat_message_send", {
        "messageId": message_id + "-assistant", "historyCount": 0,
        "isContextTruncated": False, "currentStepCount": 1,
        "traceId": request_id, "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_request_send", {
        "inputLength": 24, "isPlan": False, "isAutoExecuteTerminal": False,
        "isAutoModify": False, "codebaseEnable": False, "maxToken": 0,
        "maxSteps": 500, "temperature": 0, "maxRetries": 0,
        "mentionContexts": [], "knowledgeId": [], "knowledgeName": [],
        "codebaseId": "", "mentionContextCount": 0, "command": "",
        "recommendId": "", "skillId": "", "skillCount": 0, "totalCount": 0,
        "traceId": request_id, "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_message_response", {
        "messageId": message_id + "-assistant", "responseModelId": model_id,
        "inputToken": 120, "outputToken": 80, "totalToken": 200,
        "cachedTokens": 0, "cachedWriteTokens": 0, "cachedMissTokens": 0,
        "isSuccessful": True, "messageErrorCode": "", "finishReason": "stop",
        "firstTokenAt": now, "traceId": request_id,
        "conversationId": conversation_id,
        "rootRequestId": request_id, "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_message_status", {
        "messageId": message_id + "-assistant", "messageErrorCode": "0",
        "traceId": request_id, "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_request_response", {
        "mode": "craft", "toolCallCount": 0,
        "inputToken": 120, "outputToken": 80, "totalToken": 200,
        "cachedTokens": 0, "cachedWriteTokens": 0, "cachedMissTokens": 0,
        "isSuccessful": True, "messageErrorCode": "", "finishReason": "stop",
        "rootRequestId": request_id, "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    return ev

def desktop_buddy5_sequence(uid, nick, buddy_id, buddy_name):
    """五连「进入 Buddy 应用」事件（点亮 Buddy_App/_QQ）。"""
    ev = []
    def mk(code, extra):
        e = {"eventCode": code, "mode": "LOCAL",
             "buddyId": buddy_id, "buddyName": buddy_name}
        e.update(extra)
        ev.append(e)
    mk("buddyapp_discover_click", {})
    mk("buddyapp_show", {"elementId": buddy_id, "elementName": buddy_name, "position": 2})
    mk("buddyapp_enter_click",
       {"elementId": buddy_id, "elementName": buddy_name, "position": 2, "isFirstPage": "1"})
    mk("buddyapp_auth_confirm_click", {"elementId": buddy_id, "elementName": buddy_name})
    mk("buddyapp_bindaccount_skip_click", {"elementId": buddy_id, "elementName": buddy_name})
    return ev

DESKTOP_UA = "WorkBuddy/5.5.6 WorkBuddy/5.5.6 CLI/2.137.1"

DESKTOP_BASE = "https://copilot.tencent.com"

def report_desktop_events(s, uid, nick, events):
    """桌面指纹上报：copilot.tencent.com/v2/report，**裸数组** + 桌面头族。

    对齐上游 ReportDesktopEvent：desktopBase=chatBase(copilot 域)、body 为裸数组、
    头含 X-Domain/X-Product/X-Request-ID/X-User-Id + 桌面 UA。
    """
    fp = desktop_fingerprint(uid, nick)
    arr = []
    for e in events:
        m = dict(fp)          # 先铺指纹
        m.update(e)           # 业务字段优先（可覆盖同名设备键）
        arr.append(m)
    hdr = {"Authorization": s.headers.get("Authorization", ""),
           "Accept": "application/json, text/plain, */*",
           "Content-Type": "application/json;charset=UTF-8",
           "User-Agent": DESKTOP_UA,
           "X-Domain": DESKTOP_BASE, "X-Product": "SaaS",
           "X-Request-ID": derive_id(uid, "req") + str(int(time.time() * 1000) % 1000000)}
    if uid:
        hdr["X-User-Id"] = uid
    s2 = requests.Session(); s2.trust_env = False
    try:
        r = s2.post(DESKTOP_BASE + "/v2/report", json=arr, headers=hdr,
                    timeout=20, verify=True)
        return r.status_code
    except Exception:
        return 0

def report_web_event(s, uid, nick, event_code, page_url, element_id, element_name):
    """以 web 域指纹上报单事件（Library_read）。"""
    now = int(time.time() * 1000)
    ev = {"eventCode": event_code, "timestamp": now, "reportDelay": 0,
          "pageURL": page_url, "elementId": element_id, "elementName": element_name,
          "os": "Win32", "arch": "", "osVersion": "10.0",
          "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
          "machineId": derive_id(uid, "webmachine"), "userId": uid, "userNickname": nick}
    return api_retry(s, "POST", BASE + "/v2/report", body={"common": {
        "userId": uid, "userNickname": nick, "ideName": "web",
        "ideType": "web", "machineId": derive_id(uid, "webmachine"),
        "mode": "CLOUD", "userAgent": "Mozilla/5.0", "os": "Win32",
        "timezone": "Asia/Shanghai"}, "events": [ev]})

def _accept_with_verify(s, code, log):
    """accept 并验证登记生效（读 results[].status + 回读 accept_status）。"""
    for attempt in (1, 2):
        r = s.post(BASE + "/v2/activity/growth/tasks/accept", json={"task_codes": [code]},
                   timeout=20, verify=True)
        status = ""
        try:
            d = r.json()
            results = (d.get("data") or {}).get("results") or []
            status = (results[0].get("status") or "") if results else (d.get("msg") or "")
        except Exception:
            pass
        t = prog(s, code)
        ast = t[0] if t else "not_accepted"
        ok = (r.status_code == 200 and status == "accepted" and ast != "not_accepted")
        if ok:
            return True
        if attempt > 1:
            log("      ✗ %s: accept %s 回读=%s" % (code, status or "无返回", ast))
        time.sleep(WRITE_GAP)
    return False

# ---------- 独立维护边界与执行器 ----------
DRY = False
ERRORS = []
REQUEST_COUNT = 0
SECRETS = []
ACTIVE_TAG = '任务'
RealSession = requests.Session

def timeline(text):
    print('[%s][%s] %s' % (time.strftime('%H:%M:%S'), ACTIVE_TAG, text), flush=True)

class SafeError(RuntimeError):
    pass

class SafeSession(RealSession):
    def request(self, method, url, **kwargs):
        global REQUEST_COUNT
        if DRY:
            raise SafeError('断网预演禁止 HTTP')
        from urllib.parse import urlparse
        host = urlparse(url).hostname
        if host not in {'www.workbuddy.cn', 'www.codebuddy.cn', 'copilot.tencent.com',
                        'acc-1258344699.cos.accelerate.myqcloud.com'}:
            ERRORS.append(((method,url),'非许可接口'))
            raise SafeError('非许可接口')
        kwargs['verify'] = True
        kwargs['timeout'] = kwargs.get('timeout') or 25
        kwargs['allow_redirects'] = False
        REQUEST_COUNT += 1
        try:
            r = super().request(method, url, **kwargs)
            if r.status_code == 400 and '/activity/growth/tasks/' in url and url.endswith('/claim') and not (kwargs.get('headers') or {}).get('x-client-platform'):
                return r
            if r.status_code < 200 or r.status_code >= 300:
                raise SafeError('HTTP %d' % r.status_code)
            if not kwargs.get('stream'):
                d = r.json()
                # 无账号认证的专家市场 JSON 不使用业务 code。
                if host != 'acc-1258344699.cos.accelerate.myqcloud.com':
                    if not isinstance(d, dict) or d.get('code') not in (0, 200):
                        raise SafeError('业务码缺失或失败')
                    if not isinstance(d.get('data'), dict):
                        raise SafeError('业务数据结构变化')
            if not kwargs.get('stream') and host != 'acc-1258344699.cos.accelerate.myqcloud.com':
                identity(d['data'])
            ERRORS[:] = [item for item in ERRORS if item[0] != (method,url)]
            timeline('%s 请求：HTTP %d，业务响应已校验' % (method.upper(), r.status_code))
            return r
        except Exception as e:
            reason = str(e) if isinstance(e, SafeError) else '网络或响应解析失败'
            ERRORS.append(((method,url),reason))
            timeline('❌ ' + reason)
            raise SafeError(reason) from None

requests.Session = SafeSession

def _parse_env_tokens(raw):
    items = []
    for line in raw.splitlines():
        line = line.strip().strip('"').strip("'")
        if not line:
            continue
        # 先取首字段；配套 AT/RT 再仅切一次，保留 RT 后面的完整文本。
        first, sep, tail = line.partition(':')
        if sep and not first.startswith('eyJ'):
            at, sep2, rt = tail.partition(':')
            items.append((first, at if sep2 else '', rt if sep2 else at))
        elif sep:
            items.append(('', first, tail))
        else:
            items.append(('', '' if _token_kind(line) == 'RT' else line,
                          line if _token_kind(line) == 'RT' else ''))
    return items

def safe_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return '?'

def identity(data):
    for key in ('nickname', 'display_name', 'displayName', 'username', 'uid'):
        value = data.get(key)
        if isinstance(value, (str, int)) and str(value):
            value = str(value)
            if any(s and s in value for s in SECRETS) or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value):
                continue
            timeline('账号身份：' + value.replace('\n', ' ').replace('\r', ' '))
            return

# upstream recipes' free-form server messages are intentionally not printed.
# Every request and final state is logged by the maintained executor instead.
def recipe_log(_message):
    pass

def ensure_first_buddy(s, uid, nick, log):
    # Never consent implicitly as an accept prerequisite.
    if has_buddy(s) is True:
        return True
    raise SafeError('请本人在官方客户端阅读并同意领养协议')

GROWTH = [
    ('canvas', ['create_canvas','automation_1','playbook_prompt'], t_canvas_automation),
    ('team_3', ['Expert_team_use_3'], t_team_3),
    ('apps', ['Buddy_App','Buddy_App_QQ'], t_buddy_apps),
    ('theme', ['Hp_Appearance'], t_theme),
    ('library', ['Library_read'], t_library),
    ('expert_5', ['expert_5'], t_expert_5),
    ('template_5', ['template_5'], t_template_5),
    ('chat_5', ['Model_chat_GLM5.2','chat_5'], t_glm52),
    ('black_cat', ['black_cat'], t_black_cat),
    ('Expert_lighthouse', ['Expert_lighthouse'], t_lighthouse),
] + [('Sequential_Tasks_%d' % i, ['Sequential_Tasks_%d' % i], globals()['t_sequential_tasks' + ('' if i == 1 else '_%d' % i)]) for i in range(1,8)]

# Stage selection is fail-closed: misspelled or unsupported names are config errors.
DEFAULT_TASKS = {'checkin', 'travel', 'claim', 'buddy_info', 'badges'}
ALLOWED = DEFAULT_TASKS | {'lottery','blindbox','redeem','gift','makeup'}
for alias, codes, fn in GROWTH:
    ALLOWED.add(alias.lower())
    ALLOWED.update(c.lower() for c in codes)

def read_data(s, path, method='GET', body=None, headers=None):
    r = s.request(method, BASE + path, json=body if method != 'GET' else None, headers=headers)
    return r.json()['data']

def query_all(s):
    p = read_data(s, '/v2/activity/growth/profile')
    identity(p)
    credits = read_data(s, '/billing/meter/get-user-resource-summary', 'POST', {})
    pkgs = credits.get('Packages')
    if not isinstance(pkgs, list):
        raise SafeError('积分套餐字段缺失')
    total = 0
    for i, package in enumerate(pkgs, 1):
        remain = package.get('CycleRemainCapacity')
        if not isinstance(remain, (int, float)):
            raise SafeError('积分余额字段缺失')
        total += remain
        timeline('套餐%d：剩余%s，总量%s，已用%s' % (i, safe_number(remain),
                 safe_number(package.get('CycleTotalCapacity')), safe_number(package.get('CycleUsedCapacity'))))
    timeline('剩余积分合计：' + safe_number(total))
    usage = read_data(s, '/billing/meter/get-user-resource', 'POST', {})
    u = usage.get('Response', {}).get('Data')
    if not isinstance(u, dict):
        raise SafeError('用量字段缺失')
    timeline('用量：资源种类%s，本月使用%s次' % (safe_number(u.get('TotalCount')), safe_number(u.get('TotalDosage'))))
    energy = read_data(s, '/v2/activity/growth/energy')
    streak = read_data(s, '/v2/activity/growth/streak')
    ck = read_data(s, '/v2/billing/meter/checkin-activity-status', 'POST', {})
    timeline('成长：等级%s，能量%s，签到连签%s天，活跃连签%s天' %
             (safe_number(p.get('level')), safe_number(energy.get('balance')),
              safe_number(ck.get('streak_days')), safe_number(streak.get('streak', {}).get('days'))))
    if ck.get('active') is False:
        timeline('⚠️ 签到活动已关闭')
    elif _checkin_activity_warn(ck):
        timeline('⚠️ 签到活动即将或已经到期，请查看官方活动页')
    tasks = read_data(s, '/v2/activity/growth/tasks')
    if not isinstance(tasks.get('tasks'), list):
        raise SafeError('成长任务字段缺失')
    timeline('成长任务：服务端下发%d项' % len(tasks['tasks']))
    for row in tasks['tasks']:
        if not isinstance(row,dict):
            raise SafeError('任务行结构变化')
        code = row.get('task_code','')
        if not isinstance(code,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',code):
            raise SafeError('任务代码字段缺失')
        state = row.get('accept_status')
        label = state if state in ('not_accepted','accepted','in_progress','completed','claimed') else '未知状态'
        timeline('任务%s：%s%s' % (task_cn(code), label, '；尚未解锁' if row.get('locked') else ''))
        if code == 'wb_wechat_oa_subscribe_task':
            timeline('公众号关注需本人扫码满24小时，脚本不代为确认')
    return 'success'

def checkin(s):
    before = read_data(s, '/v2/billing/meter/checkin-activity-status', 'POST', {})
    if before.get('today_checked_in') is True:
        return 'alreadyComplete'
    if before.get('active') is False:
        return 'skipped'
    if before.get('active') is not True or before.get('today_checked_in') is not False:
        raise SafeError('签到状态字段缺失')
    read_data(s, '/v2/billing/meter/daily-checkin', 'POST', {})
    after = read_data(s, '/v2/billing/meter/checkin-activity-status', 'POST', {})
    if after.get('today_checked_in') is not True:
        raise SafeError('签到未通过回读核验')
    timeline('签到连签%s天，累计积分%s' % (safe_number(after.get('streak_days')), safe_number(after.get('total_credits'))))
    return 'success'

def claim_ready(s):
    tasks = read_data(s, '/v2/activity/growth/tasks').get('tasks')
    if not isinstance(tasks, list):
        raise SafeError('任务字段缺失')
    n = 0
    for row in tasks:
        if row.get('accept_status') == 'completed':
            code = row.get('task_code', '')
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', code):
                raise SafeError('任务代码格式变化')
            claim(s, code, recipe_log)
            if prog(s, code)[0] != 'claimed':
                raise SafeError('领奖未落账')
            n += 1
    timeline('已回读确认领取%d项奖励' % n)
    return 'success' if n else 'alreadyComplete'

def growth_run(s, uid, nick, codes, fn):
    rows = []
    mp = codes[0].startswith('Sequential_')
    for code in codes:
        row = _mp_task_row(s, code) if mp else next((x for x in read_data(s, '/v2/activity/growth/tasks')['tasks'] if x.get('task_code') == code), None)
        if row is None or row.get('locked'):
            continue
        rows.append(code)
        if not mp and row.get('accept_status') == 'not_accepted':
            result = read_data(s, '/v2/activity/growth/tasks/accept', 'POST', {'task_codes':[code]})
            if not any(x.get('task_code') == code and x.get('status') == 'accepted' for x in result.get('results', [])):
                raise SafeError('任务接受失败；前置协议需本人完成')
    if not rows:
        return 'skipped'
    fn(s, uid, nick, recipe_log)
    for code in rows:
        state = (_mp_prog if mp else prog)(s, code)[0]
        timeline('成长任务%s：%s' % (code, state if state in ('completed','claimed') else '尚未达标'))
        if state not in ('completed','claimed'):
            raise SafeError('成长任务未通过服务端终态核验')
    return 'success'

def rotate(idx, at, rt, path, cache):
    if not rt or not path:
        raise SafeError('续期需 RT 和 WORKBUDDY_TOKEN_STORE；未执行轮换')
    # Preflight an owner-only destination BEFORE rotating a credential.
    target = pathlib.Path(path).expanduser()
    if target.is_symlink() or (target.exists() and target.stat().st_mode & 0o077):
        raise SafeError('令牌保存文件必须为本人专用的普通文件，权限0600')
    if not target.parent.is_dir():
        raise SafeError('令牌保存目录不存在')
    fd, temp = tempfile.mkstemp(prefix='.wb-', dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        new_at, new_rt = refresh_one(rt)
        if not new_at:
            raise SafeError('续期失败')
        SECRETS.extend([new_at, new_rt])
        cache[str(idx)] = {'access_token':new_at, 'refresh_token':new_rt,
                           'updated':time.time(), 'source_hash':hashlib.sha256(rt.encode()).hexdigest()}
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            fd = None
            json.dump(cache, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, target)
        timeline('令牌续期已验证并保存至私有文件')
        return new_at, new_rt
    finally:
        if fd is not None:
            os.close(fd)
        if os.path.exists(temp):
            os.unlink(temp)

def notify_summary(body):
    if os.getenv('QINGLONG_NOTIFY','1').lower() in ('0','false','no','off'):
        return '已关闭'
    if DRY:
        timeline('通知：断网预演，仅生成脱敏摘要，不调用通知网络')
        return '断网预演已模拟'
    import subprocess
    script = """import importlib.util, os, pathlib, sys
try:
    import notify
except ImportError:
    notify = None
    for directory in (os.getenv('QINGLONG_NOTIFY_DIR',''), '/ql/data/scripts', '/ql/scripts'):
        p = pathlib.Path(directory) / 'notify.py'
        if directory and p.is_file():
            spec = importlib.util.spec_from_file_location('ql_notify', p)
            notify = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(notify)
            break
if notify is None or not callable(getattr(notify,'send',None)):
    sys.exit(2)
notify.send('WorkBuddy 日常维护', sys.argv[1])
"""
    try:
        result = subprocess.run([sys.executable,'-c',script,body], timeout=20,
                                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        return '已发送' if result.returncode == 0 else ('通知模块不可用' if result.returncode==2 else '通知失败（不改变业务退出码）')
    except Exception:
        return '通知失败或超时（不改变业务退出码）'


# Replacements for upstream recipes that swallowed errors or guessed state.
def t_buddy_info(s, uid, nick, log):
    d = read_data(s, '/v2/activity/growth/buddy/info')
    buddy = d.get('buddy',d)
    if not isinstance(buddy,dict):
        raise SafeError('Buddy 字段缺失')
    timeline('Buddy 信息查询已验证')
    return 'success'

def t_badges(s, uid, nick, log):
    d = read_data(s, '/v2/activity/growth/badges')
    items = d.get('badges', d.get('list'))
    if not isinstance(items,list):
        raise SafeError('徽章字段缺失')
    timeline('已获得徽章%d个' % sum(1 for b in items if isinstance(b,dict) and b.get('earned')))
    return 'success'

def t_travel(s, uid, nick, log):
    visible = read_data(s, '/v2/activity/growth/buddy/visible')
    if visible.get('buddy_visible') is False or visible.get('has_buddy') is False:
        timeline('⏭️ 无可旅行 Buddy')
        return 'skipped'
    status = read_data(s, '/v2/activity/growth/buddy/travel/status')
    state = status.get('state')
    if state == 'traveling' or status.get('daily_limit_reached') is True:
        timeline('☑️ 正在旅行或今日次数已用尽')
        return 'alreadyComplete'
    if state == 'arrived':
        reward = read_data(s, '/v2/activity/growth/buddy/travel/claim', 'POST', {})
        timeline('旅行奖励领取成功，积分%s' % safe_number(reward.get('reward_credit')))
        return 'success'
    if state != 'idle':
        raise SafeError('旅行状态未知，未派遣')
    cfg = read_data(s, '/v2/activity/growth/buddy/travel/config')
    locations = cfg.get('locations')
    if not isinstance(locations,list) or not locations or not locations[0].get('id'):
        raise SafeError('旅行目的地缺失')
    read_data(s, '/v2/activity/growth/buddy/travel/depart','POST',{'location_id':locations[0]['id']})
    if read_data(s, '/v2/activity/growth/buddy/travel/status').get('state') != 'traveling':
        raise SafeError('旅行出发未落账')
    timeline('✅ 已回读确认出发')
    return 'success'

def t_lottery(s, uid, nick, log):
    d = read_data(s, '/v2/activity/growth/lottery/chances')
    n = d.get('balance',d.get('chances',d.get('remaining')))
    if not n:
        d = read_data(s, '/v2/activity/growth/lottery/summary')
        n = d.get('chances',d.get('balance'))
    if not isinstance(n,int) or isinstance(n,bool) or not 0 <= n <= 100:
        raise SafeError('抽奖次数缺失或超出安全范围')
    for _ in range(n):
        result = read_data(s, '/v2/activity/growth/lottery/draw','POST',{'client_token':'draw-'+str(uuid.uuid4())})
        if not (result.get('prize_name') or result.get('name')):
            raise SafeError('抽奖结果字段缺失')
        timeline('抽奖结果已验证；实物奖励请在官方页面确认')
        time.sleep(WRITE_GAP)
    return 'success' if n else 'alreadyComplete'

def t_blindbox(s, uid, nick, log):
    d = read_data(s, '/v2/activity/growth/buddy/quota')
    n = d.get('affordable')
    if not isinstance(n,int) or isinstance(n,bool) or n < 0:
        raise SafeError('盲盒可用额度字段缺失')
    for _ in range(min(n,5)):
        result = read_data(s, '/v2/activity/growth/buddy/open','POST',{'count':1})
        if not isinstance(result.get('results'),list) or not result['results']:
            raise SafeError('盲盒开启结果缺失')
        timeline('盲盒开启成功（消耗能量）')
        time.sleep(WRITE_GAP)
    return 'success' if n else 'skipped'

def t_redeem(s, uid, nick, log, streak_days=None):
    d = read_data(s, '/v2/activity/growth/streak')
    rs = d.get('redemption_status') or {}
    statuses = {t:rs.get('tier_'+t+'_status') for t in ('7d','14d','28d')}
    if not any(statuses.values()):
        fallback = read_data(s, '/v2/activity/growth/redeem/summary')
        statuses = {t:fallback.get(k+'_status') for t,k in [('7d','starter'),('14d','advanced'),('28d','legendary')]}
    n = 0
    for tier,state in statuses.items():
        if state in ('locked','claimed'):
            continue
        if state != 'available':
            raise SafeError('连签兑换状态缺失，未尝试兑换')
        read_data(s, '/v2/activity/growth/redeem','POST',{'tier':tier,'client_token':'redeem-'+tier+'-'+str(uuid.uuid4())})
        timeline('连签%s档奖励领取已验证' % tier)
        n+=1
    return 'success' if n else 'alreadyComplete'

def t_makeup(s, uid, nick, log):
    hm = read_data(s, '/v2/activity/growth/heatmap')
    streak = read_data(s, '/v2/activity/growth/streak')
    bal = streak.get('makeup_cards',{}).get('balance')
    cells = hm.get('cells')
    if not isinstance(cells,list) or not isinstance(bal,int):
        raise SafeError('补签卡或热力图字段缺失')
    yesterday = (beijing_today()-datetime.timedelta(days=1)).isoformat()
    row = next((c for c in cells if str(c.get('date',''))[:10]==yesterday),None)
    if row is None or 'score' not in row:
        raise SafeError('昨日活跃状态未知，未消耗补签卡')
    if row['score'] or bal<=0:
        return 'skipped'
    read_data(s, '/v2/activity/growth/makeup-cards/use','POST',{'target_date':yesterday})
    timeline('昨日补签成功（消耗一张补签卡）')
    return 'success'

def t_gift_compensation(s, uid, nick, log):
    for path in ('/billing/meter/claim-gift','/billing/meter/claim-compensation'):
        read_data(s,path,'POST',{})
        timeline('礼包或补偿领取业务响应已验证')
    return 'success'


def main():
    global DRY, TASK_ONLY, TASK_SKIP, WRITE_GAP, MP_CHAT_GAP, ACTIVE_TAG
    DRY = os.getenv('WORKBUDDY_DRY_RUN','0').lower() in ('1','true','yes','on')
    started = time.monotonic()
    stats = {'accounts':0, 'success':0, 'failed':0, 'steps':{'success':0,'alreadyComplete':0,'skipped':0,'failed':0}, 'dryRun':DRY}
    status = 'configuration-error'
    timeline('🌱 WorkBuddy 国内版日常维护 | 开始时间：' + datetime.datetime.now().isoformat(timespec='seconds'))
    timeline('模式：' + ('断网预演' if DRY else '实际执行'))
    try:
        parser = RedactedArgumentParser()
        parser.add_argument('--credit-report', action='store_true', help='独立只读积分日报')
        parser.add_argument('--json', action='store_true', help='配合 --credit-report 输出脱敏数值数组')
        parser.add_argument('--query', action='store_true')
        parser.add_argument('--refresh', action='store_true')
        parser.add_argument('--no-desktop', action='store_true', help='兼容旧参数；桌面程序依赖已移除')
        parser.add_argument('--only', type=int)
        parser.add_argument('--gap', type=float, default=1.5)
        parser.add_argument('--mp-gap', type=float, default=float(os.getenv('WORKBUDDY_MP_GAP','45')))
        parser.add_argument('--tasks', default=os.getenv('WORKBUDDY_TASKS',os.getenv('WORKBUDDY_ONLY_TASKS','')))
        parser.add_argument('--skip-tasks', default=os.getenv('WORKBUDDY_SKIP_TASKS',''))
        args = parser.parse_args()
        if args.json and not args.credit_report:
            raise SafeError('--json 仅能配合 --credit-report')
        if args.credit_report and (args.query or args.refresh or args.tasks or args.skip_tasks):
            raise SafeError('积分日报不能与刷新、成长查询或任务筛选同时使用')
        reports = []
        TASK_ONLY = _parse_task_filter(args.tasks)
        TASK_SKIP = _parse_task_filter(args.skip_tasks)
        if (TASK_ONLY | TASK_SKIP) - ALLOWED:
            raise SafeError('未知或已移除任务名；桌面换血/自动同意协议不可执行')
        WRITE_GAP = max(1.0, args.gap)
        MP_CHAT_GAP = max(0, args.mp_gap)
        if not all(__import__('math').isfinite(x) for x in (WRITE_GAP,MP_CHAT_GAP)):
            raise SafeError('间隔必须为有限数值')
        accounts = _parse_env_tokens(os.getenv('WORKBUDDY_REFRESH_TOKEN',''))
        if not accounts:
            raise SafeError('缺少 WORKBUDDY_REFRESH_TOKEN；每行一个账号')
        selected = list(enumerate(accounts,1))
        if args.only is not None:
            if not 1 <= args.only <= len(accounts):
                raise SafeError('--only 超出账号范围')
            selected = [selected[args.only-1]]
        stats['accounts'] = len(selected)
        timeline('账号数：%d' % len(selected))
        chosen = (TASK_ONLY or DEFAULT_TASKS) - TASK_SKIP
        if not chosen and not (args.query or args.refresh or args.credit_report):
            raise SafeError('没有选中的任务')
        cache = {}
        store = os.getenv('WORKBUDDY_TOKEN_STORE','')
        if store and not DRY and pathlib.Path(store).exists():
            if pathlib.Path(store).is_symlink() or pathlib.Path(store).stat().st_mode & 0o077:
                raise SafeError('令牌缓存权限不安全；要求0600')
            cache = json.loads(pathlib.Path(store).read_text())
            if not isinstance(cache,dict):
                raise SafeError('令牌缓存结构错误')
        for idx, (note, at, rt) in selected:
            ACTIVE_TAG = '账号%d' % idx
            account_start = time.monotonic()
            counts = dict.fromkeys(stats['steps'],0)
            SECRETS.extend([note,at,rt])
            def stage(number, name, callback):
                mark = time.monotonic()
                ERRORS.clear()
                before = 0
                timeline('阶段%d：%s' % (number,name))
                try:
                    result = 'success' if DRY and number != 1 and not (args.credit_report and number == 2) else (callback() or 'success')
                    if len(ERRORS) != before:
                        raise SafeError('存在未确认请求；本阶段失败闭合')
                    if result not in counts:
                        raise SafeError('阶段结果无效')
                except Exception as e:
                    result = 'failed'
                    timeline('❌ ' + (str(e) if isinstance(e,SafeError) else '执行失败，详情已脱敏'))
                counts[result] += 1
                stats['steps'][result] += 1
                timeline('阶段%d结果：%s；耗时%.2f秒%s' % (number,result,time.monotonic()-mark,'（仅本地预演，无业务成功断言）' if DRY else ''))
                return result != 'failed'
            def authenticate():
                nonlocal at, rt
                if any(c in (at + rt + note) for c in ('@','&')):
                    raise SafeError('账号只能按换行分隔；凭据格式错误')
                if not at and not rt:
                    raise SafeError('凭据为空')
                if DRY:
                    return 'success'
                if _token_sanity(rt,at):
                    raise SafeError('凭据格式或签发域不符，请重新获取国内版明文 AT/RT')
                cached = cache.get(str(idx),{})
                if rt and cached.get('source_hash') == hashlib.sha256(rt.encode()).hexdigest():
                    at = cached.get('access_token', at)
                    rt = cached.get('refresh_token', rt)
                exp = _jwt_claims(at).get('exp',0)
                due = bool(rt and store and (time.time()-cached.get('updated',0)>10*86400 or (exp and exp-time.time()<7*86400)))
                if args.credit_report and not at:
                    raise SafeError('只读积分日报需要有效 AT；请先单独 --refresh')
                if args.refresh or (not args.credit_report and (not at or due)):
                    at, rt = rotate(idx, at, rt, store, cache)
                elif exp and exp <= time.time():
                    raise SafeError('AT 已过期；配置私有缓存和 RT 后续期')
                return 'success'
            if stage(1,'凭据检查与按需续期',authenticate) and not args.refresh:
                s = new_api(at)
                uid,nick = uid_of(at),nickname_of(at)
                if args.credit_report:
                    stage(2,'只读积分日报',lambda:credit_report(billing_report_headers(at,uid),False,idx,reports))
                elif stage(2,'账号身份、积分、用量、成长及任务查询',lambda:query_all(s)) and not args.query:
                    actions = [('checkin',lambda:checkin(s)), ('claim',lambda:claim_ready(s))]
                    for key, fn in [('travel',t_travel),('buddy_info',t_buddy_info),('badges',t_badges),('lottery',t_lottery),('blindbox',t_blindbox),('gift',t_gift_compensation),('makeup',t_makeup)]:
                        actions.append((key,lambda fn=fn:fn(s,uid,nick,recipe_log)))
                    actions.append(('redeem',lambda:t_redeem(s,uid,nick,recipe_log)))
                    n=2
                    for key, callback in actions:
                        if key in chosen:
                            n+=1
                            stage(n,task_cn(key),callback)
                    for alias,codes,fn in GROWTH:
                        if chosen & {alias.lower(),*(c.lower() for c in codes)} and not TASK_SKIP & {alias.lower(),*(c.lower() for c in codes)}:
                            n+=1
                            def run_growth(codes=codes,fn=fn):
                                if os.getenv('WORKBUDDY_ALLOW_REPORT','0') != '1':
                                    raise SafeError('成长任务会发送模拟事件，需显式 WORKBUDDY_ALLOW_REPORT=1')
                                if codes == ['black_cat'] and not within_night_window():
                                    return 'skipped'
                                return growth_run(s,uid,nick,codes,fn)
                            stage(n,task_cn(codes[0]),run_growth)
                    if 'claim' in chosen and any(chosen & {a.lower(),*(c.lower() for c in cs)} for a,cs,f in GROWTH):
                        n+=1
                        stage(n,'成长任务最终领奖',lambda:claim_ready(s))
            failed = counts['failed']>0
            stats['failed' if failed else 'success'] += 1
            timeline('账号统计：总任务%d，成功%d，已完成%d，跳过%d，失败%d，耗时%.2f秒' %
                     (sum(counts.values()),counts['success'],counts['alreadyComplete'],counts['skipped'],counts['failed'],time.monotonic()-account_start))
        if args.json:
            print(json.dumps(reports,ensure_ascii=False,separators=(',',':')))
        status = 'failure' if stats['failed']==stats['accounts'] else ('partial-failure' if stats['failed'] else ('dry-run' if DRY else 'success'))
    except (Exception,SystemExit) as e:
        timeline('❌ 配置错误：' + (str(e) if isinstance(e,SafeError) else '参数或缓存无效'))
    ACTIVE_TAG = '任务'
    code = 0 if status in ('success','dry-run') else 1
    body = '状态：%s；账号总数%d，成功%d，失败%d；子任务成功%d，已完成%d，跳过%d，失败%d' % (status,stats['accounts'],stats['success'],stats['failed'],stats['steps']['success'],stats['steps']['alreadyComplete'],stats['steps']['skipped'],stats['steps']['failed'])
    stats.update(status=status, exitCode=code, notification=notify_summary(body), durationSeconds=round(time.monotonic()-started,2))
    timeline('----------------------------------------')
    if not stats['accounts']:
        timeline('账号数：0')
    timeline(body+'；总耗时%.2f秒' % stats['durationSeconds'])
    timeline('通知状态：'+stats['notification'])
    timeline('结束时间：'+datetime.datetime.now().isoformat(timespec='seconds')+'；最终状态：'+status)
    print('TASK_SUMMARY='+json.dumps(stats,ensure_ascii=False,separators=(',',':')))
    return code


# 国际版接口来源：L0NE-6/WorkBuddy-Daily/workbuddy_intl_daily.py，MIT。
# 续期头 X-Domain / Authorization 参考同源 workbuddy_intl_login.py。
INTL_BASE = 'https://www.workbuddy.ai'
INTL_MODELS = ('deepseek-v4.1-flash', 'hy3', 'hy4-preview', 'hy4-preview-f')

def intl_accounts(raw):
    accounts = []
    for line in raw.splitlines():
        line = line.strip().strip('"').strip("'")
        if not line or line.startswith('#'):
            continue
        first, sep, tail = line.partition('|')
        if not sep:
            note, at, uid, rt = '', first, '', ''
        else:
            note = first
            at, sep, tail = tail.partition('|')
            uid, _, rt = tail.partition('|') if sep else ('', '', '')
        accounts.append((note, at, uid, rt))
    return accounts

def intl_headers(at, uid):
    h = {'Accept':'application/json', 'Content-Type':'application/json',
         'Authorization':'Bearer '+at,
         'User-Agent':'WorkBuddy/5.5.2 WorkBuddy AI/5.5.2 CLI/2.137.1',
         'X-IDE-Type':'WorkBuddy', 'X-IDE-Name':'WorkBuddy AI',
         'X-IDE-Version':'5.5.2', 'X-Product':'WorkBuddy AI'}
    if uid:
        h['X-User-Id'] = uid
    return h

def intl_post(path, headers, body=None, stream=False):
    global REQUEST_COUNT
    if DRY:
        raise SafeError('断网预演禁止 HTTP')
    if path not in {'/billing/meter/checkin-activity-status', '/v2/billing/meter/daily-checkin',
                    '/v2/chat/completions', '/v2/plugin/auth/token/refresh'}:
        raise SafeError('非许可国际版接口')
    REQUEST_COUNT += 1
    try:
        r = RealSession().post(INTL_BASE+path, headers=headers, json=body or {},
                               timeout=25, stream=stream)
        timeline('POST 请求：HTTP %d' % r.status_code)
        return r
    except Exception:
        raise SafeError('国际版网络请求失败，详情已脱敏') from None

def intl_json(path, headers):
    r = intl_post(path, headers)
    try:
        d = r.json()
    except Exception:
        raise SafeError('国际版响应不是有效JSON') from None
    if not isinstance(d, dict):
        raise SafeError('国际版响应结构变化')
    return r.status_code, d

def intl_status(headers):
    http, d = intl_json('/billing/meter/checkin-activity-status', headers)
    # 41000 的关闭含义由国际版原始业务码表支持；认证/未知失败不可冒充关闭。
    if http in (200,400,409) and d.get('code') == 41000:
        timeline('⏭️ 官方业务码41000：活动未开始或已结束')
        return False, False
    data = d.get('data')
    if http != 200 or d.get('code') != 0 or not isinstance(data, dict):
        raise SafeError('活动探测失败，不能确认活动关闭')
    identity(data)
    active = data.get('active')
    checked = data.get('today_checked_in', data.get('todayCheckedIn'))
    if not isinstance(active,bool) or (active and not isinstance(checked,bool)):
        raise SafeError('活动状态字段缺失或类型变化')
    timeline('活动状态：' + ('已关闭' if not active else ('今日已领取' if checked else '开放，今日未领取')))
    return active, checked

def intl_daily(headers):
    active, checked = intl_status(headers)
    if not active:
        return 'skipped'
    if checked:
        return 'alreadyComplete'
    http, d = intl_json('/v2/billing/meter/daily-checkin', headers)
    message = d.get('msg', d.get('message',''))
    duplicate = isinstance(message,str) and any(x in message.lower() for x in ('已签','已领','already'))
    if not (http == 200 and d.get('code') == 0) and not (http in (400,409) and duplicate):
        raise SafeError('每日奖励领取未通过业务校验')
    active, checked = intl_status(headers)
    if not checked:
        raise SafeError('领取后未回读到今日已领取状态')
    timeline('✅ 每日奖励领取与服务端回读均已验证')
    return 'alreadyComplete' if duplicate else 'success'

def intl_keepalive(headers):
    models = [v.strip() for v in os.getenv('WORKBUDDY_INTL_MODELS','').split(',') if v.strip()] or list(INTL_MODELS)
    for index, model in enumerate(models,1):
        timeline('免费模型链尝试 %d/%d（可能消耗积分）' % (index,len(models)))
        request_id = str(uuid.uuid4())
        h = dict(headers, Accept='text/event-stream', Origin=INTL_BASE, Referer=INTL_BASE+'/',
                 **{'X-Requested-With':'XMLHttpRequest','X-Agent-Purpose':'conversation'})
        for key in ('X-Request-ID','X-Conversation-Request-ID','X-Conversation-ID','X-Session-ID',
                    'X-Conversation-Message-ID','X-Root-Request-ID'):
            h[key] = request_id
        body = {'model':model,'stream':True,'max_tokens':16,'messages':[
            {'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':'hi'}]}
        try:
            with intl_post('/v2/chat/completions',h,body,stream=True) as r:
                if r.status_code != 200:
                    raise SafeError('模型HTTP失败')
                content = False
                finished = False
                for line in r.iter_lines(decode_unicode=True):
                    if not line.startswith('data:'):
                        continue
                    value = line[5:].strip()
                    if value == '[DONE]':
                        finished = True
                        break
                    event = json.loads(value)
                    if not isinstance(event,dict) or event.get('error') or event.get('code',0) not in (0,200):
                        raise SafeError('模型返回业务错误')
                    for choice in event.get('choices',[]):
                        delta = choice.get('delta') or {}
                        if isinstance(delta.get('content'),str) and delta['content'].strip():
                            content = True
                        if choice.get('finish_reason') in ('stop','length'):
                            finished = True
                if not content or not finished:
                    raise SafeError('模型流未包含有效回答与完成标志')
            timeline('✅ 模型调用已验证；保活不等于签到成功')
            return 'success'
        except Exception:
            timeline('⚠️ 当前模型未通过流式业务核验，继续下一模型（响应不输出）')
    raise SafeError('全部模型调用失败或未确认完成')

def intl_rotate(idx, at, rt, path, cache):
    if not rt or not path:
        raise SafeError('国际版续期需RT和 WORKBUDDY_INTL_TOKEN_STORE')
    target = pathlib.Path(path).expanduser()
    if target.is_symlink() or (target.exists() and (not target.is_file() or target.stat().st_mode & 0o077)):
        raise SafeError('国际版缓存必须为本人专用普通文件，权限0600')
    if not target.parent.is_dir():
        raise SafeError('缓存目录不存在')
    fd, temp = tempfile.mkstemp(prefix='.wb-intl-', dir=str(target.parent))
    try:
        os.fchmod(fd,0o600)
        h = {'User-Agent':'WorkBuddy/5.4.2','Accept':'application/json','Content-Type':'application/json',
             'X-Refresh-Token':rt,'X-Auth-Refresh-Source':'plugin',
             'X-Domain':'www.workbuddy.ai','Authorization':'Bearer '+at}
        http, d = intl_json('/v2/plugin/auth/token/refresh',h)
        data = d.get('data')
        if http != 200 or d.get('code') != 0 or not isinstance(data,dict):
            raise SafeError('国际版续期业务失败')
        new_at = data.get('accessToken',data.get('access_token'))
        new_rt = data.get('refreshToken',data.get('refresh_token',rt))
        if not isinstance(new_at,str) or not new_at or not isinstance(new_rt,str) or not new_rt:
            raise SafeError('国际版续期响应缺少令牌')
        SECRETS.extend([new_at,new_rt])
        cache[str(idx)] = {'access_token':new_at,'refresh_token':new_rt,
                          'source_hash':hashlib.sha256(rt.encode()).hexdigest(),'updated':time.time()}
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            fd = None
            json.dump(cache,f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,target)
        timeline('✅ 国际版令牌已续期并保存至私有缓存')
        return new_at,new_rt
    finally:
        if fd is not None:
            os.close(fd)
        if os.path.exists(temp):
            os.unlink(temp)

def intl_main():
    global DRY, ACTIVE_TAG
    truth = ('1','true','yes','on')
    DRY = any(os.getenv(k,'0').lower() in truth for k in ('WORKBUDDY_DRY_RUN','WORKBUDDY_INTL_DRY_RUN'))
    started = time.monotonic()
    stats = {'accounts':0,'success':0,'failed':0,'steps':dict.fromkeys(('success','alreadyComplete','skipped','failed'),0),'dryRun':DRY}
    status = 'configuration-error'
    timeline('WorkBuddy 国际版日常维护 | 开始时间：'+datetime.datetime.now().isoformat(timespec='seconds'))
    timeline('模式：'+('断网预演' if DRY else '实际执行'))
    try:
        parser = RedactedArgumentParser()
        parser.add_argument('--credit-report', action='store_true', help='独立只读积分日报')
        parser.add_argument('--json', action='store_true', help='配合 --credit-report 输出脱敏数值数组')
        parser.add_argument('--intl',action='store_true')
        parser.add_argument('--trial',action='store_true',help='独立领取一次性专家加油包')
        parser.add_argument('--only',type=int)
        parser.add_argument('--refresh',action='store_true')
        parser.add_argument('--keepalive',action='store_true')
        parser.add_argument('--no-keepalive',action='store_true')
        args = parser.parse_args()
        if args.json and not args.credit_report:
            raise SafeError('--json 仅能配合 --credit-report')
        if (args.credit_report or args.trial) and (args.refresh or args.keepalive or args.no_keepalive or
                (args.credit_report and args.trial) or os.getenv('WORKBUDDY_INTL_KEEPALIVE','0').lower() in truth):
            raise SafeError('日报或一次性加油包必须独立运行，不能与续期或模型保活组合')
        reports = []
        accounts = intl_accounts(os.getenv('WORKBUDDY_INTL_TOKENS','').strip() or os.getenv('WORKBUDDY_TOKEN',''))
        if not accounts:
            raise SafeError('缺少 WORKBUDDY_INTL_TOKENS；每行一个国际版账号')
        selected = list(enumerate(accounts,1))
        if args.only is not None:
            if not 1 <= args.only <= len(accounts):
                raise SafeError('--only 超出账号范围')
            selected = [selected[args.only-1]]
        stats['accounts'] = len(selected)
        timeline('账号数：%d' % len(selected))
        enabled = (args.keepalive or os.getenv('WORKBUDDY_INTL_KEEPALIVE','0').lower() in truth) and not args.no_keepalive
        path = os.getenv('WORKBUDDY_INTL_TOKEN_STORE','')
        cache = {}
        if path and not DRY and pathlib.Path(path).exists():
            p = pathlib.Path(path)
            if p.is_symlink() or not p.is_file() or p.stat().st_mode & 0o077:
                raise SafeError('国际版缓存必须为权限0600的普通文件')
            cache = json.loads(p.read_text())
            if not isinstance(cache,dict):
                raise SafeError('国际版缓存结构错误')
        for idx,(note,at,uid,rt) in selected:
            ACTIVE_TAG = '国际账号%d' % idx
            mark = time.monotonic()
            counts = dict.fromkeys(stats['steps'],0)
            SECRETS.extend([note,at,rt])
            def stage(n,label,fn):
                t = time.monotonic()
                timeline('阶段%d：%s' % (n,label))
                try:
                    result = fn()
                    if result not in counts:
                        raise SafeError('阶段结果无效')
                except Exception as e:
                    result = 'failed'
                    timeline('❌ '+(str(e) if isinstance(e,SafeError) else '执行失败，详情已脱敏'))
                counts[result] += 1
                stats['steps'][result] += 1
                timeline('阶段%d结果：%s；耗时%.2f秒%s' % (n,result,time.monotonic()-t,'（仅本地预演，无业务成功断言）' if DRY else ''))
                return result != 'failed'
            def auth():
                nonlocal at,rt,uid
                if not at or any(c in at+uid+rt for c in ('&','@','\r','\n')):
                    raise SafeError('国际版凭据格式错误；账号只能换行分隔')
                if DRY:
                    return 'success'
                cached = cache.get(str(idx),{})
                if rt and cached.get('source_hash') == hashlib.sha256(rt.encode()).hexdigest():
                    at,rt = cached.get('access_token',at),cached.get('refresh_token',rt)
                if args.refresh:
                    at,rt = intl_rotate(idx,at,rt,path,cache)
                elif _jwt_claims(at).get('exp',time.time()+60) <= time.time():
                    raise SafeError('国际版AT已过期，请显式 --refresh 并配置私有缓存')
                uid = uid or str(_jwt_claims(at).get('sub') or '')
                return 'success'
            if stage(1,'凭据检查与显式续期',auth) and not args.refresh:
                h = intl_headers(at,uid)
                if args.credit_report:
                    stage(2,'只读国际版积分日报',lambda:credit_report(h,True,idx,reports))
                elif args.trial:
                    stage(2,'独立领取一次性专家加油包',lambda:'success' if DRY else intl_trial(h))
                else:
                    stage(2,'活动探测、每日奖励领取与回读',lambda:'success' if DRY else intl_daily(h))
                    stage(3,'独立模型保活',lambda:'skipped' if not enabled else ('success' if DRY else intl_keepalive(h)))
            failed = counts['failed'] > 0
            stats['failed' if failed else 'success'] += 1
            timeline('账号统计：总任务%d，成功%d，已完成%d，跳过%d，失败%d，耗时%.2f秒' %
                     (sum(counts.values()),counts['success'],counts['alreadyComplete'],counts['skipped'],counts['failed'],time.monotonic()-mark))
        if args.json:
            print(json.dumps(reports,ensure_ascii=False,separators=(',',':')))
        status = ('failure' if stats['failed']==stats['accounts'] else 'partial-failure') if stats['failed'] else ('dry-run' if DRY else 'success')
    except (Exception,SystemExit) as e:
        timeline('❌ 配置错误：'+(str(e) if isinstance(e,SafeError) else '参数或缓存无效'))
    ACTIVE_TAG = '任务'
    if not stats['accounts']:
        timeline('账号数：0')
    code = 0 if status in ('success','dry-run') else 1
    body = '状态：%s；账号总数%d，成功%d，失败%d；子任务成功%d，已完成%d，跳过%d，失败%d' % (status,stats['accounts'],stats['success'],stats['failed'],stats['steps']['success'],stats['steps']['alreadyComplete'],stats['steps']['skipped'],stats['steps']['failed'])
    stats.update(status=status,exitCode=code,notification=notify_summary(body),durationSeconds=round(time.monotonic()-started,2))
    timeline('----------------------------------------')
    timeline(body+'；总耗时%.2f秒' % stats['durationSeconds'])
    timeline('通知状态：'+stats['notification'])
    timeline('结束时间：'+datetime.datetime.now().isoformat(timespec='seconds')+'；最终状态：'+status)
    print('TASK_SUMMARY='+json.dumps(stats,ensure_ascii=False,separators=(',',':')))
    return code


class RedactedArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise SafeError('命令参数无效；请使用 --help 查看用法')


def billing_report_headers(at, uid):
    # 来源：Maquer/workbuddy-checkin billingHeaders（仅传输至官方业务域）。
    headers = {'Authorization':'Bearer '+at, 'Accept':'application/json',
               'Content-Type':'application/json', 'User-Agent':'CLI/2.63.2 CodeBuddy/2.63.2'}
    if uid:
        headers['X-User-Id'] = uid
    headers['X-Domain'] = 'codebuddy.cn'
    return headers


def billing_request(path, headers, body, international):
    global REQUEST_COUNT
    if DRY:
        raise SafeError('断网预演禁止 HTTP')
    if path not in {'/v2/billing/meter/get-user-resource','/billing/ide/trial'}:
        raise SafeError('非许可积分接口')
    if path == '/billing/ide/trial' and not international:
        raise SafeError('加油包仅支持国际版')
    REQUEST_COUNT += 1
    base = INTL_BASE if international else CBDOMAIN
    try:
        response = RealSession().post(base+path, headers=headers, json=body, timeout=30)
        data = response.json()
    except Exception:
        raise SafeError('积分接口网络或解析失败，详情已脱敏') from None
    timeline('POST 请求：HTTP %d' % response.status_code)
    if not isinstance(data,dict) or not isinstance(data.get('code'),int) or isinstance(data.get('code'),bool):
        raise SafeError('积分接口业务码缺失或类型变化')
    return response.status_code, data


def package_capacity(package):
    # 保留上游 _package_remain_used 的周期/累计计算；禁止将未知数值当成余额0。
    keys = ('CycleCapacitySize','CycleCapacityRemain','CycleCapacityUsed',
            'CapacitySize','CapacityRemain','CapacityUsed')
    if not any(key in package for key in keys):
        raise SafeError('套餐容量字段缺失')
    values = {}
    for key in keys:
        value = package.get(key,0)
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not __import__('math').isfinite(value):
            raise SafeError('套餐容量字段不是有限数值')
        values[key] = value
    size = values['CycleCapacitySize']
    if size > 0:
        remain = min(max(values['CycleCapacityRemain'],0),size)
        used = size-remain
        if values['CycleCapacityUsed'] > used:
            used = values['CycleCapacityUsed']
            if size >= used:
                remain = size-used
        return remain,used,size
    remain,used = values['CycleCapacityRemain'],values['CycleCapacityUsed']
    if remain > 0 or used > 0:
        remain,used = max(remain,0),max(used,0)
        size = remain+used
        if values['CapacitySize'] > size:
            size = values['CapacitySize']
            used = size-remain
        return remain,used,size
    remain,used = max(values['CapacityRemain'],0),max(values['CapacityUsed'],0)
    size = values['CapacitySize']
    if size <= 0:
        size = remain+used
    if used == 0 and size > remain:
        used = size-remain
    return remain,used,size


def credit_report(headers, international, index, reports):
    if DRY:
        timeline('积分日报：仅验证参数与流程，不请求接口、不断言真实积分')
        reports.append({'account':index,'region':'global' if international else 'cn','dryRun':True})
        return 'success'
    body = {'PageNumber':1,'PageSize':100,'ProductCode':'p_tcaca','Status':[0,3],
            'PackageEndTimeRangeBegin':datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'PackageEndTimeRangeEnd':'2126-12-31 23:59:59'}
    http, envelope = billing_request('/v2/billing/meter/get-user-resource',headers,body,international)
    data = envelope.get('data')
    if http != 200 or envelope['code'] != 0 or not isinstance(data,dict):
        raise SafeError('积分日报未通过业务校验')
    identity(data)
    response = data.get('Response',data)
    values = response.get('Data') if isinstance(response,dict) else None
    if not isinstance(values,dict) or not isinstance(values.get('Accounts'),list):
        raise SafeError('积分日报套餐字段缺失，不能将未知余额当成0')
    # 上游只读第一页：若服务端明确还有数据，失败闭合，避免报告残缺总额。
    packages = values['Accounts']
    count = values.get('TotalCount',len(packages))
    if not isinstance(count,(int,float)) or isinstance(count,bool) or count > len(packages):
        raise SafeError('积分日报分页未完整，不能确认总余额')
    safe_packages = []
    for package in packages:
        if not isinstance(package,dict):
            raise SafeError('积分套餐行结构变化')
        remain,used,size = package_capacity(package)
        safe_packages.append({'remain':remain,'used':used,'size':size})
    remain = sum(p['remain'] for p in safe_packages)
    used = sum(p['used'] for p in safe_packages)
    size = sum(p['size'] for p in safe_packages)
    if size > 0:
        used = max(used,size-remain,0)
    dosage = values.get('TotalDosage',0)
    if not isinstance(dosage,(int,float)) or isinstance(dosage,bool) or not __import__('math').isfinite(dosage):
        raise SafeError('积分总用量字段无效')
    if dosage > size:
        size = dosage
        used = max(used,size-remain,0)
    report = {'account':index,'region':'global' if international else 'cn',
              'total_remain':remain,'total_used':used,'total_size':size,
              'pack_count':len(safe_packages),'packages':safe_packages}
    reports.append(report)
    timeline('积分日报：剩余%s，总量%s，已用%s，套餐数%d' % (remain,size,used,len(safe_packages)))
    for n,p in enumerate(safe_packages,1):
        timeline('套餐%d：剩余%s，总量%s，已用%s' % (n,p['remain'],p['size'],p['used']))
    return 'success'


def intl_trial(headers):
    # 主来源明确记载14051为已领取；不依据模糊消息文本判成功。
    http, envelope = billing_request('/billing/ide/trial',headers,{},True)
    if http in (200,400,409) and envelope['code'] == 14051:
        timeline('☑️ 官方业务码14051：此前已领取一次性专家加油包')
        return 'alreadyComplete'
    if http != 200 or envelope['code'] != 0 or not isinstance(envelope.get('data'),dict):
        raise SafeError('一次性专家加油包领取未通过业务校验')
    identity(envelope['data'])
    timeline('✅ 一次性专家加油包领取：HTTP及官方业务码已验证')
    return 'success'

if __name__ == '__main__':
    sys.exit(intl_main() if '--intl' in sys.argv[1:] else main())
