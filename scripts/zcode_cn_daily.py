#!/usr/bin/env python3
# name: ZCode 国内版领套餐
# cron: 0 9 * * *
# 来源：L0NE-6/ZCode-Daily，zcode_cn_daily.py
# 上游许可：MIT；本维护版本沿用 MIT。
"""
ZCode 国内版限时套餐领取（不是传统签到）。Python 3，仅使用标准库。
功能清点：预览套餐和权益、按最高优先级（同优先取首项）或指定套餐领取、
验证码、版本参数、单账号筛选、北京时间、多渠道通知；激活事件改为显式开启。
上游未提供 cron；建议每日北京时间 09:00，青龙调度时区需设 Asia/Shanghai。
国际版 JWT 不通用，不合并国际版；交互登录工具仅作为凭据获取参考。

ZCODE_CN_TOKENS：每行一个账号，不用 & 或 @ 分隔。兼容以下格式：
jwt；jwt|device_mid；jwt|device_mid|captcha；备注|jwt|device_mid|captcha。
备注前缀要求下一段为 JWT；依次仅在第一个 | 拆字段，最后验证码保留全部字符。
在官方 ZCode 国内版登录后，在浏览器开发者工具的网络面板查看套餐
billing/preview 或 billing/claim 请求：Authorization 的 Bearer 后内容为套餐 JWT，
X-Device-Mid 为设备值；claim 的 X-Aliyun-Captcha-Verify-Param 为验证码参数。
不要使用推理 API Key 或国际版 Token。验证码可能短时一次性，3007 时重新抓取。
设备值优先显式填写；兼容读取脚本旁已有 zcode_cn_devices.json，缺省确定性生成，
不创建或修改任何设备文件。JWT 更换会改变自动生成的设备值，建议固定显式设备值。
ZCODE_PLAN_ID：可选指定预览返回的 plan_id；ZCODE_APP_VERSION：默认 3.14.0。
ZCODE_CAPTCHA_PARAM：可选全局验证码，仅补齐账号未填写的值，优先使用账号内参数。
ZCODE_ACTIVATION：默认 0；设 1 显式补报 app_launch/app_daily_active，可能影响领取资格。
--preview：只读预览（绝不上报事件或领取）；--only N：仅运行第 N 个账号；
--no-notify：禁用通知；ZCODE_CN_DRY_RUN=1：完全断网，通知仅模拟，不验证真实账号。
QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭。自动发现青龙 notify.py，
可用 QINGLONG_NOTIFY_DIR 指定目录；通知失败不改变业务退出码。
原推送参数 PUSHPLUS_TOKEN/BARK_URL/WECOM_WEBHOOK/DINGTALK_WEBHOOK/
DINGTALK_SECRET 保留，青龙通知不可用时尝试。不得配置非 HTTPS 推送地址。
不自动登录、不安装软件、不发布文本、不重试领取 POST，以避免重复副作用。
"""
# 随任务提供的源码没有额外版权声明；保留来源归属及 MIT 许可。
# 
# MIT License
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
import os
import platform as host_platform
import re
import subprocess
import sys
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta, timezone

ORIGIN = "https://zcode.z.ai"
PREVIEW_PATH = "/api/v1/zcode-plan/billing/preview"
EVENT_REPORT_PATH = "/api/v1/event/report"
CLAIM_PATH = "/api/v1/zcode-plan/billing/claim"
DEFAULT_APP_VERSION = "3.14.0"
BEIJING_TZ = timezone(timedelta(hours=8))
FAILURE_LABELS = {1001:"没有这个套餐",1002:"活动未开始或已结束",1003:"已领取本期套餐",
1004:"账号或版本不在活动范围",1005:"今日次数用完",3001:"参数错误，请检查设备参数",
3007:"验证码未通过，请从 claim 请求重新获取验证码参数",401:"登录失效，请重新登录"}
DRY = False
SECRETS = []

def log(message):
    print(beijing_now().strftime("[%H:%M:%S] ") + str(message), flush=True)

def safe(value, public_uid=False):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已脱敏]")
    text = re.sub(r"[\r\n\x00-\x1f\x7f]", " ", text)
    if not public_uid:
        text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", text)
    return text

class TaskError(Exception):
    pass

