#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 班级魔法自动签到
# cron: 44 8 * * 1-5
#
# SPDX-License-Identifier: GPL-3.0-only
# effectiveLicense: GPL-3.0
#
# 来源：JasonYANG170/AutoCheckBJMF/main.py
# 上游提交：51db1e7fab5d41411cb089cf62f9ef62899bf90e
# 项目：https://github.com/JasonYANG170/AutoCheckBJMF
# 教程：https://github.com/JasonYANG170/AutoCheckBJMF/wiki/
# 登录：https://k8n.cn/student/login
#
# 本文件为青龙独立维护版：环境变量多账号、断网预演、超时与业务成功判定、
# 脱敏时间轴日志与青龙通知。已移除交互式 input、本地 config.json 自动写入、
# 进程内长驻 schedule 轮询、PushPlus 直连与调试明文 Cookie 输出。
#
# Copyright (C) JasonYANG170 and contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""班级魔法（k8n.cn）课堂签到独立维护版。

BJMF_COOKIE：每个非空行一个账号 Cookie。可含可选备注 username=<备注>，
以及 remember_student_59ba36addc2b2f9401580f014c7f58ea4e30989d=<令牌>。
仅在第一个字段分隔符处拆分同账号配套字段时保留后续凭据原文。
BJMF_CLASS_ID / BJMF_LAT / BJMF_LNG：班级与定位（可全班共用）。
BJMF_ACC：海拔，可空。
BJMF_DRY_RUN=1：完全断网预演，不发起网络请求。
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
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('7be4b090d277382e', 'scripts/task_7be4b090.py', 'task_7be4b090.py', 'task_7be4b090')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import gzip
import html
import importlib
import importlib.util
import io
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "班级魔法自动签到"
CATALOG_ID = "7be4b090d277382e"
BASE_HOST = "k8n.cn"
REMEMBER_KEY = "remember_student_59ba36addc2b2f9401580f014c7f58ea4e30989d"
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
UA = (
    "Mozilla/5.0 (Linux; Android 9; AKT-AK47 Build/USER-AK47; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 "
    "Mobile Safari/537.36 XWEB/1160065 MMWEBSDK/20231202 MMWEBID/1136 "
    "MicroMessenger/8.0.47.2560(0x28002F35) WeChat/arm64 Weixin NetType/4G "
    "Language/zh_CN ABI/arm64"
)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

PY_NOTIFY_RUNNER = r"""
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
"""

JS_NOTIFY_RUNNER = r"""
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
}
const path = input.path;
let mod;
if (path) {
  mod = require(path);
} else {
  process.exit(3);
}
const send = mod.sendNotify || mod.send || mod.default;
if (typeof send !== 'function') process.exit(3);
Promise.resolve(send(input.title, input.body)).then((result) => {
  process.exit(result === false ? 1 : 0);
}).catch(() => process.exit(1));
"""


def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(message: str, icon: str = "") -> None:
    prefix = f"{icon} " if icon else ""
    print(f"[{now_ts()}] {prefix}{message}", flush=True)


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    value = str(raw).strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = env(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须在 {minimum}..{maximum} 之间")
    return value


def first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def redact(text: str, secrets: List[str]) -> str:
    cleaned = html.unescape(re.sub(r"<[^>]*>", " ", str(text or "")))
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for secret in secrets:
        if not secret:
            continue
        cleaned = cleaned.replace(secret, "[REDACTED]")
        for part in secret.split(";"):
            part = part.strip()
            if "=" in part:
                key, val = part.split("=", 1)
                if val:
                    cleaned = cleaned.replace(val, f"[{key or 'SECRET'}_REDACTED]")
            elif part:
                cleaned = cleaned.replace(part, "[REDACTED]")
    cleaned = re.sub(r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])", "[手机号已隐藏]", cleaned)
    cleaned = re.sub(re.escape(REMEMBER_KEY) + r"=[^;\s]+", f"{REMEMBER_KEY}=[REDACTED]", cleaned)
    return cleaned[:240]


