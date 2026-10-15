#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 明日方舟寻访公告
# cron: 29 1 * * *
# new Env("明日方舟寻访公告")
# 明日方舟限时寻访（卡池）公告监控
# 原始来源：CN-Grace/QinglongScripts / ArknightsBanner.py
# 原始提交：a40a2b080e0160bd8e0b0b807081115537b87153
# License: MIT（上游源码没有另附版权声明，保留其来源归属）
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
#
# 必填 ARKNIGHTS_STATE_FILE：独立可写 JSON 文件路径；兼容原 config/.arknights_banner_state.json。
# ARKNIGHTS_DRY_RUN=1：使用内置公告样例，不请求网络、不加载通知代码、不读写状态。
# QINGLONG_NOTIFY 默认 1：通过青龙 notify.py 发送公告文字与每次运行总结。
# 可选 ARKNIGHTS_TELEGRAM：每行一个“机器人 Token|聊天 ID”，仅在有封面时发图片。
# Token 由 Telegram BotFather 获取，聊天 ID 由自己机器人的 getUpdates 获取；不要公开。
# Telegram 是可选封面补充，文字仍走青龙通知，图片失败保留公告重试。
# 所有 HTTP 均由本文件的标准库 urllib 实现；不依赖另一个仓库或应用。
# 首次推送最新一期；以后扫描 LATEST 全部（上限 50 页）及 ACTIVITY 前 5 页。
# 公开资料任务无需游戏登录；不会签到、抽卡、发布评论或修改游戏账号。

import contextlib
import html as html_lib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlencode, urljoin, urlparse, quote
from urllib.request import Request, urlopen

BASE_URL = "https://ak.hypergryph.com"
LIST_API = BASE_URL + "/api/news"
DETAIL_URL = BASE_URL + "/news"
MAX_SCAN_PAGES = 50
ACTIVITY_FALLBACK_PAGES = 5
GACHA_CONFIRM_KW = ["出现率上升", "占6★出率", "占5★出率", "占4★出率", "6★出率", "5★出率", "4★出率", "概率提升"]
MAX_MESSAGE_LENGTH = 3900
REQUEST_TIMEOUT = 15
SLEEP_BETWEEN = 0.5
_TZ_BEIJING = timezone(timedelta(hours=8))
FALSE_VALUES = {"0", "false", "no", "off"}


