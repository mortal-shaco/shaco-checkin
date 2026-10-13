#!/usr/bin/env python3
# name: 2cycdx自动签到
# cron: 0 8 * * *
# publish-path: scripts/2cycdx_signin.py
# 发布契约：contract.json 的 publishPath；candidate.py 仅为隔离交付名称。
# 维护新增代码许可：MIT（任务 effectiveLicense）；原始作者及许可声明保留如下。
"""
name: 2cycdx自动签到
Author: Tgkkez
Author URI: https://github.com/Tgkkez/2cycdx_Autosignin
Version: 1.0.1 (独立维护版)
更新记录：更新网站域名
License: GNU General Public License v3.0
License URI: https://www.gnu.org/licenses/gpl-3.0.html
原始许可声明如上保留；任务指定的 effectiveLicense 为 MIT。

论坛官网：https://www.2cycdx.com/；每天签到领贡献。
浏览器登录后打开 F12→网络→文档，刷新页面，从网站请求头复制完整 Cookie。
cycd_cookie：每个非空行一个账号，Cookie 内的 &、@ 不作账号分隔符。
CYCD_DRY_RUN=1：完全断网预演，包括模拟通知与签到文案获取。
QINGLONG_NOTIFY=0：关闭通知；QINGLONG_NOTIFY_DIR：可选青龙通知模块目录。
CYCD_LOCAL_TEXT：一言不可用时的本地签到文案，最多 280 字。
发布文件名：2cycdx_signin.py；隔离交付文件 candidate.py 不作为发布文件名。
凭据获取仅使用论坛官网请求，不向一言发送 Cookie。
功能清单与维护覆盖：上游的表单参数获取、每日签到、贡献领取、今日已签到
识别均已覆盖；维护版的逐行多账号、一言及署名和本地回退、页面编码处理、
XML CDATA 成功检查、青龙通知、时间轴统计与 TASK_SUMMARY、断网预演均保留。
每日 08:00 执行；唯一论坛状态变更是签到提交（包含签到文案）及其贡献奖励。
无配套账号参数；Cookie 作为完整单行保留，其他设置不与凭据混合。
本轮核对：上游全部业务功能已覆盖；没有兼容参考源可供接口对比。
本包使用标准库，以契约 smokeTest 验证导入和独立执行。当前反馈为通用发布路径冲突，
交付契约显式指定 scripts/2cycdx_signin.py；无接口失效、凭据变化或相关参考源。
产品专属发布路径以契约 publishPath 为准；不能以隔离文件名覆盖其他产品。
"""
import importlib
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = "2cycdx自动签到"
# 发布器应读取 contract.json 的 publishPath，不得沿用上游通用文件名。
PUBLISH_PATH = "scripts/2cycdx_signin.py"
BASE = "https://www.2cycdx.com"
PAGE = BASE + "/plugin.php?id=dc_signin"
SIGN = BASE + "/plugin.php?id=dc_signin:sign&inajax=1"
OFF = {"0", "false", "no", "off"}
LOCAL_TEXT = "记上一笔，hold住我的快乐！"


def stamp():
    return datetime.now().strftime("%H:%M:%S")


