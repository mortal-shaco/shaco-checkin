#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 百度贴吧签到
# cron: 28 2 * * *
"""百度贴吧每日签到（青龙维护版）。

SPDX-License-Identifier: GPL-3.0-only
Derived from sudojia/AutoTaskScript src/web/sudojia_tieba.js.
Original author: Telegram@sudojia; https://blog.imzjw.cn; 2024/5/18.
Original function: 百度贴吧每日签到；原计划 33 13 * * *。
Merged src/client/sudojia_tieba_taskSign.js (GPL-3.0), same author/site,
2024/09/07: 百度贴吧APP - 我的 - 成长任务 - 每日签到，成长值、贴贝、等级查询。
Original growth schedule: 19 7 * * *; canonical schedule remains 23 8 * * *.
Source SHA256: 26fa12b3fb1cacad85e936bd8b7fe02d75c53289540a9ca04f6c058abba1bbc3
Growth SHA256: c10c41c1e4249ba49da84bf69d0f4d0920ee5d2a4622253ab012caa42dcfd24e

参数获取：在 tieba.baidu.com 登录后从本人浏览器请求复制 Cookie 或 BDUSS。
成长任务另需本人贴吧 APP 请求 Cookie 中的 CUID；不能用别的账号字段拼接。
TIEBA_COOKIE 优先，兼容 TIE_BA_COOKIE，每个非空行一个账号；不按 &、@ 分隔。
TIEBA_GROWTH_TASKS=1 显式开启成长任务，默认关闭，不增加既有账号默认副作用。
TIEBA_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
TIEBA_VERBOSE=1 显示逐吧详情；TIEBA_DELAY_MS 默认 1200 毫秒，范围 500—10000。
无发帖、评论、分享、兑换、关注或资料修改。
Also incorporates compatible behavior from agluo/ql-script-hub
tieba_checkin.py (MIT), catalog 38ff8ca6c57173b4.
"""

from __future__ import annotations
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = True
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('e608052390d250da', 'scripts/tieba_checkin.py', 'tieba_checkin.py', 'tieba_checkin')
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
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


NAME = "百度贴吧签到"
FORUMS_URL = "https://tieba.baidu.com/mo/q/newmoindex"
SIGN_URL = "https://tieba.baidu.com/sign/add"
MAX_RESPONSE_BYTES = 1_000_000
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
)


class HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """禁止携带 Cookie 跟随到非 HTTPS 地址。"""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        if (urllib.parse.urlsplit(new_url).scheme.lower() != "https"
                or urllib.parse.urlsplit(new_url).hostname != urllib.parse.urlsplit(request.full_url).hostname):
            raise urllib.error.URLError("拒绝把账号凭据重定向到非 HTTPS 地址")
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


OPENER = urllib.request.build_opener(HttpsOnlyRedirectHandler())


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def timeline(message: str, branch: str = "◆") -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')}  {branch} {message}")


def enabled(name: str) -> bool:
    return bool(re.fullmatch(r"1|true|yes|on", os.environ.get(name, ""), re.IGNORECASE))


def notification_enabled() -> bool:
    value = os.environ.get("QINGLONG_NOTIFY")
    return value is None or not bool(re.fullmatch(r"0|false|no|off", value, re.IGNORECASE))


def notify(summary: str) -> str:
    """发送脱敏汇总；通知失败绝不覆盖业务退出码。"""
    if not notification_enabled():
        return "⏭️ 已关闭"
    if enabled("TIEBA_DRY_RUN"):
        timeline("⏭️ 断网预演通知汇总：" + summary)
        return "⏭️ 断网预演：已生成通知汇总，未加载通知组件"
    sender = None
    try:
        from notify import send as sender  # type: ignore
    except Exception:
        roots = [
            os.getenv("QINGLONG_NOTIFY_DIR", ""),
            "/ql/data/scripts",
            "/ql/scripts",
        ]
        for root in filter(None, roots):
            notify_path = Path(root) / "notify.py"
            if not notify_path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("qinglong_notify", notify_path)
            if not spec or not spec.loader:
                continue
            try:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                candidate = getattr(module, "send", None)
                if callable(candidate):
                    sender = candidate
                    break
            except Exception:
                continue
    if not callable(sender):
        print(f"[{NAME}] 未找到青龙 notify.py，已跳过任务总结推送。", file=sys.stderr)
        return "⚠️ 未找到通知组件"
    try:
        sender(NAME, summary)
        return "✅ 已推送"
    except Exception as error:
        print(f"[{NAME}] 通知发送失败：{type(error).__name__}", file=sys.stderr)
        return "⚠️ 推送失败"


