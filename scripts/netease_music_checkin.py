#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 网易云音乐签到
# cron: 15 9 * * *
# new Env('网易云音乐签到')
# 来源: deeplee/personal-scripts, netease_music_checkin.py
# 上游与维护版本许可: MIT；保留上游署名及原文件说明。
"""
网易云音乐每日签到脚本，适配青龙面板。
上游功能：每日签到获取云贝（weapi AES-128-CBC + RSA），识别成功、
今日已签到及 Cookie 失效，多账号与青龙 / PushPlus / Server酱通知回退。
依赖：pycryptodome（公开包注册表安装，仅用于 weapi AES 加密）。
NETEASE_COOKIES：每行一条完整 Cookie；兼容 NETEASE_COOKIE，前者优先。
浏览器登录 https://music.163.com，F12 → Application → Cookies，
复制同一账号 MUSIC_U 与 __csrf；可保留 __remember_me 或整段 Cookie。
Cookie 字段用分号分隔，值仅在第一个等号处拆分；不要用 & 或 @ 分账号。
NETEASE_DRY_RUN=1：断网预演，不签到、不发送真实通知。
QINGLONG_NOTIFY 默认 1；设为 0/false/no/off 关闭全部通知。
可选 PUSHPLUS_TOKEN、SENDKEY 为原通知渠道兼容配置。
"""
import base64
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# weapi 签到接口(HTTP POST, body 需加密)
WEAPI_SIGN_URL = "https://music.163.com/weapi/point/dailyTask"


# ---------------------------------------------------------------------------
# weapi 加密(pycryptodome;RSA 为原始 RSA,标准库 pow 实现)
# ---------------------------------------------------------------------------
MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7"
    "b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280"
    "104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932"
    "575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b"
    "3ece0462db0a22b8e7"
)
PUBKEY = "010001"
_NONCE = b"0CoJUm6Qyw8W8jud"
_IV = b"0102030405060708"


def _aes_encrypt(plaintext, key, iv):
    """AES-128-CBC 加密,带 PKCS7 填充,返回 bytes"""
    padlen = 16 - (len(plaintext) % 16)
    plaintext = plaintext + bytes([padlen]) * padlen
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(plaintext)


def _rsa_encrypt(text):
    """原始 RSA 公钥加密(weapi 专用: 反转字节 → int → pow → 256 hex)"""
    c = pow(int.from_bytes(text[::-1], "big"), int(PUBKEY, 16), int(MODULUS, 16))
    return format(c, "x").zfill(256)


def weapi_encrypt(plain_dict):
    """weapi 加密: 双层 AES-128-CBC + RSA,返回 {'params','encSecKey'}
    第1层: 加密原始 JSON → 输出 base64 字符串
    第2层: 加密第1层的 base64 字符串(utf-8 字节,同样 PKCS7 填充)→ 输出 base64
    """
    data = json.dumps(plain_dict, separators=(",", ":")).encode("utf-8")
    secret = base64.b64encode(os.urandom(16)).decode()[:16].encode()  # 16字节随机key
    inner_b64 = base64.b64encode(_aes_encrypt(data, _NONCE, _IV)).decode()
    params = base64.b64encode(
        _aes_encrypt(inner_b64.encode("utf-8"), secret, _IV)
    ).decode()
    return {
        "params": params,
        "encSecKey": _rsa_encrypt(secret),
    }


DISABLED = {'0', 'false', 'no', 'off'}
TITLE = '网易云音乐签到'


def log(text):
    print('[%s] %s' % (datetime.now().strftime('%H:%M:%S'), text), flush=True)


