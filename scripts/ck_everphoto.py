# -*- coding: utf-8 -*-
# name: 时光相册每日签到
# cron: 3 22 * * *
# License: MIT (upstream effective license)
# Original author: @CAB233
# Original URL: https://github.com/CAB233/everphoto_checkin
# Source: OreosLab/checkinpanel, ck_everphoto.py
"""时光相册登录与签到。EVERPHOTO：每行 手机号|密码字段值，仅首次 | 分隔。

密码字段值请在本人账户登录时从浏览器开发者工具 /api/auth 请求中获取；
若客户端对密码作了变换，应使用请求中的值，不在此脚本中猜测变换方式。
EVERPHOTO_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。

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
"""

import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import time
from urllib import error, parse, request

TITLE = "时光相册"
LOGIN_URL = "https://web.everphoto.cn/api/auth"
CHECKIN_URL = "https://openapi.everphoto.cn/sf/3/v4/PostCheckIn"
DISABLED = {"0", "false", "no", "off"}


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class TaskError(Exception):
    pass


def accounts_from_env():
    raw = os.environ.get("EVERPHOTO", "")
    if not raw.strip():
        raise TaskError("未设置必需变量 EVERPHOTO")
    # Compatibility with upstream's EVERPHOTO list of mobile/password objects.
    if raw.lstrip().startswith("["):
        try:
            rows = json.loads(raw)
        except ValueError:
            raise TaskError("EVERPHOTO JSON 格式错误") from None
        if not isinstance(rows, list) or not rows:
            raise TaskError("EVERPHOTO 必须包含账号")
        return rows
    rows = []
    for line in raw.splitlines():
        if line.strip():
            mobile, sep, password = line.partition("|")
            rows.append({"mobile": mobile.strip(), "password": password if sep else None})
    if not rows:
        raise TaskError("EVERPHOTO 必须包含账号")
    return rows


def credentials(row):
    if not isinstance(row, dict):
        raise TaskError("账号格式错误，应包含 mobile 和 password")
    mobile, password = row.get("mobile"), row.get("password")
    if not isinstance(mobile, str) or not mobile.strip() or not isinstance(password, str) or not password:
        raise TaskError("账号缺少手机号或密码字段值")
    if any(c in mobile + password for c in ("\r", "\n", "\x00")):
        raise TaskError("凭据中包含不支持的控制字符")
    return mobile.strip(), password


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward credentials to a redirected host.


def post_json(url, headers, body):
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            payload = response.read(262145)
    except error.HTTPError as exc:
        raise TaskError(f"接口 HTTP 失败（状态码 {exc.code}）") from None
    except (error.URLError, TimeoutError, OSError):
        raise TaskError("接口网络连接失败或超时") from None
    if len(payload) > 262144:
        raise TaskError("接口响应超过大小限制")
    try:
        result = json.loads(payload)
    except (ValueError, UnicodeError):
        raise TaskError("接口响应不是有效 JSON") from None
    if not isinstance(result, dict):
        raise TaskError("接口响应结构不符合契约")
    # The source has no documented alternate success codes: fail closed.
    for key in ("code", "error_code", "errcode"):
        if key in result and (isinstance(result[key], bool) or result[key] not in (0, "0")):
            raise TaskError("接口明确返回业务失败或未知业务状态")
    data = result.get("data")
    if not isinstance(data, dict):
        raise TaskError("接口缺少业务数据")
    return data


def show_identity(data, secrets):
    candidates = [data]
    for key in ("user", "user_info", "profile"):
        if isinstance(data.get(key), dict):
            candidates.append(data[key])
    for profile in candidates:
        for key in ("nickname", "username", "display_name", "uid"):
            value = profile.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                value = str(value)
                if any(secret and secret in value for secret in secrets) or re.search(r"(?<!\d)1\d{10}(?!\d)", value):
                    continue
                log(f"账号身份（{key}）：{value.replace(chr(10), ' ').replace(chr(13), ' ')}")
                return


