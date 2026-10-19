# -*- coding: utf-8 -*-
# name: 时光相册每日签到
# cron: 28 1 * * *
"""时光相册每日登录签到（独立维护版）。

来源: yuxian158/check, dailycheckin_scripts/ck_EVERPHOTO.py
上游提交: 723c834f121ff4eef2dec7afe521071a7efff1a9；许可证: MIT。
上游未包含额外版权声明；保留上游来源归属。

EVERPHOTO_ACCOUNT（必填）: 每个非空行一个账号，格式为“手机号|密码”，
仅按第一个竖线分割，密码中的后续竖线会被保留；也支持每行填写包含
mobile、password 的 JSON 对象。手机号和密码来自本人的时光相册账号。
兼容旧变量 EVERPHOTO 和“时光”；新配置请统一使用 EVERPHOTO_ACCOUNT。
EVERPHOTO_DRY_RUN=1: 完全断网预演，不登录、不签到、不加载通知模块。
QINGLONG_NOTIFY 默认 auto；设为 0/false/no/off 可关闭通知。
QINGLONG_NOTIFY_SCRIPTS 可用逗号、分号、空白或换行分隔脚本选择器；
可填写目录编号、scripts/everphoto_daily_checkin.py、文件名或文件名通配符。
上游未声明 cron；本维护版延续候选任务每天北京时间 08:00 的计划。
发布时使用产品专属路径 scripts/everphoto_daily_checkin.py，避免通用路径冲突。

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
        _ql_notify_identities = ('9031ba4f8fdb5e1a', 'scripts/yuxian158_check_everphoto.py', 'yuxian158_check_everphoto.py', 'yuxian158_check_everphoto')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


TITLE = "时光相册每日签到"
CATALOG_ID = "9031ba4f8fdb5e1a"
RELEASE_PATH = "scripts/everphoto_daily_checkin.py"
DISABLED = {"0", "false", "no", "off"}
ENABLED = {"1", "true", "yes", "on"}
DRY_ENABLED = ENABLED
MAX_RESPONSE_BYTES = 1024 * 1024
HTTP_TIMEOUT_SECONDS = 20
HEADERS = {
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 "
        "Safari/537.36 Edg/93.0.961.38"
    ),
    "accept": "*/*",
    "origin": "https://web.everphoto.cn",
    "referer": "https://web.everphoto.cn/",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class TaskError(Exception):
    """只携带固定、脱敏的错误信息。"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """禁止重定向，防止认证信息被转发到意外主机。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("拒绝重定向，避免凭据转发")


def stamp():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def post(url, fields=None, token=None):
    """向固定的时光相册接口发送请求，并验证 HTTP 与业务成功。"""
    allowed_urls = {
        "https://web.everphoto.cn/api/auth",
        "https://api.everphoto.cn/users/self/checkin/v2",
    }
    if url not in allowed_urls:
        raise TaskError("拒绝访问非预期接口")
    headers = dict(HEADERS)
    if token:
        headers["authorization"] = "Bearer " + token
    body = urllib.parse.urlencode(fields or {}).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise TaskError("HTTP 状态异常")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise TaskError("响应超过大小限制")
        result = json.loads(raw)
    except TaskError:
        raise
    except urllib.error.HTTPError:
        raise TaskError("HTTP 请求失败") from None
    except (urllib.error.URLError, OSError, ValueError, UnicodeError):
        raise TaskError("网络、超时或响应解析失败") from None
    if not isinstance(result, dict):
        raise TaskError("接口响应结构异常")
    code = result.get("code")
    if type(code) is not int or code != 0:
        raise TaskError("接口未确认业务成功")
    data = result.get("data")
    if not isinstance(data, dict):
        raise TaskError("接口数据结构异常")
    return data


def parse_account(line):
    """解析单行账号；文本格式只在第一个竖线处分割。"""
    try:
        if line.lstrip().startswith("{"):
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError()
            mobile, password = value.get("mobile"), value.get("password")
        else:
            mobile, password = line.split("|", 1)
            mobile = mobile.strip()
        if (
            not isinstance(mobile, str)
            or not mobile.strip()
            or not isinstance(password, str)
            or not password
        ):
            raise ValueError()
        if any(char in mobile + password for char in "\r\n\x00"):
            raise ValueError()
        return mobile, password
    except (ValueError, AttributeError, TypeError, json.JSONDecodeError):
        raise TaskError(
            "账号配置无效：需要手机号|密码或含 mobile、password 的 JSON 对象"
        ) from None


def account_lines():
    """优先读取规范变量，并兼容上游框架曾匹配的旧变量名。"""
    for name in ("EVERPHOTO_ACCOUNT", "EVERPHOTO", "时光"):
        value = os.environ.get(name, "")
        if value.strip():
            return [line for line in value.splitlines() if line.strip()], name
    return [], "EVERPHOTO_ACCOUNT"


