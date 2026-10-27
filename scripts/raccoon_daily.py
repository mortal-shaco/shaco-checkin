#!/usr/bin/env python3
# name: 小浣熊每日积分
# cron: 2 9 * * *
# SPDX-License-Identifier: MIT
# 上游: L0NE-6/Raccoon-Daily, raccoon_daily.py
# 参考: L0NE-6/Raccoon-Daily, raccoon_login.py（凭据获取说明，未合并交互式登录）
"""小浣熊每日积分维护版（Python 3，仅标准库）。

RACCOON_TOKENS：每个非空行一个账号，支持 token、备注|token、备注|token|refresh_token。
支持 Bearer 前缀；每个字段边界仅拆一次，refresh_token 内的后续 | 原样保留。
不使用 & 或 @ 分隔账号。备注仅用于兼容解析，不打印。
在 https://xiaohuanxiong.com 登录后，通过开发者工具网络面板中本站已登录请求的
Authorization 获取 access_token；通过本人登录/续期响应的 data.access_token 与
data.refresh_token 获取配套凭据。也可自行查看官方桌面客户端的本人 auth.json，
复制 access_token/accessToken 和 refresh_token/refreshToken；本脚本不依赖该文件。
凭据只能私下填入青龙，不能复制到日志。access 有效期约 2~3 小时，refresh 约 30 天，
以官方实际期限为准。无 refresh 的旧格式仍可使用，但过期需手动重新登录。
RACCOON_TOKEN_FILE：续期缓存路径，默认本脚本旁 raccoon_tokens.json；续期会轮换
refresh 并以 0600 权限原子保存。保持此文件私密且持久，禁止纳入版本控制或公开。
缓存绑定原始凭据和站点；修改凭据后不复用旧缓存。临期 5 分钟主动续期，认证失败后
至多重试一次；缓存续期凭据优先、环境凭据兜底。请求重定向被禁止，TLS 正常校验。
RACCOON_STATE_FILE：奖励台账路径，默认本脚本旁 raccoon_onboarding.json。
RACCOON_MAIN_SITE_URL：可选 HTTPS 站点，默认 https://xiaohuanxiong.com。
RACCOON_DRY_RUN=1：完全断网、无文件写入的预演（通知仅模拟）。
--query：只查今日入账；--skip-onboarding：不领取新手奖励；--only N：筛选账号；
--no-notify 或 QINGLONG_NOTIFY=0：关闭推送。正常运行自动领取两端一次性奖励。
QINGLONG_NOTIFY 默认 auto（本任务默认未选中）；设为 1 强制启用。
QINGLONG_NOTIFY_SCRIPTS 设置时替换默认名单：逗号、分号、空白分隔，支持本任务
catalog-id、scripts/raccoon_daily.py、raccoon_daily.py、文件名通配符或 *；空值关闭。
QINGLONG_NOTIFY_DIR 指向青龙通知模块目录。dry-run 仅模拟选中的通知，不加载通知模块。
通知优先调用青龙 notify.py，保留 PUSHPLUS_TOKEN、BARK_URL、WECOM_WEBHOOK、
DINGTALK_WEBHOOK/DINGTALK_SECRET 和 QL_URL/QL_TOKEN 兼容渠道。
上游未声明 cron；维护版建议每天北京时间 09:00，青龙应设置相应时区。

MIT License
本文件继承任务声明的上游 MIT 许可；所提供源文件未含额外版权声明。
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
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('d4bfc257a45d9e8d', 'scripts/raccoon_daily.py', 'raccoon_daily.py', 'raccoon_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import fnmatch
import math
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib import request, parse, error

BEIJING = timezone(timedelta(hours=8))
TITLE = "小浣熊每日积分"
CATALOG_ID = "d4bfc257a45d9e8d"
REFRESH = "/api/web/auth/v1/refresh"
CLIENT_VERSION = "v1.0.35"
SETTINGS = "/api/web/office/v3/setting_info"
BILLS = "/api/web/points/v1/bills?paging.limit=20&paging.offset=0"
GRANTS = (("desktop_login_grant", "首次电脑端登录奖励", "desktop-windows", CLIENT_VERSION, "/api/web/desktop/v1/login/points/grant"),
          ("mobile_login_grant", "首次手机端登录奖励", "app-android", "v1.0.3", "/api/web/mobile/v1/login/points/grant"))
DISABLED = {"0", "false", "no", "off"}
SECRETS = set()


class TaskError(Exception):
    pass


class AuthExpired(TaskError):
    pass


def log(message):
    for secret in sorted(SECRETS, key=len, reverse=True):
        message = message.replace(secret, "[凭据已隐藏]")
    print(datetime.now(BEIJING).strftime("[%H:%M:%S] ") + message, flush=True)


def enabled(name, default="0"):
    return os.environ.get(name, default).strip().lower() not in DISABLED | {""}


def secure_url(url):
    parts = parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise TaskError("地址必须为无内嵌凭据的 HTTPS 地址")
    return url


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(url, headers=None, body=None, timeout=20):
    if enabled("RACCOON_DRY_RUN"):
        raise TaskError("预演禁止网络请求")
    secure_url(url)
    hdr = {"Accept": "application/json", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=hdr, method="POST" if body is not None else "GET")
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            if response.status != 200:
                raise TaskError("接口 HTTP 状态异常")
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise TaskError("接口响应过大")
            payload = json.loads(raw.decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthExpired("登录状态失效，请续期或重新登录") from None
        raise TaskError("接口 HTTP %d" % exc.code) from None
    except (error.URLError, TimeoutError, OSError):
        raise TaskError("网络或 TLS 错误、请求超时") from None
    except (ValueError, UnicodeError):
        raise TaskError("接口未返回有效 JSON") from None
    if not isinstance(payload, dict):
        raise TaskError("接口返回结构异常")
    return payload


def unwrap(payload):
    # 上游统一 code/data 契约；缺少业务码不能视为成功。
    if not isinstance(payload, dict):
        raise TaskError("业务响应结构异常")
    if str(payload.get("code")) == "200003":
        raise AuthExpired("登录状态失效，请续期或重新登录")
    if type(payload.get("code")) not in (int, str) or str(payload["code"]) != "0":
        raise TaskError("业务码缺失或业务未成功")
    if not isinstance(payload.get("data"), dict):
        raise TaskError("业务数据结构异常")
    return payload["data"]


def headers(token, platform="desktop-windows", version=CLIENT_VERSION):
    return {"Authorization": "Bearer " + token, "X-Client-Platform": platform,
            "X-Client-Version": version, "X-Raccoon-Language": "zh"}


def accounts_from(raw):
    accounts = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.strip('"\'')
        remainder = line.split("|", 1)[1] if "|" in line else line
        token, refresh = remainder.split("|", 1) if "|" in remainder else (remainder, "")
        token, refresh = strip_bearer(token), strip_bearer(refresh)
        SECRETS.update(v for v in (token, refresh) if v)
        invalid = not token or any(ord(c) < 32 or ord(c) == 127 for c in token + refresh)
        accounts.append({"token": token, "refresh": refresh,
                         "_input_token": token, "_input_refresh": refresh,
                         "_error": "账号凭据为空或格式异常" if invalid else ""})
    if not accounts:
        raise TaskError("请配置 RACCOON_TOKENS，每个非空行一个账号")
    return accounts


def strip_bearer(value):
    value = value.strip()
    return value[7:].strip() if value.lower().startswith("bearer ") else value


def show_identity(data):
    # 只显示官方明确的非秘密身份字段，绝不输出整段响应或用户备注。
    sources = [data]
    for field in ("user", "user_info", "profile"):
        if isinstance(data.get(field), dict):
            sources.append(data[field])
    for source in sources:
        for field in ("nickname", "username", "display_name", "public_uid"):
            value = source.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                text = str(value)
                # 电话号码、设备/会话字段不作为身份输出。
                if field == "public_uid" or not re.fullmatch(r"\+?\d{11,15}", text):
                    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
                    if field != "public_uid":
                        text = re.sub(r"(?<!\d)\+?\d{11,15}(?!\d)", "[手机号已隐藏]", text)
                    log("官方账号身份：" + text)
                    return


def state_path():
    return Path(os.environ.get("RACCOON_STATE_FILE") or Path(__file__).with_name("raccoon_onboarding.json"))


def load_state():
    return load_json_store(state_path())


def save_state(state):
    save_json_store(state_path(), state)


def load_json_store(path):
    if enabled("RACCOON_DRY_RUN"):
        raise TaskError("预演禁止读取缓存或台账")
    try:
        with path.open(encoding="utf-8") as handle:
            state = json.load(handle)
        if not isinstance(state, dict) or not isinstance(state.get("accounts"), dict):
            raise ValueError()
        return state
    except FileNotFoundError:
        return {"version": 1, "accounts": {}}
    except (OSError, ValueError):
        raise TaskError("缓存或台账读取失败，拒绝覆盖已有文件") from None


def save_json_store(path, state):
    if enabled("RACCOON_DRY_RUN"):
        raise TaskError("预演禁止写入缓存或台账")
    temp = None
    try:
        import tempfile
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temp = handle.name
            os.chmod(temp, 0o600)
            json.dump(state, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError:
        raise TaskError("缓存或台账保存失败，轮换凭据可能无法在下次运行复用") from None
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def token_path():
    return Path(os.environ.get("RACCOON_TOKEN_FILE") or Path(__file__).with_name("raccoon_tokens.json"))


def account_key(account, origin):
    # 不使用备注或序号关联缓存，避免账号重新排序后读到其他人的凭据。
    raw = json.dumps([origin, account["_input_token"], account["_input_refresh"]], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def jwt_exp(token):
    # 只作为提前续期提示，绝不据此认证用户或认定业务成功。
    try:
        part = token.split(".")[1]
        value = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("exp")
        exp = float(value) if not isinstance(value, bool) else 0
        return exp if math.isfinite(exp) else 0
    except (ValueError, TypeError, IndexError, AttributeError):
        return 0


def refresh_account(account, origin):
    if enabled("RACCOON_DRY_RUN"):
        raise TaskError("预演禁止续期")
    if account.get("_refresh_rounds", 0) >= 2:
        raise AuthExpired("续期重试达到本账号上限，请重新登录")
    account["_refresh_rounds"] = account.get("_refresh_rounds", 0) + 1
    store = load_json_store(token_path())
    key = account_key(account, origin)
    entry = store["accounts"].get(key, {})
    if not isinstance(entry, dict):
        raise TaskError("续期缓存账号结构异常")
    candidates = []
    for value in (entry.get("refresh"), account.get("refresh"), account["_input_refresh"]):
        if isinstance(value, str) and value.strip() and value.strip() not in candidates:
            candidates.append(value.strip())
    if not candidates:
        raise AuthExpired("未配置可用 refresh_token，请重新登录后更新 RACCOON_TOKENS")
    for value in candidates:
        SECRETS.add(value)
        try:
            data = unwrap(http_json(origin + REFRESH, body={"refresh_token": value}))
            access = data.get("access_token")
            rotated = data.get("refresh_token") or value
            if not isinstance(access, str) or not access.strip() or not isinstance(rotated, str):
                raise TaskError("续期响应缺少有效的登录凭据")
            access, rotated = strip_bearer(access), strip_bearer(rotated)
            if not access or not rotated or any(ord(c) < 32 or ord(c) == 127 for c in access + rotated):
                raise TaskError("续期响应的登录凭据格式异常")
        except TaskError:
            log("⚠️ 当前续期凭据未成功，尝试下一份可用凭据（如有）")
            continue
        SECRETS.update((access, rotated))
        account.update(token=access, refresh=rotated)
        store["accounts"][key] = {"access": access, "refresh": rotated, "updated": int(time.time() * 1000)}
        # 保存失败必须上报，不能把轮换已生效误报为持久化成功。
        save_json_store(token_path(), store)
        log("✅ 登录态已续期，轮换凭据已私密保存")
        return
    raise AuthExpired("所有续期凭据均未成功，请重新登录后更新 RACCOON_TOKENS")


def prepare_auth(account, origin):
    if account.get("_prepared"):
        if account.get("_prepare_error"):
            raise TaskError(account["_prepare_error"])
        return
    account["_prepared"] = True
    try:
        entry = load_json_store(token_path())["accounts"].get(account_key(account, origin), {})
        if not isinstance(entry, dict):
            raise TaskError("续期缓存账号结构异常")
        access = entry.get("access")
        if isinstance(access, str) and access.strip():
            account["token"] = strip_bearer(access)
            SECRETS.add(account["token"])
        exp = jwt_exp(account["token"])
        if exp and exp - time.time() <= 300:
            if entry.get("refresh") or account.get("refresh"):
                refresh_account(account, origin)
            elif exp <= time.time():
                raise AuthExpired("access_token 已过期且无续期凭据，请重新登录")
    except TaskError as exc:
        account["_prepare_error"] = str(exc)
        raise


def call_with_auth(account, origin, action):
    prepare_auth(account, origin)
    try:
        return action(account["token"])
    except AuthExpired:
        refresh_account(account, origin)
        # 仅重试一次，不对其他业务失败重复执行有副作用的接口。
        return action(account["token"])


def daily_total(data):
    if not isinstance(data.get("items"), list):
        raise TaskError("账单缺少 items 列表")
    today = datetime.now(BEIJING).date()
    total, count = 0, 0
    for item in data["items"]:
        if not isinstance(item, dict):
            raise TaskError("账单条目结构异常")
        try:
            points = int(item.get("points") or 0)
            if points <= 0:
                continue
            stamp = datetime.fromisoformat(str(item.get("created_at", "")).replace("Z", "+00:00"))
            stamp = stamp.replace(tzinfo=BEIJING) if stamp.tzinfo is None else stamp.astimezone(BEIJING)
        except (ValueError, TypeError, OverflowError):
            raise TaskError("正积分账单字段无效") from None
        if stamp.date() == today:
            total += points
            count += 1
    if total <= 0:
        raise TaskError("北京时间今日未见正积分入账，不能确认签到成功")
    return "账单核验成功：今日 %d 笔正积分，共 +%d" % (count, total)


def run_account(index, account, args, origin, dry):
    started = time.monotonic()
    stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0)
    def stage(name, action):
        stats["total"] += 1
        step = stats["total"]
        begin = time.monotonic()
        log("账号%d 阶段%d：%s" % (index, step, name))
        try:
            status, message = ("skipped", "断网预演：仅检查任务计划") if dry else action()
            stats[status] += 1
            log("%s %s（%.2f秒）" % ({"success": "✅", "alreadyComplete": "☑️", "skipped": "⏭️"}[status], message, time.monotonic() - begin))
        except Exception as exc:
            stats["failure"] += 1
            log("❌ %s（%.2f秒）" % (str(exc) if isinstance(exc, TaskError) else "执行失败（已隐藏异常细节）", time.monotonic() - begin))
    def trigger():
        data = call_with_auth(account, origin, lambda token: unwrap(http_json(origin + SETTINGS, headers(token))))
        show_identity(data)
        return "success", "每日触发接口业务成功；最终签到结果以账单为准"
    def bills():
        data = call_with_auth(account, origin, lambda token: unwrap(http_json(origin + BILLS, headers(token), timeout=30)))
        show_identity(data)
        return "success", daily_total(data)
    if account.get("_error"):
        stats.update(total=1, failure=1)
        log("账号%d 阶段1：❌ %s（0.00秒）" % (index, account["_error"]))
    elif not args.query:
        stage("每日积分触发", trigger)
    if not account.get("_error"):
        stage("北京时间今日账单核验", bills)
    if not account.get("_error") and not args.query and not args.skip_onboarding:
        for key, title, platform, version, path in GRANTS:
            def claim(key=key, platform=platform, version=version, path=path):
                state = load_state()
                key_id = account_key(account, origin)
                ledger = state["accounts"].get(key_id, {})
                if not isinstance(ledger, dict):
                    raise TaskError("账号奖励台账结构异常")
                # 兼容原维护版与上游按 access 哈希记录的奖励，续期后使用稳定绑定键。
                for token in (account["_input_token"], account["token"]):
                    old = state["accounts"].get(hashlib.sha256(token.encode()).hexdigest()[:16], {})
                    if not isinstance(old, dict):
                        raise TaskError("账号奖励台账结构异常")
                    ledger = {**old, **ledger}
                if ledger.get(key):
                    return "alreadyComplete", "本地台账已结算，不重复请求"
                data = call_with_auth(account, origin, lambda token: unwrap(http_json(origin + path, headers(token, platform, version), body={})))
                show_identity(data)
                if type(data.get("granted")) is not bool:
                    raise TaskError("奖励接口缺少明确 granted 布尔结果")
                ledger[key] = int(time.time() * 1000)
                state["accounts"][key_id] = ledger
                save_state(state)
                if not data["granted"]:
                    return "alreadyComplete", "接口确认奖励此前已发放"
                popup = data.get("popup")
                points = popup.get("points") if isinstance(popup, dict) else None
                message = "接口确认首次登录奖励已领取"
                if type(points) is int and points > 0:
                    message += "，+%d 积分" % points
                return "success", message
            stage(title, claim)
    stats["elapsedSeconds"] = round(time.monotonic() - started, 2)
    log("账号%d统计：任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒" % (index, stats["total"], stats["success"], stats["alreadyComplete"], stats["skipped"], stats["failure"], stats["elapsedSeconds"]))
    return {"account": index, **stats, "ok": stats["failure"] == 0}


def notification_selected(disabled=False):
    if disabled:
        return False
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in DISABLED:
        return False
    if switch in {"1", "true", "yes", "on"}:
        return True
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return False  # listed-only：此任务没有默认选中依据。
    selectors = re.split(r"[,;\s]+", os.environ["QINGLONG_NOTIFY_SCRIPTS"].strip())
    names = {"raccoon_daily.py", Path(__file__).name}
    paths = {"scripts/raccoon_daily.py", "scripts/" + Path(__file__).name}
    return any(selector and (selector == CATALOG_ID or selector in paths or
                            any(fnmatch.fnmatchcase(name, selector) for name in names))
               for selector in selectors)


def notification_process(body, path=None, javascript=False):
    if enabled("RACCOON_DRY_RUN"):
        raise TaskError("预演禁止启动通知进程")
    # 隔离通知模块的日志，避免模块自行输出推送令牌；超时不改变业务退出码。
    if javascript:
        code = """const fs=require('fs');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
