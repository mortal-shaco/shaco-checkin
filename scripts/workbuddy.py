#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: WorkBuddy签到
# cron: 30 8 * * *
"""WorkBuddy(CodeBuddy CN) 独立每日签到，Python 3.8+，仅使用标准库。

来源：Cat-zaizai/ZaiZaiCat-Checkin，script/workbuddy/main.py 和 api.py。
原作者标注：Author: Assistant; Date: 2026-08-03。
接口实现参考 cockpit-tools (https://github.com/jlcodes99/cockpit-tools)
的 codebuddy_cn_oauth 模块。上游许可 MIT，维护版本沿用 MIT。

WORKBUDDY_ACCOUNTS：每个非空行是一个 JSON 对象，access_token 必填；
refresh_token、uid、enterprise_id、domain、user_agent 可选，兼容对应驼峰字段。
登录官方客户端后，从自己授权的请求中获取 Bearer 令牌和对应 X-* 请求头；
refresh_token 可取自可读取的官方登录态 auth.refreshToken，不自动解密或启动客户端。
旧配置 workbuddy.accounts 中的对象可直接逐行复制；不读取私有项目文件。
令牌过期时仅在内存中刷新，不默认回写凭据文件，下一轮需更新环境变量。
WORKBUDDY_DRY_RUN=1 完全断网，通知仅模拟；不代表真实签到成功。
WORKBUDDY_JITTER_MAX 默认 600 秒，WORKBUDDY_TIMEOUT 默认 30 秒。
QINGLONG_NOTIFY=0 关闭通知；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。

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
"""

import importlib.util
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler


TITLE = "WorkBuddy签到"
OFF = {"0", "false", "no", "off"}
ON = {"1", "true", "yes", "on"}


def log(message):
    print("[{}] {}".format(datetime.now().strftime("%H:%M:%S"), message), flush=True)


class TaskError(Exception):
    def __init__(self, message, expired=False):
        super().__init__(message)
        self.expired = expired


class NoRedirect(HTTPRedirectHandler):
    # 认证请求不跟随重定向，防止向其他主机传递凭据。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def boolean(data, keys, default=None):
    for key in keys:
        if key in data:
            value = data[key]
            if isinstance(value, bool):
                return value
            if value in (0, 1):
                return bool(value)
            if isinstance(value, str) and value.lower() in {"true", "false", "0", "1"}:
                return value.lower() in {"true", "1"}
            raise TaskError("响应布尔字段格式异常")
    return default


def number(data, *keys):
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and re.fullmatch(r"-?\d{1,12}", value):
            return int(value)
    return None


