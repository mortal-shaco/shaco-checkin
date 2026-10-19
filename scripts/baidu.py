#!/usr/bin/env python3
# name: 百度站点提交
# cron: 36 2 * * *
# 来源: Sitoi/dailycheckin dailycheckin/baidu/main.py
# 上游提交: 135cc236e59ac4f14bcddc44acb3cbb3ed6010b5，许可证: MIT
# 原始文件没有额外版权声明。保留上游署名，改写版本同样采用 MIT 许可证。
# BAIDU: 每行一个 JSON 对象，包含 data_url、submit_url，可选 times（默认 1）。
# 在百度搜索资源平台获取自己站点的 API 提交地址（含 site 和 token），
# 使用 HTTPS 地址；data_url 为自己的公开 UTF-8 文本清单，每行一个站点 URL。
# 上游未声明 cron，此处提供每日 09:00 的可调整订阅时间。
# BAIDU_DRY_RUN=1 完全离线预演；QINGLONG_NOTIFY=0 关闭通知。
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
        _ql_notify_identities = ('ed0673d8c02fc410', 'scripts/baidu.py', 'baidu.py', 'baidu')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import ipaddress
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request


TITLE = "百度站点提交"
MAX_BYTES = 1024 * 1024
TIMEOUT = 15


def log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {message}", flush=True)


def public_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError("网址格式错误")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("必须使用无用户信息及片段的 HTTPS 网址")
    if parsed.port not in (None, 443):
        raise ValueError("仅支持 HTTPS 默认端口")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".localhost")):
        raise ValueError("不支持本地地址")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("不支持非公网地址")
    return parsed