class Response:
    def __init__(self, status, payload):
        self.status_code, self.payload = status, payload
    def json(self):
        return self.payload

def request(method, url, headers=None, body=None, timeout=15, retries=1):
    if DRY:
        raise TaskError("预演禁止网络请求")
    if not url.startswith("https://"):
        raise TaskError("拒绝非 HTTPS 请求")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    raw = None if body is None else json.dumps(body).encode()
    hdr = dict(headers or {})
    if body is not None:
        hdr.setdefault("Content-Type", "application/json")
    try:
        req = urllib.request.Request(url, data=raw, headers=hdr, method=method)
        try:
            response = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.code
            data = response.read(1048577)
        if len(data) > 1048576:
            raise TaskError("响应过大")
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError()
        return Response(status, payload)
    except TaskError:
        raise
    except Exception:
        raise TaskError("网络、TLS 或响应格式异常（已隐藏原始内容）") from None

def json_of(response):
    return response.json()

def post_json(url, payload, timeout=20):
    return request("POST", url, body=payload, timeout=timeout)

def local_timezone():
    return "Asia/Shanghai"

def local_os_version():
    return ""


def beijing_now():
    return datetime.now(BEIJING_TZ)

def first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""

def app_version():
    return os.environ.get("ZCODE_APP_VERSION", "").strip() or DEFAULT_APP_VERSION

def client_platform():
    system = host_platform.system().lower()
    machine = host_platform.machine().lower()
    if system == "windows":
        return "win32-x64"
    if system == "darwin":
        return "darwin-arm64" if "arm" in machine else "darwin-x64"
    return "linux-arm64" if ("arm" in machine or "aarch64" in machine) else "linux-x64"

def os_category():
    system = host_platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"

def activation_event_body(event, user_id, device_mid):
    return {
        "event_id": str(uuid.uuid4()),
        "client_timezone": local_timezone(),
        "client_language": "zh-CN",
        "element_name": event,
        "event_region": "app",
        "event_type": "view",
        "event_text": "",
        "event_extra_detail": {},
        "user_id": user_id,
        "screen_resolution": "2560x1440",
        "app_version": app_version(),
        "device_os_category": os_category(),
        "device_os_version": local_os_version(),
        "device_mid": device_mid,
        "source_page": "",
        "source_element": "{}",
    }

def preview(region_jwt, device_mid):
    url = "%s%s?app_version=%s&platform=%s" % (ORIGIN, PREVIEW_PATH, urllib.parse.quote(app_version(), safe=""), urllib.parse.quote(client_platform(), safe=""))
    headers = {"X-Device-Mid": device_mid} if device_mid else {}
    if region_jwt:
        headers["Authorization"] = "Bearer %s" % region_jwt
    return request("GET", url, headers=headers)

def claim(jwt, plan_id, device_mid, captcha):
    headers = {
        "Authorization": "Bearer %s" % jwt,
        "Content-Type": "application/json",
        "X-ZCode-App-Version": app_version(),
        "X-Platform": client_platform(),
    }
    if captcha:
        headers["X-Aliyun-Captcha-Verify-Param"] = captcha
    if device_mid:
        headers["X-Device-Mid"] = device_mid
    return request("POST", ORIGIN + CLAIM_PATH, headers=headers, body={"plan_id": plan_id})

def parse_plans(payload):
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    raw = data.get("plans")
    plans = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            plan_id = first_text(item.get("plan_id"), item.get("planId"))
            if not plan_id:
                continue
            entitlements = []
            for entry in item.get("entitlements") or []:
                if not isinstance(entry, dict):
                    continue
                show_name = first_text(entry.get("show_name"), entry.get("showName"))
                if show_name:
                    entitlements.append({
                        "name": show_name,
                        "unit": first_text(entry.get("unit_type"), entry.get("unitType")),
                        "grant": entry.get("grant_units", entry.get("grantUnits", 0)),
                        "period": first_text(entry.get("period")),
                    })
            plans.append({
                "plan_id": plan_id,
                "name": first_text(item.get("name")) or plan_id,
                "description": first_text(item.get("description")),
                "priority": int(item.get("priority") or 0),
                "starts_at": item.get("starts_at", item.get("startsAt")),
                "ends_at": item.get("ends_at", item.get("endsAt")),
                "entitlements": entitlements,
            })
    return plans

