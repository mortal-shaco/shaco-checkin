#!/usr/bin/env python3
# name: WorkBuddy 每日积分签到
# cron: 38 9 * * *
# SPDX-License-Identifier: MIT
# 来源：Keefe-Hu/WB-daily-checkin，scripts/wb_daily_checkin.py
# 上游原始说明：自动领取每日积分，并汇总本次 / 累计 / 余额。
"""独立标准库任务。优先设置 WB_DAILY_CHECKIN_TOKEN，每行一个账号。
每行可为原始 token、uid+token，或 JSON 对象：
{"token":"占位令牌","uid":"公开用户标识","org":"组织标识","domain":"租户域"}。
配套身份字段请从本人客户端登录信息的 account/auth 字段获取，禁止分享凭据。
--token 保持兼容；未设置凭据时兼容读取本人 WorkBuddy 登录文件。
WB_DAILY_CHECKIN_DRY_RUN=1 完全断网；QINGLONG_NOTIFY 控制青龙通知。

MIT License
Copyright (c) Keefe-Hu
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
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
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
        _ql_notify_identities = ('437220302cb75855', 'scripts/wb_daily_checkin.py', 'wb_daily_checkin.py', 'wb_daily_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import fnmatch
import json
import math
import os
import re
import stat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

HOST = "https://www.codebuddy.cn"
SIGN_URL = HOST + "/v2/billing/meter/daily-checkin"
STATUS_URLS = (HOST + "/v2/billing/meter/checkin-activity-status",
               HOST + "/v2/billing/meter/checkin-status")
BALANCE_URL = HOST + "/v2/billing/meter/get-user-resource"
TITLE = "WorkBuddy 每日积分签到"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
SECRETS = []
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None
_NO_REDIRECT = NoRedirect()

# 按当前系统找本地登录凭据文件，返回多个候选路径
def _login_path(home=None, platform=sys.platform):
    home = Path.home() if home is None else Path(home)
    if platform == "darwin":
        bases = [home / "Library/Application Support"]
    elif platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        roaming = os.environ.get("APPDATA")
        bases = [Path(p) for p in (local, roaming) if p]
        bases += [home / "AppData" / "Local", home / "AppData" / "Roaming"]
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        bases = [Path(xdg)] if xdg else [home / ".local" / "share"]
    return [b / "CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info" for b in bases]


# 读取并校验凭据文件内容
def _read_token(path):
    # 拒绝符号链接，防止指向伪造文件
    if path.is_symlink():
        raise ValueError("登录文件不能是符号链接")
    try:
        info = path.stat()
    except FileNotFoundError:
        raise ValueError(f"未找到登录文件：{path}")
    # 必须是存在的普通文件
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("登录路径不是普通文件")
    # 仅允许属主本人持有（类 Unix 系统）
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise ValueError("登录文件属于其他用户")
    # 其他用户不可写（类 Unix 系统）
    if os.name != "nt" and info.st_mode & 0o022:
        raise ValueError("登录文件权限过于开放")
    # 解析 JSON，要求包含 auth 字段
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("登录文件不是有效 JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("auth"), dict):
        raise ValueError("登录文件缺少 auth 字段")
    return data


# 整理出本次请求需要的身份字段
def _credentials(token=None):
    # 直接传入令牌时跳过本地文件读取，便于未安装客户端的用户使用
    if token:
        return {"token": token.strip(), "uid": "", "org": "", "domain": ""}
    data = None
    for path in _login_path():
        if path.is_symlink():
            continue
        # 已退出登录的标记文件存在时直接提示
        if Path(f"{path}.logged-out").exists():
            raise ValueError("已退出登录，请先在客户端登录")
        if not path.exists():
            continue
        try:
            data = _read_token(path)
        except ValueError:
            continue
        break
    if data is None:
        tried = " | ".join(str(p) for p in _login_path())
        raise ValueError(f"未找到登录文件，已尝试：{tried}")
    auth = data.get("auth") if isinstance(data.get("auth"), dict) else {}
    # 兼容 token 内携带 uid 的写法（uid+token）
    raw = (auth.get("accessToken") or auth.get("access_token") or "").strip()
    if "+" in raw:
        uid_part, raw = (p.strip() for p in raw.split("+", 1))
    else:
        uid_part = ""
    if not raw:
        raise ValueError("登录文件缺少 access token")
    account = data.get("account") if isinstance(data.get("account"), dict) else {}
    return {
        "token": raw,
        "uid": str(account.get("uid") or account.get("id") or uid_part).strip(),
        "org": str(account.get("enterpriseId") or account.get("enterprise_id") or "").strip(),
        "domain": str(auth.get("domain") or data.get("domain") or "").strip(),
    }


# 组装请求头，按需带上组织 / 租户信息
def _headers(cred):
    head = {
        "Authorization": f"Bearer {cred['token']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    for key, names in (
        ("uid", ("X-User-Id",)),
        ("org", ("X-Enterprise-Id", "X-Tenant-Id")),
        ("domain", ("X-Domain",)),
    ):
        if cred[key]:
            for name in names:
                head[name] = cred[key]
    return head


def log(text):
    print(f"[{datetime.now():%H:%M:%S}] {text}", flush=True)


def safe_text(value):
    text = re.sub(r"\s+", " ", str(value)).strip()
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?i)(?:bearer\s+\S+|(?:token|cookie|session|authorization|device[_-]?id)\s*[:=]\s*\S+)",
                  "[已隐藏]", text)
    return re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)


def credentials(line):
    if line.lstrip().startswith("{"):
        try:
            value = json.loads(line)
        except ValueError:
            raise ValueError("账号 JSON 格式错误") from None
        if not isinstance(value, dict):
            raise ValueError("账号必须为 JSON 对象")
        cred = {key: value.get(key, "") for key in ("token", "uid", "org", "domain")}
        if not all(isinstance(v, str) for v in cred.values()):
            raise ValueError("账号字段必须是字符串")
        cred = {key: v.strip() for key, v in cred.items()}
    else:
        cred = {"token": line.strip(), "uid": "", "org": "", "domain": ""}
        if "+" in cred["token"]:
            cred["uid"], cred["token"] = (v.strip() for v in cred["token"].split("+", 1))
    if not cred["token"] or any(any(ord(c) < 32 or ord(c) == 127 for c in v) for v in cred.values()):
        raise ValueError("令牌为空或账号字段含控制字符")
    SECRETS.extend(cred[k] for k in ("token", "org", "domain") if cred[k])
    return cred


def post(url, headers, readonly=False):
    if os.getenv("WB_DAILY_CHECKIN_DRY_RUN", "").lower() in TRUE:
        raise ValueError("断网预演禁止 HTTP 请求")
    for attempt in range(3 if readonly else 1):
        try:
            request = Request(url, data=b"{}", headers=headers, method="POST")
            with build_opener(_NO_REDIRECT).open(request, timeout=30) as response:
                raw = response.read(1048577)
            if len(raw) > 1048576:
                raise ValueError("响应超过大小限制")
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("响应必须是 JSON 对象")
            return body
        except HTTPError as exc:
            raise ValueError(f"HTTP {exc.code}，未输出响应正文") from None
        except (URLError, TimeoutError, OSError):
            if readonly and attempt < 2:
                time.sleep(1 + attempt)
                continue
            raise ValueError("网络连接失败或超时；写请求结果不确定时请稍后查询状态") from None
        except (UnicodeError, json.JSONDecodeError):
            raise ValueError("响应不是有效 JSON") from None


def code_ok(body):
    return type(body.get("code")) is int and body["code"] == 0


def checked(data):
    value = data.get("today_checked_in", data.get("todayCheckedIn"))
    if value is True or type(value) is int and value == 1 or isinstance(value, str) and value.strip().lower() in {"true", "1"}:
        return True
    if value is False or type(value) is int and value == 0 or isinstance(value, str) and value.strip().lower() in {"false", "0"}:
        return False
    return None


def identity(payload):
    if not isinstance(payload, dict):
        return
    for key in ("nickname", "username", "displayName", "display_name", "uid"):
        value = payload.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
            log(f"账号身份 {key}：{safe_text(value)}")
    for key in ("user", "account", "userInfo", "Response", "Data"):
        if isinstance(payload.get(key), dict):
            identity(payload[key])


def probe(headers):
    for index, url in enumerate(STATUS_URLS, 1):
        try:
            body = post(url, headers, readonly=True)
            data = body.get("data")
            if code_ok(body) and isinstance(data, dict) and checked(data) is not None:
                identity(data)
                log(f"状态接口 {index}：查询成功")
                return data
            log(f"状态接口 {index}：业务码或签到状态字段无效，继续兜底")
        except ValueError as exc:
            log(f"状态接口 {index}：{exc}，继续兜底")
    return None


def number(*values):
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            return value
        if isinstance(value, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", value):
            return value
    return "-"


def selected_notification():
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    selectors = re.split(r"[,;\s]+", os.getenv("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    names = ("437220302cb75855", "scripts/wb_daily_checkin.py", "wb_daily_checkin.py",
             Path(__file__).name, "scripts/" + Path(__file__).name)
    return any(pattern and fnmatch.fnmatchcase(name, pattern) for pattern in selectors for name in names)


def notify(summary, dry):
    if dry:
        log("通知：断网预演，仅展示脱敏总结，不调用推送模块")
        return "dry-run"
    if not selected_notification():
        log("通知：未启用（默认仅推送显式选中的脚本）")
        return "disabled"
    body = (f"账号总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}；"
            f"状态 {summary['status']}")
    # 隔离通知模块异常、输出与超时，保留业务退出码。
    runner = '''import importlib.util,sys
path,title,body=sys.argv[1:]
if path:
    spec=importlib.util.spec_from_file_location("ql_notify",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(title,body)
'''
    paths = [None]
    root = os.getenv("QINGLONG_NOTIFY_DIR")
    roots = ([Path(root)] if root else []) + [Path("/ql/data/scripts"), Path("/ql/scripts")]
    paths += [p / "notify.py" for p in roots if (p / "notify.py").is_file()]
    for path in paths:
        try:
            result = subprocess.run([sys.executable, "-c", runner, str(path) if path else "", TITLE, body],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
            if result.returncode == 0:
                log("通知：发送完成")
                return "sent"
        except (OSError, subprocess.TimeoutExpired):
            pass
    for root in roots:
        path = root / "sendNotify.js"
        if not path.is_file():
            continue
        try:
            runner_js = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
            result = subprocess.run(["node", "-e", runner_js, str(path), TITLE, body],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
            if result.returncode == 0:
                log("通知：发送完成")
                return "sent"
        except (OSError, subprocess.TimeoutExpired):
            pass
    log("通知：模块不可用或发送失败，保留业务退出码")
    return "unavailable"


def account_run(cred, index, dry):
    started = time.monotonic()
    counts = dict(total=4, success=0, already=0, skipped=0, failed=0)
    result = {}
    status = None
    sign_data = {}
    activity = {}
    balance = None
    failed = False
    headers = _headers(cred)
    for stage, name in enumerate(("查询签到状态（双接口兜底）", "领取每日积分", "刷新活动及积分", "查询账户余额"), 1):
        tick = time.monotonic()
        log(f"账号 {index} 阶段 {stage}/4：{name}")
        outcome = "success"
        try:
            if dry:
                outcome = "skipped"
                log("⏭️ 断网预演：检查参数和执行计划，不发起 HTTP，不领取积分")
            elif stage == 1:
                status = probe(headers)
                if status is None:
                    outcome = "skipped"
                    log("⚠️ 状态不可用，尝试一次签到并严格核验返回")
            elif stage == 2:
                if status is not None and checked(status) is True:
                    sign_data = status
                    activity = status
                    outcome = "already"
                    log("☑️ 今天已签到过（官方状态已核验）")
                else:
                    body = post(SIGN_URL, headers)
                    data = body.get("data")
                    if not code_ok(body) or not isinstance(data, dict):
                        raise ValueError("签到业务码非零或缺少 data")
                    identity(data)
                    explicit = data.get("success")
                    if explicit is False or explicit is not None and explicit is not True:
                        raise ValueError("签到未返回明确成功状态")
                    if explicit is not True:
                        verification = probe(headers)
                        if verification is None or checked(verification) is not True:
                            raise ValueError("签到缺少 success=true 且无法确认今日已签到")
                        activity = verification
                    sign_data = data
                    log("✅ 签到完成（业务成功已核验）")
            elif stage == 3:
                if not activity:
                    activity = probe(headers) or {}
                if not activity:
                    outcome = "skipped"
                    log("⚠️ 活动信息暂不可用")
                else:
                    log("✅ 活动与积分字段已读取")
            else:
                body = post(BALANCE_URL, headers, readonly=True)
                data = body.get("data")
                if not code_ok(body) or not isinstance(data, dict):
                    raise ValueError("余额业务码非零或缺少 data")
                response = data.get("Response")
                if not isinstance(response, dict) or response.get("Error"):
                    raise ValueError("余额响应结构异常或包含错误")
                detail = response.get("Data")
                if not isinstance(detail, dict):
                    raise ValueError("余额响应缺少 Data")
                identity(data)
                balance = number(detail.get("TotalDosage"))
                if balance == "-":
                    raise ValueError("余额缺少有效数值")
                log(f"✅ 当前余额：{balance} 积分")
        except (ValueError, OSError, TypeError):
            if stage == 2:
                outcome = "failed"
                failed = True
                log("❌ 签到失败或结果无法核验；未输出服务端消息与凭据")
            else:
                outcome = "skipped"
                log("⚠️ 辅助查询失败，结果标为不可用")
        counts[outcome] += 1
        log(f"阶段 {stage} 结果：{outcome}，耗时 {time.monotonic()-tick:.2f} 秒")
    today = number(activity.get("today_credit"), activity.get("todayCredit"), activity.get("daily_credit"),
                   sign_data.get("credit"), sign_data.get("today_credit"))
    total = number(activity.get("total_credits"), activity.get("totalCredits"))
    streak = number(sign_data.get("streak_days"), sign_data.get("streakDays"), activity.get("streak_days"), activity.get("streakDays"))
    act = safe_text(activity.get("activity_name") or "-")
    result = dict(status="dry-run" if dry else "failed" if failed else "already" if counts['already'] else "success",
                  success=not failed and not dry, today_credit=today, total_credits=total, balance=number(balance),
                  streak_days=streak, activity_name=act)
    log(f"本次获得：{today} 积分；累计获得：{total} 积分；连续天数：{streak} 天；当前活动：{act}")
    print("---")
    print(json.dumps(result, ensure_ascii=False))
    log(f"账号 {index} 统计：总任务 4，成功 {counts['success']}，已完成 {counts['already']}，"
        f"跳过 {counts['skipped']}，失败 {counts['failed']}，耗时 {time.monotonic()-started:.2f} 秒")
    return not failed, counts


def run():
    started = time.monotonic()
    dry = os.getenv("WB_DAILY_CHECKIN_DRY_RUN", "").strip().lower() in TRUE
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry else '正式运行'}")
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--token", help="兼容令牌输入；多账号推荐环境变量每行一个账号")
    # 让命令行错误进入统一统计和通知流程。
    parser.exit = lambda status=0, message=None: (_ for _ in ()).throw(ValueError("命令行参数错误"))
    parser.error = lambda message: (_ for _ in ()).throw(ValueError("命令行参数错误"))
    rows = []
    config_error = False
    try:
        args = parser.parse_args()
        raw = args.token or os.getenv("WB_DAILY_CHECKIN_TOKEN", "")
        rows = [line.strip() for line in raw.splitlines() if line.strip()]
        if not rows and not dry:
            try:
                local = _credentials()
                rows = [json.dumps(local)]
            except (ValueError, OSError):
                raise ValueError("请设置 WB_DAILY_CHECKIN_TOKEN；本机兼容登录文件不可用") from None
        if not rows:
            raise ValueError("请设置 WB_DAILY_CHECKIN_TOKEN，每行一个账号")
    except (ValueError, OSError):
        log("❌ 配置错误：检查令牌环境变量或命令行参数（不展示输入）")
        config_error = True
    log(f"账号数量：{len(rows)}")
    good = bad = 0
    totals = dict(total=0, success=0, already=0, skipped=0, failed=0)
    for index, line in enumerate(rows, 1):
        try:
            cred = credentials(line)
            ok, counts = account_run(cred, index, dry)
            good += int(ok)
            bad += int(not ok)
            for key in totals:
                totals[key] += counts[key]
        except Exception:
            bad += 1
            totals['total'] += 1
            totals['failed'] += 1
            log(f"❌ 账号 {index} 失败：配置无效或执行异常，详细输入已隐藏")
            log(f"账号 {index} 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1")
    code = 1 if config_error or bad else 0
    state = "configuration-error" if config_error else "partial-failure" if bad and good else "failure" if bad else "dry-run" if dry else "success"
    summary = dict(status=state, accounts=len(rows), success=good, failed=bad,
                   subtasks=totals, mode="dry-run" if dry else "live", exitCode=code)
    log("----------------------------------------")
    log(f"任务统计：账号 {len(rows)}，成功 {good}，失败 {bad}；子任务 {json.dumps(totals, ensure_ascii=False)}")
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic()-started, 2)
    log(f"完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {summary['elapsedSeconds']} 秒；最终状态：{state}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(run())
