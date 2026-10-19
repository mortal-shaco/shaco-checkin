# -*- coding: utf-8 -*-
# name: FreeNom 域名续期维护
# cron: 30 7 */10 * *
# Upstream: OreosLab/checkinpanel, ck_freenom.py (MIT)
# MIT License: Original copyright/license notices remain applicable.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""FREENOM_ACCOUNTS: 每行 用户名|密码，仅在第一个 | 处分割。
用户名及密码来自本人 Freenom 账号；不要分享凭据。
兼容 FREENOM 的 JSON 数组 [{"username": ..., "password": ...}]。
FREENOM_RENEW=1 显式启用免费续期；默认只查询。FREENOM_DRY_RUN=1 断网预演。
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
        _ql_notify_identities = ('563cae20eed18007', 'scripts/ck_freenom.py', 'ck_freenom.py', 'ck_freenom')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import contextlib
import datetime
import http.cookiejar
import importlib.util
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://my.freenom.com/"
TITLE = "FreeNom 域名续期维护"
FALSE = {"0", "false", "no", "off"}


def enabled(name, default="0"):
    return os.getenv(name, default).lower().strip() not in FALSE | {""}


def log(stage, message, elapsed=None):
    suffix = "" if elapsed is None else f"（耗时 {elapsed:.2f} 秒）"
    print(f"[{datetime.datetime.now():%H:%M:%S}] {stage} {message}{suffix}", flush=True)


class TaskError(Exception):
    pass


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cells, self.cell = [], None, [], None
        self.token = None
        self.logout = False
        self.renewal_table = False
        self.options, self.option = [], None
        self.select_name = None
        self.identity = None
        self.identity_depth = 0
        self.identity_text = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            href = a.get("href", "")
            if urllib.parse.urlsplit(href).path.endswith("logout.php"):
                self.logout = True
            if self.row is not None:
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
                if query.get("a") == ["renewdomain"] and query.get("domain"):
                    self.row["id"] = query["domain"][0]
                    self.renewal_table = True
        if tag == "input" and a.get("name") == "token":
            self.token = a.get("value")
        if tag == "tr":
            self.row, self.cells = {}, []
        if tag == "td":
            self.cell = []
        if tag == "select":
            self.select_name = a.get("name", "")
        if tag == "option" and (self.select_name or "").startswith("renewalperiod"):
            self.option = [a.get("value", ""), []]
        # Only explicit public display-name fields; never infer identity from login email.
        if a.get("id") in {"clientname", "displayname", "nickname"}:
            self.identity_depth = 1
            self.identity_text = []
        elif self.identity_depth:
            self.identity_depth += 1

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
        if self.option is not None:
            self.option[1].append(data)
        if self.identity_depth:
            self.identity_text.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.cells.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.row["cells"] = self.cells
            self.rows.append(self.row)
            self.row = None
        if tag == "option" and self.option is not None:
            self.options.append((self.option[0], " ".join("".join(self.option[1]).split())))
            self.option = None
        if tag == "select":
            self.select_name = None
        if self.identity_depth:
            self.identity_depth -= 1
            if not self.identity_depth:
                self.identity = " ".join("".join(self.identity_text).split())

    def domains(self):
        domains = []
        for row in self.rows:
            if "id" not in row:
                continue
            cells = row["cells"]
            days = re.search(r"(-?\d+)\s*\.?\s*Days\b", " ".join(cells), re.I)
            if not cells or not days or not row["id"].isdigit():
                raise TaskError("续期列表字段无法解析，停止操作")
            domains.append((cells[0], int(days[1]), row["id"]))
        if not domains and not re.search(r"no\s+(?:domains|records|results)|没有.*域名", " ".join(" ".join(r["cells"]) for r in self.rows), re.I):
            raise TaskError("未识别到续期列表或明确的空列表，不能确认查询成功")
        return domains


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), SafeRedirect())

    def request(self, path, data=None, referer="clientarea.php"):
        payload = None if data is None else urllib.parse.urlencode(data).encode()
        request = urllib.request.Request(BASE + path, data=payload, headers={
            "User-Agent": "Mozilla/5.0 FreeNom-maintained/1.0",
            "Referer": BASE + referer,
        })
        try:
            with self.opener.open(request, timeout=20) as response:
                if response.status != 200:
                    raise TaskError("HTTP 请求未成功")
                body = response.read(2 * 1024 * 1024 + 1)
                if len(body) > 2 * 1024 * 1024:
                    raise TaskError("页面超过大小限制")
                return body.decode("utf-8", errors="replace")
        except TaskError:
            raise
        except Exception:
            raise TaskError("网络请求失败或超时（原始错误已隐藏）") from None


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != "https" or target.netloc != "my.freenom.com":
            raise TaskError("拒绝跨站或非 HTTPS 重定向")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def accounts():
    value = os.getenv("FREENOM_ACCOUNTS", "")
    if value.strip():
        result = []
        for line in value.splitlines():
            if not line.strip():
                continue
            user, sep, password = line.partition("|")
            result.append((user.strip(), password if sep else ""))
        return result
    legacy = os.getenv("FREENOM", "")
    if legacy.strip():
        try:
            data = json.loads(legacy)
            if not isinstance(data, list):
                raise ValueError()
            return [(item.get("username", ""), item.get("password", "")) for item in data]
        except Exception:
            raise TaskError("兼容变量 FREENOM 必须是账号对象 JSON 数组") from None
    raise TaskError("缺少 FREENOM_ACCOUNTS，每行填写用户名|密码")


