#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: ViewTurbo 每日签到
# cron: 10 8 * * *
#
# 来源：heibais1986/turboview turbo.py（MIT）
# https://github.com/heibais1986/turboview
# 提交：7334d28739ae238cd865b401b27ab3eb4b6a34f3
#
# MIT License
#
# Copyright (c) 2026 heibais1986
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
"""ViewTurbo（TurboView / vtpro）每日签到 - 青龙维护版。

功能清点（相对上游 turbo.py）：
- 使用邮箱与明文密码登录 api.viewturbo.com（密码按上游规则本地 MD5 后提交）
- 调用 /appuser/checkin 完成每日签到，并按业务 msg 核验成功或今日已签到
- 调用 /appuser/userinfo 读取剩余流量（字节转 MB）便于核对
- 统一多账号为 TURBOVIEW_ACCOUNTS 每行 邮箱|密码；兼容上游 USER{n}/PASS{n}
- 移除 Telegram 直连、原始响应/Token/密码打印与无超时请求
- 增加 TURBOVIEW_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

TURBOVIEW_ACCOUNTS：每个非空行一个账号，格式 邮箱|密码；仅在第一个竖线处分割。
TURBOVIEW_DOMAIN：可选 API 根地址，默认 https://api.viewturbo.com。
TURBOVIEW_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
TURBOVIEW_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求。
建议 Cron：1 8 * * *（对齐上游 Actions 的 UTC 0:01）。不打印密码、Token 或原始响应。
"""
from __future__ import annotations

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
        _ql_notify_identities = ('406081527220e412', 'scripts/turbo.py', 'turbo.py', 'turbo')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