def modify_decimal_part(num: str) -> str:
    """保留上游多人签到微偏移逻辑，避免同坐标冲突。"""
    value = float(num)
    num_str = f"{value:.8f}"
    decimal_index = num_str.find(".")
    decimal_part = num_str[decimal_index + 4 : decimal_index + 9]
    decimal_value = int(decimal_part or "0")
    random_offset = random.randint(-15000, 15000)
    new_decimal_value = abs(decimal_value + random_offset)
    new_decimal_str = f"{new_decimal_value:05d}"
    new_num_str = num_str[: decimal_index + 4] + new_decimal_str + num_str[decimal_index + 9 :]
    return f"{float(new_num_str):.8f}"


def parse_account_line(line: str) -> Dict[str, str]:
    """每行一个账号；可选 username=备注；提取 remember_student Cookie。"""
    raw = line.strip()
    if not raw:
        raise ValueError("空账号行")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise ValueError("Cookie 含非法控制字符")

    remark = ""
    remark_match = re.search(r"(?:^|[;\s])username=([^;]*)", raw, re.I)
    if remark_match:
        remark = remark_match.group(1).strip()

    remember_match = re.search(
        re.escape(REMEMBER_KEY) + r"=([^;]+)",
        raw,
        re.I,
    )
    if remember_match:
        token = remember_match.group(1).strip()
        cookie = f"{REMEMBER_KEY}={token}"
    else:
        # 允许仅填写令牌值（无键名）
        if "=" not in raw and ";" not in raw and len(raw) >= 16:
            cookie = f"{REMEMBER_KEY}={raw}"
            token = raw
        else:
            raise ValueError(f"未找到 {REMEMBER_KEY}")
    if not token or len(token) < 8:
        raise ValueError("remember_student 令牌过短或无效")
    try:
        cookie.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ValueError("Cookie 含非 Latin-1 字符") from exc
    return {"cookie": cookie, "remark": remark, "raw": raw, "token": token}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts = []
    for line in raw.splitlines():
        if line.strip():
            accounts.append(parse_account_line(line))
    return accounts


