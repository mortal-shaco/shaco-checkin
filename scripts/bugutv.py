#!/usr/bin/env python3
# name: 布谷TV每日签到
# cron: 0 8 * * *
# License: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy at http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# 上游：MonjackWon/bugutv_AutoSignin，bugutv.py
# https://github.com/MonjackWon/bugutv_AutoSignin
# 原脚本通知函数说明：以下是使用server酱通知的函数（抄来的，哈哈）
# BUGUTV_ACCOUNTS：每行 用户名|密码，仅在第一个 | 处分割。
# 用户名与密码来自 https://www.bugutv.vip 的本人注册账号。
# BUGUTV_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
# BUGUTV_SERVER_SEND_KEY 可选，兼容原 sever_jiang_send_key 配置名称。
# 运行仅需要 Python 3 标准库，无需安装其他依赖。

import html
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import time
from decimal import Decimal, InvalidOperation
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler

BASE = "https://www.bugutv.vip"
TITLE = "布谷TV每日签到"
OFF = {"0", "false", "no", "off"}


def enabled(name, default="0"):
    return os.environ.get(name, default).strip().lower() not in OFF


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class TaskError(Exception):
    """只携带固定脱敏描述。"""


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if (new.scheme, new.netloc) != (old.scheme, old.netloc):
            raise TaskError("拒绝跨站重定向")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self):
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()), SameOriginRedirect())

    def request(self, url, data=None):
        payload = urlencode(data).encode("utf-8") if data is not None else None
        req = Request(url, data=payload, headers={
            "User-Agent": "Mozilla/5.0 Qinglong-Bugutv/1.0",
            "Referer": BASE + "/", "Accept": "application/json,text/html",
        })
        try:
            with self.opener.open(req, timeout=20) as response:
                if response.status != 200:
                    raise TaskError("HTTP状态异常")
                body = response.read(2 * 1024 * 1024 + 1)
                if len(body) > 2 * 1024 * 1024:
                    raise TaskError("响应超过大小限制")
                return body.decode("utf-8", errors="strict")
        except TaskError:
            raise
        except Exception:
            raise TaskError("请求失败（网络、超时或响应编码异常）") from None


