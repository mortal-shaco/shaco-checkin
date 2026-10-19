# -*- coding: utf-8 -*-
# name: 百度搜索资源平台
# cron: 8 2 * * *
# 上游：OreosLab/checkinpanel，ck_baidu_url_submit.py
# 原始任务元数据：new Env('百度搜索资源平台');
# License: MIT
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
"""BAIDU_ACCOUNTS：每行一个 JSON 对象，包含 data_url、submit_url、可选 times。
在百度搜索资源平台验证站点后，从普通收录的 API 提交页面获取含 site/token 的
接口地址，使用 HTTPS。data_url 是自己维护的公开 UTF-8 URL 列表地址，每行一条。
默认仅推送一次；只有显式设置 times 才重复提交（会消耗配额）。兼容 BAIDU JSON 数组。
BAIDU_DRY_RUN=1 完全断网预演。QINGLONG_NOTIFY=0 关闭通知。
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
        _ql_notify_identities = ('cbcac1d0442bb8ef', 'scripts/ck_baidu_url_submit.py', 'ck_baidu_url_submit.py', 'ck_baidu_url_submit')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = "百度搜索资源平台"
MAX_BYTES = 2 * 1024 * 1024


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def enabled(name, default="0"):
    return os.getenv(name, default).strip().lower() not in ("", "0", "false", "no", "off")


class TaskError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口发生重定向，已阻止以保护凭据")


def fetch(url, data=None):
    headers = {"User-Agent": "Qinglong-Baidu-URL-Submit/1.0"}
    if data is not None:
        headers["Content-Type"] = "text/plain; charset=utf-8"
    req = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with build_opener(NoRedirect()).open(req, timeout=20) as response:
            if response.status != 200:
                raise TaskError("HTTP 状态异常")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise TaskError("响应超过大小限制")
            return body
    except TaskError:
        raise
    except Exception:
        raise TaskError("网络请求失败或超时（详情已脱敏）") from None


def web_url(value):
    if not isinstance(value, str):
        raise TaskError("URL 配置必须为字符串")
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError()
        if parsed.port not in (None, 443):
            raise ValueError()
        return parsed
    except ValueError:
        raise TaskError("地址必须为无内嵌用户名、密码或片段的 HTTPS URL") from None


def validate(account):
    if not isinstance(account, dict):
        raise TaskError("账号配置必须为 JSON 对象")
    data_url, submit_url = account.get("data_url"), account.get("submit_url")
    web_url(data_url)
    endpoint = web_url(submit_url)
    query = parse_qs(endpoint.query)
    if endpoint.hostname != "data.zz.baidu.com" or endpoint.path != "/urls":
        raise TaskError("提交地址必须是百度 data.zz.baidu.com/urls 官方接口")
    if any(len(query.get(key, [])) != 1 or not query[key][0].strip() for key in ("site", "token")):
        raise TaskError("提交接口缺少唯一的 site 或 token 参数")
    site = urlsplit(query["site"][0])
    if site.scheme not in ("http", "https") or not site.hostname or site.username or site.password:
        raise TaskError("site 参数必须为已验证站点的 HTTP 或 HTTPS 地址")
    raw_times = account.get("times", 1)
    try:
        times = int(raw_times)
        if isinstance(raw_times, bool) or str(times) != str(raw_times) or not 1 <= times <= 100:
            raise ValueError()
    except (ValueError, TypeError):
        raise TaskError("times 必须是 1 至 100 的整数，默认 1") from None
    return data_url, submit_url, times, site.hostname


def load_accounts():
    canonical = os.getenv("BAIDU_ACCOUNTS", "").strip()
    if canonical:
        result = []
        for line in canonical.splitlines():
            if line.strip():
                try:
                    result.append(json.loads(line))
                except ValueError:
                    result.append(None)
        return result
    legacy = os.getenv("BAIDU", "").strip()
    if legacy:
        try:
            result = json.loads(legacy)
            if isinstance(result, list) and result:
                return result
        except ValueError:
            pass
        raise TaskError("兼容变量 BAIDU 必须为非空 JSON 数组")
    raise TaskError("未设置必需的 BAIDU_ACCOUNTS")


def notify_summary(body, dry_run):
    if not enabled("QINGLONG_NOTIFY", "1"):
        return "已关闭"
    if dry_run:
        return "断网预演：已生成通知摘要，未调用外部通知模块"
    try:
        module = importlib.import_module("notify")
        module.send(TITLE, body)
        return "已发送"
    except Exception:
        pass
    paths = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for path in paths:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send(TITLE, body)
            return "已发送"
        except Exception:
            continue
    return "通知模块不可用或发送失败，保留业务退出码"


def run():
    started = time.monotonic()
    dry_run = enabled("BAIDU_DRY_RUN")
    log(f"===== {TITLE} =====")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry_run else '实际提交'}")
    results = []
    configuration_error = False
    try:
        accounts = load_accounts()
    except TaskError as exc:
        accounts = []
        configuration_error = True
        log(f"❌ 配置错误：{exc}")
    log(f"账号总数：{len(accounts)}")
    for index, account in enumerate(accounts, 1):
        account_start = time.monotonic()
        stats = dict(account=index, total=1, success=0, alreadyComplete=0, skipped=0, failed=0, submitted=0)
        stage_start = time.monotonic()
        try:
            log(f"账号 {index} · 阶段 1 参数检查")
            data_url, submit_url, times, site_host = validate(account)
            stats["total"] = times
            log(f"✅ 参数检查通过；计划提交 {times} 次；耗时 {time.monotonic()-stage_start:.2f} 秒")
            stage_start = time.monotonic()
            log(f"账号 {index} · 阶段 2 获取并检查 URL 列表")
            if dry_run:
                stats["skipped"] = times
                log("⏭️ DRY_RUN_OK：参数有效；跳过获取列表和提交；网络请求数 0")
            else:
                try:
                    lines = [line.strip() for line in fetch(data_url).decode("utf-8-sig").splitlines() if line.strip()]
                except UnicodeError:
                    raise TaskError("URL 列表必须使用 UTF-8 编码") from None
                if not lines:
                    raise TaskError("URL 列表为空")
                for line in lines:
                    parsed = urlsplit(line)
                    if parsed.scheme not in ("http", "https") or parsed.hostname != site_host or parsed.username or parsed.password or any(c.isspace() for c in line):
                        raise TaskError("列表包含无效 URL 或非本站 URL，已阻止提交")
                payload = ("\n".join(lines) + "\n").encode("utf-8")
                log(f"✅ 列表检查通过，共 {len(lines)} 条；耗时 {time.monotonic()-stage_start:.2f} 秒")
                for attempt in range(1, times + 1):
                    stage_start = time.monotonic()
                    log(f"账号 {index} · 阶段 {attempt+2} 推送 URL（{attempt}/{times}）")
                    try:
                        try:
                            response = json.loads(fetch(submit_url, payload))
                        except (ValueError, UnicodeError):
                            raise TaskError("接口返回无效 JSON") from None
                        if not isinstance(response, dict):
                            raise TaskError("接口返回结构异常")
                        count, remain = response.get("success"), response.get("remain")
                        if response.get("error") or type(count) is not int or count <= 0 or count > len(lines) or type(remain) is not int or remain < 0:
                            raise TaskError("百度未确认有效推送成功")
                        stats["submitted"] += count
                        if count != len(lines) or response.get("not_same_site") or response.get("not_valid"):
                            raise TaskError("部分 URL 未被接受")
                        stats["success"] += 1
                        log(f"✅ 推送成功，接受 {count} 条，剩余配额 {remain}；耗时 {time.monotonic()-stage_start:.2f} 秒")
                    except TaskError as exc:
                        stats["failed"] += 1
                        log(f"❌ {exc}；耗时 {time.monotonic()-stage_start:.2f} 秒")
        except TaskError as exc:
            stats["failed"] = stats["total"]
            log(f"❌ 账号 {index}：{exc}；耗时 {time.monotonic()-stage_start:.2f} 秒")
        except Exception:
            stats["failed"] = max(1, stats["total"] - stats["success"])
            log(f"❌ 账号 {index}：处理异常（详情已脱敏）")
        stats["elapsedSeconds"] = round(time.monotonic() - account_start, 3)
        results.append(stats)
        log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 0，跳过 {stats['skipped']}，失败 {stats['failed']}，接受 URL {stats['submitted']}，耗时 {stats['elapsedSeconds']} 秒")
    failed = sum(bool(item["failed"]) for item in results)
    success = len(results) - failed
    exit_code = 1 if configuration_error or failed else 0
    status = "configuration-error" if configuration_error else ("partial-failure" if failed and success else "failure" if failed else "dry-run" if dry_run else "success")
    summary = dict(status=status, mode="dry-run" if dry_run else "live", accounts=len(results), success=success, failed=failed, configurationError=configuration_error, results=results)
    body = f"账号总数 {len(results)}，成功 {success}，失败 {failed}；状态 {status}；接受 URL {sum(r['submitted'] for r in results)}"
    notification = notify_summary(body, dry_run)
    summary["notification"] = notification
    summary["elapsedSeconds"] = round(time.monotonic() - started, 3)
    log("----------------------------------------")
    log(body)
    log(f"子任务：成功 {sum(r['success'] for r in results)}，跳过 {sum(r['skipped'] for r in results)}，失败 {sum(r['failed'] for r in results)}")
    log(f"通知状态：{notification}")
    log(f"完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {summary['elapsedSeconds']} 秒；最终状态 {status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