def extract_title(page: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip() if match else ""


def extract_div_title(page: str) -> str:
    match = re.search(
        r'<div[^>]*\bid=["\']title["\'][^>]*>(.*?)</div>',
        page,
        re.I | re.S,
    )
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def extract_identity(page: str) -> str:
    patterns = (
        r'class=["\'][^"\']*user[^"\']*["\'][^>]*>([^<]{1,40})<',
        r"(?:姓名|昵称|学生)[：:]\s*([^<\s]{1,40})",
        r'class=["\']name["\'][^>]*>([^<]{1,40})<',
    )
    for pattern in patterns:
        match = re.search(pattern, page, re.I)
        if match:
            value = html.unescape(match.group(1)).strip()
            if value and value not in {"签到成功", "出错", "登录"}:
                return value
    return ""


def find_punch_ids(page: str) -> List[str]:
    gps = re.findall(r"punch_gps\((\d+)\)", page)
    scan = re.findall(r"punchcard_(\d+)", page)
    seen = set()
    ordered: List[str] = []
    for item in gps + scan:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.hostname != BASE_HOST:
            raise urllib.error.HTTPError(newurl, code, "拒绝向站外重定向发送凭据", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    data: Optional[Dict[str, str]],
    timeout: int,
) -> Tuple[int, str]:
    body = None
    req_headers = dict(headers)
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        req_headers.setdefault(
            "Content-Type",
            "application/x-www-form-urlencoded; charset=UTF-8",
        )
    request = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    opener = urllib.request.build_opener(SameHostRedirect())
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise RuntimeError(f"网络错误：{type(exc).__name__}") from None
    try:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        status = int(getattr(response, "status", getattr(response, "code", 0)) or 0)
        encoding = (response.headers.get("Content-Encoding") or "").lower()
    finally:
        try:
            response.close()
        except Exception:
            pass
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("响应超过大小限制")
    if encoding == "gzip":
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
            raw = gz.read(MAX_RESPONSE_BYTES + 1)
    elif encoding == "deflate":
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("解压响应超过大小限制")
    charset = "utf-8"
    try:
        charset = response.headers.get_content_charset() or "utf-8"
    except Exception:
        pass
    return status, raw.decode(charset, errors="replace")


def classify_punch_message(message: str) -> str:
    text = message or ""
    if any(token in text for token in ("签到成功", "打卡成功")):
        return "success"
    if any(token in text for token in ("已签到", "已经签到", "重复签到", "无需再签")):
        return "alreadyComplete"
    if any(token in text for token in ("失败", "错误", "无效", "过期", "异常", "未登录")):
        return "failure"
    return "failure"


class AccountRunner:
    def __init__(self, number: int, remark: str = "") -> None:
        self.number = number
        self.remark = remark
        self.identity = remark
        self.started = time.monotonic()
        self.stats = {key: 0 for key in STATES}
        self.status = "failure"
        self.message = ""
        self.details: List[str] = []

    def stage_begin(self, number: int, name: str) -> float:
        log(f"账号{self.number} · 阶段{number} {name}：开始")
        return time.monotonic()

    def stage_end(self, number: int, name: str, state: str, detail: str, began: float) -> None:
        self.stats[state] = self.stats.get(state, 0) + 1
        icon = ICONS.get(state, ICONS["failure"])
        log(
            f"账号{self.number} · 阶段{number} {name}：{icon} {detail}"
            f"（{time.monotonic() - began:.2f}秒）"
        )
        self.details.append(f"{name}:{detail}")

    def finish_log(self) -> None:
        label = self.identity or self.remark or f"账号{self.number}"
        total = sum(self.stats.values())
        log(
            f"账号{self.number}（{label}）统计：总任务{total}，成功{self.stats['success']}，"
            f"已完成{self.stats['alreadyComplete']}，跳过{self.stats['skipped']}，"
            f"失败{self.stats['failure']}，耗时{time.monotonic() - self.started:.2f}秒；"
            f"状态 {self.status}"
        )


def notification_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        log("QINGLONG_NOTIFY 值无效，按 auto 处理", ICONS["warning"])
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return False, "默认仅通知名单内脚本，未配置 QINGLONG_NOTIFY_SCRIPTS"
    selectors = [
        item.strip()
        for item in re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", ""))
        if item.strip()
    ]
    if not selectors:
        return False, "QINGLONG_NOTIFY_SCRIPTS 为空，已禁用全部通知"
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "candidate.py",
        "bjmf_autocheck.py",
        "scripts/bjmf_autocheck.py",
        "autocheckbjmf",
        "jasonyang170/autocheckbjmf",
    }
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
    enabled = any(
        any(fnmatch.fnmatchcase(identity.lower(), selector.lower()) for identity in identities)
        for selector in selectors
    )
    return enabled, "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"


