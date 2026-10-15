#!/usr/bin/env python3
# name: 快手奖励任务
# cron: 22 8,14,20 * * *
"""Read-only Kuaishou reward status for Qinglong.

name: 快手奖励任务
cron: 22 8,14,20 * * *
new Env('快手奖励任务')
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
import time
from datetime import datetime
from pathlib import Path

ENDPOINT = "https://api.kuaishouzt.com/rest/zt/appsupport/yoda/accelerate/info"
MAX_RESPONSE_BYTES = 1024 * 1024
FALSE_VALUES = {"0", "false", "no", "off"}
NOTIFY_TITLE = "快手奖励任务"
VISIBLE_KEYS = {
    "balance", "cash", "coin", "coins", "signed", "signStatus", "taskStatus",
    "todayCoin", "totalCash", "totalCoin", "userName",
}


def enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def emit(event: str, **fields: object) -> None:
    print(json.dumps({"event": event, **fields}, ensure_ascii=False, separators=(",", ":")))


def notification_enabled() -> bool:
    return os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() not in FALSE_VALUES


def load_notify_sender():
    try:
        from notify import send  # type: ignore

        return send
    except (ImportError, AttributeError):
        pass
    candidates: list[Path] = []
    custom_dir = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if custom_dir:
        candidates.append(Path(custom_dir) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_kuaishou_notify", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                sender = getattr(module, "send", None)
                if callable(sender):
                    return sender
        except Exception:
            continue
    return None


def notify_summary(body: str, dry_run: bool) -> str:
    if not notification_enabled():
        return "⏭️ 已关闭"
    if dry_run:
        return "⏭️ 预演不推送"
    sender = load_notify_sender()
    if sender is None:
        print("未找到青龙 notify.py，已跳过任务总结推送", file=sys.stderr)
        return "⚠️ 未找到通知组件"
    try:
        sender(NOTIFY_TITLE, body)
        return "✅ 青龙任务总结已推送"
    except Exception:
        print("青龙任务总结推送失败，不改变任务执行结果", file=sys.stderr)
        return "⚠️ 推送失败"


def log_banner(mode: str, total: int) -> None:
    print("快手奖励任务")
    print("═" * 62)
    print(f"运行模式  {mode}")
    print(f"账号数量  {total}")
    print(f"开始时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)


def timeline(message: str, branch: str = "◆") -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')}  {branch} {message}")


def log_task_summary(total: int, failed: int, notification: str, started: float, mode: str, status_override: str | None = None) -> None:
    elapsed = round(time.monotonic() - started, 1)
    status = status_override or ("dry_run" if mode == "dry-run" and not failed else ("success" if not failed else "partial_failure"))
    label = "配置失败" if status == "configuration_error" else ("预演通过" if status == "dry_run" else ("全部成功" if status == "success" else "部分失败"))
    payload = {"status": status, "mode": mode, "accounts_total": total, "accounts_success": total - failed, "accounts_failed": failed, "elapsed_seconds": elapsed, "notification": notification}
    timeline("生成任务总结")
    timeline(f"通知状态：{notification}", "└─")
    print("\n" + "═" * 24 + " 任务统计 " + "═" * 24)
    print(f"最终状态  {label}")
    print(f"账号统计  总数 {total} │ 成功 {total - failed} │ 失败 {failed}")
    print(f"任务统计  总数 {total} │ 成功 {total - failed} │ 已完成 0 │ 跳过 0 │ 失败 {failed}")
    print(f"通知状态  {notification}")
    print(f"总耗时    {elapsed:.1f} 秒")
    print(f"完成时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)
    print("TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def accounts() -> list[str]:
    return [line.strip() for line in os.environ.get("KUAISHOU_COOKIE", "").splitlines() if line.strip()]


def validate_cookie(cookie: str) -> None:
    if "kuaishou.api_st=" not in cookie:
        raise ValueError("Cookie 缺少 kuaishou.api_st")


def visible_status(value: object) -> dict[str, object]:
    result: dict[str, object] = {}

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                if key in VISIBLE_KEYS and isinstance(item, (str, int, float, bool, type(None))):
                    result.setdefault(key, item)
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(node, list):
            for item in node[:20]:
                visit(item)

    visit(value)
    return result


def business_error(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    code = payload.get("result", payload.get("code"))
    if code in (None, 0, 1, 200, "0", "1", "200", "success", "SUCCESS"):
        return None
    message = payload.get("error_msg", payload.get("message", "业务接口返回失败"))
    return f"{message} (code={code})"


def query(cookie: str) -> dict[str, object]:
    request = urllib.request.Request(
        ENDPOINT,
        data=b"",
        method="POST",
        headers={
            "Cookie": cookie,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Kwai/12 Qinglong read-only status",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"HTTP {response.status}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("响应超过 1 MiB 限制")
    payload = json.loads(raw.decode("utf-8"))
    error = business_error(payload)
    if error:
        raise RuntimeError(error)
    return visible_status(payload)


def main() -> int:
    started = time.monotonic()
    values = accounts()
    dry_run = enabled(os.environ.get("KUAISHOU_DRY_RUN"))
    mode = "dry-run" if dry_run else "live"
    log_banner("预演" if dry_run else "正式执行", len(values))
    if not values:
        emit("fatal", error="KUAISHOU_COOKIE 未配置；多账号必须每行一个")
        notification = notify_summary("配置失败：KUAISHOU_COOKIE 未配置", dry_run)
        log_task_summary(0, 0, notification, started, mode, "configuration_error")
        return 2
    failed = 0
    for index, cookie in enumerate(values, start=1):
        account_started = time.monotonic()
        account_ok = False
        print()
        timeline(f"账号 {index:02d}：[1/3] 参数校验（{index}/{len(values)}）")
        try:
            validate_cookie(cookie)
            timeline(f"账号 {index:02d}：✓ Cookie 必要字段完整（内容已隐藏）", "└─")
            timeline(f"账号 {index:02d}：[2/3] 查询奖励状态")
            if dry_run:
                timeline(f"账号 {index:02d}：↳ 预演模式，未发送网络请求", "└─")
                emit("account", account=index, ok=True, result="dry-run-no-network")
            else:
                status = query(cookie)
                timeline(f"账号 {index:02d}：✓ 奖励状态读取成功", "└─")
                emit("account", account=index, ok=True, result="status-read", status=status)
            timeline(f"账号 {index:02d}：[3/3] 生成账号结果")
            timeline(f"账号 {index:02d}：✓ 账号任务完成", "└─")
            account_ok = True
        except (ValueError, RuntimeError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as error:
            failed += 1
            timeline(f"账号 {index:02d}：✗ 查询失败：{error}", "└─")
            emit("account", account=index, ok=False, error=str(error))
        timeline(f"账号 {index:02d}：{'✓ 成功' if account_ok else '✗ 失败'}")
        timeline(f"总任务 1 │ 成功 {1 if account_ok else 0} │ 已完成 0 │ 跳过 0 │ 失败 {0 if account_ok else 1} │ 用时 {time.monotonic() - account_started:.1f} 秒", "└─")
    emit("summary", mode=mode, total=len(values), failed=failed)
    notification = notify_summary(
        f"模式：{mode}；账号：{len(values)}；成功：{len(values) - failed}；失败：{failed}",
        dry_run,
    )
    log_task_summary(len(values), failed, notification, started, mode)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
