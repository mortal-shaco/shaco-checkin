#!/usr/bin/env python3
# name: 魔搭社区每日签到
# cron: 0 6 * * *
# 调度时区：Asia/Shanghai；手动运行同样执行一次完整签到。
# 改编自 yierlingyi/astrbot_plugin_modelscope_daily main.py v1.1.1
# 原始提交：002d8ed697dfd934c71c99216e7c3ce653cc02a7，许可：MIT。
# 原始签到原理参考：https://github.com/L0NE-6/ModelScope-Daily
# 上游提供的 main.py 没有额外版权声明；保留其归属及 MIT 许可如下。
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
"""魔搭社区每日签到（Python 3.10+，仅标准库）。

MODELSCOPE_COOKIES：每个非空行一个账号；接受完整 Cookie、m_session_id=值、
Cookie: 前缀或会话值。电脑浏览器登录 https://www.modelscope.cn 后，在开发者工具
网络面板中查看本站已登录请求的 Cookie；复制包含 m_session_id 的完整 Cookie。
不要使用模型调用 API Key 代替网页登录会话。多账号不使用 & 或 @ 分隔。
MODELSCOPE_COOKIE 为旧式单账号兼容输入，仅在主变量未配置时使用。
MODELSCOPE_TIMEOUT：单次网络操作超时秒数，默认 30，范围 5~120。
MODELSCOPE_DRY_RUN=1：完全断网预演，通知只预览，不验证凭据有效性。
每天北京时间 06:00 运行一次；青龙调度器时区应设置为 Asia/Shanghai。
只触发幂等签到，不发帖、不分享、不消费魔粒、不修改账号资料。
由青龙 notify.py/sendNotify.js 发送汇总，不依赖 AstrBot 配置和私有仓库。
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
        _ql_notify_identities = ('7b0e6bc8644c6dfe', 'scripts/astrbot_plugin_modelscope.py', 'astrbot_plugin_modelscope.py', 'astrbot_plugin_modelscope')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

SITE = "https://www.modelscope.cn"
LOGIN_INFO_PATH = "/api/v1/users/login/info"
TRANSACTIONS_PATH = "/openapi/v1/magicubes/transactions?page=1&page_size=50"
BALANCE_PATH = "/openapi/v1/magicubes/balance"
REFERER = "https://www.modelscope.cn/models?filter=inference_type&page=1&tabKey=task"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0"
DAILY_RULE_KEYS = {"daily_active", "aliyun_bindlogin"}
BEIJING = timezone(timedelta(hours=8), "Asia/Shanghai")
TITLE = "魔搭社区每日签到"
CATALOG_ID = "7b0e6bc8644c6dfe"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
MAX_BODY = 1048576

def beijing_now() -> datetime:
    """返回当前北京时间。

    Returns:
        带 +08:00 时区信息的当前时间。
    """
    return datetime.now(BEIJING)


def today_in_beijing() -> str:
    """返回北京时间的今天日期字符串。

    Returns:
        形如 ``2026-10-31`` 的日期字符串。
    """
    return beijing_now().strftime("%Y-%m-%d")


def extract_session_id(cookie_text: str) -> str:
    """从用户粘贴的 Cookie 中提取 m_session_id。

    Args:
        cookie_text: 浏览器里复制的整段 Cookie，或单独的 m_session_id / ms- 令牌。

    Returns:
        m_session_id 的值；没有找到时返回空字符串。
    """
    raw = (cookie_text or "").strip()
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    match = re.search(r"(?:^|[;\n])\s*m_session_id\s*=\s*([^;\n]+)", raw)
    if match:
        return match.group(1).strip().strip('"')
    # 容错：用户只粘贴了会话值本身（不含分号与等号）。
    if ";" not in raw and "=" not in raw:
        return raw.split("\n")[0].strip()
    return ""


def build_cookie_header(cookie_text: str, session_id: str) -> str:
    """生成请求头里的 Cookie 值。

    Args:
        cookie_text: 用户填写的整段 Cookie、m_session_id 键值对或 ms- 令牌。
        session_id: 已提取出的 m_session_id。

    Returns:
        可直接放进 Cookie 请求头的字符串。
    """
    raw = (cookie_text or "").strip()
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    raw = re.sub(r"\r?\n", "; ", raw).strip().strip("; ")
    if "=" in raw:
        # 用户填的是整段 Cookie，原样透传，避免丢失其它风控 Cookie。
        return raw
    return f"m_session_id={session_id}"


def record_beijing_date(record: dict[str, Any]) -> str:
    """取出一条魔粒账单记录对应的北京日期。

    魔搭账单以北京时间自然日结算，字段值可能是不带时区的北京时间字符串；
    如果字段带时区（如 Z / +00:00），会先换算成北京时间再取日期。

    Args:
        record: 账单记录。

    Returns:
        形如 ``2026-10-31`` 的日期字符串；无法识别时返回空字符串。
    """
    raw = None
    for key in ("gmt_created", "gmt_create", "created_at", "create_time"):
        value = record.get(key)
        if value is not None and str(value).strip():
            raw = value
            break
    if raw is None:
        return ""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        try:
            moment = datetime.fromtimestamp(raw, tz=timezone.utc)
            return moment.astimezone(BEIJING).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return ""
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        # 退化为取前 10 位，兼容 ``2026-10-31 06:00:00`` 这类格式。
        return text[:10]
    if moment.tzinfo is not None:
        moment = moment.astimezone(BEIJING)
    return moment.strftime("%Y-%m-%d")


def envelope_data(payload: dict[str, Any]) -> dict[str, Any]:
    """取出魔搭响应信封中的 Data 字段。

    Args:
        payload: 接口返回的 JSON 对象。

    Returns:
        Data（或 data）字段；不存在或类型不符时返回空字典。
    """
    data = payload.get("Data")
    if not isinstance(data, dict):
        data = payload.get("data")
    return data if isinstance(data, dict) else {}


def envelope_message(payload: dict[str, Any]) -> str:
    """取出魔搭响应信封中的错误信息。

    Args:
        payload: 接口返回的 JSON 对象。

    Returns:
        错误信息文本；没有时返回空字符串。
    """
    for key in ("Message", "message", "msg"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def envelope_ok(payload: dict[str, Any]) -> bool:
    """判断魔搭响应信封是否表示成功。

    Args:
        payload: 接口返回的 JSON 对象。

    Returns:
        Success 为 true 或 Code 为 200 时返回 True。
    """
    for key in ("Success", "success"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    code = payload.get("Code", payload.get("code"))
    if code is None:
        return False
    try:
        return int(code) == 200
    except (TypeError, ValueError):
        return False


def daily_records(records: Any) -> list[dict[str, Any]]:
    """筛选出北京时间今天的签到到账记录。

    Args:
        records: 魔粒账单接口返回的 records 字段。

    Returns:
        当天的签到类型 EARN 记录列表。
    """
    if not isinstance(records, list):
        return []
    today = today_in_beijing()
    result: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if str(record.get("type") or "").upper() != "EARN":
            continue
        if record_beijing_date(record) != today:
            continue
        if str(record.get("rule_key") or "").lower() not in DAILY_RULE_KEYS:
            continue
        result.append(record)
    return result


def record_credit(records: list[dict[str, Any]] | None) -> float:
    """汇总账单记录里的到账魔粒数量。

    Args:
        records: 账单记录列表。

    Returns:
        所有记录的到账合计（无法解析的金额按 0 处理）。
    """
    credit = 0.0
    for record in records or []:
        if not isinstance(record, dict):
            continue
        amount = record.get("total_amount")
        try:
            if amount is not None:
                credit += float(str(amount).replace(",", ""))
        except (TypeError, ValueError):
            continue
    return credit


def format_credit(value: float) -> str:
    """把魔粒数量格式化成不带多余小数的文本。

    Args:
        value: 魔粒数量。

    Returns:
        整数原样输出，小数保留两位。
    """
    return str(int(value)) if value.is_integer() else str(round(value, 2))



class TaskError(Exception):
    """只携带可安全展示的固定错误描述。"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不能将会话凭据随重定向发往其它地址。
        return None


