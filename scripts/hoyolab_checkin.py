#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: HoYoLAB 多游戏每日签到
# cron: 25 8 * * *
# SPDX-License-Identifier: MIT
"""HoYoLAB 国际服多游戏每日签到（仅标准库）。

来源：oratis/gameclaw，gameclaw_skill/scripts/hoyolab_checkin.py；MIT License。
相关参考：同仓 account_status.py（查询已绑定游戏角色公开身份）。

上游能力：原神 / 崩坏：星穹铁道 / 崩坏3 / 绝区零 / 未定事件簿 每日签到；
可按游戏选择或全部签到；可只查询签到信息；凭据为 ltoken_v2 + ltuid_v2。
本维护版合并角色公开身份查询，转为青龙可调度独立任务：多账号、完全断网
预演、超时、业务成功判定、时间轴日志、TASK_SUMMARY 与青龙通知。

HOYOLAB_ACCOUNTS：每个非空行一个账号。推荐 Cookie 片段：
ltoken_v2=...; ltuid_v2=...
也支持「ltuid|ltoken」，仅在第一个竖线处拆分以保留 token 中的竖线。
浏览器登录 https://www.hoyolab.com ，开发者工具 → Application → Cookies
复制 ltoken_v2 与 ltuid_v2。不要把 Cookie 发给他人或写入公开仓库。
兼容单账号别名：当 HOYOLAB_ACCOUNTS 为空时，可读 LTOKEN_V2 + LTUID_V2。
HOYOLAB_GAMES：逗号分隔游戏代号或 all；默认 all。
可选：genshin,starrail,honkai3rd,zzz,tears
HOYOLAB_INFO_ONLY=1：仅查询签到信息，不提交签到。
HOYOLAB_TIMEOUT：单次请求超时秒数，默认 30，范围 5..120。
HOYOLAB_DRY_RUN=1：完全断网预演，只校验配置，不声明业务成功。
QINGLONG_NOTIFY=auto/1/0；QINGLONG_NOTIFY_SCRIPTS 与 QINGLONG_NOTIFY_DIR 见契约。
上游未声明 cron；本版建议每天 08:25。不打印 Cookie、Token 或原始响应。

MIT License

Copyright (c) oratis/gameclaw contributors

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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "a79010908be3c115",
            "scripts/hoyolab_checkin.py",
            "hoyolab_checkin.py",
            "candidate.py",
            "hoyolab_checkin",
        )
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
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TITLE = "HoYoLAB 多游戏每日签到"
CATALOG_ID = "a79010908be3c115"
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
MAX_RESPONSE_BYTES = 1024 * 1024
GAME_ROLES_URL = "https://api-os-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie"

GAMES = {
    "genshin": {
        "name": "原神",
        "act_id": "e202102251931481",
        "sign_url": "https://sg-hk4e-api.hoyolab.com/event/sol/sign",
        "info_url": "https://sg-hk4e-api.hoyolab.com/event/sol/info",
    },
    "starrail": {
        "name": "崩坏：星穹铁道",
        "act_id": "e202303301540311",
        "sign_url": "https://sg-public-api.hoyolab.com/event/luna/os/sign",
        "info_url": "https://sg-public-api.hoyolab.com/event/luna/os/info",
    },
    "honkai3rd": {
        "name": "崩坏3",
        "act_id": "e202110291205111",
        "sign_url": "https://sg-public-api.hoyolab.com/event/mani/sign",
        "info_url": "https://sg-public-api.hoyolab.com/event/mani/info",
    },
    "zzz": {
        "name": "绝区零",
        "act_id": "e202406031448091",
        "sign_url": "https://sg-act-nap-api.hoyolab.com/event/luna/zzz/os/sign",
        "info_url": "https://sg-act-nap-api.hoyolab.com/event/luna/zzz/os/info",
    },
    "tears": {
        "name": "未定事件簿",
        "act_id": "e202202281857121",
        "sign_url": "https://sg-public-api.hoyolab.com/event/luna/os/sign",
        "info_url": "https://sg-public-api.hoyolab.com/event/luna/os/info",
    },
}

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": "https://act.hoyolab.com",
    "Referer": "https://act.hoyolab.com/",
    "x-rpc-app_version": "2.34.1",
    "x-rpc-client_type": "4",
    "x-rpc-language": "zh-cn",
}


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def log(text):
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def truthy(name):
    return os.environ.get(name, "").strip().lower() in TRUE_VALUES


def redact_text(value, secrets):
    text = str(value)
    for secret in secrets:
        if secret and secret in text:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return "".join(c if c.isprintable() else " " for c in text)


def clean_identity(value, secrets):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    text = str(value).strip()
    if not text or any(secret and secret in text for secret in secrets):
        return ""
    if re.fullmatch(r"(?i)bearer\s+\S+", text):
        return ""
    return redact_text(text, secrets)


def parse_timeout():
    raw = os.environ.get("HOYOLAB_TIMEOUT", "30").strip() or "30"
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("HOYOLAB_TIMEOUT 必须是整数秒") from exc
    if value < 5 or value > 120:
        raise SafeError("HOYOLAB_TIMEOUT 允许范围 5..120")
    return value


def parse_games():
    raw = os.environ.get("HOYOLAB_GAMES", "all").strip() or "all"
    if raw.lower() == "all":
        return list(GAMES.keys())
    selected = []
    for part in re.split(r"[,;\s]+", raw):
        slug = part.strip().lower()
        if not slug:
            continue
        if slug not in GAMES:
            raise SafeError(
                "未知游戏代号「{}」；可选：{} 或 all".format(
                    slug, ",".join(GAMES.keys())
                )
            )
        if slug not in selected:
            selected.append(slug)
    if not selected:
        raise SafeError("HOYOLAB_GAMES 未指定有效游戏")
    return selected


def parse_cookie_pair(text):
    jar = {}
    for item in text.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        jar[key.strip().lower()] = value.strip()
    ltoken = jar.get("ltoken_v2") or jar.get("ltoken")
    ltuid = jar.get("ltuid_v2") or jar.get("ltuid") or jar.get("account_id_v2") or jar.get("account_id")
    return ltoken, ltuid


def parse_account_line(line, index):
    text = line.strip()
    if not text:
        raise SafeError("账号 {} 为空行".format(index))
    secrets = []
    ltoken = None
    ltuid = None
    if "ltoken" in text.lower() and "=" in text:
        ltoken, ltuid = parse_cookie_pair(text)
    elif "|" in text:
        ltuid, ltoken = text.split("|", 1)
        ltuid = ltuid.strip()
        ltoken = ltoken.strip()
    else:
        raise SafeError(
            "账号 {} 格式错误；请使用 Cookie 片段或「ltuid|ltoken」".format(index)
        )
    if not ltoken or not ltuid:
        raise SafeError("账号 {} 缺少 ltoken_v2 或 ltuid_v2".format(index))
    if not re.fullmatch(r"\d{5,20}", ltuid):
        raise SafeError("账号 {} 的 ltuid 应为数字 UID".format(index))
    if len(ltoken) < 8:
        raise SafeError("账号 {} 的 ltoken 长度异常".format(index))
    secrets.extend([ltoken, ltuid])
    return {"ltoken": ltoken, "ltuid": ltuid, "secrets": secrets}


def load_accounts():
    raw = os.environ.get("HOYOLAB_ACCOUNTS", "")
    lines = [line for line in raw.splitlines() if line.strip()]
    if lines:
        return [parse_account_line(line, index) for index, line in enumerate(lines, 1)]
    ltoken = os.environ.get("LTOKEN_V2", "").strip()
    ltuid = os.environ.get("LTUID_V2", "").strip()
    if ltoken or ltuid:
        if not ltoken or not ltuid:
            raise SafeError("兼容别名需同时提供 LTOKEN_V2 与 LTUID_V2")
        return [parse_account_line("{}|{}".format(ltuid, ltoken), 1)]
    raise SafeError("未配置 HOYOLAB_ACCOUNTS（或兼容别名 LTOKEN_V2+LTUID_V2）")


class OfflineHTTPError(SafeError):
    pass


class HttpClient:
    def __init__(self, timeout, dry_run):
        self.timeout = timeout
        self.dry_run = dry_run

    def request(self, method, url, headers=None, body=None):
        if self.dry_run:
            raise OfflineHTTPError("断网预演禁止发起网络请求")
        data = None
        req_headers = dict(headers or {})
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json;charset=UTF-8")
        request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise SafeError("响应体过大，已中止解析")
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
                status = response.getcode()
        except OfflineHTTPError:
            raise
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES + 1) if exc.fp else b""
            if len(raw) > MAX_RESPONSE_BYTES:
                raise SafeError("HTTP {} 响应体过大".format(exc.code)) from exc
            charset = "utf-8"
            if exc.headers:
                charset = exc.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            status = exc.code
            if status >= 500:
                raise SafeError("HTTP {}".format(status)) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
            raise SafeError("网络请求失败或超时") from exc
        try:
            payload = json.loads(text) if text else {}
        except ValueError as exc:
            raise SafeError("响应不是有效 JSON") from exc
        if not isinstance(payload, dict):
            raise SafeError("响应 JSON 结构异常")
        return status, payload


def cookie_header(ltoken, ltuid):
    return "ltoken_v2={}; ltuid_v2={}".format(ltoken, ltuid)


def build_headers(ltoken, ltuid, with_json=False):
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = cookie_header(ltoken, ltuid)
    if with_json:
        headers["Content-Type"] = "application/json;charset=UTF-8"
    return headers


def fetch_roles(http, ltoken, ltuid, secrets):
    status, payload = http.request(
        "GET", GAME_ROLES_URL, headers=build_headers(ltoken, ltuid)
    )
    retcode = payload.get("retcode")
    if retcode in (-100, -10001):
        raise SafeError("Cookie 无效或已过期（角色查询）")
    if retcode != 0:
        message = payload.get("message") or "retcode={}".format(retcode)
        raise SafeError("查询角色失败：" + redact_text(message, secrets))
    data = payload.get("data") or {}
    roles = data.get("list") or []
    if not isinstance(roles, list):
        return [], ""
    identities = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        nickname = clean_identity(role.get("nickname"), secrets)
        uid = clean_identity(role.get("game_uid"), secrets)
        region = clean_identity(role.get("region_name") or role.get("region"), secrets)
        level = role.get("level")
        parts = []
        if nickname:
            parts.append(nickname)
        if uid:
            parts.append("UID=" + uid)
        if region:
            parts.append(region)
        if isinstance(level, int):
            parts.append("Lv." + str(level))
        if parts:
            identities.append("/".join(parts))
    display = "；".join(identities[:5])
    return roles, display


def get_info(http, game_slug, ltoken, ltuid, secrets):
    game = GAMES[game_slug]
    url = "{}?act_id={}".format(game["info_url"], urllib.parse.quote(game["act_id"]))
    status, payload = http.request("GET", url, headers=build_headers(ltoken, ltuid))
    retcode = payload.get("retcode")
    if retcode in (-100, -10001):
        raise SafeError("Cookie 无效或已过期（{} 信息）".format(game["name"]))
    if retcode != 0:
        message = payload.get("message") or "retcode={}".format(retcode)
        raise SafeError(
            "{} 查询失败：{}".format(game["name"], redact_text(message, secrets))
        )
    data = payload.get("data") or {}
    total = data.get("total_sign_day")
    is_sign = data.get("is_sign")
    today = clean_identity(data.get("today"), secrets)
    return {
        "total_sign_day": total,
        "is_sign": bool(is_sign),
        "today": today,
        "message": "{}：累计 {} 天；今日{}；日期 {}".format(
            game["name"],
            total if total is not None else "?",
            "已签" if is_sign else "未签",
            today or "未知",
        ),
    }


def checkin_game(http, game_slug, ltoken, ltuid, secrets):
    game = GAMES[game_slug]
    url = "{}?act_id={}".format(game["sign_url"], urllib.parse.quote(game["act_id"]))
    status, payload = http.request(
        "POST",
        url,
        headers=build_headers(ltoken, ltuid, with_json=True),
        body={"act_id": game["act_id"]},
    )
    retcode = payload.get("retcode")
    message = redact_text(payload.get("message") or "", secrets)
    if retcode == 0:
        return "success", "{} 签到成功".format(game["name"])
    if retcode == -5003:
        return "alreadyComplete", "{} 今日已签到".format(game["name"])
    if retcode in (-100, -10001):
        raise SafeError("Cookie 无效或已过期（{}）".format(game["name"]))
    if retcode in (-1002, -1071):
        raise SafeError("{} 触发频率限制，请稍后重试".format(game["name"]))
    raise SafeError(
        "{} 签到失败：{}".format(game["name"], message or "retcode={}".format(retcode))
    )


class AccountRunner:
    def __init__(self, number):
        self.number = number
        self.identity = ""
        self.status = "failure"
        self.stats = {key: 0 for key in STATES}
        self.started = time.monotonic()

    def stage(self, number, name, func):
        log("账号 {} · 阶段 {} {}：开始".format(self.number, number, name))
        started = time.monotonic()
        try:
            state, detail, extra = func()
        except SafeError as error:
            self.stats["failure"] += 1
            log(
                "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.number,
                    number,
                    name,
                    ICONS["failure"],
                    str(error),
                    time.monotonic() - started,
                )
            )
            raise
        icon = ICONS.get(state, ICONS["success"])
        self.stats[state] = self.stats.get(state, 0) + 1
        log(
            "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                self.number,
                number,
                name,
                icon,
                detail,
                time.monotonic() - started,
            )
        )
        return extra

    def skip(self, number, name, reason):
        self.stats["skipped"] += 1
        log(
            "账号 {} · 阶段 {} {}：{} {}".format(
                self.number, number, name, ICONS["skipped"], reason
            )
        )

    def finish(self):
        elapsed = round(time.monotonic() - self.started, 2)
        label = self.identity or ("账号{}".format(self.number))
        log(
            "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.number,
                label,
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                elapsed,
                self.status,
            )
        )


def run_account(runner, account, http, dry_run, games, info_only):
    secrets = list(account["secrets"])
    label = "账号{}".format(runner.number)

    def validate():
        return "success", "凭据字段齐全（ltuid 已校验为数字）", None

    runner.stage(1, "校验账号配置", validate)

    if dry_run:
        runner.skip(2, "查询公开角色身份", "断网预演：不请求角色接口")
        for offset, slug in enumerate(games, 3):
            game_name = GAMES[slug]["name"]
            action = "查询签到信息" if info_only else "每日签到"
            runner.skip(
                offset,
                "{}·{}".format(game_name, action),
                "断网预演：不请求 HoYoLAB 接口",
            )
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实身份、凭据或业务结果".format(
                runner.number
            )
        )
        return

    def roles_stage():
        roles, display = fetch_roles(
            http, account["ltoken"], account["ltuid"], secrets
        )
        if display:
            return "success", "公开角色：" + display, display
        return "success", "未返回可显示角色昵称，将使用账号序号", ""

    display = runner.stage(2, "查询公开角色身份", roles_stage)
    if display:
        runner.identity = display

    stage_no = 3
    for slug in games:
        game_name = GAMES[slug]["name"]

        def make_info(current_slug=slug):
            info = get_info(
                http, current_slug, account["ltoken"], account["ltuid"], secrets
            )
            state = "alreadyComplete" if info["is_sign"] else "success"
            return state, info["message"], None

        def make_sign(current_slug=slug):
            state, detail = checkin_game(
                http, current_slug, account["ltoken"], account["ltuid"], secrets
            )
            return state, detail, None

        if info_only:
            runner.stage(stage_no, "{}·查询签到信息".format(game_name), make_info)
        else:
            runner.stage(stage_no, "{}·每日签到".format(game_name), make_sign)
        stage_no += 1
        if slug != games[-1]:
            time.sleep(1.5)

    if runner.stats["failure"]:
        runner.status = "failure"
    elif runner.stats["alreadyComplete"] and not runner.stats["success"]:
        runner.status = "alreadyComplete"
    else:
        runner.status = "success"
    log(
        "账号 {}（{}）：{}".format(
            runner.number,
            runner.identity or label,
            {
                "success": "全部任务成功",
                "alreadyComplete": "今日均已签到/已完成",
                "failure": "存在失败子任务",
            }.get(runner.status, runner.status),
        )
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
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "hoyolab_checkin.py",
        "candidate.py",
        "scripts/hoyolab_checkin.py",
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
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
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
    dry_setting = os.environ.get("HOYOLAB_DRY_RUN", "0").strip().lower()
    dry_run = dry_setting in TRUE_VALUES
    info_only = truthy("HOYOLAB_INFO_ONLY")
    accounts = []
    parsed = []
    games = []
    config_error = None
    log("========== {} ==========".format(TITLE))
    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES and dry_setting != "":
            raise SafeError("HOYOLAB_DRY_RUN 配置无效，停止执行")
        timeout = parse_timeout()
        games = parse_games()
        parsed = load_accounts()
        http = HttpClient(timeout=timeout, dry_run=dry_run)
    except SafeError as error:
        config_error = str(error)
        log(
            "开始时间：{}；运行模式：{}；账号数：0".format(
                started_at, "断网预演" if dry_run else "真实执行"
            )
        )
        log("阶段 0 参数配置：❌ " + config_error)
    else:
        mode = "断网预演" if dry_run else ("仅查询信息" if info_only else "真实签到")
        log(
            "开始时间：{}；运行模式：{}；账号数：{}；游戏：{}".format(
                started_at,
                mode,
                len(parsed),
                ",".join(games),
            )
        )
        for number, account in enumerate(parsed, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(runner, account, http, dry_run, games, info_only)
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(parsed):
                time.sleep(1)

    counts = {
        state: sum(item.status == state for item in accounts)
        for state in ("success", "alreadyComplete", "failure", "dry-run")
    }
    account_total = len(parsed) if not config_error else 0
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    if config_error and not parsed:
        failed = max(failed, 1)
    exit_code = 1 if config_error or failed else 0
    status = (
        "configuration-error"
        if config_error
        else "partial-failure"
        if failed and (succeeded or counts["dry-run"])
        else "failure"
        if failed
        else "dry-run"
        if dry_run
        else "success"
    )
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
    body = "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
        status,
        account_total if not config_error else 0,
        succeeded,
        failed,
        counts["dry-run"],
        "是" if config_error else "否",
    )
    log("阶段 N 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log(
        "阶段 N 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started)
    )
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total if not config_error else 0,
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
    if dry_run and not config_error and failed == 0:
        log("断网预演通过")
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total if not config_error else 0,
                "success": succeeded,
                "alreadyComplete": counts["alreadyComplete"],
                "failure": failed,
                "dryRun": counts["dry-run"],
                "configurationError": bool(config_error),
                "infoOnly": info_only,
                "games": games,
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
