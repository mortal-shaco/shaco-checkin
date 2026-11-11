#!/usr/bin/env python3
# name: 今日校园同学列表
# cron: 59 10 * * *
# SPDX-License-Identifier: GPL-3.0-only
# 来源：jerryshell/cpdaily-api，原文件 find_student.py
# 上游提交：02a6360cfb6c2a79e5e019a19ee4e9324ed15648
# 本维护版本依 GPL-3.0-only 分发：https://www.gnu.org/licenses/gpl-3.0.html
"""同学列表接口。

CPDAILY_ACCOUNTS：每个非空行一个 JSON 对象，含 headers 和 cookies 对象；
从本人授权登录后的 findStudent 请求复制请求头与 Cookie。不得分享凭据。
CPDAILY_RESPONSE_RULE：JSON 对象，必须含 successPath、successValue、studentsPath。
从同一接口的已知成功响应核对业务成功字段与同学数组字段；点号分隔对象路径。
不猜测缺失的上游 config 或业务响应结构。仅显示白名单公开身份，不输出响应正文。
上游未声明定时；本维护版本提供每日 09:00 的建议定时，可在青龙中调整。
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
        _ql_notify_identities = ('9698197c18a7c2eb', 'scripts/find_student.py', 'find_student.py', 'find_student')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
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
from http.cookies import SimpleCookie


TITLE = "今日校园同学列表"
CATALOG = "9698197c18a7c2eb"
ENDPOINT = "https://www.cpdaily.com/v6/user/findStudent"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
MAX_BYTES = 1024 * 1024


class TaskError(Exception):
    """仅保存可公开的固定错误消息。"""


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def integer(name, default, low, high):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        raise TaskError(f"{name} 必须为整数") from None
    if not low <= value <= high:
        raise TaskError(f"{name} 超出允许范围 {low}～{high}")
    return value


def parse_account(line):
    try:
        account = json.loads(line)
    except (ValueError, TypeError):
        raise TaskError("账号配置不是有效 JSON 对象") from None
    if not isinstance(account, dict):
        raise TaskError("账号配置必须为对象")
    headers, cookies = account.get("headers", {}), account.get("cookies", {})
    for value in (headers, cookies):
        if not isinstance(value, dict) or any(
            not isinstance(k, str) or not k or not isinstance(v, str)
            or any(c in k + v for c in "\r\n\x00") for k, v in value.items()
        ):
            raise TaskError("headers 和 cookies 必须是无换行的字符串映射")
    if not any(value.strip() for value in cookies.values()) and not any(k.lower() in {"cookie", "authorization"} and v.strip()
                               for k, v in headers.items()):
        raise TaskError("账号缺少 Cookie 或 Authorization 凭据")
    if cookies and any(k.lower() == "cookie" for k in headers):
        raise TaskError("Cookie 只能配置在 headers 或 cookies 中的一处")
    if any(k.lower() in {"host", "content-length", "transfer-encoding", "proxy-authorization"}
           for k in headers):
        raise TaskError("请移除 Host、长度或代理认证等传输层请求头")
    result = dict(headers)
    if cookies:
        try:
            jar = SimpleCookie()
            for key, value in cookies.items():
                jar[key] = value
            result["Cookie"] = "; ".join(item.OutputString() for item in jar.values())
        except Exception:
            raise TaskError("cookies 字段格式无效") from None
    return result


def parse_rule(dry):
    raw = os.environ.get("CPDAILY_RESPONSE_RULE", "")
    if not raw and dry:
        return None
    try:
        rule = json.loads(raw)
        if not isinstance(rule, dict):
            raise ValueError()
        for key in ("successPath", "studentsPath"):
            if not isinstance(rule.get(key), str) or not rule[key] or any(
                not segment for segment in rule[key].split(".")
            ):
                raise ValueError()
        if "identityPath" in rule and (not isinstance(rule["identityPath"], str) or not rule["identityPath"]):
            raise ValueError()
        if "successValue" not in rule or type(rule["successValue"]) not in (str, int, bool):
            raise ValueError()
    except (TypeError, ValueError):
        raise TaskError("请配置经成功响应核对的 CPDAILY_RESPONSE_RULE：successPath、successValue、studentsPath") from None
    return rule


def field(data, path):
    for segment in path.split("."):
        if not isinstance(data, dict) or segment not in data:
            raise TaskError("响应缺少配置字段，请核对响应契约")
        data = data[segment]
    return data


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 防止会话凭据随跳转转发。
        return None


def query(headers, limits, offset, timeout, rule):
    request = urllib.request.Request(
        ENDPOINT + "?" + urllib.parse.urlencode({"limits": limits, "offset": offset}),
        headers=headers, method="GET",
    )
    try:
        # 不读取代理环境，避免意外将账号凭据交给代理。
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise TaskError("接口 HTTP 状态不成功")
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise TaskError("接口响应超过安全大小限制")
        data = json.loads(raw)
    except urllib.error.HTTPError as error:
        raise TaskError(f"接口 HTTP 错误：{error.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError("请求失败或超时，请检查连接及凭据") from None
    except (ValueError, UnicodeError):
        raise TaskError("接口响应不是有效 JSON") from None
    actual = field(data, rule["successPath"])
    expected = rule["successValue"]
    if type(actual) is not type(expected) or actual != expected:
        raise TaskError("业务成功判据未满足，请核对登录状态及响应契约")
    students = field(data, rule["studentsPath"])
    if not isinstance(students, list) or any(not isinstance(item, dict) for item in students):
        raise TaskError("同学列表字段不是对象数组")
    return data, students


def safe_identity(value, secrets):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = str(value)
    # 保留安全公开身份原值；敏感字段、手机号及已知凭据均不展示。
    if any(secret and secret in text for secret in secrets) or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
        return None
    if len(text) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in text):
        return None
    return value


def identities(item, secrets):
    result = {}
    for key in ("nickname", "nickName", "username", "userName", "displayName", "publicUid", "uid", "userId"):
        if key in item:
            value = safe_identity(item[key], secrets)
            if value is not None:
                result[key] = value
    return result


def notify_selected():
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return False
    selection = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selection is not None:
        selectors = re.split(r"[,;\s]+", selection.strip())
        names = {CATALOG, "candidate.py", Path(__file__).name, "find_student.py",
                 "scripts/find_student.py", "scripts/candidate.py"}
        return any(fnmatch.fnmatchcase(name, pattern) for name in names
                   for pattern in selectors if pattern)
    # listed-only 默认不订阅；显式全局开启时发送。
    return switch in TRUE


def notify(summary, dry):
    if dry:
        log("通知：断网预演已生成脱敏摘要，跳过外部投递")
        return "dry-run"
    if not notify_selected():
        log("通知：未订阅或已关闭")
        return "disabled"
    body = (f"账号总数 {summary['accounts']}，成功 {summary['success']}，"
            f"失败 {summary['failed']}；状态 {summary['status']}")
    directories = [Path(__file__).resolve().parent]
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        directories.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]))
    directories += [Path("/ql/data/scripts"), Path("/ql/scripts")]
    # 子进程隔离通知输出和异常，通知失败不覆盖业务退出码。
    python_code = ("import sys,importlib.util; "
                   "p=sys.argv[1]; "
                   "s=importlib.util.spec_from_file_location('ql_task_notify',p); "
                   "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                   "m.send(sys.argv[2],sys.argv[3])")
    commands = []
    try:
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin and Path(spec.origin).is_file():
            commands.append([sys.executable, "-c", python_code, spec.origin, TITLE, body])
    except Exception:
        pass
    for directory in directories:
        if (directory / "notify.py").is_file():
            commands.append([sys.executable, "-c", python_code, str(directory / "notify.py"), TITLE, body])
        if (directory / "sendNotify.js").is_file():
            js = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
            commands.append(["node", "-e", js, str(directory / "sendNotify.js"), TITLE, body])
    for command in commands:
        try:
            # 通知组件无需取得业务凭据。
            env = {key: value for key, value in os.environ.items() if not key.startswith("CPDAILY_")}
            result = subprocess.run(command, env=env, timeout=20, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, check=False)
            if result.returncode == 0:
                log("通知：已投递")
                return "sent"
        except (OSError, subprocess.TimeoutExpired):
            pass
    log("通知：组件不可用或投递失败，保留业务退出码")
    return "unavailable"


def main():
    started = time.monotonic()
    dry = os.environ.get("CPDAILY_DRY_RUN", "0").strip().lower() in TRUE
    lines = [line.strip() for line in os.environ.get("CPDAILY_ACCOUNTS", "").splitlines() if line.strip()]
    log(f"===== {TITLE} =====")
    log(f"开始时间：{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}")
    log(f"模式：{'断网预演' if dry else '正式运行'}；账号数：{len(lines)}")
    summary = {"accounts": len(lines), "success": 0, "failed": 0, "skipped": 0,
               "alreadyComplete": 0, "students": 0, "dryRun": dry}
    config_error = False
    try:
        log("阶段 1：检查分页参数与响应契约")
        if not lines:
            raise TaskError("未配置 CPDAILY_ACCOUNTS")
        limits = integer("CPDAILY_LIMITS", 20, 1, 1000)
        offset = integer("CPDAILY_OFFSET", 0, 0, 2147483647)
        timeout = integer("CPDAILY_TIMEOUT", 15, 1, 60)
        rule = parse_rule(dry)
        log(f"阶段 1 完成：limits={limits}，offset={offset}，耗时 {time.monotonic() - started:.2f} 秒")
    except TaskError as error:
        log(f"❌ 配置错误：{error}")
        summary["failed"] = len(lines)
        config_error = True
    if not config_error:
        for index, line in enumerate(lines, 1):
            begin = time.monotonic()
            success = False
            log(f"账号 {index} / 阶段 2：检查账号配置")
            try:
                headers = parse_account(line)
                secrets = list(headers.values())
                for key, value in headers.items():
                    if key.lower() == "cookie":
                        try:
                            cookie_jar = SimpleCookie()
                            cookie_jar.load(value)
                            secrets.extend(morsel.value for morsel in cookie_jar.values())
                        except Exception:
                            pass
                    elif key.lower() == "authorization":
                        secrets.append(value.split(" ", 1)[-1])
                cookie_values = json.loads(line).get("cookies", {}).values()
                secrets.extend(cookie_values)
                log(f"账号 {index} / 阶段 2 完成：凭据格式有效，耗时 {time.monotonic() - begin:.2f} 秒")
                request_start = time.monotonic()
                log(f"账号 {index} / 阶段 3：查询同学列表")
                if dry:
                    log(f"账号 {index}：DRY_RUN_OK；GET 参数已校验，未访问网络，未验证业务成功")
                    summary["skipped"] += 1
                else:
                    data, students = query(headers, limits, offset, timeout, rule)
                    if rule.get("identityPath"):
                        owner = field(data, rule["identityPath"])
                        if not isinstance(owner, dict):
                            raise TaskError("当前账号身份字段不是对象")
                        identity = identities(owner, secrets)
                        if identity:
                            log(f"账号 {index} 身份：{json.dumps(identity, ensure_ascii=False)}")
                    # 若响应明确提供当前账号身份，则原样显示白名单字段。
                    if isinstance(data, dict):
                        for key in ("user", "currentUser"):
                            if isinstance(data.get(key), dict):
                                identity = identities(data[key], secrets)
                                if identity:
                                    log(f"账号 {index} 身份：{json.dumps(identity, ensure_ascii=False)}")
                    public_students = [identities(student, secrets) for student in students]
                    print(json.dumps({"account": index, "students": public_students,
                                      "count": len(students)}, ensure_ascii=False), flush=True)
                    summary["students"] += len(students)
                    summary["success"] += 1
                    log(f"✅ 账号 {index}：QUERY_SUCCESS，业务判据通过，返回 {len(students)} 位同学")
                success = True
                log(f"账号 {index} / 阶段 3 完成：耗时 {time.monotonic() - request_start:.2f} 秒")
            except TaskError as error:
                log(f"❌ 账号 {index}：{error}")
            except Exception:
                log(f"❌ 账号 {index}：处理异常，已隐藏异常详情")
            if not success:
                summary["failed"] += 1
            log(f"账号 {index} 统计：总任务 1，成功 {int(success and not dry)}，"
                f"已完成 0，跳过 {int(success and dry)}，失败 {int(not success)}，"
                f"耗时 {time.monotonic() - begin:.2f} 秒")
    exit_code = 1 if config_error or summary["failed"] else 0
    summary["status"] = ("configuration-error" if config_error else
                         "partial-failure" if summary["failed"] and summary["success"] else
                         "failure" if summary["failed"] else "dry-run" if dry else "success")
    summary["notification"] = notify(summary, dry)
    summary["elapsedSeconds"] = round(time.monotonic() - started, 3)
    summary["finishedAt"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    summary["exitCode"] = exit_code
    log("----------------------------------------")
    log(f"账号统计：总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}，预演跳过 {summary['skipped']}")
    log(f"子任务统计：成功 {summary['success']}，已完成 0，跳过 {summary['skipped']}，失败 {summary['failed']}")
    log(f"总耗时：{summary['elapsedSeconds']} 秒；完成时间：{summary['finishedAt']}")
    log(f"最终状态：{summary['status']}；通知：{summary['notification']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
