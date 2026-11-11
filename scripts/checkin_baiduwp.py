#!/usr/bin/env python3
# name: 百度网盘签到
# cron: 1 11 * * *
# new Env('百度网盘签到')
"""百度网盘每日签到、每日答题及会员等级和成长值查询。

来源 f1shQAQ/ql-scripts/checkin_baiduwp.py，许可 MIT。
原始接口参考 Sitoi/dailycheckin 的 baiduwp 模块（MIT）。
保留原来源署名，维护版本使用 Python 标准库独立实现 HTTP。

BAIDUWP_COOKIE 必填，每个非空行一个账号，可填完整 Cookie 或 BDUSS 值。
登录 https://pan.baidu.com，使用浏览器开发者工具的网络面板，查看本人
已登录请求的 Cookie 请求头并复制完整值，建议保留 BDUSS 与 STOKEN。
请勿分享该值。仅 BDUSS 的兼容输入可能因服务端要求 STOKEN 而失败。
账号之间仅支持换行，旧的 && 分隔需迁移为换行。
BAIDUWP_DRY_RUN=1 完全离线校验配置并预演，不执行 HTTP 或通知外发。
QINGLONG_NOTIFY=1 强制尝试青龙通知，0 关闭，默认 auto 仅通知选择器命中的脚本。
QINGLONG_NOTIFY_SCRIPTS 可用目录相对路径、文件名、glob 或目录编号匹配，
支持逗号、分号和空白分隔，* 代表全部，未配置名单时默认名单为空。
QINGLONG_NOTIFY_DIR 可指定含 notify.py 或 sendNotify.js 的青龙通知目录。
通知失败不会覆盖业务退出码，配置错误或任一账号失败均非零退出。
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
        _ql_notify_identities = ('39580db6919e11a5', 'scripts/checkin_baiduwp.py', 'checkin_baiduwp.py', 'checkin_baiduwp')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime as dt
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

TITLE = "百度网盘签到"
CATALOG_ID = "39580db6919e11a5"
API = "https://pan.baidu.com"
COMMON = {"app_id": "250528", "web": "5"}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
MAX_RESPONSE = 1024 * 1024


class TaskError(Exception):
    """只携带本地生成的脱敏错误。"""


def log(message):
    print(f"[{dt.datetime.now():%H:%M:%S}] {message}", flush=True)


def find_key(value, key):
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            result = find_key(child, key)
            if result is not None:
                return result
    elif isinstance(value, list):
        for child in value:
            result = find_key(child, key)
            if result is not None:
                return result
    return None


def check_codes(data):
    """不推测未提供证据的非零业务码语义。"""
    if not isinstance(data, dict):
        raise TaskError("接口 JSON 结构无效")
    for key in ("errno", "err_no", "error_code", "code"):
        code = data.get(key)
        if code is not None and (isinstance(code, bool) or str(code) != "0"):
            raise TaskError("接口返回非成功业务码，请检查登录状态或服务接口")
    for key in ("data", "result"):
        if isinstance(data.get(key), dict):
            check_codes(data[key])


def number(value):
    if isinstance(value, bool) or value is None:
        raise TaskError("接口缺少有效数值字段")
    if not re.fullmatch(r"\d+(?:\.\d+)?", str(value)):
        raise TaskError("接口数值字段格式异常")
    return str(value)


def normalize_cookie(value):
    if "&&" in value:
        raise TaskError("账号请使用换行分隔，请将旧的 && 分隔迁移为换行")
    if re.fullmatch(r"[A-Za-z0-9~._%+/-]+={0,2}", value):
        value = "BDUSS=" + value
    if any(ord(char) < 32 or ord(char) > 255 for char in value):
        raise TaskError("Cookie 含不支持的字符")
    fields = {}
    for item in value.split(";"):
        if not item.strip():
            continue
        key, delimiter, credential = item.strip().partition("=")
        if not delimiter or not key or not credential:
            raise TaskError("Cookie 格式错误")
        fields[key] = credential
    if not fields.get("BDUSS"):
        raise TaskError("Cookie 缺少 BDUSS")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口发生重定向，已停止该请求以保护凭据")


class Client:
    def __init__(self, cookie):
        self.cookie = cookie
        self.opener = urllib.request.build_opener(NoRedirect())

    def get(self, path, **params):
        query = urllib.parse.urlencode({**COMMON, **params}, doseq=True)
        request = urllib.request.Request(API + path + "?" + query, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
            "Referer": API + "/wap/svip/growth/task",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie": self.cookie,
        })
        try:
            with self.opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise TaskError("接口 HTTP 状态异常")
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise TaskError("接口响应超过大小限制")
            data = json.loads(raw.decode("utf-8-sig"))
        except TaskError:
            raise
        except Exception:
            raise TaskError("接口请求失败、超时或 JSON 无效") from None
        check_codes(data)
        return data


def already_complete(data, phrases):
    # 缺少数值字段时，必须同时有显式成功码及明确的已完成提示。
    code_present = any(str(data.get(key)) == "0" for key in ("errno", "err_no", "error_code", "code"))
    message = find_key(data, "show_msg") or find_key(data, "error_msg") or ""
    return code_present and isinstance(message, str) and any(phrase in message for phrase in phrases)


def signin(client):
    data = client.get("/rest/2.0/membership/level", method="signin")
    points = find_key(data, "points")
    if points is not None:
        return "success", "签到成功，成长值 +" + number(points)
    if already_complete(data, ("今日已签到", "今天已签到", "已经签到", "已签到")):
        return "alreadyComplete", "今日已签到"
    raise TaskError("签到未返回成长值或可验证的已完成结果")


def answer_question(client):
    data = client.get("/act/v2/membergrowv2/getdailyquestion")
    ask_id = find_key(data, "ask_id")
    answer = find_key(data, "answer")
    if ask_id is None or answer is None:
        if already_complete(data, ("今日已答题", "今天已答题", "已经答过", "已答题")):
            return "alreadyComplete", "今日已答题"
        raise TaskError("每日题目缺少题号或答案，无法确认任务完成")
    if isinstance(ask_id, bool) or not isinstance(ask_id, (str, int)) or not str(ask_id):
        raise TaskError("每日题目题号格式异常")
    answers = answer if isinstance(answer, list) else [answer]
    if not answers or any(isinstance(item, bool) or not isinstance(item, (str, int)) or not str(item) for item in answers):
        raise TaskError("每日题目答案格式异常")
    time.sleep(2)
    data = client.get("/act/v2/membergrowv2/answerquestion", ask_id=ask_id, answer=answer)
    score = find_key(data, "score")
    if score is not None:
        return "success", "答题成功，成长值 +" + number(score)
    if already_complete(data, ("今日已答题", "今天已答题", "已经答过", "已答题")):
        return "alreadyComplete", "今日已答题"
    raise TaskError("答题未返回得分或可验证的已完成结果")


def user_info(client):
    data = client.get("/rest/2.0/membership/user", method="query")
    level = number(find_key(data, "current_level"))
    value = number(find_key(data, "current_value"))
    for key in ("nickname", "username", "display_name", "uname", "uk", "public_uid"):
        identity = find_key(data, key)
        if isinstance(identity, (str, int)) and not isinstance(identity, bool) and str(identity):
            identity = str(identity)
            credentials = [item.partition("=")[2] for item in client.cookie.split(";")]
            if any(secret and secret in identity for secret in credentials) or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", identity):
                continue
            # JSON 转义控制字符，保留官方非敏感身份的文本内容。
            log("账号身份 " + json.dumps(identity, ensure_ascii=False))
            break
    return "success", f"会员等级 {level}，成长值 {value}"


def notify_enabled():
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    selectors = re.split(r"[,;\s]+", os.getenv("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    names = (CATALOG_ID, "candidate.py", "checkin_baiduwp.py", "checkin/candidate.py", "checkin/checkin_baiduwp.py", Path(__file__).name, Path(__file__).as_posix())
    return any(selector and any(fnmatch.fnmatch(name, selector) for name in names) for selector in selectors)


def send_notification(body, dry_run):
    if not notify_enabled():
        return "未命中通知名单或全局关闭"
    if dry_run:
        return "离线预演已生成通知摘要，未外发"
    paths = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory))
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    # 在子进程内加载通知模块，屏蔽模块输出，并限制等待时间。
    python_code = """import importlib.util, json, sys
