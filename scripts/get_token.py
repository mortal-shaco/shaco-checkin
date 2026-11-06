#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: WorkBuddy 每日签到与成长中心
# cron: 51 0,4,8,12,16,20 * * *
"""WorkBuddy 独立维护版，Python 3.9+，仅使用标准库。

上游作者：88lin；https://github.com/88lin/workbuddy-auto-signin；协议：MIT。
来源：firlsy/ql_scripts-AI_auto_sign/get_token/signin.py。
保留上游署名与 MIT 授权；凭据导出及浏览器捕获工具不作为定时任务合并。

凭据：WORKBUDDY_ACCOUNTS 每个非空行是一个 JSON 对象，结构与客户端的
明文会话相同：auth.accessToken、account.uid 必填；account.enterpriseId、
auth.domain 可选。登录自己的 WorkBuddy 后，在开发者工具网络面板查看官方
签到请求的 Authorization（去掉 Bearer 前缀）、X-User-Id；若有租户/域请求头，
分别填入 enterpriseId/domain。不要提交、打印或分享这些内容。
新版客户端的加密字段不能直接当 Token；请取得自己有效的明文请求凭据。
兼容 WB_ACCESS_TOKEN（每行一个 Token），这种模式不要求 X-User-Id，依据关联
get_token.py 的 Bearer 接口契约；不读取本机私有文件或调用桌面应用。

命令：auto/silent/silent-poll/silent-growth 为签到+成长中心；growth 仅成长中心；
status 只读状态；claim 只领取签到；all 查询后领取；doctor 离线检查凭据。
silent 别名仍接受，青龙统一输出日志而不写本地签到日志。
每日 00:05 与每四小时轮询合并为上方 cron。签到和免费领奖默认开启；
WORKBUDDY_DEPART/MAKEUP/LOTTERY/BUDDY_OPEN=1 分别授权自动派遣、消耗补登卡、
抽奖次数和能量，均默认关闭。每轮最多补一天、抽一次；写操作不自动重试。
WORKBUDDY_DRY_RUN=1 完全断网（包括通知），不读取凭据文件、不调用通知模块。
WORKBUDDY_BUDGET_SECONDS 默认每账号 420 秒，轮询 180 秒，上限 540/240 秒。
QINGLONG_NOTIFY=auto/1/0；QINGLONG_NOTIFY_SCRIPTS 可按目录/文件名/标识匹配；
QINGLONG_NOTIFY_DIR 可指定通知模块目录。通知失败不改变业务退出码。
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
        _ql_notify_identities = ('51413af773dd1c9a', 'scripts/get_token.py', 'get_token.py', 'get_token')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime
from pathlib import Path

TITLE = "WorkBuddy 每日签到与成长中心"
CATALOG = "51413af773dd1c9a"
ENDPOINT = "https://copilot.tencent.com"
CODE_NO_NETWORK = -1
CODE_BUDGET_OUT = -2
MAKEUP_MAX_PER_RUN = 1
_started_at = None
_budget_seconds = 420
stats = None
secrets = set()


def flag(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def clean(value):
    text = str(value)
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"1[3-9]\d{9}", "[手机号已隐藏]", text)
    return text.replace("\n", " ").replace("\r", " ")


def log(message):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), clean(message)), flush=True)


def _budget_left():
    return _budget_seconds - (time.monotonic() - _started_at) if _started_at else _budget_seconds


def _auth_failure(code):
    return {"result": "AUTH_REJECTED" if code == 401 else "FORBIDDEN",
            "report": "认证或权限被拒绝，请检查登录态及活动条件", "http": code}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(url, headers, method="GET", payload=None):
    if flag("WORKBUDDY_DRY_RUN"):
        raise RuntimeError("预演禁止网络")
    path = urllib.parse.urlsplit(url)
    if path.scheme != "https" or path.netloc != "copilot.tencent.com":
        return 422, {"msg": "非官方接口已拒绝"}
    if _budget_left() <= 1:
        return CODE_BUDGET_OUT, {"error": "时间预算耗尽"}
    start = time.monotonic()
    stats["total"] += 1
    number = stats["total"]
    log("阶段 %d：%s %s 开始" % (number, method, path.path))
    req = urllib.request.Request(url, headers=headers, method=method,
        data=json.dumps(payload if payload is not None else {}).encode() if method == "POST" else None)
    try:
        opener = urllib.request.build_opener(NoRedirect())
        try:
            response = opener.open(req, timeout=min(30, _budget_left()))
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            code = response.code
            raw = response.read(1048577)
        if len(raw) > 1048576:
            raise ValueError()
        body = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(body, (dict, type(None))):
            raise ValueError()
        # Only known business states may keep their messages; never return raw error text.
        if isinstance(body, dict):
            msg = str(dig(body, "msg") or "")
            safe = "业务接口拒绝或响应格式变更"
            if "tier" in msg.lower() and any(x in msg.lower() for x in ("unknown", "unsupported", "invalid")):
                safe = "unknown tier"
            elif "天数不足" in msg:
                safe = "天数不足"
            elif _is_no_chance(msg):
                safe = "no chance"
            elif msg.strip().lower() == "date is not broken, no makeup needed":
                safe = msg.strip().lower()
            if "msg" in body:
                body["msg"] = safe
            bc = body.get("code")
            if 200 <= code < 300 and (bc is not None and (type(bc) is not int or bc != 0) or body.get("success") is False):
                code = 422
            if 200 <= code < 300 and not body:
                code = 422
            # Official non-secret identity fields, never infer identity from JWTs.
            for field in ("nickname", "username", "displayName", "uid"):
                identity = dig(body, field)
                if isinstance(identity, (str, int)) and str(identity):
                    log("官方账号 %s：%s" % (field, identity))
        required_fields = {
            "/buddy/travel/status": ("state",), "/buddy/travel/config": ("locations",),
            "/tasks": ("tasks",), "/streak": ("streak",), "/heatmap": ("cells", "today"),
            "/redeem/summary": ("starter_status", "advanced_status", "legendary_status"),
            "/lottery/chances": ("balance",), "/buddy/quota": ("affordable",),
            "/energy": ("balance",)}
        if 200 <= code < 300:
            for suffix, fields in required_fields.items():
                if path.path.endswith(suffix) and any(dig(body, field) is None for field in fields):
                    code = 422
            if method == "POST" and "/activity/growth/" in path.path:
                evidence = ("reward_credit", "location", "results", "credit", "energy", "already_claimed",
                            "makeup_cards", "credit_granted", "energy_granted", "cards_granted",
                            "chances_granted", "prize_name", "prize", "buddy", "buddies", "name")
                if not isinstance(body, dict) or not (type(body.get("code")) is int and body["code"] == 0 or body.get("success") is True or any(dig(body, key) is not None for key in evidence)):
                    code = 422
        if body is None and not (200 <= code < 300 and path.path.endswith("/daily-checkin")):
            code = 422
        success = 200 <= code < 300
        already = code == 400 and isinstance(body, dict) and body.get("code") == 10001 and path.path.endswith("/daily-checkin")
        normal_skip = (code == 403 and _is_tier_locked(code, body) and path.path.endswith("/redeem") or
                       path.path.endswith("/lottery/draw") and _is_no_chance(dig(body, "msg")) or
                       path.path.endswith("/makeup-cards/use") and dig(body, "msg") == "date is not broken, no makeup needed" or
                       path.path.endswith("/redeem") and _is_unknown_tier(code, body))
        stats["success" if success else "already" if already else "skipped" if normal_skip else "failed"] += 1
        log("阶段 %d：HTTP %s，%s，耗时 %.2f 秒" % (number, code, "业务响应通过" if success else "接口未通过", time.monotonic()-start))
        return code, body
    except Exception:
        stats["failed"] += 1
        log("阶段 %d：网络或响应解析失败，耗时 %.2f 秒" % (number, time.monotonic()-start))
        return CODE_NO_NETWORK, {"error": "网络或响应解析失败"}


def post(url, headers, payload=None, retry=False):
    return _request(url, headers, "POST", payload)


def get(url, headers):
    return _request(url, headers)


def _is_hard_failure(code):
    return not 200 <= code < 300


def _http_label(code):
    return "HTTP %s" % code


def _is_no_chance(msg):
    """抽奖失败是否只是"没有次数"——这是常态，不是故障。

    服务端对"次数为 0"返回 400 + `insufficient lottery chance balance`，和真正的
    参数错误（`invalid request`）同为 400，只看状态码会把两者混为一谈：把常态记成
    失败，轮询就会每轮强制落盘、还会把失败数算进汇报。
    """
    m = str(msg or "").lower()
    if not m:
        return False
    if "insufficient" in m or "not enough" in m:
        return "chance" in m or "balance" in m
    return "no chance" in m


def _is_unknown_tier(code, body):
    """连登兑换是否因为"tier 这个值本身不认识"被拒——用于判断要不要换一种写法重试。

    /redeem 的 tier 是**档位标识字符串**（"7d"/"14d"/"28d"），权威来源是
    GET /streak 的 redemption_status.tiers[].tier。接口哪天改回收天数，脚本就会
    三档全废且看不出原因，所以保留这条兜底：档位标识被判 unknown tier 时退回天数
    再试一次。这类 400 发生在参数校验阶段，服务端没兑换任何东西，重试不会重复领取；
    `invalid request` 这类业务拒绝不在此列，不能重试。

    历史教训：2026-09-11 曾据"传天数返回 invalid request"误判 tier 要收数字，
    导致兑换模块连坏三个版本——"业务拒绝"的错误文案不能反推参数格式正确，
    必须拿到一次成功响应才算验证过。
    """
    if code != 400:
        return False
    m = str(dig(body, "msg") or "").lower()
    return "tier" in m and ("unknown" in m or "unsupported" in m or "invalid" in m)


def _is_tier_locked(code, body):
    """未解锁档位：403 + 「连续登录天数不足」——这是常态，不是故障。

    不加这条的话，未解锁档位会被计进 failures，轮询每轮都判定"有失败"从而强制
    落盘，真正有价值的记录会被这类常态信息淹没。
    """
    if code != 403:
        return False
    m = str(dig(body, "msg") or "")
    return "天数不足" in m or "不足" in m


def dig(obj, key):
    """在可能被 data/result 包裹的响应里找字段，兼容信封结构。"""
    if isinstance(obj, dict):
        if key in obj and obj[key] is not None:
            return obj[key]
        for k in ("data", "result", "resp", "response"):
            if k in obj and isinstance(obj[k], dict):
                r = dig(obj[k], key)
                if r is not None:
                    return r
    return None


def _api_success(code, body):
    """补登相关接口同时检查 HTTP 状态和 JSON 业务码。"""
    business_code = body.get("code") if isinstance(body, dict) else None
    return 200 <= code < 300 and (
        business_code is None or (type(business_code) is int and business_code == 0))


def _makeup_candidates(streak_body, heatmap_body):
    """从日历选断登日期；makeup_dates 是已补登历史，不能作为待办清单。

    对齐官方成长中心：当月、今天之前、活动上线之后、score == 0。
    使用 heatmap.today 的服务端日期，避免本机时区把月初/午夜算错。
    日历缺项不推测为零；结构异常时整段停止，不能靠猜测消耗补登卡。
    """
    def parse_date(value):
        if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise ValueError("补登日期格式无效")
        return date.fromisoformat(value)

    today_obj = dig(heatmap_body, "today")
    if not isinstance(today_obj, dict):
        raise ValueError("活跃日历缺少服务端日期")
    today = parse_date(today_obj.get("date"))
    launch = parse_date(dig(streak_body, "launch_date"))
    start = max(today.replace(day=1), launch, date(2026, 6, 17))
    streak = dig(streak_body, "streak")
    if not isinstance(streak, dict):
        raise ValueError("连登状态格式无效")
    made_up = streak.get("makeup_dates", [])
    if not isinstance(made_up, list):
        raise ValueError("已补登记录格式无效")
    made_up = {parse_date(value) for value in made_up}
    cells = dig(heatmap_body, "cells")
    if not isinstance(cells, list):
        raise ValueError("活跃日历缺少日期列表")
    scores = {}
    for cell in cells:
        if not isinstance(cell, dict):
            raise ValueError("活跃日历记录格式无效")
        day = parse_date(cell.get("date"))
        score = cell.get("score")
        if type(score) not in (int, float) or not math.isfinite(score) or score < 0:
            raise ValueError("活跃日历分数无效")
        if day in scores and scores[day] != score:
            raise ValueError("活跃日历同一日期的记录冲突")
        scores[day] = score
    # 最近的断点优先，以便尽早恢复当前连登；每轮仍受 MAKEUP_MAX_PER_RUN 限制。
    return sorted((day.isoformat() for day, score in scores.items()
                   if start <= day < today and score == 0 and day not in made_up), reverse=True)


def fmt_credit(v):
    """积分显示用：能转 int 就转，否则原样返回（OverflowError 同理，见 as_int）。"""
    try:
        return int(v)
    except (TypeError, ValueError, OverflowError):
        return v


def as_int(v, default=0):
    """把可能为字符串的数字安全地转成 int，避免与数值比较/累加时抛异常。

    OverflowError 必须一并捕获：json.loads 默认接受 Infinity，服务端返回该字面量时
    v 已经是 float('inf')，int(v) 抛的是 OverflowError 而非 ValueError。
    """
    try:
        return int(v)
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        return int(float(v))  # 兼容 "1.5"/"1e3" 这类数字串，宁可截断也不把真实数值丢成 0
    except (TypeError, ValueError, OverflowError):
        return default


def _first_int(body, key, fallback=0):
    """优先取响应里的实际数值，挖不到才用回落值。

    任务列表里的 reward_credit 只是活动配置，与服务端这次实际发放的可能不同；
    上报按响应值才不会虚报，响应里没有时才退回配置值。
    """
    if isinstance(body, dict):
        v = dig(body, key)
        if v is not None:
            return as_int(v)
    return as_int(fallback)


def _fmt_eta(arrive_at, server_now):
    """把服务端返回的 Unix 时间戳换算成"还有多久回来"。

    任一时间戳缺失/非法就返回空串——这是纯展示信息，绝不能因为它让整轮执行失败。
    json.loads 默认接受 Infinity/NaN，非有限值同样按缺失处理，否则会汇报出
    "约 inf 小时后回"这种话。
    """
    try:
        left = float(arrive_at) - float(server_now)
    except (TypeError, ValueError, OverflowError):
        return ""
    if not math.isfinite(left):
        return ""
    if left <= 0:
        return "，已到达待领取"
    # 先算分钟再决定用哪个量纲：直接按 left < 3600 分档会让 3599s 显示成"约 60 分钟"
    minutes = int(round(left / 60.0))
    if minutes < 60:
        return "，约 %d 分钟后回" % max(1, minutes)
    return "，约 %.1f 小时后回" % (left / 3600.0)


def _env_flag(name):
    """开关型环境变量是否为真；空串与 0/false/no/off 一律视为关。"""
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _client_token(prefix="u"):
    """活动接口（抽奖/连登兑换）要求的防重放 token。

    官方前端用 `crypto.randomUUID()` 拼成 "u-<uuid>"，服务端只做幂等去重、
    不校验格式；缺了它 /lottery/draw 直接 400（实测过）。
    """
    return "%s-%s" % (prefix, uuid.uuid4())


# 连登兑换各档奖励的官方文案（2026-09 活动版本）。兑换成功的汇报优先用
# 服务端返回的实际明细，挖不到字段时才回落到这里——活动改版时以响应为准。
_REDEEM_REWARDS = {
    "7d":  "+2 能量 +1 补登卡 +1 次抽奖",
    "14d": "+50 积分 +3 能量 +1 补登卡 +1 次抽奖",
    "28d": "+150 积分 +5 能量 +1 补登卡 +1 次抽奖",
}

# 连登兑换三档：(档位标识, /redeem/summary 的状态字段前缀, 展示名, 天数)
# tier 的口径是档位标识字符串，天数只用于兜底重试时退回旧写法。
_REDEEM_TIERS = (
    ("7d",  "starter",   "入门", 7),
    ("14d", "advanced",  "进阶", 14),
    ("28d", "legendary", "巅峰", 28),
)


def _redeem_reward_desc(body, tier):
    """兑换成功的奖励描述：优先拼服务端实发的 *_granted，挖不到才回落官方文案。

    注意实发字段名带 _granted 后缀（credit_granted / energy_granted /
    cards_granted / chances_granted）；直接读 `credit` 恒为空，会把兑换所得漏计。
    """
    bits = []
    credit = as_int(dig(body, "credit_granted"), 0)
    energy = as_int(dig(body, "energy_granted"), 0)
    cards = as_int(dig(body, "cards_granted"), 0)
    chances = as_int(dig(body, "chances_granted"), 0)
    if credit:
        bits.append("+%s 积分" % fmt_credit(credit))
    if energy:
        bits.append("+%s 能量" % fmt_credit(energy))
    if cards:
        bits.append("+%s 补登卡" % fmt_credit(cards))
    if chances:
        bits.append("+%s 次抽奖" % fmt_credit(chances))
    if bits:
        return "（%s）" % " ".join(bits)
    return "（%s）" % _REDEEM_REWARDS.get(tier, "奖励已到账")



def run_growth(headers, endpoint):
    """成长中心自动化：领旅行礼物→派 Buddy→领任务/领取新任务→补登→连登兑换→开盲盒→能量开 Buddy→汇报。

    各子步骤单独 try，一段失败不影响其余领取；认证或权限拒绝时结束本轮。
    """
    base = endpoint + "/v2/activity/growth"
    parts = []
    credits_gained = 0
    failures = 0        # 全部失败项，仅用于汇报
    hard_failures = 0   # 其中"需要关注"的那些，只有它们影响退出码
    successes = 0

    def _check_auth(code):
        """已知业务 403 由调用方先处理，其余认证/权限拒绝结束本轮。"""
        return code in (401, 403)

    def _note_http(code, body, label, required=False):
        """前置查询接口非 2xx 时的统一记录；返回 True 表示调用方应跳过后续处理。

        硬失败（5xx / 网络不可达 / 预算耗尽）必须计入 failures：否则整轮
        successes=0 且 failures=0 会被判成 idle，轮询既不写日志又返回 0，
        服务端故障彻底无声无息。旅行模块早就这么做了，其余各段没跟上。

        一般查询的 4xx 只进报告、不计失败。补登判断所必需的查询用 required=True：
        查询失败或业务码非零时必须提醒，不能把未知状态解释为无需补登。
        """
        nonlocal failures, hard_failures
        if 200 <= code < 300 and (not required or _api_success(code, body)):
            return False
        reason = _http_label(code)
        detail = ""
        if isinstance(body, dict):
            detail = str(body.get("error") or body.get("msg") or "")
        # 状态码与服务端给的详情都保留：只知道 500 无法判断影响，只知道 "timed out"
        # 又看不出是网络还是服务端，轮询日志里这两者都想要
        parts.append("%s失败：%s" % (label, "%s（%s）" % (reason, detail)
                                     if detail and detail != reason else (detail or reason)))
        if True:
            failures += 1
            hard_failures += 1
        return True

    # --- 1. Buddy 旅行：领礼物 + 派出发 ---
    try:
        scode, sbody = get(base + "/buddy/travel/status", headers)
        if scode == CODE_BUDGET_OUT:
            return 1, {"result": "TIMEOUT",
                       "report": "时间预算耗尽，成长中心跳过，下次自动重试"}
        if scode == CODE_NO_NETWORK:
            # 网络不可达就立刻收手，别把后续 5 个接口的重试+等待全跑一遍
            return 1, {"result": "NETWORK",
                       "report": "网络不可达，成长中心跳过（%s）" % (sbody.get("error") or "")}
        if _check_auth(scode):
            return 1, _auth_failure(scode)
        travel = dig(sbody, "state") if (200 <= scode < 300) else None
        # 服务端明确给出"今日旅行名额已用完"。读它而不是等 depart 报错，
        # 轮询场景下差别很大：后者会让每一轮都白撞一次墙。
        daily_limit = bool(dig(sbody, "daily_limit_reached")) if (200 <= scode < 300) else False
        _note_http(scode, sbody, "查旅行状态")
        claimed_travel = False
        if travel == "arrived":
            record_id = dig(sbody, "record_id")
            ccode, cbody = post(base + "/buddy/travel/claim", headers, {"record_id": record_id})
            if _check_auth(ccode):
                return 1, _auth_failure(ccode)
            if 200 <= ccode < 300 and dig(cbody, "reward_credit") is not None:
                got = as_int(dig(cbody, "reward_credit"))
                credits_gained += got
                parts.append("领旅行礼物 +%s 积分" % fmt_credit(got))
                successes += 1
                claimed_travel = True
            else:
                # 领失败：带出业务 msg，不再说"HTTP 200"；也不派 Buddy 出发，避免覆盖未领取的奖励
                msg = (dig(cbody, "msg") or "") if isinstance(cbody, dict) else ""
                parts.append("领旅行礼物失败：%s" % (msg or "HTTP %s" % ccode))
                failures += 1
                hard_failures += _is_hard_failure(ccode)
            if claimed_travel:
                travel = "idle"  # 只有领取成功后才视为 idle，允许派出发
        if travel == "idle" and not flag("WORKBUDDY_DEPART"):
            parts.append("自动派遣已关闭")
        elif travel == "idle" and daily_limit:
            # 今日名额已用完：直接收手，不碰 config/depart，省掉两个请求和一条必然的失败
            parts.append("今日旅行名额已用完")
        elif travel == "idle":
            ccode, cbody = get(base + "/buddy/travel/config", headers)
            if _check_auth(ccode):
                return 1, _auth_failure(ccode)
            locs = dig(cbody, "locations") if (200 <= ccode < 300) else None
            if locs and isinstance(locs[0], dict):
                loc = locs[0]
                dcode, dbody = post(base + "/buddy/travel/depart", headers,
                                    {"location_id": loc.get("id")})
                if _check_auth(dcode):
                    return 1, _auth_failure(dcode)
                if 200 <= dcode < 300:
                    loc_name = (dig(dbody, "location") or {}).get("name", "?")
                    dur = dig(dbody, "duration_hours") or (dig(dbody, "location") or {}).get("duration_hours", "?")
                    parts.append("派 Buddy 去%s（%s 小时后回）" % (loc_name, dur))
                    successes += 1
                else:
                    msg = dig(dbody, "msg") or ""
                    parts.append("派 Buddy 失败：%s" % (msg or "HTTP %s" % dcode))
                    failures += 1
                    hard_failures += _is_hard_failure(dcode)
        elif travel == "traveling":
            loc_name = (dig(sbody, "location") or {}).get("name", "?")
            # arrive_at / server_now 是服务端时间戳，比本地时钟可靠
            parts.append("Buddy 旅行中（%s%s）" % (
                loc_name, _fmt_eta(dig(sbody, "arrive_at"), dig(sbody, "server_now"))))
    except Exception as e:
        parts.append("旅行模块异常（%s: %s）" % (type(e).__name__, e))
        failures += 1
        hard_failures += 1

    # --- 2. 任务领奖（放在抽奖前：任务送的抽奖机会/能量，后面马上能用上）---
    if _budget_left() <= 0:
        parts.append("时间预算耗尽，任务领奖跳过")
    else:
        try:
            tcode, tbody = get(base + "/tasks", headers)
            if _check_auth(tcode):
                return 1, _auth_failure(tcode)
            if not _note_http(tcode, tbody, "查任务列表"):
                tasks = dig(tbody, "tasks") or []
                # 真实契约（2026-09 从桌面端成长中心 H5 的 growthSpace chunk 读出）：
                #   accept_status: not_accepted | accepted | in_progress | completed | claimed
                #   接单 POST /tasks/accept  body {"task_codes": [code, ...]}   ← 复数数组
                #        （旧的单数 {"task_code": x} 在新服务端一律 400 invalid request）
                #   领奖 POST /tasks/{task_code}/claim   ← 路径带 code、body 空
                #        （旧版拿 /tasks/accept 当领奖用，同样 400）
                titles = {t.get("task_code"): t.get("title", t.get("task_code")) for t in tasks}
                pending = [t.get("task_code") for t in tasks
                           if t.get("task_code") and not t.get("locked")
                           and t.get("accept_status") == "not_accepted"]
                for i in range(0, len(pending), 20):   # 分批，别把 body 撑大
                    if _budget_left() <= 0:
                        parts.append("时间预算耗尽，剩余任务下次再接单")
                        break
                    batch = pending[i:i + 20]
                    acode, abody = post(base + "/tasks/accept", headers,
                                        {"task_codes": batch})
                    if _check_auth(acode):
                        return 1, _auth_failure(acode)
                    # 逐条读 results：接单失败必须报出来（常见
                    # "prerequisite not met: first_buddy (no buddy instance found)"），
                    # 静默吞掉的话接口坏了也没人知道——轮询空跑是不写日志的。
                    results = dig(abody, "results")
                    if not isinstance(results, list):
                        results = [{"task_code": c,
                                    "status": "error",
                                    "message": dig(abody, "msg")} for c in batch]
                    if len(results) != len(batch):
                        failures += 1
                    for r in results:
                        title = titles.get(r.get("task_code"), r.get("task_code"))
                        if r.get("status") not in ("ok", "success", "accepted"):
                            parts.append("领取任务「%s」失败：%s" % (
                                title, r.get("message") or "HTTP %s" % acode))
                            failures += 1
                            hard_failures += _is_hard_failure(acode)
                        else:
                            parts.append("领取任务「%s」（进度开始计）" % title)
                            successes += 1
                for t in tasks:
                    if _budget_left() <= 0:
                        parts.append("时间预算耗尽，剩余任务奖下次再领")
                        break
                    if t.get("locked") or t.get("accept_status") != "completed":
                        continue   # 只有 completed 才发奖，且走独立路径
                    code = t.get("task_code")
                    title = titles.get(code, code)
                    try:
                        ccode, cbody = post(base + "/tasks/%s/claim" % code, headers, {})
                        if _check_auth(ccode):
                            return 1, _auth_failure(ccode)
                        if 200 <= ccode < 300 and not dig(cbody, "already_claimed"):
                            # 优先用服务端实发数值；列表里的 reward_credit 只是活动配置，
                            # 改版时会和实发对不上，挖不到才回落到列表值。
                            rc = _first_int(cbody, "credit", t.get("reward_credit"))
                            re_ = _first_int(cbody, "energy", t.get("reward_energy"))
                            credits_gained += rc
                            parts.append("领任务奖「%s」+credit%s+energy%s" % (title, rc, re_))
                            successes += 1
                        elif 200 <= ccode < 300:
                            parts.append("任务奖「%s」已领过" % title)
                        else:
                            parts.append("领任务奖「%s」失败：%s" % (
                                title, dig(cbody, "msg") or "HTTP %s" % ccode))
                            failures += 1
                            hard_failures += _is_hard_failure(ccode)
                    except Exception as e:
                        parts.append("领任务奖「%s」异常（%s: %s）" % (
                            code, type(e).__name__, e))
                        failures += 1
                        hard_failures += 1
        except Exception as e:
            parts.append("任务模块异常（%s: %s）" % (type(e).__name__, e))
            failures += 1
            hard_failures += 1

    # --- 3. 补登卡：断登自动补一张，保住连登 ---
    # 官方规则：补登卡上限 4 张、仅可补救当月断登。/streak 的 makeup_dates
    # 是已经补登的日期；真正的断点来自 /heatmap 中 score == 0 的历史日期。
    # 放在连登兑换之前：补登会改变连登天数，先补，兑换才能拿到最新解锁状态。
    # 2026-10-01 核对官方 GrowthCenterPage / AllTasksPage 与真实只读日历。
    # 保留每轮最多一张、写请求不重试的限制；空白或异常数据不会触发补登。
    streak_body = None    # 复用给第 7 段的展示值，避免同一轮打两次 /streak
    streak_stale = False  # 补登成功会改变连签天数，此时必须重新取
    if _budget_left() <= 0:
        parts.append("时间预算耗尽，补登跳过")
    else:
        try:
            mcode, mbody = get(base + "/streak", headers)
            if _check_auth(mcode):
                return 1, _auth_failure(mcode)
            if not _note_http(mcode, mbody, "查连登状态", required=True):
                streak_body = mbody
                # 余额兼容两种形状：{"makeup_cards":{"balance":2}} 与 {"makeup_cards":2}。
                # 只认前者的话，接口是后者时整个补登会一声不响地永不执行。
                cards_obj = dig(mbody, "makeup_cards")
                cards = as_int(cards_obj.get("balance")) if isinstance(cards_obj, dict) \
                    else as_int(cards_obj)
                dates = []
                if cards > 0 and flag("WORKBUDDY_MAKEUP"):
                    hcode, hbody = get(base + "/heatmap", headers)
                    if _check_auth(hcode):
                        return 1, _auth_failure(hcode)
                    if not _note_http(hcode, hbody, "查补登日历", required=True):
                        dates = _makeup_candidates(mbody, hbody)
                if dates:
                    made_up = 0
                    for d in dates[:min(cards, MAKEUP_MAX_PER_RUN)]:
                        if _budget_left() <= 0:
                            parts.append("时间预算耗尽，剩余补登下次再做")
                            break
                        ucode, ubody = post(base + "/makeup-cards/use", headers,
                                            {"target_date": d})
                        if _check_auth(ucode):
                            return 1, _auth_failure(ucode)
                        if _api_success(ucode, ubody):
                            cards -= 1
                            made_up += 1
                            streak_stale = True
                            # 优先报服务端给的余额，本地递减只是接口没给时的兜底
                            left_obj = dig(ubody, "makeup_cards")
                            left_cards = as_int(left_obj.get("balance"), cards) \
                                if isinstance(left_obj, dict) else as_int(left_obj, cards)
                            parts.append("补登 %s（剩 %s 张卡）" % (d, left_cards))
                            cards = max(0, left_cards)
                            successes += 1
                        else:
                            msg = dig(ubody, "msg") or ""
                            if ucode == 400 and str(msg).strip().lower() == "date is not broken, no makeup needed":
                                # 查询后被客户端或另一轮补上，是正常竞争；不再当作失败刷日志。
                                parts.append("%s 已活跃或已补登，无需再次补登" % d)
                                break
                            parts.append("补登 %s 失败：%s" % (d, msg or "HTTP %s" % ucode))
                            failures += 1
                            hard_failures += 1
                            break
                    if made_up and len(dates) > made_up and cards > 0:
                        parts.append("另有 %s 天可补、剩 %s 张卡，下轮继续" % (
                            len(dates) - made_up, cards))
        except Exception as e:
            parts.append("补登模块异常（%s: %s）" % (type(e).__name__, e))
            failures += 1
            hard_failures += 1

    # --- 4. 连登奖励兑换（入门/进阶/巅峰三档，附积分/能量/补登卡/抽奖机会）---
    # 入门 7 天、进阶 14 天、巅峰 28 天解锁。summary 只报 claimed/locked 两种
    # 已见状态；"非 claimed 且非 locked"即视为可兑换去尝试，被服务端拒绝时按
    # 普通业务失败处理（不算硬失败）。
    if _budget_left() <= 0:
        parts.append("时间预算耗尽，连登兑换跳过")
    else:
        try:
            rcode, rbody = get(base + "/redeem/summary", headers)
            if _check_auth(rcode):
                return 1, _auth_failure(rcode)
            if not _note_http(rcode, rbody, "查连登兑换"):
                # tier 传**档位标识**（"7d"/"14d"/"28d"），不是天数也不是档位名：
                # 实测传 "starter"/"7"/7 分别得到 unknown tier / unknown tier /
                # invalid request，只有 "7d" 会 200 兑换成功。权威来源是 GET /streak
                # 的 redemption_status.tiers[].tier；状态字段仍读 /redeem/summary
                # 的 starter/advanced/legendary_status，两者一一对应。
                for tier, status_key, label, days in _REDEEM_TIERS:
                    if _budget_left() <= 0:
                        parts.append("时间预算耗尽，剩余连登兑换下次再领")
                        break
                    status = dig(rbody, status_key + "_status")
                    # 字段缺失（None）同样跳过：接口改版时不该让脚本对三档无脑 POST。
                    # 注意别在这里再加 *_count 之类的"双保险"：实测响应里
                    # starter_count=1 与 total_consumed=0 并存，count 到底是
                    # "已兑换次数"还是"可兑换次数"并不确定，猜错就会把整段静默关掉。
                    if not status or status in ("claimed", "locked"):
                        continue
                    c2code, c2body = post(base + "/redeem", headers,
                                          {"tier": tier, "client_token": _client_token()})
                    # 档位标识被判为未知时退回天数再试一次：这类 400 是参数校验阶段
                    # 的拒绝，服务端没兑换任何东西，重试不会重复领取
                    if _is_unknown_tier(c2code, c2body):
                        c2code, c2body = post(base + "/redeem", headers,
                                              {"tier": days, "client_token": _client_token()})
                    # 403「连登天数不足」是业务常态，必须**先于** _check_auth 判断：
                    # _check_auth 会结束认证/权限拒绝的流程，若让它先跑，未解锁档位
                    # 会被当成权限拒绝并直接中止整个成长中心。
                    if _is_tier_locked(c2code, c2body):
                        parts.append("连登兑换「%s」未解锁（连登天数不足）" % label)
                        continue
                    if _check_auth(c2code):
                        return 1, _auth_failure(c2code)
                    if 200 <= c2code < 300:
                        credits_gained += as_int(dig(c2body, "credit_granted"))
                        parts.append("连登兑换「%s」%s" % (label, _redeem_reward_desc(c2body, tier)))
                        successes += 1
                    else:
                        msg = dig(c2body, "msg") or ""
                        parts.append("连登兑换「%s」失败：%s" % (label, msg or "HTTP %s" % c2code))
                        failures += 1
                        hard_failures += _is_hard_failure(c2code)
        except Exception as e:
            parts.append("连登兑换模块异常（%s: %s）" % (type(e).__name__, e))
            failures += 1
            hard_failures += 1

    # --- 5. 盲盒/抽奖（draw 必须带 client_token，缺了会 400）---
    if _budget_left() <= 0:
        parts.append("时间预算耗尽，盲盒跳过")
    else:
        try:
            lcode, lbody = get(base + "/lottery/chances", headers)
            if _check_auth(lcode):
                return 1, _auth_failure(lcode)
            chances = 0 if _note_http(lcode, lbody, "查抽奖机会") else as_int(dig(lbody, "balance"))
            if chances > 0 and flag("WORKBUDDY_LOTTERY"):
                dcode, dbody = post(base + "/lottery/draw", headers,
                                    {"client_token": _client_token()})
                if _check_auth(dcode):
                    return 1, _auth_failure(dcode)
                if 200 <= dcode < 300:
                    prize = dig(dbody, "prize_name") or dig(dbody, "prize") or "未知"
                    if not isinstance(prize, str):
                        # prize 可能是对象/数字；直接 += 会抛 TypeError，把一次已经中了的
                        # 抽奖变成"模块异常"，奖品名和下面这句提醒双双丢失
                        prize = str(prize)
                    # 奖池含实物周边（冰箱贴/胸针/杯子），中奖后要用户自己去填收件信息，
                    # 脚本代填不了也绝不该代填——但必须提醒，否则奖品会卡在未填地址状态。
                    if dig(dbody, "need_address") or dig(dbody, "require_address"):
                        prize += "（实物奖，需到成长中心填写收件信息）"
                    parts.append("开盲盒获得：%s" % prize)
                    successes += 1
                    # 一轮只开一次：这条写路径不可逆，剩下的机会留给下一轮更稳妥
                    if chances > 1:
                        parts.append("还剩 %s 次抽奖机会，下轮继续" % (chances - 1))
                else:
                    msg = dig(dbody, "msg") or ""
                    if _is_no_chance(msg):
                        # 次数为 0 是常态（次数来自连登兑换），不是故障：计入失败会让
                        # 轮询每轮强制落盘，还会把常态算进失败统计
                        parts.append("开盲盒：%s" % (msg or "无抽奖机会"))
                    else:
                        parts.append("开盲盒失败：%s" % (msg or "HTTP %s" % dcode))
                        failures += 1
                        hard_failures += _is_hard_failure(dcode)
        except Exception as e:
            parts.append("盲盒模块异常（%s: %s）" % (type(e).__name__, e))
            failures += 1
            hard_failures += 1

    # --- 6. Buddy 盲盒（能量攒够 cost_per_open 就开；能量没有其它消耗出口）---
    if _budget_left() <= 0:
        parts.append("时间预算耗尽，Buddy 盲盒跳过")
    else:
        try:
            qcode, qbody = get(base + "/buddy/quota", headers)
            if _check_auth(qcode):
                return 1, _auth_failure(qcode)
            if not _note_http(qcode, qbody, "查 Buddy 能量"):
                affordable = as_int(dig(qbody, "affordable"))
                max_open = as_int(dig(qbody, "max_open_count"), 1) or 1
                if affordable > 0 and flag("WORKBUDDY_BUDDY_OPEN"):
                    count = min(affordable, max_open)
                    ocode, obody = post(base + "/buddy/open", headers,
                                        {"count": count, "client_token": _client_token()})
                    if _check_auth(ocode):
                        return 1, _auth_failure(ocode)
                    if 200 <= ocode < 300:
                        name = dig(obody, "buddy") or dig(obody, "name") or dig(obody, "buddies")
                        if not isinstance(name, str):
                            name = "新 Buddy"
                        parts.append("开 Buddy 盲盒 ×%s（%s）" % (count, name))
                        successes += 1
                    else:
                        msg = dig(obody, "msg") or ""
                        parts.append("开 Buddy 盲盒失败：%s" % (msg or "HTTP %s" % ocode))
                        failures += 1
                        hard_failures += _is_hard_failure(ocode)
        except Exception as e:
            parts.append("Buddy 盲盒模块异常（%s: %s）" % (type(e).__name__, e))
            failures += 1
            hard_failures += 1

    # --- 7. 能量 & 连签状态（纯展示值，预算不够就直接不取，不计失败）---
    energy = None
    streak_days = None
    if _budget_left() > 0:
        try:
            ecode, ebody = get(base + "/energy", headers)
            if not _check_auth(ecode):
                energy = dig(ebody, "balance") if (200 <= ecode < 300) else None
        except Exception:
            pass

    # 连签天数：第 3 段已经取过 /streak，没补登过就直接复用，别在同一轮里打两次同一个接口。
    # 补登成功会改变天数（streak_stale），那时才有必要重新取。
    try:
        if streak_body is not None and not streak_stale:
            streak_obj = dig(streak_body, "streak") or {}
            streak_days = streak_obj.get("days") if isinstance(streak_obj, dict) else None
        elif _budget_left() > 0:
            scode2, sbody2 = get(base + "/streak", headers)
            if not _check_auth(scode2):
                streak_obj = dig(sbody2, "streak") or {}
                streak_days = streak_obj.get("days") if isinstance(streak_obj, dict) else None
    except Exception:
        pass

    tail = []
    if energy is not None:
        tail.append("能量 %s" % energy)
    if streak_days is not None:
        tail.append("连签 %s 天" % streak_days)
    if credits_gained:
        tail.append("本次 +共 %s 积分" % credits_gained)

    if parts:
        report = "；".join(parts)
    elif failures:
        report = "成长中心各步骤均失败"
    else:
        report = "成长中心无可领取项"
    if tail:
        report += "（%s）" % "，".join(tail)

    # 已获得的奖励仍保留在汇报里，但不能掩盖其他步骤需要处理的失败。
    # 已识别的正常业务状态（如旅行名额用完、日期无需补登）不会计入 hard_failures。
    result_code = 1 if failures else 0
    # idle = 这一轮既没领到东西也没出错，纯空跑（Buddy 还在路上 / 今日名额已用完 /
    # 确实没有可领项）。轮询任务靠它决定要不要写日志。
    idle = (successes == 0 and failures == 0)
    return result_code, {"result": "GROWTH", "report": report, "credits_gained": credits_gained,
                         "energy": energy, "streak_days": streak_days, "idle": idle,
                         **({"failures": failures} if failures else {})}



def account_headers(line, legacy=False):
    if legacy:
        token = line.strip()
        session = {"auth": {"accessToken": token}, "account": {}}
    else:
        session = json.loads(line)
        if not isinstance(session, dict):
            raise ValueError()
        token = session["auth"]["accessToken"]
        uid = session["account"]["uid"]
        if not isinstance(uid, str) or not uid:
            raise ValueError()
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._~+/-]{1,32768}=*", token):
        raise ValueError()
    secrets.add(token)
    auth, account = session["auth"], session["account"]
    if auth.get("endpoint", ENDPOINT) != ENDPOINT:
        raise ValueError()
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json",
               "Content-Type": "application/json", "User-Agent": "WorkBuddy",
               "Origin": "https://www.workbuddy.cn", "Referer": "https://www.workbuddy.cn/"}
    for field, target, obj in (("uid", "X-User-Id", account),
                               ("enterpriseId", "X-Enterprise-Id", account),
                               ("domain", "X-Domain", auth)):
        value = obj.get(field)
        if value:
            if not isinstance(value, str) or not re.fullmatch(r"[\x21-\x7e]{1,2048}", value):
                raise ValueError()
            headers[target] = value
            if field != "uid":
                secrets.add(value)
    if "X-Enterprise-Id" in headers:
        headers["X-Tenant-Id"] = headers["X-Enterprise-Id"]
    return headers


def signin(headers, action):
    base = ENDPOINT + "/v2/billing/meter/"
    status = {}
    if action != "claim":
        code, body = post(base + "checkin-activity-status", headers)
        if not 200 <= code < 300 or not isinstance(body, dict):
            return 1, {"result": "ERROR", "report": "签到状态查询失败"}
        status = body
        checked = dig(body, "today_checked_in")
        if type(checked) not in (bool, int) or checked not in (0, 1):
            if dig(body, "active") is False:
                return 0, {"result": "INACTIVE", "report": "签到活动未开启"}
            return 1, {"result": "ERROR", "report": "签到状态字段缺失或异常"}
        if action == "status":
            return 0, {"result": "STATUS", "report": "状态查询成功，今日%s" % ("已签到" if checked else "未签到"),
                       "streak_days": dig(body, "streak_days")}
        if checked:
            return 0, {"result": "ALREADY", "report": "今日已签到", "streak_days": dig(body, "streak_days")}
    code, body = post(base + "daily-checkin", headers)
    if 200 <= code < 300 and body is None or code == 400 and isinstance(body, dict) and body.get("code") == 10001:
        return 0, {"result": "ALREADY", "report": "服务端确认今日已签到"}
    credit = dig(body, "credit")
    if 200 <= code < 300 and type(credit) in (int, float) and math.isfinite(credit) and credit >= 0:
        return 0, {"result": "CLAIMED", "report": "签到成功，领取 %s 积分" % credit, "credit": credit}
    return 1, {"result": "ERROR", "report": "签到领取未获有效业务成功确认"}


def notify(summary, dry):
    mode = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if dry:
        return "预演跳过通知网络"
    if mode in ("0", "false", "no", "off"):
        return "全局关闭"
    selection = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    names = (CATALOG, Path(__file__).name, "output/candidate.py", "get_token/signin.py", "candidate.py")
    if mode not in ("1", "true", "yes", "on") and selection is not None:
        selectors = re.split(r"[,;\s]+", selection.strip())
        if not any(fnmatch.fnmatch(name, pattern) for name in names for pattern in selectors if pattern):
            return "选择列表未启用"
    body = "账号总数 {accounts}，成功 {success}，失败 {failed}；状态 {status}".format(**summary)
    # Notification implementations are optional Qinglong integrations, never business dependencies.
    # Suppress notifier stdout/stderr so plugin errors cannot expose secrets or raw responses.
    try:
        subprocess.run([sys.executable, "-c", "import notify,sys; notify.send(sys.argv[1],sys.argv[2])", TITLE, body],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=True)
        return "已发送"
    except Exception:
        pass
    roots = []
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        roots.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]))
    roots.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    for root in roots:
        for filename in ("notify.py", "sendNotify.js"):
            path = root / filename
            if not path.is_file():
                continue
            if filename.endswith(".py"):
                command = [sys.executable, "-c", "import importlib.util,sys; s=importlib.util.spec_from_file_location('ql_notify',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[2],sys.argv[3])", str(path), TITLE, body]
            else:
                command = ["node", "-e", "require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])", str(path), TITLE, body]
            try:
                subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=True)
                return "已发送"
            except Exception:
                continue
    return "通知不可用或发送失败，保留业务退出码"


def main():
    global stats, _started_at, _budget_seconds
    start = time.monotonic()
    dry = flag("WORKBUDDY_DRY_RUN")
    action = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WORKBUDDY_ACTION", "auto")
    legacy = not os.environ.get("WORKBUDDY_ACCOUNTS", "").strip()
    lines = [line.strip() for line in os.environ.get("WB_ACCESS_TOKEN" if legacy else "WORKBUDDY_ACCOUNTS", "").splitlines() if line.strip()]
    log("=== %s ===" % TITLE)
    log("开始时间：%s；模式：%s；账号数：%d" % (datetime.now().isoformat(timespec="seconds"), "断网预演" if dry else "实运行", len(lines)))
    allowed = ("auto", "silent", "silent-poll", "silent-growth", "growth", "status", "claim", "all", "doctor")
    config_error = not lines or action not in allowed or len(sys.argv) > 2
    try:
        default = 180 if action in ("silent-poll", "silent-growth") else 420
        limit = 240 if default == 180 else 540
        _budget_seconds = float(os.environ.get("WORKBUDDY_BUDGET_SECONDS", default))
        if not math.isfinite(_budget_seconds) or not 1 <= _budget_seconds <= limit:
            raise ValueError()
        for key in ("WORKBUDDY_DEPART", "WORKBUDDY_MAKEUP", "WORKBUDDY_LOTTERY", "WORKBUDDY_BUDDY_OPEN"):
            if os.environ.get(key, "0").lower() not in ("0", "false", "no", "off", "1", "true", "yes", "on"):
                raise ValueError()
    except Exception:
        config_error = True
    successes = 0
    failures = 0
    totals = dict(total=0, success=0, already=0, skipped=0, failed=0)
    if config_error:
        log("配置错误：请检查凭据、命令和预算/开关格式；不执行账号请求")
    else:
        for index, line in enumerate(lines, 1):
            _started_at = time.monotonic()
            stats = dict(total=0, success=0, already=0, skipped=0, failed=0)
            log("账号 %d；阶段 0：校验凭据" % index)
            try:
                headers = account_headers(line, legacy)
                if dry or action == "doctor":
                    log("阶段 1：凭据结构通过；%s，不发起 HTTP、通知或资源消耗" % ("DRY_RUN_OK 断网预演" if dry else "离线诊断"))
                    for key in ("DEPART", "MAKEUP", "LOTTERY", "BUDDY_OPEN"):
                        log("风险动作 %s：%s" % (key, "显式开启" if flag("WORKBUDDY_"+key) else "关闭"))
                    code, out = 0, {"result": "DRY_RUN_OK" if dry else "DOCTOR_OK", "report": "离线结构检查通过，不代表业务成功"}
                    log("计划阶段：查询签到状态→未签领取→旅行礼物→接单与任务领奖→日历补登→连登兑换→抽奖→Buddy 盲盒→能量及连登汇报；status/claim/growth 按命令范围执行")
                    stats["skipped"] += 1
                else:
                    code, out = (0, {"result": "GROWTH", "report": "仅运行成长中心"}) if action == "growth" else signin(headers, action)
                    if action in ("growth", "auto", "silent", "silent-poll", "silent-growth") and not code:
                        gcode, gout = run_growth(headers, ENDPOINT)
                        out["growth"] = gout.get("report")
                        out["growth_result"] = gout.get("result")
                        code = code or gcode
                    if stats["failed"]:
                        code = 1
                    log("阶段结果：%s" % out.get("report"))
                    if out.get("growth"):
                        log("成长中心：%s" % out["growth"])
                # Preserve upstream structured result fields, never raw HTTP response bodies.
                print(json.dumps(json.loads(clean(json.dumps(out, ensure_ascii=False))), ensure_ascii=False))
            except Exception:
                code = 1
                stats["failed"] += 1
                log("凭据格式或账号处理失败；已隐藏错误内容，继续下一个账号")
            successes += int(code == 0)
            failures += int(code != 0)
            for key in totals:
                totals[key] += stats[key]
            log("账号 %d：%s；总步骤 %d，成功 %d，已完成 %d，跳过 %d，失败 %d；耗时 %.2f 秒" % (index, "成功" if not code else "失败", stats["total"], stats["success"], stats["already"], stats["skipped"], stats["failed"], time.monotonic()-_started_at))
    status = "configuration-error" if config_error else "partial-failure" if failures and successes else "failure" if failures else "dry-run" if dry else "success"
    result = dict(accounts=len(lines), success=successes, failed=failures, status=status, steps=totals)
    notification = notify(result, dry)
    log("----------------------------------------")
    log("任务统计：账号 %d，成功 %d，失败 %d；子步骤 %s" % (len(lines), successes, failures, totals))
    log("通知：%s；总耗时 %.2f 秒；完成时间 %s；最终状态 %s" % (notification, time.monotonic()-start, datetime.now().isoformat(timespec="seconds"), status))
    result["notification"] = notification
    print("TASK_SUMMARY=" + json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 2 if config_error else 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
