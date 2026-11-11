# -*- coding: utf-8 -*-
# name: 米游社原神自动签到
# cron: 56 1 * * *
"""米游社原神签到：MYS_ACCOUNTS 每个非空行使用 UID,区服|完整Cookie。

从米游社官方原神签到页的本人已登录请求中取得 Cookie；UID 和区服可从
游戏内个人资料及该页签到请求的 uid、region 字段核对。不要分享这些值。
默认国服官服区服 cn_gf01，渠道服请使用本人请求中的 region。
不支持人机验证绕过；验证、过期凭据和接口变更均报告失败。

来源：BRSblackshoot/mihoyo_autosign，米游社自动签到.py
上游提交：5d73ed1cb644da2b44f4e012c204ff48c3ca0bbe；许可：MIT。
保留上游签名算法署名：v2.2.0 @Womsxd；v2.3.0 web @povsister & @journey-ad。
未获得新接口证据，因此保留上游 URL、DS 盐和配套 2.3.0 版本，未声称已实测可用。

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
        _ql_notify_identities = ('b59e31965541a4fa', 'scripts/task_b59e3196.py', 'task_b59e3196.py', 'task_b59e3196')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import string
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

TITLE = "米游社原神自动签到"
CATALOG_ID = "b59e31965541a4fa"
BASE = "https://api-takumi.mihoyo.com"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}


class TaskError(Exception):
    """只包含可公开的固定错误描述。"""


def log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {message}", flush=True)


def ds():
    # n = 'cx2y9z9a29tfqvr1qsq6c7yz99b5jsqt' # v2.2.0 @Womsxd
    salt = "h8w582wxwgqvahcdkpvdhbh2w9casgfl"  # v2.3.0 web @povsister & @journey-ad
    stamp = str(int(time.time()))
    nonce = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    digest = hashlib.md5(f"salt={salt}&t={stamp}&r={nonce}".encode()).hexdigest()
    return f"{stamp},{nonce},{digest}"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Cookie 和签名不得被重定向到其他主机。
        return None


class Client:
    def __init__(self, cookie, act_id, dry):
        self.cookie = cookie
        self.act_id = act_id
        self.dry = dry
        self.device = str(uuid.uuid4()).upper()
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, query=None, body=None):
        if self.dry:
            raise TaskError("预演模式禁止网络请求")
        url = BASE + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=utf-8",
            "Accept-Language": "zh-cn",
            "Origin": "https://webstatic.mihoyo.com",
            "Referer": "https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html?" +
                       urllib.parse.urlencode({"bbs_auth_required": "true", "act_id": self.act_id,
                                               "utm_source": "bbs", "utm_medium": "mys",
                                               "utm_campaign": "icon"}),
            "User-Agent": "Mozilla/5.0 (iPad; CPU OS 14_4 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) miHoYoBBS/2.21.2",
            "x-rpc-device_id": self.device,
            "x-rpc-client_type": "5",
            "x-rpc-app_version": "2.3.0",
            "DS": ds(),
            "Cookie": self.cookie,
        }
        req = urllib.request.Request(url, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     method="POST" if body is not None else "GET")
        try:
            with self.opener.open(req, timeout=15) as response:
                if response.status != 200:
                    raise TaskError("HTTP 状态异常")
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise TaskError("接口响应过大")
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise TaskError(f"HTTP 请求失败（状态 {exc.code}）") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络请求失败或超时") from None
        except (ValueError, UnicodeError):
            raise TaskError("接口未返回有效 JSON") from None
        if not isinstance(result, dict) or type(result.get("retcode")) is not int:
            raise TaskError("接口响应结构变化：缺少业务状态码")
        code = result["retcode"]
        # 不输出服务器 message，避免其中回显凭据。
        if code not in (0, -5003):
            raise TaskError(f"业务请求失败（状态 {code}），请核对登录、验证和接口兼容性")
        if code == -5003 and body is None:
            raise TaskError("查询业务状态异常")
        return result

    def data(self, path, query):
        result = self.request(path, query=query)
        if result["retcode"] != 0 or not isinstance(result.get("data"), dict):
            raise TaskError("接口缺少有效业务数据")
        return result["data"]


def parse_account(line):
    # 仅在首个 | 拆分，保留 Cookie 中的后续分隔符、&、@ 和等号。
    fields = line.split("|", 1)
    if len(fields) != 2:
        raise TaskError("账号格式错误，应为 UID,区服|完整Cookie")
    role, cookie = fields
    parts = role.strip().split(",")
    if len(parts) not in (1, 2) or not re.fullmatch(r"[0-9]{6,12}", parts[0].strip()):
        raise TaskError("UID 格式错误")
    uid = parts[0].strip()
    region = parts[1].strip() if len(parts) == 2 else "cn_gf01"
    if not re.fullmatch(r"cn_[a-z0-9]+", region):
        raise TaskError("区服格式错误，请填写本人原神国服 region")
    cookie = cookie.strip()
    if not cookie or "=" not in cookie or any(ord(c) < 32 or ord(c) > 126 for c in cookie):
        raise TaskError("Cookie 格式错误：应为单行完整请求 Cookie")
    return uid, region, cookie


def run_account(index, line, dry, act_id):
    start = time.monotonic()
    stats = {"account": index, "total": 5, "success": 0, "alreadyComplete": 0,
             "skipped": 0, "failed": 0}
    stages = ["检查配置与角色身份", "查询当前签到状态", "执行每日签到", "验证签到结果", "查询奖励与累计天数"]
    completed = 0
    current_started = start
    try:
        uid, region, cookie = parse_account(line)
        client = Client(cookie, act_id, dry)
        query = {"region": region, "act_id": act_id, "uid": uid}
        signed = False
        total = None
        for number, name in enumerate(stages, 1):
            current_started = time.monotonic()
            log(f"账号 {index} 阶段 {number}/5：{name}")
            if dry:
                if number == 1:
                    stats["success"] += 1
                    log("✅ 本地账号格式有效；预演不验证凭据有效性")
                else:
                    stats["skipped"] += 1
                    log("⏭️ 离线预演跳过接口请求及签到")
            elif number == 1:
                data = client.data("/binding/api/getUserGameRolesByCookie", {"game_biz": "hk4e_cn"})
                roles = data.get("list")
                if not isinstance(roles, list):
                    raise TaskError("角色列表结构变化")
                match = next((r for r in roles if isinstance(r, dict) and
                              str(r.get("game_uid")) == uid and r.get("region") == region), None)
                if match is None:
                    raise TaskError("Cookie 未绑定指定 UID 与区服，停止该账号签到")
                for field in ("nickname", "game_uid"):
                    value = match.get(field)
                    if isinstance(value, (str, int)):
                        # JSON 转义控制字符，保持官方身份内容。
                        log(f"官方身份 {field}：{json.dumps(value, ensure_ascii=False)}")
                stats["success"] += 1
            elif number in (2, 4):
                info = client.data("/event/bbs_sign_reward/info", query)
                if type(info.get("is_sign")) is not bool:
                    raise TaskError("签到状态缺少布尔 is_sign，停止猜测结果")
                signed = info["is_sign"]
                total = info.get("total_sign_day")
                if number == 4 and not signed:
                    raise TaskError("签到后未验证到 is_sign=true")
                log("✅ 已核验当天签到" if signed else "✅ 当天尚未签到")
                stats["success"] += 1
            elif number == 3:
                if signed:
                    stats["alreadyComplete"] += 1
                    log("☑️ 今日已签到")
                else:
                    result = client.request("/event/bbs_sign_reward/sign", body=query)
                    data = result.get("data")
                    if result["retcode"] == 0 and not isinstance(data, dict):
                        raise TaskError("签到响应结构变化，尚未确认成功")
                    if isinstance(data, dict):
                        risk = data.get("risk_code", 0)
                        if risk != 0 or data.get("gt") or data.get("challenge") or data.get("is_risk"):
                            raise TaskError("签到需要人工完成官方验证")
                    if result["retcode"] == -5003:
                        stats["alreadyComplete"] += 1
                        log("☑️ 接口报告已签到，下一阶段复核")
                    else:
                        stats["success"] += 1
                        log("✅ 签到请求已受理，下一阶段复核")
            else:
                home = client.data("/event/bbs_sign_reward/home", {"act_id": act_id})
                awards = home.get("awards")
                if type(total) is not int or total <= 0 or not isinstance(awards, list) or total > len(awards):
                    raise TaskError("奖励或累计签到字段不完整")
                award = awards[total - 1]
                if not isinstance(award, dict) or not isinstance(award.get("name"), str) or type(award.get("cnt")) is not int:
                    raise TaskError("奖励响应结构变化")
                log(f"✅ 累计签到 {total} 天；奖励 {json.dumps(award['name'], ensure_ascii=False)} × {award['cnt']}")
                stats["success"] += 1
            log(f"阶段 {number} 结束，耗时 {time.monotonic() - current_started:.2f} 秒")
            completed += 1
    except TaskError as exc:
        log(f"❌ 账号 {index}：{exc}（阶段耗时 {time.monotonic() - current_started:.2f} 秒）")
        stats["failed"] += 1
        stats["skipped"] += 5 - completed - 1
    except Exception:
        log(f"❌ 账号 {index}：发生未预期的本地或响应结构错误，已隐藏异常内容")
        stats["failed"] += 1
        stats["skipped"] += 5 - completed - 1
    stats["elapsedSeconds"] = round(time.monotonic() - start, 3)
    log(f"账号 {index} 统计：总任务 5，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，"
        f"跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {stats['elapsedSeconds']:.2f} 秒")
    return stats


def selected_notification():
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    if switch != "auto":
        log("⚠️ 通知开关无效，按关闭处理")
        return False
    # listed-only：本任务不在默认通知列表；显式选择后启用。
    selectors = re.split(r"[,;\s]+", os.getenv("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    names = (CATALOG_ID, Path(__file__).name, "米游社自动签到.py", "scripts/米游社自动签到.py",
             "scripts/" + Path(__file__).name)
    return any(pattern and any(fnmatch.fnmatch(name, pattern) for name in names) for pattern in selectors)


def notify_summary(body, dry):
    if not selected_notification():
        return "disabled"
    if dry:
        # notify.py/sendNotify.js 的实际投递可能联网，离线模式不能执行。
        log("⏭️ 预演通知摘要已生成；离线模式禁止外部通知投递")
        return "dry-run"
    # 隔离第三方通知模块的输出，设置总超时，防止泄漏环境和原始响应。
    python_code = '''import importlib.util, sys
path = sys.argv[1]
if path:
    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(sys.argv[2], sys.argv[3])
'''
    roots = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        roots.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]))
    roots.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    commands = [[sys.executable, "-c", python_code, "", TITLE, body]]
    commands += [[sys.executable, "-c", python_code, str(root / "notify.py"), TITLE, body]
                 for root in roots if (root / "notify.py").is_file()]
    js = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
    commands += [["node", "-e", js, str(root / "sendNotify.js"), TITLE, body]
                 for root in roots if (root / "sendNotify.js").is_file()]
    for command in commands:
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=20, check=False)
            if result.returncode == 0:
                return "sent"
        except (OSError, subprocess.TimeoutExpired):
            pass
    log("⚠️ 青龙通知不可用或投递失败，保留业务退出码")
    return "unavailable"


def main():
    started = time.monotonic()
    start_time = datetime.datetime.now().isoformat(timespec="seconds")
    mode = os.getenv("MYS_DRY_RUN", "0").strip().lower()
    dry = mode in TRUE
    lines = [line.strip() for line in os.getenv("MYS_ACCOUNTS", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{start_time}；模式：{'离线预演' if dry else '正式执行'}；账号数：{len(lines)}")
    results = []
    act_id = os.getenv("MYS_ACT_ID", "e202009291139501").strip()
    config_error = (not lines or mode not in TRUE | FALSE or not re.fullmatch(r"[A-Za-z0-9_-]+", act_id))
    if config_error:
        log("❌ 配置错误：请检查 MYS_ACCOUNTS、MYS_DRY_RUN 和 MYS_ACT_ID")
    else:
        for index, line in enumerate(lines, 1):
            results.append(run_account(index, line, dry, act_id))
    failed = len(lines) if config_error else sum(r["failed"] > 0 for r in results)
    succeeded = sum(r["failed"] == 0 for r in results)
    exit_code = 1 if config_error or failed else 0
    status = ("configuration-error" if config_error else "partial-failure" if failed and succeeded
              else "failure" if failed else "dry-run" if dry else "success")
    body = (f"{TITLE}；状态：{status}；账号总数：{len(lines)}；成功数：{succeeded}；失败数：{failed}；"
            f"{'仅验证本地格式，未验证业务成功' if dry else '结果以官方签到状态复核为准'}")
    try:
        notification = notify_summary(body, dry)
    except Exception:
        notification = "unavailable"
        log("⚠️ 通知发生本地错误，保留业务退出码")
    finish = datetime.datetime.now().isoformat(timespec="seconds")
    totals = {key: sum(r[key] for r in results)
              for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "status": status,
               "accounts": len(lines), "succeeded": succeeded, "failed": failed,
               "verifiedAccounts": 0 if dry else succeeded, "tasks": totals, "accountResults": results,
               "startedAt": start_time, "finishedAt": finish,
               "elapsedSeconds": round(time.monotonic() - started, 3),
               "notification": notification, "exitCode": exit_code}
    log("----------------------------------------")
    log(body)
    log(f"子任务统计：总数 {totals['total']}，成功 {totals['success']}，已完成 {totals['alreadyComplete']}，"
        f"跳过 {totals['skipped']}，失败 {totals['failed']}")
    log(f"完成时间：{finish}；总耗时：{summary['elapsedSeconds']:.2f} 秒；通知：{notification}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