def notify(body: str, dry_run: bool) -> str:
    enabled, reason = notification_enabled()
    if not enabled:
        log(f"通知：{ICONS['skipped']} {reason}")
        return "disabled"
    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": dry_run,
        "directory": str(Path(__file__).resolve().parent),
        "path": None,
    }
    paths: List[Path] = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser())
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    adapters: List[Tuple[str, Optional[Path]]] = [("python", None)]
    adapters.extend(
        ("python", folder / "notify.py")
        for folder in paths
        if (folder / "notify.py").is_file()
    )
    node = shutil.which("node")
    if node:
        adapters.extend(
            ("javascript", folder / "sendNotify.js")
            for folder in paths
            if (folder / "sendNotify.js").is_file()
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


def load_shared_config() -> Dict[str, str]:
    class_id = first_env("BJMF_CLASS_ID", "BJMF_CLASS", "ClassID")
    lat = first_env("BJMF_LAT", "X")
    lng = first_env("BJMF_LNG", "Y")
    acc = first_env("BJMF_ACC", "ACC", default="")
    if not class_id:
        raise ValueError("缺少 BJMF_CLASS_ID（班级 ID）")
    if not re.fullmatch(r"[0-9A-Za-z_-]{1,64}", class_id):
        raise ValueError("BJMF_CLASS_ID 格式无效")
    if not lat:
        raise ValueError("缺少 BJMF_LAT（纬度）")
    if not lng:
        raise ValueError("缺少 BJMF_LNG（经度）")
    try:
        float(lat)
        float(lng)
    except ValueError as exc:
        raise ValueError("BJMF_LAT / BJMF_LNG 必须是数字") from exc
    return {"class_id": class_id, "lat": lat, "lng": lng, "acc": acc}


def run_account(
    number: int,
    account: Dict[str, str],
    shared: Dict[str, str],
    timeout: int,
    gps_offset: bool,
    retries: int,
    retry_delay: int,
) -> AccountRunner:
    runner = AccountRunner(number, account.get("remark", ""))
    secrets = [account["cookie"], account.get("token", ""), account.get("raw", "")]
    class_id = shared["class_id"]
    list_url = f"http://{BASE_HOST}/student/course/{class_id}/punchs"
    headers = {
        "User-Agent": UA,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;q=0.8,"
            "application/signed-exchange;v=b3;q=0.7"
        ),
        "X-Requested-With": "com.tencent.mm",
        "Referer": f"http://{BASE_HOST}/student/course/{class_id}",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": account["cookie"],
    }

    attempt = 0
    last_error = "未执行"
    while attempt <= retries:
        attempt += 1
        try:
            began = runner.stage_begin(1, "拉取进行中签到")
            status, page = http_request("GET", list_url, headers, None, timeout)
            if status != 200:
                runner.stage_end(1, "拉取进行中签到", "failure", f"HTTP {status}", began)
                last_error = f"列表页 HTTP {status}"
                if attempt <= retries:
                    time.sleep(retry_delay)
                    continue
                runner.status = "failure"
                runner.message = last_error
                runner.finish_log()
                return runner

            title = extract_title(page)
            identity = extract_identity(page)
            if identity:
                runner.identity = identity
                log(f"账号{number} · 用户：{identity}")
            elif runner.remark:
                log(f"账号{number} · 备注：{runner.remark}")

            if title and "出错" in title:
                runner.stage_end(1, "拉取进行中签到", "failure", "登录状态异常，请更新 Cookie", began)
                runner.status = "failure"
                runner.message = "登录状态异常"
                runner.finish_log()
                return runner

            punch_ids = find_punch_ids(page)
            if not punch_ids:
                runner.stage_end(1, "拉取进行中签到", "skipped", "当前无进行中的签到", began)
                runner.status = "skipped"
                runner.message = "当前无进行中的签到"
                runner.finish_log()
                return runner

            runner.stage_end(
                1,
                "拉取进行中签到",
                "success",
                f"发现 {len(punch_ids)} 个签到任务",
                began,
            )

            punch_states: List[str] = []
            punch_messages: List[str] = []
            for index, punch_id in enumerate(punch_ids, 1):
                began_p = runner.stage_begin(1 + index, f"提交签到#{punch_id}")
                lat = modify_decimal_part(shared["lat"]) if gps_offset else shared["lat"]
                lng = modify_decimal_part(shared["lng"]) if gps_offset else shared["lng"]
                punch_url = f"http://{BASE_HOST}/student/punchs/course/{class_id}/{punch_id}"
                payload = {
                    "id": punch_id,
                    "lat": lat,
                    "lng": lng,
                    "acc": shared["acc"],
                    "res": "",
                    "gps_addr": "",
                }
                try:
                    p_status, p_page = http_request("POST", punch_url, headers, payload, timeout)
                except RuntimeError as exc:
                    state = "failure"
                    detail = redact(str(exc), secrets)
                    runner.stage_end(1 + index, f"提交签到#{punch_id}", state, detail, began_p)
                    punch_states.append(state)
                    punch_messages.append(detail)
                    continue
                if p_status != 200:
                    state = "failure"
                    detail = f"HTTP {p_status}"
                    runner.stage_end(1 + index, f"提交签到#{punch_id}", state, detail, began_p)
                    punch_states.append(state)
                    punch_messages.append(detail)
                    continue
                message = extract_div_title(p_page) or extract_title(p_page) or "未找到签到结果"
                message = redact(message, secrets)
                state = classify_punch_message(message)
                # 无明确成功文案时不猜测成功
                if state == "failure" and message and "未找到" not in message:
                    # 保留业务原文摘要（已脱敏）
                    pass
                runner.stage_end(1 + index, f"提交签到#{punch_id}", state, message, began_p)
                punch_states.append(state)
                punch_messages.append(message)

            if any(state == "success" for state in punch_states) and not any(
                state == "failure" for state in punch_states
            ):
                runner.status = "success"
                runner.message = "签到成功"
            elif any(state == "alreadyComplete" for state in punch_states) and not any(
                state == "failure" for state in punch_states
            ):
                runner.status = "alreadyComplete"
                runner.message = "今日已签到"
            elif any(state == "success" for state in punch_states) or any(
                state == "alreadyComplete" for state in punch_states
            ):
                # 部分成功仍视为账号未完全成功，触发非零退出
                runner.status = "failure"
                runner.message = "部分签到失败：" + "；".join(punch_messages)
            else:
                runner.status = "failure"
                runner.message = "签到失败：" + "；".join(punch_messages)
                if attempt <= retries:
                    log(f"账号{number} · 准备短重试（{retry_delay}秒）", ICONS["warning"])
                    time.sleep(retry_delay)
                    # 重置本轮失败计数后重试列表页（保留已记录阶段）
                    continue
            runner.finish_log()
            return runner
        except RuntimeError as exc:
            last_error = redact(str(exc), secrets)
            log(f"账号{number} · {ICONS['failure']} {last_error}")
            if attempt <= retries:
                time.sleep(retry_delay)
                continue
            runner.stats["failure"] += 1
            runner.status = "failure"
            runner.message = last_error
            runner.finish_log()
            return runner
        except Exception:
            last_error = "内部处理失败，已抑制异常详情"
            runner.stats["failure"] += 1
            runner.status = "failure"
            runner.message = last_error
            runner.finish_log()
            return runner

    runner.status = "failure"
    runner.message = last_error
    runner.finish_log()
    return runner


