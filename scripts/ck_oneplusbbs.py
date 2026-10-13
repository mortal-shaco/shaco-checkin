# -*- coding: utf-8 -*-
# name: 一加手机社区官方论坛
# cron: 0 8 * * *
# Source: yuxian158/check dailycheckin_scripts/ck_oneplusBBS.py
# Upstream commit: 723c834f121ff4eef2dec7afe521071a7efff1a9
# License: MIT
# MIT License
# Original attribution: yuxian158/check contributors (upstream has no copyright notice).
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
"""独立签到；ONEPLUSBBS 每行一个完整 Cookie（兼容 ONEPLUSBBS_COOKIE）。
浏览器登录 https://www.oneplusbbs.com 后从开发者工具网络请求获取 Cookie，
必须含 bbs_formhash；不从 Cookie 提取并展示身份。默认不消费加油；
ONEPLUSBBS_DRAW=1 显式授权最多十次抽奖，每次消耗十加油。
ONEPLUSBBS_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
"""
import html
import importlib.util
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib import parse, request

TITLE = "一加手机社区官方论坛"
BASE = "https://www.oneplusbbs.com"
FALSE = {"0", "false", "no", "off"}


def enabled(name, default="0"):
    value = os.environ.get(name, default).strip().lower()
    if value in FALSE:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    raise ValueError("开关配置必须为 1/0、true/false、yes/no 或 on/off")


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 不向跳转目标泄漏 Cookie，也不重复提交副作用请求。


def http(url, *, cookie=None, data=None, limit=262144, timeout=15):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    if cookie:
        headers.update({"Cookie": cookie, "Origin": BASE,
                        "Referer": BASE + ("/plugin-choujiang.html" if "choujiang" in url else "/plugin-dsu_paulsign:sign.html"),
                        "X-Requested-With": "XMLHttpRequest"})
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = request.Request(url, data=data, headers=headers)
    with request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("响应超出限制")
        return raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def normalize(value):
    return " ".join(value.split()) if isinstance(value, str) else ""


def public_text():
    fallback = normalize(os.environ.get("ONEPLUSBBS_LOCAL_TEXT", "努力奋斗"))
    if not fallback or len(fallback) > 280:
        fallback = "努力奋斗"
    try:
        obj = json.loads(http("https://v1.hitokoto.cn/?encode=json", limit=16384, timeout=8))
        text = normalize(obj.get("hitokoto"))
        author, source = normalize(obj.get("from_who")), normalize(obj.get("from"))
        if not text:
            raise ValueError()
        if author and source:
            text += f" —— {author}《{source}》"
        elif source:
            text += f" ——《{source}》"
        elif author:
            text += f" —— {author}"
        if len(text) > 280:
            raise ValueError()
        log("签到文字：一言内容获取成功（含来源署名，不展示正文）")
        return text
    except Exception:
        log("签到文字：一言不可用，使用本地文字")
        return fallback


def formhash(cookie):
    if not cookie or any(ord(c) < 32 or ord(c) == 127 for c in cookie):
        raise ValueError("Cookie 为空或包含控制字符")
    # 只分割 Cookie 字段，不把 &、@ 当账号分隔符。
    matches = re.findall(r"(?:^|;)\s*bbs_formhash=([^;]+)", cookie)
    if len(matches) != 1 or not matches[0].strip():
        raise ValueError("Cookie 必须含唯一且非空的 bbs_formhash")
    token = matches[0].strip().strip('"')
    if not token:
        raise ValueError("bbs_formhash 不能为空")
    return token


def identity(body):
    # Discuz 官方页面的账号名称链接，绝不读取 Cookie 中的账号字段。
    match = re.search(r'<strong\b[^>]*>\s*<a\b[^>]*href=[\'"][^\'"]*home\.php\?mod=space(?:&amp;|&)uid=\d+[^\'"]*[\'"][^>]*>([^<>]+)</a>', body)
    if match:
        name = html.unescape(match[1]).strip()
        if name and not re.search(r"\d{7,}|[\r\n]", name):
            log("官方账号昵称：" + name)


def sign(cookie, token):
    url = BASE + "/plugin.php?" + parse.urlencode({"id": "dsu_paulsign:sign", "operation": "qiandao", "infloat": "1", "inajax": "1"})
    body = http(url, cookie=cookie, data=parse.urlencode({"formhash": token, "qdxq": "kx", "qdmode": "1", "todaysay": public_text()}).encode())
    identity(body)
    messages = re.findall(r'<div\s+class=[\'"]c[\'"]\s*>(.*?)</div>', body, re.S)
    text = html.unescape(re.sub(r"<[^>]+>", "", " ".join(messages)))
    if any(word in text for word in ("签到成功", "签到完成")) and not any(word in text for word in ("失败", "未", "不成功")):
        return "success", "签到成功（官方响应确认）"
    if any(word in text for word in ("今天已经签到", "今日已经签到", "今天您已经签到", "您今天已经签到", "已经签过到")):
        return "already", "今日已签到（官方响应确认）"
    return "failed", "签到未获得明确成功确认；请核对登录状态或接口，响应已隐藏"


