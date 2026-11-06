# -*- coding: utf-8 -*-
# name: SophNet 签到
# cron: 3 10 * * *
# new Env('SophNet 签到');
# 作者: zephyr_xiao
# 来源: zephyr-xiao/qinglong-script / sophnet_checkin/sophnet_checkin.py
# SPDX-License-Identifier: MIT
"""SophNet(www.sophnet.com) 福利中心每日签到，签到领 Token 奖励。
纯 API 模式，用 refreshToken 兑换短期 accessToken 后签到，无需浏览器/验证码。

SOPHNET_REFRESH_TOKEN 必填，每个非空行一个账号的 refreshToken，不使用 & 分账号。
获取方法：在已登录 SophNet 的浏览器 DevTools Console 执行
localStorage.getItem('sophnet-auth-tab-sync-v1')，读取 JSON 的 p.refreshToken。
SOPHNET_TIMEOUT 请求超时秒数，默认 30，范围 1 至 300。
SOPHNET_PROXY 可选 HTTP/HTTPS 代理地址，默认不读取系统代理。
SOPHNET_DEBUG 默认 false，仅增加脱敏 HTTP 状态日志。
SOPHNET_DRY_RUN=1 完全断网预演，通知仅模拟，不验证真实凭据。
SOPHNET_NOTIFY 默认 true；SOPHNET_NOTIFY_ONLY_FAIL 默认 false。
QINGLONG_NOTIFY 支持 auto/1/true/yes/on/0/false/no/off，默认 auto。
强制开启时发送所有结果；auto 服从脚本通知配置与选择名单。
QINGLONG_NOTIFY_SCRIPTS 若设置则替换默认选择，支持目录相对路径、文件名、
文件名通配符、目录编号 da2b7014b2824de3，以逗号、分号、空白分隔，空值关闭。
QINGLONG_NOTIFY_DIR 可选通知模块目录，支持 notify.py 或 sendNotify.js。
不输出凭据、原始响应或异常详情；TLS 校验失败立即失败。

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
        _ql_notify_identities = ('da2b7014b2824de3', 'scripts/sophnet_checkin.py', 'sophnet_checkin.py', 'sophnet_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

TITLE = "SophNet 签到"
CATALOG_ID = "da2b7014b2824de3"
BASE_URL = "https://www.sophnet.com"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def enabled(name, default=False):
    value = os.getenv(name, "").strip().lower()
    return default if not value else value in TRUE_VALUES


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    def __init__(self, message, auth=False):
        super().__init__(message)
        self.auth = auth


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, timeout, proxy, debug):
        proxies = {"http": proxy, "https": proxy} if proxy else {}
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler(proxies),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            NoRedirect())
        self.timeout = timeout
        self.debug = debug
        self.secrets = []

    def request(self, method, path, token=None, body=None):
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
        if method == "POST":
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(BASE_URL + path, data=payload,
                                         headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if self.debug:
                    log(f"调试 {method} {path} HTTP {response.status}")
                if response.status != 200:
                    raise TaskError(f"HTTP {response.status}")
                raw = response.read(1048577)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise TaskError(f"HTTP {code}，请求失败", auth=code == 401) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise TaskError("网络、超时、TLS 或请求配置错误") from None
        if len(raw) > 1048576:
            raise TaskError("响应超过大小限制")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TaskError("响应不是有效 JSON") from None
        if not isinstance(data, dict) or type(data.get("status")) is not int:
            raise TaskError("响应业务状态格式异常")
        return data


def result_object(data):
    result = data.get("result")
    if not isinstance(result, dict):
        raise TaskError("响应缺少有效结果对象")
    return result


def check_status(data):
    if data["status"] != 0:
        raise TaskError("业务状态未确认成功", auth=data["status"] == 10025)


def show_identity(result, secrets):
    """只展示明确的公开身份字段，不转储用户对象。"""
    objects = [result]
    for key in ("user", "userInfo", "profile"):
        if isinstance(result.get(key), dict):
            objects.append(result[key])
    for obj in objects:
        for key in ("nickname", "nickName", "username", "displayName", "publicUid", "uid"):
            value = obj.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            text = str(value)
            if not text or any(secret and secret in text for secret in secrets):
                continue
            if re.search(r"[\r\n\x00-\x1f]|(?<!\d)\+?\d[\d -]{9,}\d(?!\d)", text) and key not in ("publicUid", "uid"):
                continue
            # JSON 编码控制字符，保留公开身份原值，避免日志注入。
            log(f"官方账号身份 {key} {json.dumps(value, ensure_ascii=False)}")


def welfare(client, access):
    data = client.request("GET", "/api/sys/checkin/welfare", token=access)
    check_status(data)
    result = result_object(data)
    show_identity(result, client.secrets)
    return result


def show_stats(result):
    checkin = result.get("checkIn", {})
    if not isinstance(checkin, dict):
        return
    parts = []
    for key, label in (("tokenBalance", "可提现 Tokens"),
                       ("currentContinuousDays", "连续签到天数"),
                       ("totalCheckInDays", "累计签到天数")):
        value = checkin.get(key)
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            parts.append(f"可提现 {value // 1000:g}k Tokens" if key == "tokenBalance" else f"{label} {value}")
    if parts:
        log("奖励统计　" + "，".join(parts))


def run_account(refresh, index, total, timeout, proxy, debug, dry):
    started = time.monotonic()
    counts = {"total": 0, "success": 0, "alreadyComplete": 0,
              "skipped": 0, "failed": 0, "warning": 0}
    log(f"账号 {index}/{total} 开始")

    def stage(number, name, action=None, skip=False, completed=False):
        tick = time.monotonic()
        counts["total"] += 1
        log(f"账号 {index} 阶段 {number}/4 {name} 开始")
        if completed:
            counts["alreadyComplete"] += 1
            log(f"☑️ 账号 {index} 阶段 {number}/4 {name} 今日已完成，耗时 {time.monotonic() - tick:.2f} 秒")
            return None
        if skip or dry:
            counts["skipped"] += 1
            log(f"⏭️ 账号 {index} 阶段 {number}/4 {name} "
                f"{'断网预演' if dry else '跳过'}，耗时 {time.monotonic() - tick:.2f} 秒")
            return None
        try:
            value = action()
            counts["success"] += 1
            log(f"✅ 账号 {index} 阶段 {number}/4 {name} 成功，耗时 {time.monotonic() - tick:.2f} 秒")
            return value
        except TaskError as exc:
            counts["failed"] += 1
            log(f"❌ 账号 {index} 阶段 {number}/4 {name} {exc}，耗时 {time.monotonic() - tick:.2f} 秒")
            raise

    ok, already = False, False
    try:
        if dry:
            for number, name in enumerate(("刷新访问令牌", "查询签到状态", "执行每日签到", "查询奖励统计"), 1):
                stage(number, name)
            ok = True
        else:
            client = Client(timeout, proxy, debug)
            client.secrets = [refresh]

            def refresh_access():
                data = client.request("POST", "/api/sys/login/refresh", body={"refreshToken": refresh})
                check_status(data)
                result = result_object(data)
                token = result.get("token")
                if not isinstance(token, str) or not token.strip() or re.search(r"[\x00-\x20\x7f]", token):
                    raise TaskError("刷新响应缺少有效访问令牌")
                client.secrets.append(token)
                show_identity(result, client.secrets)
                return token

            access = stage(1, "刷新访问令牌", refresh_access)
            before = {}
            try:
                before = stage(2, "查询签到状态", lambda: welfare(client, access))
            except TaskError as exc:
                if exc.auth:
                    raise
                counts["warning"] += 1
                log("⚠️ 状态读取失败，继续以签到接口的明确业务结果判定")
            checkin = before.get("checkIn", {})
            already = isinstance(checkin, dict) and (checkin.get("todayCheckedIn") is True or
                                                     type(checkin.get("todayCheckedIn")) is int and checkin.get("todayCheckedIn") == 1)
            if already:
                stage(3, "执行每日签到", completed=True)
                stage(4, "查询奖励统计", skip=True)
                log("☑️ 今日已签到")
                show_stats(before)
            else:
                def checkin_action():
                    data = client.request("POST", "/api/sys/checkin/do", token=access)
                    if data["status"] not in (0, 1):
                        raise TaskError("签到业务状态未确认成功", auth=data["status"] == 10025)
                    if isinstance(data.get("result"), dict):
                        show_identity(data["result"], client.secrets)
                    return data["status"]
                code = stage(3, "执行每日签到", checkin_action)
                already = code == 1
                if already:
                    counts["success"] -= 1
                    counts["alreadyComplete"] += 1
                log("☑️ 今日已签到" if already else "✅ 签到成功")
                try:
                    after = stage(4, "查询奖励统计", lambda: welfare(client, access))
                    show_stats(after)
                except TaskError:
                    counts["warning"] += 1
                    log("⚠️ 签到已确认，奖励统计暂不可用")
            ok = True
    except TaskError:
        pass
    except Exception:
        counts["failed"] += 1
        log(f"❌ 账号 {index} 执行异常，已隐藏异常详情")
    names = ("刷新访问令牌", "查询签到状态", "执行每日签到", "查询奖励统计")
    while counts["total"] < 4:
        number = counts["total"] + 1
        stage(number, names[number - 1], skip=True)
    elapsed = round(time.monotonic() - started, 3)
    log(f"账号 {index} 统计　总任务 {counts['total']}，成功 {counts['success']}，"
        f"已完成 {counts['alreadyComplete']}，跳过 {counts['skipped']}，失败 {counts['failed']}，"
        f"警告 {counts['warning']}，耗时 {elapsed:.2f} 秒，结果 {'通过' if ok else '失败'}")
    return {"account": index, "success": ok, "alreadyComplete": already,
            "steps": counts, "elapsedSeconds": elapsed}


def notify(summary, dry):
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return "已关闭"
    if switch not in TRUE_VALUES:
        if not enabled("SOPHNET_NOTIFY", True):
            return "已关闭"
        if enabled("SOPHNET_NOTIFY_ONLY_FAIL") and summary["status"] == "success":
            return "仅失败通知，本次跳过"
        selectors = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
        if selectors is not None:
            names = {CATALOG_ID, Path(__file__).name, "sophnet_checkin.py",
                     "sophnet_checkin/sophnet_checkin.py", "output/candidate.py"}
            names.update(Path(__file__).as_posix().split("/scripts/", 1)[-1:])
            patterns = re.split(r"[,;\s]+", selectors.strip())
            if not any(fnmatch.fnmatchcase(name, pattern) for name in names for pattern in patterns if pattern):
                return "未列入通知名单"
    if dry:
        return "断网预演，已模拟通知"
    body = (f"账号总数 {summary['accounts']}，成功 {summary['success']}，"
            f"失败 {summary['failed']}，最终状态 {summary['status']}")
    # 子进程隔离通知模块的输出、异常与退出，保持业务退出码。
    python_code = (
        "import importlib.util,os,sys; "
        "p=sys.argv[1]; sys.path.insert(0,os.path.dirname(p)); "
        "spec=importlib.util.spec_from_file_location('qinglong_notify',p); "
        "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
        "m.send(sys.argv[2],sys.argv[3])"
    )
    directories = []
    configured = os.getenv("QINGLONG_NOTIFY_DIR")
    if configured:
        directories.append(Path(configured))
    directories.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    commands = []
    try:
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin:
            commands.append([sys.executable, "-c", python_code, spec.origin, TITLE, body])
    except Exception:
        pass
    for directory in directories:
        py = directory / "notify.py"
        js = directory / "sendNotify.js"
        if py.is_file():
            commands.append([sys.executable, "-c", python_code, str(py), TITLE, body])
        if js.is_file():
            commands.append(["node", "-e",
                             "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                             str(js.resolve()), TITLE, body])
    for command in commands:
        try:
            result = subprocess.run(command, timeout=30, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, check=False)
            if result.returncode == 0:
                return "已发送"
        except (OSError, subprocess.TimeoutExpired):
            continue
    return "通知不可用或发送失败，保留业务退出码"


def main():
    started = time.monotonic()
    dry = enabled("SOPHNET_DRY_RUN")
    tokens = [line.strip() for line in os.getenv("SOPHNET_REFRESH_TOKEN", "").splitlines() if line.strip()]
    log("=" * 60)
    log(f"{TITLE}　开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}")
    log(f"运行模式 {'断网预演' if dry else '正式执行'}，账号数 {len(tokens)}")
    results = []
    configuration_error = False
    try:
        timeout = int(os.getenv("SOPHNET_TIMEOUT") or "30")
        if not 1 <= timeout <= 300:
            raise ValueError
        proxy = os.getenv("SOPHNET_PROXY", "").strip()
        if proxy:
            parsed = urllib.parse.urlsplit(proxy)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise ValueError
        if not tokens:
            raise ValueError
    except ValueError:
        configuration_error = True
        log("❌ 配置错误，请检查 SOPHNET_REFRESH_TOKEN、SOPHNET_TIMEOUT 和 SOPHNET_PROXY 的格式")
    if not configuration_error:
        for index, token in enumerate(tokens, 1):
            results.append(run_account(token, index, len(tokens), timeout, proxy,
                                       enabled("SOPHNET_DEBUG"), dry))
            if index < len(tokens) and not dry:
                time.sleep(1)
    success = sum(result["success"] for result in results)
    failed = len(tokens) - success
    status = ("configuration-error" if configuration_error else
              "partial-failure" if failed and success else "failure" if failed else
              "dry-run" if dry else "success")
    exit_code = 1 if configuration_error or failed else 0
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "status": status,
               "accounts": len(tokens), "success": success, "failed": failed,
               "results": results, "exitCode": exit_code}
    try:
        summary["notification"] = notify(summary, dry)
    except Exception:
        summary["notification"] = "通知失败，保留业务退出码"
    summary["elapsedSeconds"] = round(time.monotonic() - started, 3)
    summary["finishedAt"] = datetime.now().isoformat(timespec="seconds")
    log("-" * 60)
    log(f"任务统计　账号总数 {len(tokens)}，成功 {success}，失败 {failed}")
    for key, label in (("total", "总任务"), ("success", "成功"), ("alreadyComplete", "已完成"),
                       ("skipped", "跳过"), ("failed", "失败"), ("warning", "警告")):
        log(f"子任务统计　{label} {sum(item['steps'][key] for item in results)}")
    log(f"通知状态　{summary['notification']}")
    log(f"总耗时 {summary['elapsedSeconds']:.2f} 秒，完成时间 {summary['finishedAt']}，最终状态 {status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