def response_message(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        raise TaskError("业务响应不是有效JSON") from None
    if not isinstance(value, dict):
        raise TaskError("业务响应结构异常")
    if value.get("success") is False:
        raise TaskError("接口明确返回失败")
    if "status" in value and (value["status"] is False or value["status"] in (0, "0", "error", "failed", "fail")):
        raise TaskError("接口明确返回失败状态")
    # 只检查业务消息字段，不扫描原始响应、用户名或回显请求。
    messages = []
    for key in ("msg", "message", "data"):
        item = value.get(key)
        if isinstance(item, str):
            messages.append(item)
        elif isinstance(item, dict):
            for field in ("msg", "message"):
                if isinstance(item.get(field), str):
                    messages.append(item[field])
    return " ".join(messages), value


def verified_message(message, phrase):
    # 不把“未签到成功”等否定句当作业务成功。
    message = html.unescape(re.sub(r"<[^>]*>", " ", message)).strip()
    if re.search(r"失败|错误|无效|过期|未登录|未签到|不成功", message):
        return False
    return bool(re.search(r"(?:^|[\s，。！!：:])" + re.escape(phrase) + r"(?:$|[\s，。！!：:])", message))


def points(page):
    match = re.search(r'<span\b[^>]*class=[\"\'][^\"\']*badge-warning-lighten[^\"\']*[\"\'][^>]*>\s*<i\b[^>]*class=[\"\'][^\"\']*fa-coins[^\"\']*[\"\'][^>]*>\s*</i>\s*([0-9]+(?:\.[0-9]+)?)\s*</span>', page, re.I)
    if not match:
        raise TaskError("未找到账户积分，页面或登录状态可能变化")
    try:
        return Decimal(match.group(1))
    except InvalidOperation:
        raise TaskError("积分格式异常") from None


def nonce(page):
    values = []
    targeted = []
    for tag in re.findall(r"<[^>]+>", page):
        found = re.search(r'\bdata-nonce\s*=\s*[\"\']([^\"\']+)[\"\']', tag, re.I)
        if found:
            values.append(html.unescape(found.group(1)))
            if re.search(r"qiandao|checkin|签到", tag, re.I):
                targeted.append(html.unescape(found.group(1)))
    candidates = set(targeted or values)
    if len(candidates) != 1:
        raise TaskError("签到nonce缺失或不明确，停止提交")
    return candidates.pop()


def public_identity(value):
    for source in (value, value.get("data")):
        if isinstance(source, dict):
            for key in ("nickname", "display_name", "username", "public_uid"):
                name = source.get(key)
                if isinstance(name, (str, int)) and not isinstance(name, bool):
                    name = str(name)
                    # 不打印控制字符或手机号；普通公开昵称按返回值显示。
                    if not re.search(r"[\x00-\x1f\x7f]|(?<!\d)1[3-9]\d{9}(?!\d)", name):
                        return name
    return None


def logout_url(page):
    for found in re.findall(r'href\s*=\s*[\"\']([^\"\']+)[\"\']', page, re.I):
        url = html.unescape(found)
        if url.startswith("/"):
            url = BASE + url
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        if (parts.scheme == "https" and parts.netloc == "www.bugutv.vip"
                and parts.path == "/wp-login.php" and query.get("action") == ["logout"]
                and query.get("_wpnonce")):
            return url
    raise TaskError("未找到有效退出链接")


def account_run(index, username, password, dry):
    stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    started = time.monotonic()
    client = None
    authenticated = False
    page = ""
    gain = balance = None

    def stage(number, name, action):
        stats["total"] += 1
        tick = time.monotonic()
        log(f"账号{index} · 阶段{number} {name} 开始")
        try:
            result = action()
            state = "alreadyComplete" if result == "alreadyComplete" else "success"
            stats[state] += 1
            log(f"账号{index} · 阶段{number} {'☑️ 已完成' if state == 'alreadyComplete' else '✅ 成功'} · 耗时{time.monotonic()-tick:.2f}秒")
            return result
        except Exception as error:
            stats["failed"] += 1
            detail = str(error) if isinstance(error, TaskError) else "处理异常（详情已脱敏）"
            log(f"账号{index} · 阶段{number} ❌ {detail} · 耗时{time.monotonic()-tick:.2f}秒")
            raise TaskError(detail) from None

    try:
        if dry:
            for number, name in enumerate(("登录", "读取签到前积分", "每日签到", "读取签到后积分", "退出登录"), 1):
                if number == 5 and not enabled("BUGUTV_LOGOUT", "1"):
                    stats["total"] += 1
                    stats["skipped"] += 1
                    log(f"账号{index} · 阶段5 ⏭️ 退出登录已关闭 · 耗时0.00秒")
                else:
                    stage(number, name + "（离线模拟）", lambda: None)
            log(f"账号{index} DRY_RUN_OK：仅验证流程，未验证真实登录或签到")
        else:
            client = Client()

            def login():
                client.request(BASE)
                message, response = response_message(client.request(BASE + "/wp-admin/admin-ajax.php", {
                    "action": "user_login", "username": username, "password": password, "rememberme": 1,
                }))
                if not verified_message(message, "登录成功"):
                    raise TaskError("未确认登录成功")
                identity = public_identity(response)
                if identity:
                    log(f"账号{index} 官方账户身份：{identity}")

            stage(1, "登录", login)
            authenticated = True

            def before():
                nonlocal page
                page = client.request(BASE + "/user")
                return points(page)

            initial = stage(2, "读取签到前积分", before)

            def checkin():
                message, _ = response_message(client.request(BASE + "/wp-admin/admin-ajax.php", {
                    "action": "user_qiandao", "nonce": nonce(page),
                }))
                if verified_message(message, "今日已签到"):
                    return "alreadyComplete"
                if not verified_message(message, "签到成功"):
                    raise TaskError("未确认签到成功，不自动重试写操作")

            stage(3, "每日签到", checkin)

            def after():
                nonlocal page
                page = client.request(BASE + "/user")
                return points(page)

            balance = stage(4, "读取签到后积分", after)
            gain = balance - initial
            log(f"账号{index} 本次获得积分：{gain}；累计积分：{balance}")
    except TaskError:
        pass
    finally:
        if authenticated and enabled("BUGUTV_LOGOUT", "1"):
            def logout():
                current = client.request(BASE + "/user")
                client.request(logout_url(current))
                # 退出后个人空间不应再提供账户积分。
                probe = client.request(BASE + "/user")
                try:
                    points(probe)
                except TaskError:
                    if re.search(r'\bname\s*=\s*[\"\'](?:username|log)[\"\']', probe, re.I) and re.search(r'\bname\s*=\s*[\"\'](?:password|pwd)[\"\']', probe, re.I):
                        return
                    raise TaskError("退出后未确认登录页面，页面结构可能变化") from None
                raise TaskError("退出后仍可读取账户积分，未确认退出成功")
            try:
                stage(5, "退出登录", logout)
            except TaskError:
                pass
        elif not dry:
            stats["total"] += 1
            stats["skipped"] += 1
            log(f"账号{index} · 阶段5 ⏭️ 退出登录未执行 · 耗时0.00秒")
        stats["durationSeconds"] = round(time.monotonic() - started, 2)
        stats["account"] = index
        if balance is not None:
            stats["points"] = str(balance)
            stats["pointsGained"] = str(gain)
        stats["status"] = "failure" if stats["failed"] else ("dry-run" if dry else "success")
        log(f"账号{index} 统计：总任务{stats['total']}，成功{stats['success']}，已完成{stats['alreadyComplete']}，跳过{stats['skipped']}，失败{stats['failed']}，耗时{stats['durationSeconds']}秒")
    return stats


def deny_network(*args, **kwargs):
    raise OSError("dry-run network disabled")


def offline_guard():
    socket.socket.connect = deny_network
    socket.socket.connect_ex = deny_network
    socket.create_connection = deny_network
    socket.getaddrinfo = deny_network


def notification_worker():
    # 单独的标准Python进程隔离第三方通知日志和超时，避免泄漏其配置。
    import contextlib
    import io
    payload = json.loads(sys.stdin.read())
    if payload["dry"]:
        offline_guard()
    outcome = "通知失败（详情已脱敏），已保留业务退出码"
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            try:
                import notify
                send = notify.send
            except ImportError:
                paths = []
                if os.environ.get("QINGLONG_NOTIFY_DIR"):
                    paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
                paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
                send = None
                for path in paths:
                    if path.is_file():
                        spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        send = module.send
                        break
                if send is None:
                    outcome = "通知模块不可用，已保留业务退出码"
                else:
                    send(TITLE, payload["body"])
                    outcome = "已调用青龙通知"
            else:
                send(TITLE, payload["body"])
                outcome = "已调用青龙通知"
        except Exception:
            pass
    print(outcome)


def notify_summary(body, dry):
    if not enabled("QINGLONG_NOTIFY", "1"):
        return "已关闭"
    try:
        child = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--notify-worker"],
                               input=json.dumps({"body": body, "dry": dry}), text=True,
                               capture_output=True, timeout=10)
        allowed = {"已调用青龙通知", "通知模块不可用，已保留业务退出码", "通知失败（详情已脱敏），已保留业务退出码"}
        result = child.stdout.strip() if child.stdout.strip() in allowed else "通知失败（详情已脱敏），已保留业务退出码"
    except Exception:
        result = "通知不可用或超时，已保留业务退出码"
    # 原可选Server酱能力；dry-run绝不发送网络请求。
    key = os.environ.get("BUGUTV_SERVER_SEND_KEY", os.environ.get("sever_jiang_send_key", ""))
    if key:
        if dry:
            result += "；Server酱离线跳过"
        elif not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            result += "；Server酱参数无效"
        else:
            try:
                host = "https://sctapi.ftqq.com/" if "SCT" in key else "https://sc.ftqq.com/"
                message, response = response_message(Client().request(host + key + ".send", {"text": TITLE, "desp": body.replace("\n", "\n\n")}))
                ok = any(type(response.get(field)) is int and response[field] == 0 for field in ("errno", "code"))
                result += "；Server酱" + ("成功" if ok else "失败")
            except Exception:
                result += "；Server酱失败（详情已脱敏）"
    return result


