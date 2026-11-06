#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 终末地签到
# cron: 35 8 * * *
# new Env("终末地签到")
"""明日方舟：终末地（Endfield）国服森空岛 / 国际服 Skport 每日签到。

来源：Andrewww1228/Python-Endfield-Auto-Sign-In-with-Github
  Endfield_auto_signin.py（MIT，提交 ee4f48341e6e896f257076f4cd6a79d8f0d2bb74）
上游文件头标注 Author: sjtt2，系对 sjtt2/endfield_auto_sign 的适配；
国服签到路径与角色遍历参考已维护森空岛脚本（web/v1 终末地接口）。

功能清点（相对上游）：
- 国服 SKYLAND：Token → grant → cred → 绑定查询 → 终末地签到
- 国际服 SKPORT：同上流程，使用 gryphline / skport 域名
- 展示角色昵称、公开 UID、渠道与奖励；区分签到成功与今日已签到
- 移除 MANUAL_TOKENS 硬编码、result.json 落盘、无超时风险与分号多账号
- 统一为逐行多账号；遍历全部终末地绑定角色（不再只签第一个）
- 增加 ENDFIELD_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

ENDFIELD_ACCOUNTS（规范）：每个非空行一个账号，格式 region|token。
  region 为 cn / skland / 国服 或 global / skport / 国际服；
  仅在第一个 | 处分割，后续原文保留为 Token。
SKYLAND_TOKEN / SKPORT_TOKEN：可选兼容输入，每行一个 Token，区域隐含。
ENDFIELD_DRY_RUN=1：完全断网预演，不声明真实签到成功。
建议 Cron：30 8 * * *（与上游 0 30 8 * * * 对齐）。
"""
from __future__ import annotations
#
# MIT License
#
# Copyright (c) Andrewww1228 / Python-Endfield-Auto-Sign-In-with-Github contributors
# Copyright (c) sjtt2 / endfield_auto_sign contributors
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
        _ql_notify_identities = ('225069c5a03aea03', 'scripts/endfield_auto_signin.py', 'endfield_auto_signin.py', 'endfield_auto_signin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from urllib import parse as urlparse

TITLE = "终末地签到"
CATALOG_ID = "225069c5a03aea03"
PLATFORM = "3"
VNAME = "1.0.0"
DEFAULT_TIMEOUT = 20
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

SERVERS: Dict[str, Dict[str, str]] = {
    "cn": {
        "name": "国服",
        "APP_CODE": "4ca99fa6b56cc2ba",
        "GRANT_URL": "https://as.hypergryph.com/user/oauth2/v2/grant",
        "CRED_URL": "https://zonai.skland.com/web/v1/user/auth/generate_cred_by_code",
        "BIND_URL": "https://zonai.skland.com/api/v1/game/player/binding",
        "SIGN_URL": "https://zonai.skland.com/web/v1/game/endfield/attendance",
        "REFERER": "https://game.skland.com/",
        "ORIGIN": "https://game.skland.com/",
        "UA": "Skland/1.0.1 (com.skland.grass; Android; SDK_INT 34; Build/UP1A.231005.004)",
    },
    "global": {
        "name": "国际服",
        "APP_CODE": "6eb76d4e13aa36e6",
        "GRANT_URL": "https://as.gryphline.com/user/oauth2/v2/grant",
        "CRED_URL": "https://zonai.skport.com/web/v1/user/auth/generate_cred_by_code",
        "BIND_URL": "https://zonai.skport.com/api/v1/game/player/binding",
        "SIGN_URL": "https://zonai.skport.com/web/v1/game/endfield/attendance",
        "REFERER": "https://www.skport.com/",
        "ORIGIN": "https://www.skport.com/",
        "UA": "Skland/1.0.1 (skport; Android; SDK_INT 34; Build/UP1A.231005.004)",
    },
}

REGION_ALIASES = {
    "cn": "cn",
    "skland": "cn",
    "国服": "cn",
    "china": "cn",
    "global": "global",
    "skport": "global",
    "国际服": "global",
    "overseas": "global",
}


class SafeError(Exception):
    """仅携带脱敏说明。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def display(value: Any, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value if value is not None else "")).strip()
    return text[:limit]


def resolve_timeout() -> float:
    raw = env("ENDFIELD_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("ENDFIELD_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("ENDFIELD_TIMEOUT 须在 5 到 60 秒之间")
    return value


def normalize_token(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise SafeError("Token 为空")
    if any(ord(ch) < 32 for ch in text):
        raise SafeError("Token 含控制字符")
    try:
        payload = json.loads(text)
    except Exception:
        return text
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("content"), str):
            content = data["content"].strip()
            if content:
                return content
        if isinstance(payload.get("content"), str) and payload["content"].strip():
            return payload["content"].strip()
    return text


def parse_region_token_line(line: str) -> Dict[str, str]:
    text = line.strip()
    if "|" not in text:
        raise SafeError("账号行须为 region|token，例如 cn|你的Token")
    region_raw, token_raw = text.split("|", 1)
    region_key = REGION_ALIASES.get(region_raw.strip().lower()) or REGION_ALIASES.get(
        region_raw.strip()
    )
    if not region_key:
        raise SafeError("区域仅支持 cn/skland/国服 或 global/skport/国际服")
    token = normalize_token(token_raw)
    return {"region": region_key, "token": token, "label": SERVERS[region_key]["name"]}


def collect_accounts() -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    canonical = env("ENDFIELD_ACCOUNTS")
    if canonical:
        for line in canonical.splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            accounts.append(parse_region_token_line(text))
    for region, name in (("cn", "SKYLAND_TOKEN"), ("global", "SKPORT_TOKEN")):
        raw = env(name)
        if not raw:
            continue
        for line in raw.splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            if ";" in text:
                raise SafeError(
                    "{} 须每行一个 Token，不再使用分号分隔账号".format(name)
                )
            accounts.append(
                {
                    "region": region,
                    "token": normalize_token(text),
                    "label": SERVERS[region]["name"],
                }
            )
    return accounts


def http_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[dict],
    timeout: float,
    dry_run: bool,
) -> dict:
    if dry_run:
        raise SafeError("预演禁止网络请求")
    data = None
    req_headers = dict(headers)
    if body is not None:
        data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        req_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            if not 200 <= int(status) < 300:
                raise SafeError("HTTP 状态异常（{}）".format(status))
            chunks: List[bytes] = []
            size = 0
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise SafeError("响应超过大小限制")
                chunks.append(chunk)
    except SafeError:
        raise
    except urllib.error.HTTPError as error:
        raise SafeError("HTTP 状态异常（{}）".format(error.code)) from None
    except Exception:
        raise SafeError("网络或接口解析失败") from None
    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except Exception:
        raise SafeError("接口响应不是合法 JSON") from None
    if not isinstance(payload, dict):
        raise SafeError("接口响应格式异常")
    return payload


def generate_sign(token: str, path: str, body: str) -> Tuple[str, Dict[str, str]]:
    timestamp = str(int(time.time()))
    sign_header = {
        "platform": PLATFORM,
        "timestamp": timestamp,
        "dId": "",
        "vName": VNAME,
    }
    sign_header_str = json.dumps(sign_header, separators=(",", ":"))
    sign_str = path + body + timestamp + sign_header_str
    hmac_hex = hmac.new(
        token.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    md5_sign = hashlib.md5(hmac_hex.encode("utf-8")).hexdigest()
    return md5_sign, sign_header


def get_grant_code(token: str, cfg: Dict[str, str], timeout: float, dry_run: bool) -> str:
    payload = http_json(
        "POST",
        cfg["GRANT_URL"],
        {
            "User-Agent": cfg["UA"],
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        {"appCode": cfg["APP_CODE"], "token": token, "type": 0},
        timeout,
        dry_run,
    )
    if payload.get("status") != 0:
        raise SafeError(
            "获取授权码失败：{}".format(
                display(payload.get("msg") or payload.get("message") or "未知错误")
            )
        )
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("code"), str) or not data["code"]:
        raise SafeError("授权响应缺少 code")
    return data["code"]


def get_cred(
    grant_code: str, cfg: Dict[str, str], timeout: float, dry_run: bool
) -> Tuple[str, str, str]:
    payload = http_json(
        "POST",
        cfg["CRED_URL"],
        {
            "User-Agent": cfg["UA"],
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        {"code": grant_code, "kind": 1},
        timeout,
        dry_run,
    )
    if payload.get("code") != 0:
        raise SafeError(
            "获取凭据失败：{}".format(display(payload.get("message") or "未知错误"))
        )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SafeError("凭据响应格式异常")
    cred = data.get("cred")
    sign_token = data.get("token")
    if not isinstance(cred, str) or not cred or not isinstance(sign_token, str) or not sign_token:
        raise SafeError("凭据响应缺少 cred 或 token")
    identity = ""
    for key in ("nickName", "nickname", "username", "displayName", "uid"):
        if data.get(key) is not None and str(data.get(key)).strip():
            identity = display(data[key])
            break
    user = data.get("user")
    if not identity and isinstance(user, dict):
        for key in ("nickname", "nickName", "username", "uid"):
            if user.get(key) is not None and str(user.get(key)).strip():
                identity = display(user[key])
                break
    return cred, sign_token, identity


def signed_headers(
    cfg: Dict[str, str],
    cred: str,
    sign_token: str,
    url: str,
    body: str,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    path = urlparse.urlparse(url).path
    sign, sign_header = generate_sign(sign_token, path, body)
    headers = {
        "cred": cred,
        "platform": PLATFORM,
        "vName": VNAME,
        "timestamp": sign_header["timestamp"],
        "dId": "",
        "sign": sign,
        "User-Agent": cfg["UA"],
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
        "referer": cfg["REFERER"],
        "origin": cfg["ORIGIN"],
    }
    if extra:
        headers.update(extra)
    return headers


def list_endfield_roles(
    cred: str, sign_token: str, cfg: Dict[str, str], timeout: float, dry_run: bool
) -> List[dict]:
    headers = signed_headers(cfg, cred, sign_token, cfg["BIND_URL"], "")
    payload = http_json("GET", cfg["BIND_URL"], headers, None, timeout, dry_run)
    if payload.get("code") != 0:
        raise SafeError(
            "获取角色失败：{}".format(display(payload.get("message") or "未知错误"))
        )
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("list"), list):
        raise SafeError("角色列表格式异常")
    roles: List[dict] = []
    for app in data["list"]:
        if not isinstance(app, dict):
            continue
        if app.get("appCode") != "endfield":
            continue
        binding_list = app.get("bindingList")
        if not isinstance(binding_list, list):
            raise SafeError("终末地绑定列表格式异常")
        for binding in binding_list:
            if not isinstance(binding, dict):
                raise SafeError("终末地绑定数据格式异常")
            role_items = binding.get("roles")
            if isinstance(role_items, list) and role_items:
                for role in role_items:
                    if not isinstance(role, dict):
                        raise SafeError("终末地角色数据格式异常")
                    roles.append(role)
                continue
            default_role = binding.get("defaultRole")
            if isinstance(default_role, dict):
                roles.append(default_role)
                continue
            # 部分响应把角色字段直接放在 bindingList 项上
            if binding.get("roleId") and binding.get("serverId"):
                roles.append(binding)
    if not roles:
        raise SafeError("未绑定终末地角色")
    return roles


def format_awards(data: dict) -> str:
    award_ids = data.get("awardIds")
    resource_map = data.get("resourceInfoMap")
    if not isinstance(award_ids, list) or not isinstance(resource_map, dict):
        return "无额外奖励"
    parts: List[str] = []
    for award in award_ids:
        if not isinstance(award, dict):
            continue
        award_id = award.get("id")
        if award_id is None:
            continue
        item = resource_map.get(str(award_id))
        if item is None:
            item = resource_map.get(award_id)
        if not isinstance(item, dict):
            continue
        name = display(item.get("name") or "未知物品")
        count = item.get("count", 1)
        parts.append("{} x{}".format(name, display(count)))
    return ", ".join(parts) if parts else "无额外奖励"


def do_sign_role(
    role: dict,
    cred: str,
    sign_token: str,
    cfg: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> Tuple[str, str]:
    role_id = role.get("roleId")
    server_id = role.get("serverId")
    if not role_id or not server_id:
        raise SafeError("终末地角色缺少角色或服务器标识")
    nickname = (
        role.get("nickname")
        or role.get("nickName")
        or role.get("roleName")
        or role_id
    )
    channel = role.get("serverName") or role.get("channelName") or server_id
    identity = "{}({}) UID={}".format(display(nickname), display(channel), display(role_id))
    role_header = "3_{}_{}".format(role_id, server_id)
    headers = signed_headers(
        cfg,
        cred,
        sign_token,
        cfg["SIGN_URL"],
        "",
        {"sk-game-role": role_header, "sk-language": "zh-CN"},
    )
    payload = http_json("POST", cfg["SIGN_URL"], headers, None, timeout, dry_run)
    code = payload.get("code")
    message = display(payload.get("message") or "")
    if code == 0:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SafeError("签到响应缺少数据")
        reward = format_awards(data)
        return "success", "{} 签到成功，奖励：{}".format(identity, reward)
    if "请勿重复签到" in message or "do not sign in again" in message.lower():
        return "alreadyComplete", "{} 今日已签到".format(identity)
    raise SafeError("{} 签到失败：{}".format(identity, message or "未知错误"))


class AccountRunner:
    def __init__(self, index: int, region_label: str) -> None:
        self.index = index
        self.region_label = region_label
        self.identity = "账号{}".format(index)
        self.status = "failure"
        self.stats = {key: 0 for key in STATES}
        self.details: List[str] = []
        self.started = time.monotonic()
        self.stage_no = 0

    def set_identity(self, value: str) -> None:
        text = display(value)
        if text:
            self.identity = text

    def display_name(self) -> str:
        return "{}·{}".format(self.region_label, self.identity)

    def stage(self, name: str, func) -> Any:
        self.stage_no += 1
        started = time.monotonic()
        log(
            "账号 {} 阶段 {} {}：开始".format(
                self.display_name(), self.stage_no, name
            )
        )
        try:
            result = func()
            state = "success"
            detail = ""
            if isinstance(result, tuple) and len(result) >= 2:
                state, detail = result[0], result[1]
            elif isinstance(result, str):
                detail = result
            icon = ICONS.get(state, ICONS["success"])
            self.stats[state if state in self.stats else "success"] += 1
            text = detail or name + "完成"
            self.details.append(
                "{} 阶段{} {}：{}".format(icon, self.stage_no, name, text)
            )
            log(
                "账号 {} 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.display_name(),
                    self.stage_no,
                    name,
                    icon,
                    text,
                    time.monotonic() - started,
                )
            )
            return result
        except SafeError as error:
            self.stats["failure"] += 1
            self.details.append(
                "{} 阶段{} {}：{}".format(
                    ICONS["failure"], self.stage_no, name, str(error)
                )
            )
            log(
                "账号 {} 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.display_name(),
                    self.stage_no,
                    name,
                    ICONS["failure"],
                    str(error),
                    time.monotonic() - started,
                )
            )
            raise

    def finish(self) -> Dict[str, Any]:
        elapsed = round(time.monotonic() - self.started, 2)
        if self.stats["failure"]:
            self.status = "failure"
        elif self.status not in ("success", "alreadyComplete", "dry-run"):
            if self.stats["alreadyComplete"] and not self.stats["success"]:
                self.status = "alreadyComplete"
            elif self.stats["success"] or self.stats["alreadyComplete"]:
                self.status = "success"
        log(
            "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f} 秒，状态 {}".format(
                self.display_name(),
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                elapsed,
                self.status,
            )
        )
        return {
            "account": self.index,
            "identity": self.display_name(),
            "region": self.region_label,
            "status": self.status,
            **self.stats,
            "details": self.details,
            "elapsedSeconds": elapsed,
        }


def run_account(
    runner: AccountRunner, account: Dict[str, str], timeout: float, dry_run: bool
) -> None:
    region = account["region"]
    cfg = SERVERS[region]
    token = account["token"]

    if dry_run:
        def cfg_stage():
            for key in (
                "APP_CODE",
                "GRANT_URL",
                "CRED_URL",
                "BIND_URL",
                "SIGN_URL",
            ):
                if not cfg.get(key):
                    raise SafeError("区域配置缺失：" + key)
            if len(token) < 8:
                raise SafeError("Token 过短，疑似未配置")
            return "success", "{} 配置有效；Token 长度 {}".format(
                cfg["name"], len(token)
            )

        runner.stage("参数与区域配置预演", cfg_stage)

        def sign_stage():
            sign, header = generate_sign("dry-signing-key", "/web/v1/game/endfield/attendance", "")
            if len(sign) != 32 or header.get("platform") != PLATFORM:
                raise SafeError("离线请求签名格式异常")
            return "success", "请求签名构造通过；未发送业务请求"

        runner.stage("签到签名预演", sign_stage)
        runner.status = "dry-run"
        log("账号 {}：DRY_RUN_OK，仅验证配置与签名，未联网".format(runner.display_name()))
        return

    def login_stage():
        grant = get_grant_code(token, cfg, timeout, dry_run)
        cred, sign_token, identity = get_cred(grant, cfg, timeout, dry_run)
        if identity:
            runner.set_identity(identity)
            log("账号 {} 身份：{}".format(runner.display_name(), identity))
        return "success", "登录成功", (cred, sign_token)

    login_result = runner.stage("登录{}".format(cfg["name"]), login_stage)
    cred, sign_token = login_result[2]

    def bind_stage():
        roles = list_endfield_roles(cred, sign_token, cfg, timeout, dry_run)
        names = []
        for role in roles:
            nick = role.get("nickname") or role.get("nickName") or role.get("roleId")
            names.append(display(nick))
        return (
            "success",
            "找到 {} 个终末地角色：{}".format(len(roles), ", ".join(names)),
            roles,
        )

    bind_result = runner.stage("查询终末地绑定角色", bind_stage)
    roles = bind_result[2]

    any_ok = False
    any_fail = False
    for index, role in enumerate(roles, 1):
        nick = role.get("nickname") or role.get("nickName") or role.get("roleId") or index
        try:
            state_detail = runner.stage(
                "角色 {} 签到".format(display(nick)),
                lambda r=role: do_sign_role(r, cred, sign_token, cfg, timeout, dry_run),
            )
            if state_detail[0] in ("success", "alreadyComplete"):
                any_ok = True
        except SafeError:
            any_fail = True
            continue
    if any_fail:
        runner.status = "failure"
        raise SafeError("存在角色签到失败")
    if not any_ok:
        runner.status = "failure"
        raise SafeError("未验证到任何角色签到成功")
    if runner.stats["alreadyComplete"] and not runner.stats["success"]:
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
    script = os.path.basename(__file__)
    identities = {
        CATALOG_ID,
        script,
        "endfield_signin.py",
        "candidate.py",
        "scripts/endfield_signin.py",
        "Endfield_auto_signin.py",
    }
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
    from pathlib import Path

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
    dry_setting = env("ENDFIELD_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("ENDFIELD_DRY_RUN 配置无效")
        timeout = resolve_timeout()
        accounts_data = collect_accounts()
        if not accounts_data:
            raise SafeError(
                "未配置账号；请设置 ENDFIELD_ACCOUNTS（region|token，每行一个），"
                "或兼容填写 SKYLAND_TOKEN / SKPORT_TOKEN（每行一个 Token）"
            )
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    records: List[Dict[str, Any]] = []
    runners: List[AccountRunner] = []
    if config_error is None:
        for number, item in enumerate(accounts_data, 1):
            runner = AccountRunner(number, item["label"])
            runners.append(runner)
            try:
                run_account(runner, item, timeout, dry_run)
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log(
                    "账号 {}：❌ 未预期的本地错误，详情已抑制".format(
                        runner.display_name()
                    )
                )
            finally:
                records.append(runner.finish())

    account_total = len(accounts_data)
    counts = {
        "success": sum(r["status"] == "success" for r in records),
        "alreadyComplete": sum(r["status"] == "alreadyComplete" for r in records),
        "failure": sum(r["status"] == "failure" for r in records),
        "dry-run": sum(r["status"] == "dry-run" for r in records),
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
    tasks = {key: sum(r.get(key, 0) for r in records) for key in STATES}
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
    for record in records:
        body += "\n账号 {}：{}".format(record.get("identity"), record.get("status"))
        for detail in record.get("details") or []:
            body += "\n  " + detail

    log("阶段 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log(
        "阶段 通知：结束（{:.2f}秒）".format(
            time.monotonic() - notification_started
        )
    )

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
                "catalogId": CATALOG_ID,
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
