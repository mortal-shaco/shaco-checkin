# name: 有道云笔记每日空间奖励
# cron: 55 0 * * *
"""独立维护版；来源 Sitoi/dailycheckin dailycheckin/youdao/main.py，
以及 lizhixu/ql-script-hub 的 youdao.py。
上游提交：135cc236e59ac4f14bcddc44acb3cbb3ed6010b5、
ac591a320092dcaeaf236b7c2b6acfd28981e589；均为 MIT。
YOUDAO_COOKIE：网页 note.youdao.com 登录后，从开发者工具 Network 中复制
发往 note.youdao.com 请求的完整 Cookie 请求头（不含 Cookie: 前缀）。
每行一个账号；分号分隔 Cookie 字段，字段只在第一个等号处分割。
默认依次同步奖励、签到、领取三次广告空间奖励；会改变账号空间额度。
YOUDAO_AD_REWARDS=0 可关闭三次广告奖励；默认 1 保留原动作。
YOUDAO_DRY_RUN=1 完全断网预演，通知也只模拟；不验证真实凭据。
QINGLONG_NOTIFY=0 关闭通知；可用 QINGLONG_NOTIFY_DIR 指定青龙通知目录。
上游未提供调度，本维护版建议每日 08:00（以青龙时区为准）。

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
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('4cc5f70c13c67bbd', 'scripts/youdao.py', 'youdao.py', 'youdao')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

TITLE = "有道云笔记每日空间奖励"
DISABLED = {"0", "false", "no", "off"}
BASE = "https://note.youdao.com"
LIMIT = 1024 * 1024


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def enabled(name, default="0"):
    return os.getenv(name, default).strip().lower() not in DISABLED | {""}


class TaskError(Exception):
    pass


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 登录跳转不代表业务成功，禁止重定向携带凭据。
        raise TaskError("接口发生重定向，可能需要重新登录")


def parse_cookie(line):
    result = {}
    for part in line.split(";"):
        if not part.strip():
            continue
        name, sep, value = part.strip().partition("=")
        if (not sep or not name or not value
                or any(c in name for c in " \t\r\n:")
                or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise TaskError("Cookie 格式错误，请复制完整请求头")
        result[name] = value
    if not result.get("YNOTE_PERS"):
        raise TaskError("Cookie 缺少 YNOTE_PERS，请重新获取登录凭据")
    return result


class Client:
    def __init__(self, cookies):
        jar = http.cookiejar.CookieJar()
        for name, value in cookies.items():
            jar.set_cookie(http.cookiejar.Cookie(
                0, name, value, None, False, "note.youdao.com", False, False,
                "/", True, True, None, True, None, None, {}, False))
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar), RestrictedRedirect())

    def request(self, path, method="POST", require_json=True):
        req = urllib.request.Request(
            BASE + path, data=b"" if method == "POST" else None,
            method=method, headers={"Accept": "application/json", "User-Agent": "Youdao-Qinglong/1.0"})
        try:
            with self.opener.open(req, timeout=15) as response:
                data = response.read(LIMIT + 1)
                if response.status != 200:
                    raise TaskError("接口 HTTP 状态异常")
        except urllib.error.HTTPError as exc:
            raise TaskError(f"接口 HTTP 错误 {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络连接失败或超时") from None
        if len(data) > LIMIT:
            raise TaskError("接口响应超过大小限制")
        if not require_json:
            # 会话接口响应格式未在源码中声明；后续奖励接口必须逐项验证。
            return None
        try:
            result = json.loads(data)
        except (ValueError, UnicodeError):
            raise TaskError("接口未返回有效 JSON，可能需要重新登录") from None
        if not isinstance(result, dict):
            raise TaskError("接口响应结构异常")
        if "error" in result or "errorCode" in result:
            raise TaskError("接口返回业务错误，请检查登录状态")
        # 不臆测未知业务码含义；遇到未有依据的状态字段时失败闭合。
        if "code" in result or "success" in result:
            raise TaskError("接口新增状态字段，需核对业务协议后继续")
        return result


def reward(result, key):
    value = result.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TaskError("奖励字段缺失或无效，无法确认业务成功")
    return value // 1048576


def identity(result):
    # 只显示官方返回的非敏感身份，不从会话 Cookie 推导身份。
    for key in ("nickname", "username", "displayName", "publicUid"):
        value = result.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value)
            if value and not any(c in value for c in "\r\n"):
                # 手机号即使被标记为用户名也不输出。
                digits = "".join(c for c in value if c.isdigit())
                if key != "publicUid" and len(digits) >= 11:
                    continue
                log(f"官方账号身份（{key}）：{value}")


def notify(body, dry):
    if not enabled("QINGLONG_NOTIFY", "1"):
        return "已关闭"
    if dry:
        log("⏭️ 断网预演：模拟发送脱敏通知")
        return "预演模拟"
    paths = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR")
    if custom:
        paths.append(Path(custom))
    paths.extend([Path(__file__).resolve().parent, Path("/ql/data/scripts"), Path("/ql/scripts")])
    try:
        spec = importlib.util.find_spec("notify")
    except (ImportError, ValueError):
        spec = None
    candidates = ([Path(spec.origin)] if spec and spec.origin else [])
    candidates.extend(p / "notify.py" for p in paths)
    # 子进程设超时，禁止通知实现改变业务退出码或向日志输出凭据。
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        program = ("import importlib.util,sys; "
                   "s=importlib.util.spec_from_file_location('ql_notify',sys.argv[1]); "
                   "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                   "m.send(sys.argv[2],sys.argv[3])")
        try:
            subprocess.run([sys.executable, "-c", program, str(path), TITLE, body],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20, check=True)
            return "已发送"
        except (OSError, subprocess.SubprocessError):
            log("⚠️ Python 通知发送失败，继续尝试兼容通知")
    for directory in paths:
        path = directory / "sendNotify.js"
        if not path.is_file():
            continue
        program = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
        try:
            subprocess.run(["node", "-e", program, str(path), TITLE, body],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20, check=True)
            return "已发送"
        except (OSError, subprocess.SubprocessError):
            log("⚠️ JavaScript 通知发送失败")
    log("⚠️ 通知不可用，保留业务退出码")
    return "不可用或失败"


def main():
    started = time.monotonic()
    dry = enabled("YOUDAO_DRY_RUN")
    ads_enabled = enabled("YOUDAO_AD_REWARDS", "1")
    accounts = [line.strip() for line in os.getenv("YOUDAO_COOKIE", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry else '实际运行'}；账号数：{len(accounts)}")
    totals = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    results = []
    config_error = not accounts
    if config_error:
        log("❌ 配置错误：请设置 YOUDAO_COOKIE，每行一个账号")
    for index, line in enumerate(accounts, 1):
        account_start = time.monotonic()
        counts = {key: 0 for key in totals}
        earned = 0
        stages = [("同步奖励", "/yws/api/daupromotion?method=sync", "rewardSpace"),
                  ("每日签到", "/yws/mapi/user?method=checkin", "space")]
        stages.extend((f"广告奖励 {n}/3", "/yws/mapi/user?method=adRandomPrompt", "space") for n in range(1, 4))
        log(f"----- 账号 {index} -----")
        completed = 0
        stage_start = account_start
        try:
            cookies = parse_cookie(line)
            client = None if dry else Client(cookies)
            stage_start = time.monotonic()
            log(f"账号 {index} 阶段 1/6：刷新登录会话")
            if client:
                client.request("/login/acc/pe/getsess?product=YNOTE", "GET", False)
            counts["success"] += 1
            completed += 1
            log(f"{'⏭️ 预演：不发送请求' if dry else '✅ 会话请求完成，等待奖励接口验证登录'}；耗时 {time.monotonic()-stage_start:.2f} 秒")
            for number, (label, path, key) in enumerate(stages, 2):
                stage_start = time.monotonic()
                log(f"账号 {index} 阶段 {number}/6：{label}")
                if label.startswith("广告奖励") and not ads_enabled:
                    counts["skipped"] += 1
                    completed += 1
                    log("⏭️ 广告奖励已通过 YOUDAO_AD_REWARDS=0 关闭")
                    continue
                if dry:
                    log("⏭️ 预演：接口、方法和奖励校验已就绪，不发送请求")
                else:
                    result = client.request(path)
                    space = reward(result, key)
                    identity(result)
                    earned += space
                    log(f"✅ {label}已确认，空间奖励 {space}M")
                counts["success"] += 1
                completed += 1
                log(f"阶段耗时 {time.monotonic()-stage_start:.2f} 秒")
        except TaskError as exc:
            counts["failed"] += 1
            counts["skipped"] = 6 - completed - 1
            log(f"❌ 账号 {index}：{exc}；阶段耗时 {time.monotonic()-stage_start:.2f} 秒；后续步骤已跳过")
        except Exception:
            counts["failed"] += 1
            counts["skipped"] = 6 - completed - 1
            log(f"❌ 账号 {index}：未预期的本地错误，已隐藏异常详情；阶段耗时 {time.monotonic()-stage_start:.2f} 秒")
        for key in totals:
            totals[key] += counts[key]
        ok = counts["failed"] == 0
        results.append({"account": index, "ok": ok, "statistics": counts})
        log(f"账号 {index} 统计：总任务 6，成功 {counts['success']}，已完成 0，跳过 {counts['skipped']}，失败 {counts['failed']}；耗时 {time.monotonic()-account_start:.2f} 秒")
        log(f"获取空间: {'预演未领取' if dry else '+' + str(earned) + 'M（仅已确认奖励）'}")
    succeeded = sum(item["ok"] for item in results)
    failed = len(results) - succeeded
    exit_code = 1 if config_error or failed else 0
    status = "configuration-error" if config_error else ("partial-failure" if failed and succeeded else "failure" if failed else "dry-run" if dry else "success")
    body = f"状态：{status}；账号总数：{len(accounts)}；成功：{succeeded}；失败：{failed}；预演：{'是，未验证真实业务' if dry else '否'}"
    notification = notify(body, dry)
    log("----------------------------------------")
    log(body)
    log(f"子任务统计：{json.dumps(totals, ensure_ascii=False)}；总耗时 {time.monotonic()-started:.2f} 秒")
    log(f"完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；通知：{notification}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "mode": "dry-run" if dry else "live", "status": status,
          "accounts": len(accounts), "succeeded": succeeded, "failed": failed, "statistics": totals,
          "notification": notification, "results": results, "exitCode": exit_code}, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