def beijing_time_str():
    return datetime.now(_TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def log_info(message):
    print(f"[{beijing_time_str()[11:]}] {message}")


def enabled(name, default="0"):
    return os.environ.get(name, default).strip().lower() not in FALSE_VALUES | {""}


def request_bytes(url, data=None, limit=4 * 1024 * 1024):
    if enabled("ARKNIGHTS_DRY_RUN"):
        raise RuntimeError("断网预演禁止 HTTP")
    if urlparse(url).scheme != "https":
        raise RuntimeError("仅允许 HTTPS")
    headers = {"User-Agent": "ArknightsBannerMonitor/1.0", "Accept": "application/json,text/html"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urlencode(data).encode("utf-8")
    with urlopen(Request(url, data=data, headers=headers), timeout=REQUEST_TIMEOUT) as response:
        if response.status != 200 or urlparse(response.geturl()).scheme != "https":
            raise RuntimeError("HTTP 状态或重定向异常")
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise RuntimeError("响应超过大小限制")
    return raw


def fetch_news_list(category, page):
    result = json.loads(request_bytes(LIST_API + "?" + urlencode({"category": category, "page": page})))
    if not isinstance(result, dict) or type(result.get("code")) is not int or result["code"] != 0:
        raise RuntimeError("公告业务状态异常")
    data = result.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("list"), list) or not isinstance(data.get("end"), bool):
        raise RuntimeError("公告响应结构异常")
    for item in data["list"]:
        if not isinstance(item, dict) or not isinstance(item.get("cid"), (str, int)) or isinstance(item["cid"], bool) or not str(item["cid"]):
            raise RuntimeError("公告标识缺失")
        item["cid"] = str(item["cid"])
    if not data["list"] and not data["end"]:
        raise RuntimeError("空列表没有末页标志")
    return data


def fetch_new_news(known_cids):
    items, all_cids, seen = [], set(), set()
    for category, pages in [("LATEST", MAX_SCAN_PAGES), ("ACTIVITY", ACTIVITY_FALLBACK_PAGES)]:
        for page in range(1, pages + 1):
            began = time.monotonic()
            result = fetch_news_list(category, page)
            page_cids = []
            for item in result["list"]:
                cid = item["cid"]
                all_cids.add(cid)
                page_cids.append(cid)
                if cid not in known_cids and cid not in seen:
                    seen.add(cid)
                    items.append(item)
            log_info(f"阶段 2 扫描 {category} 第 {page} 页：{len(page_cids)} 条，耗时 {time.monotonic()-began:.2f} 秒")
            if result["end"] or (category == "ACTIVITY" and known_cids and page_cids and all(c in known_cids for c in page_cids)):
                break
            time.sleep(SLEEP_BETWEEN)
    # 两个来源都成功且至少取得一条公告才视为有效扫描。
    if not all_cids:
        raise RuntimeError("未取得任何公告，不能确认扫描成功")
    items.sort(key=lambda item: float(item.get("displayTime") or 0))
    return items, all_cids


def parse_detail_html(content, cid):
    no_script = re.sub(r"<script\b[\s\S]*?</script>", "", content, flags=re.I)
    date = re.search(r"\d{4}\s*//\s*\d{2}\s*/\s*\d{2}", no_script)
    seg = no_script[date.start():] if date else no_script
    health = seg.find("本网络游戏适合")
    if health >= 0:
        seg = seg[:health]
    paragraphs = []
    for match in re.finditer(r"<p\b[^>]*>([\s\S]*?)</p>", seg, flags=re.I):
        text = html_lib.unescape(re.sub(r"<[^>]+>", "", match.group(1)))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            paragraphs.append(text)
    if not paragraphs:
        raise RuntimeError("未识别正文段落，保留公告供重试")
    cover = None
    for tag in re.findall(r"<img\b[^>]*>", seg, flags=re.I):
        attrs = dict((k.lower(), html_lib.unescape(v)) for k, _, v in re.findall(r"([\w-]+)\s*=\s*([\"'])(.*?)\2", tag))
        if attrs.get("data-width") == "1560" and attrs.get("src"):
            image_url = urljoin(BASE_URL, attrs["src"])
            if urlparse(image_url).scheme == "https":
                cover = image_url
                break
    return {"cid": cid, "cover": cover, "paragraphs": paragraphs, "url": DETAIL_URL + "/" + quote(str(cid), safe="")}


def fetch_banner_detail(cid):
    url = DETAIL_URL + "/" + quote(str(cid), safe="")
    return parse_detail_html(request_bytes(url).decode("utf-8"), cid)


def confirm_gacha_by_detail(paragraphs: List[str]) -> bool:
    """根据正文内容判断是否为卡池公告（不依赖标题/摘要，直接看详情数据）"""
    text = " ".join(paragraphs)
    return any(k in text for k in GACHA_CONFIRM_KW)


def _ts_to_beijing(ts: int) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts, _TZ_BEIJING).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def parse_banner(item: Dict, detail: Dict) -> Dict:
    """从公告标题与正文段落解析卡池结构化数据

    适配两种格式：
      - 独立寻访公告：★★★★★★：麒麟R夜刀（占6★出率的50%）
      - 活动附带寻访：★★★★★★（6★出率：2%）：琴柳 / 号角 / 白铁
    """
    title = item.get("title", "")
    paragraphs = detail.get("paragraphs", [])

    # 寻访名称：优先从"活动说明：活动期间【xxx】...寻访开启"提取，回退到标题
    banner_name = ""
    for p in paragraphs:
        m = re.search(r"活动期间【([^】]+)】.*?寻访开启", p)
        if m:
            banner_name = m.group(1).strip()
            break
    if not banner_name:
        m = re.match(r"\[([^\]]+)\]\s*【([^】]+)】", title)
        if m:
            banner_name = m.group(2).strip()

    # 寻访类型：优先从"◆...寻访为【xxx】"提取，回退到标题前缀
    banner_type = ""
    for p in paragraphs:
        m = re.search(r"寻访为【([^】]+)】", p)
        if m:
            banner_type = m.group(1).strip()
            break
    if not banner_type:
        m = re.match(r"\[([^\]]+)\]", title)
        if m:
            banner_type = m.group(1).strip()

    # 活动时间：定位寻访说明段（含"出现率上升/以下干员/活动期间...寻访"），取其前面最近的"活动时间："
    activity_time = ""
    xf_idx = None
    for i, p in enumerate(paragraphs):
        if "出现率上升" in p or "以下干员" in p or ("活动期间" in p and "寻访" in p):
            xf_idx = i
            break
    if xf_idx is not None:
        for j in range(xf_idx, -1, -1):
            if paragraphs[j].startswith("活动时间："):
                activity_time = paragraphs[j][len("活动时间："):].strip()
                break
    if not activity_time:
        for p in paragraphs:
            if p.startswith("活动时间："):
                activity_time = p[len("活动时间："):].strip()
                break

    # 6★/5★ UP：★5-6 开头，排除兑换所行与纯干员列表（UP 段必含"出率"）
    star = [p for p in paragraphs
            if re.match(r"^★{5,6}", p) and "寻访数据契约" not in p and "出率" in p]
    six_star = [p for p in star if p.startswith("★★★★★★")]
    five_star = [p for p in star if not p.startswith("★★★★★★")]

    # 寻访数据契约兑换所
    exchange = [p for p in paragraphs
                if "寻访数据契约" in p and ("交换所" in p or re.match(r"^★{5,6}（", p) or "可兑换干员" in p)]

    # 保底与规则：只保留卡池相关 ◆ 段落（过滤时装/活动/信赖等无关内容）
    RULES_KEEP = ["寻访", "出率", "保底", "必定", "累计", "六星", "五星", "获得干员", "寻访数据契约"]
    RULES_SKIP = ["时装", "回顾展", "信赖获取", "合成玉", "入场券", "故事集收录", "关卡开放", "凭证过期"]
    rules: List[str] = []
    for p in paragraphs:
        keep = False
        if p.startswith("◆"):
            if any(k in p for k in RULES_KEEP) and not any(k in p for k in RULES_SKIP):
                keep = True
        elif "累计寻访" in p and ("必定" in p or "额外" in p):
            keep = True
        elif re.match(r"^【.+?】说明$", p):
            keep = True
        if keep:
            rules.append(p)
    seen_r = set()
    rules = [x for x in rules if not (x in seen_r or seen_r.add(x))]

    return {
        "cid": item.get("cid"),
        "title": title,
        "banner_type": banner_type,
        "banner_name": banner_name,
        "activity_time": activity_time,
        "cover": detail.get("cover"),
        "six_star": six_star,
        "five_star": five_star,
        "exchange": exchange,
        "rules": rules,
        "announce_time": item.get("displayTime", 0),
        "brief": item.get("brief", ""),
        "url": detail.get("url", f"{DETAIL_URL}/{item.get('cid')}"),
    }