def dry_run_account(number: int, account: Dict[str, str], shared: Dict[str, str]) -> AccountRunner:
    runner = AccountRunner(number, account.get("remark", ""))
    if runner.remark:
        runner.identity = runner.remark
        log(f"账号{number} · 备注：{runner.remark}")
    stages = (
        (1, "校验 Cookie 与班级定位配置"),
        (2, "拉取进行中签到"),
        (3, "提交 GPS/扫码签到"),
    )
    for number_stage, name in stages:
        began = runner.stage_begin(number_stage, name)
        if number_stage == 1:
            ok = bool(account.get("cookie") and shared.get("class_id") and shared.get("lat") and shared.get("lng"))
            state = "success" if ok else "failure"
            detail = "配置校验通过" if ok else "配置不完整"
            runner.stage_end(number_stage, name, state, detail, began)
            if not ok:
                runner.status = "failure"
                runner.message = detail
                runner.finish_log()
                return runner
        else:
            runner.stage_end(number_stage, name, "skipped", "断网预演跳过，未访问网络", began)
    runner.status = "dry-run"
    runner.message = "断网预演通过"
    runner.finish_log()
    return runner


def account_ok(runner: AccountRunner) -> bool:
    return runner.status in {"success", "alreadyComplete", "skipped", "dry-run"}


def build_notify_body(
    runners: List[AccountRunner],
    dry_run: bool,
    status: str,
    config_error: str = "",
) -> str:
    total = len(runners)
    succeeded = sum(1 for item in runners if account_ok(item) and item.status != "failure")
    failed = sum(1 for item in runners if not account_ok(item))
    lines = [
        f"账号总数{total}，成功{succeeded}，失败{failed}；状态{status}",
    ]
    if config_error:
        lines.append(config_error)
    for item in runners:
        label = item.identity or item.remark or f"账号{item.number}"
        lines.append(f"账号{item.number} {label}：{item.message or item.status}")
    if dry_run:
        lines.append("模式：断网预演")
    return "\n".join(lines)


