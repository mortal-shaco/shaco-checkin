# -*- coding: utf-8 -*-
# name: EMOS 每日签到
# cron: 30 8 * * *
# SPDX-License-Identifier: MIT
# 来源：xlzs001/emos-loon-sign，python/emos_sign.py（MIT）
# https://github.com/xlzs001/emos-loon-sign
# 保留上游原始说明：混淆产物 · 源码不在本仓库，请勿手改
# 本维护版已展开实现；上面的说明仅保留为上游归属记录。
"""EMOS 独立签到任务（仅使用 Python 标准库）。

登录 https://emos.best，在浏览器开发者工具的网络面板中查看本人
/api/sign/check 或 /api/user 请求的 Authorization 请求头，复制 Bearer 后的完整
Token，保存到青龙环境变量 EMOS_TOKENS；每个非空行一个账号。不要分享抓包。
兼容单个/换行多账号变量 EMOS_TOKEN，EMOS_TOKENS 非空时优先。
EMOS_DRY_RUN=1：完全断网预演，凭据仅做本地格式检查，不声明真实签到成功。
EMOS_BASE：可选的首选地址，仅接受 https://emos.best 或 https://api.emos.best。
EMOS_LOCAL_TEXT：一言不可用时的本地签到文案（默认随机选择上游签到短句）。
QINGLONG_NOTIFY=auto/1/0：按选择列表通知/强制通知/关闭通知。
QINGLONG_NOTIFY_SCRIPTS：逗号、分号或空白分隔的目录相对路径、文件名通配符或
目录编号；设置为空则关闭自动选择，* 选择全部。默认未列入通知名单。
QINGLONG_NOTIFY_DIR：可选的青龙 notify.py 或 sendNotify.js 所在目录。
预演通知也调用可用的通知适配器，但在子进程中阻止联网和启动外部进程；
投递不可用或被阻止只记通知失败，不改变业务退出码。
上游未声明 cron；本版提供每天 08:30 的建议，可在青龙中按需修改。
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
        _ql_notify_identities = ('8aba65e222e7eb74', 'scripts/emos_sign.py', 'emos_sign.py', 'emos_sign')
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
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


TITLE = "EMOS 每日签到"
CATALOG_ID = "8aba65e222e7eb74"
BASES = ("https://emos.best", "https://api.emos.best")
USER_AGENT = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
              "Mobile/15E148 Safari/604.1")
LOCAL_TEXTS = (
    "签到", "打卡", "今日份到", "来签个到", "顺手签到", "准点冒泡", "今天也在",
    "醒来签到", "梦里签到", "路过一下", "悄悄签到", "照常营业", "保持热爱",
    "平安喜乐", "万事顺意", "元气在线", "好运敲门", "认真生活", "慢慢变好",
    "继续发光", "今日达成", "任务完成", "签到打卡", "我又来了",
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {"success": "✅", "alreadyComplete": "☑️", "skipped": "⏭️", "failure": "❌"}


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def log(text):
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def clean_identity(value, tokens):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    value = str(value)
    if any(token and token in value for token in tokens):
        return ""
    # 非凭据公开名称完整保留；手机号和控制字符不能进入日志。
    value = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", value)
    return "".join(c if c.isprintable() else " " for c in value)


def valid_token(token):
    # 单行只有一个不透明 Token，不猜测或拆分其内部字段。
    return bool(token) and not any(c.isspace() or ord(c) < 32 or ord(c) > 126 for c in token) \
        and not any(c in token for c in ",;")


def get_bases():
    configured = os.environ.get("EMOS_BASE", "").strip().rstrip("/")
    if configured and configured not in BASES:
        raise SafeError("EMOS_BASE 仅允许已知的两个 HTTPS 服务域名，避免向其他地址发送凭据")
    return tuple(dict.fromkeys(((configured,) if configured else ()) + BASES))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 禁止携带 Authorization 跟随跳转，也禁止文本供应商跳转至非 HTTPS 地址。
        return None


class Http:
    def __init__(self, bases, dry_run=False):
        self.bases = bases
        self.dry_run = dry_run
        # 不采纳环境代理，避免凭据被不明代理收集；TLS 保持标准库验证。
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, url, method="GET", token=None, timeout=20, limit=65536):
        if self.dry_run:
            raise SafeError("断网预演禁止 HTTP 请求")
        headers = {"Accept": "application/json, text/plain, */*", "User-Agent": USER_AGENT}
        if token is not None:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme != "https" or parsed.netloc not in ("emos.best", "api.emos.best"):
                raise SafeError("拒绝向非可信地址发送凭据")
            headers.update({"Authorization": "Bearer " + token, "Referer": "https://emos.best/"})
        request = urllib.request.Request(url, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                status, raw = response.status, response.read(limit + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            # 不读取错误页：服务端可能回显凭据或其他隐私。
            error.close()
            return status, None
        except Exception:
            raise SafeError("网络、超时或 TLS 校验失败") from None
        if len(raw) > limit:
            raise SafeError("响应超过大小限制")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            payload = None
        return status, payload

    def api(self, method, path, token):
        for index, base in enumerate(self.bases):
            try:
                return self.request(base + path, method=method, token=token)
            except SafeError:
                if method != "GET" or index == len(self.bases) - 1:
                    # 写请求结果不确定时不能盲目重放，调用者随后跨域名复核状态。
                    raise
                log("备用域名：主域名读取失败，尝试下一可信域名")
        raise SafeError("所有可信域名均不可用")


def checked_state(http, token):
    status, payload = http.api("GET", "/api/sign/check", token)
    if status in (401, 403):
        raise SafeError("凭据无效或没有访问权限，请重新获取 Token")
    if status != 200:
        raise SafeError("签到状态查询失败（HTTP {}）".format(status))
    if not isinstance(payload, dict) or type(payload.get("is_sign")) is not bool:
        raise SafeError("签到状态响应缺少布尔字段 is_sign，停止写入")
    if payload.get("success") is False or payload.get("error"):
        raise SafeError("签到状态接口返回业务失败，停止写入")
    return payload["is_sign"]


def published_text(http):
    """一言供应商使用独立、无凭据的请求；所有声明的异常均回退本地。"""
    fallback = " ".join(os.environ.get("EMOS_LOCAL_TEXT", "").split())
    if not fallback or len(fallback) > 280:
        fallback = random.choice(LOCAL_TEXTS)
    try:
        status, payload = http.request("https://v1.hitokoto.cn/?encode=json", timeout=8, limit=16384)
        if status != 200 or not isinstance(payload, dict):
            raise SafeError("文案接口响应不可用")
        text = payload.get("hitokoto")
        if not isinstance(text, str) or not text.strip():
            raise SafeError("文案缺失")
        text = " ".join(text.split())
        author = payload.get("from_who")
        source = payload.get("from")
        author = " ".join(author.split()) if isinstance(author, str) else ""
        source = " ".join(source.split()) if isinstance(source, str) else ""
        if author and source:
            text += " —— {}《{}》".format(author, source)
        elif source:
            text += " ——《{}》".format(source)
        elif author:
            text += " —— {}".format(author)
        if len(text) > 280:
            raise SafeError("署名后的文案过长")
        return text, "使用一言文案，保留作者和作品署名"
    except Exception:
        return fallback, "一言不可用，使用本地签到文案"


class Account:
    def __init__(self, number):
        self.number = number
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
            log("账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                self.number, number, name, ICONS[state], detail, time.monotonic() - started))

    def skip(self, number, name, reason):
        self.stage(number, name, lambda: ("skipped", reason, None))

    def finish(self):
        log("账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
            self.number, sum(self.stats.values()), self.stats["success"], self.stats["alreadyComplete"],
            self.stats["skipped"], self.stats["failure"], time.monotonic() - self.started, self.status))


def run_account(account, token, tokens, http, dry_run):
    def parameter_check():
        if not valid_token(token):
            raise SafeError("Token 格式错误；每个非空行只填写一个完整 Token，不加 Bearer 前缀")
        return "success", "凭据本地格式检查通过，内容不输出", None

    account.stage(1, "参数检查", parameter_check)
    if dry_run:
        for number, name in ((2, "公开身份查询"), (3, "签到状态查询"),
                             (4, "获取签到文案"), (5, "执行并复核签到")):
            account.skip(number, name, "断网预演：不请求账号、文本供应商或签到接口")
        account.status = "dry-run"
        log("账号 {}：断网预演通过；未验证真实身份、凭据或业务结果".format(account.number))
        return

    def identity():
        try:
            status, payload = http.api("GET", "/api/user", token)
            if status != 200 or not isinstance(payload, dict):
                return "skipped", "公开身份暂不可用，继续独立核验签到", None
            user = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            for key in ("username", "name", "user_id", "nickname", "display_name", "uid"):
                value = clean_identity(user.get(key), tokens)
                if value:
                    return "success", "公开账号身份：" + value, None
            return "skipped", "接口未提供可显示的公开身份，使用账号序号", None
        except SafeError:
            return "skipped", "公开身份查询不可用，继续独立核验签到", None

    account.stage(2, "公开身份查询", identity)

    def check():
        signed = checked_state(http, token)
        return ("alreadyComplete" if signed else "success",
                "今日已签到（已核实）" if signed else "今日尚未签到，允许执行一次签到", signed)

    signed = account.stage(3, "签到状态查询", check)
    if signed:
        account.skip(4, "获取签到文案", "今日已完成，无需文案")
        account.skip(5, "执行并复核签到", "保留已核实状态，不重复写入")
        account.status = "alreadyComplete"
        return

    def content():
        text, detail = published_text(http)
        return "success", detail, text

    text = account.stage(4, "获取签到文案", content)

    def sign():
        payload, status = None, None
        try:
            status, payload = http.api("PUT", "/api/user/sign?content=" + urllib.parse.quote(text, safe=""), token)
        except SafeError:
            log("账号 {}：签到请求结果不确定，不重放写请求，开始只读复核".format(account.number))
        if status in (401, 403):
            raise SafeError("签到凭据无效或没有访问权限")
        if status is not None:
            log("账号 {}：签到请求 HTTP {}；以状态复核确认业务结果".format(account.number, status))
        # 200、409、429 以及异常结果均不能直接算成功；必须重新读取 is_sign。
        if not checked_state(http, token):
            raise SafeError("签到后复核仍未签到；限流、冲突或 HTTP 200 均不能替代业务成功")
        metrics = []
        if status == 200 and isinstance(payload, dict) and payload.get("success") is not False and not payload.get("error"):
            for key, label in (("earn_point", "获得积分"), ("continuous_days", "连续天数"), ("sign_index", "签到排名")):
                value = payload.get(key)
                # 只输出这些预期的数值字段，永不打印任意响应字符串。
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if abs(value) < 10 ** 15:
                        metrics.append("{} {}".format(label, value))
                elif isinstance(value, str) and re.fullmatch(r"\d{1,12}(?:\.\d{1,4})?", value):
                    metrics.append("{} {}".format(label, value))
        detail = "签到成功（已复核）" if status == 200 else "今日已签到（已核实）"
        if metrics:
            detail += "；" + "，".join(metrics)
        return "success" if status == 200 else "alreadyComplete", detail, None

    account.stage(5, "执行并复核签到", sign)
    account.status = "success" if account.stats["alreadyComplete"] == 0 else "alreadyComplete"


# 通知在隔离子进程执行，抑制第三方适配器的输出及异常细节。
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
    identities = {CATALOG_ID, script.name, "emos_sign.py", "candidate.py", "python/emos_sign.py"}
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
    enabled = any(selector and any(fnmatch.fnmatchcase(identity, selector) for identity in identities)
                  for selector in selectors)
    return enabled, "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"


def notify(body, dry_run):
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    specification = {"title": TITLE, "body": body, "dry_run": dry_run,
                     "directory": str(Path(__file__).resolve().parent), "path": None}
    paths = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        paths.append(Path(directory).expanduser())
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    adapters = [("python", None)]
    adapters.extend(("python", directory / "notify.py") for directory in paths if (directory / "notify.py").is_file())
    node = shutil.which("node")
    if node:
        adapters.extend(("javascript", directory / "sendNotify.js") for directory in paths if (directory / "sendNotify.js").is_file())
    for kind, path in adapters:
        specification["path"] = str(path.resolve()) if path is not None else None
        command = [sys.executable, "-c", PY_NOTIFY_RUNNER] if kind == "python" else [node, "-e", JS_NOTIFY_RUNNER]
        try:
            result = subprocess.run(command, input=json.dumps(specification, ensure_ascii=False), text=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
            if result.returncode == 0:
                log("通知：✅ 脱敏总结已交给青龙适配器" + ("（断网保护启用）" if dry_run else ""))
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用、投递失败或被断网保护阻止；保留业务退出码")
    return "unavailable-or-failed"


def main():
    started = time.monotonic()
    started_at = clock()
    raw = os.environ.get("EMOS_TOKENS", "")
    if not raw.strip():
        raw = os.environ.get("EMOS_TOKEN", "")
    tokens = [line.strip() for line in raw.splitlines() if line.strip()]
    dry_setting = os.environ.get("EMOS_DRY_RUN", "0").strip().lower()
    dry_run = dry_setting in TRUE_VALUES
    log("========== {} ==========".format(TITLE))
    log("开始时间：{}；运行模式：{}；账号数：{}".format(started_at, "断网预演" if dry_run else "真实执行", len(tokens)))
    accounts = []
    config_error = None
    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES:
            raise SafeError("EMOS_DRY_RUN 配置无效，停止执行")
        if not tokens:
            raise SafeError("未配置 EMOS_TOKENS，请在青龙环境变量中按每个非空行一个账号填写 Token")
        http = Http(get_bases(), dry_run=dry_run)
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)
    if config_error is None:
        for number, token in enumerate(tokens, 1):
            account = Account(number)
            accounts.append(account)
            try:
                run_account(account, token, tokens, http, dry_run)
            except SafeError:
                # 阶段日志已有脱敏原因；不影响后续账号。
                account.status = "failure"
            except Exception:
                account.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                account.finish()
            if not dry_run and number != len(tokens):
                time.sleep(1)
    counts = {state: sum(a.status == state for a in accounts)
              for state in ("success", "alreadyComplete", "failure", "dry-run")}
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = len(tokens) if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    status = ("configuration-error" if config_error else "partial-failure" if failed and (succeeded or counts["dry-run"])
              else "failure" if failed else "dry-run" if dry_run else "success")
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
    body = "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
        status, len(tokens), succeeded, failed, counts["dry-run"], "是" if config_error else "否")
    log("阶段 6 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log("阶段 6 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started))
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log("任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
        len(tokens), succeeded, counts["alreadyComplete"], failed, counts["dry-run"]))
    log("子任务统计：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
        sum(tasks.values()), tasks["success"], tasks["alreadyComplete"], tasks["skipped"], tasks["failure"]))
    log("完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态 {}".format(finished_at, elapsed, notification, status))
    print("TASK_SUMMARY=" + json.dumps({
        "task": TITLE, "mode": "dry-run" if dry_run else "live", "status": status,
        "accounts": len(tokens), "success": succeeded, "alreadyComplete": counts["alreadyComplete"],
        "failure": failed, "dryRun": counts["dry-run"], "configurationError": bool(config_error),
        "tasks": tasks, "notification": notification, "startTime": started_at, "finishTime": finished_at,
        "durationSeconds": elapsed, "exitCode": exit_code,
    }, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