# ==================== 报告格式化 ====================
def format_banner_report(b: Dict, index: int = 0, total: int = 0) -> str:
    lines = []
    head = "🎰 明日方舟 新卡池公告"
    if total > 1:
        head += f"（{index}/{total}）"
    lines.append(head)
    lines.append("")
    if b["banner_type"]:
        lines.append(f"🏷️ 寻访类型: {b['banner_type']}")
    if b["banner_name"]:
        lines.append(f"📛 寻访名称: {b['banner_name']}")
    if b["activity_time"]:
        lines.append(f"📅 活动时间: {b['activity_time']}")
    if b["announce_time"]:
        lines.append(f"📰 发布时间: {_ts_to_beijing(b['announce_time'])}")
    if b.get("cover"):
        lines.append("🖼️ 卡池封面: 见推送图片")
    lines.append("")

    if b["six_star"]:
        lines.append("⭐ 6★ UP干员（出现率上升）")
        for p in b["six_star"]:
            lines.append(f"  {p}")
        lines.append("")
    if b["five_star"]:
        lines.append("⭐ 5★ UP干员（出现率上升）")
        for p in b["five_star"]:
            lines.append(f"  {p}")
        lines.append("")
    if b["rules"]:
        lines.append("📋 保底与规则")
        for p in b["rules"]:
            lines.append(f"  {p}")
        lines.append("")
    if b["exchange"]:
        lines.append("🔄 寻访数据契约兑换所")
        for p in b["exchange"]:
            lines.append(f"  {p}")
        lines.append("")

    lines.append(f"🔗 公告链接: {b['url']}")
    lines.append("─" * 18)
    lines.append(f"🕒 推送时间: {beijing_time_str()}")
    return "\n".join(lines)