def log(text):
    print(f"[{beijing_now():%H:%M:%S}] {text}", flush=True)


def get_json(cookie, path, timeout):
    if os.getenv("MODELSCOPE_DRY_RUN", "").strip().lower() in TRUE:
        raise TaskError("断网预演禁止请求")
    headers = {"Accept": "application/json, text/plain, */*", "Referer": REFERER,
               "User-Agent": USER_AGENT, "Cookie": cookie,
               "x-modelscope-accept-language": "zh_CN",
               "X-Modelscope-Trace-Id": str(uuid.uuid4())}
    request = urllib.request.Request(SITE + path, headers=headers, method="GET")
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY:
                raise TaskError("响应过大")
            if response.status != 200:
                raise TaskError("接口 HTTP 状态异常")
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code == 401:
            raise TaskError("会话失效（HTTP 401），请重新获取 Cookie") from None
        if code == 403:
            raise TaskError("请求被风控拒绝（HTTP 403）") from None
        raise TaskError(f"接口返回 HTTP {code}") from None
    except (OSError, ValueError):
        raise TaskError("网络请求失败或超时") from None
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError):
        raise TaskError("响应不是有效 JSON") from None
    if (not isinstance(payload, dict) or not envelope_ok(payload)
            or payload.get("Success") is False or payload.get("success") is False):
        raise TaskError("接口未明确返回业务成功")
    # 明确的错误业务码不能被 Success=true 掩盖。
    for key in ("Code", "code"):
        if key in payload and str(payload[key]) != "200":
            raise TaskError("接口返回非成功业务码")
    return envelope_data(payload)


