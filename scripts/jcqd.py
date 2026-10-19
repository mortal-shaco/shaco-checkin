#!/usr/bin/env python3
# name: jcqd 多站签到
# cron: 5 1 * * *
# 上游：Rookie-wb-WH/ql_scripts，jcqd.py
# 来源提交：08e5c06461c4a0112ea3735f48fe671734bb7707
# SPDX-License-Identifier: MIT
# 上游未提供作者版权行；保留其项目归属，适用 MIT 许可。
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""ikuuu + v2free + gw树洞

上游注册地址（仅保留来源说明，不自动访问）：
v2free: https://w1.v2free.top/auth/register?code=O9dv
ikuuu: https://ikuuu.art/auth/register?code=OlHp
gw树洞: https://kkone.io/auth/register?code=4fMxiN

JCQD_ACCOUNTS 每个非空行填写 登录邮箱|密码，仅按第一个 | 分割。
同一行用于所选站点，原脚本要求这些站点的用户名和密码相同。
兼容旧单账号 jcuname / jcpasswd；新变量配置时优先使用新变量。
JCQD_TASKS 默认 ikuuu；可填写 ikuuu,v2free,gw，仅显式开启其他站点。
不同站点凭据不同请分别建立青龙任务，设置对应站点和账号行。
JCQD_DRY_RUN=1 完全断网预演，包含通知不联网、不导入通知模块。
IKUUU_BASE_URL 可指定经本人确认的官方 HTTPS 域名，绕过导航页。
默认从 https://ikuuu.club/ 提取且仅接受 ikuuu.art / ikuuu.club 域名。
如官方更换域名，请人工核实后设置 IKUUU_BASE_URL，勿填不可信站点。
QINGLONG_NOTIFY 未设置时按上架状态；设为 0/false/no/off 关闭通知。
依赖：青龙 Python 依赖管理安装 requests；Python 3.9 或以上。
每日 09:00 为维护版建议定时；上游没有声明定时表达式。
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
        _ql_notify_identities = ('757bc6292780fb17', 'scripts/jcqd.py', 'jcqd.py', 'jcqd')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import importlib
import importlib.util
import json
import os
import random
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

DISABLED = {"0", "false", "no", "off"}
TITLE = "jcqd 多站签到"
UA = "Mozilla/5.0 (compatible; QinglongCheckin/1.0)"
TIMEOUT = (8, 20)
LIMIT = 262144


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    pass


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href" and v)