Promise.resolve(require(process.argv[1]).sendNotify(p.title,p.body))
.then(r=>{process.exitCode=r===false?1:0;}).catch(()=>{process.exitCode=1;});"""
        command = ["node", "-e", code, str(path)]
    else:
        code = """import sys,json,importlib.util
p=json.load(sys.stdin)
if len(sys.argv)>1:
    from pathlib import Path
    sys.path.insert(0,str(Path(sys.argv[1]).parent))
    spec=importlib.util.spec_from_file_location('qinglong_notify',sys.argv[1])
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    send=module.send
else:
    from notify import send
result=send(p['title'],p['body'])
sys.exit(1 if result is False else 0)
"""
        command = [sys.executable, "-c", code] + ([str(path)] if path else [])
    try:
        result = subprocess.run(command, input=json.dumps({"title": TITLE, "body": body}),
                                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=30, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def notify_summary(body, disabled, dry):
    if not notification_selected(disabled):
        return "已关闭或未选中"
    if dry:
        log("⏭️ 预演通知模拟：" + body)
        return "预演模拟（未调用通知模块）"
    if notification_process(body):
        return "青龙已发送"
    folders = []
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        folders.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]))
    folders.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    seen = set()
    for javascript, filename in ((False, "notify.py"), (True, "sendNotify.js")):
        for folder in folders:
            path = (folder / filename).absolute()
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            if notification_process(body, path, javascript):
                return "青龙已发送"
            log("⚠️ 青龙通知调用失败（细节已隐藏）")
    # 保留原脚本兼容渠道；所有请求校验 TLS，错误只记录固定文字。
    e = lambda name: os.environ.get(name, "").strip()
    channels = []
    if e("PUSHPLUS_TOKEN"):
        channels.append(("https://www.pushplus.plus/send", {"token": e("PUSHPLUS_TOKEN"), "title": TITLE, "content": body, "template": "txt"}, "code", 200))
    if e("BARK_URL"):
        channels.append((e("BARK_URL").rstrip("/"), {"title": TITLE, "body": body, "group": "小浣熊"}, "code", 200))
    if e("WECOM_WEBHOOK"):
        hook = e("WECOM_WEBHOOK")
        if "://" not in hook:
            hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + parse.quote(hook, safe="")
        channels.append((hook, {"msgtype": "text", "text": {"content": TITLE + "\n" + body}}, "errcode", 0))
    if e("DINGTALK_WEBHOOK"):
        hook = e("DINGTALK_WEBHOOK")
        secret = e("DINGTALK_SECRET")
        if secret:
            stamp = str(int(time.time() * 1000))
            sig = base64.b64encode(hmac.new(secret.encode(), (stamp + "\n" + secret).encode(), hashlib.sha256).digest()).decode()
            hook += ("&" if "?" in hook else "?") + parse.urlencode({"timestamp": stamp, "sign": sig})
        channels.append((hook, {"msgtype": "text", "text": {"content": TITLE + "\n" + body}}, "errcode", 0))
    if e("QL_URL") and e("QL_TOKEN"):
        channels.append((e("QL_URL").rstrip("/") + "/api/system/notify?" + parse.urlencode({"token": e("QL_TOKEN")}), {"title": TITLE, "content": body}, "code", (0, 200)))
    for url, payload, field, expected in channels:
        try:
            result = http_json(url, body=payload, timeout=15)
            allowed = expected if isinstance(expected, tuple) else (expected,)
            if str(result.get(field)) in {str(v) for v in allowed}:
                return "兼容渠道已发送"
        except Exception:
            pass
    log("⚠️ 通知不可用或失败，保留业务退出码")
    return "不可用或失败"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError("命令参数无效，请使用 --query、--skip-onboarding、--only N、--no-notify")


def main():
    start = time.monotonic()
    dry = enabled("RACCOON_DRY_RUN")
    log("========== " + TITLE + " ==========")
    log("开始时间：" + datetime.now(BEIJING).isoformat(timespec="seconds"))
    log("运行模式：" + ("断网预演" if dry else "正式执行"))
    results, config_error, selected = [], False, []
    args = argparse.Namespace(no_notify="--no-notify" in sys.argv[1:])
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("--query", action="store_true")
        parser.add_argument("--skip-onboarding", action="store_true")
        parser.add_argument("--only", type=int)
        parser.add_argument("--no-notify", action="store_true")
        args = parser.parse_args()
        accounts = accounts_from(os.environ.get("RACCOON_TOKENS", ""))
        if args.only is not None and not 1 <= args.only <= len(accounts):
            raise TaskError("--only 必须是已配置账号的有效序号")
        selected = [(i, account) for i, account in enumerate(accounts, 1) if args.only is None or args.only == i]
        origin = secure_url((os.environ.get("RACCOON_MAIN_SITE_URL", "").strip() or "https://xiaohuanxiong.com").rstrip("/"))
        if parse.urlsplit(origin).query or parse.urlsplit(origin).path not in ("", "/"):
            raise TaskError("站点配置仅允许 HTTPS 域名及可选端口")
        log("账号数：配置%d，本次%d" % (len(accounts), len(selected)))
        for index, account in selected:
            results.append(run_account(index, account, args, origin, dry))
    except Exception as exc:
        config_error = True
        log("❌ 配置错误：" + (str(exc) if isinstance(exc, TaskError) else "配置处理失败（细节已隐藏）"))
        log("账号数：本次%d" % len(selected))
    good = sum(r["ok"] for r in results)
    bad = len(results) - good
    exit_code = 1 if config_error or bad else 0
    status = "configuration-error" if config_error else "partial-failure" if bad and good else "failure" if bad else "dry-run" if dry else "success"
    totals = {k: sum(r[k] for r in results) for k in ("total", "success", "alreadyComplete", "skipped", "failure")}
    body = "状态：%s；账号总数%d，成功%d，失败%d；子任务%d，成功%d，已完成%d，跳过%d，失败%d%s" % (status, len(selected), good, bad, totals["total"], totals["success"], totals["alreadyComplete"], totals["skipped"], totals["failure"], "；配置错误" if config_error else "")
    log("----------------------------------------")
    log(body)
    try:
        notification = notify_summary(body, args.no_notify, dry)
    except Exception:
        notification = "不可用或失败"
        log("⚠️ 通知失败（细节已隐藏），保留业务退出码")
    summary = {"task": TITLE, "status": status, "dryRun": dry, "accountCount": len(selected), "successCount": good, "failureCount": bad, "configurationError": config_error, "accounts": results, "stages": totals, "notification": notification, "elapsedSeconds": round(time.monotonic() - start, 2), "exitCode": exit_code}
    log("通知状态：" + notification)
    log("总耗时：%.2f秒；完成时间：%s；最终状态：%s" % (summary["elapsedSeconds"], datetime.now(BEIJING).isoformat(timespec="seconds"), status))
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
