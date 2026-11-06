#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 九号出行每日签到
# cron: 0 7 * * *
from __future__ import annotations
#
# 来源：guopenglong/automation-scripts ninebot/nine_bot_checkin.py（MIT）
# https://github.com/guopenglong/automation-scripts
# 提交：65931dcd9a3c37619b442bea4930df0dc44c57f2
# 同应用合并：ninebot/nine_bot_blind_box.py（签到里程碑盲盒查询与领取）
# 同应用未合并：ninebot/nine_bot_share_reward.py（硬编码会话加密载荷，不可移植）
# 参考：ninebot/notification.py（错误提示风格；通知改用青龙适配器）
#
# MIT License
#
# Copyright (c) 2026 Zhu
# Copyright (c) guopenglong / automation-scripts contributors
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
"""九号出行（Ninebot）每日签到 - 青龙维护版。

功能清点（相对上游 nine_bot_checkin.py / nine_bot_blind_box.py）：
- 调用 portal 用户签到 v2 接口完成每日签到
- 合并同日同凭据的盲盒列表查询与可领取里程碑领取（经验 / N币）
- 移除对私有 notification.py、Server 酱密钥推送与失败静默 exit(0) 的依赖
- 不合并分享领奖：上游硬编码加密回调载荷，无法安全移植到任意账号
- 增加逐行多账号、NINEBOT_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

NINEBOT_ACCOUNTS：每个非空行一个账号，格式 Authorization令牌|device_id；
仅在第一个竖线处分割，后续凭据文本保留。不要用 & 或 @ 分隔账号。
兼容单账号别名：同时设置 NINEBOT_TOKEN 与 NINEBOT_DEVICE_ID（仅当 NINEBOT_ACCOUNTS 为空）。
NINEBOT_ENABLE_BLIND_BOX：默认 1，开启签到后的盲盒检查与领取；设为 0 可仅签到。
NINEBOT_TIMEOUT：单次 HTTPS 请求超时秒数，默认 30，范围 5..60。
NINEBOT_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：0 7 * * *（对齐上游 daily.yml 北京时间 07:00）。不打印 Token、device_id 或原始响应。
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
        _ql_notify_identities = ('8b80e03b90d5b3a1', 'scripts/nine_bot_checkin.py', 'nine_bot_checkin.py', 'nine_bot_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "九号出行每日签到"
CATALOG_ID = "8b80e03b90d5b3a1"
GATEWAY = "https://cn-cbu-gateway.ninebot.com"
SIGN_PATH = "/portal/api/user-sign/v2/sign"
BLIND_LIST_PATH = "/portal/api/user-sign/v2/blind-box/list"
BLIND_RECEIVE_PATH = "/portal/api/user-sign/v2/blind-box/receive"
DEFAULT_TIMEOUT = 30
MAX_BYTES = 1048576
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
REWARD_TYPE_LABELS = {
    1: "经验",
    2: "N币",
}
ALREADY_HINTS = ("已签到", "重复签到", "已经签到", "今日已签", "签过到", "already")
IDENTITY_KEYS = (
    "nickname",
    "nickName",
    "nick",
    "userName",
    "username",
    "displayName",
    "display_name",
    "name",
    "uid",
    "userId",
    "user_id",
    "id",
)
UA_H5 = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_timeout() -> float:
    raw = env("NINEBOT_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("NINEBOT_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("NINEBOT_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_flag(name: str, default: bool) -> bool:
    raw = env(name)
    if not raw:
        return default
    lowered = raw.lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    raise SafeError("{} 须为布尔值（1/0、true/false、yes/no、on/off）".format(name))


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 Authorization令牌|device_id")
    token, device_id = text.split("|", 1)
    token = token.strip()
    device_id = device_id.strip()
    if not token or not device_id:
        raise SafeError("Authorization 令牌或 device_id 为空")
    if any(ord(ch) < 32 for ch in token) or any(ord(ch) < 32 for ch in device_id):
        raise SafeError("账号行含控制字符")
    return {"token": token, "device_id": device_id}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("NINEBOT_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("NINEBOT_ACCOUNTS 没有有效账号行")
        return accounts
    token = env("NINEBOT_TOKEN")
    device_id = env("NINEBOT_DEVICE_ID")
    if token or device_id:
        if not token or not device_id:
            raise SafeError(
                "兼容别名需同时提供 NINEBOT_TOKEN 与 NINEBOT_DEVICE_ID；"
                "推荐改用 NINEBOT_ACCOUNTS（令牌|device_id）"
            )
        return [{"token": token, "device_id": device_id}]
    raise SafeError(
        "未配置 NINEBOT_ACCOUNTS；请按每个非空行 Authorization令牌|device_id 填写"
    )


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    candidates: List[Any] = []
    if isinstance(data, dict):
        candidates.append(data)
        for key in ("user", "userInfo", "profile", "member", "account"):
            nested = data.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)
    candidates.append(payload)
    for mapping in candidates:
        if not isinstance(mapping, dict):
            continue
        for key in IDENTITY_KEYS:
            value = mapping.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                text = compact(value, 64)
                if not text:
                    continue
                lowered = key.lower()
                if lowered in {"token", "authorization", "device_id", "deviceid"}:
                    continue
                if len(text) > 80 and re.fullmatch(r"[A-Za-z0-9._\-]+", text):
                    continue
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                return text
    return ""


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("msg", "message", "error", "errorMessage", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    return ""


def is_already_signed(payload: Any) -> bool:
    message = business_message(payload).lower()
    if any(hint.lower() in message for hint in ALREADY_HINTS):
        return True
    code = payload.get("code") if isinstance(payload, dict) else None
    # 部分网关用非 0 业务码表示重复签到，仅在文案命中时按已完成处理
    if code not in (0, "0", None) and message and any(
        hint.lower() in message for hint in ALREADY_HINTS
    ):
        return True
    return False


def is_receivable_box(box: Dict[str, Any]) -> bool:
    reward_status = box.get("rewardStatus")
    left_days = box.get("leftDaysToOpen")
    if reward_status == 1:
        return True
    if left_days in (0, "0"):
        return True
    if left_days is None:
        return True
    return False


def format_reward_message(result: Dict[str, Any]) -> str:
    reward_info = result.get("data") if isinstance(result.get("data"), dict) else {}
    reward_type = reward_info.get("rewardType")
    reward_value = reward_info.get("rewardValue")
    reward_label = REWARD_TYPE_LABELS.get(reward_type)
    if reward_label and reward_value is not None:
        return "{} {}".format(reward_label, reward_value)
    if reward_value is not None:
        return compact(reward_value, 64)
    return "未知奖励"


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""

    def display(self) -> str:
        return self.identity or "账号{}".format(self.number)

    def stage(self, number: int, name: str, operation):
        started = time.monotonic()
        log("账号 {} · 阶段 {} {}：开始".format(self.display(), number, name))
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
                    self.display(),
                    number,
                    name,
                    ICONS.get(state, ICONS["failure"]),
                    detail,
                    time.monotonic() - started,
                )
            )

    def skip(self, number: int, name: str, reason: str) -> None:
        self.stage(number, name, lambda: ("skipped", reason, None))

    def finish(self) -> None:
        log(
            "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.display(),
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                time.monotonic() - self.started,
                self.status,
            )
        )


class NinebotClient:
    def __init__(self, token: str, device_id: str, timeout: float) -> None:
        self.token = token
        self.device_id = device_id
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _headers(self) -> Dict[str, str]:
        return {
            "Host": "cn-cbu-gateway.ninebot.com",
            "Accept": "application/json, text/plain, */*",
            "Authorization": self.token,
            "Content-Type": "application/json",
            "platform": "h5",
            "language": "zh",
            "sys_language": "zh-CN",
            "device_id": self.device_id,
            "Origin": "https://h5-bj.ninebot.com",
            "Referer": "https://h5-bj.ninebot.com/",
            "User-Agent": UA_H5,
            "Connection": "close",
        }

    def request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        query: str = "",
    ) -> Tuple[int, Any]:
        url = "{}{}{}".format(GATEWAY, path, query)
        body = None
        headers = self._headers()
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers=headers, method=method.upper()
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
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
        if not raw:
            return status, None
        try:
            return status, json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise SafeError("响应不是合法 JSON") from exc


def do_sign(client: NinebotClient) -> Tuple[str, str, Any]:
    status, result = client.request_json(
        SIGN_PATH,
        method="POST",
        payload={"deviceId": client.device_id},
    )
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("签到响应无法解析")
    if result.get("code") in (0, "0"):
        return "success", "签到成功（业务码已核实）", result
    if is_already_signed(result):
        return "alreadyComplete", "今日已签到（业务文案已核实）", result
    hint = business_message(result)
    if hint:
        raise SafeError("签到业务失败")
    raise SafeError("签到业务失败（缺少可核实成功字段）")


def do_blind_boxes(client: NinebotClient) -> Tuple[str, str, Any]:
    timestamp = int(time.time() * 1000)
    status, result = client.request_json(
        BLIND_LIST_PATH,
        method="GET",
        query="?t={}".format(timestamp),
    )
    if status in (401, 403):
        raise SafeError("盲盒列表凭据无效或会话已过期")
    if status != 200:
        raise SafeError("盲盒列表请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("盲盒列表响应无法解析")
    if result.get("code") not in (0, "0"):
        raise SafeError("获取盲盒列表业务失败")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    boxes = data.get("notOpenedBoxes") if isinstance(data.get("notOpenedBoxes"), list) else []
    opened = 0
    skipped_missing = 0
    for box in boxes:
        if not isinstance(box, dict):
            continue
        if not is_receivable_box(box):
            continue
        award_days = box.get("awardDays")
        blind_box_ids = box.get("blindBoxIds") or []
        reward_id = blind_box_ids[0] if blind_box_ids else None
        if not reward_id:
            skipped_missing += 1
            log(
                "账号盲盒：⚠️ {}天里程碑缺少 rewardId，跳过领取".format(
                    compact(award_days, 16) or "?"
                )
            )
            continue
        recv_status, recv_result = client.request_json(
            BLIND_RECEIVE_PATH,
            method="POST",
            payload={"rewardId": str(reward_id)},
        )
        if recv_status in (401, 403):
            raise SafeError("盲盒领取凭据无效或会话已过期")
        if recv_status != 200:
            raise SafeError(
                "盲盒领取失败（HTTP {}，{}天里程碑）".format(
                    recv_status, compact(award_days, 16) or "?"
                )
            )
        if not isinstance(recv_result, dict):
            raise SafeError("盲盒领取响应无法解析")
        if recv_result.get("code") not in (0, "0"):
            raise SafeError(
                "盲盒领取业务失败（{}天里程碑）".format(compact(award_days, 16) or "?")
            )
        opened += 1
        log(
            "账号盲盒：✅ {}天里程碑领取成功：{}".format(
                compact(award_days, 16) or "?",
                format_reward_message(recv_result),
            )
        )
    detail = "未开启盲盒 {} 个；本轮领取 {} 个".format(len(boxes), opened)
    if skipped_missing:
        detail += "；缺 rewardId 跳过 {}".format(skipped_missing)
    if opened:
        return "success", detail, result
    if boxes:
        return "alreadyComplete", detail + "（无可立即领取项）", result
    return "success", "当前无未开启盲盒里程碑", result


def run_account(
    runner: AccountRunner,
    token: str,
    device_id: str,
    timeout: float,
    enable_blind_box: bool,
    dry_run: bool,
) -> None:
    def parameter_check():
        return "success", "凭据本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "每日签到", "断网预演：不请求签到接口")
        if enable_blind_box:
            runner.skip(3, "盲盒检查与领取", "断网预演：不请求盲盒接口")
        else:
            runner.skip(3, "盲盒检查与领取", "已关闭 NINEBOT_ENABLE_BLIND_BOX")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    client = NinebotClient(token, device_id, timeout)
    sign_state_box: Dict[str, str] = {"state": "failure"}

    def sign_stage():
        state, detail, result = do_sign(client)
        identity = extract_identity(result)
        if identity:
            runner.identity = identity
            detail = "{}；公开身份：{}".format(detail, identity)
        sign_state_box["state"] = state
        return state, detail, result

    runner.stage(2, "每日签到", sign_stage)

    def blind_stage():
        if not enable_blind_box:
            return "skipped", "已关闭 NINEBOT_ENABLE_BLIND_BOX", None
        state, detail, result = do_blind_boxes(client)
        if not runner.identity:
            identity = extract_identity(result)
            if identity:
                runner.identity = identity
                detail = "{}；公开身份：{}".format(detail, identity)
        return state, detail, result

    runner.stage(3, "盲盒检查与领取", blind_stage)

    if runner.stats["failure"]:
        runner.status = "failure"
    elif sign_state_box["state"] == "alreadyComplete" and runner.stats["success"] == 0:
        runner.status = "alreadyComplete"
    else:
        runner.status = "success"


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


def notification_enabled() -> Tuple[bool, str]:
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
        "ninebot_checkin.py",
        "nine_bot_checkin.py",
        "candidate.py",
        "scripts/ninebot_checkin.py",
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


def notify(body: str, dry_run: bool) -> str:
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


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("NINEBOT_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    enable_blind_box = True
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("NINEBOT_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        enable_blind_box = resolve_flag("NINEBOT_ENABLE_BLIND_BOX", True)
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；盲盒：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                "开启" if enable_blind_box else "关闭",
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, item in enumerate(accounts_data, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(
                    runner,
                    item["token"],
                    item["device_id"],
                    timeout,
                    enable_blind_box,
                    dry_run,
                )
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
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