payload = json.load(sys.stdin)
if len(sys.argv) > 1:
    spec = importlib.util.spec_from_file_location('ql_notify_bridge', sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(payload['title'], payload['body'])
"""
    commands = [[sys.executable, "-c", python_code]]
    for path in paths:
        if (path / "notify.py").is_file():
            commands.append([sys.executable, "-c", python_code, str(path / "notify.py")])
        if (path / "sendNotify.js").is_file():
            js = "let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',async()=>{try{const p=JSON.parse(s);await require(process.argv[1]).sendNotify(p.title,p.body)}catch(e){process.exitCode=1}})"
            commands.append(["node", "-e", js, str(path / "sendNotify.js")])
    payload = json.dumps({"title": TITLE, "body": body}, ensure_ascii=False)
    for command in commands:
        try:
            result = subprocess.run(command, input=payload, text=True, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=25, check=False)
            if result.returncode == 0:
                return "已调用青龙通知"
        except (OSError, subprocess.TimeoutExpired):
            continue
    return "通知不可用或发送失败，保留业务退出码"


def main():
    started = time.monotonic()
    dry_run = os.getenv("BAIDUWP_DRY_RUN", "").strip().lower() in TRUE_VALUES
    accounts = [line.strip() for line in os.getenv("BAIDUWP_COOKIE", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间 {dt.datetime.now():%Y-%m-%d %H:%M:%S}，模式 {'离线预演' if dry_run else '正式执行'}，账号数 {len(accounts)}")
    totals = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
    results = []
    if not accounts:
        log("❌ 配置错误，请设置 BAIDUWP_COOKIE，每行一个账号")
    for index, account in enumerate(accounts, 1):
        account_start = time.monotonic()
        stats = {key: 0 for key in totals}
        log(f"账号 {index} 开始")
        try:
            cookie = normalize_cookie(account)
        except TaskError as exc:
            stats["failure"] = 1
            stats["skipped"] = 3
            log(f"❌ 账号 {index} 配置检查失败，{exc}")
        else:
            client = None if dry_run else Client(cookie)
            stages = (("每日签到", signin), ("每日答题", answer_question), ("会员信息查询", user_info))
            for stage_index, (label, action) in enumerate(stages, 1):
                stage_start = time.monotonic()
                log(f"账号 {index} 阶段 {stage_index}/3 {label} 开始")
                try:
                    if dry_run:
                        state, message = "skipped", "DRY_RUN_OK 配置有效，离线预演，未调用接口"
                    else:
                        if stage_index == 2:
                            time.sleep(3)
                        state, message = action(client)
                except TaskError as exc:
                    state, message = "failure", str(exc)
                except Exception:
                    state, message = "failure", "执行异常，详细信息已隐藏以保护凭据"
                stats[state] += 1
                icon = {"success": "✅", "alreadyComplete": "☑️", "skipped": "⏭️", "failure": "❌"}[state]
                log(f"{icon} 账号 {index} 阶段 {stage_index}/3 {label}，{message}，耗时 {time.monotonic() - stage_start:.2f} 秒")
        for key in totals:
            totals[key] += stats[key]
        passed = stats["failure"] == 0
        results.append({"account": index, "ok": passed, **stats})
        log(f"账号 {index} 统计，总任务 {sum(stats.values())}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failure']}，耗时 {time.monotonic() - account_start:.2f} 秒")
    succeeded = sum(item["ok"] for item in results)
    failed = len(accounts) - succeeded
    exit_code = 0 if accounts and not failed else 1
    status = "configuration-error" if not accounts else ("partial-failure" if failed and succeeded else "failure") if failed else "dry-run" if dry_run else "success"
    summary = {"task": TITLE, "status": status, "mode": "dry-run" if dry_run else "live", "accounts": len(accounts), "success": succeeded, "failure": failed, "configurationErrors": int(not accounts), "steps": totals, "results": results, "exitCode": exit_code}
    body = f"{TITLE}\n状态 {status}\n账号总数 {len(accounts)}，成功数 {succeeded}，失败数 {failed}\n配置错误 {int(not accounts)}\n子任务成功 {totals['success']}，已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，失败 {totals['failure']}"
    notification = send_notification(body, dry_run)
    summary["notification"] = notification
    log("----------------------------------------")
    log(body.replace("\n", "，"))
    log(f"通知状态 {notification}")
    log(f"总耗时 {time.monotonic() - started:.2f} 秒，完成时间 {dt.datetime.now():%Y-%m-%d %H:%M:%S}，最终状态 {status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
