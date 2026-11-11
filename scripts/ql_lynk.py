#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 领克签到与账户任务
# cron: 56 10 * * *
# SPDX-License-Identifier: MIT
# MIT License
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
# 来源: vongzh/lynk-auto-sign, ql_lynk.py (MIT)
# 保留上游归属；上游未附独立版权声明。
# [FORK] License 公钥与校验逻辑已移除 — 自用版无需授权, 直接放行.
# [FORK] License 校验与反篡改检测已全部移除 — 自用版直接放行, 不读 license.txt, 不依赖 cryptography
"""领克签到维护版（Python 3 标准库，无安装引导）。
配置 LYNK_ACCOUNTS，每行 refreshToken|deviceId，仅按第一个 | 拆分。
在自己的领克 App 登录抓包中，从 app-services.lynkco.com.cn 的
mobileCodeLogin 响应取得 refreshToken，从登录 URL 的 deviceId 参数取得设备 ID。
兼容 LYNK_REFRESH_TOKEN + LYNK_DEVICE_ID，以及命令行 --token/--device-id。
缓存保存续期结果（权限 0600），不改写青龙环境文件、不打印任何令牌。
轮换后的令牌保留在该账号缓存中；清缓存前应自行通过 App 重新取得有效凭据。
LYNK_AUTO_SHARE 默认关闭；开启后 LYNK_TOKEN_B 每行 token|deviceId，
B 账号只做分享点击，不自动签到。只有 token 的旧配置使用主账号 deviceId。
--token-b 同样仅接受换行，不再接受逗号多账号。
默认仅生成手工分享链接；该链接含公开分享码，不包含账号登录凭据。
不发布帖子、评论或分享文案，随机文案策略不适用。
LYNK_DRY_RUN=1 时不读写缓存、不请求服务或通知服务。
通知遵守 QINGLONG_NOTIFY 和 QINGLONG_NOTIFY_SCRIPTS，默认列入本任务。
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
        _ql_notify_identities = ('c537807373d74e3f', 'scripts/ql_lynk.py', 'ql_lynk.py', 'ql_lynk')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import os
import sys
import json
import time
import uuid
import hmac
import base64
import hashlib
import argparse
import re
import fnmatch
import importlib.util
import importlib
import contextlib
import io
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

API_BASE = "https://app-api-gw-toc.lynkco.com"
OAUTH_BASE = "https://app-services.lynkco.com.cn"
REFRESH_URL = OAUTH_BASE + "/auth/login/refresh"

# H5 签名密钥 (查询类接口仍可用; 签到写接口已对该 AppKey 撤销授权)
CA_KEY = os.environ.get("LYNK_H5_APP_KEY", "204644386").strip() or "204644386"
CA_SECRET = os.environ.get("LYNK_H5_APP_SECRET", "QCl7udM3PB9cOIOwquwPglikFQnzJRsX").strip() or "QCl7udM3PB9cOIOwquwPglikFQnzJRsX"
SIG_HDRS = "X-Ca-Key,X-Ca-Timestamp,X-Ca-Nonce,X-Ca-Signature-Method"

# App 原生签名密钥 (签到 /up/api/v1/user/sign/upgrade 必需; H5 Key 会 403 Unauthorized Consumer)
# 可用环境变量覆盖; 默认值为 App 内置常量 (非个人隐私)
NATIVE_APP_KEY = os.environ.get("LYNK_NATIVE_APP_KEY", "203760416").strip() or "203760416"
NATIVE_APP_SECRET = os.environ.get("LYNK_NATIVE_APP_SECRET", "e1msl9aqd101gfcjpo873hrs5jg752og").strip() or "e1msl9aqd101gfcjpo873hrs5jg752og"
NATIVE_SIG_HDRS = "x-ca-nonce,x-ca-key,x-ca-timestamp"
NATIVE_ANDROID_UA = "ALIYUN-ANDROID-UA"

# 2026-07 起真正执行签到的接口改为 sign/upgrade + 原生签名; 旧 /user/sign 对 H5 Key 返回 403
EP_SIGN = "/up/api/v1/user/sign/upgrade"
EP_SIGN_DAY = "/up/api/v1/user/sign/day/info"           # 今日是否已签 (signStatus=1)
EP_SIGN_INFO = "/up/api/v1/userReward/getContinueDaysAndSignCard"
EP_ENERGY = "/app/energy/myEnergy"
EP_TASKS = "/up/api/v1/userReward/getTaskList"           # 签到任务进度 (连续7天/月度/季度/年度)
EP_GROWTH = "/app/energy/my/growth"                       # 成长等级 + 成长值

# 分享相关端点 (从 lynk_sign.py 迁移)
EP_SHARE_CHECK = "/app/v1/task/shareContentContectCheck"
EP_SHARE_REPORT = "/app/v1/task/shareContentContectReporting"
EP_SHARE_LOOKUP = "/app/v1/task/shareCodeToUserId"
EP_GET_SHARE_CODE = "/app/v1/task/getShareCode"

# H5 分享链接模板 (手工复制到微信发, 别人点击后给主账号加 5 能量体)
SHARE_URL_TEMPLATE = "https://h5.lynkco.com/app-h5/dist/web/pages/exploration/article/index.html?id={cid}&isShare={is_share}&shareCode={code}"

APP_CODE = "3fa3314998bd4195a9fe2df3e85e6a12"
DEFAULT_SHARE_CONTENT_ID = "2072260486405246976"

# [FORK] License 公钥与校验逻辑已移除 — 自用版无需授权, 直接放行.



def gen_nonce():
    return str(uuid.uuid4()).upper()


def build_sig(method, path, params=None):
    """H5 签名 (查询类接口: 能量体/任务/连续天数/分享等)"""
    ts = str(int(time.time() * 1000))
    nonce = gen_nonce()
    sh = {
        "X-Ca-Key": CA_KEY,
        "X-Ca-Nonce": nonce,
        "X-Ca-Signature-Method": "HmacSHA256",
        "X-Ca-Timestamp": ts,
    }
    url = path
    if params:
        q = urlencode(sorted(params.items()))
        url = f"{path}?{q}" if q else path
    parts = [method.upper(), "*/*", "", "application/json", ""]
    for k, v in sh.items():
        parts.append(f"{k}:{v}")
    parts.append(url)
    sig = base64.b64encode(
        hmac.new(CA_SECRET.encode(), "\n".join(parts).encode(), hashlib.sha256).digest()
    ).decode()
    return {
        **sh,
        "X-Ca-Signature-Headers": SIG_HDRS,
        "X-Ca-Signature": sig,
        "Accept": "*/*",
    }


def build_native_sig(method, path, body=None):
    """App 原生 SDK 签名 (签到 upgrade 等写接口必需).

    对照阿里云 SignUtil.buildStringToSign:
      METHOD\\n Accept\\n Content-MD5\\n Content-Type\\n Date\\n
      (x-ca-* 头按字典序, 每行 name:value\\n) path

    POST body 即使是空对象 b"{}" 也必须算 Content-MD5 并放入签名与请求头.
    """
    nonce = str(uuid.uuid4())
    timestamp = str(int(time.time() * 1000))
    date_str = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    accept = "application/json; charset=utf-8"
    content_type = "application/json; charset=utf-8"
    content_md5 = ""
    if body:
        content_md5 = base64.b64encode(hashlib.md5(body).digest()).decode()

    ca_headers = {
        "x-ca-key": NATIVE_APP_KEY,
        "x-ca-nonce": nonce,
        "x-ca-timestamp": timestamp,
    }
    parts = [method.upper(), "\n", accept, "\n", content_md5, "\n", content_type, "\n", date_str, "\n"]
    for k in sorted(ca_headers.keys()):
        parts.append(f"{k}:{ca_headers[k]}")
        parts.append("\n")
    parts.append(path)
    string_to_sign = "".join(parts)
    digest = hmac.new(NATIVE_APP_SECRET.encode(), string_to_sign.encode(), hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode()

    result = {
        **ca_headers,
        "x-ca-signature-headers": NATIVE_SIG_HDRS,
        "x-ca-signature": signature,
        "date": date_str,
        "accept": accept,
        "content-type": content_type,
    }
    if content_md5:
        result["content-md5"] = content_md5
    return result



TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
DRY = os.getenv('LYNK_DRY_RUN', '').strip().lower() in TRUE
TITLE = '领克签到与账户任务'
CATALOG = 'c537807373d74e3f'


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


class TaskError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 不向重定向目标传递凭据


def http(method, url, headers=None, body=None, timeout=20):
    if DRY:
        raise TaskError('预演禁止网络访问')
    try:
        req = Request(url, data=body, headers=headers or {}, method=method)
        with build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('响应超出限制')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise TaskError('响应结构不符合契约')
            return result
    except TaskError:
        raise
    except Exception:
        # urllib 异常常包含携带令牌的 URL，禁止输出异常内容
        raise TaskError('网络、HTTP 或响应解析失败') from None


def api_ok(result):
    return isinstance(result, dict) and (result.get('success') is True or str(result.get('code')) in ('success', '200'))


def data_ok(result):
    if not api_ok(result):
        raise TaskError('接口未返回明确业务成功')
    return result.get('data')


def obj(value):
    if not isinstance(value, dict):
        raise TaskError('响应字段结构错误')
    return value


def signed_call(method, path, token, body=None, native=False):
    raw = json.dumps(body or {}, ensure_ascii=False, separators=(',', ':')).encode() if method == 'POST' else None
    headers = {'token': token}
    if native:
        headers.update(build_native_sig(method, path, raw))
        headers.update({'ca_version': '1', 'x-requiretoken': 'false', 'User-Agent': NATIVE_ANDROID_UA})
    else:
        headers.update(build_sig(method, path))
        headers['content-type'] = 'application/json'
    # 有副作用的请求不自动重试，避免重复记账
    return http(method, API_BASE + path, headers, raw)


def expiry(value):
    try:
        if isinstance(value, (int, float)):
            return float(value) / 1000 if value > 1e12 else float(value)
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
        return dt.timestamp()
    except Exception:
        return 0


def cache_path(token, device):
    # 多账号独立缓存，不在文件名中暴露凭据；无共享 /tmp 明文缓存
    key = hashlib.sha256((token + '\0' + device).encode()).hexdigest()
    return Path(os.getenv('LYNK_CACHE_DIR', str(Path.home() / '.cache' / 'lynk-sign'))) / (key + '.json')


def read_cache(path):
    try:
        if path.is_symlink() or path.stat().st_mode & 0o077:
            return {}
        return obj(json.loads(path.read_text()))
    except Exception:
        return {}


def save_cache(path, entry):
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp = tempfile.mkstemp(prefix='.lynk-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(entry, stream)
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    except Exception:
        raise TaskError('无法安全保存轮换令牌缓存，请检查缓存目录权限') from None


def access_token(token, device, no_cache=False):
    path = cache_path(token, device)
    entry = read_cache(path)  # 强制续期仍使用缓存中的最新轮换凭据
    if not no_cache and entry.get('access') and expiry(entry.get('expires')) > time.time() + 60:
        log('✅ 令牌缓存命中')
        return entry['access']
    rt = entry.get('refresh') or token
    params = {'refreshToken': rt, 'deviceId': device, 'deviceType': 'IOS', 'appVersion': '4.2.0'}
    headers = {
        'Authorization': f'APPCODE {APP_CODE}', 'accept': 'application/json',
        'content-type': 'application/json; charset=UTF-8', 'publicplatform': 'iOS',
        'user-agent': 'CA_iOS_SDK_2.0', 'token': '', 'gl_dev_id': device,
        'appversioncode': '4.2.0', 'appversionname': '40200106',
        'gl_app_version': '4.2.0', 'gl_app_build': '40200106', 'x-ca-version': '1',
    }
    try:
        response = http('GET', REFRESH_URL + '?' + urlencode(params), headers)
        dto = obj(obj(data_ok(response)).get('centerTokenDto'))
        at = dto.get('token')
        if not isinstance(at, str) or not at:
            raise TaskError('续期响应缺少令牌')
    except TaskError:
        # 保留上游 accessToken 兼容回退，但必须通过业务查询验证
        data_ok(signed_call('GET', EP_SIGN_INFO, token))
        log('✅ 使用已验证的短期 accessToken 兼容模式')
        return token
    SECRETS.update((at, dto.get('refreshToken') or rt))
    save_cache(path, {'access': at, 'refresh': dto.get('refreshToken') or rt, 'expires': dto.get('expireAt')})
    log('✅ 令牌续期成功，轮换结果已安全缓存')
    return at


def identity(data):
    # 仅读取公开身份字段；不输出电话、设备或会话字段
    for key in ('nickname', 'nickName', 'username', 'userName', 'displayName', 'publicUid'):
        value = data.get(key)
        if isinstance(value, (str, int)) and str(value):
            log(f'账号身份：{safe_public(value)}')


SECRETS = set()


def safe_public(value):
    text = str(value).replace('\r', ' ').replace('\n', ' ')
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return text


def parse_accounts(raw, fallback_device=None):
    accounts = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        token, sep, device = line.strip().partition('|')
        device = device if sep else (fallback_device or '')
        SECRETS.update((token, device))
        # 每行独立记录错误，不能让坏账号阻塞其余账号
        accounts.append((token, device, bool(token and device)))
    return accounts


def get_signed(token):
    status = obj(data_ok(signed_call('GET', EP_SIGN_DAY, token))).get('signStatus')
    if status not in (0, 1, '0', '1', False, True):
        raise TaskError('今日签到状态字段缺失或未知')
    return str(status) in ('1', 'True')


def share(token, content, code):
    before = obj(data_ok(signed_call('GET', EP_ENERGY, token))).get('point')
    data_ok(signed_call('POST', EP_SHARE_LOOKUP, token, {'shareCode': code}))
    data_ok(signed_call('POST', EP_SHARE_CHECK, token, {'contentId': content, 'shareCode': code}))
    data_ok(signed_call('POST', EP_SHARE_REPORT, token, {'contentId': content, 'shareCode': code}))
    time.sleep(2)
    after = obj(data_ok(signed_call('GET', EP_ENERGY, token))).get('point')
    # 不能仅凭“已结束”或 report 成功文案宣称得分
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)) or after <= before:
        raise TaskError('分享上报后未验证到能量体增长')
    log(f'✅ 分享已验证，能量体增加 {after - before}')


def run_account(index, token, device, valid, args, helpers):
    started = time.monotonic()
    stats = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failure': 0}
    def stage(number, name, action):
        stats['total'] += 1
        tick = time.monotonic()
        log(f'账号 {index} [{number}] {name}')
        try:
            value = action()
            stats['success'] += 1
            log(f'✅ {name}完成，耗时 {time.monotonic() - tick:.2f} 秒')
            return value
        except Exception:
            stats['failure'] += 1
            log(f'❌ {name}失败（配置、网络或业务校验未通过），耗时 {time.monotonic() - tick:.2f} 秒')
            return None
    if not valid:
        stage(1, '凭据检查', lambda: (_ for _ in ()).throw(TaskError('账号需要 token|deviceId')))
    elif DRY:
        for n, name in enumerate(('凭据格式检查', '令牌续期与缓存计划', '签到状态与签到计划', '能量体、成长等级与任务进度计划', '分享链接与可选分享计划'), 1):
            stage(n, name, lambda: log('⏭️ 断网预演：不请求接口、不读写缓存、不改变账号状态'))
        if args.auto_share and (not helpers or any(not h[2] for h in helpers)):
            stage(6, '分享账号配置检查', lambda: (_ for _ in ()).throw(TaskError('分享账号未配置完整')))
        log('DRY_RUN_OK：配置预演通过' if stats['failure'] == 0 else '预演配置失败')
    else:
        at = stage(1, '获取令牌', lambda: access_token(token, device, args.no_cache))
        if at:
            SECRETS.add(at)
            def sign():
                if get_signed(at):
                    stats['alreadyComplete'] += 1
                    log('☑️ 今日已签到')
                    return
                try:
                    data_ok(signed_call('POST', EP_SIGN, at, native=True))
                except TaskError:
                    # 请求结果不明时只读回查，不重复写入
                    if not get_signed(at):
                        raise
                    stats['alreadyComplete'] += 1
                    log('☑️ 回查确认今日已签到')
                    return
                if not get_signed(at):
                    raise TaskError('签到后状态未确认')
                log('✅ 签到成功（已回查确认）')
            stage(2, '今日签到', sign)
            def info():
                data = obj(data_ok(signed_call('GET', EP_SIGN_INFO, at)))
                identity(data)
                days = data.get('continuousSignDays', data.get('serialDays', data.get('continueDays', 0)))
                log(f"连续签到 {safe_public(days)} 天；补签卡 {safe_public(data.get('signCardNumber', 0))} 张")
            stage(3, '连续签到与补签卡', info)
            def energy():
                data = obj(data_ok(signed_call('GET', EP_ENERGY, at)))
                identity(data)
                log(f"能量体 {safe_public(data.get('point', '-'))}；累计获得 {safe_public(data.get('incomePoint', '-'))}")
            stage(4, '能量体查询', energy)
            def growth():
                data = obj(data_ok(signed_call('GET', EP_GROWTH, at)))
                identity(data)
                level = obj(data.get('accountLevelVo'))
                log(f"等级 {safe_public(level.get('name', '-'))}；成长值 {safe_public(level.get('growth', '-'))}")
            stage(5, '成长等级查询', growth)
            def tasks():
                data = data_ok(signed_call('GET', EP_TASKS, at))
                if not isinstance(data, list):
                    raise TaskError('任务列表结构变化')
                for task in data:
                    task = obj(task)
                    name = str(task.get('taskName', '?'))
                    total = re.search(r'(\d+)天', name)
                    progress = str(task.get('taskProcess', '?')) + (' / ' + total[1] if total else '')
                    log(f"任务 {safe_public(name)}：{safe_public(progress)}；奖励 {safe_public(', '.join(map(str, task.get('rewardContent') or [])))}")
            stage(6, '签到任务进度', tasks)
            def code_action():
                code = data_ok(signed_call('GET', EP_GET_SHARE_CODE, at))
                if not isinstance(code, str) or not re.fullmatch(r'[a-fA-F0-9]{32,}', code):
                    raise TaskError('分享码字段无效')
                route = quote(f'lynkco://wx/?routeUrl=/pages/exploration/article/index.js?id={args.content_id}', safe='')
                log('手工分享链接：' + SHARE_URL_TEMPLATE.format(cid=args.content_id, is_share=route, code=code))
                return code
            code = stage(7, '生成手工分享链接', code_action)
            if args.auto_share:
                if not helpers or not code:
                    stage(8, '自动分享前提检查', lambda: (_ for _ in ()).throw(TaskError('缺少分享账号或分享码')))
                else:
                    for j, (bt, bd, bv) in enumerate(helpers, 1):
                        def click(bt=bt, bd=bd, bv=bv):
                            if not bv:
                                raise TaskError('分享账号配置错误')
                            bat = access_token(bt, bd, args.no_cache)
                            SECRETS.add(bat)
                            share(bat, args.content_id, code)
                        stage(f'8.{j}', f'分享账号 {j} 点击核验', click)
            else:
                stats['skipped'] += 1
                stats['total'] += 1
                log('⏭️ 自动分享默认关闭')
    stats['success'] -= stats['alreadyComplete']
    result = {'account': index, **stats, 'elapsedSeconds': round(time.monotonic() - started, 2)}
    log(f'账号 {index} 统计：' + json.dumps(result, ensure_ascii=False))
    return result


def notify_enabled():
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    if switch != 'auto':
        return False
    if os.getenv('LYNK_USE_QL_NOTIFY', '1').lower() in FALSE:
        return False
    selection = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if selection is None:
        return True
    names = (CATALOG, 'ql_lynk.py', 'candidate.py', Path(__file__).name, 'checkin/ql_lynk.py', 'scripts/ql_lynk.py')
    return any(fnmatch.fnmatch(name, pattern) for pattern in re.split(r'[,;\s]+', selection.strip()) if pattern for name in names)


def notify_summary(body):
    if not notify_enabled():
        return '已关闭'
    if DRY:
        return '断网预演，已模拟通知'
    # 在有界子进程中执行面板通知，隔离通知模块的原始输出和异常。
    code = r"""