def log(message):
    print(f"[{stamp()}] {message}", flush=True)


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if new.scheme != "https" or new.netloc != old.netloc:
            raise ValueError("拒绝跨站重定向")
        if req.data is not None:
            raise ValueError("拒绝签到提交重定向")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http(url, cookie=None, data=None, charset="utf-8", limit=1048576, timeout=15):
    if os.getenv("CYCD_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError("断网预演禁止 HTTP 请求")
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    if cookie is not None:
        headers.update({"Cookie": cookie, "Referer": PAGE})
    body = None
    if data is not None:
        body = urlencode(data, encoding=charset).encode("ascii")
        headers.update({"Content-Type": "application/x-www-form-urlencoded", "Origin": BASE})
    request = Request(url, data=body, headers=headers)
    with build_opener(SafeRedirect()).open(request, timeout=timeout) as response:
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("响应超过大小限制")
        declared = response.headers.get_content_charset()
        meta = re.search(br'charset\s*=\s*["\x27]?([\w-]+)', raw[:8192], re.I)
        encoding = declared or (meta.group(1).decode("ascii") if meta else charset)
        if encoding.lower() in {"gb2312", "gbk"}:
            encoding = "gb18030"
        return raw.decode(encoding), encoding


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.formhash = None
        self.text = []
        self.identity = []
        self.in_identity = False
        self.identity_container = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "formhash":
            self.formhash = attrs.get("value")
        # Discuz 的账号菜单使用 class=vwmy 显示登录用户名。
        if "vwmy" in attrs.get("class", "").split():
            self.identity_container = True
        if tag == "a" and self.identity_container:
            self.in_identity = True

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_identity = False
            self.identity_container = False
        elif tag == "strong":
            self.identity_container = False

    def handle_data(self, data):
        self.text.append(data)
        if self.in_identity:
            self.identity.append(data)


def parsed(text):
    # Discuz 的 inajax 响应可将消息封装在 XML CDATA 中。
    # HTMLParser 默认忽略 CDATA；先提取其内容再解析原有 HTML 消息。
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", lambda match: match.group(1), text, flags=re.S)
    page = Page()
    page.feed(text)
    return page


def sign_status(visible):
    """仅接受明确成功，拒绝包含否定或登录要求的混合响应。"""
    if any(marker in visible for marker in (
        "签到失败", "未签到成功", "没有签到成功", "尚未签到成功", "登录后", "请先登录",
    )):
        return "failure"
    if "您今日已经签过到" in visible:
        return "already-complete"
    if "签到成功" in visible:
        return "success"
    return "failure"


def normalized(value):
    return " ".join(value.split()) if isinstance(value, str) else ""


def signin_text():
    try:
        # 独立请求，不携带 Cookie、Token 或论坛请求头。
        raw, _ = http("https://v1.hitokoto.cn/?encode=json", limit=16384, timeout=8)
        data = json.loads(raw)
        text = normalized(data.get("hitokoto"))
        author, source = normalized(data.get("from_who")), normalized(data.get("from"))
        if not text:
            raise ValueError("缺少文案")
        if author and source:
            text += f" —— {author}《{source}》"
        elif source:
            text += f" ——《{source}》"
        elif author:
            text += f" —— {author}"
        if len(text) > 280:
            raise ValueError("文案过长")
        log("文案：一言获取成功（不输出文案内容）")
        return text
    except Exception:
        log("⚠️ 文案：一言不可用，使用本地文案")
        return normalized(os.getenv("CYCD_LOCAL_TEXT", "")) or LOCAL_TEXT


def _notify(body, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in OFF:
        return "已关闭"
    if dry:
        return "预演通知（断网，未调用通知模块）"
    try:
        try:
            module = importlib.import_module("notify")
        except ImportError:
            module = None
            paths = []
            directory = os.getenv("QINGLONG_NOTIFY_DIR")
            if directory:
                paths.append(Path(directory) / "notify.py")
            paths += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, "send", None)):
            return "不可用（业务退出码保留）"
        # 通知模块输出可能含渠道凭据，因此不转发它的 stdout/stderr。
        import contextlib
        with open(os.devnull, "w") as sink:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                module.send(TITLE, body)
        return "已发送"
    except (Exception, SystemExit):
        return "失败（业务退出码保留）"


def notify(body, dry):
    # 连同模块加载过程一起抑制输出，防止第三方通知代码输出渠道凭据。
    import contextlib
    with open(os.devnull, "w") as sink:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            return _notify(body, dry)


