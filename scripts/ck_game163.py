# -*- coding: utf-8 -*-
# name: 网易云游戏每日签到
# cron: 21 1 * * *
"""
cron: 21 1 * * *
new Env('网易云游戏每日签到');

来源：OreosLab/checkinpanel，ck_game163.py，MIT 许可。
原始提交：911402e4b2e559ffd62c4949a971ddd6834edd7d
原文件未附版权声明；保留上述原始任务元数据。

GAME163_AUTHORIZATION：每个非空行填写一个账号的完整 Authorization 请求头。
在本人登录的网易云游戏网页 https://cg.163.com/ 中打开浏览器开发者工具，
从网络面板的 n.cg.163.com 请求获取 Authorization；保留其完整值和可能的前缀。
不要公开该值。兼容 GAME163：换行分隔的凭据，或原账号配置的 JSON 数组，
数组每项为包含 authorization 的对象；规范变量优先。不使用 & 或 @ 分隔账号。
GAME163_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
预演仅模拟通知，不加载通知模块，以保证不会通过通知渠道联网。
仅执行每日签到，不自动执行消费、发帖或修改账号资料。
HTTPS 接口和业务响应未经过在线验证；未知响应一律按失败处理。

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
        _ql_notify_identities = ('86bf0d1d9f07edf8', 'scripts/ck_game163.py', 'ck_game163.py', 'ck_game163')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request


TITLE = "网易云游戏"
ENDPOINT = "https://n.cg.163.com/api/v2/sign-today"
TIMEOUT = 15
MAX_RESPONSE = 65536
UA = ("Mozilla/5.0 (Linux; Android 10; Redmi K30 Build/QKQ1.190825.002; wv) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
      "Chrome/85.0.4183.127 Mobile Safari/537.36")
DISABLED = {"0", "false", "no", "off"}
SUCCESS_TEXT = {"签到成功", "今日签到成功", "今日已签到", "今天已签到", "已签到", "今日已签过"}
ALREADY_TEXT = {"今日已签到", "今天已签到", "已签到", "今日已签过"}


def timestamp():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def log(message):
    print("[{}] {}".format(datetime.datetime.now().strftime("%H:%M:%S"), message), flush=True)


def load_accounts():
    raw = os.environ.get("GAME163_AUTHORIZATION", "").strip()
    if not raw:
        raw = os.environ.get("GAME163", "").strip()
        if raw.startswith("["):
            try:
                items = json.loads(raw)
            except (ValueError, TypeError):
                raise ValueError("GAME163 兼容配置必须是有效的账号 JSON 数组") from None
            if not isinstance(items, list) or not items:
                raise ValueError("GAME163 兼容配置必须是非空数组")
            return [item.get("authorization") if isinstance(item, dict) else None for item in items]
    if not raw:
        raise ValueError("缺少 GAME163_AUTHORIZATION，每个非空行填写一个账号")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def valid_credential(value):
    # 不切分凭据内部字符，拒绝 HTTP 请求头注入和无法编码的请求头。
    return (isinstance(value, str) and bool(value.strip()) and
            all(32 <= ord(char) <= 126 for char in value))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 防止 Authorization 经跳转发往其他地址；也不自动重试签到请求。
        return None


def business_result(body):
    """不将 HTTP 200、空响应、一般 success 或未知数字业务码视为签到成功。"""
    text = body.strip()
    try:
        payload = json.loads(text)
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        # 明确错误字段优先于可能存在的成功文字。
        if payload.get("success") is False or payload.get("error") not in (None, False, "", 0):
            return False, False, payload
        for field in ("code", "status", "retcode"):
            value = payload.get(field)
            if value is False:
                return False, False, payload
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value not in (0, 200):
                return False, False, payload
            if isinstance(value, str) and value.strip().lower() in {"error", "failed", "failure"}:
                return False, False, payload
            if isinstance(value, str) and value.strip().lstrip("-").isdigit() and value.strip() not in {"0", "200"}:
                return False, False, payload
        text = next((payload[key].strip() for key in ("msg", "message", "detail")
                     if isinstance(payload.get(key), str)), "")
    elif payload is not None:
        # JSON 字符串可以是明确的业务文字，其他 JSON 类型无法核验。
        text = payload.strip() if isinstance(payload, str) else ""
    text = text.rstrip("。！!.")
    return text in SUCCESS_TEXT, text in ALREADY_TEXT, payload


def show_identity(payload, credentials):
    if not isinstance(payload, dict):
        return
    containers = [payload]
    if isinstance(payload.get("data"), dict):
        containers.append(payload["data"])
    for container in containers:
        for key in ("nickname", "username", "displayName", "uid"):
            value = container.get(key)
            if value is None or isinstance(value, (dict, list, bool)):
                continue
            identity = str(value)
            # 身份按官方原值显示；疑似敏感内容则不输出，不做掩码替代。
            if (not identity or len(identity) > 200 or any(ord(c) < 32 for c in identity)
                    or any(secret and secret in identity for secret in credentials)
                    or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", identity)
                    or re.search(r"(?i)(bearer\s|token[=:]|cookie[=:]|session[=:])", identity)):
                continue
            log("账号身份 {}：{}".format(key, identity))
            return


def checkin(authorization, credentials):
    request = urllib.request.Request(ENDPOINT, data=b"", method="POST",
                                     headers={"User-Agent": UA, "Authorization": authorization})
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                return False, False, "HTTP 状态不符合预期"
            body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            return False, False, "响应超出大小限制"
        decoded = body.decode("utf-8", errors="strict")
        success, already, payload = business_result(decoded)
        show_identity(payload, credentials)
        if not success:
            return False, False, "未获得明确签到成功结果；请检查凭据或接口契约（原始响应不输出）"
        return True, already, "今日已签到" if already else "签到成功"
    except urllib.error.HTTPError as exc:
        return False, False, "HTTP {}，请求失败".format(exc.code)
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeError, ValueError):
        return False, False, "网络、超时或响应解析失败（敏感详情不输出）"


def notify_summary(body, dry_run):
    if os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in DISABLED:
        log("⏭️ 通知已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    if dry_run:
        log("⏭️ 断网预演：通知总结已生成，模拟通知投递")
        return "simulated"
    # 隔离通知输出并限制耗时，不让通知故障改变业务退出码。
    notifier = r'''
import importlib.util, os, sys
try:
    from notify import send
except ImportError:
    paths = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(os.path.join(directory, "notify.py"))
    paths.extend(["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"])
    send = None
    for path in paths:
        if not os.path.isfile(path):
            continue
        spec = importlib.util.spec_from_file_location("qinglong_notify", path)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.dirname(path))
        spec.loader.exec_module(module)
        send = getattr(module, "send", None)
        if callable(send):
            break
    if not callable(send):
        sys.exit(2)
result = send(sys.argv[1], sys.argv[2])
sys.exit(1 if result is False else 0)
'''
    try:
        result = subprocess.run([sys.executable, "-c", notifier, TITLE, body],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
                                check=False)
        if result.returncode == 0:
            log("✅ 已调用青龙通知")
            return "sent"
    except (OSError, subprocess.TimeoutExpired):
        pass
    log("⚠️ 青龙通知不可用或投递失败，保留业务退出码")
    return "unavailable-or-failed"


def main():
    started = time.monotonic()
    dry_run = os.environ.get("GAME163_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}
    log("========== {} ==========".format(TITLE))
    log("开始时间：{}；模式：{}".format(timestamp(), "断网预演" if dry_run else "实际签到"))
    results = []
    accounts = []
    config_error = None
    try:
        accounts = load_accounts()
    except ValueError as exc:
        config_error = str(exc)
    log("账号数量：{}".format(len(accounts)))
    if config_error:
        log("❌ 阶段 1 参数检查：{}".format(config_error))
    credentials = [item for item in accounts if isinstance(item, str)]
    for index, authorization in enumerate(accounts, 1):
        account_start = time.monotonic()
        stage_start = time.monotonic()
        log("账号 {} / 阶段 1 参数检查".format(index))
        valid = valid_credential(authorization)
        log("{} 参数检查，耗时 {:.3f} 秒".format("✅ 通过" if valid else "❌ 凭据缺失或格式无效",
                                                time.monotonic() - stage_start))
        status = "failure"
        if valid:
            stage_start = time.monotonic()
            log("账号 {} / 阶段 2 每日签到".format(index))
            if dry_run:
                log("✅ DRY_RUN_OK：请求及结果处理预演通过，未发送网络请求")
                status = "dry-run"
            else:
                ok, already, detail = checkin(authorization, credentials)
                status = "already-complete" if ok and already else "success" if ok else "failure"
                log("{} {}".format("☑️" if already else "✅" if ok else "❌", detail))
            log("阶段 2 耗时 {:.3f} 秒".format(time.monotonic() - stage_start))
        elapsed = round(time.monotonic() - account_start, 3)
        result = {"account": index, "status": status, "elapsedSeconds": elapsed}
        results.append(result)
        log("账号 {} 统计：总任务 1，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.3f} 秒".format(
            index, int(status == "success"), int(status == "already-complete"),
            int(status == "dry-run"), int(status == "failure"), elapsed))
    failed = sum(result["status"] == "failure" for result in results)
    passed = len(results) - failed
    exit_code = 1 if config_error or failed else 0
    status = ("configuration-error" if config_error else "partial-failure" if failed and passed
              else "failure" if failed else "dry-run" if dry_run else "success")
    body = "模式：{}；账号总数 {}，成功数 {}，失败数 {}；最终状态 {}".format(
        "断网预演（未验证业务）" if dry_run else "实际签到", len(accounts), passed, failed, status)
    if config_error:
        body += "；参数配置错误"
    log("阶段 3 结果通知")
    notify_start = time.monotonic()
    notification = notify_summary(body, dry_run)
    log("阶段 3 耗时 {:.3f} 秒".format(time.monotonic() - notify_start))
    finished = timestamp()
    elapsed = round(time.monotonic() - started, 3)
    log("----------------------------------------")
    log(body)
    log("子任务统计：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
        len(results), sum(r["status"] == "success" for r in results),
        sum(r["status"] == "already-complete" for r in results),
        sum(r["status"] == "dry-run" for r in results), failed))
    log("总耗时 {:.3f} 秒；完成时间 {}；通知状态 {}；最终状态 {}".format(
        elapsed, finished, notification, status))
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "status": status, "dryRun": dry_run,
          "accounts": len(accounts), "success": passed, "failed": failed,
          "verifiedSuccess": sum(r["status"] in {"success", "already-complete"} for r in results),
          "results": results, "notification": notification, "finishedAt": finished,
          "elapsedSeconds": elapsed, "exitCode": exit_code}, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
