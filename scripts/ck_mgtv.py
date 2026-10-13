# -*- coding: utf-8 -*-
# name: 芒果TV每日签到
# cron: 15 8 * * *
# 来源：yuxian158/check dailycheckin_scripts/ck_mgtv.py
# 上游版本：723c834f121ff4eef2dec7afe521071a7efff1a9；许可证：MIT
# 上游文件未包含独立版权声明；保留来源署名。
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
"""芒果TV每日签到；仅使用 Python 标准库。

MGTV_PARAMS：每行一个账号的完整 creditsTake 请求查询串，不含 URL 或问号。
登录芒果TV后，在本人设备的网络调试工具中执行签到，找到
https://credits.bz.mgtv.com/user/creditsTake，复制原始查询串。
必须保留 ticket、uuid，以及请求中的 abroad、appVersion、device、did、
osType、callback 等字段。不要分享参数；失效时重新登录获取。
兼容 MGTV 环境变量（同一查询串格式）；MGTV_PARAMS 优先。
原来的私有配置对象 params 对应本环境变量的一行。
MGTV_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
上游未声明 cron，本维护版建议每天 08:15 执行一次。
"""

import datetime
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request


TITLE = "芒果TV签到"
OFF = {"0", "false", "no", "off"}


class TaskError(Exception):
    pass


def log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {message}", flush=True)


