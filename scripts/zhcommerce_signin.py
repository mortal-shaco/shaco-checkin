# -*- coding: utf-8 -*-
# name: zhcommerce每日签到
# cron: 45 7 * * *
# SPDX-License-Identifier: MIT
# 来源: guopenglong/automation-scripts，zhcommerce/zhcommerce_signin.py
# 参考: 同仓库 zhcommerce/notification.py（MIT）
# 上游未在这两个文件中提供额外版权声明。
"""独立维护版；仅使用 Python 标准库。

ZH_ACCOUNTS：每个非空行是一个 JSON 对象，字段为 accessToken、deviceId、
appUid、sid、lat、lon，可选 mallId（默认 201）。从本人已登录的 zhcommerce
微信小程序签到请求中获取查询参数和 JSON 请求体，勿分享请求或凭据。
兼容单账号 ZH_ACCESS_TOKEN、ZH_DEVICE_ID、ZH_APP_UID、ZH_SID、ZH_LAT、
ZH_LON、ZH_MALL_ID；不再使用上游硬编码的账号、会话及经纬度。
ZH_DRY_RUN=1 完全断网，验证配置和签名构造，不代表真实签到成功。

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

QINGLONG_NOTIFY 控制通知；QINGLONG_NOTIFY_SCRIPTS 支持目录路径、文件名、
文件名通配符及目录编号，以逗号、分号或空白分隔，空值禁用全部。
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
        _ql_notify_identities = ('cc47f2a2bfb54455', 'scripts/zhcommerce_signin.py', 'zhcommerce_signin.py', 'zhcommerce_signin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import string
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler


TITLE = "zhcommerce每日签到"
CATALOG_ID = "cc47f2a2bfb54455"
WAP_KEYS = [
    "N94QKAZD289GQARELPOJQGZM8", "GFNCV79W9U1CYFEXQ904OI6BB",
    "C1BOEMXCP1A5KUBVQIXKGBH51", "0RU2DV7E67T7ZMPQXWAVD99MY",
    "EPOJKLVKIQQMGG9XWT9C28F5C", "8GTBBWEADC6RG237EUEC7KZFU",
    "1XP3TLH0BZMZS7TT3TF7JD500", "TNFVOH7WHTC4NCD6SI9QZ3W5N",
    "ZZNEL2ULF9TPAC9NU3493GL7I", "8SABWT2MB1JOHOM02QVN36TGI",
]
API_BASE = "https://m.zhcommerce.com/api/v3"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 26_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.70(0x18004634) NetType/WIFI Language/zh_CN"
)
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
REQUIRED = ("accessToken", "deviceId", "appUid", "sid", "lat", "lon")
LEGACY = dict(zip(REQUIRED, (
    "ZH_ACCESS_TOKEN", "ZH_DEVICE_ID", "ZH_APP_UID", "ZH_SID", "ZH_LAT", "ZH_LON"
)))


class TaskError(Exception):
    """只携带可公开的固定错误说明。"""


def log(text):
    print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)


def env(name, default=""):
    return os.environ.get(name, default).strip()


def load_lines():
    if "ZH_ACCOUNTS" in os.environ:
        lines = [s.strip() for s in os.environ["ZH_ACCOUNTS"].splitlines() if s.strip()]
        if not lines:
            raise TaskError("ZH_ACCOUNTS 不能为空；每行填写一个账号 JSON")
        return lines
    if any(env(v) for v in LEGACY.values()):
        data = {k: env(v) for k, v in LEGACY.items()}
        data["mallId"] = env("ZH_MALL_ID", "201")
        return [json.dumps(data)]
    raise TaskError("缺少 ZH_ACCOUNTS；也可使用完整的旧版单账号变量")


def parse_account(line):
    try:
        account = json.loads(line)
    except (ValueError, TypeError):
        raise TaskError("账号格式错误，须为单行 JSON 对象") from None
    if not isinstance(account, dict):
        raise TaskError("账号须为 JSON 对象")
    for key in REQUIRED:
        value = account.get(key)
        if isinstance(value, bool) or not isinstance(value, (str, int, float)) or str(value).strip() == "":
            raise TaskError(f"账号缺少有效字段 {key}")
    for key in ("accessToken", "deviceId", "appUid", "sid"):
        if not isinstance(account[key], str) or any(ord(c) < 32 for c in account[key]):
            raise TaskError(f"账号字段 {key} 必须是无控制字符的字符串")
    for key, bound in (("lat", 90), ("lon", 180)):
        try:
            value = float(account[key])
        except (ValueError, TypeError, OverflowError):
            raise TaskError(f"账号字段 {key} 必须是数字") from None
        if not math.isfinite(value) or abs(value) > bound:
            raise TaskError(f"账号字段 {key} 超出有效范围")
        account[key] = value
    mall = account.get("mallId", "201")
    if isinstance(mall, bool) or not isinstance(mall, (str, int)) or not str(mall).isdigit():
        raise TaskError("mallId 必须是商场编号")
    account["mallId"] = str(mall)
    return account


def build_request_config(account):
    timestamp = int(time.time())
    body = {k: account[k] for k in ("lat", "lon", "mallId")}
    body_json = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    params = {
        "currentPageType": "user", "clientType": "mini_weixin", "appVersion": "3.2.73",
        "customVersion": "9", "osVersion": "iOS 26.4", "model": "iPhone 15 pro max<iPhone16,2>",
        "clientAppName": "memberClient", "rnd": "".join(random.SystemRandom().choices(
            string.digits + string.ascii_uppercase + string.ascii_lowercase, k=30)),
        "appKey": "OW5OGNWC", "sid": account["sid"], "appUid": account["appUid"],
        "deviceId": account["deviceId"], "sdkVersion": "3.15.2", "programVersion": "8.0.70",
        "sceneValue": "1104", "mallId": account["mallId"], "timestamp": timestamp,
        "accessToken": account["accessToken"],
    }
    sign_params = dict(params, body=body_json)
    source = "&".join(f"{k}={sign_params[k]}" for k in sorted(sign_params)
                      if sign_params[k] not in ("", None)) + WAP_KEYS[timestamp % 10]
    params["sign"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    params["signType"] = "sha"
    url = f"{API_BASE}/member/{quote(account['appUid'], safe='')}/signs?{urlencode(params)}"
    headers = {
        "Content-Type": "application/json", "EncryptBody": "false", "Mobcb-Encrypt": "true",
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": "https://servicewechat.com/wxd4680abecbc3f014/339/page-frame.html",
    }
    return Request(url, data=body_json.encode("utf-8"), headers=headers, method="POST")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def perform_request(request):
    # 签到是写操作：不自动重试，禁止跟随跳转，避免凭据泄漏或重复请求。
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200:
                raise TaskError("HTTP 状态异常，签到未确认")
            data = response.read(1024 * 1024 + 1)
    except HTTPError as exc:
        status = exc.code
        exc.close()
        raise TaskError(f"HTTP {status}，签到未确认") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise TaskError("网络请求失败或超时，签到未确认；请稍后检查签到状态") from None
    if len(data) > 1024 * 1024:
        raise TaskError("响应过大，签到未确认")
    try:
        result = json.loads(data)
    except (ValueError, UnicodeError):
        raise TaskError("响应不是有效 JSON，签到未确认") from None
    if not isinstance(result, dict):
        raise TaskError("响应结构异常，签到未确认")
    return result


def display_identity(result, secrets):
    body = result.get("body")
    containers = [result]
    if isinstance(body, dict):
        containers.insert(0, body)
        for key in ("member", "user", "userInfo", "memberInfo"):
            if isinstance(body.get(key), dict):
                containers.append(body[key])
    for data in containers:
        for key in ("nickname", "nickName", "username", "userName", "displayName", "publicUid", "uid"):
            value = data.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            text = str(value)
            # 官方公开身份原样展示；疑似手机号、凭据及控制字符则不输出。
            if (not text or any(ord(c) < 32 for c in text)
                    or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text)
                    or re.search(r"cookie|token|session|bearer", text, re.I)
                    or any(secret and secret in text for secret in secrets)):
                continue
            log(f"账号身份（{key}）：{text}")
            return


def safe_number(value):
    if isinstance(value, bool):
        return "未提供"
    if isinstance(value, (str, int, float)) and re.fullmatch(r"\d{1,12}(?:\.\d{1,4})?", str(value)):
        return str(value)
    return "未提供"


def notification_selected():
    switch = env("QINGLONG_NOTIFY", "auto").lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True  # 此维护任务列入默认通知名单。
    selectors = re.split(r"[,;\s]+", os.environ["QINGLONG_NOTIFY_SCRIPTS"].strip())
    names = (CATALOG_ID, "zhcommerce/zhcommerce_signin.py", "zhcommerce_signin.py",
             "candidate.py", Path(__file__).name, str(Path(__file__).resolve()))
    return any(fnmatch.fnmatchcase(name, selector) for selector in selectors if selector for name in names)


def notify_summary(body, dry):
    if not notification_selected():
        return "已禁用"
    if dry:
        log("通知：断网预演，仅生成脱敏摘要，不加载或调用通知模块")
        return "预演未发送"
    # 通知适配器在子进程中执行，隔离其日志/异常；失败不改变业务退出码。
    python_code = '''
import importlib.util,json,sys
title,body,path=json.loads(sys.stdin.read())
if path:
    spec=importlib.util.spec_from_file_location("ql_notice",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(title,body)
'''
    js_code = '''let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',async()=>{
try {let [title,body,path]=JSON.parse(s);await require(path).sendNotify(title,body);}
catch(e){process.exitCode=1;}});'''
    roots = ([Path(env("QINGLONG_NOTIFY_DIR"))] if env("QINGLONG_NOTIFY_DIR") else [])
    roots += [Path("/ql/data/scripts"), Path("/ql/scripts")]
    attempts = [([sys.executable, "-c", python_code], "")]
    for root in roots:
        if (root / "notify.py").is_file():
            attempts.append(([sys.executable, "-c", python_code], str((root / "notify.py").resolve())))
    for root in roots:
        if (root / "sendNotify.js").is_file():
            attempts.append((["node", "-e", js_code], str((root / "sendNotify.js").resolve())))
    for command, path in attempts:
        try:
            outcome = subprocess.run(command, input=json.dumps([TITLE, body, path]), text=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if outcome.returncode == 0:
                return "已发送"
        except (OSError, subprocess.TimeoutExpired):
            pass
    log("⚠️ 通知适配器不可用或发送失败，保留业务退出码")
    return "不可用或失败"


def main():
    start = time.monotonic()
    start_time = time.strftime("%Y-%m-%d %H:%M:%S %z")
    dry = env("ZH_DRY_RUN").lower() in TRUE
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{start_time}；模式：{'断网预演' if dry else '正式签到'}")
    accounts = []
    config_error = False
    try:
        lines = load_lines()
    except TaskError as exc:
        lines = []
        config_error = True
        log(f"❌ 阶段 1 配置检查：{exc}")
    log(f"账号数量：{len(lines)}")
    # 提前收集所有账号敏感值，仅用于防止身份字段意外回显凭据。
    secrets = [env(v) for v in LEGACY.values() if env(v)]
    for line in lines:
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                secrets.extend(str(data[k]) for k in ("accessToken", "deviceId", "appUid", "sid") if data.get(k))
        except (ValueError, TypeError):
            pass
    for index, line in enumerate(lines, 1):
        began = time.monotonic()
        status = "failure"
        log(f"--- 账号 {index} ---")
        try:
            stage = time.monotonic()
            account = parse_account(line)
            request = build_request_config(account)
            log(f"阶段 1 参数与签名构造：✅ 完成，耗时 {time.monotonic()-stage:.3f} 秒")
            stage = time.monotonic()
            if dry:
                status = "dry-run"
                log("阶段 2 签到：⏭️ DRY_RUN_OK 配置有效；未请求业务接口或通知服务")
            else:
                result = perform_request(request)
                display_identity(result, secrets)
                code = result.get("errorCode")
                if code == "PUB-00000":
                    status = "success"
                    body = result.get("body")
                    body = body if isinstance(body, dict) else {}
                    log("阶段 2 签到：✅ 签到成功")
                    log(f"奖励积分：{safe_number(body.get('signInCreditValue', 0))}；连续签到：{safe_number(body.get('continuousDays'))} 天")
                elif code == "MBR-00029":
                    status = "already-complete"
                    log("阶段 2 签到：☑️ 今天已签到")
                else:
                    raise TaskError("接口未返回已知签到成功码或已签到码")
            log(f"阶段 2 完成，耗时 {time.monotonic()-stage:.3f} 秒")
        except TaskError as exc:
            log(f"❌ 账号 {index}：{exc}；阶段耗时 {time.monotonic()-stage:.3f} 秒")
        except Exception:
            log(f"❌ 账号 {index}：内部处理失败；已抑制异常详情；阶段耗时 {time.monotonic()-stage:.3f} 秒")
        row = {"account": index, "status": status, "total": 1,
               "success": int(status == "success"), "alreadyComplete": int(status == "already-complete"),
               "skipped": int(status == "dry-run"), "failed": int(status == "failure"),
               "elapsedSeconds": round(time.monotonic()-began, 3)}
        accounts.append(row)
        log(f"账号 {index} 统计：总任务 1；成功 {row['success']}；已完成 {row['alreadyComplete']}；跳过 {row['skipped']}；失败 {row['failed']}；耗时 {row['elapsedSeconds']} 秒")
    failed = sum(a["failed"] for a in accounts)
    successful = sum(a["status"] in ("success", "already-complete") for a in accounts)
    exit_code = int(config_error or failed > 0)
    status = ("configuration-error" if config_error else "partial-failure" if failed and failed < len(accounts)
              else "failure" if failed else "dry-run" if dry else "success")
    message = (f"{TITLE}；状态：{status}；账号总数 {len(accounts)}，成功 {successful}，"
               f"失败 {failed}，预演 {sum(a['skipped'] for a in accounts)}；配置错误 {int(config_error)}")
    log("阶段 3 通知汇总")
    notice_start = time.monotonic()
    try:
        notification = notify_summary(message, dry)
    except Exception:
        notification = "不可用或失败"
        log("⚠️ 通知处理失败，保留业务退出码")
    log(f"阶段 3 完成，耗时 {time.monotonic()-notice_start:.3f} 秒")
    log("----------------------------------------")
    log(message)
    totals = {key: sum(a[key] for a in accounts) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log(f"子任务统计：总数 {totals['total']}；成功 {totals['success']}；已完成 {totals['alreadyComplete']}；跳过 {totals['skipped']}；失败 {totals['failed']}")
    log(f"通知状态：{notification}；总耗时：{time.monotonic()-start:.3f} 秒")
    finish = time.strftime("%Y-%m-%d %H:%M:%S %z")
    log(f"完成时间：{finish}；最终状态：{status}；退出码：{exit_code}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "status": status, "dryRun": dry,
          "accountCount": len(accounts), "successfulAccounts": successful, "failedAccounts": failed,
          "configurationError": config_error, "accounts": accounts, "tasks": totals,
          "notification": notification, "startedAt": start_time, "finishedAt": finish,
          "elapsedSeconds": round(time.monotonic()-start, 3), "exitCode": exit_code}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
