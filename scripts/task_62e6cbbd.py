#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: OA实习签到
# cron: 34 8 * * *
# SPDX-License-Identifier: GPL-3.0-only
#
# 上游：JasonYANG170/OA-Sgin main.py（GPL-3.0）
# https://github.com/JasonYANG170/OA-Sgin
# 提交：066417ea3cdd01d25ce3b6882445457f50908e41
#
# 本程序是自由软件：你可以在遵循 GNU 通用公共许可证第 3 版或（按你的选择）
# 任何更新版本的条款下再分发和/或修改它。本程序的发布不附带任何担保。
# 完整许可证文本见上游仓库 LICENSE。
#
"""OA 实习签到（青龙维护版，仅标准库）。

面向 stu-oa.xxgcxy.cn 实习打卡接口。上游为交互式日期区间批量补签；本维护版
仅允许单日签到（默认当天），移除不安全的区间批量写入。

OA_SGIN_ACCOUNTS：每个非空行一个账号，格式 studentId#X-Access-Token；仅在第一个
井号处分割，后续 Token 原文保留。在微信小程序 / 学校 OA 抓包本人 internship
相关请求头中的 X-Access-Token，以及本人实习学生 ID。不要分享抓包或凭据。
OA_SGIN_LONGITUDE / OA_SGIN_LATITUDE / OA_SGIN_SIGNADDRESS：共享签到位置（经度、
纬度、地址文本），须为本人真实实习地点。
OA_SGIN_DATE：可选单日覆盖，格式 YYYY-MM-DD；未设置则使用当天本地日期。禁止
日期区间。
OA_SGIN_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
建议 Cron：每天 08:30。
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
        _ql_notify_identities = ('62e6cbbde90ebb5f', 'scripts/task_62e6cbbd.py', 'task_62e6cbbd.py', 'task_62e6cbbd')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

TITLE = "OA实习签到"
CATALOG_ID = "62e6cbbde90ebb5f"
SIGN_PATH = "/scloudoa/jobInternship/internshipSignIn/add"
DEFAULT_ORIGIN = "http://stu-oa.xxgcxy.cn"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 15; Pixel 9 Build/AP3A.241105.008; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 "
    "Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240801 MMWEBID/1136 "
    "MicroMessenger/8.0.51.2702(0x28003342) WeChat/arm64 Weixin NetType/WIFI "
    "Language/zh_CN ABI/arm64"
)
TIMEOUT = 20
MAX_BYTES = 65536
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def log(text):
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name, default=""):
    return os.environ.get(name, default).strip()


def truthy(name):
    return env(name, "0").lower() in TRUE_VALUES


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parse_accounts(raw):
    accounts = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "#" not in text:
            raise SafeError("账号行缺少分隔符；格式为 studentId#X-Access-Token")
        student_id, token = text.split("#", 1)
        student_id = student_id.strip()
        token = token.strip()
        if not student_id or not re.fullmatch(r"\d{1,18}", student_id):
            raise SafeError("学生 ID 须为不超过 18 位的数字")
        if not token or any(ord(ch) < 32 for ch in token):
            raise SafeError("X-Access-Token 为空或含控制字符")
        accounts.append({"student_id": student_id, "token": token})
    return accounts


def parse_location():
    lon_raw = env("OA_SGIN_LONGITUDE")
    lat_raw = env("OA_SGIN_LATITUDE")
    address = env("OA_SGIN_SIGNADDRESS")
    if not lon_raw or not lat_raw or not address:
        raise SafeError(
            "缺少签到位置：请配置 OA_SGIN_LONGITUDE、OA_SGIN_LATITUDE、OA_SGIN_SIGNADDRESS"
        )
    try:
        longitude = float(lon_raw)
        latitude = float(lat_raw)
    except ValueError as exc:
        raise SafeError("经度或纬度不是合法数字") from exc
    if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
        raise SafeError("经纬度超出合法范围")
    if len(address) > 200:
        raise SafeError("签到地址过长")
    return longitude, latitude, address


def resolve_sign_date():
    override = env("OA_SGIN_DATE")
    if not override:
        return datetime.date.today().isoformat()
    try:
        return datetime.datetime.strptime(override, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise SafeError("OA_SGIN_DATE 须为 YYYY-MM-DD 单日，不支持日期区间") from exc


def classify_business(payload):
    """根据 JeecgBoot 风格响应判定业务结果，不输出原始正文。"""
    if not isinstance(payload, dict):
        return "failure", "响应不是可解析的业务对象"
    success = payload.get("success")
    code = payload.get("code")
    message = payload.get("message")
    if not isinstance(message, str):
        message = payload.get("msg") if isinstance(payload.get("msg"), str) else ""
    normalized = " ".join(message.split())
    already_markers = ("已签", "已打卡", "重复", "已经签到", "今日已签")
    if any(marker in normalized for marker in already_markers):
        return "alreadyComplete", "今日已签到（业务提示）"
    code_ok = code in (0, 200, "0", "200")
    if success is True or (success is None and code_ok):
        return "success", "签到成功（业务字段已核实）"
    if success is False or (code is not None and not code_ok):
        return "failure", "签到业务失败"
    if code_ok:
        return "success", "签到成功（业务字段已核实）"
    return "failure", "响应缺少可核实的成功字段"


class Account:
    def __init__(self, number, student_id):
        self.number = number
        self.student_id = student_id
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"

    def stage(self, number, name, operation):
        started = time.monotonic()
        log("账号 {} · 阶段 {} {}：开始".format(self.number, number, name))
        state, detail = "failure", "操作未完成"
        try:
            state, detail, result = operation()
            return result
        except SafeError as error:
            detail = str(error)
            raise
        except Exception:
            detail = "内部处理失败，已抑制异常详情"
            raise SafeError(detail) from None
        finally:
            self.stats[state] += 1
            log(
                "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.number,
                    number,
                    name,
                    ICONS.get(state, ICONS["failure"]),
                    detail,
                    time.monotonic() - started,
                )
            )

    def skip(self, number, name, reason):
        self.stage(number, name, lambda: ("skipped", reason, None))

    def finish(self):
        log(
            "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.number,
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                time.monotonic() - self.started,
                self.status,
            )
        )


def post_sign(token, student_id, longitude, latitude, address, sign_date):
    url = DEFAULT_ORIGIN + SIGN_PATH
    payload = {
        "probationaryworkplacementstudentid": int(student_id),
        "longitude": float(longitude),
        "latitude": float(latitude),
        "date": sign_date,
        "signaddress": address,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/json",
        "X-Access-Token": token,
        "Origin": DEFAULT_ORIGIN,
        "X-Requested-With": "com.tencent.mm",
        "Referer": DEFAULT_ORIGIN + "/scloudapp/",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NoRedirect(),
    )
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            status = response.status
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        status = error.code
        try:
            raw = error.read(MAX_BYTES + 1)
        except Exception:
            raw = b""
        finally:
            error.close()
    except Exception as exc:
        raise SafeError("网络、超时或连接失败") from exc
    if len(raw) > MAX_BYTES:
        raise SafeError("响应超过大小限制")
    payload = None
    if raw:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            payload = None
    return status, payload


def run_account(account, token, location, sign_date, dry_run):
    longitude, latitude, address = location

    def parameter_check():
        return "success", "凭据与位置本地格式检查通过，内容不输出", None

    account.stage(1, "参数检查", parameter_check)

    def identity():
        # 上游无公开身份接口；使用学生 ID 作为可核对的非凭据公开标识。
        return "success", "公开账号身份：学生ID {}".format(account.student_id), None

    account.stage(2, "公开身份", identity)

    if dry_run:
        account.skip(3, "提交实习签到", "断网预演：不请求签到接口")
        account.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果；目标日期 {}".format(
                account.number, sign_date
            )
        )
        return

    def submit():
        status, payload = post_sign(
            token, account.student_id, longitude, latitude, address, sign_date
        )
        if status in (401, 403):
            raise SafeError("凭据无效或没有访问权限，请重新获取 X-Access-Token")
        if status != 200:
            raise SafeError("签到请求失败（HTTP {}）".format(status))
        state, detail = classify_business(payload)
        if state == "failure":
            raise SafeError(detail)
        return state, "{}；日期 {}".format(detail, sign_date), None

    account.stage(3, "提交实习签到", submit)
    account.status = (
        "alreadyComplete" if account.stats["alreadyComplete"] else "success"
    )


PY_NOTIFY_RUNNER = r'''
import importlib, importlib.util, json, os, socket, subprocess, sys
specification = json.loads(sys.stdin.read())
if specification["dry_run"]:
    def denied(*args, **kwargs):
        raise RuntimeError("dry-run forbids network and external processes")
    class OfflineSocket(socket.socket):
        connect = denied
        connect_ex = denied
        sendto = denied
        sendmsg = denied
    socket.socket = OfflineSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    subprocess.Popen = denied
    os.system = denied
    os.popen = denied
    for name in dir(os):
        if name.startswith(("exec", "spawn")) or name in ("fork", "forkpty", "posix_spawn", "posix_spawnp"):
            setattr(os, name, denied)
sys.path.insert(0, specification["directory"])
module = None
if specification["path"] is None:
    try:
        module = importlib.import_module("notify")
    except ModuleNotFoundError as error:
        sys.exit(3 if error.name == "notify" else 1)
else:
    spec = importlib.util.spec_from_file_location("qinglong_notify_adapter", specification["path"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
sender = getattr(module, "send", None)
if not callable(sender):
    sys.exit(3)
result = sender(specification["title"], specification["body"])
sys.exit(1 if result is False else 0)
'''

JS_NOTIFY_RUNNER = r'''
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
if (input.dry_run) {
  const denied = () => { throw new Error('dry-run forbids network and external processes'); };
  require('net').Socket.prototype.connect = denied;
  require('dgram').createSocket = denied;
  for (const name of ['http', 'https']) {
    require(name).request = denied;
    require(name).get = denied;
  }
  require('tls').connect = denied;
  require('http2').connect = denied;
  const dns = require('dns');
  for (const key of Object.keys(dns)) if (typeof dns[key] === 'function') dns[key] = denied;
  for (const key of Object.keys(dns.promises)) if (typeof dns.promises[key] === 'function') dns.promises[key] = denied;
  const cp = require('child_process');
  for (const key of ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']) cp[key] = denied;
  require('worker_threads').Worker = denied;
  globalThis.fetch = denied;
}
Promise.resolve().then(() => require(input.path).sendNotify(input.title, input.body))
  .then(result => process.exit(result === false ? 1 : 0))
  .catch(() => process.exit(1));
'''


def notification_enabled():
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", env("QINGLONG_NOTIFY_SCRIPTS"))
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "oa_sgin.py",
        "candidate.py",
        "scripts/oa_sgin.py",
    }
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
    enabled = any(
        selector
        and any(fnmatch.fnmatchcase(identity, selector) for identity in identities)
        for selector in selectors
    )
    return enabled, "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"


def notify(body, dry_run):
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": dry_run,
        "directory": str(Path(__file__).resolve().parent),
        "path": None,
    }
    paths = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser())
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    adapters = [("python", None)]
    adapters.extend(
        ("python", directory / "notify.py")
        for directory in paths
        if (directory / "notify.py").is_file()
    )
    node = shutil.which("node")
    if node:
        adapters.extend(
            ("javascript", directory / "sendNotify.js")
            for directory in paths
            if (directory / "sendNotify.js").is_file()
        )
    for kind, path in adapters:
        specification["path"] = str(path.resolve()) if path is not None else None
        command = (
            [sys.executable, "-c", PY_NOTIFY_RUNNER]
            if kind == "python"
            else [node, "-e", JS_NOTIFY_RUNNER]
        )
        try:
            result = subprocess.run(
                command,
                input=json.dumps(specification, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                log(
                    "通知：✅ 脱敏总结已交给青龙适配器"
                    + ("（断网保护启用）" if dry_run else "")
                )
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用、投递失败或被断网保护阻止；保留业务退出码")
    return "unavailable-or-failed"


def main():
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("OA_SGIN_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    raw_accounts = env("OA_SGIN_ACCOUNTS")
    accounts_data = []
    location = None
    sign_date = None
    config_error = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("OA_SGIN_DRY_RUN 配置无效，停止执行")
        if not raw_accounts:
            raise SafeError(
                "未配置 OA_SGIN_ACCOUNTS；请按每个非空行 studentId#X-Access-Token 填写"
            )
        accounts_data = parse_accounts(raw_accounts)
        if not accounts_data:
            raise SafeError("OA_SGIN_ACCOUNTS 没有有效账号行")
        location = parse_location()
        sign_date = resolve_sign_date()
        log(
            "运行模式：{}；账号数：{}；签到日期：{}；位置参数已配置".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                sign_date,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts = []
    if config_error is None:
        for number, item in enumerate(accounts_data, 1):
            account = Account(number, item["student_id"])
            accounts.append(account)
            try:
                run_account(account, item["token"], location, sign_date, dry_run)
            except SafeError:
                account.status = "failure"
            except Exception:
                account.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                account.finish()
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        state: sum(a.status == state for a in accounts)
        for state in ("success", "alreadyComplete", "failure", "dry-run")
    }
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    if config_error:
        status = "configuration-error"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
    elif failed:
        status = "failure"
    elif dry_run:
        status = "dry-run"
    else:
        status = "success"
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
    body = (
        "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
            status,
            account_total,
            succeeded,
            failed,
            counts["dry-run"],
            "是" if config_error else "否",
        )
    )
    log("阶段 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log("阶段 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started))
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total,
            succeeded,
            counts["alreadyComplete"],
            failed,
            counts["dry-run"],
        )
    )
    log(
        "子任务统计：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
            sum(tasks.values()),
            tasks["success"],
            tasks["alreadyComplete"],
            tasks["skipped"],
            tasks["failure"],
        )
    )
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态 {}".format(
            finished_at, elapsed, notification, status
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total,
                "success": succeeded,
                "alreadyComplete": counts["alreadyComplete"],
                "failure": failed,
                "dryRun": counts["dry-run"],
                "configurationError": bool(config_error),
                "tasks": tasks,
                "notification": notification,
                "startTime": started_at,
                "finishTime": finished_at,
                "durationSeconds": elapsed,
                "exitCode": exit_code,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