def emit_summary(payload: Dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    print("TASK_SUMMARY=" + encoded, flush=True)


def main() -> int:
    started = time.monotonic()
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    dry_run = env_bool("BJMF_DRY_RUN")
    log(f"==== {TITLE} ====")
    log(f"开始时间 {started_at}")
    log(f"运行模式 {'断网预演' if dry_run else '正式签到'}")

    runners: List[AccountRunner] = []
    config_error = ""
    notify_status = "disabled"
    exit_code = 0

    try:
        timeout = bounded_int("BJMF_TIMEOUT", 20, 5, 120)
        retries = bounded_int("BJMF_RETRY", 1, 0, 3)
        retry_delay = bounded_int("BJMF_RETRY_DELAY", 3, 0, 30)
        gps_offset = env_bool("BJMF_GPS_OFFSET", True)
        shared = load_shared_config()
        cookie_raw = first_env("BJMF_COOKIE", "BJMF_COOKIES", "Cookies")
        if not cookie_raw:
            raise ValueError("缺少 BJMF_COOKIE：请每行填写一个账号 Cookie")
        accounts = parse_accounts(cookie_raw)
        if not accounts:
            raise ValueError("BJMF_COOKIE 无有效账号行")
    except ValueError as exc:
        config_error = str(exc)
        log(f"账号数 0；{ICONS['failure']} 配置错误：{config_error}")
        exit_code = 2
        status = "configuration_error"
        body = build_notify_body([], dry_run, status, config_error)
        notify_status = notify(body, dry_run=True if dry_run else False)
        finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
        log("----------------------------------------")
        log(body.replace("\n", "；"))
        log(
            f"完成时间 {finished_at}；耗时{time.monotonic() - started:.2f}秒；"
            f"最终状态 {status}；通知 {notify_status}"
        )
        emit_summary(
            {
                "application": "bjmf",
                "catalogId": CATALOG_ID,
                "dryRun": dry_run,
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "status": status,
                "exitCode": exit_code,
                "notification": notify_status,
                "finishedAt": finished_at,
                "elapsedSeconds": round(time.monotonic() - started, 2),
                "message": config_error,
            }
        )
        return exit_code

    log(f"账号数 {len(accounts)}；班级ID已配置；定位已配置；凭据已隐藏")
    if dry_run:
        for index, account in enumerate(accounts, 1):
            runners.append(dry_run_account(index, account, shared))
        ok = all(account_ok(item) for item in runners)
        exit_code = 0 if ok else 2
        status = "dry-run" if ok else "configuration_error"
        if ok:
            log("断网预演通过", ICONS["success"])
    else:
        for index, account in enumerate(accounts, 1):
            runners.append(
                run_account(
                    index,
                    account,
                    shared,
                    timeout=timeout,
                    gps_offset=gps_offset,
                    retries=retries,
                    retry_delay=retry_delay,
                )
            )
        ok = all(account_ok(item) for item in runners)
        exit_code = 0 if ok else 1
        if ok:
            if all(item.status == "skipped" for item in runners):
                status = "success"
            elif any(item.status == "failure" for item in runners):
                status = "partial-failure"
            else:
                status = "success"
        else:
            status = (
                "partial-failure"
                if any(account_ok(item) for item in runners)
                else "failure"
            )

    body = build_notify_body(runners, dry_run, status, config_error)
    notify_status = notify(body, dry_run=dry_run)
    finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
    totals = {key: sum(item.stats.get(key, 0) for item in runners) for key in STATES}
    succeeded = sum(1 for item in runners if account_ok(item))
    failed = len(runners) - succeeded

    log("----------------------------------------")
    log(
        f"任务统计：账号总数{len(runners)}，成功{succeeded}，失败{failed}；"
        f"子任务成功{totals['success']}，已完成{totals['alreadyComplete']}，"
        f"跳过{totals['skipped']}，失败{totals['failure']}"
    )
    log(
        f"完成时间 {finished_at}；耗时{time.monotonic() - started:.2f}秒；"
        f"最终状态 {status}；通知 {notify_status}"
    )
    emit_summary(
        {
            "application": "bjmf",
            "catalogId": CATALOG_ID,
            "dryRun": dry_run,
            "total": len(runners),
            "succeeded": succeeded,
            "failed": failed,
            "status": status,
            "exitCode": exit_code,
            "notification": notify_status,
            "finishedAt": finished_at,
            "elapsedSeconds": round(time.monotonic() - started, 2),
            "taskStatistics": totals,
            "accounts": [
                {
                    "account": item.number,
                    "identity": item.identity or item.remark or "",
                    "status": item.status,
                    "message": item.message,
                    "statistics": item.stats,
                }
                for item in runners
            ],
        }
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