def pick_plan(plans):
    wanted = os.environ.get("ZCODE_PLAN_ID", "").strip()
    if wanted:
        for plan in plans:
            if plan["plan_id"] == wanted:
                return plan
        return None
    best = None
    for plan in plans:          # 同优先级取最先出现的
        if best is None or plan["priority"] > best["priority"]:
            best = plan
    return best

def format_time(seconds):
    if not seconds:
        return "立即"
    try:
        return datetime.fromtimestamp(int(seconds), BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(seconds)

def describe_plan(plan):
    text = plan["name"]
    if plan.get("entitlements"):
        parts = []
        for entry in plan["entitlements"]:
            unit = entry.get("unit") or ""
            grant = entry.get("grant") or 0
            period = "每日" if entry.get("period") == "daily" else "一次性"
            parts.append("%s %s%s（%s）" % (entry["name"], grant, unit, period))
        text += "：" + "，".join(parts)
    return text

def _env(name):
    return os.environ.get(name, "").strip()

def notify_pushplus(title, content):
    token = _env("PUSHPLUS_TOKEN")
    if not token:
        return False
    try:
        text = (content[:18000] + "\n...(已截断)") if len(content) > 18000 else content
        answer = post_json("https://www.pushplus.plus/send",
                           {"token": token, "title": title, "content": text, "template": "txt"})
        return answer.status_code == 200 and str(json_of(answer).get("code")) == "200"
    except Exception:
        return False

def notify_bark(title, content):
    endpoint = _env("BARK_URL").rstrip("/")
    if not endpoint:
        return False
    try:
        answer = post_json(endpoint, {"title": title, "body": content, "group": "ZCode"})
        return answer.status_code == 200 and json_of(answer).get("code") == 200
    except Exception:
        return False

def notify_wecom(title, content):
    hook = _env("WECOM_WEBHOOK")
    if not hook:
        return False
    if not hook.startswith("http"):
        hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + hook
    try:
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": ("%s\n%s" % (title, content))[:2000]}})
        return answer.status_code == 200 and json_of(answer).get("errcode") == 0
    except Exception:
        return False

def notify_dingtalk(title, content):
    hook = _env("DINGTALK_WEBHOOK")
    if not hook:
        return False
    try:
        secret = _env("DINGTALK_SECRET")
        if secret:
            stamp = str(int(time.time() * 1000))
            digest = hmac.new(secret.encode(), ("%s\n%s" % (stamp, secret)).encode(),
                              hashlib.sha256).digest()
            hook += ("&" if "?" in hook else "?") + "timestamp=%s&sign=%s" % (
                stamp, urllib.parse.quote(base64.b64encode(digest)))
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": "%s\n%s" % (title, content)}})
        return answer.status_code == 200 and json_of(answer).get("errcode") == 0
    except Exception:
        return False

def looks_like_jwt(value):
    value = (value or "").strip()
    return value.startswith("eyJ") or value.count(".") >= 2

def jwt_user_id(jwt):
    """从 JWT 载荷里取用户标识（激活事件上报用）；取不到返回空串。"""
    try:
        payload = jwt.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return ""
    for key in ("user_id", "userId", "uid", "sub", "id"):
        value = claims.get(key) if isinstance(claims, dict) else None
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    data = claims.get("data") if isinstance(claims, dict) else None
    if isinstance(data, dict):
        for key in ("id", "user_id", "uid"):
            value = data.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return ""

def account_lines(raw):
    return [line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith('#')]


def parse_account(line):
    first, sep, rest = line.partition('|')
    # 仅 JWT 可明确识别时接受备注前缀，避免吞掉验证码中的分隔符。
    if sep and not looks_like_jwt(first) and looks_like_jwt(rest.partition('|')[0]):
        token, sep, rest = rest.partition('|')
    else:
        token = first
    mid, _, captcha = rest.partition('|') if sep else ('', '', '')
    token, mid = token.strip(), mid.strip()
    captcha = captcha.strip() or _env('ZCODE_CAPTCHA_PARAM')
    SECRETS.extend([token, mid, captcha])
    if not token or not looks_like_jwt(token) or any(c in token for c in '\r\n&@ '):
        raise TaskError('账号格式错误：请每行填写一个套餐 JWT，可附带设备及验证码参数')
    if not mid and not DRY:
        # 只兼容读取，不再默认创建或改写设备文件。
        try:
            store = json.loads(Path(__file__).with_name('zcode_cn_devices.json').read_text())
            mid = store[hashlib.sha256(token.encode()).hexdigest()[:16]]['mid']
            if not isinstance(mid, str):
                mid = ''
        except Exception:
            mid = ''
    if not mid:
        mid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'zcode-cn:' + hashlib.sha256(token.encode()).hexdigest()))
    SECRETS.append(mid)
    return {'jwt': token, 'device_mid': mid, 'captcha': captcha, 'user_id': jwt_user_id(token)}