def transactions(cookie, timeout):
    data = get_json(cookie, TRANSACTIONS_PATH, timeout)
    rows = data.get("records", data.get("Records"))
    if not isinstance(rows, list):
        raise TaskError("账单记录字段缺失或类型异常")
    return daily_records(rows)


def number(value):
    try:
        parsed = float(str(value).replace(",", ""))
        return parsed if math.isfinite(parsed) else None
    except (ValueError, TypeError):
        return None


def identity(data, secrets):
    for key in ("NickName", "Name", "nickname", "name", "HavanaId"):
        value = data.get(key)
        if not isinstance(value, (str, int)) or not str(value).strip():
            continue
        text = str(value).strip()
        # 保留官方身份原值，只阻止凭据、手机号和控制字符进入日志。
        if any(secret and secret in text for secret in secrets) or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
            return ""
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
            return ""
        return text
    return ""


def check_account(raw, index, dry, timeout):
    started = time.monotonic()
    stats = dict(total=5, success=0, alreadyComplete=0, skipped=0, failed=0)
    label = f"账号{index}"
    fatal = False
    cookie = ""
    before = None
    records = []
    message = ""
    session = ""
    for stage, title in enumerate(("凭据格式检查", "签到前账单", "登录签到", "到账核验", "余额展示"), 1):
        tick = time.monotonic()
        log(f"{label} 阶段 {stage}/5 {title} 开始")
        status = "success"
        detail = ""
        if fatal:
            status, detail = "skipped", "前置步骤失败，跳过"
        elif dry and stage > 1:
            status, detail = "skipped", "断网预演：不调用接口，不触发签到"
        else:
            try:
                if stage == 1:
                    session = extract_session_id(raw)
                    if not session or any(ord(c) < 32 or ord(c) == 127 for c in raw):
                        raise TaskError("凭据格式无效，需包含 m_session_id 或单独会话值")
                    cookie = build_cookie_header(raw, session)
                    if not cookie.isascii():
                        raise TaskError("Cookie 包含不支持的字符，请重新复制请求头")
                    detail = "凭据格式通过；未展示凭据"
                elif stage == 2:
                    before = transactions(cookie, timeout)
                    detail = f"查询成功，今日签到记录 {len(before)} 条"
                elif stage == 3:
                    data = get_json(cookie, LOGIN_INFO_PATH, timeout)
                    label = identity(data, [raw, session]) or label
                    detail = "登录请求业务成功，仍需验证签到到账"
                elif stage == 4:
                    for attempt in range(1, 4):
                        try:
                            records = transactions(cookie, timeout)
                            if records:
                                break
                            log(f"{label} 核验 {attempt}/3：尚无今日签到记录")
                        except TaskError as exc:
                            log(f"{label} 核验 {attempt}/3：{exc}")
                            if "401" in str(exc) or "403" in str(exc):
                                raise
                        if attempt < 3:
                            time.sleep(3)
                    if not records:
                        raise TaskError("未确认今日签到到账；请稍后重新运行复查")
                    credit = record_credit(records)
                    if not math.isfinite(credit):
                        raise TaskError("账单金额异常，无法核验到账统计")
                    old = record_credit(before)
                    if before is None:
                        message = f"今日到账 +{format_credit(credit)} 魔粒"
                    elif not before:
                        message = f"本次到账 +{format_credit(credit)} 魔粒"
                    elif credit > old:
                        message = f"本次到账 +{format_credit(credit-old)} 魔粒；今日合计 +{format_credit(credit)} 魔粒"
                    else:
                        status = "alreadyComplete"
                        message = f"今天已签到过，本次无新增到账；今日合计 +{format_credit(credit)} 魔粒"
                    # 使用已知规则名称，不输出服务端任意账单标题。
                    rules = list(dict.fromkeys(str(r.get("rule_key")).lower() for r in records))
                    message += "（" + " + ".join({"daily_active": "每日活跃", "aliyun_bindlogin": "阿里云绑定登录"}[r] for r in rules) + "）"
                    detail = message
                elif stage == 5:
                    data = get_json(cookie, BALANCE_PATH, timeout)
                    available, total = number(data.get("available_balance")), number(data.get("total_balance"))
                    if available is None:
                        raise TaskError("余额字段缺失或异常，签到到账已单独核验")
                    detail = f"当前余额 {format_credit(available)} 魔粒"
                    if total is not None:
                        detail += f"（总计 {format_credit(total)}）"
                    message += "；" + detail
            except TaskError as exc:
                detail = str(exc)
                if stage in (2, 5):
                    status = "skipped"
                    detail = "非关键查询失败：" + detail
                else:
                    status, fatal = "failed", True
                    message = detail
            except Exception:
                status, fatal = "failed", True
                detail = message = "步骤处理异常，未输出异常内容"
        stats[status] += 1
        icon = {"success": "✅", "alreadyComplete": "☑️", "skipped": "⏭️", "failed": "❌"}[status]
        log(f"{label} 阶段 {stage}/5 {title} {icon} {detail}；耗时 {time.monotonic()-tick:.2f}秒")
    elapsed = round(time.monotonic() - started, 2)
    log(f"{label} 账号统计：总任务5，成功{stats['success']}，已完成{stats['alreadyComplete']}，跳过{stats['skipped']}，失败{stats['failed']}；耗时{elapsed}秒")
    return {"account": index, "display": label, "status": "failed" if fatal else ("dry-run" if dry else "success"),
            "summary": message or "断网预演通过，未验证真实业务", "statistics": stats, "elapsedSeconds": elapsed}


