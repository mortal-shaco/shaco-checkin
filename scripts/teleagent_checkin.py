#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 星辰超级智能体签到
# cron: 12 10 * * *
# 来源: firlsy/ql_scripts-AI_auto_sign / teleagent_checkin.py
# 上游提交: 820b611ad874f8282a23d90b621afd68e66d0960；许可证: MIT
"""星辰超级智能体（TeleAgent）每日积分签到，Python 标准库独立维护版。

参数获取：登录 https://agent.teleai.com.cn，在浏览器开发者工具的存储中
取得本账号 console_token，或从已登录请求的 Authorization 中取得裸令牌。
TELEAGENT_TOKEN 每个非空行一个账号，不使用 & 或 @ 分隔，不要分享令牌。
在网络面板手动领取每日积分，确认实际 POST、JSON 空对象请求及响应业务码，
将同站领取路径填入 TELEAGENT_CLAIM_PATHS（逗号分隔、按顺序尝试）。
未配置时不猜测领取接口、不发任何业务请求。此脚本只支持上游的 POST {} 契约；
若实际接口需要其他参数，应先适配，不能盲目调用。成功响应须为 HTTP 2xx 且
code 为 0/200 或 success 为 true，冲突的错误码优先判失败。
TELEAGENT_API_BASE 保留兼容，仅允许官方 HTTPS 站点（可含尾部斜线）。
TELEAGENT_DRY_RUN=1 完全断网，仅校验配置并模拟阶段，不表示真实签到成功。
每天 08:30：30 8 * * *。无第三方依赖；notify.py / sendNotify.js 仅用于可选通知。
QINGLONG_NOTIFY=1 强制通知，0 禁用，auto 只通知 QINGLONG_NOTIFY_SCRIPTS
选中的脚本（本任务无默认名单）；支持目录 QINGLONG_NOTIFY_DIR。
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
        _ql_notify_identities = ('956b31e72c16b768', 'scripts/teleagent_checkin.py', 'teleagent_checkin.py', 'teleagent_checkin')
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
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


TITLE = "星辰超级智能体签到"
CATALOG = "956b31e72c16b768"
TIMEOUT = 20
MAX_BYTES = 262144
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
SECRETS = []


def safe(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return "".join(c if c.isprintable() else " " for c in text)


def log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {safe(message)}", flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 不把凭据转发到重定向地址，也不重试变更请求


def request(method, base, path, token):
    headers = {
        "User-Agent": "Mozilla/5.0 TeleAgentCheckin/1.0",
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Origin": base,
        "Referer": base + "/",
        "Authorization": "Bearer " + token,
        "Auth-Token": "Bearer " + token,
    }
    body = b"{}" if method == "POST" else None
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=TIMEOUT) as resp:
            if not 200 <= resp.status < 300:
                raise TaskError("HTTP 状态未通过")
            raw = resp.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise TaskError("响应超过大小限制")
        data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise TaskError(f"HTTP {status}，请求未通过") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError("网络请求失败或超时") from None
    except (UnicodeError, ValueError):
        raise TaskError("响应不是有效 JSON") from None
    if not isinstance(data, dict):
        raise TaskError("响应结构不符合接口契约")
    code = data.get("code")
    valid_code = type(code) in (str, int) and str(code) in {"0", "200"}
    if (code is not None and not valid_code) or data.get("success") is False:
        raise TaskError("业务状态未通过（令牌、权限或接口状态异常）")
    if not valid_code and data.get("success") is not True:
        raise TaskError("响应缺少明确的业务成功标志")
    return data


def show_summary(data):
    payload = data.get("data")
    if not isinstance(payload, dict):
        log("资源查询业务成功，未返回可安全展示的概览字段")
        return
    # 只输出明确身份和数值积分，不打印任意字段或完整响应。
    identity_keys = ("nickname", "nickName", "username", "userName", "displayName", "publicUid", "uid")
    for obj in (payload, payload.get("user"), payload.get("userInfo")):
        if not isinstance(obj, dict):
            continue
        for key in identity_keys:
            value = obj.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                log(f"账号身份 {key}：{value}")
    count = 0
    def visit(obj, prefix="", depth=0):
        nonlocal count
        if not isinstance(obj, dict) or depth > 3:
            return
        for key, value in obj.items():
            if key in {"points", "point", "balance", "credits", "credit", "totalPoints", "availablePoints", "remainingPoints"}:
                if type(value) in (int, float) or (isinstance(value, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", value)):
                    log(f"积分概览 {prefix}{key}：{value}")
                    count += 1
            if key in {"resource", "resources", "points", "credits", "summary"} and isinstance(value, dict):
                visit(value, prefix + key + ".", depth + 1)
    visit(payload)
    if not count:
        log("资源查询业务成功，未返回已知的数值积分字段")


def configuration():
    tokens = [x.strip() for x in os.getenv("TELEAGENT_TOKEN", "").splitlines() if x.strip()]
    SECRETS.extend(tokens)
    if not tokens:
        raise TaskError("未配置 TELEAGENT_TOKEN；每行填写一个账号的 console_token")
    if any(any(ord(c) < 32 or ord(c) > 126 for c in token) for token in tokens):
        raise TaskError("令牌必须为可用于 HTTP 请求头的文本")
    base = os.getenv("TELEAGENT_API_BASE", "https://agent.teleai.com.cn").rstrip("/")
    if base != "https://agent.teleai.com.cn":
        raise TaskError("TELEAGENT_API_BASE 仅允许官方 HTTPS 站点，避免泄漏令牌")
    paths = [p.strip() for p in os.getenv("TELEAGENT_CLAIM_PATHS", "").split(",") if p.strip()]
    if not paths:
        raise TaskError("必须配置抓包确认的 TELEAGENT_CLAIM_PATHS；已移除猜测接口默认值")
    for path in paths:
        parts = urllib.parse.urlsplit(path)
        if (not path.startswith("/") or path.startswith("//") or parts.scheme or parts.netloc
                or parts.query or parts.fragment or "\\" in path or "%" in path
                or any(c.isspace() or ord(c) < 32 for c in path)
                or any(p in {".", ".."} for p in parts.path.split("/"))):
            raise TaskError("领取路径须为同站绝对路径，不含域名、查询凭据、片段或路径跳转")
    return tokens, base, list(dict.fromkeys(paths))


def run_account(index, token, base, paths, dry):
    started = time.monotonic()
    stats = {"total": 4, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
    log(f"账号 #{index} 开始")
    blocked = False
    for number, title in enumerate(("令牌校验与积分概览", "活动配置查询", "每日积分领取", "领取后积分概览"), 1):
        tick = time.monotonic()
        log(f"账号 #{index} 阶段 {number}/4：{title}")
        if dry or blocked:
            stats["skipped"] += 1
            log(f"⏭️ {'断网预演，未发送请求' if dry else '令牌校验失败，跳过后续请求'}；耗时 {time.monotonic()-tick:.2f} 秒")
            continue
        try:
            if number in (1, 4):
                show_summary(request("GET", base, "/console/api/user/resource/summary", token))
            elif number == 2:
                result = request("POST", base, "/console/api/notifications/campaigns", token)
                payload = result.get("data")
                log("活动配置业务成功" + (f"，配置项 {len(payload)} 个" if isinstance(payload, (dict, list)) else ""))
            else:
                claimed = False
                for attempt, path in enumerate(paths, 1):
                    try:
                        request("POST", base, path, token)
                        log(f"领取路径 #{attempt}：业务成功，停止后续尝试")
                        claimed = True
                        break
                    except TaskError as exc:
                        log(f"领取路径 #{attempt}：❌ {exc}")
                if not claimed:
                    raise TaskError("所有显式配置的领取路径均未验证成功")
            stats["success"] += 1
            log(f"✅ 阶段完成；耗时 {time.monotonic()-tick:.2f} 秒")
        except TaskError as exc:
            stats["failure"] += 1
            blocked = number == 1
            log(f"❌ {exc}；耗时 {time.monotonic()-tick:.2f} 秒")
        except Exception:
            stats["failure"] += 1
            blocked = number == 1
            log(f"❌ 阶段执行异常，未展示敏感异常内容；耗时 {time.monotonic()-tick:.2f} 秒")
    stats["seconds"] = round(time.monotonic() - started, 2)
    log(f"账号 #{index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 0，跳过 {stats['skipped']}，失败 {stats['failure']}，耗时 {stats['seconds']} 秒")
    return stats


def notify_summary(body, dry):
    if dry:
        log("通知：断网预演，仅生成脱敏摘要，未调用通知服务")
        return "dry-run"
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch not in TRUE | FALSE | {"auto"}:
        log("通知：开关无效，已跳过；业务退出码保持不变")
        return "invalid-switch"
    selectors = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    names = {CATALOG, "teleagent_checkin.py", "scripts/teleagent_checkin.py", Path(__file__).name, "scripts/" + Path(__file__).name}
    selected = selectors is not None and any(
        fnmatch.fnmatchcase(name, pattern) for pattern in re.split(r"[,;\s]+", selectors.strip()) if pattern for name in names)
    if switch in FALSE or (switch == "auto" and not selected):
        log("通知：已依全局开关或脚本名单关闭")
        return "disabled"
    # 通知子进程输出全部隔离；超时和失败不改变业务退出码。
    directories = [str(Path(__file__).resolve().parent), os.getcwd()]
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        directories.append(os.environ["QINGLONG_NOTIFY_DIR"])
    directories += ["/ql/data/scripts", "/ql/scripts"]
    pycode = "import sys,json;sys.path[:0]=json.loads(sys.argv[1]);from notify import send;send(sys.argv[2],sys.argv[3])"
    commands = [[sys.executable, "-c", pycode, json.dumps(directories), TITLE, body]]
    jscode = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
    commands += [["node", "-e", jscode, str(Path(d) / "sendNotify.js"), TITLE, body]
                 for d in directories if (Path(d) / "sendNotify.js").is_file()]
    for command in commands:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25, check=False)
            if result.returncode == 0:
                log("通知：脱敏摘要已发送")
                return "sent"
        except (OSError, subprocess.TimeoutExpired):
            pass
    log("⚠️ 通知不可用或发送失败；保留业务退出码")
    return "unavailable-or-failed"


def main():
    started = time.monotonic()
    dry = os.getenv("TELEAGENT_DRY_RUN", "0").strip().lower() in TRUE
    count = len([x for x in os.getenv("TELEAGENT_TOKEN", "").splitlines() if x.strip()])
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry else '正式执行'}；账号数：{count}")
    results = []
    error = False
    try:
        tokens, base, paths = configuration()
        for index, token in enumerate(tokens, 1):
            results.append(run_account(index, token, base, paths, dry))
    except TaskError as exc:
        error = True
        log(f"❌ 配置错误：{exc}")
    failed = count if error else sum(r["failure"] > 0 for r in results)
    succeeded = 0 if dry or error else count - failed
    status = "configuration-error" if error else ("partial-failure" if failed and succeeded else "failure" if failed else "dry-run" if dry else "success")
    code = 1 if error or failed else 0
    totals = {key: sum(r[key] for r in results) for key in ("total", "success", "alreadyComplete", "skipped", "failure")}
    body = f"账号总数 {count}，成功 {succeeded}，失败 {failed}，预演 {len(results) if dry else 0}；状态 {status}；子任务 {json.dumps(totals, ensure_ascii=False)}"
    notification = notify_summary(body, dry)
    log("----------------------------------------")
    log(f"账号统计：总数 {count}，成功 {succeeded}，失败 {failed}，预演 {len(results) if dry else 0}")
    log(f"子任务统计：总数 {totals['total']}，成功 {totals['success']}，已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，失败 {totals['failure']}")
    elapsed = round(time.monotonic() - started, 2)
    log(f"完成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {elapsed} 秒；最终状态：{status}；通知：{notification}")
    print("TASK_SUMMARY=" + json.dumps({"status": status, "mode": "dry-run" if dry else "live", "accounts": count, "success": succeeded, "failure": failed, "tasks": totals, "seconds": elapsed, "notification": notification, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