def verify_response(response, action):
    payload = json_of(response)
    code = payload.get('code')
    if response.status_code != 200 or type(code) is not int or code != 0:
        label = FAILURE_LABELS.get(code) if isinstance(code, int) else None
        # 只打印本地映射和 HTTP 状态，不信任服务器错误文本或任意业务字段。
        raise TaskError(action + '失败：' + (label or '业务响应未确认成功') + '（HTTP %d）' % response.status_code)
    if not isinstance(payload.get('data'), dict):
        raise TaskError(action + '响应缺少有效 data')
    data = payload['data']
    identities = [data.get('user'), data.get('account'), data]
    for identity in identities:
        if not isinstance(identity, dict):
            continue
        for key in ('nickname', 'username', 'display_name', 'displayName', 'public_uid', 'user_id', 'uid'):
            value = identity.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                log('👤 官方账号身份 ' + key + ': ' + safe(value, public_uid=key in ('public_uid', 'user_id', 'uid')))
    return payload


def run_account(account, args, index):
    stats = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failure': 0}
    started = time.monotonic()
    def stage(number, title, action=None):
        stamp = time.monotonic()
        stats['total'] += 1
        log('账号%d 阶段%d：%s' % (index, number, title))
        try:
            if action is None:
                stats['skipped'] += 1
                log('⏭️ 已跳过；耗时 %.2fs' % (time.monotonic() - stamp))
                return None
            result = action()
            stats['success'] += 1
            log('✅ 阶段完成；耗时 %.2fs' % (time.monotonic() - stamp))
            return result
        except Exception as error:
            stats['failure'] += 1
            msg = str(error) if isinstance(error, TaskError) else '处理异常（原始内容已隐藏）'
            log('❌ ' + safe(msg) + '；耗时 %.2fs' % (time.monotonic() - stamp))
            raise TaskError(msg) from None
    try:
        if DRY:
            stage(1, '断网参数预演', lambda: log('DRY_RUN_OK：参数已解析，未发送请求或写入设备文件'))
            stage(2, '激活事件预演（不发送）')
            stage(3, '套餐预览及领取预演（不发送）')
        else:
            if args.preview or _env('ZCODE_ACTIVATION') != '1':
                stage(1, '激活事件（默认关闭，预览模式始终关闭）')
            else:
                def activate():
                    if not account['user_id']:
                        raise TaskError('JWT 缺少用户标识，无法补报激活事件')
                    for event in ('app_launch', 'app_daily_active'):
                        response = request('POST', ORIGIN + EVENT_REPORT_PATH,
                                           body=activation_event_body(event, account['user_id'], account['device_mid']), timeout=10)
                        payload = json_of(response)
                        if response.status_code != 200 or type(payload.get('code')) is not int or payload['code'] != 0:
                            raise TaskError('激活事件未确认成功')
                        log('✅ ' + event + ' 已确认')
                # 激活失败仍继续预览和领取，最终保留失败退出码。
                try:
                    stage(1, '显式补报激活事件', activate)
                except TaskError:
                    pass
            def inspect():
                payload = verify_response(preview(account['jwt'], account['device_mid']), '套餐预览')
                raw = payload['data'].get('plans')
                if not isinstance(raw, list):
                    raise TaskError('套餐列表结构异常')
                plans = parse_plans(payload)
                for plan in plans:
                    log('套餐：' + safe(describe_plan(plan)) + '；有效期 ' + safe(format_time(plan['starts_at'])) + ' ~ ' + safe(format_time(plan['ends_at'])))
                log('✅ PREVIEW_SUCCESS：已验证套餐预览，套餐数 %d' % len(plans))
                return plans
            plans = stage(2, '读取可领套餐及权益', inspect)
            if args.preview:
                stage(3, '只读预览，未领取')
            else:
                def redeem():
                    if not plans:
                        raise TaskError('现在没有可领取的套餐，未确认领取成功')
                    selected = pick_plan(plans)
                    if selected is None:
                        raise TaskError('指定的 ZCODE_PLAN_ID 不在可领列表')
                    log('目标套餐：' + safe(describe_plan(selected)))
                    response = claim(account['jwt'], selected['plan_id'], account['device_mid'], account['captcha'])
                    body = verify_response(response, '套餐领取')
                    plan = body['data'].get('plan')
                    if not isinstance(plan, dict) or not plan:
                        raise TaskError('领取响应缺少有效套餐，未确认成功')
                    returned_id = first_text(plan.get('plan_id'), plan.get('planId'))
                    if returned_id and returned_id != selected['plan_id']:
                        raise TaskError('返回套餐与目标不一致')
                    log('✅ CLAIM_SUCCESS：领取成功；' + safe(selected['name']) + '（' + safe(format_time(plan.get('starts_at', plan.get('startsAt')))) + ' ~ ' + safe(format_time(plan.get('ends_at', plan.get('endsAt')))) + '）')
                stage(3, '领取套餐（不重试写请求）', redeem)
    except TaskError:
        pass
    stats['elapsedSeconds'] = round(time.monotonic() - started, 2)
    log(('账号%d 统计：' % index) + ('总任务 %(total)d，成功 %(success)d，已完成 %(alreadyComplete)d，跳过 %(skipped)d，失败 %(failure)d；耗时 %(elapsedSeconds).2fs' % stats))
    return stats