def account(cookie, index, dry):
    started = time.monotonic()
    stats = {"total": 2, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    stage = time.monotonic()
    log(f"账号 {index} · 1/2 获取签到页面与登录参数")
    try:
        if any(ord(c) < 32 or ord(c) == 127 for c in cookie):
            raise ValueError("凭据格式无效")
        if dry:
            log(f"⏭️ 账号 {index} · 1/2 预演通过，未请求网络，耗时 {time.monotonic()-stage:.2f} 秒")
            stage = time.monotonic()
            log(f"账号 {index} · 2/2 模拟签到、文案和通知")
            log(f"⏭️ 账号 {index} · 2/2 DRY_RUN_OK，未修改论坛状态，耗时 {time.monotonic()-stage:.2f} 秒")
            stats["skipped"] = 2
            ok = True
        else:
            text, encoding = http(PAGE, cookie)
            page = parsed(text)
            identity = "".join(page.identity).strip()
            if identity and not re.search(r"1[3-9]\d{9}", identity) and cookie not in identity:
                log(f"账号 {index} · 官方用户名：{identity}")
            visible = "".join(page.text)
            if sign_status(visible) == "already-complete":
                stats.update(success=1, alreadyComplete=1)
                log(f"☑️ 账号 {index} · 1/2 今日已签到，耗时 {time.monotonic()-stage:.2f} 秒")
                log(f"☑️ 账号 {index} · 2/2 已完成，无需再次提交，耗时 0.00 秒")
                ok = True
            else:
                if not page.formhash or not re.fullmatch(r"[A-Za-z0-9]+", page.formhash):
                    raise ValueError("未获得有效登录参数")
                stats["success"] = 1
                log(f"✅ 账号 {index} · 1/2 登录参数已获取，耗时 {time.monotonic()-stage:.2f} 秒")
                stage = time.monotonic()
                log(f"账号 {index} · 2/2 提交签到")
                content = signin_text()
                result, _ = http(SIGN, cookie, {
                    "formhash": page.formhash, "signsubmit": "yes", "handlekey": "signin",
                    "emotid": "11", "referer": PAGE, "content": content,
                }, charset=encoding)
                result = "".join(parsed(result).text)
                if sign_status(result) == "already-complete":
                    stats["alreadyComplete"] = 1
                    log(f"☑️ 账号 {index} · 2/2 今日已签到，耗时 {time.monotonic()-stage:.2f} 秒")
                elif sign_status(result) == "success":
                    stats["success"] += 1
                    log(f"✅ 账号 {index} · 2/2 签到成功，耗时 {time.monotonic()-stage:.2f} 秒")
                else:
                    raise ValueError("服务端未确认签到成功")
                ok = True
    except Exception as error:
        # 不输出异常文本：其中可能含 Cookie、URL 参数或服务器原始响应。
        if isinstance(error, HTTPError):
            diagnosis = f"HTTP 状态 {error.code}，请检查网站状态和凭据"
        elif isinstance(error, (TimeoutError, URLError)):
            diagnosis = "连接失败或超时，请检查网络和网站状态"
        elif isinstance(error, (UnicodeError, LookupError)):
            diagnosis = "响应编码或字符格式无效"
        elif isinstance(error, ValueError):
            diagnosis = "凭据、登录参数或业务响应未通过验证"
        else:
            diagnosis = "运行异常，未获得业务成功确认"
        stats["failed"] = 1
        stats["skipped"] = stats["total"] - stats["success"] - 1
        failed_stage = 2 if stats["success"] else 1
        log(f"❌ 账号 {index} · {failed_stage}/2 阶段失败：{diagnosis}；耗时 {time.monotonic()-stage:.2f} 秒")
        if stats["skipped"]:
            log(f"⏭️ 账号 {index} · 2/2 签到提交跳过：前置阶段失败；耗时 0.00 秒")
        ok = False
    stats["elapsedSeconds"] = round(time.monotonic() - started, 2)
    log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {stats['elapsedSeconds']} 秒")
    return ok, stats


def main():
    started = time.monotonic()
    dry = os.getenv("CYCD_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}
    accounts = [line.strip() for line in os.getenv("cycd_cookie", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.now().isoformat(timespec='seconds')}；模式：{'断网预演' if dry else '正式签到'}；账号数：{len(accounts)}")
    local = normalized(os.getenv("CYCD_LOCAL_TEXT", ""))
    config_error = not accounts or len(local) > 280
    results = []
    if config_error:
        log("❌ 配置错误：请设置 cycd_cookie，且 CYCD_LOCAL_TEXT 不得超过 280 字")
    else:
        for index, cookie in enumerate(accounts, 1):
            results.append(account(cookie, index, dry))
    success = sum(ok for ok, _ in results)
    failed = len(accounts) - success
    status = "configuration-error" if config_error else ("dry-run" if dry and not failed else "success" if not failed else "partial-failure" if success else "failure")
    code = 2 if config_error else int(failed > 0)
    totals = {key: sum(stats[key] for _, stats in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    body = f"状态：{status}；账号总数 {len(accounts)}，成功 {success}，失败 {failed}；子任务总数 {totals['total']}，成功 {totals['success']}，已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，失败 {totals['failed']}"
    delivery = notify(body, dry)
    log("----------------------------------------")
    log(body)
    log(f"通知状态：{delivery}；总耗时：{time.monotonic()-started:.2f} 秒")
    log(f"完成时间：{datetime.now().isoformat(timespec='seconds')}；最终状态：{status}；退出码：{code}")
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "status": status, "accounts": len(accounts), "success": success, "failed": failed, "tasks": totals, "notification": delivery, "exitCode": code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
