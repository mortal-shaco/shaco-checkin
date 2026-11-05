#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 广州信息技术职校微信签到
# cron: 30 7 * * *
#
# 来源：RyrieNorth/AppAutoSignIn AutoSignIn-Base.py（MIT）
# https://github.com/RyrieNorth/AppAutoSignIn
# 提交：29ec0efbeda57629c5ee1a08eaa869b41046f5b6
# 同仓参考：AutoSignIn-Server-v2.py / AutoSignIn-Server.py / autoSignIn-v3.py
#
# MIT License
#
# Copyright (c) RyrieNorth / AppAutoSignIn contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""广州信息技术职业学校学生微信平台（gzsx.qidisoft.cn）每日签到。

功能清点（相对上游 AutoSignIn-Base.py 与同仓参考）：
- 主源仅为 ComApi/PostObject 空模板；参考脚本补齐 gzsxWebApi.DoSignin 载荷。
- 正式模式按账号提交每日签到；以响应 status=success 判定业务成功。
- 移除源码硬编码坐标、原始响应打印、无超时请求与 Server 酱推送。
- 登录取 Token（v3 CLI）不并入定时任务：微信 OAuth/验证码流程不适合青龙调度；
  请在微信端绑定后自行取得 apitoken 与 UserID。
- 多账号、GZSX_DRY_RUN 断网预演、超时、时间轴日志、青龙通知与 TASK_SUMMARY。

