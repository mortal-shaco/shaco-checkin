# -*- coding: utf-8 -*-
# name: 多看阅读
# cron: 5 2 * * *
# 来源: OreosLab/checkinpanel, ck_duokan.py
# 上游提交: 911402e4b2e559ffd62c4949a971ddd6834edd7d
# 许可证: MIT；原文件没有额外版权声明。
# SPDX-License-Identifier: MIT
"""多看阅读独立维护版（Python 3 标准库）。

DUOKAN_COOKIE：在本人登录的多看网页请求中复制完整 Cookie；每个非空行
一个账号，必须含 device_id 和登录会话字段；不要公开或打印 Cookie。
兼容 DUOKAN（每行 Cookie，或上游 [{"cookie": "..."}] JSON 列表）。
默认执行签到与书豆查询；DUOKAN_FREE、DUOKAN_DELAY、DUOKAN_DRAW=1
分别启用限免领书、书豆延期、抽奖。抽奖仅消耗已有机会，最多 6 次。
DUOKAN_DRY_RUN=1 完全断网预演（含通知模拟），不验证真实业务成功。
移除上游硬编码签名重放、虚增机会、伪报下载/体验/其他任务次数。

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
        _ql_notify_identities = ('c722e904dffeaf49', 'scripts/ck_duokan.py', 'ck_duokan.py', 'ck_duokan')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "多看阅读"
BASE = "https://www.duokan.com"
FALSE = {"0", "false", "no", "off"}
TRUE = {"1", "true", "yes", "on"}


class TaskError(Exception):
    pass


def stamp():
    return datetime.datetime.now().strftime("%H:%M:%S")


def log(message):
    print(f"[{stamp()}] {message}", flush=True)


def flag(name, default=False):
    value = os.environ.get(name, "1" if default else "0").strip().lower()
    if value not in TRUE | FALSE:
        raise TaskError(f"{name} 必须为 1 或 0（也接受 true/false、yes/no、on/off）")
    return value in TRUE


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不向跳转目标传递账号凭据，也不重放状态变更请求。
        return None


class Client:
    def __init__(self, cookie, timeout):
        self.cookie = cookie
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def signed(self, **extra):
        ts = int(time.time())
        checksum = 0
        for char in f"{self.cookie['device_id']}&{ts}":
            checksum = (checksum * 131 + ord(char)) % 65536
        return dict(_t=ts, _c=checksum, **extra)

    def request(self, path, data=None):
        headers = {
            "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookie.items()),
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        }
        payload = None if data is None else urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(BASE + path, data=payload, headers=headers,
                                     method="GET" if data is None else "POST")
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                if response.status != 200:
                    raise TaskError("接口 HTTP 状态异常")
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise TaskError("接口响应超过安全大小限制")
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise TaskError(f"接口 HTTP 错误 {exc.code}，未重试") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络失败或超时，未重试状态变更请求") from None
        except (ValueError, UnicodeError):
            raise TaskError("接口返回无效 JSON") from None
        if not isinstance(result, dict):
            raise TaskError("接口响应结构不符")
        return result


def check_success(result):
    # 上游明确使用 result == 0 或 msg == 成功；未知字段/文本不推测成功。
    if "result" in result:
        if type(result["result"]) is not int or result["result"] != 0:
            raise TaskError("业务码未确认成功（可能凭据失效或活动不可用）")
    elif result.get("msg") != "成功":
        raise TaskError("业务结果未确认成功（可能接口变化或凭据失效）")
    # 两个成功字段矛盾时失败闭合。
    if isinstance(result.get("msg"), str) and any(
        x in result["msg"] for x in ("失败", "尚未登录", "未登录", "失效", "错误")
    ):
        raise TaskError("接口报告业务失败")


def identity(result, cookie):
    containers = [result]
    if isinstance(result.get("data"), dict):
        containers.append(result["data"])
    for obj in list(containers):
        if isinstance(obj.get("user"), dict):
            containers.append(obj["user"])
    for obj in containers:
        for key in ("nickname", "username", "display_name", "uid"):
            value = obj.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                value = str(value)
                # 不展示手机号、设备标识或任何与凭据相同的值。
                if (not value or re.fullmatch(r"(?:\+?86)?1[3-9]\d{9}", value)
                        or any(secret and secret in value for key, secret in cookie.items()
                               if key.lower() not in ("uid", "user_id", "userid"))):
                    continue
                log("官方账号身份 " + key + "=" + json.dumps(value, ensure_ascii=False))
                return


def parse_cookie(line):
    if not isinstance(line, str) or not line.strip():
        raise TaskError("账号 Cookie 为空或格式错误")
    cookies = {}
    for item in line.split(";"):
        if not item.strip():
            continue
        key, delimiter, value = item.strip().partition("=")
        if (not delimiter or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key)
                or not value or any(ord(c) < 32 or ord(c) > 126 for c in value)):
            raise TaskError("Cookie 字段格式错误；必须使用完整请求 Cookie")
        if key in cookies:
            raise TaskError("Cookie 含重复字段，请重新获取")
        cookies[key] = value
    if not cookies.get("device_id") or len(cookies) < 2:
        raise TaskError("Cookie 必须包含 device_id 和登录会话字段")
    return cookies


def account_lines():
    canonical = os.environ.get("DUOKAN_COOKIE", "").strip()
    raw = canonical or os.environ.get("DUOKAN", "").strip()
    if not raw:
        raise TaskError("缺少必需变量 DUOKAN_COOKIE（兼容 DUOKAN）")
    if not canonical and raw.startswith("["):
        try:
            data = json.loads(raw)
            if not isinstance(data, list) or not data:
                raise ValueError()
            # 不良条目保留为独立失败账号，不妨碍有效账号运行。
            return [x.get("cookie") if isinstance(x, dict) else None for x in data]
        except ValueError:
            raise TaskError("DUOKAN 兼容 JSON 格式错误") from None
    return [line.strip() for line in raw.splitlines() if line.strip()]


def run_account(number, line, settings, dry):
    started = time.monotonic()
    counts = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
    cookie = None
    awards = None

    def stage(index, name, action, enabled=True):
        begin = time.monotonic()
        counts["total"] += 1
        log(f"账号 {number} · 阶段 {index} {name} 开始")
        try:
            if not enabled:
                counts["skipped"] += 1
                log(f"⏭️ {name}：未开启；耗时 {time.monotonic()-begin:.2f}s")
                return None
            value = action()
            counts["success"] += 1
            log(f"✅ {name}：{'预演通过，未发送请求' if dry else '业务成功已核验'}；耗时 {time.monotonic()-begin:.2f}s")
            return value
        except TaskError as exc:
            counts["failed"] += 1
            log(f"❌ {name}：{exc}；耗时 {time.monotonic()-begin:.2f}s")
        except Exception:
            counts["failed"] += 1
            log(f"❌ {name}：响应结构或执行异常（已脱敏）；耗时 {time.monotonic()-begin:.2f}s")
        return None

    cookie = stage(1, "凭据格式检查", lambda: parse_cookie(line))
    if cookie is not None:
        client = Client(cookie, settings["timeout"])

        def execute(path, data):
            if dry:
                return {}
            response = client.request(path, data)
            identity(response, cookie)
            check_success(response)
            return response

        stage(2, "每日签到", lambda: execute("/checkin/v0/checkin", client.signed()))

        def info():
            if dry:
                return []
            response = execute("/store/v0/award/coin/list", client.signed(sandbox=0, withid=1))
            data = response.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("award"), list):
                raise TaskError("书豆列表结构不符")
            entries = data["award"]
            for entry in entries:
                if (not isinstance(entry, dict) or type(entry.get("coin")) not in (int, float)
                        or not math.isfinite(entry["coin"]) or entry["coin"] < 0):
                    raise TaskError("书豆数量结构不符")
            log(f"当前书豆: {sum(x['coin'] for x in entries)}；批次 {len(entries)}")
            for i, entry in enumerate(entries, 1):
                # 日期只显示经过格式验证的值，避免回显异常响应。
                expiry = entry.get("expire")
                safe_date = expiry if isinstance(expiry, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", expiry) else "日期未识别"
                log(f"书豆批次 {i}：{entry['coin']} 书豆，到期 {safe_date}，可延期 {'是' if entry.get('delay') == 1 else '否'}")
            return entries

        awards = stage(3, "书豆查询", info)

        def delay():
            if dry:
                return
            if awards is None:
                raise TaskError("书豆查询失败，无法安全延期")
            eligible = [a for a in awards if a.get("delay") == 1]
            failures = 0
            for i, award in enumerate(eligible, 1):
                try:
                    expiry = award.get("expire")
                    if not isinstance(expiry, (str, int)) or isinstance(expiry, bool):
                        raise TaskError("延期日期结构不符")
                    execute("/store/v0/award/coin/delay", client.signed(date=expiry, withid=1))
                    log(f"延期批次 {i}：✅ 业务成功已核验")
                except TaskError as exc:
                    failures += 1
                    log(f"延期批次 {i}：❌ {exc}")
            log(f"延期批次：总数 {len(eligible)}，成功 {len(eligible)-failures}，失败 {failures}")
            if failures:
                raise TaskError("部分书豆延期失败")

        stage(4, "书豆延期", delay, settings["delay"])

        def free():
            if dry:
                return
            result = client.request("/hs/v4/channel/query/2027")
            # 上游频道 GET 没有业务码要求；若有业务码则必须成功。
            if "result" in result:
                check_success(result)
            try:
                bid = result["items"][0]["data"]["book_id"]
            except (KeyError, IndexError, TypeError):
                raise TaskError("限免频道没有可识别图书") from None
            if not isinstance(bid, (str, int)) or isinstance(bid, bool) or not str(bid):
                raise TaskError("限免图书编号结构不符")
            # 保留零价格约束；不支付书豆，不回退为付费购买。
            execute("/store/v0/payment/book/create", dict(payment_name="BC", ch="VSZUVB",
                    book_id=bid, price=0, allow_discount=1))

        stage(5, "限免领书（零价格）", free, settings["free"])

        def draw():
            if dry:
                return
            for i in range(6):
                execute("/store/v0/event/drawing", client.signed(code="8ulcky4bknbe_f", withid=1))
                log(f"抽奖 {i+1}/6：✅ 业务成功已核验")
                # 任意失败立即停止，不虚报完成，不自动增加机会。

        stage(6, "抽奖（仅已有机会）", draw, settings["draw"])
    counts["durationSeconds"] = round(time.monotonic()-started, 3)
    counts["account"] = number
    counts["status"] = "failed" if counts["failed"] else ("dry-run" if dry else "success")
    log(f"账号 {number} 统计：总任务 {counts['total']}，成功 {counts['success']}，已完成 {counts['alreadyComplete']}，跳过 {counts['skipped']}，失败 {counts['failed']}，耗时 {counts['durationSeconds']:.3f}s")
    return counts


def notify(body, dry):
    if os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in FALSE:
        log("⏭️ 通知已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    if dry:
        log("✅ 通知预演：" + body + "（未加载通知模块，未联网）")
        return "dry-run"
    try:
        files = []
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin:
            files.append(Path(spec.origin))
        if os.environ.get("QINGLONG_NOTIFY_DIR"):
            files.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
        files.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
        path = next((p for p in files if p.is_file()), None)
        if path is None:
            log("⚠️ 通知不可用：未找到青龙 notify.py；保留业务退出码")
            return "unavailable"
        code = ("import importlib.util,sys; "
                "sys.path.insert(0,str(__import__('pathlib').Path(sys.argv[1]).parent)); "
                "s=importlib.util.spec_from_file_location('notify',sys.argv[1]); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "m.send(sys.argv[2],sys.argv[3])")
        # 捕获通知模块日志，防止其打印自己的通知凭据。
        result = subprocess.run([sys.executable, "-c", code, str(path), TITLE, body],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if result.returncode:
            raise TaskError("通知模块执行失败")
        log("✅ 通知模块执行完成")
        return "sent"
    except Exception:
        log("⚠️ 通知投递失败（已脱敏）；保留业务退出码")
        return "failed"


def main():
    started = time.monotonic()
    log("========== 多看阅读 ==========")
    log("开始时间：" + datetime.datetime.now().isoformat(timespec="seconds"))
    dry = os.environ.get("DUOKAN_DRY_RUN", "0").strip().lower() in TRUE
    log("运行模式：" + ("断网预演" if dry else "真实业务"))
    accounts = []
    results = []
    config_error = False
    try:
        dry = flag("DUOKAN_DRY_RUN")
        accounts = account_lines()
        settings = {k: flag("DUOKAN_" + k.upper()) for k in ("free", "delay", "draw")}
        try:
            timeout = float(os.environ.get("DUOKAN_TIMEOUT", "15"))
        except ValueError:
            raise TaskError("DUOKAN_TIMEOUT 必须为 1 至 60 的秒数") from None
        if not math.isfinite(timeout) or not 1 <= timeout <= 60:
            raise TaskError("DUOKAN_TIMEOUT 必须为 1 至 60 的秒数")
        settings["timeout"] = timeout
        log(f"账号数量：{len(accounts)}")
        for number, line in enumerate(accounts, 1):
            results.append(run_account(number, line, settings, dry))
    except TaskError as exc:
        config_error = True
        log(f"❌ 配置错误：{exc}")
        log(f"账号数量：{len(accounts)}")
    except Exception:
        config_error = True
        log("❌ 执行异常（已脱敏）")
    succeeded = sum(r["failed"] == 0 for r in results)
    failed = len(accounts) - succeeded
    exit_code = 1 if config_error or failed else 0
    status = ("configuration-error" if config_error else "partial-failure" if failed and succeeded
              else "failure" if failed else "dry-run" if dry else "success")
    totals = {key: sum(r[key] for r in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    body = f"状态 {status}；账号总数 {len(accounts)}，成功 {succeeded}，失败 {failed}；子任务成功 {totals['success']}，跳过 {totals['skipped']}，失败 {totals['failed']}"
    notification = notify(body, dry)
    log("----------------------------------------")
    log(body)
    finish = datetime.datetime.now().isoformat(timespec="seconds")
    duration = round(time.monotonic()-started, 3)
    log(f"总耗时：{duration:.3f}s；完成时间：{finish}；通知状态：{notification}；最终状态：{status}")
    summary = dict(task=TITLE, mode="dry-run" if dry else "live", status=status,
                   accountCount=len(accounts), successCount=succeeded, failureCount=failed,
                   configurationError=config_error, stages=totals, accounts=results,
                   durationSeconds=duration, finishTime=finish, notification=notification,
                   exitCode=exit_code)
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
