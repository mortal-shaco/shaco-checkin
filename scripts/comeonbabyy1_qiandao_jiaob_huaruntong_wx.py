#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 华润通微信签到
# cron: 54 9 * * *
# 来源: comeonbabyy1/qiandao-jiaob
# script/huaruntong/huaruntong_wx/main.py 与 api.py
# 上游许可: MIT；输入文件未提供独立版权声明。
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
"""
华润通签到主程序 / 华润通签到API接口（独立维护版）
依赖：pycryptodome（公开 Python 包；仅实跑加密使用，不自动安装）。
HRT_WX_ACCOUNTS 必填：每个非空行一个账号，可填 token 或单行 JSON 对象。
JSON 保留上游字段 token、account_name、answerResult、channelId、merchantCode、
storeCode、sysId、transactionUuid、inviteCode、user_agent。不要用 & 或 @ 分隔账号。
token 获取：本人登录华润通微信端，在授权的本机抓包中查看
mid.huaruntong.cn/api/points/saveQuestionSignin 的加密前 token；网络封包
key/data 不是 token。若只能得到加密封包，请使用本人可查看的登录会话
调试数据，不猜测凭据。其它字段从本人同一签到请求的加密前参数获取。
默认参数完全沿用上游；不自动设置邀请码、交易标识或注册邀请关系。
上游未声明 cron，本维护版建议每天 08:00，可在青龙调整。
HRT_WX_DRY_RUN=1 完全断网预演，只验证账号参数，不宣称业务成功。
QINGLONG_NOTIFY=auto 默认仅选中脚本发送；=1 强制发送，=0 关闭。
QINGLONG_NOTIFY_SCRIPTS 可用目录相对路径、文件名、通配符或目录编号选择。
预演只展示通知摘要，禁止通知网络；实跑通知不可用不改变业务退出码。
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
        _ql_notify_identities = ('8d1f195e1b3e02a0', 'scripts/comeonbabyy1_qiandao_jiaob_huaruntong_wx.py', 'comeonbabyy1_qiandao_jiaob_huaruntong_wx.py', 'comeonbabyy1_qiandao_jiaob_huaruntong_wx')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import fnmatch
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, HTTPRedirectHandler, build_opener

TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
TITLE = "华润通微信签到"


class TaskError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def log(text):
    print(f"[{datetime.now():%H:%M:%S}] {text}", flush=True)


class HuaRunTongAPI:
    """华润通签到API接口类"""

    # 配置常量
    SECRET = "c274fc67-19f9-47ba-bb84-585a2e3a1f6a"
    PUB_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDuAiqDmvn9Rf15o21qkDxN0rUf
ZsX6rVBrtfgY6tamN2Yn+1D3eHZJuKNlucyqeBr6nmfN2srYAX+oyCXr5vWwFclj
PuWh8aSASqyk7MfbAv5Q4VqYS7lsYUQRdw4plZG0NASDeBvHWi3lsHjGfNb7iUvg
rk312EDfBHtRgDvB0QIDAQAB
-----END PUBLIC KEY-----"""
    APP_ID = "API_AUTH_WEB"
    HOST = "https://mid.huaruntong.cn"

    def __init__(self, token: str, answer_result: int = 1, channel_id: str = "APP",
                 merchant_code: str = "1641000001532", store_code: str = "qiandaosonjifen",
                 sys_id: str = "T0000001", transaction_uuid: str = "",
                 invite_code: str = "", user_agent: str = None):
        """
        初始化华润通API

        :param token: 认证token
        :param answer_result: 答题结果
        :param channel_id: 渠道ID
        :param merchant_code: 商户编码
        :param store_code: 门店编码
        :param sys_id: 系统ID
        :param transaction_uuid: 交易UUID
        :param invite_code: 邀请码
        :param user_agent: 用户代理字符串
        """
        self.token = token
        self.answer_result = answer_result
        self.channel_id = channel_id
        self.merchant_code = merchant_code
        self.store_code = store_code
        self.sys_id = sys_id
        self.transaction_uuid = transaction_uuid
        self.invite_code = invite_code
        self.user_agent = user_agent or "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"

    def _generate_aes_key(self):
        """生成16字节随机AES密钥"""
        return os.urandom(16)

    def _pad_pkcs7(self, data: bytes, block_size: int = 16) -> bytes:
        """PKCS7填充"""
        padding_len = block_size - (len(data) % block_size)
        return data + bytes([padding_len] * padding_len)

    def _crypto_data(self, params: dict, api_path: str) -> dict:
        """加密请求数据"""
        # 添加必要字段
        params["apiPath"] = quote(api_path, safe='')
        params["appId"] = self.APP_ID
        params["timestamp"] = int(time.time() * 1000)

        # 生成签名 (HMAC-MD5)
        parts = []
        for key, value in params.items():
            if value is not None:
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, separators=(',', ':'))
                parts.append(f"{key}={value}")

        sign_str = "&".join(sorted(parts))
        signature = hmac.new(
            self.SECRET.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.md5
        ).hexdigest()
        params["signature"] = signature

        # AES-CBC 加密 (IV为空)
        from Crypto.Cipher import AES, PKCS1_OAEP
        from Crypto.PublicKey import RSA

        aes_key = self._generate_aes_key()
        iv = b'\x00' * 16
        cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)

        plaintext = json.dumps(params, separators=(',', ':')).encode('utf-8')
        padded = self._pad_pkcs7(plaintext)
        encrypted_data = cipher_aes.encrypt(padded)
        data_b64 = base64.b64encode(encrypted_data).decode('utf-8')

        # RSA-OAEP 加密 AES 密钥
        rsa_key = RSA.import_key(self.PUB_KEY)
        cipher_rsa = PKCS1_OAEP.new(rsa_key)
        encrypted_key = cipher_rsa.encrypt(aes_key)
        key_b64 = base64.b64encode(encrypted_key).decode('utf-8')

        return {"key": key_b64, "data": data_b64}

    def _get_headers(self):
        """获取请求头"""
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "X-HRT-MID-NEWRISK": "newRisk",
            "X-Hrt-Mid-Appid": self.APP_ID,
            "Origin": "https://cloud.huaruntong.cn",
            "Referer": "https://cloud.huaruntong.cn/",
        }

    def _send_request(self, api_path: str, payload: dict) -> dict:
        """发送加密请求"""
        url = f"{self.HOST}{api_path}"
        encrypted = self._crypto_data(payload.copy(), api_path)

        request = Request(url, data=json.dumps(encrypted).encode("utf-8"),
                          headers=self._get_headers(), method="POST")
        # 禁止重定向，避免将加密凭据发送至其它地址；不自动重试状态变更。
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise TaskError("响应超过大小限制")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise TaskError("响应结构不符合签到契约")
            return result

    def sign_in(self) -> dict:
        """
        签到接口

        :return: 响应数据
        """
        payload = {
            "answerResult": self.answer_result,
            "channelId": self.channel_id,
            "merchantCode": self.merchant_code,
            "storeCode": self.store_code,
            "sysId": self.sys_id,
            "transactionUuid": self.transaction_uuid,
            "inviteCode": self.invite_code,
            "token": self.token
        }

        api_path = "/api/points/saveQuestionSignin"
        return self._send_request(api_path, payload)



