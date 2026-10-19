# -*- coding: utf-8 -*-
# name: CCAVA每日签到
# cron: 31 1 * * *
# new Env('CCAVA每日签到');
# 来源：OreosLab/checkinpanel，ck_ccava.py
# 原始提交：911402e4b2e559ffd62c4949a971ddd6834edd7d；许可：MIT
# 原始文件未附版权声明；保留上游署名及 MIT 许可。
"""CCAVA_COOKIE：每个非空行填写一个账号的完整 Cookie。
在 https://pc.ccava.net 登录后，从浏览器开发者工具 Network 中复制
该站点已登录请求的 Cookie 请求头值（不含 Cookie: 前缀）。不要公开凭据。
每天 18:55 签到；无需另一个仓库或私有工具。Python 3.8+，仅标准库。
CCAVA_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
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
        _ql_notify_identities = ('93e0b2068d55d68f', 'scripts/ck_ccava.py', 'ck_ccava.py', 'ck_ccava')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import contextlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import time
import urllib.request

TITLE = "CCAVA每日签到"
URL = "https://pc.ccava.net/zb_users/plugin/mochu_us/cmd.php?act=qiandao"
DISABLED = {"0", "false", "no", "off"}


def log(message):
    print("[{}] {}".format(time.strftime("%H:%M:%S"), message), flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不向登录页或其他域名转发 Cookie，也不重复签到请求。
        return None


def sign(cookie):
    request = urllib.request.Request(URL, headers={"Cookie": cookie,
                                                 "Accept": "application/json"})
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError("HTTP 状态异常")
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("响应过大")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("msg"), str):
        raise ValueError("响应格式不符合签到契约")
    msg = data["msg"].strip()
    # 上游没有可核实的业务码；只接受明确成功或明确今天已签到文案。
    if re.search(r"登录|登陆|失败|错误|无效|过期|异常|未成功|不成功|不能|无法|未签到成功|不是.{0,8}签到成功|没有.{0,8}签到成功", msg):
        raise ValueError("签到未获业务成功确认，可能需要更新 Cookie")
    if re.search(r"重复签到|今天.{0,8}(?:已签到|已经签到|签到过)", msg):
        status = "alreadyComplete"
    elif "签到成功" in msg:
        status = "success"
    else:
        raise ValueError("签到结果未获明确业务确认")
    balance = data.get("giod")
    balance = str(balance) if isinstance(balance, (str, int, float)) else ""
    if not re.fullmatch(r"\d+(?:\.\d+)?", balance):
        balance = None
    return status, balance, data


def identity(data, cookie):
    for key in ("nickname", "username", "displayName", "display_name", "uid"):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value)
            # 保留官方身份字段；凭据及手机号不进入日志。
            secrets = [cookie] + [part.split("=", 1)[1].strip()
                                  for part in cookie.split(";") if "=" in part]
            for secret in secrets:
                if secret:
                    value = value.replace(secret, "[凭据已隐藏]")
            value = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", value)
            return value.replace("\n", " ").replace("\r", " ")
    return None


def notify(summary, dry_run):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in DISABLED:
        return "已关闭"
    if dry_run:
        # 通知工具可能联网：断网模式只预演发送，不导入或调用工具。
        log("⏭️ 通知预演：" + summary)
        return "断网预演"
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                module = importlib.import_module("notify")
            except ImportError:
                module = None
            if module is None or not callable(getattr(module, "send", None)):
                paths = []
                directory = os.getenv("QINGLONG_NOTIFY_DIR")
                if directory:
                    paths.append(Path(directory) / "notify.py")
                paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
                for path in paths:
                    if path.is_file():
                        spec = importlib.util.spec_from_file_location("ql_notify", path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        if callable(getattr(module, "send", None)):
                            break
            if module is None or not callable(getattr(module, "send", None)):
                raise RuntimeError("通知工具不可用")
            module.send(TITLE, summary)
        return "已发送"
    except Exception:
        log("⚠️ 通知工具不可用或发送失败；保留业务退出码")
        return "不可用或失败"


def main():
    started = time.monotonic()
    dry_run = os.getenv("CCAVA_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}
    accounts = [line.strip() for line in os.getenv("CCAVA_COOKIE", "").splitlines() if line.strip()]
    log("========== {} ==========".format(TITLE))
    log("开始时间：{}；模式：{}；账号数：{}".format(
        time.strftime("%Y-%m-%d %H:%M:%S"), "断网预演" if dry_run else "实际签到", len(accounts)))
    stats = dict(total=len(accounts), success=0, alreadyComplete=0, skipped=0, failure=0)
    config_error = not accounts
    if config_error:
        log("❌ 阶段 1 参数检查：缺少 CCAVA_COOKIE；每个非空行填写一个账号 Cookie")
    for number, cookie in enumerate(accounts, 1):
        account_start = time.monotonic()
        status = "failure"
        log("账号 {} / 阶段 1 参数检查".format(number))
        try:
            if "=" not in cookie or any(ord(char) < 32 or ord(char) > 255 for char in cookie):
                raise ValueError("Cookie 格式错误")
            log("✅ 参数检查通过；阶段 1 耗时 {:.2f}秒".format(time.monotonic() - account_start))
            stage_start = time.monotonic()
            log("账号 {} / 阶段 2 每日签到".format(number))
            if dry_run:
                status = "skipped"
                log("⏭️ DRY_RUN_OK：参数有效；已预演签到和余额查询，未发送请求")
            else:
                status, balance, data = sign(cookie)
                label = identity(data, cookie)
                if label is not None:
                    log("账号 {} 官方身份：{}".format(number, label))
                log("{} {}{}".format("☑️" if status == "alreadyComplete" else "✅",
                    "今天已签到" if status == "alreadyComplete" else "签到成功",
                    "，剩余 {} 月光币".format(balance) if balance is not None else "，未返回有效余额"))
            log("阶段 2 耗时 {:.2f}秒".format(time.monotonic() - stage_start))
        except ValueError as error:
            # 只输出本脚本定义的错误，绝不输出 JSON 解码器或服务端原文。
            message = str(error) if type(error) is ValueError else "响应不是有效 JSON"
            log("❌ 账号 {}：{}".format(number, message))
        except Exception:
            log("❌ 账号 {}：网络、超时或响应处理失败；未确认签到成功".format(number))
        stats[status] += 1
        log("账号 {} 统计：总任务 1，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒".format(
            number, int(status == "success"), int(status == "alreadyComplete"),
            int(status == "skipped"), int(status == "failure"), time.monotonic() - account_start))
    exit_code = int(config_error or stats["failure"] > 0)
    final_status = ("configuration-error" if config_error else "partial-failure" if exit_code and
                    stats["failure"] < len(accounts) else "failure" if exit_code else
                    "dry-run" if dry_run else "success")
    body = "账号总数 {}，成功 {}，失败 {}，已完成 {}，跳过 {}；状态 {}".format(
        len(accounts), stats["success"], stats["failure"], stats["alreadyComplete"], stats["skipped"], final_status)
    notification = notify(body, dry_run)
    log("----------------------------------------")
    log("任务统计：" + body)
    log("子任务统计：总数 {}；通知状态：{}".format(len(accounts), notification))
    log("完成时间：{}；总耗时 {:.2f}秒；最终状态：{}".format(
        time.strftime("%Y-%m-%d %H:%M:%S"), time.monotonic() - started, final_status))
    print("TASK_SUMMARY=" + json.dumps(dict(stats, status=final_status, configurationError=config_error,
          dryRun=dry_run, notification=notification, exitCode=exit_code), ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