def parse_account(line):
    item = json.loads(line)
    if not isinstance(item, dict):
        raise ValueError("账号行必须为 JSON 对象")
    public_url(item.get("data_url"))
    submit = public_url(item.get("submit_url"))
    if submit.hostname != "data.zz.baidu.com" or submit.path != "/urls":
        raise ValueError("提交地址必须为百度站点提交接口")
    query = urllib.parse.parse_qs(submit.query, keep_blank_values=True)
    if len(query.get("token", [])) != 1 or not query["token"][0] or len(query.get("site", [])) != 1 or not query["site"][0]:
        raise ValueError("提交地址缺少唯一的 site 或 token")
    site = urllib.parse.urlsplit(query["site"][0])
    if site.scheme not in ("http", "https") or not site.hostname or site.username or site.password or site.query or site.fragment:
        raise ValueError("site 必须为无凭据的站点地址")
    times = item.get("times", 1)
    if type(times) is not int or not 1 <= times <= 100:
        raise ValueError("times 必须为 1 至 100 的整数")
    item["times"] = times
    item["site_host"] = site.hostname
    return item


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, data=None):
    # 禁止重定向，避免将带 token 的提交地址转发到其他站点。
    opener = urllib.request.build_opener(NoRedirect())
    headers = {"User-Agent": "Qinglong-Baidu-Submit/1.0"}
    if data is not None:
        headers["Content-Type"] = "text/plain; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers)
    with opener.open(req, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise ValueError("HTTP 状态不是 200")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("响应超过大小限制")
        return raw


def fetch_payload(item):
    raw = request(item["data_url"])
    urls = [line.strip() for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    if not urls:
        raise ValueError("URL 清单为空")
    for url in urls:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https") or parsed.hostname != item["site_host"] or parsed.username or parsed.password or parsed.fragment or any(c.isspace() for c in url):
            raise ValueError("清单包含格式错误或非本站 URL")
    return "\n".join(urls).encode("utf-8"), len(urls)


def submit_once(item, payload, count):
    response = json.loads(request(item["submit_url"], payload))
    if not isinstance(response, dict) or "error" in response:
        raise ValueError("百度接口返回业务错误")
    success, remain = response.get("success"), response.get("remain")
    if type(success) is not int or not 0 < success <= count or type(remain) is not int or remain < 0:
        raise ValueError("百度响应缺少有效 success 或 remain")
    if response.get("not_same_site") or response.get("not_valid") or success != count:
        raise ValueError("百度接口仅接受部分 URL 或拒绝了 URL")
    return success, remain


def notify(summary, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in ("0", "false", "no", "off"):
        return "已关闭"
    if dry:
        return "离线预演，已生成通知摘要，未调用通知网络"
    body = (f"状态：{summary['status']}；账号总数：{summary['accounts']}；"
            f"成功：{summary['successfulAccounts']}；失败：{summary['failedAccounts']}；"
            f"子任务成功：{summary['steps']['success']}；失败：{summary['steps']['failed']}")
    # 通知在子进程执行，抑制通知模块输出并限制耗时，保留业务退出码。
    helper = '''import importlib.util, pathlib, sys
title, body, directory = sys.argv[1:]
try:
    from notify import send
except ImportError:
    send = None
    for root in ([directory] if directory else []) + ['/ql/data/scripts', '/ql/scripts']:
        path = pathlib.Path(root) / 'notify.py'
        if path.is_file():
            spec = importlib.util.spec_from_file_location('ql_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = module.send
            break
if send is None:
    sys.exit(2)
send(title, body)
'''
    try:
        result = subprocess.run([sys.executable, "-c", helper, TITLE, body, os.getenv("QINGLONG_NOTIFY_DIR", "")],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
        return "已发送" if result.returncode == 0 else "不可用或发送失败（业务退出码不变）"
    except Exception:
        return "发送失败或超时（业务退出码不变）"


def main():
    begin = time.monotonic()
    dry = os.getenv("BAIDU_DRY_RUN", "0").lower() in ("1", "true", "yes", "on")
    lines = [line.strip() for line in os.getenv("BAIDU", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.datetime.now().isoformat(timespec='seconds')}；模式：{'离线预演' if dry else '实际提交'}；账号数：{len(lines)}")
    summary = {"accounts": len(lines), "successfulAccounts": 0, "failedAccounts": 0, "configurationErrors": 0,
               "dryRun": dry, "steps": {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}}
    if not lines:
        log("❌ 配置错误：必须设置 BAIDU，每行一个站点配置")
    for index, line in enumerate(lines, 1):
        account_start = time.monotonic()
        stats = {"total": 1, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        stage = time.monotonic()
        log(f"账号 {index} / 阶段 1：校验参数")
        good = True
        try:
            item = parse_account(line)
            log(f"站点地址：{item['site_host']}")
            log(f"✅ 参数校验完成；耗时 {time.monotonic()-stage:.2f} 秒")
        except Exception:
            log(f"❌ 参数无效：检查 JSON、HTTPS 接口、site、token 和 times；耗时 {time.monotonic()-stage:.2f} 秒")
            stats["failed"] += 1
            summary["configurationErrors"] += 1
            good = False
        if good:
            stats["success"] += 1
            stage = time.monotonic()
            stats["total"] += 1
            log(f"账号 {index} / 阶段 2：读取本站 URL 清单")
            try:
                if dry:
                    payload, count = b"", 0
                    log("⏭️ 离线预演：不读取清单、不调用百度、不消耗配额")
                    stats["skipped"] += 1
                else:
                    payload, count = fetch_payload(item)
                    log(f"✅ 清单校验完成：{count} 条 URL")
                    stats["success"] += 1
            except Exception:
                log("❌ 清单获取或校验失败（未输出地址、凭据或原始响应）")
                stats["failed"] += 1
                good = False
            log(f"阶段 2 耗时：{time.monotonic()-stage:.2f} 秒")
        if good:
            total_success, remain, submit_successes, submit_failures = 0, None, 0, 0
            for attempt in range(item["times"]):
                stage = time.monotonic()
                stats["total"] += 1
                log(f"账号 {index} / 阶段 {attempt+3}：提交 {attempt+1}/{item['times']}")
                if dry:
                    stats["skipped"] += 1
                    log("⏭️ DRY_RUN_OK：提交阶段已离线预演")
                else:
                    try:
                        accepted, remain = submit_once(item, payload, count)
                        total_success += accepted
                        submit_successes += 1
                        stats["success"] += 1
                        log(f"✅ 百度确认提交成功：{accepted} 条；剩余条数：{remain}")
                    except Exception:
                        submit_failures += 1
                        stats["failed"] += 1
                        good = False
                        log("❌ 提交失败或业务结果未完整确认；停止本站后续重复提交，避免重复副作用")
                log(f"阶段 {attempt+3} 耗时：{time.monotonic()-stage:.2f} 秒")
                if not good:
                    remaining = item["times"] - attempt - 1
                    stats["total"] += remaining
                    stats["skipped"] += remaining
                    break
            log(f"账号 {index}：成功条数 {total_success}；剩余条数 {remain if remain is not None else '未查询'}；成功次数 {submit_successes}；失败次数 {submit_failures}")
        summary["successfulAccounts" if good else "failedAccounts"] += 1
        for key in stats:
            summary["steps"][key] += stats[key]
        log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}；耗时 {time.monotonic()-account_start:.2f} 秒")
    failed = not lines or summary["failedAccounts"] > 0
    summary["status"] = "configuration-error" if not lines or summary["configurationErrors"] == len(lines) else ("partial-failure" if failed and summary["successfulAccounts"] else "failure" if failed else "dry-run" if dry else "success")
    summary["notification"] = notify(summary, dry)
    summary["durationSeconds"] = round(time.monotonic() - begin, 2)
    summary["finishedAt"] = datetime.datetime.now().isoformat(timespec="seconds")
    log("----------------------------------------")
    log(f"任务统计：账号 {summary['accounts']}；成功 {summary['successfulAccounts']}；失败 {summary['failedAccounts']}；子任务 {json.dumps(summary['steps'], ensure_ascii=False)}")
    log(f"完成时间：{summary['finishedAt']}；总耗时 {summary['durationSeconds']} 秒；通知：{summary['notification']}；最终状态：{summary['status']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