# 将可选青龙通知放在独立进程中，禁止通知模块输出凭据、原始响应或修改业务退出码。
NOTIFY_CODE = r'''
import contextlib, importlib.util, json, os, pathlib, subprocess, sys
payload = json.loads(sys.stdin.read())
with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
    modules = []
    try:
        import notify
        modules.append(notify)
    except Exception:
        pass
    directories = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    for directory in directories:
        if not directory:
            continue
        file = pathlib.Path(directory) / 'notify.py'
        if file.is_file():
            try:
                sys.path.insert(0, str(file.parent))
                spec = importlib.util.spec_from_file_location('ql_task_notify', file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                modules.append(module)
            except Exception:
                pass
    for module in modules:
        try:
            if callable(getattr(module, 'send', None)):
                result = module.send(payload['title'], payload['body'])
                if result is not False:
                    sys.exit(0)
        except Exception:
            pass
    for directory in directories:
        if not directory:
            continue
        file = pathlib.Path(directory) / 'sendNotify.js'
        if file.is_file():
            try:
                code = "const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));Promise.resolve(require(process.argv[1]).sendNotify(p.title,p.body)).then(()=>process.exit(0)).catch(()=>process.exit(1));"
                result = subprocess.run(['node', '-e', code, str(file)], input=json.dumps(payload), text=True, stdout=sink, stderr=sink, timeout=15)
                if result.returncode == 0:
                    sys.exit(0)
            except Exception:
                pass
sys.exit(1)
'''