def split_message(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """按行分段；单行超长也分割，保证通知渠道长度上限。"""
    if max_len < 1:
        raise ValueError("分段上限必须大于零")
    parts, current = [], ""
    for line in text.split("\n"):
        while len(line) > max_len:
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:max_len])
            line = line[max_len:]
        if len(current) + len(line) + bool(current) > max_len:
            parts.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        parts.append(current)
    return parts or [""]


def load_state(path):
    if not path.exists():
        return {"known_cids": [], "notified_cids": [], "last_run": ""}
    with path.open(encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict):
        raise ValueError("状态文件格式异常")
    for key in ("known_cids", "notified_cids"):
        values = state.setdefault(key, [])
        if not isinstance(values, list) or any(not isinstance(x, (str, int)) or isinstance(x, bool) for x in values):
            raise ValueError("状态公告标识格式异常")
        state[key] = list(dict.fromkeys(str(x) for x in values))
    return state


def save_state(path, state):
    state["last_run"] = beijing_time_str()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".arknights-", delete=False) as handle:
            temporary = handle.name
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)


def find_notifier():
    # 青龙通知为可选运行时集成，不是业务 HTTP 的实现或仓库依赖。
    # 不打印外部通知模块导入时的配置或错误内容。
    candidates = []
    try:
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin:
            candidates.append(Path(spec.origin))
    except Exception:
        pass
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        candidates.append(Path(directory) / "notify.py")
    candidates += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                spec = importlib.util.spec_from_file_location("_arknights_ql_notify", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            if callable(getattr(module, "send", None)):
                return module.send
        except Exception:
            continue
    return None


def send_text(sender, title, body):
    if sender is None:
        raise RuntimeError("青龙通知模块不可用")
    # 通知模块可能输出 Token，所有输出都隔离；无返回值表示其 API 调用完成。
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        result = sender(title, body)
    if result is False:
        raise RuntimeError("青龙通知报告失败")


def telegram_destinations():
    result = []
    for line in os.environ.get("ARKNIGHTS_TELEGRAM", "").splitlines():
        if not line.strip():
            continue
        token, separator, chat = line.strip().partition("|")
        # 只拆第一个字段分隔符，绝不将符号用于分隔接收目标。
        if not separator or not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token) or not re.fullmatch(r"-?\d+", chat):
            raise ValueError("ARKNIGHTS_TELEGRAM 格式错误")
        result.append((token, chat))
    return result


def send_photo(destinations, cover, caption):
    failures = 0
    for number, (token, chat) in enumerate(destinations, 1):
        began = time.monotonic()
        try:
            reply = json.loads(request_bytes("https://api.telegram.org/bot" + token + "/sendPhoto", {
                "chat_id": chat, "photo": cover, "caption": caption[:1024]
            }, limit=256 * 1024))
            if not isinstance(reply, dict) or reply.get("ok") is not True or not isinstance(reply.get("result"), dict) or not reply["result"].get("message_id"):
                raise RuntimeError("图片业务响应异常")
            log_info(f"阶段 4 图片接收目标 {number}：✅ 成功，耗时 {time.monotonic()-began:.2f} 秒")
        except Exception:
            failures += 1
            log_info(f"阶段 4 图片接收目标 {number}：❌ 失败，耗时 {time.monotonic()-began:.2f} 秒；不输出凭据和响应")
    if failures:
        raise RuntimeError("部分图片接收目标失败")


def push_banner(item, detail, sender, destinations, idx=0, total=0, first_run=False):
    parsed = parse_banner(item, detail)
    report = format_banner_report(parsed, idx, total)
    if parsed.get("cover"):
        # 保留图片推送能力，并让未配置 Telegram 的用户仍可打开封面。
        report += "\n🖼️ 封面链接: " + parsed["cover"]
    print("\n" + report + "\n")
    title = "明日方舟 寻访公告（首次初始化）" if first_run else "明日方舟 新卡池公告"
    if total > 1:
        title += f"（{idx}/{total}）"
    for number, part in enumerate(split_message(report), 1):
        send_text(sender, title + (f"（{number}）" if len(report) > MAX_MESSAGE_LENGTH else ""), part)
    if parsed.get("cover") and destinations:
        send_photo(destinations, parsed["cover"], "【" + (parsed.get("banner_name") or parsed.get("banner_type") or "卡池") + "】")