def origin(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.port not in (None, 443)
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise ValueError()
        return f"https://{parsed.hostname.lower()}"
    except ValueError:
        raise TaskError("站点配置必须是无路径、无用户信息的 HTTPS 官方域名") from None


def response_body(response):
    try:
        if response.status_code != 200:
            raise TaskError("HTTP 状态异常或重定向被拒绝")
        body = bytearray()
        for block in response.iter_content(8192):
            body.extend(block)
            if len(body) > LIMIT:
                raise TaskError("响应超过安全大小限制")
        return bytes(body)
    finally:
        response.close()


def request_json(session, url, **kwargs):
    response = session.post(url, timeout=TIMEOUT, allow_redirects=False,
                            stream=True, **kwargs)
    try:
        result = json.loads(response_body(response))
    except (ValueError, UnicodeError):
        raise TaskError("接口未返回有效 JSON") from None
    if not isinstance(result, dict):
        raise TaskError("接口响应结构不符合契约")
    return result


def successful(result):
    # 上游 SSPanel 接口的 ret=1 为成功；不以非空 msg 判定成功。
    return type(result.get("ret")) is int and result["ret"] == 1


def already_complete(result):
    message = result.get("msg")
    return (type(result.get("ret")) is int and result["ret"] == 0
            and isinstance(message, str)
            and any(text in message for text in ("今日已签到", "今天已签到", "您今日已签到", "今天已经签到")))


def identity(result, secrets):
    # 仅从明确命名的公开身份字段读取，绝不输出原始响应。
    containers = [result]
    for field in ("data", "user"):
        if isinstance(result.get(field), dict):
            containers.append(result[field])
    for container in containers:
        for key in ("nickname", "username", "display_name", "public_uid"):
            value = container.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                value = str(value)
                if (value and not any(secret and secret in value for secret in secrets)
                        and "@" not in value
                        and (key == "public_uid" or not any(c.isdigit() and value[i:i + 11].isdigit()
                                    for i, c in enumerate(value) if i + 11 <= len(value)))):
                    return json.dumps(value, ensure_ascii=False)
    return None


def ikuuu_origin(requests):
    explicit = os.getenv("IKUUU_BASE_URL", "").strip()
    if explicit:
        return origin(explicit)
    # 导航页请求永远不携带账号数据或登录 cookie。
    with requests.Session() as navigation:
        navigation.trust_env = False
        response = navigation.get("https://ikuuu.club/", headers={"User-Agent": UA},
                                  timeout=TIMEOUT, allow_redirects=False, stream=True)
        parser = Links()
        parser.feed(response_body(response).decode("utf-8"))
    candidates = set()
    for href in parser.links:
        try:
            candidate = origin(urljoin("https://ikuuu.club/", href))
            host = urlsplit(candidate).hostname
            if host in {"ikuuu.art", "ikuuu.club"}:
                candidates.add(candidate)
        except TaskError:
            continue
    if not candidates:
        raise TaskError("导航页没有可信官方域名；请核实并配置 IKUUU_BASE_URL")
    return random.choice(sorted(candidates))


def perform(requests, task, email, password):
    base = {"v2free": "https://w1.v2free.top", "gw": "https://m.mmomm.io"}.get(task)
    if task == "ikuuu":
        base = ikuuu_origin(requests)
    with requests.Session() as session:
        session.trust_env = False
        session.headers.update({"User-Agent": UA, "Origin": base})
        logged_in = request_json(session, base + "/auth/login",
                                 data={"email": email, "passwd": password})
        if not successful(logged_in):
            raise TaskError("登录未得到 ret=1，已停止该站点签到")
        label = identity(logged_in, (email, password))
        log("登录验证成功" + (f"；官方身份：{label}" if label else ""))
        result = request_json(session, base + "/user/checkin")
        label = identity(result, (email, password))
        if label:
            log(f"官方身份：{label}")
        if successful(result):
            return "success"
        if already_complete(result):
            return "alreadyComplete"
        raise TaskError("签到未得到明确业务成功或今日已签到结果")


def parse_config():
    selected = os.getenv("JCQD_TASKS", "ikuuu").split(",")
    tasks = list(dict.fromkeys(item.strip() for item in selected))
    if not tasks or any(item not in {"ikuuu", "v2free", "gw"} for item in tasks):
        raise TaskError("JCQD_TASKS 仅支持 ikuuu,v2free,gw")
    if "JCQD_ACCOUNTS" in os.environ:
        accounts = []
        for line in os.environ["JCQD_ACCOUNTS"].splitlines():
            if not line.strip():
                continue
            email, delimiter, password = line.partition("|")
            if not delimiter or not email.strip() or not password:
                accounts.append(("", ""))
            else:
                accounts.append((email.strip(), password))
    else:
        email, password = os.getenv("jcuname", ""), os.getenv("jcpasswd", "")
        accounts = [(email, password)] if email.strip() and password else []
    if not accounts:
        raise TaskError("请配置 JCQD_ACCOUNTS 或旧单账号 jcuname / jcpasswd")
    if os.getenv("IKUUU_BASE_URL", "").strip():
        origin(os.environ["IKUUU_BASE_URL"].strip())
    return tasks, accounts


def notify(summary, dry_run):
    if os.getenv("QINGLONG_NOTIFY", "1").lower().strip() in DISABLED:
        return "已关闭"
    if dry_run:
        # 通知通常也使用网络，因此断网预演只构建并展示脱敏摘要。
        log("通知预演：" + summary)
        return "断网预演"
    try:
        try:
            module = importlib.import_module("notify")
        except ImportError:
            paths = []
            directory = os.getenv("QINGLONG_NOTIFY_DIR")
            if directory:
                paths.append(Path(directory) / "notify.py")
            paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
            if module is None:
                log("⚠️ 青龙通知模块不可用，保留业务退出码")
                return "不可用"
        module.send(TITLE, summary)
        return "已发送"
    except Exception:
        log("⚠️ 通知发送失败，保留业务退出码")
        return "失败"


def main():
    started = time.monotonic()
    dry_run = os.getenv("JCQD_DRY_RUN", "0").lower().strip() in {"1", "true", "yes", "on"}
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry_run else '正式执行'}")
    stats = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    total = passed = failed = 0
    configuration_error = False
    try:
        tasks, accounts = parse_config()
        total = len(accounts)
        log(f"账号总数：{total}；所选任务：{','.join(tasks)}")
        requests = None
        if not dry_run:
            try:
                requests = importlib.import_module("requests")
            except ImportError:
                raise TaskError("缺少 requests，请在青龙 Python 依赖管理安装") from None
        for number, (email, password) in enumerate(accounts, 1):
            account_start = time.monotonic()
            counts = dict.fromkeys(stats, 0)
            for stage, task in enumerate(tasks, 1):
                step_start = time.monotonic()
                log(f"账号 {number} 阶段 {stage}/{len(tasks)}：{task} 登录与签到")
                try:
                    if not email or not password:
                        raise TaskError("账号格式错误，应为每行 登录邮箱|密码；该账号未发起请求")
                    if dry_run:
                        status = "skipped"
                        log("⏭️ DRY_RUN_OK：参数和任务有效；未调用导航、登录或签到接口")
                    else:
                        status = perform(requests, task, email, password)
                        log("✅ 签到业务成功" if status == "success" else "☑️ 今日已签到")
                except TaskError as exc:
                    status = "failed"
                    log(f"❌ {exc}")
                except Exception:
                    status = "failed"
                    log("❌ 网络、证书或接口处理失败；不展示异常内容及原始响应")
                counts[status] += 1
                stats[status] += 1
                log(f"账号 {number} 阶段 {stage} 耗时：{time.monotonic() - step_start:.2f} 秒")
            if counts["failed"]:
                failed += 1
            else:
                passed += 1
            log(f"账号 {number} 统计：总任务 {len(tasks)}，成功 {counts['success']}，已完成 {counts['alreadyComplete']}，跳过 {counts['skipped']}，失败 {counts['failed']}；耗时 {time.monotonic() - account_start:.2f} 秒")
    except TaskError as exc:
        configuration_error = True
        log(f"❌ 配置错误：{exc}")
    exit_code = 1 if failed or configuration_error else 0
    status = ("configuration-error" if configuration_error else
              "partial-failure" if failed and passed else "failure" if failed else
              "dry-run" if dry_run else "success")
    summary = f"状态：{status}；账号总数 {total}，成功数 {passed}，失败数 {failed}；子任务成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}"
    log("----------------------------------------")
    log("任务统计：" + summary)
    notification = notify(summary, dry_run)
    log(f"通知状态：{notification}；总耗时：{time.monotonic() - started:.2f} 秒")
    log(f"完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"status": status, "mode": "dry-run" if dry_run else "live",
          "accounts": total, "successfulAccounts": passed, "failedAccounts": failed,
          "tasks": stats, "notification": notification, "exitCode": exit_code}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