def account_identity(profile, secrets):
    """仅返回官方的非敏感公开身份字段，不回退到手机号等凭据字段。"""
    for field in ("nickname", "username", "display_name", "uid"):
        value = profile.get(field)
        if isinstance(value, (str, int)) and str(value):
            value = str(value)
            if len(value) > 256 or not value.isprintable():
                continue
            if any(secret and secret in value for secret in secrets):
                continue
            return value
    return None


def notification_selected():
    """实现全局开关及按目录编号、路径、文件名/通配符选择。"""
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in DISABLED:
        return False, "全局开关已关闭"
    if switch not in ENABLED and switch != "auto":
        return False, "全局开关值无效"

    raw_selectors = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if raw_selectors is None:
        return True, ""
    selectors = [item for item in re.split(r"[,;\s]+", raw_selectors.strip()) if item]
    if not selectors:
        return False, "脚本选择列表为空"
    names = {
        CATALOG_ID,
        RELEASE_PATH,
        pathlib.PurePosixPath(RELEASE_PATH).name,
        pathlib.Path(__file__).name,
    }
    for selector in selectors:
        if selector == "*" or any(fnmatch.fnmatchcase(name, selector) for name in names):
            return True, ""
    return False, "当前脚本未被选择"


def notification_body(summary):
    return (
        f"账号总数 {summary['accounts']}，成功 {summary['succeeded']}，"
        f"失败 {summary['failed']}；状态 {summary['status']}；"
        f"任务成功 {summary['tasks']['success']}，"
        f"已完成 {summary['tasks']['alreadyComplete']}，"
        f"跳过 {summary['tasks']['skipped']}，失败 {summary['tasks']['failed']}"
    )


def python_notify_candidates():
    """返回模块发现标记及显式 notify.py 路径，路径均由青龙约定提供。"""
    candidates = []
    try:
        if importlib.util.find_spec("notify") is not None:
            candidates.append("module:notify")
    except (ImportError, AttributeError, ValueError):
        pass
    folders = [
        os.environ.get("QINGLONG_NOTIFY_DIR"),
        "/ql/data/scripts",
        "/ql/scripts",
    ]
    for folder in folders:
        if folder:
            path = pathlib.Path(folder) / "notify.py"
            if path.is_file():
                candidates.append(str(path))
    return list(dict.fromkeys(candidates))


def javascript_notify_candidates():
    folders = [
        os.environ.get("QINGLONG_NOTIFY_DIR"),
        "/ql/data/scripts",
        "/ql/scripts",
    ]
    candidates = []
    for folder in folders:
        if folder:
            path = pathlib.Path(folder) / "sendNotify.js"
            if path.is_file():
                candidates.append(str(path))
    return list(dict.fromkeys(candidates))