def draw(cookie):
    prizes = {"2": 18, "4": 188, "5": 88, "7": 8}
    outcomes = []
    gain = 0
    for number in range(1, 11):
        started = time.monotonic()
        try:
            body = json.loads(http(BASE + "/plugin.php?id=choujiang&do=draw", cookie=cookie, data=b""))
            ret = str(body.get("ret", ""))
            if ret in prizes:
                gain += prizes[ret] - 10
                status, detail = "success", f"抽奖已确认，奖励 {prizes[ret]} 加油，消耗 10 加油"
            else:
                status, detail = "failed", "抽奖返回未验证业务码；停止后续抽奖，响应已隐藏"
        except Exception:
            status, detail = "failed", "抽奖请求失败；结果可能未确认，停止后续抽奖"
        outcomes.append(status)
        log(f"阶段 2.{number} 抽奖：{detail}；耗时 {time.monotonic()-started:.2f} 秒")
        if status == "failed":
            break
        if number < 10:
            time.sleep(5)
    log(f"抽奖统计：确认成功 {outcomes.count('success')} 次，确认净加油 {gain}")
    return outcomes


def notify(summary, dry):
    try:
        if not enabled("QINGLONG_NOTIFY", "1"):
            return "已关闭"
        if dry:
            # 通知器通常会联网；断网预演只输出通知摘要，绝不调用它。
            log("预演通知摘要：" + summary)
            return "预演摘要已生成，断网模式不外发"
        try:
            import notify as module
        except ImportError:
            module = None
            candidates = []
            directory = os.environ.get("QINGLONG_NOTIFY_DIR")
            if directory:
                candidates.append(Path(directory) / "notify.py")
            candidates += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
            for path in candidates:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, "send", None)):
            return "通知组件不可用，保留业务退出码"
        module.send(TITLE, summary)
        return "通知已发送"
    except Exception:
        return "通知失败，保留业务退出码（异常内容已隐藏）"


def main():
    began = time.monotonic()
    start_time = datetime.now().isoformat(timespec="seconds")
    log("========== " + TITLE + " ==========")
    log("开始时间：" + start_time)
    value = os.environ.get("ONEPLUSBBS", "").strip() or os.environ.get("ONEPLUSBBS_COOKIE", "").strip()
    accounts = [line.strip() for line in value.splitlines() if line.strip()]
    results = []
    config_error = False
    dry = False
    try:
        dry = enabled("ONEPLUSBBS_DRY_RUN")
        do_draw = enabled("ONEPLUSBBS_DRAW")
        enabled("QINGLONG_NOTIFY", "1")
        if not accounts:
            raise ValueError("请配置 ONEPLUSBBS，每行一个完整 Cookie")
    except ValueError as exc:
        log("❌ 配置错误：" + str(exc))
        config_error = True
    log(f"运行模式：{'断网预演' if dry else '正式执行'}；账号总数：{len(accounts)}")
    if not config_error:
        for index, cookie in enumerate(accounts, 1):
            account_start = time.monotonic()
            steps = []
            log(f"----- 账号 {index} -----")
            stage_start = time.monotonic()
            try:
                token = formhash(cookie)
                if dry:
                    log("阶段 1 签到：DRY_RUN_OK 参数已解析，未发送请求，未产生业务成功记录")
                    steps.append("skipped")
                else:
                    status, detail = sign(cookie, token)
                    steps.append(status)
                    log("阶段 1 签到：" + detail)
            except Exception:
                steps.append("failed")
                log("阶段 1 签到：❌ 凭据格式错误或请求失败；详情已隐藏")
            log(f"阶段 1 耗时 {time.monotonic()-stage_start:.2f} 秒")
            if do_draw and not dry and steps[0] != "failed":
                steps.extend(draw(cookie))
            else:
                steps.append("skipped")
                log("阶段 2 抽奖：⏭️ " + ("断网预演，未消耗加油" if dry else "未授权抽奖或签到失败") + "；耗时 0.00 秒")
            stats = {key: steps.count(key) for key in ("success", "already", "skipped", "failed")}
            result = {"account": index, "ok": stats["failed"] == 0, "tasks": len(steps), **stats,
                      "elapsedSeconds": round(time.monotonic()-account_start, 2)}
            results.append(result)
            log(f"账号 {index} 统计：总任务 {len(steps)}，成功 {stats['success']}，已完成 {stats['already']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {result['elapsedSeconds']} 秒")
    failed = sum(not result["ok"] for result in results)
    ok = not config_error and not failed
    status = "configuration-error" if config_error else ("dry-run" if dry and ok else ("success" if ok else "partial-failure" if failed < len(results) else "failure"))
    summary = f"账号总数 {len(accounts)}，{'预演通过' if dry else '成功'} {sum(r['ok'] for r in results)}，失败 {failed}；状态 {status}"
    notification = notify(summary, dry)
    log("----------------------------------------")
    log(summary)
    totals = {key: sum(r[key] for r in results) for key in ("tasks", "success", "already", "skipped", "failed")}
    log(f"子任务统计：总数 {totals['tasks']}，成功 {totals['success']}，已完成 {totals['already']}，跳过 {totals['skipped']}，失败 {totals['failed']}")
    log("通知状态：" + notification)
    finish = datetime.now().isoformat(timespec="seconds")
    log(f"完成时间：{finish}；总耗时 {time.monotonic()-began:.2f} 秒；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"status": status, "dryRun": dry, "accountCount": len(accounts),
          "passedAccounts": sum(r["ok"] for r in results), "failedAccounts": failed, "configurationError": config_error,
          "accounts": results, "taskStatistics": totals, "notification": notification,
          "startTime": start_time, "finishTime": finish, "elapsedSeconds": round(time.monotonic()-began, 2)}, ensure_ascii=False, separators=(",", ":")))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
