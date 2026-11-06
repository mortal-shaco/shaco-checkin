#!/usr/bin/env python3
# name: 微博黄婷婷超话每日任务
# cron: 28 10 * * *
# 上游归属: qqqqqqiu0804/weibo-chaohua-checkin，account2_daily.py
# 上游提交: b59b2220eb25a77c0c65f2d106015bfb891b9ddc
# 许可证: MIT，沿用上游许可。输入源码未包含独立版权声明。
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
"""
微博黄婷婷超话签到，以及显式启用的评论、带标签转发，发布后保留。
每天默认北京时间 08:15 执行，计划为维护版新增，可在青龙修改。

配置 WEIBO_ACCOUNTS，每个非空行一个 m.weibo.cn 的完整 Cookie。
浏览器登录 https://m.weibo.cn 后，在开发者工具的网络面板复制该站请求的
Cookie 请求头值。保留其中分号、等号，切勿提供给第三方或写入仓库。
默认仅签到。WEIBO_TASKS=checkin,comment,repost 显式开启公开互动，
默认每日评论 4 条、转发 2 条，均保留、不删除。内容先取一言并署名，失败
使用本地模板。WEIBO_TAG 或 --tag 可覆盖 #黄婷婷[超话]#。
WEIBO_DRY_RUN=1 或 --dry-run 完全断网，不修改任何本地状态。
--force 忽略当日已完成配额，但仍拒绝重试结果不确定的公开发布。

可选 --data-dir / WEIBO_DATA_DIR 指定原 data-htt2 目录，单账号时兼容
session.json（version 2 cookies）、config.json、state.json（version 4 history）。
仅在未配置 WEIBO_ACCOUNTS 时读取指定目录的 session.json，不调用 weibo-exp。
config.json 支持 comment_limit、repost_limit、comment_templates、max_feed_pages、
max_posts_per_topic。多账号按 Cookie 摘要隔离存储，每次请求后原子保存续期 Cookie。
状态以官方 UID 绑定，并按天保留七天记录。状态目录应保留，以避免重复公开发布。
发布前写入待确认记录。超时、响应不明或中断后须人工核对网页与 state.json 的
pending 字段，确认是否发布成功再恢复，--force 不绕过该保护。
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
        _ql_notify_identities = ('60bd73f06f55fa82', 'scripts/account2_daily.py', 'account2_daily.py', 'account2_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
import contextlib
import datetime
import fnmatch
import hashlib
import html
import http.cookiejar
import http.client
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import fcntl

BASE = "https://m.weibo.cn"
TOPIC_ID = "100808b0cbb89cb1591ec01a568798e0d788ed"
DEFAULT_TAG = "#黄婷婷[超话]#"
TITLE = "微博黄婷婷超话每日任务"
CATALOG = "60bd73f06f55fa82"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
ENABLED = {"1", "true", "yes", "on"}
DISABLED = {"0", "false", "no", "off"}


class TaskError(Exception):
    pass


def log(message):
    print("[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), message), flush=True)


def load_json(path, default):
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError):
        raise TaskError("本地配置或进度文件无效，请人工核对") from None


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".weibo-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parse_cookie_line(line):
    if "\r" in line or "\n" in line:
        raise TaskError("Cookie 不得包含换行")
    cookies = []
    for part in line.split(";"):
        if not part.strip():
            continue
        name, separator, value = part.strip().partition("=")
        if not separator or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) or not value:
            raise TaskError("Cookie 格式无效，应为完整请求头值")
        cookies.append({"name": name, "value": value, "domain": "m.weibo.cn", "path": "/", "secure": True, "host_only": True})
    if not cookies:
        raise TaskError("账号 Cookie 为空")
    return cookies


class Weibo:
    def __init__(self, cookies, session_path, session):
        self.jar = http.cookiejar.CookieJar()
        self.path = session_path
        self.session = session
        for item in cookies:
            domain = item.get("domain", "").lower()
            if domain.lstrip(".") not in {"m.weibo.cn", "weibo.cn"}:
                continue
            self.jar.set_cookie(http.cookiejar.Cookie(
                0, item["name"], item["value"], None, False, domain,
                not item.get("host_only", False), domain.startswith("."),
                item.get("path") or "/", True, bool(item.get("secure", False)),
                item.get("expires"), False, None, None, {}, False))
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar))

    def persist(self):
        self.session["cookies"] = [
            {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path,
             "host_only": not c.domain_specified, "secure": c.secure, "expires": c.expires}
            for c in self.jar]
        self.session["updated_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        save_json(self.path, self.session)

    def request(self, method, target, form=None):
        url = urllib.parse.urljoin(BASE + "/", target)
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "m.weibo.cn" or parsed.username:
            raise TaskError("接口地址不在允许的微博 HTTPS 域名内")
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "User-Agent": UA, "Accept": "application/json", "Referer": BASE + "/",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(2097153)
            self.persist()
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError):
            raise TaskError("微博请求失败或超时，未输出响应或凭据") from None
        if len(raw) > 2097152:
            raise TaskError("微博响应超过安全大小")
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TaskError("微博未返回有效 JSON，可能需要重新登录") from None
        if not isinstance(payload, dict) or type(payload.get("ok")) is not int or payload["ok"] != 1:
            raise TaskError("微博业务未明确成功，请核对登录状态和接口")
        result = payload.get("data", payload)
        if not isinstance(result, dict):
            raise TaskError("微博业务响应结构不符合预期")
        return result

    def get(self, target):
        return self.request("GET", target)

    def post(self, target, form):
        return self.request("POST", target, form)


def sval(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else ""
    if isinstance(v, (int, float)):
        return "" if v == 0 else str(int(v))
    return str(v)


def parse_topics(data):
    out = []
    seen = set()

    def visit(card):
        for nested in card.get("card_group") or []:
            if isinstance(nested, dict):
                visit(nested)
        title = sval(card.get("title_sub"))
        if not title:
            return
        itemid = sval(card.get("itemid"))
        scheme = sval(card.get("scheme"))
        m = re.search(r"100808[0-9a-z]{32}", scheme + " " + itemid, re.I)
        if not m:
            return
        tid = m.group(0)
        if tid in seen:
            return
        btn_name, btn_url = "", ""
        for b in card.get("buttons") or []:
            n, u = sval(b.get("name")), sval(b.get("scheme"))
            if not btn_name:
                btn_name, btn_url = n, u
            if "签到" in n or "已签" in n:
                btn_name, btn_url = n, u
                break
        if not (itemid.startswith("follow_super_follow_") or "签到" in btn_name or "已签" in btn_name):
            return
        seen.add(tid)
        out.append({
            "id": tid, "name": title, "button": btn_name, "url": btn_url,
            "signed": "已签" in btn_name,
            "can_checkin": "签到" in btn_name and "已签" not in btn_name,
        })

    for c in data.get("cards") or []:
        if isinstance(c, dict):
            visit(c)
    return out


def parse_posts(data, self_uid):
    out = []
    seen = set()

    def visit(card):
        for nested in card.get("card_group") or []:
            if isinstance(nested, dict):
                visit(nested)
        mb = card.get("mblog")
        if not isinstance(mb, dict):
            return
        mid = sval(mb.get("mid")) or sval(mb.get("id"))
        if not mid or mid in seen:
            return
        seen.add(mid)
        uid = sval((mb.get("user") or {}).get("id"))
        out.append({"mid": mid, "is_self": bool(self_uid) and uid == self_uid})

    for c in data.get("cards") or []:
        if isinstance(c, dict):
            visit(c)
    return out


def created_id(data):
    if not isinstance(data, dict):
        return ""
    dm = data.get("data") if isinstance(data.get("data"), dict) else {}
    cands = [dm.get("idstr"), dm.get("id"), dm.get("mid")]
    for key in ("comment", "status"):
        sub = data.get(key) or dm.get(key)
        if isinstance(sub, dict):
            cands += [sub.get("idstr"), sub.get("id"), sub.get("mid")]
    cands += [data.get("idstr"), data.get("id"), data.get("mid")]
    for c in cands:
        v = sval(c)
        if v:
            return v
    return ""


def choose_template(post_mid, date_topic, templates):
    if not templates:
        return "打卡"
    h = 2166136261
    for ch in (date_topic + ":" + post_mid):
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return templates[h % len(templates)]


def public_text(mid, today, templates, tag=""):
    """独立无 Cookie 的一言请求，所有声明的失败均回落到本地。"""
    def normalize(value):
        return " ".join(value.split()) if isinstance(value, str) else ""

    prefix = normalize(tag)
    content = ""
    try:
        request = urllib.request.Request("https://v1.hitokoto.cn/?encode=json", headers={"Accept": "application/json"})
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=8) as response:
            raw = response.read(16385)
        if len(raw) > 16384:
            raise ValueError()
        data = json.loads(raw)
        text = normalize(data.get("hitokoto"))
        author = normalize(data.get("from_who"))
        source = normalize(data.get("from"))
        if not text:
            raise ValueError()
        content = text
        if author and source:
            content += " —— %s《%s》" % (author, source)
        elif source:
            content += " ——《%s》" % source
        elif author:
            content += " —— %s" % author
        if len((prefix + " " + content).strip()) > 280:
            raise ValueError()
        log("公开文案：一言获取成功，已应用署名格式")
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError, UnicodeError, AttributeError):
        content = normalize(choose_template(mid, today + ":" + TOPIC_ID, templates))
        log("公开文案：一言不可用，使用本地模板")
    result = (prefix + " " + content).strip()
    if not result or len(result) > 280:
        raise TaskError("本地文案或标签为空或超过 280 字，请调整配置")
    return result


@contextlib.contextmanager
def stage(number, name):
    start = time.monotonic()
    log("阶段 %d · %s · 开始" % (number, name))
    try:
        yield
    finally:
        log("阶段 %d · %s · 耗时 %.2f 秒" % (number, name, time.monotonic() - start))


def integer(config, name, default, minimum, maximum):
    value = config.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise TaskError("配置 %s 必须为 %d 至 %d 的整数" % (name, minimum, maximum))
    return value


def run_account(account, index, args, tasks, dry, stats):
    raw_cookie, directory, legacy = account
    with stage(1, "读取账号与任务配置"):
        config = load_json(directory / "config.json", {})
        comments = integer(config, "comment_limit", 4, 0, 100)
        reposts = integer(config, "repost_limit", 2, 0, 100)
        page_limit = integer(config, "max_feed_pages", 8, 1, 100)
        post_limit = max(integer(config, "max_posts_per_topic", 80, 1, 1000), comments + reposts)
        templates = config.get("comment_templates") or ["打卡"]
        if os.environ.get("WEIBO_LOCAL_TEXT"):
            templates = [os.environ["WEIBO_LOCAL_TEXT"]]
        if not isinstance(templates, list) or not all(isinstance(x, str) and x.strip() for x in templates):
            raise TaskError("comment_templates 必须为非空中文案字符串列表")
        if not args.tag.strip() or len(args.tag) > 200 or "\n" in args.tag or "\r" in args.tag:
            raise TaskError("超话标签为空、过长或包含换行")
        session_path = directory / "session.json"
        session = load_json(session_path, {"version": 2, "cookies": []})
        cookies = session.get("cookies") if legacy else parse_cookie_line(raw_cookie)
        if not legacy:
            credential_hash = hashlib.sha256(raw_cookie.encode()).hexdigest()
            if session.get("credential_sha256") == credential_hash and session.get("cookies"):
                cookies = session["cookies"]
            session["credential_sha256"] = credential_hash
        if not isinstance(cookies, list) or not cookies or not all(
                isinstance(c, dict) and isinstance(c.get("name"), str) and isinstance(c.get("value"), str)
                for c in cookies):
            raise TaskError("会话缺少有效 cookies，需从浏览器重新获取")
        stats["total"] = (1 if "checkin" in tasks else 0) + (comments if "comment" in tasks else 0) + (reposts if "repost" in tasks else 0)
        if dry:
            stats["skipped"] = stats["total"]
            with stage(2, "断网预演"):
                log("DRY_RUN_OK：账号 %d 参数校验通过；签到=%s，评论配额=%d，转发配额=%d" % (
                    index, "checkin" in tasks, comments if "comment" in tasks else 0, reposts if "repost" in tasks else 0))
                log("不发出微博、一言或通知网络请求，不创建进度文件；公开互动需显式选择")
            return

    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "account.lock").open("a") as lock:
        os.chmod(directory / "account.lock", 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise TaskError("同一账号正在执行，停止以避免重复互动") from None
        state_path = directory / "state.json"
        state = load_json(state_path, {"version": 4, "history": {}, "uid": ""})
        wb = Weibo(cookies, session_path, session)
        with stage(2, "验证官方登录状态"):
            conf = wb.get("/api/config")
            if conf.get("login") is not True or not sval(conf.get("uid")) or not sval(conf.get("st")):
                raise TaskError("登录状态未验证或缺少 UID、st，请更新 Cookie")
            uid, st = sval(conf["uid"]), sval(conf["st"])
            if state.get("uid") and str(state["uid"]) != uid:
                raise TaskError("进度文件绑定了其他账号，拒绝跨账号写入")
            state["uid"] = uid
            identity = (conf.get("user") or {}).get("screen_name") if isinstance(conf.get("user"), dict) else None
            log("官方账号 UID=%s%s" % (uid, " 昵称=" + str(identity) if identity else ""))
            if state.get("pending"):
                raise TaskError("存在待核对的发布记录，请人工确认结果后处理 pending，禁止自动重发")
            today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
            cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=6)).isoformat()
            history = state.setdefault("history", {})
            if not isinstance(history, dict):
                raise TaskError("历史进度结构无效")
            state["history"] = {day: value for day, value in history.items() if day >= cutoff}
            day = state["history"].setdefault(today, {})
            if args.force:
                day.pop(TOPIC_ID, None)
            record = day.setdefault(TOPIC_ID, {"comments": [], "reposts": []})
            for key in ("comments", "reposts"):
                record.setdefault(key, [])
                if not isinstance(record[key], list):
                    raise TaskError("互动进度结构无效")
            save_json(state_path, state)

        with stage(3, "检查关注超话与签到"):
            topics = parse_topics(wb.get("/api/container/getIndex?containerid=100803_-_followsuper"))
            topic = next((t for t in topics if t["id"] == TOPIC_ID), None)
            if topic is None:
                raise TaskError("关注列表未找到黄婷婷超话，请先用该账号关注")
            if "checkin" not in tasks:
                log("⏭️ 未选择签到任务")
            elif topic["signed"]:
                stats["alreadyComplete"] += 1
                log("☑️ 官方关注列表确认今日已签到")
            elif topic["can_checkin"] and topic["url"]:
                wb.get(topic["url"])
                refreshed = parse_topics(wb.get("/api/container/getIndex?containerid=100803_-_followsuper"))
                if not any(t["id"] == TOPIC_ID and t["signed"] for t in refreshed):
                    raise TaskError("签到请求后未确认已签到状态")
                stats["success"] += 1
                log("✅ 签到成功，已回读确认")
            else:
                raise TaskError("签到无有效入口，不能确认为成功")

        needed = {}
        for task, key, limit in (("comment", "comments", comments), ("repost", "reposts", reposts)):
            if task in tasks:
                completed = min(limit, len(record[key]))
                stats["alreadyComplete"] += completed
                needed[key] = limit - completed
        if not sum(needed.values()):
            log("☑️ 所选互动配额已完成或未启用")
            return
        with stage(4, "分页筛选帖子"):
            posts, seen, cursors, cursor = [], set(record["comments"]) | set(record["reposts"]), set(), ""
            for _ in range(page_limit):
                path = "/api/container/getIndex?" + urllib.parse.urlencode({"containerid": TOPIC_ID, "since_id": cursor})
                data = wb.get(path)
                for post in parse_posts(data, uid):
                    if not post["is_self"] and post["mid"] not in seen:
                        seen.add(post["mid"])
                        posts.append(post["mid"])
                next_cursor = sval((data.get("cardlistInfo") or {}).get("since_id"))
                if len(posts) >= post_limit or not next_cursor or next_cursor in cursors:
                    break
                cursors.add(next_cursor)
                cursor = next_cursor
            log("候选帖子 %d 条，已排除本人、重复帖子与当日已互动帖子" % len(posts))
        insufficient = len(posts) < sum(needed.values())
        offset = 0
        for stage_num, task, key in ((5, "comment", "comments"), (6, "repost", "reposts")):
            count = needed.get(key, 0)
            if not count:
                continue
            targets = posts[offset:offset + count]
            offset += len(targets)
            with stage(stage_num, "发布并保留评论" if task == "comment" else "发布并回读带标签转发"):
                for number, mid in enumerate(targets, 1):
                    content = public_text(mid, today, templates, args.tag if task == "repost" else "")
                    state["pending"] = {"date": today, "action": task, "mid": mid}
                    save_json(state_path, state)
                    if task == "comment":
                        result = wb.post("/api/comments/create", {"content": content, "mid": mid, "st": st})
                    else:
                        result = wb.post("/api/statuses/repost", {"id": mid, "mid": mid, "content": content, "dualPost": "0", "st": st})
                    new_id = created_id(result)
                    if not new_id:
                        raise TaskError("发布响应没有新内容 ID，保留待核对记录，禁止自动重试")
                    state["pending"]["created_id"] = new_id
                    save_json(state_path, state)
                    if task == "repost":
                        detail = wb.get("/api/statuses/show?" + urllib.parse.urlencode({"id": new_id}))
                        if args.tag not in html.unescape(re.sub(r"<[^>]+>", "", sval(detail.get("text")))):
                            raise TaskError("转发已发布但标签回读未通过，保留待核对记录")
                    record[key].append(mid)
                    state.pop("pending", None)
                    save_json(state_path, state)
                    stats["success"] += 1
                    log("✅ %s %d/%d，官方返回新内容 ID 并确认成功，内容保留" % ("评论" if task == "comment" else "转发", number, len(targets)))
                    time.sleep(random.uniform(8, 14))
        if insufficient:
            raise TaskError("可用帖子不足，尚未达到所选每日互动配额")


def notify(summary, dry):
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in DISABLED:
        return "已关闭"
    selectors = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selectors is not None:
        names = [CATALOG, "account2_daily.py", "candidate.py", pathlib.Path(__file__).name,
                 "scripts/account2_daily.py"]
        selected = any(fnmatch.fnmatch(name, pattern) for pattern in re.split(r"[,;\s]+", selectors.strip()) if pattern for name in names)
    else:
        selected = False  # listed-only：此任务不在输入提供的默认清单中
    if switch not in ENABLED and not selected:
        return "未列入通知清单"
    if dry:
        log("通知摘要已生成；断网预演仅本地显示，不调用可能联网的通知模块")
        return "断网预演仅本地显示"
    body = "账号总数 {accounts}，成功 {success}，失败 {failure}，状态 {status}".format(**summary)
    # 隔离通知模块的输出和异常，避免第三方实现泄露配置，也不影响业务退出码。
    code = '''import importlib.util, sys
path, title, body = sys.argv[1:]
if path:
    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(title, body)
'''
    paths = [None]
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        paths.append(pathlib.Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths += [pathlib.Path("/ql/data/scripts/notify.py"), pathlib.Path("/ql/scripts/notify.py")]
    for path in paths:
        if path is not None and not path.is_file():
            continue
        try:
            result = subprocess.run([sys.executable, "-c", code, str(path) if path else "", TITLE, body],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
            if result.returncode == 0:
                return "已发送"
            # 已发现模块但发送失败时可能已投递，不继续其他渠道以免重复通知。
            if path is not None:
                return "投递失败，业务退出码保持"
        except (OSError, subprocess.TimeoutExpired):
            return "投递不可用，业务退出码保持"
    return "未找到可用 notify.py，业务退出码保持"


def main():
    start = time.monotonic()
    log("========== %s ==========" % TITLE)
    log("开始时间 %s" % datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--tag", default=os.environ.get("WEIBO_TAG", DEFAULT_TAG))
    parser.add_argument("--data-dir", default=os.environ.get("WEIBO_DATA_DIR"))
    dry = os.environ.get("WEIBO_DRY_RUN", "").lower() in ENABLED or "--dry-run" in sys.argv
    summary = {"accounts": 0, "success": 0, "failure": 0, "status": "configuration-error", "mode": "dry-run" if dry else "live"}
    totals = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
    code = 2
    try:
        try:
            args = parser.parse_args()
        except SystemExit as exc:
            if exc.code == 0:
                summary["status"] = "help"
                code = 0
                return code
            raise TaskError("命令行参数无效") from None
        tasks = set(os.environ.get("WEIBO_TASKS", "checkin").split(","))
        tasks = {task.strip() for task in tasks}
        if not tasks or not tasks <= {"checkin", "comment", "repost"}:
            raise TaskError("WEIBO_TASKS 仅允许 checkin、comment、repost，以逗号组合")
        base = pathlib.Path(args.data_dir).expanduser() if args.data_dir else pathlib.Path(__file__).resolve().parent / "data-htt2"
        lines = [line.strip() for line in os.environ.get("WEIBO_ACCOUNTS", "").splitlines() if line.strip()]
        if len(lines) != len(set(lines)):
            raise TaskError("账号列表包含重复 Cookie，请删除重复项")
        accounts = []
        for line in lines:
            directory = base if len(lines) == 1 else base / hashlib.sha256(line.encode()).hexdigest()
            accounts.append((line, directory, False))
        if not accounts and args.data_dir:
            accounts = [(None, base, True)]
        summary["accounts"] = len(accounts)
        log("运行模式 %s；账号数 %d；任务 %s" % (summary["mode"], len(accounts), ",".join(sorted(tasks))))
        if not accounts:
            raise TaskError("请配置 WEIBO_ACCOUNTS，每个非空行填写一个账号的 Cookie")
        for index, account in enumerate(accounts, 1):
            account_start = time.monotonic()
            stats = dict.fromkeys(totals, 0)
            log("---------- 账号 %d/%d ----------" % (index, len(accounts)))
            try:
                run_account(account, index, args, tasks, dry, stats)
                summary["success"] += 1
            except Exception as exc:
                stats["failure"] = max(1, stats["total"] - stats["success"] - stats["alreadyComplete"] - stats["skipped"])
                summary["failure"] += 1
                stats["total"] = max(stats["total"], stats["success"] + stats["alreadyComplete"] + stats["skipped"] + stats["failure"])
                log("❌ " + (str(exc) if isinstance(exc, TaskError) else "账号处理异常，详情已抑制以保护凭据"))
            for key in totals:
                totals[key] += stats[key]
            log("账号 %d 统计：总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d，耗时 %.2f 秒" % (
                index, stats["total"], stats["success"], stats["alreadyComplete"], stats["skipped"], stats["failure"], time.monotonic() - account_start))
        code = 1 if summary["failure"] else 0
        summary["status"] = ("partial-failure" if summary["success"] else "failure") if code else ("dry-run" if dry else "success")
    except Exception as exc:
        log("❌ " + (str(exc) if isinstance(exc, TaskError) else "配置处理异常，详情已抑制以保护凭据"))
    finally:
        try:
            notification = notify(summary, dry)
        except Exception:
            notification = "通知异常，业务退出码保持"
        summary["tasks"] = totals
        summary["notification"] = notification
        summary["elapsedSeconds"] = round(time.monotonic() - start, 2)
        log("----------------------------------------")
        log("账号统计：总数 %d，成功 %d，失败 %d" % (summary["accounts"], summary["success"], summary["failure"]))
        log("子任务统计：总数 %(total)d，成功 %(success)d，已完成 %(alreadyComplete)d，跳过 %(skipped)d，失败 %(failure)d" % totals)
        log("通知状态：%s" % notification)
        log("完成时间 %s；总耗时 %.2f 秒；最终状态 %s" % (datetime.datetime.now().astimezone().isoformat(timespec="seconds"), time.monotonic() - start, summary["status"]))
        print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