import os, sys, importlib, importlib.util
from pathlib import Path
try:
    import notify
    notify.send(sys.argv[1], sys.argv[2])
    sys.exit(0)
except Exception:
    pass
for directory in [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']:
    p = Path(directory) / 'notify.py'
    if directory and p.is_file():
        try:
            spec = importlib.util.spec_from_file_location('lynk_notify', p)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send(sys.argv[1], sys.argv[2])
            sys.exit(0)
        except Exception:
            pass
sys.exit(1)
"""
    delivered = False
    try:
        result = subprocess.run([sys.executable, '-c', code, TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        delivered = result.returncode == 0
    except Exception:
        pass
    if not delivered:
        for directory in [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']:
            p = Path(directory) / 'sendNotify.js'
            if directory and p.is_file():
                try:
                    js = 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))'
                    result = subprocess.run(['node', '-e', js, str(p), TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                    if result.returncode == 0:
                        delivered = True
                        break
                except Exception:
                    pass
    extra = direct_notifications(body)
    return ('已发送' if delivered else '青龙通知不可用或失败，保留业务退出码') + extra


def direct_notifications(body):
    """保留上游自定义通知渠道；遵循全局开关，仅发送脱敏统计。"""
    count, failures = 0, 0
    def send(url, payload=None, method='POST'):
        nonlocal count, failures
        count += 1
        try:
            if not url.startswith('https://'):
                raise TaskError('通知仅支持 HTTPS')
            raw = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
            http(method, url, {'content-type': 'application/json'}, raw, timeout=10)
        except Exception:
            failures += 1
    for env, payload in (
        ('PUSH_WECOM_WEBHOOK', {'msgtype': 'markdown', 'markdown': {'content': f'**{TITLE}**\n{body}'}}),
        ('PUSH_DINGTALK_WEBHOOK', {'msgtype': 'markdown', 'markdown': {'title': TITLE, 'text': body}}),
        ('PUSH_FEISHU_WEBHOOK', {'msg_type': 'text', 'content': {'text': TITLE + '\n' + body}}),
    ):
        if os.getenv(env):
            send(os.environ[env], payload)
    if os.getenv('PUSH_TG_BOT_TOKEN') and os.getenv('PUSH_TG_CHAT_ID'):
        send('https://api.telegram.org/bot' + os.environ['PUSH_TG_BOT_TOKEN'] + '/sendMessage', {'chat_id': os.environ['PUSH_TG_CHAT_ID'], 'text': TITLE + '\n' + body})
    if os.getenv('PUSH_SERVERCHAN_KEY'):
        send('https://sctapi.ftqq.com/' + os.environ['PUSH_SERVERCHAN_KEY'] + '.send', {'title': TITLE, 'desp': body})
    if os.getenv('PUSH_PUSHPLUS_TOKEN'):
        send('https://www.pushplus.plus/send', {'token': os.environ['PUSH_PUSHPLUS_TOKEN'], 'title': TITLE, 'content': body, 'template': 'markdown'})
    if os.getenv('PUSH_BARK_URL'):
        url = os.environ['PUSH_BARK_URL'].strip()
        if not url.startswith(('https://', 'http://')):
            url = 'https://api.day.app/' + url
        sep = '&' if '?' in url else '?'
        send(url + sep + urlencode({'title': TITLE, 'body': body}), method='GET')
    return f'；额外渠道尝试 {count}，失败 {failures}' if count else ''


def main():
    started = time.monotonic()
    log('=' * 48)
    log(TITLE + f' | 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log('模式：' + ('断网预演' if DRY else '正式执行'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token')
    parser.add_argument('--device-id')
    parser.add_argument('--token-b')
    parser.add_argument('--content-id')
    parser.add_argument('--auto-share', action='store_true')
    parser.add_argument('--no-cache', action='store_true')
    parser.add_argument('--clear-cache', action='store_true')
    parser.add_argument('--quiet', action='store_true', help='兼容参数，所有模式均不打印原始响应')
    accounts, results, configuration_error = [], [], False
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            args = parser.parse_args()
        device = args.device_id or os.getenv('LYNK_DEVICE_ID', '')
        raw = (args.token if args.token is not None else os.getenv('LYNK_ACCOUNTS', '') or os.getenv('LYNK_REFRESH_TOKEN', ''))
        accounts = parse_accounts(raw, device)
        helpers_raw = args.token_b if args.token_b is not None else os.getenv('LYNK_TOKEN_B', '')
        args.auto_share = args.auto_share or os.getenv('LYNK_AUTO_SHARE', '').lower() in TRUE
        args.content_id = args.content_id or os.getenv('LYNK_SHARE_CONTENT_ID', DEFAULT_SHARE_CONTENT_ID)
        if not re.fullmatch(r'\d+', args.content_id):
            raise TaskError('LYNK_SHARE_CONTENT_ID 必须为文章数字编号')
        log(f'账号总数：{len(accounts)}')
        if not accounts:
            raise TaskError('请配置 LYNK_ACCOUNTS，每行 token|deviceId')
        if args.clear_cache:
            for token, dev, valid in accounts:
                if not valid:
                    raise TaskError('清缓存需要完整账号配置')
                if not DRY:
                    cache_path(token, dev).unlink(missing_ok=True)
            log('缓存清理' + ('已模拟' if DRY else '完成；轮换凭据一并清除，后续请确保输入凭据有效'))
        else:
            for i, (token, dev, valid) in enumerate(accounts, 1):
                helpers = parse_accounts(helpers_raw, dev)
                results.append(run_account(i, token, dev, valid, args, helpers))
            configuration_error = any(not account[2] for account in accounts)
    except (Exception, SystemExit) as exc:
        configuration_error = True
        # 不回显异常和 argparse 输入，可能包含凭据
        log('❌ 配置错误或执行中断，请核对帮助中的环境变量格式')
    failed = sum(r['failure'] > 0 for r in results)
    success = sum(r['failure'] == 0 for r in results)
    status = 'configuration-error' if configuration_error else ('partial-failure' if failed and success else 'failure' if failed else 'dry-run' if DRY else 'success')
    exit_code = 1 if configuration_error or failed else 0
    totals = {key: sum(r[key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    body = f'状态：{status}；账号总数 {len(accounts)}；成功 {success}；失败 {failed + (1 if configuration_error and not failed else 0)}；子任务 {totals["total"]}；子任务失败 {totals["failure"]}'
    notification = notify_summary(body)
    log('-' * 48)
    log(body)
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log('通知状态：' + notification)
    log(f'完成时间 {datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {time.monotonic() - started:.2f} 秒；最终状态 {status}')
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'dryRun': DRY, 'accountCount': len(accounts), 'successCount': success, 'failureCount': failed, 'configurationError': configuration_error, 'tasks': totals, 'accounts': results, 'notification': notification, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
