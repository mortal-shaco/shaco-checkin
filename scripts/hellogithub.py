#!/usr/bin/env python3
# name: HelloGitHub月刊提醒
# cron: 31 8 1 * *
# new Env("HelloGitHub月刊提醒")
# HelloGitHub 月刊更新提醒
# 每月运行一次，检查并发送最新月刊内容。
# 支持分多条消息发送完整内容，基于字符长度分段。
# 来源：CN-Grace/QinglongScripts / HelloGithub.py
# 上游提交：a40a2b080e0160bd8e0b0b807081115537b87153
# 许可：MIT。保留上游署名；上游文件未包含独立版权声明。
# MIT License
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
"""公开月刊提醒，无需 HelloGitHub 账号或凭据。
必填 HELLOGITHUB_STATE_FILE：持久化 JSON 文件的绝对路径，可沿用旧版
脚本目录/config/.hellogithub_bot_state.json（保留 last_sent_volume）。
青龙通知渠道在 notify.py 中配置；QINGLONG_NOTIFY_DIR 可指定其所在目录。
HELLOGITHUB_DRY_RUN=1：仅使用内置公开模拟数据，不联网、不发通知、不写状态。
QINGLONG_NOTIFY=0：禁用通知；有新刊时无法完成提醒，退出非零且不写状态。
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
        _ql_notify_identities = ('e249d85fcb6de594', 'scripts/hellogithub.py', 'hellogithub.py', 'hellogithub')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List
from urllib.request import Request, urlopen

PERIODICAL_API = "https://abroad.hellogithub.com/v1/periodical/"
PERIODICAL_PAGE_URL = "https://hellogithub.com/periodical"
MAX_MESSAGE_LENGTH = 3900
DRY = os.environ.get("HELLOGITHUB_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}

def now():
    return datetime.now(timezone(timedelta(hours=8)))

def log(message):
    print(f"[{now():%H:%M:%S}] {message}", flush=True)

def log_info(message):
    log(message)

class TaskError(Exception):
    pass

def fetch(url, as_json=True):
    if DRY:
        raise TaskError("预演禁止 HTTP 请求")
    try:
        req = Request(url, headers={"User-Agent": "HelloGitHub-Qinglong/1.0", "Accept": "application/json" if as_json else "text/html"})
        with urlopen(req, timeout=10) as resp:
            if resp.status != 200 or not resp.geturl().startswith("https://"):
                raise TaskError("HTTP 状态或重定向不符合要求")
            body = resp.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024:
            raise TaskError("响应超过大小限制")
        text = body.decode("utf-8")
        return json.loads(text) if as_json else text
    except TaskError:
        raise
    except Exception:
        raise TaskError("HTTP 请求失败或响应格式无效") from None

def latest_info():
    data = fetch(PERIODICAL_API)
    try:
        if data.get("success") is not True:
            raise ValueError()
        latest = data["volumes"][0]
        num = latest["num"]
        lastmod = latest["lastmod"]
        if type(num) is not int or num <= 0 or not isinstance(lastmod, str) or not lastmod:
            raise ValueError()
        return num, lastmod
    except Exception:
        raise TaskError("月刊接口未明确成功或期号字段无效") from None

def get_content(num):
    html = fetch(PERIODICAL_PAGE_URL, False)
    match = re.search(r'<script\b(?=[^>]*\bid=[\'"]__NEXT_DATA__[\'"])[^>]*>(.*?)</script>', html, re.S)
    try:
        build_id = json.loads(match.group(1))["buildId"] if match else None
        if not isinstance(build_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", build_id):
            raise ValueError()
        data = fetch(f"https://hellogithub.com/_next/data/{build_id}/zh/periodical/volume/{num}.json")
        props = data["pageProps"]
        volume = props.get("volumeData") or props.get("volume")
        categories = []
        for cat in volume["data"]:
            items = []
            for item in cat["items"]:
                project = {"full_name": item.get("full_name", "未知项目"), "description": item.get("description", "暂无描述"),
                           "github_url": item.get("github_url", ""), "language": item.get("lang", ""), "homepage": item.get("homepage", "")}
                for key in ("stars", "forks", "watch"):
                    project[key] = int(item.get(key, 0) or 0)
                if any(not isinstance(value, str) for key, value in project.items() if key not in {"stars", "forks", "watch"}):
                    raise ValueError()
                items.append(project)
            if items:
                categories.append({"category_name": cat.get("category_name", "未分类"), "items": items})
        if not categories:
            raise ValueError()
        return {"title": volume.get("title", f"HelloGitHub 第 {num} 期"), "description": volume.get("desc", ""),
                "categories": categories, "total_items": sum(len(cat["items"]) for cat in categories), "volume_num": num}
    except TaskError:
        raise
    except Exception:
        raise TaskError("月刊页面或项目内容字段无效，未更新状态") from None

def format_project_info(project: Dict, project_num: int, total_projects: int) -> str:
    name = project["full_name"]
    desc = project["description"]
    stars, forks, watch = project["stars"], project["forks"], project["watch"]
    lang = project["language"]
    github_url = project["github_url"]
    lines = [f"  {project_num}/{total_projects}. 【{name}】"]
    if lang:
        lines.append(f"     语言: {lang}")
    lines.append(f"     描述: {desc}")
    stats = []
    if stars > 0: stats.append(f"⭐ {stars}")
    if forks > 0: stats.append(f"🔀 {forks}")
    if watch > 0: stats.append(f"👀 {watch}")
    if stats:
        lines.append(f"     数据: {' | '.join(stats)}")
    if github_url:
        lines.append(f"     链接: {github_url}")
    lines.append("")
    return "\n".join(lines)


def format_category_header(category: Dict, category_num: int, total_categories: int) -> str:
    category_name = category["category_name"]
    items = category["items"]
    return f"\n🎯 {category_num}/{total_categories}. {category_name} ({len(items)} 个项目)\n"


def calculate_message_count(total_chars: int, max_length: int = MAX_MESSAGE_LENGTH) -> int:
    """计算消息条数：向上取整，小数位>0.7则+1"""
    ratio = total_chars / max_length
    integer_part = int(ratio)
    decimal_part = ratio - integer_part

    if decimal_part == 0:
        return integer_part
    elif decimal_part > 0.7:
        return integer_part + 2  # 向上取整 + 1
    else:
        return integer_part + 1  # 向上取整


def build_header(title: str, desc: str, volume_num: int, total_items: int, total_categories: int, pub_date: str) -> str:
    """构建月刊信息"""
    header = f"🚀 {title}\n"
    if desc:
        header += f"📝 {desc}\n"
    header += f"📅 发布时间: {pub_date}\n🔢 期号: 第 {volume_num} 期\n📚 项目总数: {total_items} 个\n🏷️ 分类数量: {total_categories} 个\n{'─' * 40}"
    return header


def build_project_parts(categories: List[Dict], total_items: int, total_categories: int) -> List[str]:
    """构建项目详情列表"""
    parts = []
    cat_num = 1
    for cat in categories:
        parts.append(format_category_header(cat, cat_num, total_categories))
        items = cat["items"]
        for i, item in enumerate(items):
            proj_num = sum(len(c["items"]) for c in categories[:cat_num - 1]) + i + 1
            text = format_project_info(item, proj_num, total_items)
            # 如果是分类最后一个项目，添加分割线
            if i == len(items) - 1:
                text += f"{'─' * 40}"
            parts.append(text)
        cat_num += 1
    return parts


def build_footer(volume_num: int) -> str:
    """构建月刊总结"""
    read_more = f"https://hellogithub.com/zh/periodical/volume/{volume_num}/"
    return f"\n🔗 在线阅读: {read_more}\n🌟 GitHub: https://github.com/521xueweihan/HelloGitHub"


def create_report_pages(content, lastmod):
    categories = content["categories"]
    text = build_header(content["title"], content["description"], content["volume_num"], content["total_items"], len(categories), lastmod[:10])
    text += "".join(build_project_parts(categories, content["total_items"], len(categories)))
    text += build_footer(content["volume_num"])
    # 保留全部正文；超长单项目也按字符硬分段，保证每条消息有界。
    return [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]

def state_path():
    value = os.environ.get("HELLOGITHUB_STATE_FILE", "").strip()
    if not value or not Path(value).is_absolute():
        raise TaskError("配置错误：HELLOGITHUB_STATE_FILE 必须是持久化 JSON 文件的绝对路径")
    return Path(value)

def load_state(path):
    if not path.exists():
        return 0
    try:
        volume = json.loads(path.read_text(encoding="utf-8"))["last_sent_volume"]
        if type(volume) is not int or volume < 0:
            raise ValueError()
        return volume
    except Exception:
        raise TaskError("历史状态损坏或无法读取，停止以避免重复通知") from None

def save_state(path, num):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            name = stream.name
            json.dump({"last_sent_volume": num, "updated_at": now().isoformat(), "last_run": now().strftime("%Y-%m-%d %H:%M:%S")}, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except Exception:
        raise TaskError("状态保存失败，下次可能重复提醒") from None
    finally:
        if name and Path(name).exists():
            Path(name).unlink()

def notify(title, body):
    if DRY:
        return "预演跳过（不联网）"
    if os.environ.get("QINGLONG_NOTIFY", "1").lower() in {"0", "false", "no", "off"}:
        return "已禁用"
    paths = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory) / "notify.py")
    paths.extend([Path(__file__).parent / "notify.py", Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    try:
        # 助手导入和发送阶段的输出均可能包含渠道配置，禁止透传。
        import contextlib
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
            if module is None:
                import notify as module
            result = module.send(title, body)
        if result is False:
            return "失败"
        return "已提交通知助手"
    except Exception:
        return "不可用或失败"

def main():
    started = time.monotonic()
    log("===== HelloGitHub 月刊提醒 =====")
    log(f"开始时间：{now():%Y-%m-%d %H:%M:%S %z}；模式：{'断网预演' if DRY else '正式'}；账号数：0（公开月刊任务）")
    count = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    status, code, volume, pages_count = "success", 0, None, 0
    stage = 0
    def run(label, action):
        nonlocal stage
        stage += 1
        count["total"] += 1
        begin = time.monotonic()
        log(f"阶段 {stage}：{label}")
        try:
            value = action()
            count["success"] += 1
            log(f"✅ 阶段 {stage} 成功，耗时 {time.monotonic() - begin:.2f} 秒")
            return value
        except Exception:
            count["failed"] += 1
            log(f"❌ 阶段 {stage} 失败，耗时 {time.monotonic() - begin:.2f} 秒")
            raise
    try:
        path = run("检查配置", state_path)
        if DRY:
            sample = {"title": "HelloGitHub 预演月刊", "description": "公开模拟内容", "volume_num": 1, "total_items": 1,
                      "categories": [{"category_name": "示例分类", "items": [{"full_name": "HelloGitHub", "description": "开源项目介绍", "language": "Python", "stars": 1, "forks": 1, "watch": 1, "github_url": "https://github.com/521xueweihan/HelloGitHub"}]}]}
            pages = run("模拟内容格式与分段", lambda: create_report_pages(sample, "2026-01-01"))
            if not pages or any(len(page) > MAX_MESSAGE_LENGTH for page in pages):
                raise TaskError("预演分段验证失败")
            pages_count = len(pages)
            volume = 1
            log(f"DRY_RUN_OK：模拟生成 {pages_count} 条月刊消息；HTTP、通知、状态写入均未执行")
            status = "dry-run"
        else:
            last = run("读取历史状态", lambda: load_state(path))
            volume, lastmod = run("查询最新期号", latest_info)
            log(f"最新期号：{volume}；已提醒期号：{last}")
            if volume <= last:
                count["alreadyComplete"] += 1
                log("☑️ 没有新刊发布")
            else:
                content = run("获取完整月刊", lambda: get_content(volume))
                pages = run("生成全部项目分段报告", lambda: create_report_pages(content, lastmod))
                pages_count = len(pages)
                for index, page in enumerate(pages, 1):
                    def send_page():
                        result = notify(f"HelloGitHub 第 {volume} 期 ({index}/{len(pages)})", page)
                        if result != "已提交通知助手":
                            raise TaskError("月刊通知未提交，保留原有期号")
                        log(f"第 {index}/{len(pages)} 条：{len(page)} 字符，已提交通知助手（不代表渠道已送达）")
                    run(f"发送月刊 {index}/{len(pages)}", send_page)
                    if index < len(pages):
                        time.sleep(2)
                run("保存已发送期号", lambda: save_state(path, volume))
            log("HELLOGITHUB_SUCCESS：公开月刊检查完成")
    except TaskError as error:
        log(f"❌ {error}")
        status = "configuration-error" if stage == 1 else "failure"
        code = 1
    except Exception:
        log("❌ 处理失败，错误详情已隐藏")
        status, code = "failure", 1
    summary_body = f"状态：{status}；账号总数：0；成功账号：0；失败账号：0；成功步骤：{count['success']}；失败步骤：{count['failed']}；消息数：{pages_count}"
    notification = notify("HelloGitHub月刊任务总结", summary_body)
    log("----------------------------------------")
    log(summary_body)
    log(f"子任务统计：{json.dumps(count, ensure_ascii=False)}；总耗时：{time.monotonic() - started:.2f} 秒")
    log(f"完成时间：{now():%Y-%m-%d %H:%M:%S %z}；通知状态：{notification}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"task": "HelloGitHub月刊", "status": status, "accounts": 0, "successAccounts": 0, "failedAccounts": 0, "steps": count, "volume": volume, "pages": pages_count, "notification": notification, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code

if __name__ == "__main__":
    sys.exit(main())
