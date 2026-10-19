# -*- coding: utf-8 -*-
# name: 小米运动
# cron: 1 0 * * *
# 来源：yuxian158/check，dailycheckin_scripts/ck_mimotion.py
# 上游许可证：MIT；原文件未附额外版权声明。
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
小米运动独立维护脚本（仅中国大陆华米手机号账号）。
MIMOTION_ACCOUNTS：每行一个 JSON 对象，phone/password 为原参数名；
min_step/max_step 保持原默认值 10000/19999。密码只由 JSON 解析，保留所有分隔符。
在 Zepp Life（原小米运动）注册华米手机号账号并设置密码；不是小米账号密码。
默认 MIMOTION_ACTION=login，仅验证登录和应用令牌，不上传健康记录。
显式 MIMOTION_ACTION=upload 时，账号还需 last_deviceid 和 band_data：
从本人获授权的 band_data.json 同步请求获取 last_deviceid 和解码后的 data_json
数组，将其作为 band_data；数组须仅含当天记录，summary 为 JSON 字符串，
且包含 stp.ttl。脚本仅调整日期及 stp.ttl，保留本人模板的其他数据。
模板包含的活动、睡眠、心率等会一同上传，不要使用他人或历史模板。
可填 device_id 为本人的登录请求设备 UUID；省略时为本轮生成 UUID。
禁止使用上游固定设备标识及伪造历史健康模板。无法获取本人模板时仅运行登录。
上游没有 cron；此版本建议每日 20:00（按青龙本地时区），可自行调整。
MIMOTION_DRY_RUN=1 完全断网，仅校验参数及构造请求，通知仅预览。
"""
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('04e92730d2cbeb73', 'scripts/ck_mimotion.py', 'ck_mimotion.py', 'ck_mimotion')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

TITLE = "小米运动"
FALSE = {"0", "false", "no", "off"}


class TaskError(Exception):
    pass


def log(message):
    print(f"[{dt.datetime.now():%H:%M:%S}] {message}", flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http(url, data=None, headers=None, redirect_login=False):
    if os.getenv("MIMOTION_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}:
        raise TaskError("预演模式禁止网络请求")
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data is not None else None,
                                 headers=headers or {})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise TaskError("响应超过大小限制")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise TaskError("响应结构不符合预期")
        return result
    except urllib.error.HTTPError as exc:
        if redirect_login and exc.code in {301, 302, 303, 307, 308}:
            location = exc.headers.get("Location", "")
            exc.close()
            parsed = urllib.parse.urlsplit(location)
            params = urllib.parse.parse_qs(parsed.query)
            params.update(urllib.parse.parse_qs(parsed.fragment))
            access = params.get("access", [""])[0]
            if access:
                return {"access": access}
            raise TaskError("登录重定向未返回访问凭据") from None
        exc.close()
        raise TaskError(f"接口 HTTP 状态异常（{exc.code}）") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError("网络连接失败或请求超时") from None
    except (ValueError, UnicodeError):
        raise TaskError("接口未返回有效 JSON") from None


def prepare(line, action):
    try:
        account = json.loads(line)
        if not isinstance(account, dict):
            raise ValueError
        phone, password = account["phone"], account["password"]
        if not isinstance(phone, str) or not re.fullmatch(r"1\d{10}", phone):
            raise ValueError
        if not isinstance(password, str) or not password:
            raise ValueError
        low, high = account.get("min_step", 10000), account.get("max_step", 19999)
        low, high = int(low), int(high)
        if not 0 <= low <= high <= 100000:
            raise ValueError
        account["step"] = random.randint(low, high)
        account["device_id"] = account.get("device_id") or str(uuid.uuid4()).upper()
        if not isinstance(account["device_id"], str):
            raise ValueError
        if action == "upload":
            device = account["last_deviceid"]
            records = account["band_data"]
            today = dt.date.today().isoformat()
            if not isinstance(device, str) or not device or not isinstance(records, list) or len(records) != 1:
                raise ValueError
            record = records[0]
            if not isinstance(record, dict) or record.get("date") != today:
                raise ValueError
            summary = json.loads(record["summary"])
            if not isinstance(summary["stp"]["ttl"], (int, float)):
                raise ValueError
            summary["stp"]["ttl"] = account["step"]
            record["date"] = today
            record["summary"] = json.dumps(summary, separators=(",", ":"))
            account["data_json"] = json.dumps(records, separators=(",", ":"))
        return account
    except (ValueError, KeyError, TypeError, OverflowError):
        raise TaskError("账号参数无效：检查手机号、密码、步数范围；上传需本人设备和当天单条健康数据模板") from None


def identity(response, account):
    containers = [response]
    for key in ("user_info", "token_info"):
        if isinstance(response.get(key), dict):
            containers.append(response[key])
    for obj in containers:
        for field in ("nickname", "display_name", "username", "user_id"):
            value = obj.get(field)
            if isinstance(value, (str, int)) and value:
                value = " ".join(str(value).split())
                if account["phone"] in value or account["password"] in value or re.search(r"(?<!\d)1\d{10}(?!\d)", value):
                    continue
                log(f"官方账号身份：{value}")


def stage(number, name, fn):
    started = time.monotonic()
    log(f"阶段 {number}：{name}")
    try:
        result = fn()
    except Exception:
        log(f"❌ 阶段 {number} 失败，耗时 {time.monotonic() - started:.2f} 秒")
        raise
    log(f"✅ 阶段 {number} 完成，耗时 {time.monotonic() - started:.2f} 秒")
    return result


def login(account):
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
               "User-Agent": "MiFit/4.6.0 (iPhone; iOS 14.0.1; Scale/2.00)"}
    auth = http("https://api-user.huami.com/registrations/+86" + account["phone"] + "/tokens",
                {"client_id": "HuaMi", "password": account["password"],
                 "redirect_uri": "https://s3-us-west-2.amazonaws.com/hm-registration/successsignin.html",
                 "token": "access"}, headers, True)
    if not auth.get("access"):
        raise TaskError("登录未返回访问凭据")
    result = http("https://account.huami.com/v2/client/login", {
        "app_name": "com.xiaomi.hm.health", "app_version": "5.0.2", "code": auth["access"],
        "country_code": "CN", "device_id": account["device_id"], "device_model": "phone",
        "grant_type": "access_token", "third_name": "huami_phone"}, headers)
    token = result.get("token_info", {})
    if not isinstance(token, dict) or not token.get("login_token") or not token.get("user_id"):
        raise TaskError("登录未返回有效账号和登录令牌")
    identity(result, account)
    return token


def app_token(token):
    query = urllib.parse.urlencode({"app_name": "com.xiaomi.hm.health",
        "dn": "api-user.huami.com,api-mifit.huami.com,app-analytics.huami.com",
        "login_token": token["login_token"]})
    result = http("https://account-cn.huami.com/v1/client/app_tokens?" + query,
                  headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; MI 6 MIUI/20.6.18)"})
    info = result.get("token_info", {})
    if not isinstance(info, dict) or not info.get("app_token"):
        raise TaskError("未返回有效应用令牌")
    return info["app_token"]


def upload(account, token, app):
    # 使用本机时间，移除上游向无关第三方发起的明文时间请求。
    result = http("https://api-mifit-cn.huami.com/v1/data/band_data.json?&t=" + str(int(time.time() * 1000)),
        {"userid": token["user_id"], "last_sync_data_time": account.get("last_sync_data_time", 0),
         "device_type": 0, "last_deviceid": account["last_deviceid"], "data_json": account["data_json"]},
        {"apptoken": app, "Content-Type": "application/x-www-form-urlencoded"})
    if result.get("message") != "ok" or ("code" in result and str(result["code"]) != "0"):
        raise TaskError("上传未返回明确业务成功标志；不重试写入，请在应用中核对")
    log(f"上传业务成功，目标步数 {account['step']}（不代表真实运动或人工确认）")


def notify(body, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in FALSE:
        return "已关闭"
    if dry:
        log("通知预览：" + body)
        return "预演模式仅预览，未发送"
    # 独立子进程限制通知耗时，隐藏通知模块输出，避免异常输出含凭据。
    helper = '''import contextlib,importlib.util,io,sys
with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
 if sys.argv[1]:
  s=importlib.util.spec_from_file_location("ql_notify",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
 else:
  import notify as m
 m.send(sys.argv[2],sys.argv[3])
'''
    paths = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
    for path in [""] + [str(p) for p in paths if p.is_file()]:
        try:
            completed = subprocess.run([sys.executable, "-c", helper, path, TITLE, body],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
            if completed.returncode == 0:
                return "已发送"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "不可用或发送失败（保留业务退出码）"


def main():
    started = time.monotonic()
    dry = os.getenv("MIMOTION_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}
    lines = [line for line in os.getenv("MIMOTION_ACCOUNTS", "").splitlines() if line.strip()]
    action = os.getenv("MIMOTION_ACTION", "login").lower()
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{dt.datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry else '正式运行'}；动作：{'上传' if action == 'upload' else '登录检查'}；账号数：{len(lines)}")
    results = []
    config_error = not lines or action not in {"login", "upload"}
    if config_error:
        log("❌ 配置错误：必须填写 MIMOTION_ACCOUNTS；MIMOTION_ACTION 只能为 login 或 upload")
    else:
        for index, line in enumerate(lines, 1):
            begin = time.monotonic()
            stats = {"account": index, "total": 3 if action == "login" else 4,
                     "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
            log(f"---------- 账号 {index} ----------")
            try:
                account = stage(1, "参数及写入边界检查", lambda: prepare(line, action))
                stats["success"] += 1
                if dry:
                    for n, label in [(2, "登录请求"), (3, "应用令牌请求")] + ([(4, "当天步数上传请求")] if action == "upload" else []):
                        stage(n, label + "（仅预演，不发送）", lambda: None)
                        stats["skipped"] += 1
                    log("✅ DRY_RUN_OK：参数与请求规划通过，未验证真实业务")
                else:
                    token = stage(2, "华米账号登录", lambda: login(account))
                    stats["success"] += 1
                    app = stage(3, "取得应用令牌", lambda: app_token(token))
                    stats["success"] += 1
                    if action == "upload":
                        stage(4, "上传本人当天健康模板及目标步数", lambda: upload(account, token, app))
                        stats["success"] += 1
                    log("✅ BUSINESS_SUCCESS：账号业务验证通过")
            except TaskError as exc:
                stats["failed"] += 1
                log("❌ " + str(exc))
            except Exception:
                stats["failed"] += 1
                log("❌ 接口结构或执行异常（已隐藏详情及凭据）")
            stats["skipped"] += stats["total"] - stats["success"] - stats["failed"] - stats["skipped"]
            stats["seconds"] = round(time.monotonic() - begin, 2)
            results.append(stats)
            log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 0，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {stats['seconds']} 秒")
    failed = sum(bool(r["failed"]) for r in results)
    good = len(results) - failed
    status = "configuration-error" if config_error else ("partial-failure" if failed and good else "failure" if failed else "dry-run" if dry else "success")
    code = 1 if config_error or failed else 0
    body = f"账号总数 {len(lines)}，成功数 {good}，失败数 {failed}；状态 {status}；预演结果不代表业务成功。" if dry else f"账号总数 {len(lines)}，成功数 {good}，失败数 {failed}；状态 {status}。"
    notification = notify(body, dry)
    log("----------------------------------------")
    log(body)
    totals = {key: sum(r[key] for r in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log(f"子任务统计：总数 {totals['total']}，成功 {totals['success']}，已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，失败 {totals['failed']}")
    log(f"通知状态：{notification}；总耗时：{time.monotonic() - started:.2f} 秒")
    finish = dt.datetime.now().isoformat(timespec="seconds")
    log(f"完成时间：{finish}；最终状态：{status}；退出码：{code}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "mode": "dry-run" if dry else "live",
        "status": status, "accounts": len(lines), "success": good, "failed": failed,
        "configurationError": config_error, "results": results, "tasks": totals,
        "notification": notification, "finishedAt": finish, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