def notify(summary, dry):
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return "已关闭"
    if switch not in TRUE:
        selectors = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
        if selectors is not None:
            names = [CATALOG_ID, Path(__file__).name, "scripts/" + Path(__file__).name]
            if not any(fnmatch.fnmatchcase(name, pattern) for pattern in re.split(r"[,;\s]+", selectors) if pattern for name in names):
                return "未选中"
        # 当前脚本为此次导入的列举任务，auto 默认启用。
    if dry:
        return "断网预演：仅预览脱敏通知，不加载通知模块"
    body = (f"账号总数：{summary['accounts']}；成功：{summary['success']}；失败：{summary['failed']}；"
            f"状态：{summary['status']}\n" + "\n".join(f"账号{r['account']}：{r['summary']}" for r in summary["results"]))
    try:
        result = subprocess.run([sys.executable, "-c", NOTIFY_CODE], input=json.dumps({"title": TITLE, "body": body}),
                                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        return "通知模块调用成功" if result.returncode == 0 else "通知不可用或发送失败"
    except Exception:
        return "通知不可用或发送失败"


def main():
    started = time.monotonic()
    start = beijing_now().isoformat()
    dry_value = os.getenv("MODELSCOPE_DRY_RUN", "0").strip().lower()
    dry = dry_value in TRUE
    raw = os.getenv("MODELSCOPE_COOKIES", "").strip() or os.getenv("MODELSCOPE_COOKIE", "")
    accounts = list(dict.fromkeys(line.strip() for line in raw.splitlines() if line.strip()))
    log(f"========== {TITLE} ==========\n开始时间：{start}；模式：{'断网预演' if dry else '正式执行'}；账号数：{len(accounts)}")
    results = []
    error = ""
    try:
        timeout = int(os.getenv("MODELSCOPE_TIMEOUT", "30"))
        if not 5 <= timeout <= 120:
            raise ValueError
        if dry_value not in TRUE | FALSE:
            raise ValueError
    except ValueError:
        error = "配置错误：TIMEOUT 需为 5~120 秒整数，DRY_RUN 需为布尔开关"
    if not accounts:
        error = "配置错误：请设置 MODELSCOPE_COOKIES，每个非空行一个账号"
    if error:
        log("❌ " + error)
    else:
        for index, account in enumerate(accounts, 1):
            if index > 1 and not dry:
                time.sleep(1)
            results.append(check_account(account, index, dry, timeout))
    failed = sum(r["status"] == "failed" for r in results)
    success = sum(r["status"] == "success" for r in results)
    status = "configuration-error" if error else ("partial-failure" if failed and failed < len(accounts) else "failure" if failed else "dry-run" if dry else "success")
    exit_code = 2 if error else int(failed > 0)
    stats = {key: sum(r["statistics"][key] for r in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    summary = dict(task=TITLE, status=status, mode="dry-run" if dry else "live", accounts=len(accounts), success=success,
                   failed=len(accounts) if error else failed, dryRunPassed=sum(r["status"] == "dry-run" for r in results),
                   results=results, statistics=stats, startTime=start, error=error, exitCode=exit_code)
    summary["notification"] = notify(summary, dry)
    summary["elapsedSeconds"] = round(time.monotonic()-started, 2)
    summary["finishTime"] = beijing_now().isoformat()
    log("----------------------------------------")
    log(f"任务统计：账号{len(accounts)}，成功{success}，失败{summary['failed']}，预演通过{summary['dryRunPassed']}")
    log(f"子任务统计：总数{stats['total']}，成功{stats['success']}，已完成{stats['alreadyComplete']}，跳过{stats['skipped']}，失败{stats['failed']}")
    log(f"总耗时：{summary['elapsedSeconds']}秒；完成时间：{summary['finishTime']}；通知：{summary['notification']}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