def main():
    begin = time.monotonic()
    dry = enabled("BUGUTV_DRY_RUN")
    if dry:
        # 即使第三方notify模块尝试联网，离线模式也禁止socket连接。
        offline_guard()
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{time.strftime('%Y-%m-%d %H:%M:%S')}；模式：{'离线预演' if dry else '正式运行'}")
    lines = [line for line in os.environ.get("BUGUTV_ACCOUNTS", "").splitlines() if line.strip()]
    log(f"账号数量：{len(lines)}")
    results = []
    configuration_error = not lines
    if not lines:
        log("❌ 配置错误：请设置BUGUTV_ACCOUNTS，每行用户名|密码")
    for index, line in enumerate(lines, 1):
        username, separator, password = line.partition("|")
        if not separator or not username.strip() or not password:
            configuration_error = True
            log(f"账号{index} · 阶段1 ❌ 凭据格式错误 · 耗时0.00秒")
            row = {"account": index, "status": "failure", "total": 1, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 1, "durationSeconds": 0}
            results.append(row)
            log(f"账号{index} 统计：总任务1，成功0，已完成0，跳过0，失败1，耗时0秒")
            continue
        results.append(account_run(index, username, password, dry))
    failed = sum(row["status"] == "failure" for row in results)
    succeeded = len(results) - failed
    exit_code = 1 if failed or configuration_error else 0
    status = ("configuration-error" if configuration_error else
              "partial-failure" if failed and succeeded else "failure" if failed else
              "dry-run" if dry else "success")
    totals = {key: sum(row[key] for row in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    body = f"状态：{status}\n账号总数：{len(lines)}；成功数：{succeeded}；失败数：{failed}\n子任务：成功{totals['success']}，已完成{totals['alreadyComplete']}，跳过{totals['skipped']}，失败{totals['failed']}"
    for row in results:
        body += f"\n账号{row['account']}：{row['status']}"
        if "points" in row:
            body += f"；本次获得积分{row['pointsGained']}；累计积分{row['points']}"
    if dry:
        body += "\n离线预演未验证真实业务。"
    notification = notify_summary(body, dry)
    finished = time.strftime('%Y-%m-%d %H:%M:%S')
    duration = round(time.monotonic() - begin, 2)
    log("----------------------------------------")
    log(body.replace("\n", "；"))
    log(f"总任务{totals['total']}；耗时{duration}秒；完成时间：{finished}")
    log(f"通知状态：{notification}；最终状态：{status}")
    summary = {"task": "bugutv", "mode": "dry-run" if dry else "live", "status": status,
               "accounts": len(lines), "success": succeeded, "failed": failed,
               "configurationError": configuration_error, "stages": totals, "results": results,
               "durationSeconds": duration, "finishedAt": finished, "notification": notification, "exitCode": exit_code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    if sys.argv[1:] == ["--notify-worker"]:
        notification_worker()
    else:
        sys.exit(main())
