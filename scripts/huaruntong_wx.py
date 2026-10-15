# name: 华润通微信版签到
# cron: 18 1 1 1 1
# 来源: Cat-zaizai/ZaiZaiCat-Checkin
# script/huaruntong/huaruntong_wx/main.py 与 api.py；MIT 许可。
# 原始文件未包含其他版权声明；保留来源归属。
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
# HRT_WX_ACCOUNTS: 每行一个 token 或含 token 的 JSON 对象。
# JSON 可保留上游 answerResult/channelId/merchantCode/storeCode/sysId/
# transactionUuid/inviteCode/user_agent/account_name 参数；不再读取私有文件。
# HRT_WX_DRY_RUN=1 完全断网预演；生产需 pip 安装 pycryptodome。

import urllib.request
import importlib.util
import subprocess
import re
from datetime import datetime
from pathlib import Path

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

"""
华润通签到API接口
"""
import json
import time
import hmac
import hashlib
import base64
import os
from urllib.parse import quote


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
        from Crypto.Cipher import AES, PKCS1_OAEP
        from Crypto.PublicKey import RSA

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

        request = urllib.request.Request(
            url, data=json.dumps(encrypted).encode("utf-8"),
            headers=self._get_headers(), method="POST")
        # 禁止重定向，避免认证请求被转发；签到写操作不自动重试。
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=20) as response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise ValueError("响应过大")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("响应格式错误")
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



import sys

TITLE = "华润通微信版签到"
DISABLED = {"0", "false", "no", "off"}

def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)

def accounts_from_env():
    lines = [line.strip() for line in os.environ.get("HRT_WX_ACCOUNTS", "").splitlines() if line.strip()]
    accounts = []
    for line in lines:
        try:
            value = json.loads(line) if line.startswith("{") else {"token": line}
            if not isinstance(value, dict) or not isinstance(value.get("token"), str) or not value["token"].strip():
                raise ValueError()
            if any(not isinstance(value.get(key, ""), str) for key in
                   ("channelId", "merchantCode", "storeCode", "sysId", "transactionUuid", "inviteCode", "user_agent")):
                raise ValueError()
            if "answerResult" in value and (type(value["answerResult"]) is not int):
                raise ValueError()
            accounts.append(value)
        except (ValueError, TypeError):
            accounts.append(None)
    return accounts

