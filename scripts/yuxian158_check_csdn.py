# -*- coding: utf-8 -*-
# name: CSDN每日签到与可选抽奖
# cron: 36 1 * * *
# publish_path: scripts/csdn_daily_checkin.py
# new Env('CSDN每日签到与可选抽奖');
"""CSDN 独立维护版（Python 3，仅标准库）。

来源：yuxian158/check，dailycheckin_scripts/ck_csdn.py
上游提交：723c834f121ff4eef2dec7afe521071a7efff1a9；许可证：MIT。
上游没有内嵌版权声明；保留来源归属和 MIT 许可。

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

青龙变量 CSDN_COOKIE：每个非空行保存一个账号的完整 Cookie。
浏览器登录 https://www.csdn.net 后，打开开发者工具的网络面板，
从发往 CSDN 的已登录请求复制 Cookie 请求头（不要复制到日志或公开仓库）。
Cookie 各字段以分号分隔，字段仅在第一个等号处分割，保留值中的等号。
兼容变量 csdn_cookie；优先使用 CSDN_COOKIE，不合并两者。
每天签到；CSDN_DRAW=1 显式启用抽奖，可能消耗抽奖机会，默认关闭。
上游未声明时间；本维护版建议每天北京时间 08:00（青龙时区自行设置）。
CSDN_DRY_RUN=1 完全断网，仅验证参数和任务规划，通知在本地预演。
QINGLONG_NOTIFY 默认为 auto；设为 0/false/no/off 关闭通知。
QINGLONG_NOTIFY_SCRIPTS 可用逗号、分号、空白或换行指定脚本；显式空值关闭全部。
QINGLONG_NOTIFY_DIR 可指定青龙 notify.py 或 sendNotify.js 所在目录。
接口沿用上游，未经过真实业务验证；不把 dry-run 当作签到成功。
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
        _ql_notify_identities = ('9a5f757a8ae60a32', 'scripts/yuxian158_check_csdn.py', 'yuxian158_check_csdn.py', 'yuxian158_check_csdn')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

from fnmatch import fnmatchcase
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from urllib.request import Request, build_opener, HTTPRedirectHandler


TITLE = "CSDN每日签到"
CATALOG_ID = "9a5f757a8ae60a32"
CANONICAL_PATH = "scripts/csdn_daily_checkin.py"
BASE = "https://me.csdn.net/api/LuckyDraw_v2/"
FALSE = {"0", "false", "no", "off"}
TRUE = {"1", "true", "yes", "on"}


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def flag(name, default="0"):
    value = os.getenv(name, default).strip().lower()
    if value not in FALSE | TRUE:
        raise ValueError(f"{name} 必须为 1/0、true/false、yes/no 或 on/off")
    return value in TRUE


def parse_cookie(line):
    if any(ord(char) < 32 or ord(char) > 126 for char in line):
        raise ValueError("Cookie 含不支持的字符，请复制完整请求头")
    fields = {}
    for part in line.split(";"):
        part = part.strip()
        if not part:
            continue
        key, separator, value = part.partition("=")
        if not separator or not key or not value or any(char.isspace() for char in key):
            raise ValueError("Cookie 格式错误，需要以分号分隔的名称=值")
        fields[key] = value
    if not fields:
        raise ValueError("Cookie 不能为空")
    return "; ".join(f"{key}={value}" for key, value in fields.items())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不将凭据转发到重定向地址，也不将登录页面视为成功。
        return None


def request_action(action, cookie):
    request = Request(
        BASE + action,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Cookie": cookie,
        },
        method="GET",
    )
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError("HTTP 状态异常")
        body = response.read(65537)
        if len(body) > 65536:
            raise ValueError("响应超过大小限制")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError("响应不是 JSON 对象")
    data = result.get("data")
    if result.get("code") != 200 or not isinstance(data, dict):
        raise ValueError("业务状态未通过，请检查登录状态或接口变化")
    message = data.get("msg")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("业务响应缺少结果说明")
    # 不输出服务端消息：它可能包含凭据、电话号码或原始异常。
    if any(word in message.lower() for word in (
        "失败", "未登录", "登录失效", "过期", "不足", "无机会", "没有机会",
        "次数用完", "上限", "异常", "错误", "error", "fail", "登录后",
    )):
        raise ValueError("业务返回未成功，请检查登录状态、机会或接口变化")
    already = action == "signIn" and any(
        word in message for word in ("已签到", "已经签到", "重复签到")
    )
    # 仅接受明确的业务结果，拒绝不认识的 code=200 消息。
    markers = ("签到成功", "签到了", "签到完成") if action == "signIn" else (
        "抽奖成功", "恭喜", "获得", "中奖", "谢谢参与", "未中奖", "再接再厉",
    )
    if not already and not any(word in message for word in markers):
        raise ValueError("无法确认业务成功，需核对接口结果格式")
    return result, data, already


def show_identity(objects, cookie):
    secret_values = [
        part.partition("=")[2]
        for part in cookie.split("; ")
        if part.partition("=")[0].lower() not in ("username", "nickname")
    ]
    for source in objects:
        if not isinstance(source, dict):
            continue
        for key in ("nickname", "nickName", "username", "userName", "displayName", "uid"):
            value = source.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            looks_like_phone = key != "uid" and value.isdigit() and len(value) == 11
            if (
                value
                and len(value) <= 120
                and not any(ord(char) < 32 for char in value)
                and not looks_like_phone
                and not any(
                    secret
                    and (value == secret or (len(secret) >= 8 and secret in value))
                    for secret in secret_values
                )
            ):
                log(f"官方账号身份：{value}")
                return


def notification_selection():
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return False, "已关闭"
    if switch not in TRUE | {"auto"}:
        return False, "配置无效（未发送）"

    raw_selectors = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if raw_selectors is None:
        return True, ""
    selectors = [item for item in re.split(r"[,;\s]+", raw_selectors.strip()) if item]
    if not selectors:
        return False, "脚本选择列表为空（未发送）"

    current_name = Path(__file__).name
    candidates = {
        CATALOG_ID,
        CANONICAL_PATH,
        Path(CANONICAL_PATH).name,
        current_name,
        f"output/{current_name}",
    }
    selected = any(
        selector == "*" or any(fnmatchcase(candidate, selector) for candidate in candidates)
        for selector in selectors
    )
    return (True, "") if selected else (False, "当前脚本未被选择")


def notify(body, dry):
    selected, selection_status = notification_selection()
    if not selected:
        return selection_status
    if dry:
        log("通知预演（断网）：" + body)
        return "本地预演"

    directories = []
    configured_directory = os.getenv("QINGLONG_NOTIFY_DIR")
    if configured_directory:
        directories.append(Path(configured_directory))
    directories.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    try:
        try:
            module = importlib.util.find_spec("notify")
        except (ImportError, ValueError):
            module = None
        if module:
            # 子进程限制通知耗时，丢弃通知器输出，避免其打印敏感配置。
            code = "import notify,sys; notify.send(sys.argv[1],sys.argv[2])"
            subprocess.run(
                [sys.executable, "-c", code, TITLE, body],
                check=True,
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "已发送"
        for directory in directories:
            python_file = directory / "notify.py"
            javascript_file = directory / "sendNotify.js"
            if python_file.is_file():
                code = (
                    "import importlib.util,sys; "
                    "s=importlib.util.spec_from_file_location('ql_notify',sys.argv[1]); "
                    "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                    "m.send(sys.argv[2],sys.argv[3])"
                )
                command = [sys.executable, "-c", code, str(python_file), TITLE, body]
            elif javascript_file.is_file():
                command = [
                    "node",
                    "-e",
                    "require(process.argv[1]).sendNotify(process.argv[2],process.argv[3]).catch(()=>process.exit(1))",
                    str(javascript_file),
                    TITLE,
                    body,
                ]
            else:
                continue
            subprocess.run(
                command,
                check=True,
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "已发送"
        return "不可用（未找到青龙通知器）"
    except Exception:
        return "发送失败（保留业务退出码）"


def main():
    started = time.monotonic()
    dry = os.getenv("CSDN_DRY_RUN", "0").strip().lower() in TRUE
    log("========== CSDN每日签到 ==========")
    log(
        f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；"
        f"模式：{'断网预演' if dry else '正式执行'}"
    )
    raw = os.getenv("CSDN_COOKIE") or os.getenv("csdn_cookie", "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    log(f"账号总数：{len(lines)}")
    records = []
    config_error = False
    draw = False
    try:
        dry = flag("CSDN_DRY_RUN")
        draw = flag("CSDN_DRAW")
        if not lines:
            raise ValueError("请设置 CSDN_COOKIE，每个非空行一个账号")
    except ValueError as error:
        log(f"❌ 配置错误：{error}")
        config_error = True

    if not config_error:
        for index, line in enumerate(lines, 1):
            account_start = time.monotonic()
            stats = {
                "account": index,
                "total": 3,
                "success": 0,
                "alreadyComplete": 0,
                "skipped": 0,
                "failed": 0,
            }
            log(f"--- 账号 {index} ---")
            valid = True
            cookie = ""
            stages = (("参数校验", None), ("每日签到", "signIn"), ("抽奖", "goodluck"))
            for number, (stage, action) in enumerate(stages, 1):
                stage_start = time.monotonic()
                log(f"阶段 {number}/3：{stage}")
                try:
                    if action is None:
                        cookie = parse_cookie(line)
                        stats["success"] += 1
                        log("✅ Cookie 格式通过（未验证登录状态）")
                    elif not valid or (action == "goodluck" and not draw):
                        stats["skipped"] += 1
                        log(
                            "⏭️ 参数无效，跳过"
                            if not valid
                            else "⏭️ 抽奖未启用；CSDN_DRAW=1 可启用"
                        )
                    elif dry:
                        stats["skipped"] += 1
                        log(f"⏭️ DRY_RUN：计划执行{stage}，未发送请求")
                    else:
                        result, data, already = request_action(action, cookie)
                        show_identity((data, result), cookie)
                        stats["alreadyComplete" if already else "success"] += 1
                        log("☑️ 今日已签到" if already else f"✅ {stage}业务结果已确认")
                except Exception as error:
                    stats["failed"] += 1
                    if action is None:
                        valid = False
                    # 只有本地构造的 ValueError 可打印，其他异常可能含 URL 或凭据。
                    detail = (
                        str(error)
                        if type(error) is ValueError
                        else "请求或响应处理失败，请检查网络、登录状态和接口"
                    )
                    log(f"❌ {stage}：{detail}")
                log(f"阶段 {number} 耗时：{time.monotonic() - stage_start:.2f} 秒")
            stats["seconds"] = round(time.monotonic() - account_start, 2)
            records.append(stats)
            log(
                f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，"
                f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
                f"失败 {stats['failed']}，耗时 {stats['seconds']} 秒"
            )

    failed = sum(record["failed"] > 0 for record in records)
    passed = len(records) - failed
    exit_code = 1 if config_error or failed else 0
    status = (
        "configuration-error"
        if config_error
        else "partial-failure"
        if failed and passed
        else "failure"
        if failed
        else "dry-run"
        if dry
        else "success"
    )
    body = (
        f"账号总数 {len(lines)}，成功 {passed if not dry else 0}，失败 {failed}，"
        f"预演通过 {passed if dry else 0}，状态 {status}"
    )
    notification = notify(body, dry)
    log("----------------------------------------")
    log(body)
    totals = {
        key: sum(record[key] for record in records)
        for key in ("total", "success", "alreadyComplete", "skipped", "failed")
    }
    log(
        f"子任务统计：总数 {totals['total']}，成功 {totals['success']}，"
        f"已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，"
        f"失败 {totals['failed']}"
    )
    elapsed = round(time.monotonic() - started, 2)
    log(f"总耗时：{elapsed} 秒；通知状态：{notification}")
    finished = datetime.now().isoformat(timespec="seconds")
    log(f"完成时间：{finished}；最终状态：{status}")
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "mode": "dry-run" if dry else "live",
                "status": status,
                "accounts": len(lines),
                "success": passed if not dry else 0,
                "failed": failed,
                "dryRunPassed": passed if dry else 0,
                "configurationError": config_error,
                "stages": totals,
                "results": records,
                "seconds": elapsed,
                "finishedAt": finished,
                "notification": notification,
                "exitCode": exit_code,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
