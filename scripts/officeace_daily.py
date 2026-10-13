#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: OfficeAce 果办每日奖励
# cron: 0 9 * * *
# License: MIT
# 原始来源: L0NE-6/OfficeAce-Daily, officeace_daily.py
# 参考: officeace_get_token.py（仅采纳凭据获取说明，不读取桌面配置）
"""OfficeAce（华为云果办 / OfficeClaw）每日签到维护版。

每日领取当天奖励和一次性新人礼；--query 只查询，--only N 选择账号。
OFFICEACE_TOKENS 每个非空行一个账号：AK|SK|security_token|project_id|base_url，
兼容 备注|AK|SK|security_token|project_id|base_url。不支持 & 分隔账号。
也接受单账号 OFFICEACE_AK/SK/STS/PROJECT_ID/BASE_URL。
请从已登录果办客户端或控制台的授权控制面请求取得同一账号的临时凭据、
项目 ID 和网关地址；临时凭据上游说明约两小时有效，请运行前刷新。
桌面 models.json 中的 Basic 网关 key/secret 仅用于转发，不能用于签到。
默认领取奖励；不发帖、不消费积分、不更改账号配置。
OFFICEACE_DRY_RUN=1 完全离线，只验证配置、签名和任务计划。
OFFICEACE_RETRIES 默认 2（首次之外的重试次数，最大 5）。
QINGLONG_NOTIFY 默认 1；NO_NOTIFY=1 兼容关闭通知。
支持 QYWX_TOKEN/WECHAT_WEBHOOK、PLUSPLUS_TOKEN 的可选兼容推送。
Python 3.8+，业务 HTTP 与签名仅用标准库，通知组件可选。
"""
import argparse
import hashlib
import hmac as _hmaclib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 20
MAX_RESPONSE = 1048576


def log(message):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), message), flush=True)


class TaskError(Exception):
    pass


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse 的默认错误包含原始输入，未知参数可能误带凭据。
        raise TaskError('命令行参数错误；支持 --query 与 --only 正整数')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("拒绝重定向，避免凭据传往其他地址")


def enabled(name):
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


SDK_ALGORITHM = "SDK-HMAC-SHA256"
V11_ALGORITHM = "V11-HMAC-SHA256"
SCOPE_SERVICE = "apic"
EMPTY_BODY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
DEFAULT_REGION = "cn-southwest-2"

_UNRESERVED = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~")


def _encode_component(data):
    out = []
    for b in data:
        if b in _UNRESERVED:
            out.append(chr(b))
        else:
            out.append("%%%02X" % b)
    return "".join(out)


def _unhex(a, b):
    digits = "0123456789abcdef"
    la = digits.find(chr(a).lower())
    lb = digits.find(chr(b).lower())
    if la < 0 or lb < 0:
        return None
    return (la << 4) | lb


def _decode_component(text):
    raw = text.encode("utf-8")
    out = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] == 0x25 and i + 2 < n:
            hi = _unhex(raw[i + 1], raw[i + 2])
            if hi is not None:
                out.append(hi)
                i += 3
                continue
        out.append(raw[i])
        i += 1
    return bytes(out)


def _decode_form(text):
    return _decode_component(text.replace("+", " ")).decode("utf-8", "replace")


def _canonical_uri(path):
    path = path or "/"
    escaped = "/".join(_encode_component(_decode_component(seg)) for seg in path.split("/"))
    return escaped if escaped.endswith("/") else escaped + "/"


def _canonical_query(raw_query):
    if not raw_query:
        return ""
    pairs = []
    for part in raw_query.split("&"):
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
        else:
            key, value = part, ""
        pairs.append((_decode_form(key), _decode_form(value)))
    pairs.sort(key=lambda kv: (kv[0], kv[1]))
    return "&".join("%s=%s" % (_encode_component(k.encode()), _encode_component(v.encode()))
                    for k, v in pairs)