def run_account(index, credentials, dry, renew):
    started = time.monotonic()
    last_stage = started
    stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    prefix = f"账号 {index}"
    def step(number, message, status="success"):
        nonlocal last_stage
        now = time.monotonic()
        stats["total"] += 1
        stats[status] += 1
        log(f"{prefix} 阶段 {number}", message, now - last_stage)
        last_stage = now
    try:
        user, password = credentials
        if not isinstance(user, str) or not isinstance(password, str) or not user or not password:
            raise TaskError("账号格式错误：用户名和密码均不能为空")
        if dry:
            step(1, "✅ 参数解析通过")
            step(2, "⏭️ DRY_RUN_OK：登录、查询、续期均未发送请求", "skipped")
        else:
            client = Client()
            login = Page(client.request("clientarea.php"))
            data = {"username": user, "password": password}
            if login.token:
                data["token"] = login.token
            client.request("dologin.php", data)
            listing = Page(client.request("domains.php?a=renewals"))
            if not listing.logout:
                raise TaskError("未验证到已登录状态，可能凭据失效或页面变化")
            if listing.identity:
                identity = listing.identity
                if user not in identity and password not in identity and not re.search(r"@|\b\d{7,}\b", identity):
                    log(prefix, "官方账号名称：" + identity)
            step(1, "✅ 登录状态已验证")
            domains = listing.domains()
            step(2, f"✅ 已验证续期列表，共 {len(domains)} 个域名")
            for _, days, renewal_id in domains:
                # Domain names are unnecessary in logs and can contain personal data.
                if days >= 14:
                    step(3, f"☑️ 域名 {renewal_id} 距续期 {days} 天，尚未进入续期窗口", "alreadyComplete")
                    continue
                if not renew:
                    step(3, f"⏭️ 域名 {renewal_id} 距续期 {days} 天；查询模式未执行续期", "skipped")
                    continue
                form = Page(client.request(f"domains.php?a=renewdomain&domain={renewal_id}"))
                free = any(value == "12M" and re.search(r"\bfree\b|免费|(?:USD|EUR|\$|€)\s*0[.,]00\b|\b0[.,]00\s*(?:USD|EUR|\$|€)", label, re.I) for value, label in form.options)
                if not form.logout or not form.token or not free:
                    raise TaskError("续期表单未明确证明 12 个月免费或会话失效，拒绝续期")
                result = client.request("domains.php?submitrenewals=true", {
                    "token": form.token, "renewalid": renewal_id,
                    f"renewalperiod[{renewal_id}]": "12M", "paymentmethod": "credit",
                }, f"domains.php?a=renewdomain&domain={renewal_id}")
                if "Order Confirmation" not in result:
                    raise TaskError("续期响应未包含订单确认，禁止自动重试")
                verify = Page(client.request("domains.php?a=renewals"))
                if not verify.logout:
                    raise TaskError("续期后的会话验证失败")
                refreshed = {rid: remaining for _, remaining, rid in verify.domains()}
                if refreshed.get(renewal_id, days) <= days:
                    raise TaskError("续期后的天数未增加，结果未验证；请人工检查后再运行")
                step(3, f"✅ 域名 {renewal_id} 的 12 个月免费续期已复核")
    except TaskError as error:
        step("失败", "❌ " + str(error), "failed")
    except Exception:
        step("失败", "❌ 执行异常（详情已脱敏）", "failed")
    stats["elapsedSeconds"] = round(time.monotonic() - started, 3)
    log(prefix + " 统计", json.dumps(stats, ensure_ascii=False))
    return stats