def deliver_notification(title, content, disabled=False):
    if disabled or _env('QINGLONG_NOTIFY').lower() in ('0', 'false', 'no', 'off'):
        log('⏭️ 通知已关闭')
        return 'disabled'
    if DRY:
        log('✅ 通知预演：' + content)
        return 'simulated'
    # 子进程限制通知模块导入及发送耗时；不暴露其 stdout/stderr。
    dirs = [Path(__file__).parent]
    configured = _env('QINGLONG_NOTIFY_DIR')
    if configured:
        dirs.append(Path(configured))
    dirs += [Path('/ql/data/scripts'), Path('/ql/scripts')]
    candidates = [p / 'notify.py' for p in dirs]
    spec = importlib.util.find_spec('notify')
    if spec and spec.origin:
        candidates.insert(0, Path(spec.origin))
    runner = ('import importlib.util,json,sys; p,t,c=json.load(sys.stdin); '
              's=importlib.util.spec_from_file_location("notify",p); m=importlib.util.module_from_spec(s); '
              'sys.path.insert(0,str(__import__("pathlib").Path(p).parent)); s.loader.exec_module(m); '
              'r=m.send(t,c); sys.exit(1 if r is False else 0)')
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        try:
            result = subprocess.run([sys.executable, '-c', runner], input=json.dumps([str(path), title, content]),
                                    text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if result.returncode == 0:
                log('✅ 青龙通知已调用')
                return 'sent'
        except Exception:
            pass
    for handler in (notify_pushplus, notify_bark, notify_wecom, notify_dingtalk):
        if handler(title, content):
            log('✅ 兼容推送已发送')
            return 'sent'
    # 保留原 QL_URL/QL_TOKEN 配置；安全传输且只通知脱敏统计。
    endpoint, token = _env('QL_URL').rstrip('/'), _env('QL_TOKEN')
    if endpoint and token:
        try:
            response = post_json(endpoint + '/api/system/notify?' + urllib.parse.urlencode({'token': token}),
                                 {'title': title, 'content': content}, timeout=15)
            if response.status_code == 200 and str(response.json().get('code')) in ('0', '200'):
                log('✅ 青龙接口通知已发送')
                return 'sent'
        except Exception:
            pass
    log('⚠️ 通知不可用或发送失败；保留业务退出码')
    return 'unavailable'


def main():
    global DRY
    DRY = _env('ZCODE_CN_DRY_RUN').lower() in ('1', 'true', 'yes', 'on')
    started = time.monotonic()
    log('======== ZCode 国内版领套餐 ========')
    log('开始时间：' + beijing_now().isoformat(timespec='seconds'))
    log('模式：' + ('断网预演' if DRY else '实际执行'))
    lines = account_lines(os.environ.get('ZCODE_CN_TOKENS', ''))
    log('账号总数：%d' % len(lines))
    # 收集敏感值，包括可选推送凭据；不记录备注，避免备注含凭据。
    for name in ('ZCODE_CAPTCHA_PARAM', 'PUSHPLUS_TOKEN', 'BARK_URL', 'WECOM_WEBHOOK',
                 'DINGTALK_WEBHOOK', 'DINGTALK_SECRET', 'QL_TOKEN'):
        SECRETS.append(_env(name))
    results, config_error, no_notify = [], False, '--no-notify' in sys.argv[1:]
    parser = argparse.ArgumentParser(description='ZCode 国内版套餐领取')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--only', type=int)
    parser.add_argument('--no-notify', action='store_true')
    try:
        # 避免 argparse 错误日志回显未知参数里的敏感值。
        class QuietParser(argparse.ArgumentParser):
            def error(self, message):
                raise TaskError('命令参数错误：支持 --preview、--only 正整数、--no-notify')
        parser.__class__ = QuietParser
        args = parser.parse_args()
        if not lines:
            raise TaskError('未配置 ZCODE_CN_TOKENS：每行一个国内版套餐 JWT')
        if args.only is not None and not 1 <= args.only <= len(lines):
            raise TaskError('--only 超出账号范围')
        if _env('ZCODE_ACTIVATION') not in ('', '0', '1'):
            raise TaskError('ZCODE_ACTIVATION 仅支持 0 或 1')
        for index, line in enumerate(lines, 1):
            if args.only is not None and index != args.only:
                continue
            log('-------- 账号%d --------' % index)
            try:
                account = parse_account(line)
                stats = run_account(account, args, index)
            except Exception as error:
                log('❌ 阶段0：' + (safe(error) if isinstance(error, TaskError) else '参数处理异常'))
                stats = {'total': 1, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failure': 1, 'elapsedSeconds': 0}
                log('账号%d 统计：总任务1，成功0，已完成0，跳过0，失败1；耗时0s' % index)
            results.append({'account': index, **stats})
    except TaskError as error:
        config_error = True
        log('❌ 阶段0：配置检查失败；' + safe(error) + '；耗时 %.2fs' % (time.monotonic() - started))
    failure = sum(r['failure'] > 0 for r in results)
    success = len(results) - failure
    exit_code = 1 if config_error or failure else 0
    status = 'configuration-error' if config_error else ('partial-failure' if failure and success else 'failure' if failure else 'dry-run' if DRY else 'success')
    task_stats = {key: sum(r[key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    summary = {'status': status, 'mode': 'dry-run' if DRY else 'live', 'accountCount': len(lines),
               'processedAccounts': len(results), 'successAccounts': success, 'failedAccounts': failure,
               'configurationError': config_error, 'tasks': task_stats, 'accounts': results, 'exitCode': exit_code}
    log('------------------------------------')
    log('任务统计：账号总数 %d，处理 %d，成功 %d，失败 %d' % (len(lines), len(results), success, failure))
    log('子任务统计：' + json.dumps(task_stats, ensure_ascii=False))
    content = '账号总数 %d，处理 %d，成功 %d，失败 %d；配置错误 %s；状态 %s' % (len(lines), len(results), success, failure, '是' if config_error else '否', status)
    try:
        summary['notification'] = deliver_notification('ZCode 国内版领套餐', content, no_notify)
    except Exception:
        summary['notification'] = 'unavailable'
        log('⚠️ 通知异常；保留业务退出码')
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['finishedAt'] = beijing_now().isoformat(timespec='seconds')
    log('总耗时 %.2fs；完成时间 %s；最终状态 %s' % (summary['elapsedSeconds'], summary['finishedAt'], status))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
