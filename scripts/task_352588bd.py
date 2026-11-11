#!/usr/bin/env python3
# name: 夸克网盘签到
# cron: 58 10 * * *
"""夸克网盘签到、容量查询与可选抽奖余额查询。

来源 PLA888/kuake_qiandao main.py，提交 fdbaf547f0ca14f375759225122bace857b1eb6c。
原始源码未附版权声明，沿用任务指定的 MIT 许可。

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

QUARK_ACCOUNTS 每个非空行一个账号，格式为 kps|sign|vcode，仅拆分前两个 |。
登录本人夸克手机客户端，通过本人授权的 HTTPS 抓包查看
drive-m.quark.cn/1/clouddrive/capacity/growth/info 或 /sign 请求的
kps、sign、vcode 查询参数，URL 解码一次后填入同一行。凭据需来自同一账号，
失效后重新获取。保留单账号 QUARK_KPS、QUARK_SIGN、QUARK_VCODE 兼容输入。
QUARK_QUERY_BALANCE=1 额外查询抽奖余额。QUARK_DRY_RUN=1 完全断网预演。
SMTP_SERVER、SMTP_PORT（默认587）、EMAIL、PASSWORD 完整配置时启用邮箱通知，
465 使用隐式 TLS，其余端口必须支持 STARTTLS。
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
        _ql_notify_identities = ('352588bd2bb301df', 'scripts/task_352588bd.py', 'task_352588bd.py', 'task_352588bd')
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
import smtplib
import ssl
import subprocess
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


TITLE = "夸克网盘签到"
CATALOG_ID = "352588bd2bb301df"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
TIMEOUT = 20
LIMIT = 262144
SECRETS = []


class TaskError(Exception):
    pass


def redact(value):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return " ".join(text.split())


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {redact(message)}", flush=True)


def switch(name, default=False):
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    if raw in TRUE:
        return True
    if raw in FALSE:
        return False
    raise TaskError(f"{name} 需填写 1 或 0")


def accounts_from_env():
    if "QUARK_ACCOUNTS" in os.environ:
        lines = [line.strip() for line in os.environ["QUARK_ACCOUNTS"].splitlines() if line.strip()]
        if not lines:
            raise TaskError("QUARK_ACCOUNTS 未配置有效账号")
        accounts = []
        for line in lines:
            fields = line.split("|", 2)
            SECRETS.extend(fields)
            accounts.append(fields)
        return accounts
    fields = [os.getenv(name, "").strip() for name in ("QUARK_KPS", "QUARK_SIGN", "QUARK_VCODE")]
    SECRETS.extend(fields)
    if not any(fields):
        raise TaskError("请配置 QUARK_ACCOUNTS，或完整配置兼容的三个凭据变量")
    return [fields]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(host, endpoint, params, payload=None):
    url = f"https://{host}{endpoint}?{urlencode(params)}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Accept": "application/json", "Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                raise TaskError("HTTP 状态异常")
            raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise TaskError("响应超过大小限制")
        content = json.loads(raw)
    except HTTPError as error:
        raise TaskError(f"HTTP 请求失败，状态码 {error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise TaskError("网络请求失败或超时") from None
    except (ValueError, UnicodeError):
        raise TaskError("响应不是有效 JSON") from None
    if not isinstance(content, dict) or type(content.get("code")) is not int or content["code"] != 0:
        raise TaskError("业务状态未确认成功，请检查凭据或接口状态")
    data = content.get("data")
    if not isinstance(data, dict):
        raise TaskError("业务数据格式异常")
    return data


def number(data, field):
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise TaskError(f"业务字段 {field} 缺失或无效")
    return value


def human_unit(value):
    units = ("MB", "GB", "TB", "PB", "EB")
    value /= 1024 ** 2
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    return f"{value:.2f} {units[index]}"


def print_identity(data):
    # 仅接受公开身份字段，不回显完整响应及设备、会话字段。
    for key in ("nickname", "username", "display_name", "uid"):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
            log(f"账号身份 {key} = {value}")


def checkin(params):
    data = request_json("drive-m.quark.cn", "/1/clouddrive/capacity/growth/sign", params, {"sign_cyclic": True})
    reward = number(data, "sign_daily_reward")
    print_identity(data)
    return f"签到成功，获得容量 {human_unit(reward)}"


def user_info(params):
    data = request_json("drive-m.quark.cn", "/1/clouddrive/capacity/growth/info", params)
    cap = data.get("cap_sign")
    if not isinstance(cap, dict) or cap.get("sign_daily") is not True:
        raise TaskError("容量接口未确认今日已签到")
    total = number(data, "total_capacity")
    used = number(data, "use_capacity")
    expires = number(data, "super_vip_exp_at")
    reward = number(cap, "sign_daily_reward")
    progress = number(cap, "sign_progress")
    member = data.get("member_type")
    if not isinstance(member, (str, int)) or isinstance(member, bool):
        raise TaskError("会员类型字段缺失或无效")
    try:
        expiry = datetime.fromtimestamp(expires / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OverflowError, OSError):
        raise TaskError("会员过期时间无效") from None
    print_identity(data)
    ratio = f"{used / total * 100:.2f}%" if total else "总容量为零"
    return (f"今日已签到，获得容量 {human_unit(reward)}，签到进度 {progress}；"
            f"会员类型 {member}，过期时间 {expiry}，总计容量 {human_unit(total)}，"
            f"使用容量 {human_unit(used)}，使用百分比 {ratio}")


def query_balance(params):
    data = request_json("coral2.quark.cn", "/currency/v1/queryBalance", {
        "moduleCode": "1f3563d38896438db994f118d4ff53cb", "kps": params["kps"]})
    print_identity(data)
    values = []
    for key in ("balance", "currencyBalance", "availableBalance", "totalBalance"):
        if key in data:
            values.append(f"{key}={number(data, key)}")
    if not values:
        raise TaskError("余额字段未识别，需根据脱敏接口证据适配")
    return "抽奖余额查询成功，" + "，".join(values)


def notify_selected():
    mode = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if mode in FALSE:
        return False
    if mode in TRUE:
        return True
    if mode != "auto":
        return False
    selectors = re.split(r"[,;\s]+", os.getenv("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    script = Path(__file__).resolve()
    names = {CATALOG_ID, script.name, script.as_posix()}
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            names.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in selectors if pattern for name in names)


def qinglong_notify(body):
    paths = []
    override = os.getenv("QINGLONG_NOTIFY_DIR")
    if override:
        paths.append(Path(override))
    paths.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    python_files = []
    try:
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin:
            python_files.append(Path(spec.origin))
    except (ImportError, ValueError):
        pass
    python_files.extend(root / "notify.py" for root in paths)
    runner = ("import importlib.util,sys; "
              "s=importlib.util.spec_from_file_location('notify',sys.argv[1]); "
              "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
              "m.send(sys.argv[2],sys.argv[3])")
    for file in dict.fromkeys(python_files):
        if file.is_file():
            try:
                result = subprocess.run([sys.executable, "-c", runner, str(file), TITLE, body],
                                        capture_output=True, timeout=30, check=False)
                if result.returncode == 0:
                    return "已发送"
            except (OSError, subprocess.TimeoutExpired):
                pass
    js_runner = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
    for root in paths:
        file = root / "sendNotify.js"
        if file.is_file():
            try:
                result = subprocess.run(["node", "-e", js_runner, str(file), TITLE, body],
                                        capture_output=True, timeout=30, check=False)
                if result.returncode == 0:
                    return "已发送"
            except (OSError, subprocess.TimeoutExpired):
                pass
    return "通知模块不可用或发送失败"


def email_notify(body):
    names = ("SMTP_SERVER", "EMAIL", "PASSWORD")
    values = [os.getenv(name, "") for name in names]
    if not any(values):
        return "未配置"
    if not all(values):
        return "配置不完整"
    host, email, password = values
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        message = EmailMessage()
        message["From"] = message["To"] = email
        message["Subject"] = TITLE
        message.set_content(body)
        context = ssl.create_default_context()
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT, context=context)
        else:
            server = smtplib.SMTP(host, port, timeout=TIMEOUT)
        with server:
            if port != 465:
                server.starttls(context=context)
            server.login(email, password)
            server.send_message(message)
        return "已发送"
    except Exception:
        return "发送失败或配置无效"


def run():
    started = time.monotonic()
    start_time = datetime.now().isoformat(timespec="seconds")
    dry_run = os.getenv("QUARK_DRY_RUN", "").strip().lower() in TRUE
    mode = "离线预演" if dry_run else "正式运行"
    SECRETS.extend(os.getenv(name, "") for name in ("PASSWORD", "EMAIL"))
    log(f"========== {TITLE} ==========")
    log(f"开始时间 {start_time} | 运行模式 {mode}")
    results = []
    details = []
    configuration_error = False
    try:
        dry_run = switch("QUARK_DRY_RUN")
        extra = switch("QUARK_QUERY_BALANCE")
        accounts = accounts_from_env()
    except TaskError as error:
        accounts = []
        configuration_error = True
        log(f"❌ 配置错误 {error}")
    log(f"账号数量 {len(accounts)}")
    for index, fields in enumerate(accounts, 1):
        account_start = time.monotonic()
        stats = {"account": index, "total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        log(f"账号 {index} 开始")
        actions = [("签到", checkin), ("容量与会员信息核验", user_info)]
        if extra:
            actions.append(("抽奖余额查询", query_balance))
        stats["total"] = len(actions)
        if len(fields) != 3 or not all(field.strip() for field in fields):
            stats["failed"] = 1
            stats["skipped"] = len(actions) - 1
            configuration_error = True
            log(f"❌ 账号 {index} 凭据不完整，需填写 kps|sign|vcode")
        else:
            params = dict(zip(("kps", "sign", "vcode"), fields))
            params.update({"pr": "ucpro", "fr": "android"})
            for stage, (label, action) in enumerate(actions, 1):
                step_start = time.monotonic()
                log(f"账号 {index} 阶段 {stage}/{len(actions)} {label} 开始")
                try:
                    if dry_run:
                        stats["skipped"] += 1
                        log(f"⏭️ 账号 {index} {label} 预演完成，未发送请求")
                    else:
                        message = action(params)
                        stats["success"] += 1
                        log(f"✅ 账号 {index} {message}")
                        details.append(redact(f"账号 {index} {message}"))
                except TaskError as error:
                    stats["failed"] += 1
                    log(f"❌ 账号 {index} {label} 失败，{error}")
                except Exception:
                    stats["failed"] += 1
                    log(f"❌ 账号 {index} {label} 处理异常，已隐藏异常详情")
                log(f"账号 {index} 阶段 {stage} 耗时 {time.monotonic() - step_start:.2f} 秒")
        stats["elapsedSeconds"] = round(time.monotonic() - account_start, 3)
        results.append(stats)
        log(f"账号 {index} 统计 总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {stats['elapsedSeconds']} 秒")
    failed = sum(item["failed"] > 0 for item in results)
    successful = len(results) - failed
    exit_code = int(configuration_error or failed > 0)
    status = "configuration-error" if configuration_error else ("partial-failure" if failed and successful else "failure" if failed else "dry-run" if dry_run else "success")
    body = f"{TITLE}，状态 {status}，模式 {mode}，账号总数 {len(results)}，成功 {successful}，失败 {failed}。"
    body += "\n" + "\n".join(f"账号 {item['account']} 任务成功 {item['success']}，跳过 {item['skipped']}，失败 {item['failed']}" for item in results)
    body += "\n" + "\n".join(details)
    # 预演禁止加载通知模块和建立 SMTP 连接。
    if dry_run:
        notification = "离线预演，仅生成通知摘要"
        email = "离线预演"
    else:
        try:
            notification = qinglong_notify(redact(body)) if notify_selected() else "未启用或未选中"
        except Exception:
            notification = "通知不可用"
        email = "全局关闭" if os.getenv("QINGLONG_NOTIFY", "auto").strip().lower() in FALSE else email_notify(redact(body))
    elapsed = round(time.monotonic() - started, 3)
    finished = datetime.now().isoformat(timespec="seconds")
    log("----------------------------------------")
    log(f"任务统计 账号总数 {len(results)}，成功 {successful}，失败 {failed}")
    totals = {key: sum(item[key] for item in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log(f"子任务统计 总数 {totals['total']}，成功 {totals['success']}，已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，失败 {totals['failed']}")
    log(f"通知状态 {notification} | 邮箱通知 {email}")
    log(f"完成时间 {finished} | 总耗时 {elapsed} 秒 | 最终状态 {status}")
    summary = {"task": TITLE, "mode": "dry-run" if dry_run else "live", "status": status,
               "accounts": len(results), "successfulAccounts": successful, "failedAccounts": failed,
               "configurationError": configuration_error, "tasks": totals, "accountResults": results,
               "notification": notification, "emailNotification": email, "startTime": start_time,
               "finishTime": finished, "elapsedSeconds": elapsed, "exitCode": exit_code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