def _split_path_query(url):
    if "://" not in url:
        raise ValueError("地址缺少 scheme：%s" % url)
    rest = url.split("://", 1)[1]
    rest = rest.split("#", 1)[0]
    path_query = rest[rest.index("/"):] if "/" in rest else "/"
    if "?" in path_query:
        path, query = path_query.split("?", 1)
    else:
        path, query = path_query, ""
    return path, query


def _authority_of(url):
    rest = url.split("://", 1)[1]
    cut = len(rest)
    for ch in ("/", "?", "#"):
        idx = rest.find(ch)
        if idx >= 0:
            cut = min(cut, idx)
    return rest[:cut].rsplit("@", 1)[-1]


def _sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _hmac_raw(key, message):
    return _hmaclib.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _hmac_hex(key, message):
    return _hmaclib.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


class Credential:
    def __init__(self, access_key_id, secret_access_key, security_token="", project_id=""):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.security_token = security_token
        self.project_id = project_id


def sign(credential, method, url, headers=None, body=b"", algorithm=V11_ALGORITHM,
         region=DEFAULT_REGION, date_override=None):
    if not credential.access_key_id or not credential.secret_access_key:
        raise ValueError("凭据不完整：access key 与 secret key 都得有")
    path, raw_query = _split_path_query(url)

    items = []

    def set_header(name, value):
        low = name.lower()
        for idx, (existing, _) in enumerate(items):
            if existing.lower() == low:
                items[idx] = (name, value)
                return
        items.append((name, value))

    def has_header(name):
        return any(existing.lower() == name.lower() for existing, _ in items)

    for name, value in (headers or {}).items():
        set_header(name, value)
    if credential.security_token:
        set_header("X-Security-Token", credential.security_token)
    if credential.project_id:
        set_header("X-Project-ID", credential.project_id)
    if date_override:
        set_header("X-Sdk-Date", date_override)
    elif not has_header("X-Sdk-Date"):
        import time
        set_header("X-Sdk-Date", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    if not has_header("Host"):
        set_header("Host", _authority_of(url))

    date = ""
    for name, value in items:
        if name.lower() == "x-sdk-date":
            date = value
            break

    canonical = sorted((name.lower(), " ".join(value.split())) for name, value in items)
    canonical_headers = "".join("%s:%s\n" % (name, value) for name, value in canonical)
    signed_headers = ";".join(name for name, _ in canonical)

    payload_hash = EMPTY_BODY_SHA256 if not body else _sha256_hex(body)
    canonical_request = "\n".join([method.upper(), _canonical_uri(path), _canonical_query(raw_query),
                                   canonical_headers, signed_headers, payload_hash])

    if algorithm == SDK_ALGORITHM:
        string_to_sign = "\n".join([SDK_ALGORITHM, date, _sha256_hex(canonical_request.encode())])
        signature = _hmac_hex(credential.secret_access_key.encode(), string_to_sign)
        authorization = ("%s Access=%s, SignedHeaders=%s, Signature=%s"
                         % (SDK_ALGORITHM, credential.access_key_id, signed_headers, signature))
    else:
        scope = "%s/%s/%s" % (date[:8], region, SCOPE_SERVICE)
        string_to_sign = "\n".join([V11_ALGORITHM, date, scope, _sha256_hex(canonical_request.encode())])
        step1 = _hmac_raw(credential.access_key_id.encode(), credential.secret_access_key)
        seed = scope.encode() + b"\x01"
        derived = _hmac_raw(step1, seed.decode("latin-1"))[:32]
        signing_key_hex = "".join("%02x" % b for b in derived)
        signature = _hmac_hex(signing_key_hex.encode(), string_to_sign)
        authorization = ("%s Credential=%s/%s, SignedHeaders=%s, Signature=%s"
                         % (V11_ALGORITHM, credential.access_key_id, scope, signed_headers, signature))

    set_header("Authorization", authorization)
    return dict(items), {"canonical_request": canonical_request, "string_to_sign": string_to_sign,
                         "signed_headers": signed_headers, "signature": signature}

def gateway_base(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or
            parsed.path.rstrip('/') not in ('', '/v2')):
        raise TaskError('网关地址必须为无认证信息的 HTTPS 根地址或 /v2 地址')
    try:
        parsed.port
    except ValueError:
        raise TaskError('网关端口格式错误')
    return 'https://' + parsed.netloc


def parse_line(line):
    # 有固定字段数量，限制拆分次数，末尾地址文本不会被截断。
    parts = line.split('|', 5)
    if len(parts) == 6:
        parts = parts[1:]  # 备注不打印，避免备注含敏感信息
    if len(parts) != 5 or not all(p.strip() for p in parts):
        raise TaskError('账号格式错误：需要 AK|SK|STS|项目 ID|网关地址 五个非空字段')
    ak, sk, sts, project, base = (p.strip() for p in parts)
    if any('\r' in p or '\n' in p for p in (ak, sk, sts, project)):
        raise TaskError('凭据字段含非法换行')
    return Credential(ak, sk, sts, project), gateway_base(base)


def account_lines():
    raw = os.getenv('OFFICEACE_TOKENS', '').strip()
    if raw:
        return [s.strip() for s in raw.splitlines() if s.strip() and not s.strip().startswith('#')]
    keys = ['OFFICEACE_AK', 'OFFICEACE_SK', 'OFFICEACE_STS', 'OFFICEACE_PROJECT_ID', 'OFFICEACE_BASE_URL']
    fields = [os.getenv(k, '').strip() for k in keys]
    return ['|'.join(fields)] if any(fields) else []


def request_json(url, method='GET', body=None, headers=None):
    if enabled('OFFICEACE_DRY_RUN'):
        raise TaskError('预演禁止网络调用')
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=TIMEOUT) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise TaskError('控制面凭据无效或过期，请重新获取临时凭据') from None
        raise TaskError('HTTP 请求失败，状态 %d' % exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError('网络连接失败或超时') from None
    if len(raw) > MAX_RESPONSE:
        raise TaskError('响应超过大小限制')
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise TaskError('响应不是有效 JSON') from None


def validate_subscription(data):
    if not isinstance(data, dict):
        raise TaskError('订阅响应格式不匹配')
    # 只接受已知成功码；HTTP 200 不能替代业务成功检查。
    for key in ('code', 'status_code'):
        if key in data and (isinstance(data[key], bool) or str(data[key]) not in ('0', '200')):
            raise TaskError('接口返回业务失败或未知业务码')
    if ('success' in data and data['success'] is not True) or data.get('error') or data.get('error_code'):
        raise TaskError('接口返回业务失败')
    items = data.get('bonus_skus')
    if not isinstance(items, list):
        raise TaskError('响应缺少奖励列表，不能确认成功')
    for item in items:
        if not isinstance(item, dict) or not any(isinstance(item.get(k), str) and item[k].strip()
                for k in ('activity_id', 'cbc_resource_id', 'activity_name')):
            raise TaskError('奖励条目缺少标识')
        for key in ('points', 'current_value'):
            value = item.get(key)
            try:
                valid = not isinstance(value, bool) and math.isfinite(float(value)) and float(value) >= 0
            except (TypeError, ValueError, OverflowError):
                valid = False
            if not valid:
                raise TaskError('奖励条目积分字段无效')
    return data


def control(credential, base, claim=False):
    path = '/v1/subscription/bonus/claim' if claim else '/v1/subscription'
    method = 'POST' if claim else 'GET'
    payload = b'{}' if claim else b''
    headers = {'x-subscription-type': 'v2'}
    if claim:
        headers['Content-Type'] = 'application/json'
    headers, _ = sign(credential, method, base + path, headers, payload)
    return validate_subscription(request_json(base + path, method, payload if claim else None, headers))


def total(data, field):
    return sum(float(x[field]) for x in data['bonus_skus'])


def show_identity(data, credential):
    # 仅显示官方非敏感身份字段；不显示备注、手机号、设备和原始响应。
    for key in ('nickname', 'username', 'display_name', 'public_uid'):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value)
            if any(secret in text for secret in (credential.access_key_id, credential.secret_access_key,
                                                 credential.security_token, credential.project_id)):
                continue
            if re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text):
                continue
            log('官方账号身份：' + ''.join(c for c in text if c.isprintable()))