def dry_run_fixture():
    item = {"cid": "dry-run", "title": "[标准寻访]【断网预演卡池】", "displayTime": 1}
    detail = parse_detail_html('''<script><p>不应作为正文</p></script>
        2026 // 10 / 13
        <p>活动时间：10月13日 10:00 - 10月27日 03:59</p>
        <p>活动期间【断网预演卡池】寻访开启，以下干员出现率上升</p>
        <p>★★★★★★：预演六星（占6★出率的50%）</p>
        <p>★★★★★：预演五星（占5★出率的50%）</p>
        <p>◆本次寻访为【标准寻访】</p>
        <p>累计寻访100次必定获得六星干员</p>
        <p>寻访数据契约交换所可兑换干员</p>
        <img data-width="1560" src="https://ak.hypergryph.com/example-banner.png">
        本网络游戏适合<p>忽略页脚</p>''', item["cid"])
    parsed = parse_banner(item, detail)
    assert confirm_gacha_by_detail(detail["paragraphs"])
    assert parsed["banner_name"] == "断网预演卡池" and parsed["banner_type"] == "标准寻访"
    assert parsed["activity_time"] and parsed["six_star"] and parsed["five_star"]
    assert parsed["rules"] and parsed["exchange"] and parsed["cover"]
    assert "不应作为正文" not in detail["paragraphs"] and "忽略页脚" not in detail["paragraphs"]
    report = format_banner_report(parsed)
    assert "预演六星" in report and split_message(report, 120)
    print(report)
    log_info("阶段 3 ✅ 正文识别、卡池字段、封面、报告分段及页脚过滤预演通过")