def parse_account(line):
    if line.startswith('{'):
        try:
            account = json.loads(line)
        except (ValueError, TypeError):
            raise TaskError('账号 JSON 无效') from None
        if not isinstance(account, dict):
            raise TaskError('账号必须是 JSON 对象')
    else:
        account = {'token': line}
    token = account.get('token')
    if not isinstance(token, str) or not token.strip() or any(c.isspace() for c in token):
        raise TaskError('缺少有效 token，或 token 包含空白字符')
    answer = account.get('answerResult', 1)
    if isinstance(answer, bool) or not isinstance(answer, int):
        raise TaskError('answerResult 必须为整数，请核对本人签到参数')
    defaults = {
        'channelId': 'APP', 'merchantCode': '1641000001532',
        'storeCode': 'qiandaosonjifen', 'sysId': 'T0000001',
        'transactionUuid': '', 'inviteCode': '',
    }
    for field, default in defaults.items():
        value = account.get(field, default)
        if not isinstance(value, str) or '\r' in value or '\n' in value:
            raise TaskError('账号请求参数格式错误')
    ua = account.get('user_agent')
    if ua is not None and (not isinstance(ua, str) or '\r' in ua or '\n' in ua):
        raise TaskError('user_agent 格式错误')
    return account


def new_api(account):
    return HuaRunTongAPI(
        token=account['token'], answer_result=account.get('answerResult', 1),
        channel_id=account.get('channelId', 'APP'),
        merchant_code=account.get('merchantCode', '1641000001532'),
        store_code=account.get('storeCode', 'qiandaosonjifen'),
        sys_id=account.get('sysId', 'T0000001'),
        transaction_uuid=account.get('transactionUuid', ''),
        invite_code=account.get('inviteCode', ''),
        user_agent=account.get('user_agent'))