def notify_summary(body, dry):
    if os.environ.get("QINGLONG_NOTIFY", "1").lower() in DISABLED:
        log("⏭️ 通知已关闭")
        return "disabled"
    if dry:
        log("⏭️ 断网预演：模拟发送脱敏通知")
        return "dry-run"
    # 使用独立进程限制通知耗时，通知异常不改变业务退出码。
    runner = """import sys, importlib.util
path, title, body = sys.argv[1:]
if path:
    spec = importlib.util.spec_from_file_location('ql_notify', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(title, body)
"""
    notify_dir = os.environ.get("QINGLONG_NOTIFY_DIR", "")
    dirs = ([Path(notify_dir)] if notify_dir else []) + [Path("/ql/data/scripts"), Path("/ql/scripts")]
    candidates = [None] + [d / "notify.py" for d in dirs]
    for path in candidates:
        if path is not None and not path.is_file():
            continue
        try:
            result = subprocess.run([sys.executable, "-c", runner, str(path) if path else "", TITLE, body],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if result.returncode == 0:
                log("✅ 脱敏通知已发送")
                return "sent"
        except (OSError, subprocess.TimeoutExpired):
            pass
    for directory in dirs:
        path = directory / "sendNotify.js"
        if not path.is_file():
            continue
        try:
            result = subprocess.run(["node", "-e", "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))", str(path), TITLE, body],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if result.returncode == 0:
                log("✅ 脱敏通知已发送")
                return "sent"
        except (OSError, subprocess.TimeoutExpired):
            pass
    log("⚠️ 通知不可用或发送失败，保留业务退出码")
    return "unavailable"

def print_identity(result, credentials):
    # 仅打印明确的官方公开身份字段，绝不输出整个响应或服务端消息。
    containers = [result]
    if isinstance(result.get("data"), dict):
        containers.append(result["data"])
    for container in containers:
        for field in ("nickname", "nickName", "username", "userName", "displayName", "publicUid"):
            value = container.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                value = str(value)
                for credential in credentials:
                    if credential:
                        value = value.replace(credential, "[已脱敏]")
                value = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", value)
                value = value.replace("\r", " ").replace("\n", " ")
                log(f"官方身份 {field}: {value}")

def main():
    started = time.monotonic()
    start_time = datetime.now().isoformat(timespec="seconds")
    dry = os.environ.get("HRT_WX_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}
    accounts = accounts_from_env()
    log("========== 华润通微信版签到 ==========")
    log(f"开始时间: {start_time}；模式: {'断网预演' if dry else '正式签到'}；账号数: {len(accounts)}")
    successes = failures = skipped = 0
    records = []
    if not accounts:
        log("❌ 配置错误：HRT_WX_ACCOUNTS 未提供非空账号行")
    for index, account in enumerate(accounts, 1):
        tick = time.monotonic()
        log(f"账号 {index} / 阶段 1：检查配置")
        ok = False
        account_skipped = False
        if account is None:
            log("❌ 账号配置错误：需要非空 token 和有效参数类型")
        else:
            log(f"✅ 配置有效；阶段 1 耗时 {time.monotonic()-tick:.2f} 秒")
            stage = time.monotonic()
            log(f"账号 {index} / 阶段 2：{'模拟签到' if dry else '加密签到请求'}")
            if dry:
                log("✅ DRY_RUN_OK：参数检查通过，未发起任何网络请求或签到写入")
                ok = True
                account_skipped = True
            else:
                try:
                    api = HuaRunTongAPI(
                        token=account["token"], answer_result=account.get("answerResult", 1),
                        channel_id=account.get("channelId", "APP"),
                        merchant_code=account.get("merchantCode", "1641000001532"),
                        store_code=account.get("storeCode", "qiandaosonjifen"),
                        sys_id=account.get("sysId", "T0000001"),
                        transaction_uuid=account.get("transactionUuid", ""),
                        invite_code=account.get("inviteCode", ""), user_agent=account.get("user_agent"))
                    result = api.sign_in()
                    print_identity(result, [a.get(k, "") for a in accounts if a for k in ("token", "transactionUuid", "inviteCode")])
                    ok = result.get("code") == "S0A00000"
                    log("✅ 签到成功：业务码 S0A00000" if ok else "❌ 签到失败：业务码未确认成功；请在官方页面检查登录或活动状态")
                except Exception as error:
                    log(f"❌ 签到失败：{type(error).__name__}（异常详情已隐藏）")
            log(f"阶段 2 耗时 {time.monotonic()-stage:.2f} 秒")
        successes += int(ok)
        failures += int(not ok)
        skipped += int(account_skipped)
        records.append({"account": index, "status": "dry-run" if account_skipped else ("success" if ok else "failure")})
        log(f"账号 {index} 统计：总任务 1；成功 {int(ok and not dry)}；已完成 0；跳过 {int(account_skipped)}；失败 {int(not ok)}；耗时 {time.monotonic()-tick:.2f} 秒")
    status = "configuration-error" if not accounts else ("partial-failure" if failures and successes else ("failure" if failures else ("dry-run" if dry else "success")))
    exit_code = int(bool(failures) or not accounts)
    finish = datetime.now().isoformat(timespec="seconds")
    body = f"状态: {status}；账号总数: {len(accounts)}；成功数: {successes if not dry else 0}；失败数: {failures}；预演通过: {successes if dry else 0}；完成时间: {finish}"
    log("阶段 3：任务汇总与通知")
    notify_started = time.monotonic()
    notification = notify_summary(body, dry)
    log(f"阶段 3 耗时 {time.monotonic()-notify_started:.2f} 秒")
    log("----------------------------------------")
    log(body)
    log(f"子任务总数: {len(accounts)}；成功 {successes if not dry else 0}；已完成 0；跳过 {skipped}；失败 {failures}")
    log(f"总耗时: {time.monotonic()-started:.2f} 秒；通知: {notification}；完成时间: {finish}；最终状态: {status}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "status": status, "mode": "dry-run" if dry else "live", "accounts": len(accounts), "success": successes if not dry else 0, "failed": failures, "skipped": skipped, "dryRunPassed": successes if dry else 0, "alreadyComplete": 0, "results": records, "startTime": start_time, "finishTime": finish, "durationSeconds": round(time.monotonic()-started, 2), "notification": notification, "exitCode": exit_code}, ensure_ascii=False, separators=(",", ":")))
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