def main():
    began = time.monotonic()
    dry = enabled("ARKNIGHTS_DRY_RUN")
    notifications = enabled("QINGLONG_NOTIFY", "1")
    stats = {"scanned": 0, "tasks": 0, "success": 0, "already_complete": 0, "skipped": 0, "failed": 0, "published": 0}
    status, code, sender = "success", 0, None
    log_info("===== 明日方舟寻访公告监控 =====")
    log_info(f"开始时间：{beijing_time_str()}；模式：{'断网预演' if dry else '正式运行'}；账号数：0（公开公告，无需登录）；监控源：1")
    try:
        stage = time.monotonic()
        log_info("阶段 1 配置检查与状态读取")
        state_text = os.environ.get("ARKNIGHTS_STATE_FILE", "").strip()
        if not state_text:
            raise ValueError("必须配置 ARKNIGHTS_STATE_FILE")
        path = Path(state_text).expanduser()
        if path.name in {"", ".", ".."} or (path.exists() and not path.is_file()):
            raise ValueError("ARKNIGHTS_STATE_FILE 必须是独立 JSON 文件路径")
        destinations = telegram_destinations()
        log_info(f"阶段 1 ✅ 配置通过，图片接收目标 {len(destinations)} 个，耗时 {time.monotonic()-stage:.2f} 秒")
        if dry:
            log_info("阶段 2 使用内置公告样例；不联网、不加载通知模块、不读写状态")
            stage = time.monotonic()
            dry_run_fixture()
            stats.update(scanned=1, tasks=1, success=1)
            log_info(f"阶段 3 耗时 {time.monotonic()-stage:.2f} 秒")
            log_info("阶段 4 通知与图片发送已模拟；阶段 5 状态更新已模拟")
            status = "dry-run"
        else:
            if notifications:
                sender = find_notifier()
            state = load_state(path)
            known = set(state["known_cids"])
            notified = set(state["notified_cids"])
            first = not known
            log_info("阶段 2 公告列表扫描与业务状态核验")
            items, scanned = fetch_new_news(known)
            stats["scanned"] = len(scanned)
            stats["already_complete"] = len(scanned & known)
            completed = set()
            confirmed = []
            log_info("阶段 3 抓取正文，按卡池内容识别（不使用标题预筛）")
            for number, item in enumerate(reversed(items) if first else items, 1):
                step = time.monotonic()
                stats["tasks"] += 1
                try:
                    detail = fetch_banner_detail(item["cid"])
                    if confirm_gacha_by_detail(detail["paragraphs"]):
                        confirmed.append((item, detail))
                        log_info(f"阶段 3 公告 {number}：✅ 确认为卡池，耗时 {time.monotonic()-step:.2f} 秒")
                        if first:
                            break
                    else:
                        completed.add(item["cid"])
                        stats["skipped"] += 1
                        log_info(f"阶段 3 公告 {number}：⏭️ 正文非卡池，耗时 {time.monotonic()-step:.2f} 秒")
                except Exception:
                    stats["failed"] += 1
                    log_info(f"阶段 3 公告 {number}：❌ 详情失败，保留重试，耗时 {time.monotonic()-step:.2f} 秒")
                    # 首次定位不能越过失败详情选择更旧卡池并吞掉较新公告。
                    if first:
                        break
                time.sleep(SLEEP_BETWEEN)
            log_info(f"阶段 4 推送卡池公告，共 {len(confirmed)} 条")
            for number, (item, detail) in enumerate(confirmed, 1):
                step = time.monotonic()
                if item["cid"] in notified:
                    completed.add(item["cid"])
                    stats["already_complete"] += 1
                    continue
                if not notifications:
                    stats["skipped"] += 1
                    log_info("阶段 4 ⏭️ 全局通知已关闭，保留卡池等待重新开启通知")
                    continue
                try:
                    push_banner(item, detail, sender, destinations, number, len(confirmed), first)
                    completed.add(item["cid"])
                    notified.add(item["cid"])
                    stats["success"] += 1
                    stats["published"] += 1
                    log_info(f"阶段 4 卡池 {number}：✅ 通知调用完成，耗时 {time.monotonic()-step:.2f} 秒")
                except Exception:
                    stats["failed"] += 1
                    log_info(f"阶段 4 卡池 {number}：❌ 推送失败，保留重试，耗时 {time.monotonic()-step:.2f} 秒")
            stage = time.monotonic()
            log_info("阶段 5 原子更新状态（失败公告不标为已处理）")
            if first:
                # 首次保持原来的只推送最新卡池语义；失败或通知关闭时不建立基线。
                if not stats["failed"] and (not confirmed or all(item["cid"] in completed for item, _ in confirmed)):
                    known |= scanned
                else:
                    completed.clear()
            else:
                known |= completed
            state.update(known_cids=sorted(known), notified_cids=sorted(notified))
            save_state(path, state)
            log_info(f"阶段 5 ✅ 状态写入完成，耗时 {time.monotonic()-stage:.2f} 秒")
            if stats["failed"]:
                code = 1
                status = "partial-failure" if stats["success"] or stats["skipped"] else "failure"
    except ValueError:
        status, code = "configuration-error", 1
        stats["failed"] += 1
        log_info("❌ 配置或状态格式错误；请核对状态文件、图片接收配置；不输出参数值")
    except Exception:
        status, code = "failure", 1
        stats["failed"] += 1
        log_info("❌ 执行失败；请检查网络、接口结构、状态文件权限和青龙通知；不输出原始异常")
    business_code = code
    body = (f"状态：{status}；账号总数：0，成功账号：0，失败账号：0（公开公告监控）\n"
            f"公告扫描：{stats['scanned']}；子任务：{stats['tasks']}；成功：{stats['success']}；"
            f"已完成：{stats['already_complete']}；跳过：{stats['skipped']}；失败：{stats['failed']}；"
            f"新推送：{stats['published']}；耗时：{time.monotonic()-began:.2f} 秒")
    if dry:
        notice = "断网预演模拟" if notifications else "全局关闭"
    elif not notifications:
        notice = "全局关闭"
    else:
        try:
            if sender is None:
                sender = find_notifier()
            send_text(sender, "明日方舟寻访公告", body)
            notice = "通知调用完成"
        except Exception:
            notice = "通知不可用或失败，保留业务退出码"
    print("-" * 48)
    log_info("监控源 1 统计：" + body)
    log_info(f"通知状态：{notice}；完成时间：{beijing_time_str()}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({
        "task": "明日方舟寻访公告", "mode": "dry-run" if dry else "live", "status": status,
        "accounts": 0, "successful_accounts": 0, "failed_accounts": 0, **stats,
        "notification": notice, "elapsed_seconds": round(time.monotonic()-began, 3), "exit_code": business_code
    }, ensure_ascii=False, separators=(",", ":")))
    return business_code


if __name__ == "__main__":
    sys.exit(main())