class WorkBuddyAPI:
    BASE_URL = "https://www.codebuddy.cn"
    CHECKIN_STATUS_PATHS = (
        "/v2/billing/meter/checkin-activity-status",
        "/v2/billing/meter/checkin-status",
    )
    DAILY_CHECKIN_PATH = "/v2/billing/meter/daily-checkin"
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, account, timeout):
        self.account = dict(account)
        self.timeout = timeout
        self.refreshed = False
        self.opener = build_opener(NoRedirect())

    def identity(self, data):
        # 仅显示官方返回的公开身份；不使用用户配置中的邮箱或设备信息。
        for key in ("nickname", "username", "displayName", "display_name", "uid"):
            value = data.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value)
                secrets = [self.account.get(k) for k in ("access_token", "refresh_token")]
                if any(v and v in text for v in secrets) or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                log("官方账号身份：" + json.dumps(text, ensure_ascii=False))
                break

    def post(self, path, refreshing=False):
        headers = {
            "Authorization": "Bearer " + self.account["access_token"],
            "Accept": "application/json", "Content-Type": "application/json",
            "User-Agent": self.account.get("user_agent") or self.DEFAULT_USER_AGENT,
        }
        for field, names in {
            "uid": ("X-User-Id",), "enterprise_id": ("X-Enterprise-Id", "X-Tenant-Id"),
            "domain": ("X-Domain",),
        }.items():
            if self.account.get(field):
                for name in names:
                    headers[name] = self.account[field]
        if refreshing:
            headers["X-Refresh-Token"] = self.account["refresh_token"]
        try:
            with self.opener.open(Request(self.BASE_URL + path, data=b"{}", headers=headers,
                                          method="POST"), timeout=self.timeout) as response:
                raw = response.read(1048577)
        except HTTPError as exc:
            raise TaskError("HTTP 请求失败（状态 {}）".format(exc.code), exc.code == 401) from None
        except (URLError, OSError, ValueError):
            raise TaskError("网络请求失败或超时") from None
        if len(raw) > 1048576:
            raise TaskError("响应超出大小限制")
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TaskError("接口响应不是有效 JSON") from None
        if not isinstance(body, dict):
            raise TaskError("接口响应结构异常")
        code = body.get("code")
        if type(code) is not int or code != 0:
            message = str(body.get("message") or body.get("msg") or "")
            expired = code == 401 or "登录" in message or "token" in message.lower()
            safe_code = str(code) if type(code) is int else "未知"
            raise TaskError("业务请求失败（业务码 {}）".format(safe_code), expired)
        data = body.get("data")
        if not isinstance(data, dict):
            raise TaskError("成功响应缺少有效 data 对象")
        self.identity(data)
        return data

    def request(self, path):
        try:
            return self.post(path)
        except TaskError as exc:
            if not exc.expired or not self.account.get("refresh_token"):
                raise
        log("令牌过期，尝试刷新并重试一次")
        data = self.post("/v2/plugin/auth/token/refresh", refreshing=True)
        token = data.get("accessToken") or data.get("access_token")
        if not isinstance(token, str) or not token or any(c in token for c in "\r\n"):
            raise TaskError("刷新响应缺少有效访问令牌")
        self.account["access_token"] = token
        for field, alias in (("refresh_token", "refreshToken"), ("domain", "domain")):
            value = data.get(alias) or data.get(field)
            if value:
                if not isinstance(value, str) or any(c in value for c in "\r\n"):
                    raise TaskError("刷新响应字段格式异常")
                self.account[field] = value
        self.refreshed = True
        log("✅ 访问令牌已在内存刷新；未写入配置文件")
        return self.post(path)

    def status(self):
        for i, path in enumerate(self.CHECKIN_STATUS_PATHS):
            try:
                data = self.request(path)
                active = boolean(data, ("active", "Active"), True)
                checked = boolean(data, ("today_checked_in", "todayCheckedIn"))
                if active and checked is None:
                    raise TaskError("状态响应缺少今日签到字段")
                return data, active, checked
            except TaskError as exc:
                log("⚠️ 状态接口 {}：{}".format(i + 1, exc))
                if exc.expired or i == 1:
                    raise
                log("尝试兼容状态接口")


def parse_account(line):
    try:
        data = json.loads(line)
    except ValueError:
        raise TaskError("账号行必须是有效 JSON 对象") from None
    if not isinstance(data, dict):
        raise TaskError("账号行必须是 JSON 对象")
    for canonical, alias in (("access_token", "accessToken"), ("refresh_token", "refreshToken"),
                             ("enterprise_id", "enterpriseId"), ("user_agent", "userAgent")):
        if not data.get(canonical) and data.get(alias):
            data[canonical] = data[alias]
    if not isinstance(data.get("access_token"), str) or not data["access_token"].strip():
        raise TaskError("账号缺少 access_token，请重新获取登录凭据")
    for key in ("access_token", "refresh_token", "uid", "enterprise_id", "domain", "user_agent"):
        if data.get(key) is not None and (not isinstance(data[key], str) or any(c in data[key] for c in "\r\n")):
            raise TaskError("账号认证字段必须是无换行的字符串")
    return data