def enabled(name, default='0'):
    return os.environ.get(name, default).strip().lower() not in DISABLED | {''}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # Cookie 及通知凭据不得随重定向传给其他主机。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, data, headers=None):
    if enabled('NETEASE_DRY_RUN'):
        raise RuntimeError('断网预演禁止 HTTP')
    req = urllib.request.Request(url, data=data, headers=headers or {}, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            payload = response.read(262145)
            if len(payload) > 262144:
                return None, '响应超过大小限制'
            if response.status != 200:
                return None, 'HTTP 状态异常'
            result = json.loads(payload.decode('utf-8'))
            if not isinstance(result, dict):
                return None, '响应结构异常'
            return result, ''
    except urllib.error.HTTPError as exc:
        return None, 'HTTP %d' % exc.code
    except (ValueError, UnicodeError):
        return None, '返回非有效 JSON'
    except Exception:
        return None, '网络请求失败或超时'


def parse_cookie(cookie):
    fields = {}
    for part in cookie.split(';'):
        if '=' in part:
            key, value = part.split('=', 1)
            fields[key.strip()] = value.strip()
    return fields


def parse_accounts():
    raw = os.environ.get('NETEASE_COOKIES', '').strip()
    if not raw:
        raw = os.environ.get('NETEASE_COOKIE', '').strip()
    return [line.strip().strip("'").strip('"') for line in raw.splitlines()
            if line.strip() and not line.strip().startswith('#')]


def sign_in(cookie):
    fields = parse_cookie(cookie)
    if '\r' in cookie or '\n' in cookie or not fields.get('MUSIC_U') or not fields.get('__csrf'):
        return 'failure', 'Cookie 必须含同一账号的非空 MUSIC_U 和 __csrf'
    if enabled('NETEASE_DRY_RUN'):
        return 'skipped', 'DRY_RUN_OK：凭据格式通过，模拟签到；未发起 HTTP 或真实通知'
    encrypted = weapi_encrypt({'type': 1, 'csrf_token': fields['__csrf']})
    result, error = request_json(
        WEAPI_SIGN_URL, urllib.parse.urlencode(encrypted).encode('utf-8'),
        {'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://music.163.com',
         'Cookie': cookie, 'User-Agent': UA, 'Referer': 'https://music.163.com/', 'Accept': 'application/json'})
    if result is None:
        return 'failure', error
    # 只展示官方明确返回的公开身份，不输出响应、会话或设备字段。
    profile = result.get('profile')
    if isinstance(profile, dict):
        for field in ('nickname', 'userName', 'displayName', 'userId'):
            value = profile.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                log('官方账号身份 %s：%s' % (field, json.dumps(value, ensure_ascii=False)))
    for field in ('nickname', 'username', 'displayName', 'userId'):
        value = result.get(field)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            log('官方账号身份 %s：%s' % (field, json.dumps(value, ensure_ascii=False)))
    code = result.get('code')
    if code == 200:
        point = result.get('point')
        extra = '，+%s云贝' % point if isinstance(point, (int, float)) and not isinstance(point, bool) else ''
        return 'success', '签到成功' + extra
    if code == -2:
        return 'alreadyComplete', '今日已签到'
    if code == 301:
        return 'failure', 'Cookie 失效（301），请重新登录获取'
    # 不以任意错误消息中的“重复”判定成功，也不打印原始服务端消息。
    return 'failure', '业务未确认成功（状态码 %s）' % (code if isinstance(code, int) else '未知')


def ql_notify(title, body):
    candidates = [None]
    folder = os.environ.get('QINGLONG_NOTIFY_DIR', '').strip()
    if folder:
        candidates.append(Path(folder) / 'notify.py')
    candidates.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    import contextlib
    for path in candidates:
        try:
            with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                if path is None:
                    module = importlib.import_module('notify')
                else:
                    if not path.is_file():
                        continue
                    spec = importlib.util.spec_from_file_location('qinglong_task_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                delivered = module.send(title, body)
            if delivered is not False:
                return True
        except Exception:
            continue
    return False


def send_notify(title, body):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    if enabled('NETEASE_DRY_RUN'):
        log('通知预演：%s；%s' % (title, body.replace('\n', '；')))
        return '断网模拟发送'
    if ql_notify(title, body):
        return '青龙通知'
    token = os.environ.get('PUSHPLUS_TOKEN', '').strip()
    if token:
        result, _ = request_json('https://www.pushplus.plus/send',
            json.dumps({'token': token, 'title': title, 'content': body}).encode('utf-8'),
            {'Content-Type': 'application/json'})
        if result and result.get('code') == 200:
            return 'PushPlus'
    key = os.environ.get('SENDKEY', '').strip()
    if key:
        result, _ = request_json('https://sctapi.ftqq.com/%s.send' % urllib.parse.quote(key, safe=''),
            urllib.parse.urlencode({'title': title, 'desp': body}).encode('utf-8'),
            {'Content-Type': 'application/x-www-form-urlencoded'})
        if result and result.get('code') == 0:
            return 'Server酱'
    return '不可用或发送失败（保留业务退出码）'


def main():
    started = time.monotonic()
    dry = enabled('NETEASE_DRY_RUN')
    accounts = parse_accounts()
    log('=' * 48 + '\n' + TITLE)
    log('开始时间：%s；模式：%s；账号总数：%d' %
        (datetime.now().isoformat(timespec='seconds'), '断网预演' if dry else '真实执行', len(accounts)))
    config_error = ''
    if not accounts:
        config_error = '未配置 NETEASE_COOKIES（兼容 NETEASE_COOKIE）'
    if accounts and not dry:
        try:
            global AES
            from Crypto.Cipher import AES
        except ImportError:
            config_error = '缺少公开依赖 pycryptodome，请在青龙依赖管理安装'
    results = []
    totals = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
    if config_error:
        log('❌ 配置错误：' + config_error)
    for index, cookie in enumerate(accounts, 1):
        tick = time.monotonic()
        log('账号%d / 阶段1：凭据检查与%s' % (index, '签到预演' if dry else '每日签到'))
        try:
            state, message = ('failure', config_error) if config_error else sign_in(cookie)
        except Exception:
            state, message = 'failure', '执行异常（已隐藏敏感异常内容）'
        totals[state] += 1
        elapsed = round(time.monotonic() - tick, 3)
        log('账号%d / 阶段1结果：%s；耗时 %.3f 秒' % (index, message, elapsed))
        log('账号%d 统计：总任务1，成功%d，已完成%d，跳过%d，失败%d；耗时 %.3f 秒' %
            (index, state == 'success', state == 'alreadyComplete', state == 'skipped', state == 'failure', elapsed))
        results.append({'account': index, 'status': state, 'message': message, 'durationSeconds': elapsed})
    failures = sum(r['status'] == 'failure' for r in results)
    passed = sum(r['status'] in ('success', 'alreadyComplete') for r in results)
    simulated = sum(r['status'] == 'skipped' for r in results)
    exit_code = 1 if config_error or failures else 0
    status = ('configuration-error' if config_error else 'partial-failure' if failures and (passed or simulated)
              else 'failure' if failures else 'dry-run' if dry else 'success')
    body = '账号总数%d，成功%d，失败%d；最终状态：%s' % (len(accounts), passed, failures, status)
    if dry:
        body += '；预演通过%d（不代表真实签到成功）' % simulated
    if config_error:
        body += '\n' + config_error
    body += ''.join('\n账号%d：%s' % (r['account'], r['message']) for r in results)
    log('阶段2：发送脱敏总结通知')
    tick = time.monotonic()
    try:
        channel = send_notify(TITLE, body)
    except Exception:
        channel = '通知异常（保留业务退出码）'
    log('阶段2结果：%s；耗时 %.3f 秒' % (channel, time.monotonic() - tick))
    log('-' * 48)
    log(body)
    log('子任务统计：总数%d，成功%d，已完成%d，跳过%d，失败%d' %
        (len(results), totals['success'], totals['alreadyComplete'], totals['skipped'], totals['failure']))
    finished = datetime.now().isoformat(timespec='seconds')
    log('总耗时 %.3f 秒；完成时间：%s；通知状态：%s；最终状态：%s' %
        (time.monotonic() - started, finished, channel, status))
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'mode': 'dry-run' if dry else 'live',
        'status': status, 'accountCount': len(accounts), 'successfulAccounts': passed,
        'failedAccounts': failures, 'dryRunAccounts': simulated, 'tasks': totals, 'accounts': results, 'notification': channel,
        'finishTime': finished, 'durationSeconds': round(time.monotonic() - started, 3),
        'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
