#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: AcFun Cookie每日任务
# cron: 21 0 * * *
# filename: beacherz_dailycheckin_plus_acfun.py
# publish-path: scripts/beacherz_dailycheckin_plus_acfun.py
# 发布文件名：beacherz_dailycheckin_plus_acfun.py；不得部署为 scripts/acfun.py 或 scripts/main.py。
"""AcFun Cookie 每日任务（产品专属发布路径：scripts/beacherz_dailycheckin_plus_acfun.py）。

上游：BeacherZ/dailycheckin-plus dailycheckin_plus/acfun/main.py
来源提交：8d3078bd1418fb6cef268cb9ccc5b8389dffcf86
License: MIT；保留上游归属。原文件无额外版权声明。

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

凭据：网页登录后复制 Cookie，至少包含 acPasstoken 与 auth_key（约一个月过期），
不必把手机号和密码写入环境变量。ACFUN_COOKIE 每个非空行一个账号 Cookie。
本任务与手机号密码版（scripts/acfun.py）凭据边界不同，必须使用产品专属路径发布。
默认仅签到与等级/香蕉查询。ACFUN_TASKS 可选 sign,info,like,like-cycle,danmu,banana,share。
like-cycle 表示点赞后取消；banana 消耗一根香蕉；danmu 公开发布文本。
ACFUN_DRY_RUN=1 完全断网预演；通知测试请设置 QINGLONG_NOTIFY=0。
隔离交付文件名 candidate.py 仅用于修复流水线，不得作为通用发布名。
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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "2ecd586638b72a85",
            "scripts/beacherz_dailycheckin_plus_acfun.py",
            "beacherz_dailycheckin_plus_acfun.py",
            "beacherz_dailycheckin_plus_acfun",
            "candidate.py",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import http.cookiejar
import importlib
import importlib.util
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

TITLE = "AcFun Cookie每日任务"
CATALOG_ID = "2ecd586638b72a85"
WEB = "https://www.acfun.cn"
ID = "https://id.app.acfun.cn"
INFO_URL = WEB + "/rest/pc-direct/user/personalInfo"
DISABLED = {"0", "false", "no", "off"}
ACTIONS = {"sign", "info", "like", "like-cycle", "danmu", "banana", "share"}
LABELS = {
    "sign": "签到",
    "info": "等级和香蕉余额查询",
    "like": "点赞",
    "like-cycle": "点赞后取消",
    "danmu": "发布弹幕",
    "banana": "投一根香蕉",
    "share": "分享任务上报",
}
ALLOWED_HOSTS = {
    "www.acfun.cn",
    "id.app.acfun.cn",
    "kuaishouzt.com",
    "api-ipv6.acfunchina.com",
    "v1.hitokoto.cn",
}


class TaskError(Exception):
    """可安全展示且不含凭据或原始响应的错误。"""


def log(message):
    print("[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), message), flush=True)


def enabled(name, default="0"):
    return os.getenv(name, default).strip().lower() not in DISABLED | {""}


def normalize(value):
    return " ".join(value.split()) if isinstance(value, str) else ""


def parse_cookie(cookie):
    """k=v; k2=v2 -> dict；只切第一个 =；换行也当分隔符。"""
    out = {}
    text = str(cookie or "").replace("\r\n", "\n").replace("\n", ";")
    for part in text.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        if key:
            out[key] = value.strip()
    return out


def load_accounts():
    """读取 ACFUN_COOKIE；兼容单账号别名 ACFUN_COOKIES。"""
    primary = os.getenv("ACFUN_COOKIE", "")
    alias = os.getenv("ACFUN_COOKIES", "")
    text = primary if primary.strip() else alias
    return [line.strip() for line in text.splitlines() if line.strip()]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口跳转已拒绝，避免跨域传递凭据")


class Client:
    def __init__(self, pairs):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.70"
            ),
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": WEB + "/",
        }
        self._apply_cookies(pairs)
        self.st = ""
        self.info = {}
        self.username = urllib.parse.unquote(pairs.get("ac_username") or "").strip()

    def _apply_cookies(self, pairs):
        for name, value in pairs.items():
            cookie = http.cookiejar.Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=".acfun.cn",
                domain_specified=True,
                domain_initial_dot=True,
                path="/",
                path_specified=True,
                secure=False,
                expires=None,
                discard=True,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
            self.jar.set_cookie(cookie)

    def request(self, url, data=None, method=None, headers=None, raw=False, timeout=15, limit=2 * 1024 * 1024):
        host = urllib.parse.urlsplit(url).hostname or ""
        if host not in ALLOWED_HOSTS:
            raise TaskError("业务接口域名不在白名单")
        body = None
        if data is not None:
            if isinstance(data, (dict, list, tuple)):
                body = urllib.parse.urlencode(data).encode("utf-8")
            elif isinstance(data, str):
                body = data.encode("utf-8")
            else:
                body = data
        verb = method or ("POST" if body is not None else "GET")
        h = dict(self.headers)
        if body is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        h.update(headers or {})
        try:
            req = urllib.request.Request(url, data=body, headers=h, method=verb)
            with self.opener.open(req, timeout=timeout) as response:
                content = response.read(limit + 1)
            if len(content) > limit:
                raise TaskError("接口响应过大")
            decoded = content.decode("utf-8")
            return decoded if raw else json.loads(decoded)
        except TaskError:
            raise
        except Exception:
            raise TaskError("网络、HTTP 或响应解析失败；未输出原始错误与响应") from None

    def successful(self, data, code=0):
        if not isinstance(data, dict) or type(data.get("result")) is not int or data["result"] != code:
            raise TaskError("接口未确认业务成功（响应或业务码不符合源接口契约）")
        return data

    def fetch_info(self):
        data = self.successful(self.request(INFO_URL))
        info = data.get("info")
        if not isinstance(info, dict):
            raise TaskError("Cookie 已失效或用户信息缺失")
        self.info = info
        if not self.username:
            for key in ("userName", "username", "nickName", "nickname", "name"):
                value = str(info.get(key) or "").strip()
                if value:
                    self.username = value
                    break
        return info

    def show_identity(self, index):
        if self.username:
            log("账号身份（昵称）：%s" % json.dumps(self.username, ensure_ascii=False))
            return
        for key in ("userId", "uid", "userName", "username", "nickName", "nickname"):
            value = self.info.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value).strip()
                if text and not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    log("账号身份（%s）：%s" % (key, json.dumps(text, ensure_ascii=False)))
                    return
        log("账号 %s：未返回公开身份，使用序号标识" % index)

    def video(self):
        data = self.successful(self.request(WEB + "/rest/pc-direct/rank/channel"))
        ranks = data.get("rankList")
        if not isinstance(ranks, list) or not ranks or not isinstance(ranks[0], dict):
            raise TaskError("排行榜没有可用视频")
        value = str(ranks[0].get("contentId", ""))
        if not value.isdigit():
            raise TaskError("视频标识不符合契约")
        return value

    def get_token(self):
        data = self.successful(
            self.request(ID + "/rest/web/token/get?sid=acfun.midground.api", method="POST")
        )
        token = data.get("acfun.midground.api_st")
        if not isinstance(token, str) or not token:
            raise TaskError("点赞令牌缺失")
        self.st = token
        return token

    def action(self, action, content):
        if action == "sign":
            data = self.successful(self.request(WEB + "/rest/pc-direct/user/signIn", method="POST"))
            msg = str(data.get("msg") or "签到成功").strip() or "签到成功"
            log("签到信息：%s" % msg)
        elif action == "info":
            info = self.info or self.fetch_info()
            for key, label in (("level", "等级"), ("banana", "香蕉余额")):
                value = info.get(key)
                if type(value) not in (int, float) or value < 0:
                    raise TaskError("账户统计字段缺失或无效")
                log("%s：%s" % (label, value))
        elif action in ("like", "like-cycle"):
            if not self.st:
                self.get_token()
            body = {
                "kpn": "ACFUN_APP",
                "kpf": "PC_WEB",
                "subBiz": "mainApp",
                "interactType": "1",
                "objectType": "2",
                "objectId": content,
                "acfun.midground.api_st": self.st,
                "extParams[isPlaying]": "false",
                "extParams[showCount]": "1",
                "extParams[otherBtnClickedCount]": "10",
                "extParams[playBtnClickedCount]": "0",
            }
            self.successful(
                self.request("https://kuaishouzt.com/rest/zt/interact/add", body, method="POST"),
                1,
            )
            log("点赞接口确认成功")
            if action == "like-cycle":
                self.successful(
                    self.request(
                        "https://kuaishouzt.com/rest/zt/interact/delete", body, method="POST"
                    ),
                    1,
                )
                log("取消点赞接口确认成功")
        elif action == "banana":
            self.successful(
                self.request(
                    WEB + "/rest/pc-direct/banana/throwBanana",
                    {"resourceId": content, "count": "1", "resourceType": "2"},
                    method="POST",
                )
            )
        elif action == "danmu":
            page = self.request(WEB + "/v/ac" + content, raw=True)
            video = re.search(r'"currentVideoId"\s*:\s*(\d+)', page)
            channel = re.search(
                r"\{subChannelId:(\d+),subChannelName:\"([^\r\n\"]+)\"\}", page
            )
            if not video or not channel:
                raise TaskError("视频或分区字段缺失，禁止使用硬编码目标发弹幕")
            text = public_text(dry=False)
            self.successful(
                self.request(
                    WEB + "/rest/pc-direct/new-danmaku/add",
                    {
                        "mode": "1",
                        "color": "16777215",
                        "size": "25",
                        "body": text,
                        "videoId": video.group(1),
                        "position": "2719",
                        "type": "douga",
                        "id": content,
                        "subChannelId": channel.group(1),
                        "subChannelName": channel.group(2),
                    },
                    method="POST",
                )
            )
        elif action == "share":
            self.successful(
                self.request(
                    "https://api-ipv6.acfunchina.com/rest/app/task/reportTaskAction"
                    "?taskType=1&market=tencent&product=ACFUN_APP&appMode=0",
                    method="GET",
                )
            )


def public_text(dry=False):
    fallback = normalize(os.getenv("ACFUN_LOCAL_TEXT", "今天也要保持好心情。"))
    if not fallback or len(fallback) > 280:
        raise TaskError("本地备用文案必须为 1 至 280 字符")
    if dry:
        return fallback
    try:
        opener = urllib.request.build_opener(NoRedirect())
        req = urllib.request.Request(
            "https://v1.hitokoto.cn/?encode=json",
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        with opener.open(req, timeout=8) as response:
            content = response.read(16385)
        if len(content) > 16384:
            raise ValueError("oversized")
        data = json.loads(content)
        text = normalize(data.get("hitokoto"))
        author = normalize(data.get("from_who"))
        source = normalize(data.get("from"))
        if not text:
            raise ValueError("missing-text")
        if author and source:
            text = "%s —— %s《%s》" % (text, author, source)
        elif source:
            text = "%s ——《%s》" % (text, source)
        elif author:
            text = "%s —— %s" % (text, author)
        if len(text) > 280:
            raise ValueError("overlong")
        log("文案：一言内容与署名已校验（不输出正文）")
        return text
    except Exception:
        log("⚠️ 文案提供方不可用或内容无效，使用本地备用文案")
        return fallback


def notify(body):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in DISABLED:
        return "已关闭"
    try:
        try:
            sender = importlib.import_module("notify").send
        except (ImportError, AttributeError):
            paths = []
            if os.getenv("QINGLONG_NOTIFY_DIR"):
                paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
            paths += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                js_paths = []
                if os.getenv("QINGLONG_NOTIFY_DIR"):
                    js_paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "sendNotify.js")
                js_paths += [
                    Path("/ql/data/scripts/sendNotify.js"),
                    Path("/ql/scripts/sendNotify.js"),
                ]
                if any(p.is_file() for p in js_paths):
                    raise RuntimeError("仅发现 JS 通知入口，当前 Python 任务跳过")
                raise RuntimeError("通知模块不可用")
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = module.send
        sender(TITLE, body)
        return "已发送"
    except Exception:
        log("⚠️ 通知不可用或发送失败，保留业务退出码")
        return "不可用或失败"


def validate_cookie_line(line):
    pairs = parse_cookie(line)
    if not pairs.get("acPasstoken"):
        raise TaskError("Cookie 里没有 acPasstoken，请重新登录后整块复制")
    if not pairs.get("auth_key"):
        raise TaskError("Cookie 里没有 auth_key，请重新登录后整块复制")
    return pairs


def main():
    started = time.monotonic()
    dry = enabled("ACFUN_DRY_RUN")
    log("========== %s ==========" % TITLE)
    log(
        "开始时间：%s；模式：%s"
        % (
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "完全断网预演" if dry else "正式运行",
        )
    )
    lines = load_accounts()
    log("账号总数：%s" % len(lines))
    tasks = [s.strip() for s in os.getenv("ACFUN_TASKS", "sign,info").split(",") if s.strip()]
    results = []
    total = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    configuration_error = (
        not lines
        or not tasks
        or bool(set(tasks) - ACTIONS)
        or len(tasks) != len(set(tasks))
        or {"like", "like-cycle"} <= set(tasks)
    )
    if "danmu" in tasks and not 1 <= len(
        normalize(os.getenv("ACFUN_LOCAL_TEXT", "今天也要保持好心情。"))
    ) <= 280:
        configuration_error = True
    if configuration_error:
        log("❌ 配置错误：检查 Cookie、任务列表、重复动作或备用文案；不输出配置值")
    else:
        for index, line in enumerate(lines, 1):
            t0 = time.monotonic()
            stage_total = len(tasks) + 1
            stats = {
                "total": stage_total,
                "success": 0,
                "alreadyComplete": 0,
                "skipped": 0,
                "failed": 0,
            }
            log("账号 %s 开始" % index)
            auth_ok = False
            client = None
            stage_start = time.monotonic()
            try:
                log("账号 %s 阶段 1/%s：Cookie 校验与身份确认" % (index, stage_total))
                pairs = validate_cookie_line(line)
                if dry:
                    nickname = urllib.parse.unquote(pairs.get("ac_username") or "").strip()
                    if nickname:
                        log("账号身份（昵称）：%s" % json.dumps(nickname, ensure_ascii=False))
                    else:
                        log("账号 %s：预演未请求接口，使用序号标识" % index)
                    log("断网预演：Cookie 字段齐全；未发送请求、未验证登录态")
                else:
                    client = Client(pairs)
                    client.fetch_info()
                    client.show_identity(index)
                auth_ok = True
                stats["success"] += 1
                log(
                    "✅ Cookie 校验："
                    + ("预演通过（未验证真实登录）" if dry else "业务成功")
                    + "；耗时 %.2f 秒" % (time.monotonic() - stage_start)
                )
            except TaskError as exc:
                stats["failed"] += 1
                log("❌ Cookie 校验：%s；耗时 %.2f 秒" % (exc, time.monotonic() - stage_start))
            content = None
            for stage, action in enumerate(tasks, 2):
                st = time.monotonic()
                log("账号 %s 阶段 %s/%s：%s" % (index, stage, stage_total, LABELS[action]))
                if not auth_ok:
                    stats["skipped"] += 1
                    log("⏭️ Cookie 或配置失败，跳过；耗时 0.00 秒")
                    continue
                try:
                    if dry:
                        if action == "danmu":
                            public_text(dry=True)
                        log("断网预演：参数和执行计划通过；未发送请求、未执行副作用")
                    else:
                        if action in ("like", "like-cycle", "danmu", "banana") and content is None:
                            content = client.video()
                            log("排行榜视频选择成功")
                        client.action(action, content)
                    stats["success"] += 1
                    log(
                        "✅ %s：" % LABELS[action]
                        + ("预演通过" if dry else "业务成功")
                        + "；耗时 %.2f 秒" % (time.monotonic() - st)
                    )
                except TaskError as exc:
                    stats["failed"] += 1
                    log("❌ %s：%s；耗时 %.2f 秒" % (LABELS[action], exc, time.monotonic() - st))
                except Exception:
                    stats["failed"] += 1
                    log(
                        "❌ %s：响应字段或运行异常（已脱敏）；耗时 %.2f 秒"
                        % (LABELS[action], time.monotonic() - st)
                    )
            for key in total:
                total[key] += stats[key]
            ok = stats["failed"] == 0 and stats["skipped"] == 0
            results.append(ok)
            log(
                "账号 %s 统计：总任务 %s，成功 %s，已完成 %s，跳过 %s，失败 %s；耗时 %.2f 秒"
                % (
                    index,
                    stats["total"],
                    stats["success"],
                    stats["alreadyComplete"],
                    stats["skipped"],
                    stats["failed"],
                    time.monotonic() - t0,
                )
            )
    successes = sum(1 for ok in results if ok)
    failures = len(lines) - successes if lines else (1 if configuration_error else 0)
    if configuration_error and not lines:
        failures = 1
    code = 1 if configuration_error or failures else 0
    if configuration_error:
        status = "configuration-error"
    elif dry and not failures:
        status = "dry-run"
    elif failures and successes:
        status = "partial-failure"
    elif failures:
        status = "failure"
    else:
        status = "success"
    body = (
        "模式：%s；账号总数 %s，成功 %s，失败 %s；状态 %s；子任务成功 %s，失败 %s，跳过 %s。"
        % (
            "完全断网预演" if dry else "正式运行",
            len(lines),
            successes,
            failures if lines else int(configuration_error),
            status,
            total["success"],
            total["failed"],
            total["skipped"],
        )
    )
    if dry:
        body += "预演未验证真实业务。"

        def deny_external_io(event, args):
            if event.startswith("socket.") or event in (
                "subprocess.Popen",
                "os.system",
                "os.exec",
                "os.posix_spawn",
                "os.fork",
                "os.forkpty",
                "pty.spawn",
                "ctypes.dlopen",
            ):
                raise RuntimeError("断网预演禁止网络及外部通知进程")

        sys.addaudithook(deny_external_io)
        notification = notify(body)
    else:
        notification = notify(body)
    log("----------------------------------------")
    log(body)
    log("子任务统计：%s" % json.dumps(total, ensure_ascii=False))
    log(
        "总耗时：%.2f 秒；完成时间：%s"
        % (time.monotonic() - started, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    log("通知状态：%s；最终状态：%s" % (notification, status))
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
                "mode": "dry-run" if dry else "live",
                "accounts": len(lines),
                "success": successes,
                "failed": failures if lines else int(configuration_error),
                "steps": total,
                "status": status,
                "notification": notification,
                "exitCode": code,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