def notify(summary, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in OFF:
        return "已关闭"
    if dry:
        return "断网预演，已模拟通知"
    body = "账号总数 {total}，成功 {success}，失败 {failed}；最终状态 {status}".format(**summary)
    candidates = []
    configured = os.getenv("QINGLONG_NOTIFY_DIR")
    if configured:
        candidates.append(Path(configured) / "notify.py")
    candidates.extend([Path(__file__).resolve().parent / "notify.py",
                       Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    try:
        for path in candidates:
            if path.is_file():
                spec = importlib.util.spec_from_file_location("ql_notify", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.send(TITLE, body)
                return "已发送"
        # 青龙可以将 notify 安装在模块搜索路径中。
        import notify as module
        module.send(TITLE, body)
        return "已发送"
    except Exception:
        log("⚠️ 通知模块不可用或发送失败，保留业务退出码")
        return "不可用或发送失败"


def main():
    started = time.monotonic()
    dry = os.getenv("WORKBUDDY_DRY_RUN", "0").strip().lower() in ON
    lines = [line.strip() for line in os.getenv("WORKBUDDY_ACCOUNTS", "").splitlines() if line.strip()]
    log("========== {} ==========".format(TITLE))
    log("开始时间：" + datetime.now().isoformat(timespec="seconds"))
    log("模式：{}；账号数：{}".format("断网预演" if dry else "正式运行", len(lines)))
    results = []
    config_error = False
    try:
        timeout = int(os.getenv("WORKBUDDY_TIMEOUT", "30"))
        jitter = int(os.getenv("WORKBUDDY_JITTER_MAX", "600"))
        if not 1 <= timeout <= 120 or not 0 <= jitter <= 3600:
            raise ValueError()
        if not lines:
            raise TaskError("未配置 WORKBUDDY_ACCOUNTS")
    except (ValueError, TaskError):
        config_error = True
        log("❌ 配置错误：账号不能为空，超时须为 1～120 秒，随机延迟须为 0～3600 秒")
    if not config_error:
        if not dry and jitter:
            delay = random.uniform(0, jitter)
            log("启动错峰等待 {:.1f} 秒".format(delay))
            time.sleep(delay)
        for index, line in enumerate(lines, 1):
            account_start = time.monotonic()
            counts = dict(total=0, success=0, already=0, skipped=0, failed=0)
            log("--- 账号 {} ---".format(index))
            def stage(name, action, simulated=False):
                counts["total"] += 1
                tick = time.monotonic()
                log("阶段 {}：{}".format(counts["total"], name))
                try:
                    value = action()
                    counts["skipped" if simulated else "success"] += 1
                    log("{} {}{}；耗时 {:.2f} 秒".format(
                        "⏭️" if simulated else "✅", name,
                        "已模拟（未请求服务端）" if simulated else "完成", time.monotonic() - tick))
                    return value
                except Exception:
                    counts["failed"] += 1
                    log("❌ {}失败；耗时 {:.2f} 秒".format(name, time.monotonic() - tick))
                    raise
            ok = False
            try:
                account = stage("验证账号参数", lambda: parse_account(line))
                if dry:
                    stage("预演状态查询、刷新重试与签到复查流程", lambda: None, simulated=True)
                    log("DRY_RUN_OK：未发起 HTTP、未改写凭据、已模拟通知")
                else:
                    api = WorkBuddyAPI(account, timeout)
                    data, active, checked = stage("查询今日签到状态", api.status)
                    log("每日积分 {}，连签天数 {}".format(number(data, "daily_credit", "dailyCredit"),
                                                               number(data, "streak_days", "streakDays")))
                    if not active:
                        counts["skipped"] += 1
                        log("⏭️ 官方确认签到活动未开启或不适用")
                    elif checked:
                        counts["already"] += 1
                        log("☑️ 今日已签到")
                    else:
                        try:
                            def checkin():
                                response = api.request(api.DAILY_CHECKIN_PATH)
                                if boolean(response, ("success",), True) is not True:
                                    raise TaskError("签到业务返回失败")
                                return response
                            reward = stage("执行每日签到", checkin)
                            log("✅ 签到成功；积分 {}，连签 {} 天，连签奖励 {}".format(
                                number(reward, "credit", "today_credit", "todayCredit"),
                                number(reward, "streak_days", "streakDays"),
                                "是" if boolean(reward, ("is_streak_day", "isStreakDay"), False) else "否"))
                        except TaskError:
                            _, _, latest = stage("签到失败后复查", api.status)
                            if not latest:
                                raise TaskError("签到未成功且复查未确认今日已签")
                            counts["already"] += 1
                            log("☑️ 复查确认今日已签到")
                ok = True
            except TaskError as exc:
                log("❌ 账号 {}：{}".format(index, exc))
            except Exception:
                log("❌ 账号 {}：执行异常，未输出异常内容或凭据".format(index))
            results.append({"account": index, "success": ok, "tasks": counts})
            log("账号 {}统计：总任务 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}；耗时 {:.2f} 秒".format(
                index, time.monotonic() - account_start, **counts))
            if not dry and index < len(lines):
                time.sleep(random.uniform(5, 10))
    success = sum(item["success"] for item in results)
    failed = len(lines) - success
    exit_code = 1 if config_error or failed else 0
    status = "配置错误" if config_error else ("预演通过" if dry and not failed else (
        "成功" if not failed else ("部分失败" if success else "失败")))
    summary = {"total": len(lines), "success": success, "failed": failed, "status": status,
               "mode": "dry-run" if dry else "live", "exit_code": exit_code, "accounts": results}
    notification = notify(summary, dry)
    summary["notification"] = notification
    summary["duration_seconds"] = round(time.monotonic() - started, 2)
    log("----------------------------------------")
    log("任务统计：账号总数 {}，成功 {}，失败 {}".format(len(lines), success, failed))
    totals = {key: sum(item["tasks"][key] for item in results) for key in ("total", "success", "already", "skipped", "failed")}
    log("子任务统计：总数 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}".format(**totals))
    log("通知状态：{}；总耗时：{} 秒".format(notification, summary["duration_seconds"]))
    log("完成时间：{}；最终状态：{}".format(datetime.now().isoformat(timespec="seconds"), status))
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