def notify_summary(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in ('0', 'false', 'no', 'off') or enabled('NO_NOTIFY'):
        return '已关闭'
    if dry:
        log('通知预演：脱敏总结已生成；离线模式不调用通知组件')
        return '离线预演'
    title = 'OfficeAce 果办每日奖励'
    body = '账号总数 %d，成功 %d，失败 %d，状态 %s' % (
        summary['accounts'], summary['success'], summary['failed'], summary['status'])
    delivered = False
    try:
        # 青龙的通知组件可选，业务脚本无需私有仓库或客户端。
        try:
            import notify
        except ImportError:
            notify = None
            roots = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
            for root in roots:
                path = Path(root) / 'notify.py' if root else None
                if path and path.is_file():
                    spec = importlib.util.spec_from_file_location('qinglong_notify', str(path))
                    notify = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(notify)
                    break
        if notify and callable(getattr(notify, 'send', None)):
            notify.send(title, body)
            delivered = True
    except Exception:
        log('⚠️ 青龙通知失败，保留业务退出码')
    for channel in ('wechat', 'pushplus'):
        key = (os.getenv('QYWX_TOKEN', '') or os.getenv('WECHAT_WEBHOOK', '')).strip() if channel == 'wechat' else os.getenv('PLUSPLUS_TOKEN', '').strip()
        if not key:
            continue
        try:
            if channel == 'wechat':
                key = key.split('key=')[-1]
                url = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=' + urllib.parse.quote(key, safe='')
                payload = {'msgtype': 'text', 'text': {'content': title + '\n' + body}}
            else:
                url = 'https://www.pushplus.plus/send'
                payload = {'token': key, 'title': title, 'content': body, 'template': 'txt'}
            response = request_json(url, 'POST', json.dumps(payload).encode(), {'Content-Type': 'application/json'})
            if not isinstance(response, dict) or response.get('errcode' if channel == 'wechat' else 'code') != (0 if channel == 'wechat' else 200):
                raise TaskError('推送业务失败')
            delivered = True
        except Exception:
            log('⚠️ 兼容推送失败，保留业务退出码')
    if not delivered:
        log('⚠️ 通知组件不可用或投递失败，保留业务退出码')
    return '已调用' if delivered else '不可用或失败'


def main():
    started = time.monotonic()
    dry = enabled('OFFICEACE_DRY_RUN')
    log('════════ OfficeAce 果办每日奖励 ════════')
    log('开始时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('运行模式：' + ('离线预演' if dry else '实时执行'))
    summary = {'accounts': 0, 'success': 0, 'failed': 0, 'tasks': {'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}, 'dryRun': dry}
    config_error = False
    try:
        parser = SafeArgumentParser(description='果办每日奖励领取；--query 仅查询')
        parser.add_argument('--query', action='store_true')
        parser.add_argument('--only', type=int)
        args = parser.parse_args()
        retries = int(os.getenv('OFFICEACE_RETRIES', '2'))
        if not 0 <= retries <= 5:
            raise TaskError('OFFICEACE_RETRIES 必须为 0 到 5')
        lines = account_lines()
        if not lines:
            raise TaskError('未配置 OFFICEACE_TOKENS 或兼容单账号凭据')
        if args.only is not None and not 1 <= args.only <= len(lines):
            raise TaskError('--only 账号序号超出范围')
        selected = [(i, s) for i, s in enumerate(lines, 1) if args.only is None or args.only == i]
        summary['accounts'] = len(selected)
        log('账号数：%d' % len(selected))
        for index, line in selected:
            acct_start = time.monotonic()
            counts = {'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
            def stage(number, name, action, category='success'):
                t = time.monotonic()
                log('账号 %d · 阶段 %d：%s' % (index, number, name))
                try:
                    result = action()
                except Exception:
                    counts['failed'] += 1
                    log('❌ 阶段 %d 失败，耗时 %.2f 秒' % (number, time.monotonic() - t))
                    raise
                counts[category] += 1
                log('✅ 阶段 %d 完成，耗时 %.2f 秒' % (number, time.monotonic() - t))
                return result
            try:
                credential, base = stage(1, '核验配套凭据和 HTTPS 地址', lambda: parse_line(line))
                if dry:
                    stage(2, '离线验证 V11 签名与任务计划', lambda: sign(credential, 'GET' if args.query else 'POST', base + ('/v1/subscription' if args.query else '/v1/subscription/bonus/claim'), {'x-subscription-type': 'v2'}, b'' if args.query else b'{}'))
                    log('DRY_RUN_OK 账号 %d：%s，未发出请求' % (index, '只读查询' if args.query else '每日签到和新人礼领取'))
                    counts['skipped'] += 1
                elif args.query:
                    data = stage(2, '只读查询积分', lambda: control(credential, base))
                    show_identity(data, credential)
                    log('当前奖励额度合计 %g 积分' % total(data, 'points'))
                else:
                    before = stage(2, '读取领取前积分', lambda: control(credential, base))
                    show_identity(before, credential)
                    def claim():
                        for attempt in range(retries + 1):
                            try:
                                return control(credential, base, True)
                            except TaskError:
                                if attempt == retries:
                                    raise
                                log('⚠️ 幂等奖励请求未确认，重试 %d/%d' % (attempt + 1, retries))
                                time.sleep(1)
                    after = stage(3, '领取每日奖励和新人礼并核验响应', claim)
                    show_identity(after, credential)
                    gained = total(after, 'current_value') - total(before, 'current_value')
                    if gained < 0:
                        counts['success'] -= 1
                        counts['failed'] += 1
                        raise TaskError('领取后累计积分下降，不能确认成功')
                    if gained == 0:
                        counts['success'] -= 1
                        counts['alreadyComplete'] += 1
                        log('☑️ 今天没有可领的奖励（或已领过）')
                    else:
                        log('领取成功：+%g 积分（奖励额度合计 %g）' % (gained, total(after, 'points')))
                summary['success'] += 1
            except Exception as exc:
                summary['failed'] += 1
                log('❌ 账号 %d：%s' % (index, str(exc) if isinstance(exc, TaskError) else '执行异常（已隐藏详细信息）'))
            for k in counts:
                summary['tasks'][k] += counts[k]
            log('账号 %d 统计：总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d，耗时 %.2f 秒' % (index, sum(counts.values()), counts['success'], counts['alreadyComplete'], counts['skipped'], counts['failed'], time.monotonic() - acct_start))
    except (TaskError, ValueError, SystemExit) as exc:
        config_error = True
        log('❌ 配置错误：' + (str(exc) if isinstance(exc, TaskError) else '参数格式错误'))
        log('账号数：%d' % summary['accounts'])
    summary['status'] = 'configuration-error' if config_error else ('partial-failure' if summary['failed'] and summary['success'] else 'failure' if summary['failed'] else 'dry-run' if dry else 'success')
    summary['notification'] = notify_summary(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['finishTime'] = time.strftime('%Y-%m-%d %H:%M:%S')
    log('----------------------------------------')
    log('任务统计：账号 %d，成功 %d，失败 %d；子任务 %s；耗时 %.2f 秒' % (summary['accounts'], summary['success'], summary['failed'], json.dumps(summary['tasks'], ensure_ascii=False), summary['elapsedSeconds']))
    log('完成时间：%s；通知状态：%s；最终状态：%s' % (summary['finishTime'], summary['notification'], summary['status']))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return 1 if config_error or summary['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