GZSX_ACCOUNTS：每个非空行一个账号，格式 apitoken|userid；仅在第一个竖线处分割。
兼容单账号别名：同时设置 GZSX_APITOKEN 与 GZSX_USERID（仅当 GZSX_ACCOUNTS 为空）。
可选定位：GZSX_LAT / GZSX_LNG / GZSX_ADDRESS / GZSX_DISTANCE / GZSX_ACCURACY；
默认留空，不伪造学校坐标。
GZSX_UA：可选 User-Agent；不填使用微信内置浏览器常见 UA。
GZSX_TIMEOUT：单次请求超时秒数，默认 20，范围 5..60。
GZSX_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：30 7 * * *。不打印 apitoken、原始响应或设备标识。
"""
from __future__ import annotations

# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "36caf0959fcbed55",
            "scripts/gzsx_wechat_signin.py",
            "gzsx_wechat_signin.py",
            "candidate.py",
            "AutoSignIn-Base.py",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "广州信息技术职校微信签到"
CATALOG_ID = "36caf0959fcbed55"
APPLICATION_KEY = "app"
SIGNIN_URL = "http://gzsx.qidisoft.cn/WXPlatGZSXStu/ComApi/PostObject"
API_NAME = "gzsxWebApi.DoSignin"
DEFAULT_TIMEOUT = 20
MAX_RESPONSE_BYTES = 65536
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 "
    "NetType/WIFI MicroMessenger/7.0.20.1781(0x6700143B) "
    "WindowsWechat(0x6307001d)"
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return time.strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(stamp(), message), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_flag(name: str, default: str = "0") -> bool:
    return env(name, default).lower() in TRUE_VALUES


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def resolve_timeout() -> float:
    raw = env("GZSX_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("GZSX_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("GZSX_TIMEOUT 须在 5 到 60 秒之间")
    return value


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 apitoken|userid")
    token, userid = text.split("|", 1)
    token = token.strip()
    userid = userid.strip()
    if not token or not userid:
        raise SafeError("apitoken 或 userid 为空")
    if any(ord(ch) < 32 for ch in token) or any(ord(ch) < 32 for ch in userid):
        raise SafeError("账号行含控制字符")
    return {"apitoken": token, "userid": userid}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("GZSX_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("GZSX_ACCOUNTS 没有有效账号行")
        return accounts
    token = env("GZSX_APITOKEN")
    userid = env("GZSX_USERID")
    if token or userid:
        if not token or not userid:
            raise SafeError(
                "兼容别名需同时提供 GZSX_APITOKEN 与 GZSX_USERID；"
                "推荐改用 GZSX_ACCOUNTS（apitoken|userid）"
            )
        return [{"apitoken": token, "userid": userid}]
    raise SafeError("未配置 GZSX_ACCOUNTS；请按每个非空行 apitoken|userid 填写")


def location_fields() -> Dict[str, str]:
    return {
        "lat": env("GZSX_LAT"),
        "lng": env("GZSX_LNG"),
        "distance": env("GZSX_DISTANCE"),
        "accuracy": env("GZSX_ACCURACY"),
        "address": env("GZSX_ADDRESS"),
    }


def build_payload(userid: str, location: Dict[str, str]) -> Dict[str, Any]:
    return {
        "apiName": API_NAME,
        "UserID": userid,
        "lat": location.get("lat", ""),
        "lng": location.get("lng", ""),
        "distance": location.get("distance", ""),
        "accuracy": location.get("accuracy", ""),
        "address": location.get("address", ""),
        "type": 1,
        "locationStatus": "1",
        "signinStatus": "1",
        "remark": "",
        "fileJson": "[]",
    }


def build_headers(apitoken: str) -> Dict[str, str]:
    return {
        "Host": "gzsx.qidisoft.cn",
        "Connection": "keep-alive",
        "apitoken": apitoken,
        "User-Agent": env("GZSX_UA") or DEFAULT_UA,
        "Content-Type": "application/json;charset=UTF-8",
        "Referer": "http://gzsx.qidisoft.cn/WXPlatGZSXStu/dist/index.html",
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json, text/plain, */*",
    }


def http_post_json(
    url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: float
) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise SafeError("响应过大，已中止读取")
            if response.getcode() != 200:
                raise SafeError("HTTP 状态码异常：{}".format(response.getcode()))
    except SafeError:
        raise
    except urllib.error.HTTPError as exc:
        raise SafeError("HTTP 错误：{}".format(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise SafeError("网络错误：{}".format(compact(getattr(exc, "reason", exc)))) from exc
    except Exception as exc:
        raise SafeError("请求失败：{}".format(compact(type(exc).__name__))) from exc
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise SafeError("响应不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise SafeError("响应 JSON 结构异常")
    return data


def extract_identity(data: Dict[str, Any], userid: str) -> str:
    for key in ("name", "nickname", "userName", "username", "displayName", "NickName"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    memo = data.get("memo")
    if isinstance(memo, dict):
        for key in ("name", "nickname", "uid"):
            value = memo.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (int, float)):
                return str(value)
    return userid


def interpret_signin(data: Dict[str, Any]) -> Tuple[str, str]:
    status = str(data.get("status") or "").strip().lower()
    message = compact(
        data.get("msg")
        or data.get("message")
        or data.get("Message")
        or data.get("error")
        or ""
    )
    if status == "success":
        return "success", message or "签到成功"
    lowered = message.lower()
    if any(token in message for token in ("已签到", "重复签到", "今日已签")) or "already" in lowered:
        return "alreadyComplete", message or "今日已签到"
    return "failure", message or "签到未成功"


def script_selectors() -> List[str]:
    script = Path(__file__).resolve()
    return [
        CATALOG_ID,
        script.name,
        "candidate.py",
        "gzsx_wechat_signin.py",
        "AutoSignIn-Base.py",
        "output/candidate.py",
        "scripts/gzsx_wechat_signin.py",
        script.as_posix(),
    ]


def notification_selected() -> bool:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    selected = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selected is None:
        return False
    stripped = selected.strip()
    if stripped == "":
        return False
    if stripped == "*":
        return True
    patterns = [part for part in re.split(r"[,;\s]+", stripped) if part]
    choices = script_selectors()
    return any(
        fnmatch.fnmatchcase(choice, pattern)
        for pattern in patterns
        for choice in choices
    )


def discover_notify_paths() -> Tuple[List[Path], List[Path]]:
    dirs: List[Path] = []
    custom = env("QINGLONG_NOTIFY_DIR")
    if custom:
        dirs.append(Path(custom))
    dirs.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    py_paths = [directory / "notify.py" for directory in dirs]
    js_paths = [directory / "sendNotify.js" for directory in dirs]
    return py_paths, js_paths


def send_via_python(title: str, body: str, paths: List[Path]) -> bool:
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            sender(title, body)
            return True
    except Exception:
        pass
    for path in paths:
        try:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("qinglong_gzsx_notify", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                sender(title, body)
                return True
        except Exception:
            continue
    return False


def send_via_node(title: str, body: str, paths: List[Path]) -> bool:
    node = None
    for candidate in ("node", "nodejs"):
        from shutil import which

        node = which(candidate)
        if node:
            break
    if not node:
        return False
    payload = json.dumps({"title": title, "body": body}, ensure_ascii=False)
    worker = (
        "const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));"
        "Promise.resolve().then(()=>require(process.argv[1]).sendNotify(p.title,p.body))"
        ".then(r=>process.exit(r===false?1:0)).catch(()=>process.exit(1));"
    )
    for path in paths:
        if not path.is_file():
            continue
        try:
            completed = subprocess.run(
                [node, "-e", worker, str(path.resolve())],
                input=payload,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                return True
        except Exception:
            continue
    return False


def notify(summary: str, dry_run: bool) -> str:
    if not notification_selected():
        log("{} 通知：未启用或未命中通知名单".format(ICONS["skipped"]))
        return "disabled"
    if dry_run:
        log("{} 通知预演：{}".format(ICONS["skipped"], summary))
        return "dry-run"
    py_paths, js_paths = discover_notify_paths()
    try:
        if send_via_python(TITLE, summary, py_paths):
            log("{} 通知已通过 notify.py 发送".format(ICONS["success"]))
            return "sent"
        if send_via_node(TITLE, summary, js_paths):
            log("{} 通知已通过 sendNotify.js 发送".format(ICONS["success"]))
            return "sent"
        log("{} 通知工具不可用；保留业务退出码".format(ICONS["warning"]))
        return "unavailable"
    except Exception:
        log("{} 通知发送失败；保留业务退出码".format(ICONS["warning"]))
        return "failed"


def process_account(
    index: int,
    total: int,
    account: Dict[str, str],
    location: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> Dict[str, Any]:
    account_started = time.monotonic()
    userid = account["userid"]
    result: Dict[str, Any] = {
        "account": index,
        "ok": False,
        "status": "failure",
        "identity": userid,
        "message": "",
        "elapsedSeconds": 0.0,
        "tasks": {
            "total": 1,
            "success": 0,
            "alreadyComplete": 0,
            "skipped": 0,
            "failure": 0,
        },
    }
    log("---------- 账号 {}/{} ----------".format(index, total))

    stage1 = time.monotonic()
    log("账号 {} / 阶段 1 参数检查".format(index))
    try:
        if not account["apitoken"] or not userid:
            raise SafeError("凭据不完整")
        log(
            "{} 参数检查通过；公开 UID：{}；阶段 1 耗时 {:.2f}秒".format(
                ICONS["success"], userid, time.monotonic() - stage1
            )
        )
    except SafeError as error:
        log("{} {}".format(ICONS["failure"], error))
        result["message"] = str(error)
        result["tasks"]["failure"] = 1
        result["elapsedSeconds"] = round(time.monotonic() - account_started, 3)
        log(
            "账号 {} 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1，耗时 {:.2f}秒".format(
                index, result["elapsedSeconds"]
            )
        )
        return result

    if dry_run:
        stage2 = time.monotonic()
        log("账号 {} / 阶段 2 每日签到（预演）".format(index))
        log("{} DRY_RUN_OK：已预演 DoSignin，未发送请求、无副作用".format(ICONS["skipped"]))
        log("阶段 2 耗时 {:.2f}秒".format(time.monotonic() - stage2))
        result.update(ok=True, status="skipped", message="DRY_RUN_OK")
        result["tasks"]["skipped"] = 1
        result["elapsedSeconds"] = round(time.monotonic() - account_started, 3)
        log(
            "账号 {}（{}）统计：总任务 1，成功 0，已完成 0，跳过 1，失败 0，耗时 {:.2f}秒".format(
                index, userid, result["elapsedSeconds"]
            )
        )
        return result

    stage2 = time.monotonic()
    log("账号 {} / 阶段 2 每日签到".format(index))
    try:
        data = http_post_json(
            SIGNIN_URL,
            build_headers(account["apitoken"]),
            build_payload(userid, location),
            timeout,
        )
        identity = extract_identity(data, userid)
        result["identity"] = identity
        if identity != userid:
            log("账号 {} 官方身份：{}".format(index, identity))
        status, message = interpret_signin(data)
        icon = ICONS.get(status, ICONS["failure"])
        log(
            "{} {}；阶段 2 耗时 {:.2f}秒".format(
                icon, message, time.monotonic() - stage2
            )
        )
        result["message"] = message
        result["status"] = status
        result["ok"] = status in {"success", "alreadyComplete"}
        if status == "success":
            result["tasks"]["success"] = 1
        elif status == "alreadyComplete":
            result["tasks"]["alreadyComplete"] = 1
        else:
            result["tasks"]["failure"] = 1
    except SafeError as error:
        log(
            "{} {}；阶段 2 耗时 {:.2f}秒".format(
                ICONS["failure"], error, time.monotonic() - stage2
            )
        )
        result["message"] = str(error)
        result["tasks"]["failure"] = 1
    except Exception:
        log(
            "{} 未预期错误；阶段 2 耗时 {:.2f}秒".format(
                ICONS["failure"], time.monotonic() - stage2
            )
        )
        result["message"] = "未预期错误"
        result["tasks"]["failure"] = 1

    result["elapsedSeconds"] = round(time.monotonic() - account_started, 3)
    log(
        "账号 {}（{}）统计：总任务 1，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒".format(
            index,
            result["identity"],
            result["tasks"]["success"],
            result["tasks"]["alreadyComplete"],
            result["tasks"]["skipped"],
            result["tasks"]["failure"],
            result["elapsedSeconds"],
        )
    )
    return result


def main() -> int:
    started = time.monotonic()
    started_at = now_text()
    dry_setting = env("GZSX_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    location = location_fields()
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "正式运行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("GZSX_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        accounts = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "正式运行",
                len(accounts),
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
        if any(location.values()):
            log("已配置可选定位字段（不打印具体坐标内容）")
        else:
            log("定位字段留空（与上游 Server 版默认一致，不伪造坐标）")
    except SafeError as error:
        config_error = str(error)
        log("{} 阶段 0 参数配置：{}".format(ICONS["failure"], config_error))

    results: List[Dict[str, Any]] = []
    if config_error is None:
        for index, account in enumerate(accounts, 1):
            results.append(
                process_account(
                    index, len(accounts), account, location, timeout, dry_run
                )
            )

    success = sum(1 for item in results if item["status"] == "success")
    already = sum(1 for item in results if item["status"] == "alreadyComplete")
    skipped = sum(1 for item in results if item["status"] == "skipped")
    failure = sum(1 for item in results if item["status"] == "failure")
    passed = sum(1 for item in results if item["ok"])
    if config_error:
        failed_accounts = max(len(accounts), 1)
        exit_code = 1
        final_status = "configuration-error"
    else:
        failed_accounts = len(results) - passed
        exit_code = 1 if failed_accounts > 0 or not accounts else 0
        if dry_run and exit_code == 0:
            final_status = "dry-run"
        elif exit_code == 0:
            final_status = "success"
        elif passed > 0 and failed_accounts > 0:
            final_status = "partial-failure"
        else:
            final_status = "failure"

    body = "账号总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}；状态 {}".format(
        len(accounts), success, already, skipped, failure, final_status
    )
    if config_error:
        body += "。配置错误：{}".format(config_error)
    if dry_run:
        body += "。断网预演，未进行真实签到"
    notification = notify(body, dry_run)

    log("----------------------------------------")
    log("任务统计：" + body)
    log(
        "子任务统计：成功 {}，已完成 {}，跳过 {}，失败 {}；通知状态：{}".format(
            success, already, skipped, failure, notification
        )
    )
    finished_at = now_text()
    log(
        "完成时间：{}；总耗时 {:.2f}秒；最终状态：{}；退出码 {}".format(
            finished_at, time.monotonic() - started, final_status, exit_code
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    summary = {
        "applicationKey": APPLICATION_KEY,
        "task": TITLE,
        "catalogId": CATALOG_ID,
        "mode": "dry-run" if dry_run else "live",
        "status": final_status,
        "accounts": len(accounts),
        "success": success,
        "alreadyComplete": already,
        "skipped": skipped,
        "failure": failure,
        "passedAccounts": passed,
        "failedAccounts": failed_accounts,
        "configurationError": bool(config_error),
        "dryRun": dry_run,
        "notification": notification,
        "startTime": started_at,
        "finishTime": finished_at,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "exitCode": exit_code,
        "results": [
            {
                "account": item["account"],
                "ok": item["ok"],
                "status": item["status"],
                "identity": item["identity"],
                "elapsedSeconds": item["elapsedSeconds"],
                "tasks": item["tasks"],
            }
            for item in results
        ],
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