def log_banner(mode: str, total: int) -> None:
    print(NAME)
    print("═" * 62)
    print(f"开始时间  {now_text()}")
    print(f"运行模式  {mode}")
    print(f"账号数量  {total}")
    print("═" * 62)


def parse_accounts(value: str | None) -> list[str]:
    """每个非空行是一个账号；整行作为 Cookie，绝不按 & 或 @ 拆账号。"""
    accounts: list[str] = []
    for raw_line in str(value or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        has_bduss = re.search(r"(?:^|;\s*)BDUSS\s*=", line, re.IGNORECASE)
        # 含等号的输入按完整 Cookie 处理，以便在校验阶段识别误填的 Cookie；
        # 仅无等号的单值写法才自动补上 BDUSS 字段名。
        cookie = line if has_bduss or "=" in line else f"BDUSS={line}"
        if cookie not in accounts:
            accounts.append(cookie)
    return accounts


def validate_cookie(cookie: str) -> None:
    match = re.search(r"(?:^|;\s*)BDUSS\s*=\s*([^;\s]+)", cookie, re.IGNORECASE)
    if not match:
        raise ValueError("账号配置中缺少非空 BDUSS")
    if any(char in cookie for char in ("\r", "\n", "\x00")):
        raise ValueError("账号配置包含非法控制字符")


def account_headers(cookie: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookie,
        "Referer": "https://tieba.baidu.com/",
        "User-Agent": USER_AGENT,
    }


def request_json(url: str, headers: dict[str, str], data: bytes | None = None) -> dict[str, Any]:
    if enabled("TIEBA_DRY_RUN"):
        raise RuntimeError("断网预演禁止 HTTP 请求")
    if urllib.parse.urlsplit(url).scheme.lower() != "https":
        raise RuntimeError("拒绝向非 HTTPS 接口发送请求")
    request = urllib.request.Request(url, headers=headers, data=data, method="POST" if data is not None else "GET")
    try:
        with OPENER.open(request, timeout=15) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RuntimeError("接口响应超过 1 MB 上限")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"接口返回 HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError("网络请求失败（详细响应已隐藏）") from error
    except TimeoutError as error:
        raise RuntimeError("网络请求超时") from error
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("接口未返回有效 JSON") from error
    if not isinstance(value, dict):
        raise RuntimeError("接口返回结构异常")
    return value


def get_session(headers: dict[str, str]) -> tuple[str, list[dict[str, Any]], str]:
    data = request_json(FORUMS_URL, headers)
    session = data.get("data")
    if not isinstance(session, dict):
        raise RuntimeError("登录接口返回结构异常")
    tbs = session.get("tbs") or session.get("itb_tbs")
    forums = session.get("like_forum")
    if not tbs:
        raise RuntimeError("Cookie 已失效或账号未登录")
    if not isinstance(forums, list):
        raise RuntimeError("未能读取关注贴吧列表")
    normalized = []
    for forum in forums:
        if not isinstance(forum, dict) or not forum.get("forum_name"):
            continue
        normalized.append(
            {
                "name": str(forum["forum_name"]),
                "signed": str(forum.get("is_sign", "0")) == "1",
            }
        )
    identity_sources = [session]
    identity_sources.extend(
        value for value in session.values() if isinstance(value, dict)
    )
    identity = next(
        (
            str(source.get(key)).strip()
            for source in identity_sources
            for key in ("user_name", "name_show", "un", "username", "nickname", "uname")
            if source.get(key)
        ),
        "",
    )
    if not identity:
        identity = next(
            (
                f"UID {str(source.get(key)).strip()}"
                for source in identity_sources
                for key in ("user_id", "uid")
                if source.get(key)
            ),
            "接口未返回",
        )
    return str(tbs), normalized, identity


def sign_forum(headers: dict[str, str], tbs: str, name: str) -> tuple[str, str]:
    body = urllib.parse.urlencode({"ie": "utf-8", "kw": name, "tbs": tbs}).encode("utf-8")
    sign_headers = {
        **headers,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"https://tieba.baidu.com/f?kw={urllib.parse.quote(name)}&fr=home",
        "X-Requested-With": "XMLHttpRequest",
    }
    data = request_json(SIGN_URL, sign_headers, body)
    message = str(data.get("error") or data.get("error_msg") or "未知错误")
    try:
        code = int(data.get("no", data.get("error_code", -1)))
    except (TypeError, ValueError):
        code = -1
    if code == 0:
        return "success", message
    if code == 1101 or re.search(r"已经签到|已签到", message):
        return "already", message
    return "failed", message


def empty_result() -> dict[str, int]:
    return {"total": 0, "success": 0, "already": 0, "skipped": 0, "failed": 0}


def stage(index: int, title: str, action) -> Any:
    started = time.monotonic()
    timeline(f"[{index}/{7 if enabled('TIEBA_GROWTH_TASKS') else 4}] {title}")
    try:
        result = action()
    except Exception:
        timeline(f"[{index}/{7 if enabled('TIEBA_GROWTH_TASKS') else 4}] {title}失败，用时 {time.monotonic() - started:.1f} 秒", "└─")
        raise
    timeline(f"[{index}/{7 if enabled('TIEBA_GROWTH_TASKS') else 4}] {title}完成，用时 {time.monotonic() - started:.1f} 秒", "└─")
    return result


def run_forums(cookie: str, index: int, dry_run: bool, verbose: bool, delay_seconds: float) -> dict[str, int]:
    result = empty_result()
    stage(1, "参数校验", lambda: validate_cookie(cookie))
    timeline("✓ Cookie 必要字段完整（内容已隐藏）", "└─")

    if dry_run:
        for number, title in ((2, "登录验证"), (3, "读取关注贴吧"), (4, "执行签到")):
            started = time.monotonic()
            timeline(f"[{number}/{7 if enabled('TIEBA_GROWTH_TASKS') else 4}] {title}")
            timeline(f"⏭️ 预演模式：跳过网络请求和账号副作用，用时 {time.monotonic() - started:.1f} 秒", "└─")
        result.update({"total": 1, "skipped": 1})
        return result

    headers = account_headers(cookie)
    tbs, forums, identity = stage(2, "登录验证", lambda: get_session(headers))
    timeline("✓ 登录状态有效，TBS 已获取（内容已隐藏）", "└─")
    timeline(f"✓ 账号身份：{identity}", "└─")

    list_started = time.monotonic()
    timeline(f"[3/{7 if enabled('TIEBA_GROWTH_TASKS') else 4}] 读取关注贴吧")
    signed = [forum for forum in forums if forum["signed"]]
    pending = [forum for forum in forums if not forum["signed"]]
    timeline(
        f"✓ 共 {len(forums)} 个贴吧，已签到 {len(signed)} 个，待签到 {len(pending)} 个，用时 {time.monotonic() - list_started:.1f} 秒",
        "└─",
    )
    if verbose and pending:
        timeline("待签到贴吧：" + "、".join(str(forum["name"]) for forum in pending), "└─")

    action_started = time.monotonic()
    timeline(f"[4/{7 if enabled('TIEBA_GROWTH_TASKS') else 4}] 执行签到")
    result.update({"total": len(forums), "already": len(signed)})
    for position, forum in enumerate(pending, 1):
        name = str(forum["name"])
        try:
            state, message = sign_forum(headers, tbs, name)
            if state == "success":
                result["success"] += 1
                timeline(f"✅ 第 {position}/{len(pending)} 项签到成功" + (f"：{name}" if verbose else ""), "├─")
            elif state == "already":
                result["already"] += 1
                timeline(f"☑️ 第 {position}/{len(pending)} 项今日已完成" + (f"：{name}" if verbose else ""), "├─")
            else:
                result["failed"] += 1
                detail = f"：{name}（接口未确认业务成功）" if verbose else ""
                timeline(f"❌ 第 {position}/{len(pending)} 项签到失败{detail}", "├─")
        except Exception as error:
            result["failed"] += 1
            detail = f"：{name}（{type(error).__name__}）" if verbose else ""
            timeline(f"❌ 第 {position}/{len(pending)} 项请求异常{detail}", "├─")
        if position < len(pending):
            time.sleep(delay_seconds)
    timeline(f"[4/{7 if enabled('TIEBA_GROWTH_TASKS') else 4}] 执行签到完成，用时 {time.monotonic() - action_started:.1f} 秒", "└─")
    return result



GROWTH_URL = "https://tieba.baidu.com/mo/q/usergrowth/showUserGrowth?client_type=2&client_version=12.60.1.2"
GROWTH_SIGN_URL = "https://tieba.baidu.com/mo/q/usergrowth/commitUGTaskInfo"


def cookie_field(cookie: str, field: str) -> str:
    for part in cookie.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key.lower() == field.lower():
            return value.strip()
    return ""


def growth_data(headers: dict[str, str]) -> dict[str, Any]:
    response = request_json(GROWTH_URL, headers)
    # 缺失业务码不能被当作成功；沿用上游 no=0 协议。
    if str(response.get("no")) != "0" or not isinstance(response.get("data"), dict):
        raise RuntimeError("成长查询未确认业务成功或返回结构异常")
    return response["data"]


def growth_identity(data: dict[str, Any]) -> str:
    user = data.get("user")
    if not isinstance(user, dict):
        return "接口未返回"
    for key in ("uname", "nickname", "name_show", "username", "user_name", "uid", "user_id"):
        value = user.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return "接口未返回"


def growth_metrics(data: dict[str, Any]) -> str:
    growth = data.get("growth_info")
    money = data.get("tmoney")
    levels = data.get("level_info")
    if not isinstance(growth, dict) or not isinstance(money, dict) or not isinstance(levels, list):
        raise RuntimeError("成长积分返回结构异常")
    current = next((item for item in levels if isinstance(item, dict)
                    and str(item.get("is_current")) == "1"), None)
    if not current or "value" not in growth or "current" not in money:
        raise RuntimeError("成长积分或当前等级字段缺失")
    try:
        # 与上游一致，以当前等级 growth_value 计算下一等级差值。
        remaining = int(current["next_level_value"]) - int(current["growth_value"])
        level = int(current["level"])
        value = int(growth["value"])
        balance = int(money["current"])
    except (KeyError, ValueError, TypeError):
        raise RuntimeError("成长数值或下一等级字段异常") from None
    return f"当前成长值：{value}；当前贴贝余额：{balance}；当前等级：Lv.{level}；距离下一等级还需{remaining}成长值"


def run_growth(cookie: str, dry_run: bool) -> dict[str, int]:
    result = empty_result()
    if not enabled("TIEBA_GROWTH_TASKS"):
        timeline("⏭️ APP 成长任务：默认关闭，未产生额外副作用", "└─")
        return result
    result["total"] = 2  # 成长签到、签到后的成长信息查询
    started = time.monotonic()
    timeline("[5/7] APP 成长登录与参数校验")
    cuid = cookie_field(cookie, "CUID")
    if not cookie_field(cookie, "BDUSS") or not cuid:
        result["failed"] = 2
        timeline("❌ 成长任务需要同一账号 Cookie 中的非空 BDUSS 和 CUID；未提交请求", "└─")
        return result
    if dry_run:
        result["skipped"] = 2
        for number, title in ((5, "成长登录"), (6, "成长每日签到"), (7, "成长值、贴贝和等级查询")):
            timeline(f"[{number}/7] {title}：⏭️ 断网预演，必要字段通过；跳过请求，用时 0.0 秒", "└─")
        return result
    headers = account_headers(cookie)
    try:
        data = growth_data(headers)
        timeline("✓ 成长账号身份：" + growth_identity(data), "└─")
        tbs = data.get("tbs")
        if not isinstance(tbs, str) or not tbs.strip():
            raise RuntimeError("成长接口缺少 TBS")
        timeline(f"[5/7] 成长登录完成，用时 {time.monotonic()-started:.1f} 秒", "└─")
    except Exception as error:
        result["failed"] = 2
        timeline(f"❌ 成长登录失败：{type(error).__name__}，未提交签到", "└─")
        return result
    started = time.monotonic()
    timeline("[6/7] APP 成长每日签到")
    try:
        body = urllib.parse.urlencode({
            "tbs": tbs, "act_type": "page_sign", "cuid": cuid,
            "client_type": "2", "brand": "OPPO", "model": "OPPO R9s", "zid": "",
            "clientVersion": "12.60.1.2", "clientType": "2",
        }).encode("utf-8")
        response = request_json(GROWTH_SIGN_URL, {
            **headers, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }, body)
        if str(response.get("no")) != "0":
            raise RuntimeError("成长签到接口未明确返回业务码 0")
        result["success"] += 1
        timeline("✅ 成长任务每日签到成功（业务码 0）", "└─")
    except Exception as error:
        result["failed"] += 1
        timeline(f"❌ 成长签到失败：{type(error).__name__}；仍继续查询成长信息", "└─")
    timeline(f"[6/7] 成长签到结束，用时 {time.monotonic()-started:.1f} 秒", "└─")
    started = time.monotonic()
    timeline("[7/7] 成长值、贴贝和等级查询")
    try:
        timeline("✅ " + growth_metrics(growth_data(headers)), "└─")
        result["success"] += 1
    except Exception as error:
        result["failed"] += 1
        timeline(f"❌ 成长信息查询失败：{type(error).__name__}", "└─")
    timeline(f"[7/7] 成长信息查询结束，用时 {time.monotonic()-started:.1f} 秒", "└─")
    return result


def run_account(cookie: str, index: int, dry_run: bool, verbose: bool, delay_seconds: float) -> dict[str, int]:
    validate_cookie(cookie)
    try:
        result = run_forums(cookie, index, dry_run, verbose, delay_seconds)
    except Exception as error:
        timeline(f"❌ 逐吧签到流程失败：{type(error).__name__}；继续独立处理成长任务", "└─")
        result = empty_result()
        result.update(total=1, failed=1)
    growth = run_growth(cookie, dry_run)
    return {key: result[key] + growth[key] for key in result}


def account_failed(result: dict[str, int]) -> bool:
    return result["failed"] > 0


def log_task_summary(
    results: list[dict[str, int]],
    notification: str,
    started: float,
    dry_run: bool,
    status_override: str | None = None,
) -> None:
    totals = {key: sum(item[key] for item in results) for key in empty_result()}
    accounts_failed = sum(account_failed(item) for item in results)
    accounts_success = len(results) - accounts_failed
    elapsed = round(time.monotonic() - started, 1)
    if status_override:
        status = status_override
    elif dry_run and not accounts_failed:
        status = "dry_run"
    elif accounts_failed == 0:
        status = "success"
    elif accounts_success:
        status = "partial_failure"
    else:
        status = "failure"
    labels = {
        "configuration_error": "配置失败",
        "dry_run": "预演通过",
        "success": "全部成功",
        "partial_failure": "部分失败",
        "failure": "执行失败",
    }
    payload = {
        "status": status,
        "mode": "dry-run" if dry_run else "live",
        "accounts_total": len(results),
        "accounts_success": accounts_success,
        "accounts_failed": accounts_failed,
        "tasks_total": totals["total"],
        "tasks_success": totals["success"],
        "tasks_already_complete": totals["already"],
        "tasks_skipped": totals["skipped"],
        "tasks_failed": totals["failed"],
        "elapsed_seconds": elapsed,
        "notification": notification,
    }
    print("\n" + "═" * 24 + " 任务统计 " + "═" * 24)
    print(f"账号统计  总数 {len(results)} │ 成功 {accounts_success} │ 失败 {accounts_failed}")
    print(
        f"子任务结果  总数 {totals['total']} │ 成功 {totals['success']} │ "
        f"已完成 {totals['already']} │ 跳过 {totals['skipped']} │ 失败 {totals['failed']}"
    )
    print(f"总耗时    {elapsed:.1f} 秒")
    print(f"完成时间  {now_text()}")
    print(f"通知状态  {notification}")
    print(f"最终状态  {labels[status]}")
    print("═" * 62)
    print("TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def main() -> int:
    started = time.monotonic()
    dry_run = enabled("TIEBA_DRY_RUN")
    accounts = parse_accounts(os.environ.get("TIEBA_COOKIE") or os.environ.get("TIE_BA_COOKIE"))
    log_banner("断网预演" if dry_run else "正式签到", len(accounts))

    if not accounts:
        message = "配置失败：缺少 TIEBA_COOKIE。请填写 BDUSS 或完整 Cookie，多账号每行一个。"
        timeline(f"❌ {message}")
        print(message, file=sys.stderr)
        notification = notify("配置失败；账号总数 0，成功 0，失败 0。")
        log_task_summary([], notification, started, dry_run, "configuration_error")
        return 2

    verbose = enabled("TIEBA_VERBOSE")
    try:
        delay_ms = int(os.environ.get("TIEBA_DELAY_MS", "1200"))
    except ValueError:
        delay_ms = 1200
        timeline("⚠️ TIEBA_DELAY_MS 格式无效，已使用安全默认值 1200 毫秒")
    delay_ms = min(10_000, max(500, delay_ms))

    results: list[dict[str, int]] = []
    for index, cookie in enumerate(accounts, 1):
        account_started = time.monotonic()
        print()
        timeline(f"账号 {index:02d} 开始执行（{index}/{len(accounts)}）")
        try:
            result = run_account(cookie, index, dry_run, verbose, delay_ms / 1000)
        except Exception as error:
            timeline(f"❌ 账号执行失败：{type(error).__name__}（详细内容已隐藏）", "└─")
            result = empty_result()
            result["total"] = 1
            result["failed"] = 1
        results.append(result)
        if result["failed"]:
            label = "❌ 失败"
        elif dry_run:
            label = "✅ 预演通过"
        else:
            label = "✅ 成功"
        timeline(f"账号 {index:02d}：{label}")
        timeline(
            f"总任务 {result['total']} │ 成功 {result['success']} │ 已完成 {result['already']} │ "
            f"跳过 {result['skipped']} │ 失败 {result['failed']} │ 用时 {time.monotonic() - account_started:.1f} 秒",
            "└─",
        )

    failed_accounts = sum(account_failed(item) for item in results)
    successful_accounts = len(results) - failed_accounts
    totals = {key: sum(item[key] for item in results) for key in empty_result()}
    summary = (
        f"账号总数 {len(results)}，成功 {successful_accounts}，失败 {failed_accounts}；"
        f"子任务总数 {totals['total']}，成功 {totals['success']}，已完成 {totals['already']}，"
        f"跳过 {totals['skipped']}，失败 {totals['failed']}。"
    )
    timeline(f"汇总：{summary}")
    notification = notify(summary)
    log_task_summary(results, notification, started, dry_run)
    return 1 if failed_accounts else 0


if __name__ == "__main__":
    raise SystemExit(main())
