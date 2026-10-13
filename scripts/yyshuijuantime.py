#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 阴阳师绘卷时间获取
# cron: 0 0 * * *
# new Env("阴阳师绘卷时间获取")
# 来源: CN-Grace/QinglongScripts / YysHuijuanTime.py
# 原作者: CN-Grace；上游许可及本维护版本许可: MIT
# 上游文件未包含其他版权或许可声明。
# MIT License
# Copyright (c) CN-Grace
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
"""每日读取官网公告。必须设置 YYS_HUIJUAN_OUTPUT 为明确授权写入的 JSON 路径。
兼容旧数据位置：将该变量设为原脚本目录/config/yys_huijuan_time.json。
YYS_HUIJUAN_DRY_RUN=1 使用内置公开公告样例，不联网、不读写数据、不投递通知。
仅用 Python 标准库；通知模块为可选青龙运行环境集成。
"""

import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

TZ = timezone(timedelta(hours=8))
LIST_URL = "https://yys.163.com/news/update/"
TITLE = "阴阳师绘卷时间获取"


def now():
    return datetime.now(TZ)


def log(message):
    print(f"[{now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    pass


def official_url(url):
    p = urlsplit(url)
    return (p.scheme == "https" and p.netloc == "yys.163.com"
            and p.path.startswith("/news/update/") and not p.query and not p.fragment)


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not official_url(newurl):
            raise TaskError("官网跳转地址不符合来源约束")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    if not official_url(url):
        raise TaskError("公告地址不符合来源约束")
    try:
        request = Request(url, headers={"User-Agent": "Qinglong-Huijuan/1.0"})
        with build_opener(SafeRedirect()).open(request, timeout=15) as response:
            if response.status != 200:
                raise TaskError("官网 HTTP 状态不是 200")
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise TaskError("公告响应超过大小限制")
            return raw.decode("utf-8")
    except TaskError:
        raise
    except Exception:
        raise TaskError("官网请求失败或响应编码异常") from None


class Announcements(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag != "a":
            return
        title = attrs.get("title", "").strip()
        url = urljoin(LIST_URL, attrs.get("href", ""))
        if ("维护更新公告" in title and official_url(url)
                and re.fullmatch(r"/news/update/\d+/\d+_\d+\.html", urlsplit(url).path)):
            item = {"title": title, "url": url}
            if item not in self.items:
                self.items.append(item)


class Body(HTMLParser):
    """跟踪嵌套 div，避免正文被内层 div 截断。"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts = []
        self.done = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self.depth and not self.done and tag == "div" and (
                attrs.get("id") == "NIE-art" or
                {"artText", "art-con"}.intersection(attrs.get("class", "").split())):
            self.depth = 1
        elif self.depth and tag == "div":
            self.depth += 1
        if self.depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.depth:
            self.parts.append("\n")
            if tag == "div":
                self.depth -= 1
                self.done = self.depth == 0

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def parse_activity(content, title):
    match = re.search(r"((?:SP|SSR|SR)?[一-龥]+追忆绘卷活动)", content)
    if not match:
        match = re.search(r"([\s\S]{0,50}追忆绘卷活动)", content)
    if not match:
        return None
    name = re.sub(r"[\n\r]+", "", match[1]).strip()[-30:]
    surrounding = content[max(0, match.start() - 100):match.end() + 300]
    dates = re.search(
        r"(\d{1,2})月(\d{1,2})日[^\d]*[-—~～至][^\d]*(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})",
        surrounding)
    if not dates:
        raise TaskError("发现绘卷活动，但时间格式无法核验")
    year_match = re.search(r"(\d{4})年", title)
    year = int(year_match[1]) if year_match else now().year
    sm, sd, em, ed = map(int, dates.groups()[:4])
    try:
        start = datetime(year, sm, sd, tzinfo=TZ)
        end_year = year + int(em < sm)
        end = datetime.strptime(f"{end_year}-{em:02d}-{ed:02d} {dates[5]}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        if end <= start:
            raise ValueError()
    except ValueError:
        raise TaskError("活动日期无效或结束时间早于开始时间") from None
    return {"name": name, "start_time": start.strftime("%Y-%m-%d"),
            "end_time": end.strftime("%Y-%m-%d %H:%M"),
            "start_note": "维护后", "end_note": dates[5]}


def save_activity(path, ann, activity):
    data = {"last_update": "", "latest_announcement": {}, "huijuan_activity": {}, "history": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("history"), list):
                raise ValueError()
            if any(not isinstance(h, dict) for h in data["history"]):
                raise ValueError()
        except Exception:
            raise TaskError("原 JSON 无法读取或结构无效；已保留原文件") from None
    today = now().strftime("%Y-%m-%d")
    data.update(last_update=today, latest_announcement={**ann, "date": today}, huijuan_activity=activity)
    if not any(h.get("name") == activity["name"] and h.get("start") == activity["start_time"] for h in data["history"]):
        data["history"].append({"date": today, "name": activity["name"],
                                "start": activity["start_time"], "end": activity["end_time"]})
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
            temporary = f.name
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    except Exception:
        raise TaskError("JSON 保存失败") from None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def notify(body, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in {"0", "false", "no", "off"}:
        return "已关闭"
    if dry:
        log("通知：断网预演，仅展示摘要，不调用通知模块")
        for line in body.splitlines():
            log(line)
        return "预演跳过投递"
    try:
        # 子进程限制通知耗时；阻止通知模块向日志写入敏感信息。
        import subprocess
        runner = '''import importlib.util, os
from pathlib import Path
try:
    from notify import send
except ImportError:
    paths = [Path(os.getenv("QINGLONG_NOTIFY_DIR", "/ql/data/scripts")) / "notify.py", Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
    path = next((p for p in paths if p.is_file()), None)
    if path is None:
        raise RuntimeError("通知模块不可用")
    spec = importlib.util.spec_from_file_location("ql_notify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    send = module.send
send(os.environ["_HUIJUAN_NOTICE_TITLE"], os.environ["_HUIJUAN_NOTICE_BODY"])
'''
        result = subprocess.run([sys.executable, "-c", runner],
                                env={**os.environ, "_HUIJUAN_NOTICE_TITLE": TITLE, "_HUIJUAN_NOTICE_BODY": body},
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return "已发送" if result.returncode == 0 else "不可用或发送失败"
    except Exception:
        return "不可用或发送失败"


def main():
    began = time.monotonic()
    dry = os.getenv("YYS_HUIJUAN_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}
    status, code, report = "failure", 1, ""
    successful, failed, skipped = 0, 0, 0
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry else '正式'}；账号总数：0（公开公告任务，无需账号）")
    try:
        stage = time.monotonic()
        log("阶段 1：核验参数")
        value = os.getenv("YYS_HUIJUAN_OUTPUT", "").strip()
        if not value or not Path(value).is_absolute() or Path(value).suffix.lower() != ".json":
            status = "configuration-error"
            raise TaskError("必须设置 YYS_HUIJUAN_OUTPUT 为绝对 JSON 文件路径")
        path = Path(value)
        log(f"✅ 参数有效；耗时 {time.monotonic() - stage:.2f} 秒")
        successful += 1
        stage = time.monotonic()
        log("阶段 2：读取最新五条维护公告并核验绘卷时间")
        if dry:
            html = '<a title="2026年12月30日维护更新公告" href="/news/update/20261230/12345_1234567.html">更新</a>'
        else:
            html = fetch(LIST_URL)
        parser = Announcements()
        parser.feed(html)
        if not parser.items:
            raise TaskError("官网列表未返回可核验的维护公告")
        log(f"列表核验成功；检查 {len(parser.items[:5])} 条公告")
        selected = None
        errors = 0
        for index, ann in enumerate(parser.items[:5], 1):
            log(f"阶段 2.{index}：检查维护公告")
            try:
                page = ('<div class="artText"><div>SSR测试式神追忆绘卷活动</div>'
                        '<p>12月30日维护后 - 1月6日23:59</p></div>') if dry else fetch(ann["url"])
                body = Body()
                body.feed(page)
                text = re.sub(r"\n+", "\n", "".join(body.parts)).strip()
                if not text:
                    raise TaskError("公告正文结构无法核验")
                activity = parse_activity(text, ann["title"])
                if activity:
                    # 不能用较旧公告掩盖较新公告的读取/解析失败。
                    if errors:
                        raise TaskError("较新公告核验失败，无法确认最新活动")
                    selected = (ann, activity)
                    break
                log("⏭️ 正文已核验；无绘卷活动")
            except TaskError as exc:
                errors += 1
                log(f"⚠️ {exc}")
        if selected is None:
            raise TaskError("未找到可核验的最新绘卷活动信息")
        ann, activity = selected
        log(f"✅ 活动：{activity['name']}；开始：{activity['start_time']}（维护后）；结束：{activity['end_time']}；耗时 {time.monotonic() - stage:.2f} 秒")
        log(f"最新公告：{ann['title']}")
        successful += 1
        stage = time.monotonic()
        log("阶段 3：保存活动及去重历史")
        if dry:
            skipped += 1
            log("⏭️ 断网预演：未读写 JSON")
        else:
            save_activity(path, ann, activity)
            successful += 1
            log("✅ JSON 原子保存成功")
        log(f"阶段 3 耗时 {time.monotonic() - stage:.2f} 秒")
        end = datetime.strptime(activity["end_time"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        report = (f"活动名称：{activity['name']}\n开始时间：{activity['start_time']}（维护后）\n结束时间：{activity['end_time']}"
                  if now() < end else "目前无活动")
        log("========== 查询完成 ==========")
        status, code = ("dry-run" if dry else "success"), 0
    except TaskError as exc:
        failed += 1
        report = str(exc)
        log(f"❌ {report}")
    except Exception:
        failed += 1
        report = "运行异常；未输出原始响应或文件内容"
        log(f"❌ {report}")
    summary = {"status": status, "mode": "dry-run" if dry else "live", "accounts": 0,
               "successAccounts": 0, "failedAccounts": 0, "totalTasks": successful + failed + skipped,
               "success": successful, "alreadyComplete": 0, "skipped": skipped, "failed": failed,
               "elapsedSeconds": round(time.monotonic() - began, 2), "exitCode": code}
    notice = f"状态：{status}；账号总数：0；成功账号：0；失败账号：0\n成功步骤：{successful}；失败步骤：{failed}\n{report}\n执行时间：{now():%Y-%m-%d %H:%M:%S}"
    log("阶段 4：发送脱敏任务摘要")
    stage = time.monotonic()
    summary["notification"] = notify(notice, dry)
    log(f"通知：{summary['notification']}；耗时 {time.monotonic() - stage:.2f} 秒")
    summary["elapsedSeconds"] = round(time.monotonic() - began, 2)
    log("----------------------------------------")
    log(f"任务统计：总步骤 {summary['totalTasks']}；成功 {successful}；已完成 0；跳过 {skipped}；失败 {failed}")
    log(f"完成时间：{now():%Y-%m-%d %H:%M:%S}；总耗时 {summary['elapsedSeconds']:.2f} 秒；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