def parse_account(line):
    if line.startswith(("http://", "https://", "?")):
        raise TaskError("请填写原始查询串，不含完整网址或问号")
    try:
        pairs = urllib.parse.parse_qs(line, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise TaskError("查询串格式错误") from None
    if any(len(values) != 1 for values in pairs.values()):
        raise TaskError("查询串含重复字段，请重新获取")
    params = {key: values[0] for key, values in pairs.items()}
    if not all(params.get(key, "").strip() for key in ("ticket", "uuid")):
        raise TaskError("缺少 ticket 或 uuid 字段")
    params["timestamp"] = str(round(time.time()))
    return params


def get_json(url, params, callback=None):
    # 固定官方 HTTPS 地址；不跟随重定向，防止查询串凭据跨站流出。
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    request = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                     headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            if response.status != 200:
                raise TaskError("HTTP 状态异常")
            raw = response.read(262145)
        if len(raw) > 262144:
            raise TaskError("响应超过大小限制")
        content = raw.decode("utf-8").strip()
        if callback and not content.startswith("{"):
            match = re.fullmatch(re.escape(callback) + r"\s*\((.*)\)\s*;?", content, re.S)
            if not match:
                raise TaskError("JSONP 格式与 callback 不匹配")
            content = match.group(1)
        result = json.loads(content)
        if not isinstance(result, dict):
            raise TaskError("响应结构错误")
        return result
    except TaskError:
        raise
    except (urllib.error.URLError, OSError, ValueError, UnicodeError):
        # 网络异常通常包含带凭据的 URL，禁止打印异常文本。
        raise TaskError("网络请求或响应解析失败，请检查连接及参数有效性") from None


def checked_data(result):
    if type(result.get("code")) is not int or result["code"] != 200:
        raise TaskError("业务未确认成功，请检查登录状态或接口变化")
    data = result.get("data")
    if not isinstance(data, dict):
        raise TaskError("业务响应缺少 data")
    return data


def notify_summary(body, dry_run):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in OFF:
        return "已关闭"
    if dry_run:
        log("通知预演：" + body)
        return "预演成功（未发送网络通知）"
    try:
        try:
            module = importlib.import_module("notify")
        except ImportError:
            paths = []
            if os.getenv("QINGLONG_NOTIFY_DIR"):
                paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
            paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                return "不可用（未找到 notify.py）"
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.send(TITLE, body)
        return "已发送"
    except Exception:
        return "发送失败（业务退出码保持不变）"


def main():
    started = time.monotonic()
    dry_run = os.getenv("MGTV_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}
    value = os.getenv("MGTV_PARAMS", "").strip() or os.getenv("MGTV", "").strip()
    accounts = [line.strip() for line in value.splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.datetime.now().isoformat(timespec='seconds')}；模式：{'断网预演' if dry_run else '正式'}；账号数：{len(accounts)}")
    totals = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    results = []
    if not accounts:
        log("❌ 配置错误：请设置 MGTV_PARAMS，每行一个账号查询串")
    for index, line in enumerate(accounts, 1):
        account_start = time.monotonic()
        stats = {key: 0 for key in totals}
        params = None
        log(f"账号 {index} 开始")
        for number, name in enumerate(("参数校验", "账号信息", "签到积分"), 1):
            stage_start = time.monotonic()
            stats["total"] += 1
            try:
                if number == 1:
                    params = parse_account(line)
                    detail = "查询串有效，保留原请求字段并刷新 timestamp"
                elif params is None:
                    stats["skipped"] += 1
                    log(f"账号 {index} 阶段 {number} {name}：⏭️ 参数无效，跳过；耗时 {time.monotonic() - stage_start:.2f}s")
                    continue
                elif dry_run:
                    detail = "DRY_RUN_OK：模拟成功，未进行网络请求或签到"
                elif number == 2:
                    user_params = {key: params.get(key, "") for key in
                                   ("abroad", "appVersion", "device", "did", "osType", "ticket", "uuid")}
                    user_params.update(ageMode="0", artistId=params["uuid"], mac=params.get("did", ""), src="mgtv", testversion="")
                    data = checked_data(get_json("https://homepage.bz.mgtv.com/v2/user/userInfo", user_params))
                    nickname = data.get("nickName")
                    detail = "账号信息查询成功"
                    if isinstance(nickname, str) and nickname:
                        # 以 JSON 字符串显示官方昵称，避免控制字符注入日志。
                        # 不输出以参数回显、手机号或设备标识冒充的昵称。
                        sensitive = [params.get(k) for k in ("ticket", "uuid", "did", "device") if params.get(k)]
                        if not any(secret in nickname for secret in sensitive) and not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", nickname):
                            detail += "；昵称：" + json.dumps(nickname, ensure_ascii=False)
                else:
                    data = checked_data(get_json("https://credits.bz.mgtv.com/user/creditsTake", params, params.get("callback")))
                    for field in ("curDay", "credits"):
                        val = data.get(field)
                        if isinstance(val, bool) or not isinstance(val, (int, float)) or val < 0 or not float(val).is_integer():
                            raise TaskError("签到响应缺少有效积分或签到天数")
                    detail = f"签到成功；签到积分：{data['credits']}积分；已经签到：{data['curDay']}天/21天"
                stats["success"] += 1
                log(f"账号 {index} 阶段 {number} {name}：✅ {detail}；耗时 {time.monotonic() - stage_start:.2f}s")
            except TaskError as error:
                stats["failed"] += 1
                log(f"账号 {index} 阶段 {number} {name}：❌ {error}；耗时 {time.monotonic() - stage_start:.2f}s")
            except Exception:
                stats["failed"] += 1
                log(f"账号 {index} 阶段 {number} {name}：❌ 处理异常（详细响应已隐藏）；耗时 {time.monotonic() - stage_start:.2f}s")
        for key in totals:
            totals[key] += stats[key]
        results.append({"account": index, "status": "failed" if stats["failed"] else "success", "tasks": stats})
        log(f"账号 {index} 统计：总任务 {stats['total']}；成功 {stats['success']}；已完成 {stats['alreadyComplete']}；跳过 {stats['skipped']}；失败 {stats['failed']}；耗时 {time.monotonic() - account_start:.2f}s")
    successes = sum(result["status"] == "success" for result in results)
    failures = len(accounts) - successes
    code = 1 if failures or not accounts else 0
    status = "configuration-error" if not accounts else ("partial-failure" if failures and successes else "failure" if failures else "dry-run" if dry_run else "success")
    body = f"状态：{status}；账号总数：{len(accounts)}；成功：{successes}；失败：{failures}；子任务成功：{totals['success']}；子任务失败：{totals['failed']}"
    notification = notify_summary(body, dry_run)
    log("----------------------------------------")
    log(body)
    log(f"子任务统计：总数 {totals['total']}；已完成 {totals['alreadyComplete']}；跳过 {totals['skipped']}")
    log(f"完成时间：{datetime.datetime.now().isoformat(timespec='seconds')}；总耗时 {time.monotonic() - started:.2f}s；通知：{notification}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"application": "mgtv", "mode": "dry-run" if dry_run else "live", "status": status, "accounts": len(accounts), "success": successes, "failed": failures, "tasks": totals, "results": results, "notification": notification, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