def run_account(row, index, dry):
    started = time.monotonic()
    stats = {"total": 2, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    ok = False
    try:
        mobile, password = credentials(row)
        headers = {"User-Agent": "EverPhoto/4.5.0 (Android;4050002;MuMu;23;dev)", "application": "tc.everphoto"}
        stage = time.monotonic()
        log(f"账号 {index} · 阶段 1/2 登录")
        if dry:
            log("⏭️ 凭据格式通过；预演不发送登录请求")
            stats["skipped"] += 1
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = post_json(LOGIN_URL, headers, parse.urlencode({"mobile": mobile, "password": password}).encode())
            token = data.get("token")
            if not isinstance(token, str) or not token.strip() or any(c in token for c in "\r\n"):
                raise TaskError("登录未返回有效 Token")
            show_identity(data, (mobile, password, token))
            stats["success"] += 1
            log("✅ 登录成功，已取得有效凭据")
        log(f"阶段 1 耗时 {time.monotonic() - stage:.2f} 秒")
        stage = time.monotonic()
        log(f"账号 {index} · 阶段 2/2 每日签到")
        if dry:
            stats["skipped"] += 1
            log("⏭️ 预演不发送签到请求、不改变账号状态")
        else:
            headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
            data = post_json(CHECKIN_URL, headers, b"")
            show_identity(data, (mobile, password, token))
            result, continuity = data.get("checkin_result"), data.get("continuity")
            if type(result) is not bool or type(continuity) is not int or continuity < 1:
                raise TaskError("签到响应缺少可验证的签到结果或连续天数")
            # Upstream defines false as not the first check-in today.
            stats["success" if result else "alreadyComplete"] += 1
            log(f"{'✅ 签到成功' if result else '☑️ 今日已签到'}；是否为今日第一次签到：{result}；累积签到天数：{continuity}")
        log(f"阶段 2 耗时 {time.monotonic() - stage:.2f} 秒")
        ok = True
    except TaskError as exc:
        stats["failed"] += 1
        stats["skipped"] = stats["total"] - stats["success"] - stats["alreadyComplete"] - stats["failed"]
        log(f"❌ 账号 {index}：{exc}")
    except Exception:
        stats["failed"] += 1
        stats["skipped"] = max(0, 2 - sum(stats[k] for k in ("success", "alreadyComplete", "failed")))
        log(f"❌ 账号 {index}：执行异常，详细响应与凭据已隐藏")
    log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {time.monotonic() - started:.2f} 秒")
    return ok, stats


def notify_summary(body, dry):
    if os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in DISABLED:
        return "已关闭"
    if dry:
        log(f"通知断网预演：{body}")
        return "已断网预演（未投递）"
    child_env = dict(os.environ)
    child_env.pop("EVERPHOTO", None)
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--notify-summary"],
            input=body, text=True, env=child_env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=20, check=False,
        )
        if result.returncode == 0:
            return "已调用通知模块"
        if result.returncode == 2:
            return "不可用（保留业务退出码）"
        return "投递失败（保留业务退出码）"
    except (OSError, subprocess.TimeoutExpired):
        return "投递失败或超时（保留业务退出码）"


def notification_worker():
    try:
        try:
            module = importlib.import_module("notify")
        except ImportError:
            paths = []
            if os.environ.get("QINGLONG_NOTIFY_DIR"):
                paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
            paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, "send", None)):
            return 2
        module.send(TITLE, sys.stdin.read())
        return 0
    except Exception:
        return 3



def main():
    started = time.monotonic()
    dry = os.environ.get("EVERPHOTO_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{time.strftime('%Y-%m-%d %H:%M:%S')}；模式：{'断网预演' if dry else '正式执行'}")
    totals = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    success = failed = 0
    configuration_error = False
    try:
        rows = accounts_from_env()
    except TaskError as exc:
        rows = []
        configuration_error = True
        log(f"❌ 配置错误：{exc}")
    log(f"账号总数：{len(rows)}")
    for index, row in enumerate(rows, 1):
        ok, stats = run_account(row, index, dry)
        success += int(ok)
        failed += int(not ok)
        for key in totals:
            totals[key] += stats[key]
    exit_code = int(configuration_error or failed > 0)
    status = "configuration-error" if configuration_error else "partial-failure" if failed and success else "failure" if failed else "dry-run" if dry else "success"
    body = f"账号总数 {len(rows)}，成功 {success}，失败 {failed}；状态 {status}；子任务成功 {totals['success']}，已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，失败 {totals['failed']}"
    delivery = notify_summary(body, dry)
    log("----------------------------------------")
    log(body)
    log(f"总耗时：{time.monotonic() - started:.2f} 秒；完成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}；通知：{delivery}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "mode": "dry-run" if dry else "live", "status": status, "accounts": len(rows), "success": success, "failed": failed, "configurationError": configuration_error, "steps": totals, "notification": delivery, "exitCode": exit_code}, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(notification_worker() if sys.argv[1:] == ["--notify-summary"] else main())
