# -*- coding: utf-8 -*-
# name: SSPanel 每日签到
# cron: 0 11 * * *
"""独立 SSPanel 签到；原作者 Icrons，2021/3/21，来源 jing5460/SSr-Sign/main.py。
上游许可 MIT，保留原始署名：@Time ： 2021/3/21 12:01；@Auth ： Icrons；@IDE ：PyCharm。

MIT License
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

SSPANEL_ACCOUNTS：每个非空行 HTTPS站点|邮箱|密码，仅分割前两个 |。
站点和账号从所使用的 SSPanel 站点注册/登录页获取，密码从密码管理器获取。
无源码内置凭据，无自动购买、转账、发帖操作。只支持原来的密码登录接口，
不绕过验证码或双因素认证。SSPANEL_DRY_RUN=1 完全断网，亦不发送通知。
原脚本未提供 cron；建议每日 08:00。兼容云函数 main_handler(event, context)。
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
        _ql_notify_identities = ('a5843af909a36789', 'scripts/task_a5843af9.py', 'task_a5843af9.py', 'task_a5843af9')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape

TITLE = "SSPanel 每日签到"
CATALOG = "a5843af909a36789"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
TIMEOUT = 15
LIMIT = 1024 * 1024


class TaskError(Exception):
    pass


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # 不向重定向目标转发账号、密码或通知密钥。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def client():
    return urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(opener, url, data=None, headers=None, as_json=True, raw=False):
    if os.environ.get("SSPANEL_DRY_RUN", "").lower() in TRUE:
        raise TaskError("断网预演禁止请求")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise TaskError("请求地址必须为无内嵌凭据的 HTTPS 地址")
    body = data if raw else (urllib.parse.urlencode(data).encode() if data is not None else None)
    request_headers = {"User-Agent": "SSPanel-Qinglong/1.0"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=request_headers)
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            content = response.read(LIMIT + 1)
        if len(content) > LIMIT:
            raise TaskError("响应超过大小限制")
        text = content.decode("utf-8")
        return json.loads(text) if as_json else text
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError(f"HTTP 请求失败（状态码 {exc.code}，不自动重试）") from None
    except Exception:
        raise TaskError("请求失败：网络、超时或响应格式异常") from None


def accounts():
    lines = [line.strip() for line in os.environ.get("SSPANEL_ACCOUNTS", "").splitlines() if line.strip()]
    result = []
    for line in lines:
        try:
            base, email, password = line.split("|", 2)
            base = base.strip().rstrip("/")
            email = email.strip()
            parsed = urllib.parse.urlsplit(base)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                    parsed.password or parsed.query or parsed.fragment or not email or not password):
                raise ValueError()
            result.append((base, email, password))
        except ValueError:
            result.append(None)
    return result


def clean(value, secrets=()):
    text = unescape(str(value))
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"[\w.+-]+@[\w.-]+", "[邮箱已隐藏]", text)
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return " ".join(text.split())[:200]


def identity(payload, secrets):
    if not isinstance(payload, dict):
        return
    for source in [payload, payload.get("data"), payload.get("user")]:
        if isinstance(source, dict):
            for key in ("nickname", "username", "display_name", "uid"):
                value = source.get(key)
                if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                    log(f"官方账号身份（{key}）：{clean(value, secrets)}")


def verified(payload):
    return isinstance(payload, dict) and type(payload.get("ret")) in (str, int) and str(payload["ret"]) == "1"


def run_account(index, account, dry):
    started = time.monotonic()
    stats = {"account": index, "total": 3, "success": 0, "alreadyComplete": 0,
             "skipped": 0, "failure": 0}
    log(f"账号 {index} 开始")
    opener = client()
    if account:
        base, email, password = account
        secrets = (email, password)
    for stage, label in enumerate(("建立会话并登录", "每日签到", "查询账户信息（editXY）"), 1):
        step = time.monotonic()
        log(f"账号 {index} 阶段 {stage}/3：{label}")
        try:
            if account is None:
                raise TaskError("账号配置无效：需要 HTTPS站点|邮箱|密码")
            if dry:
                log("⏭️ 断网预演：参数有效，未发送请求、未签到")
                stats["skipped"] += 1
            elif stage == 1:
                request(opener, base, as_json=False)
                payload = request(opener, base + "/auth/login",
                                  {"email": email, "passwd": password, "code": ""})
                if not verified(payload):
                    raise TaskError("登录未获明确成功确认；请检查凭据、验证码及接口兼容性")
                identity(payload, secrets)
                log("✅ 登录成功（ret=1）")
                stats["success"] += 1
            elif stage == 2:
                payload = request(opener, base + "/user/checkin", {}, {"Referer": base + "/user"})
                if not verified(payload):
                    raise TaskError("签到未获明确成功确认；不根据消息猜测成功或重复签到")
                identity(payload, secrets)
                log("✅ 签到成功（ret=1）；未输出服务器原始消息")
                stats["success"] += 1
            else:
                page = request(opener, base + "/user", as_json=False)
                found = 0
                for key, title in (("Class", "用户等级"), ("Class_Expire", "到期时间"),
                                   ("Unused_Traffic", "剩余流量")):
                    match = re.search(r'\[\s*"' + key + r'"\s*,\s*"([^"\r\n]*)"\s*\]', page)
                    if match:
                        value = clean(re.sub(r"<[^>]*>", "", match.group(1)), secrets)
                        log(f"{title}：{value}")
                        found += 1
                if found:
                    stats["success"] += 1
                    log(f"✅ 读取 {found}/3 项账户信息")
                else:
                    stats["skipped"] += 1
                    log("⏭️ 页面未提供 editXY 字段；已验证的签到结果保留")
        except TaskError as exc:
            stats["failure"] += 1
            log(f"❌ {exc}")
            stats["skipped"] += 3 - stage
            break
        except Exception:
            stats["failure"] += 1
            stats["skipped"] += 3 - stage
            log("❌ 阶段处理异常，已隐藏异常详情")
            break
        finally:
            log(f"账号 {index} 阶段 {stage} 耗时 {time.monotonic() - step:.2f} 秒")
    stats["elapsedSeconds"] = round(time.monotonic() - started, 3)
    log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 "
        f"{stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failure']}，"
        f"耗时 {stats['elapsedSeconds']:.2f} 秒")
    return stats


def notification_enabled():
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").lower()
    if switch in FALSE:
        return False
    selected = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selected is not None:
        names = [CATALOG, Path(__file__).name, Path(__file__).as_posix()]
        for root in ("/ql/data/scripts", "/ql/scripts"):
            try:
                names.append(Path(__file__).resolve().relative_to(root).as_posix())
            except ValueError:
                pass
        return any(fnmatch.fnmatch(name, pattern) for name in names
                   for pattern in re.split(r"[,;\s]+", selected.strip()) if pattern)
    return switch in TRUE  # auto 默认仅名单；没有内置名单。


def qinglong_notify(body):
    paths = []
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]))
    paths += [Path("/ql/data/scripts"), Path("/ql/scripts")]
    candidates = []
    try:
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin:
            candidates.append(Path(spec.origin))
    except Exception:
        pass
    candidates += [p / "notify.py" for p in paths]
    for path in candidates:
        if path.is_file():
            code = ("import runpy,sys; m=runpy.run_path(sys.argv[1]); "
                    "m['send'](sys.argv[2],sys.argv[3])")
            command = [sys.executable, "-c", code, str(path), TITLE, body]
            break
    else:
        script = next((p / "sendNotify.js" for p in paths if (p / "sendNotify.js").is_file()), None)
        if script is None:
            return "不可用"
        command = ["node", "-e", "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                   str(script), TITLE, body]
    try:
        child = subprocess.run(command, timeout=30, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, check=False)
        return "已发送" if child.returncode == 0 else "发送失败"
    except Exception:
        return "发送失败"


def legacy_notify(body):
    """保留原五个可选渠道；独立密钥仍为可选配置。"""
    jobs = []
    env = os.environ
    if env.get("SendKey"):
        jobs.append(("Server酱", "https://sctapi.ftqq.com/" + urllib.parse.quote(env["SendKey"], safe="") + ".send",
                     {"text": TITLE, "desp": body}, lambda p: p.get("code") == 0))
    if env.get("ktkey"):
        jobs.append(("酷推", "https://push.xuthus.cc/send/" + urllib.parse.quote(env["ktkey"], safe=""),
                     body.encode(), lambda p: p.get("code") == 200))
    if env.get("QmsgKey"):
        jobs.append(("Qmsg", "https://qmsg.zendee.cn/send/" + urllib.parse.quote(env["QmsgKey"], safe=""),
                     {"msg": body}, lambda p: p.get("success") is True))
    if env.get("tele_bot_token"):
        jobs.append(("Telegram", env.get("tele_api_url", "https://api.telegram.org").rstrip("/") +
                     "/bot" + urllib.parse.quote(env["tele_bot_token"], safe=":") + "/sendMessage",
                     {"chat_id": env.get("tele_user_id", ""), "text": body}, lambda p: p.get("ok") is True))
    if env.get("push_token"):
        jobs.append(("Pushplus", "https://www.pushplus.plus/send",
                     {"token": env["push_token"], "title": TITLE, "content": body}, lambda p: p.get("code") == 200))
    for name, url, data, check in jobs:
        try:
            headers = None
            if name == "Pushplus":
                data = json.dumps(data).encode("utf-8")
                headers = {"Content-Type": "application/json"}
            payload = request(client(), url, data, headers=headers, raw=isinstance(data, bytes))
            log(f"{name} 通知：" + ("已发送" if isinstance(payload, dict) and check(payload) else "未获成功确认"))
        except Exception:
            log(f"{name} 通知失败（详情已隐藏，不改变业务退出码）")


def main():
    started = time.monotonic()
    dry = os.environ.get("SSPANEL_DRY_RUN", "").lower() in TRUE
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.now().isoformat(timespec='seconds')}；模式：{'断网预演' if dry else '正式执行'}")
    entries = accounts()
    log(f"账号数量：{len(entries)}")
    results = [run_account(i, account, dry) for i, account in enumerate(entries, 1)]
    failed = sum(r["failure"] > 0 for r in results)
    success = len(results) - failed
    exit_code = int(not entries or failed > 0)
    if not entries:
        log("❌ 配置错误：必须提供 SSPANEL_ACCOUNTS，每行一个账号")
    status = ("configuration-error" if not entries else "partial-failure" if failed and success
              else "failure" if failed else "dry-run" if dry else "success")
    body = f"状态：{status}；账号总数 {len(entries)}，成功数 {success}，失败数 {failed}。"
    if dry:
        body += " 断网预演，成功数仅表示参数检查通过，未实际签到。"
        notification = "断网预演跳过投递"
    elif notification_enabled():
        notification = qinglong_notify(body)
        legacy_notify(body)
    else:
        notification = "开关或名单关闭"
    log("----------------------------------------")
    log(body)
    totals = {key: sum(r[key] for r in results) for key in ("total", "success", "alreadyComplete", "skipped", "failure")}
    log(f"子任务统计：总任务 {totals['total']}，成功 {totals['success']}，已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，失败 {totals['failure']}")
    log(f"完成时间：{datetime.now().isoformat(timespec='seconds')}；总耗时 {time.monotonic()-started:.2f} 秒")
    log(f"通知状态：{notification}；最终状态：{status}；退出码：{exit_code}")
    print("TASK_SUMMARY=" + json.dumps({"status": status, "mode": "dry-run" if dry else "live",
          "accounts": len(entries), "success": success, "failed": failed, "tasks": totals,
          "results": results, "notification": notification, "exitCode": exit_code}, ensure_ascii=False))
    return exit_code


def main_handler(event, context):
    return {"exitCode": main()}


if __name__ == "__main__":
    sys.exit(main())