TITLE = "ViewTurbo 每日签到"
CATALOG_ID = "406081527220e412"
DEFAULT_DOMAIN = "https://api.viewturbo.com"
WEB_ORIGIN = "https://web.vtpro.xyz"
DEFAULT_TIMEOUT = 15
MAX_BYTES = 1024 * 1024
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
ALREADY_HINTS = (
    "今日已签到",
    "已经签到",
    "已签到",
    "重复签到",
    "请勿重复",
    "already",
)
IDENTITY_KEYS = (
    "nickname",
    "nickName",
    "nick",
    "username",
    "userName",
    "name",
    "display_name",
    "displayName",
    "email",
    "uid",
    "id",
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def resolve_timeout() -> float:
    raw = env("TURBOVIEW_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("TURBOVIEW_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("TURBOVIEW_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_domain() -> str:
    raw = env("TURBOVIEW_DOMAIN") or DEFAULT_DOMAIN
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SafeError("TURBOVIEW_DOMAIN 须为 https:// 开头的 API 根地址")
    if parsed.path not in ("", "/"):
        raise SafeError("TURBOVIEW_DOMAIN 仅填写 API 根地址，不要带业务路径")
    return "{}://{}".format(parsed.scheme, parsed.netloc)


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 邮箱|密码")
    email, password = text.split("|", 1)
    email = email.strip()
    password = password.strip()
    if not email or not password:
        raise SafeError("邮箱或密码为空")
    if any(ord(ch) < 32 for ch in email) or any(ord(ch) < 32 for ch in password):
        raise SafeError("账号行含控制字符")
    if "@" not in email:
        raise SafeError("邮箱格式无效：缺少 @")
    return {"email": email, "password": password}


def load_accounts() -> List[Dict[str, str]]:
    raw = env("TURBOVIEW_ACCOUNTS")
    accounts: List[Dict[str, str]] = []
    if raw:
        for line in raw.replace("\r\n", "\n").splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            accounts.append(parse_account_line(text))
        if not accounts:
            raise SafeError("TURBOVIEW_ACCOUNTS 中没有有效账号行")
        log("凭据来源：TURBOVIEW_ACCOUNTS")
        return accounts

    index = 1
    while True:
        user = env("USER{}".format(index))
        password = env("PASS{}".format(index))
        if not user and not password:
            break
        if not user or not password:
            raise SafeError(
                "兼容凭据 USER{0}/PASS{0} 不完整，请成对填写或改用 TURBOVIEW_ACCOUNTS".format(
                    index
                )
            )
        if "|" in user:
            raise SafeError(
                "兼容凭据 USER{} 不应包含字段分隔符；请改用 TURBOVIEW_ACCOUNTS".format(
                    index
                )
            )
        accounts.append(parse_account_line("{}|{}".format(user, password)))
        index += 1

    if not accounts:
        raise SafeError(
            "未配置凭据：请设置 TURBOVIEW_ACCOUNTS（每行 邮箱|密码）；"
            "兼容上游 USER1/PASS1、USER2/PASS2…"
        )
    log("凭据来源：USER{n}/PASS{n}（兼容模式）")
    return accounts


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("msg", "message", "error", "errorMessage", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    return ""


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates: List[Any] = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.append(data)
        for nested_key in ("user", "userInfo", "profile", "account"):
            nested = data.get(nested_key)
            if isinstance(nested, dict):
                candidates.append(nested)
    for mapping in candidates:
        if not isinstance(mapping, dict):
            continue
        for key in IDENTITY_KEYS:
            value = mapping.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                text = compact(value, 64)
                if not text:
                    continue
                lower = key.lower()
                if lower in {"token", "password", "authorization", "cookie"}:
                    continue
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                if lower in {"token"} or "token" in lower:
                    continue
                if len(text) > 80 and re.fullmatch(r"[A-Za-z0-9._\-]+", text):
                    continue
                return text
    return ""


def classify_checkin(payload: Any) -> Tuple[str, str]:
    if not isinstance(payload, dict):
        return "failure", "签到响应不是可解析的业务对象"
    message = business_message(payload)
    if message == "成功":
        return "success", "签到成功"
    lowered = message.lower()
    for hint in ALREADY_HINTS:
        if hint.lower() in lowered:
            return "alreadyComplete", "今日已签到（{}）".format(message or hint)
    if message:
        return "failure", "签到业务失败"
    return "failure", "签到业务失败（缺少可核实成功字段）"


def format_transfer_mb(raw: Any) -> Optional[str]:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    mb = round(value / 1024 / 1024, 2)
    return "{:.2f} MB".format(mb)


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""
        self.message = ""
        self.transfer = ""

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


class TurboClient:
    def __init__(self, domain: str, timeout: float) -> None:
        self.domain = domain.rstrip("/")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/json",
            "origin": WEB_ORIGIN,
            "referer": WEB_ORIGIN + "/",
            "user-agent": UA,
        }

    def _params(self, token: str = "") -> Dict[str, str]:
        return {
            "platform": "web",
            "cur_version": "0.0.0",
            "token": token,
            "deviceinfo": "",
            "lang": "hk",
            "code": "Others",
        }

    def request_json(
        self,
        path: str,
        *,
        method: str = "POST",
        payload: Optional[Dict[str, Any]] = None,
        token: str = "",
        empty_body: bool = False,
    ) -> Tuple[int, Any]:
        query = urllib.parse.urlencode(self._params(token))
        url = "{}/{}?{}".format(self.domain, path.lstrip("/"), query)
        body = None
        headers = self._headers()
        if empty_body:
            body = b"{}"
        elif payload is not None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
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


def do_login(client: TurboClient, email: str, password: str) -> Tuple[str, str]:
    password_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
    status, result = client.request_json(
        "appuser/reglogin",
        method="POST",
        payload={"email": email, "password": password_md5},
    )
    if status in (401, 403):
        raise SafeError("登录凭据无效或没有访问权限")
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("登录响应无法解析")
    message = business_message(result)
    if message != "成功":
        if any(word in message for word in ("密码", "账号", "邮箱", "用户", "登录", "凭证")):
            raise SafeError("登录业务失败（账号或密码可能无效）")
        raise SafeError("登录业务失败")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise SafeError("登录成功但未返回会话令牌")
    identity = extract_identity(result)
    return token.strip(), identity


def do_checkin(client: TurboClient, token: str) -> Tuple[str, str]:
    status, result = client.request_json(
        "appuser/checkin",
        method="POST",
        token=token,
        empty_body=True,
    )
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    state, detail = classify_checkin(result)
    if state == "failure":
        raise SafeError(detail)
    return state, detail


def do_userinfo(client: TurboClient, token: str) -> Tuple[str, str]:
    status, result = client.request_json(
        "appuser/userinfo",
        method="GET",
        token=token,
    )
    if status in (401, 403):
        raise SafeError("用户信息凭据无效或会话已过期")
    if status != 200:
        raise SafeError("用户信息请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("用户信息响应无法解析")
    message = business_message(result)
    if message and message != "成功":
        raise SafeError("用户信息业务失败")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    transfer = format_transfer_mb(data.get("transfer") if isinstance(data, dict) else None)
    if transfer is None:
        raise SafeError("用户信息未返回可解析的剩余流量")
    identity = extract_identity(result)
    return transfer, identity


def run_account(
    runner: AccountRunner,
    email: str,
    password: str,
    domain: str,
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        return "success", "凭据本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "登录获取会话", "断网预演：不请求登录接口")
        runner.skip(3, "提交每日签到", "断网预演：不请求签到接口")
        runner.skip(4, "读取剩余流量", "断网预演：不请求用户信息")
        runner.status = "dry-run"
        log("账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display()))
        return

    client = TurboClient(domain, timeout)
    token_box: Dict[str, str] = {}

    def login_stage():
        token, identity = do_login(client, email, password)
        token_box["token"] = token
        if identity:
            runner.identity = identity
            return "success", "登录成功；公开身份：{}".format(identity), token
        return "success", "登录成功（会话令牌不输出）", token

    runner.stage(2, "登录获取会话", login_stage)

    def checkin_stage():
        state, detail = do_checkin(client, token_box["token"])
        runner.message = detail
        return state, detail, None

    runner.stage(3, "提交每日签到", checkin_stage)

    def userinfo_stage():
        try:
            transfer, identity = do_userinfo(client, token_box["token"])
            runner.transfer = transfer
            if identity and not runner.identity:
                runner.identity = identity
            detail = "剩余流量 {}".format(transfer)
            if identity:
                detail += "；公开身份：{}".format(identity)
            return "success", detail, transfer
        except SafeError as error:
            # 流量查询为核对能力，失败不回滚已成功签到，但账号记为失败
            return "failure", "剩余流量查询失败（{}）".format(error), None

    info_result = runner.stage(4, "读取剩余流量", userinfo_stage)
    if runner.stats["failure"]:
        runner.status = "failure"
        return
    if runner.stats["alreadyComplete"]:
        runner.status = "alreadyComplete"
    else:
        runner.status = "success"
    if info_result:
        log("账号 {} 剩余流量：{}".format(runner.display(), info_result))


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
        "turboview_checkin.py",
        "candidate.py",
        "scripts/turboview_checkin.py",
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
    if dry_run:
        log("通知：⏭️ 断网预演禁止执行可能联网的通知模块；摘要已生成")
        return "dry-run-skipped"
    paths: List[Path] = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser() / "notify.py")
    paths.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    try:
        module = None
        try:
            import notify as imported  # type: ignore

            module = imported
        except Exception:
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location(
                        "qinglong_notify", path
                    )
                    if spec is None or spec.loader is None:
                        continue
                    candidate = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(candidate)
                    module = candidate
                    break
        if module is not None and callable(getattr(module, "send", None)):
            outcome: List[bool] = []

            def deliver() -> None:
                try:
                    module.send(TITLE, body)
                    outcome.append(True)
                except Exception:
                    outcome.append(False)

            worker = threading.Thread(target=deliver, daemon=True)
            worker.start()
            worker.join(20)
            if outcome and outcome[0]:
                log("通知：✅ 脱敏总结已交给青龙 notify.py")
                return "sent"
            log("通知：⚠️ 投递失败或超时；保留业务退出码")
            return "unavailable-or-failed"
        node = shutil.which("node")
        if node:
            for path in paths:
                js_path = path.with_name("sendNotify.js")
                if not js_path.is_file():
                    continue
                result = subprocess.run(
                    [
                        node,
                        "-e",
                        "Promise.resolve(require(process.argv[1]).sendNotify("
                        "process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                        str(js_path),
                        TITLE,
                        body,
                    ],
                    timeout=20,
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知：✅ 脱敏总结已交给青龙 sendNotify.js")
                    return "sent"
        log("通知：⚠️ 青龙适配器不可用；保留业务退出码")
        return "unavailable-or-failed"
    except Exception:
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
        return "unavailable-or-failed"


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("TURBOVIEW_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    domain = DEFAULT_DOMAIN
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("TURBOVIEW_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        domain = resolve_domain()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；API：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                domain,
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
                    item["email"],
                    item["password"],
                    domain,
                    timeout,
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
        "success": sum(1 for item in accounts if item.status == "success"),
        "alreadyComplete": sum(
            1 for item in accounts if item.status == "alreadyComplete"
        ),
        "failure": sum(1 for item in accounts if item.status == "failure"),
        "dry-run": sum(1 for item in accounts if item.status == "dry-run"),
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
    tasks = {key: sum(item.stats[key] for item in accounts) for key in STATES}
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
    final_label = {
        "success": "SUCCESS",
        "partial-failure": "PARTIAL_FAILURE",
        "failure": "FAILURE",
        "configuration-error": "CONFIG_ERROR",
        "dry-run": "DRY-RUN",
    }.get(status, status.upper())
    log("最终状态：{}".format(final_label))
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