def show_identity(result, token):
    # 仅读取明确的公开身份字段；不输出消息、手机号、设备号和原始响应。
    containers = [result]
    data = result.get('data')
    if isinstance(data, dict):
        containers.append(data)
        if isinstance(data.get('userInfo'), dict):
            containers.append(data['userInfo'])
    for container in containers:
        for key in ('nickname', 'nickName', 'username', 'displayName', 'uid'):
            value = container.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value)
                if (text and token not in text and not re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text)
                        and not any(ord(c) < 32 or ord(c) == 127 for c in text)):
                    log(f'官方账号身份 {key}: {text}')
                    return


def account_task(index, line, dry):
    start = time.monotonic()
    counts = {'total': 3, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    stage = 1
    stage_start = start
    log(f'账号 {index} / 阶段 1/3：验证参数')
    try:
        account = parse_account(line)
        api = new_api(account)
        counts['success'] += 1
        log(f'✅ 参数验证通过；阶段耗时 {time.monotonic() - stage_start:.2f} 秒')
        stage = 2
        stage_start = time.monotonic()
        log(f'账号 {index} / 阶段 2/3：签名加密及签到请求')
        if dry:
            # 实际构建并加密原有契约，请求入口被替换，绝不打开网络。
            original_send = api._send_request
            def preview(path, payload):
                encrypted = api._crypto_data(payload.copy(), path)
                if set(encrypted) != {'key', 'data'} or not all(encrypted.values()):
                    raise TaskError('加密请求封装无效')
                return {}
            api._send_request = preview
            api.sign_in()
            api._send_request = original_send
            counts['skipped'] += 1
            log(f'⏭️ 加密契约验证通过，已跳过 HTTP 请求；阶段耗时 {time.monotonic() - stage_start:.2f} 秒')
            stage = 3
            stage_start = time.monotonic()
            log(f'账号 {index} / 阶段 3/3：业务成功核验')
            counts['skipped'] += 1
            log('⏭️ DRY_RUN_OK：断网预演通过，未执行签到，未验证业务成功；阶段耗时 0.00 秒')
            status = 'dry-run'
        else:
            result = api.sign_in()
            counts['success'] += 1
            log(f'✅ HTTP 响应及 JSON 结构检查通过；阶段耗时 {time.monotonic() - stage_start:.2f} 秒')
            stage = 3
            stage_start = time.monotonic()
            log(f'账号 {index} / 阶段 3/3：业务成功核验')
            show_identity(result, account['token'])
            if result.get('code') != 'S0A00000':
                raise TaskError('业务未确认成功，请在官方端检查登录和签到状态；未自动重试')
            counts['success'] += 1
            log(f'✅ 签到成功（code=S0A00000）；阶段耗时 {time.monotonic() - stage_start:.2f} 秒')
            status = 'success'
    except Exception as exc:
        if isinstance(exc, TaskError):
            detail = str(exc)
        elif isinstance(exc, ImportError):
            detail = '缺少公开依赖 pycryptodome，请在青龙依赖管理安装后重试'
        elif isinstance(exc, HTTPError):
            detail = f'HTTP 状态异常（{exc.code}），未自动重试'
        elif isinstance(exc, (URLError, TimeoutError, OSError)):
            detail = '网络、超时或运行环境异常，签到结果未确认，未自动重试'
        elif isinstance(exc, (ValueError, TypeError)):
            detail = '响应或加密参数无效，未确认业务成功'
        else:
            detail = '执行异常，未确认业务成功'
        counts['failed'] += 1
        counts['skipped'] += 3 - stage
        log(f'❌ 阶段 {stage}/3 失败：{detail}；阶段耗时 {time.monotonic() - stage_start:.2f} 秒')
        status = 'failure'
    elapsed = round(time.monotonic() - start, 3)
    log(f'账号 {index} 统计：总任务 {counts["total"]}，成功 {counts["success"]}，'
        f'已完成 {counts["alreadyComplete"]}，跳过 {counts["skipped"]}，'
        f'失败 {counts["failed"]}，耗时 {elapsed:.2f} 秒，状态 {status}')
    return {'account': index, 'status': status, 'tasks': counts, 'elapsedSeconds': elapsed}


NOTIFY_HELPER = r'''
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
try:
    title, body = sys.argv[1:3]
    spec = importlib.util.find_spec('notify')
    if spec:
        import notify
        notify.send(title, body)
        sys.exit(0)
    dirs = []
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        dirs.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    dirs += [Path('/ql/data/scripts'), Path('/ql/scripts')]
    for directory in dirs:
        path = directory / 'notify.py'
        if path.is_file():
            sys.path.insert(0, str(directory))
            spec = importlib.util.spec_from_file_location('ql_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send(title, body)
            sys.exit(0)
    for directory in dirs:
        path = directory / 'sendNotify.js'
        if path.is_file():
            code = 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).catch(()=>process.exit(1))'
            result = subprocess.run(['node', '-e', code, str(path), title, body], timeout=18)
            sys.exit(result.returncode)
    sys.exit(2)
except Exception:
    sys.exit(1)
'''


def notify(summary, dry):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    selectors = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    names = {'8d1f195e1b3e02a0', Path(__file__).name,
             'script/huaruntong/huaruntong_wx/main.py', 'main.py',
             'scripts/huaruntong_wx.py', 'huaruntong_wx.py'}
    selected = selectors is not None and any(
        fnmatch.fnmatchcase(name, pattern)
        for pattern in re.split(r'[,;\s]+', selectors.strip()) if pattern
        for name in names)
    if switch in FALSE or (switch not in TRUE and not selected):
        log('⏭️ 通知关闭：全局开关关闭或未被通知列表选中')
        return 'disabled'
    body = (f'账号总数 {summary["accountCount"]}；成功 {summary["success"]}；'
            f'预演通过 {summary["dryRunPassed"]}；失败 {summary["failed"]}；状态 {summary["status"]}')
    if dry:
        log(f'⏭️ 通知摘要（断网预演，不调用通知服务）：{body}')
        return 'dry-run-preview'
    try:
        result = subprocess.run([sys.executable, '-c', NOTIFY_HELPER, TITLE, body],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=20, check=False)
        if result.returncode != 0:
            log('⚠️ 通知不可用或发送失败，保留业务退出码')
            return 'unavailable-or-failed'
        log('✅ 通知调用完成')
        return 'sent'
    except Exception:
        log('⚠️ 通知不可用、超时或发送失败，保留业务退出码')
        return 'unavailable-or-failed'


def main():
    started = time.monotonic()
    start_time = datetime.now().isoformat(timespec='seconds')
    dry = os.getenv('HRT_WX_DRY_RUN', '').strip().lower() in TRUE
    lines = [s.strip() for s in os.getenv('HRT_WX_ACCOUNTS', '').splitlines() if s.strip()]
    log('=' * 54)
    log(f'{TITLE} | 开始时间 {start_time}')
    log(f'运行模式：{"断网预演" if dry else "实跑"}；账号数：{len(lines)}')
    results = []
    if not lines:
        log('❌ 配置错误：HRT_WX_ACCOUNTS 必填，每个非空行一个账号')
    else:
        results = [account_task(i, line, dry) for i, line in enumerate(lines, 1)]
    failed = sum(r['status'] == 'failure' for r in results)
    success = sum(r['status'] == 'success' for r in results)
    previews = sum(r['status'] == 'dry-run' for r in results)
    code = 2 if not lines else (1 if failed else 0)
    status = ('configuration-error' if not lines else
              'partial-failure' if failed and failed < len(lines) else
              'failure' if failed else 'dry-run' if dry else 'success')
    tasks = {key: sum(r['tasks'][key] for r in results)
             for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live',
               'status': status, 'accountCount': len(lines), 'success': success,
               'dryRunPassed': previews, 'failed': failed, 'configurationErrors': int(not lines),
               'tasks': tasks, 'accounts': results, 'startTime': start_time, 'exitCode': code}
    summary['notification'] = notify(summary, dry)
    summary['finishTime'] = datetime.now().isoformat(timespec='seconds')
    summary['elapsedSeconds'] = round(time.monotonic() - started, 3)
    log('-' * 54)
    log(f'任务统计：账号总数 {len(lines)}，成功 {success}，预演通过 {previews}，失败 {failed}')
    log(f'子任务统计：总任务 {tasks["total"]}，成功 {tasks["success"]}，'
        f'已完成 {tasks["alreadyComplete"]}，跳过 {tasks["skipped"]}，失败 {tasks["failed"]}')
    log(f'完成时间 {summary["finishTime"]}；总耗时 {summary["elapsedSeconds"]:.2f} 秒')
    log(f'最终状态：{status}；通知状态：{summary["notification"]}；退出码：{code}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