def notify(summary, dry):
    body = f"模式：{summary['mode']}；账号总数：{summary['accounts']}；成功：{summary['success']}；失败：{summary['failed']}；状态：{summary['status']}"
    if not enabled("QINGLONG_NOTIFY", "1"):
        return "已关闭"
    if dry:
        log("通知", "⏭️ 断网预演通知摘要：" + body + "；跳过网络发送")
        return "断网预演跳过发送"
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                import notify as module
            except ImportError:
                module = None
                paths = [Path(os.getenv("QINGLONG_NOTIFY_DIR", "/ql/data/scripts")) / "notify.py", Path("/ql/scripts/notify.py")]
                for path in paths:
                    if path.is_file():
                        spec = importlib.util.spec_from_file_location("qinglong_notification", path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        break
                if module is None:
                    return "通知模块不可用"
            module.send(TITLE, body)
        return "已发送"
    except BaseException:
        return "通知发送失败（不影响业务退出码）"


def main():
    started = time.monotonic()
    dry, renew = enabled("FREENOM_DRY_RUN"), enabled("FREENOM_RENEW")
    mode = "断网预演" if dry else ("免费续期" if renew else "仅查询")
    print("=" * 48 + "\n" + TITLE)
    log("开始", f"{datetime.datetime.now().isoformat(timespec='seconds')}；模式：{mode}")
    results, configuration_error = [], False
    try:
        items = accounts()
        if not items:
            raise TaskError("账号列表为空")
        log("阶段 1 参数检查", f"账号数：{len(items)}")
        for index, item in enumerate(items, 1):
            results.append(run_account(index, item, dry, renew))
    except TaskError as error:
        configuration_error = True
        log("阶段 1 参数检查", "❌ " + str(error))
    failed = sum(bool(r["failed"]) for r in results)
    code = 1 if configuration_error or failed else 0
    status = "configuration-error" if configuration_error else ("partial-failure" if failed and failed < len(results) else "failure" if failed else "dry-run" if dry else "success")
    summary = {"mode": mode, "accounts": len(results), "success": len(results) - failed,
               "failed": failed, "status": status, "exitCode": code,
               "tasks": {key: sum(r[key] for r in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}}
    summary["notification"] = notify(summary, dry)
    summary["elapsedSeconds"] = round(time.monotonic() - started, 3)
    summary["finishTime"] = datetime.datetime.now().isoformat(timespec="seconds")
    print("-" * 48)
    log("任务统计", f"账号总数 {len(results)}；成功 {summary['success']}；失败 {failed}；子任务 {summary['tasks']}；总耗时 {summary['elapsedSeconds']} 秒")
    log("完成", f"{summary['finishTime']}；最终状态 {status}；通知：{summary['notification']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