def send_notification(summary, dry_run):
    """发送脱敏摘要；失败不覆盖业务退出码。"""
    selected, reason = notification_selected()
    if not selected:
        return "已关闭" if reason == "全局开关已关闭" else f"已跳过（{reason}）"
    if dry_run:
        # 预演必须保证完全断网；真实通知器通常会访问外部推送服务。
        log("通知：断网预演已生成脱敏摘要，未加载或调用通知器")
        return "断网预演（摘要已生成）"

    body = notification_body(summary)
    python_code = r'''import importlib.util, pathlib, sys
try:
    target = sys.argv[1]
    if target == "module:notify":
        from notify import send
    else:
        path = pathlib.Path(target)
        spec = importlib.util.spec_from_file_location("qinglong_notify", path)
        if spec is None or spec.loader is None:
            raise RuntimeError()
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        send = module.send
    send(sys.argv[2], sys.argv[3])
except BaseException:
    sys.exit(2)
'''
    for target in python_notify_candidates():
        try:
            result = subprocess.run(
                [sys.executable, "-c", python_code, target, TITLE, body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                return "已调用 notify.py"
        except (OSError, subprocess.TimeoutExpired):
            continue

    node = shutil.which("node")
    javascript_code = r'''try {
  const loaded = require(process.argv[1]);
  const send = typeof loaded === "function" ? loaded : loaded.sendNotify;
  if (typeof send !== "function") process.exit(2);
  Promise.resolve(send(process.argv[2], process.argv[3]))
    .then(() => process.exit(0)).catch(() => process.exit(2));
} catch (_) { process.exit(2); }
'''
    if node:
        for target in javascript_notify_candidates():
            try:
                result = subprocess.run(
                    [node, "-e", javascript_code, target, TITLE, body],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    return "已调用 sendNotify.js"
            except (OSError, subprocess.TimeoutExpired):
                continue
    return "不可用或发送失败（保留业务退出码）"


def main():
    started = time.monotonic()
    start_time = stamp()
    dry_run = os.environ.get("EVERPHOTO_DRY_RUN", "0").strip().lower() in DRY_ENABLED
    lines, account_source = account_lines()
    log(f"========== {TITLE} ==========")
    log(
        f"开始时间：{start_time}；模式：{'断网预演' if dry_run else '正式执行'}；"
        f"账号数：{len(lines)}"
    )
    if account_source != "EVERPHOTO_ACCOUNT" and lines:
        log(f"⚠️ 正在使用兼容变量 {account_source}，建议迁移到 EVERPHOTO_ACCOUNT")

    totals = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    succeeded = 0
    failed = 0
    if not lines:
        log("❌ 配置错误：未设置必填 EVERPHOTO_ACCOUNT")

    for index, line in enumerate(lines, 1):
        account_started = time.monotonic()
        counts = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        stage = 1
        stage_started = time.monotonic()
        log(f"账号 {index} / 阶段 1：配置校验与登录")
        try:
            mobile, password = parse_account(line)
            if dry_run:
                log(
                    f"账号 {index} / 阶段 1：✅ 配置有效，登录请求未发送；"
                    f"耗时 {time.monotonic() - stage_started:.2f} 秒"
                )
                counts["skipped"] += 1
                stage = 2
                log(f"账号 {index} / 阶段 2：⏭️ 签到请求未发送；耗时 0.00 秒")
                counts["skipped"] += 1
            else:
                data = post(
                    "https://web.everphoto.cn/api/auth",
                    {"mobile": mobile, "password": password},
                )
                token = data.get("token")
                if not isinstance(token, str) or not token or any(
                    char in token for char in "\r\n"
                ):
                    raise TaskError("登录未返回有效凭据")
                profile = data.get("user_profile")
                identity = (
                    account_identity(profile, (mobile, password, token))
                    if isinstance(profile, dict)
                    else None
                )
                if identity is not None:
                    log(f"账号 {index} 身份：{identity}")
                counts["success"] += 1
                log(
                    f"账号 {index} / 阶段 1：✅ 登录成功；"
                    f"耗时 {time.monotonic() - stage_started:.2f} 秒"
                )

                stage = 2
                stage_started = time.monotonic()
                log(f"账号 {index} / 阶段 2：每日签到")
                data = post(
                    "https://api.everphoto.cn/users/self/checkin/v2", token=token
                )
                result = data.get("checkin_result")
                if result is not True and not (type(result) is int and result == 1):
                    raise TaskError("签到未确认成功（可能已签到，不能认定成功）")
                counts["success"] += 1
                log(
                    f"账号 {index} / 阶段 2：✅ 签到成功；"
                    f"耗时 {time.monotonic() - stage_started:.2f} 秒"
                )
            succeeded += 1
        except Exception as error:
            counts["failed"] += 1
            if stage == 1:
                counts["skipped"] += 1
            failed += 1
            message = (
                str(error)
                if isinstance(error, TaskError)
                else "内部处理失败，详情已抑制"
            )
            log(
                f"账号 {index} / 阶段 {stage}：❌ {message}；"
                f"耗时 {time.monotonic() - stage_started:.2f} 秒"
            )
            if stage == 1:
                log(f"账号 {index} / 阶段 2：⏭️ 登录失败，签到跳过；耗时 0.00 秒")

        for key in totals:
            totals[key] += counts[key]
        log(
            f"账号 {index} 统计：总任务 2，成功 {counts['success']}，"
            f"已完成 {counts['alreadyComplete']}，跳过 {counts['skipped']}，"
            f"失败 {counts['failed']}；耗时 {time.monotonic() - account_started:.2f} 秒"
        )

    status = (
        "configuration-error"
        if not lines
        else "partial-failure"
        if failed and succeeded
        else "failure"
        if failed
        else "dry-run"
        if dry_run
        else "success"
    )
    summary = {
        "status": status,
        "mode": "dry-run" if dry_run else "live",
        "accounts": len(lines),
        "succeeded": succeeded,
        "failed": failed,
        "configurationErrors": 0 if lines else 1,
        "tasks": totals,
        "startTime": start_time,
    }
    summary["notification"] = send_notification(summary, dry_run)
    summary["finishTime"] = stamp()
    summary["durationSeconds"] = round(time.monotonic() - started, 2)

    log("----------------------------------------")
    log(
        f"任务统计：账号总数 {len(lines)}，成功 {succeeded}，失败 {failed}；"
        f"配置错误 {summary['configurationErrors']}"
    )
    log(
        f"子任务统计：总数 {sum(totals.values())}，成功 {totals['success']}，"
        f"已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，"
        f"失败 {totals['failed']}"
    )
    log(
        f"通知状态：{summary['notification']}；"
        f"总耗时 {summary['durationSeconds']:.2f} 秒"
    )
    log(f"完成时间：{summary['finishTime']}；最终状态：{status}")
    print(
        "TASK_SUMMARY="
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return 1 if failed or not lines else 0


if __name__ == "__main__":
    sys.exit(main())
