#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: iamtxt 每日签到
# cron: 21 10 * * *
# SPDX-License-Identifier: GPL-3.0
# 来源：yjnu/iamtxt-signin，iamtxtsignin.py
# 上游提交：5e8909a5689f33bbc6dc17c1bbd031dba98e0773；保留 GPL-3.0 授权。
"""iamtxt 独立签到脚本（Python 3，仅标准库）。

IAMTXT_COOKIE：登录 https://www.iamtxt.com/ 后，在浏览器开发者工具的
网络面板中查看本站请求，复制请求头 Cookie 的完整值（不含 Cookie:）。
每个非空行一个账号，Cookie 内的分号、&、@ 均原样保留；兼容旧变量 COOKIE。
IAMTXT_DRY_RUN=1：完全断网，校验配置并模拟任务，不验证登录或签到。
SENDKEY：可选，兼容原脚本的 Server酱推送密钥，从其官方控制台获取。
QINGLONG_NOTIFY：auto（默认）/1 开启，0 关闭；QINGLONG_NOTIFY_SCRIPTS
可用逗号、分号或空白分隔脚本选择器，支持 catalogId、路径和文件名通配符，
设置为空禁用全部。此脚本默认列入通知；通知失败不改变业务退出码。
QINGLONG_NOTIFY_DIR：可选，青龙 notify.py 或 sendNotify.js 所在目录。
每日运行一次；仅签到改变账号状态，无发帖、评论、消费或账号资料修改。
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
        _ql_notify_identities = ('e1245908d22b3902', 'scripts/iamtxtsignin.py', 'iamtxtsignin.py', 'iamtxtsignin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "iamtxt 每日签到"
CATALOG_ID = "e1245908d22b3902"
URL = "https://www.iamtxt.com/e/extend/signin.php"
TIMEOUT = 15
MAX_BYTES = 65536
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不向重定向目标转发 Cookie 或推送密钥。
        return None


def http_post(url, data, headers):
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with opener.open(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise ValueError("接口状态异常")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("接口响应过大")
        return body.decode("utf-8-sig", errors="strict").strip()


def sign(cookie):
    if any(ord(char) < 32 or ord(char) == 127 for char in cookie) or "=" not in cookie:
        return "failure", "Cookie 格式错误，请重新复制本站请求头"
    try:
        text = http_post(URL, b"userid=0", {
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Cookie": cookie,
            "Origin": "https://www.iamtxt.com",
            "Referer": "https://www.iamtxt.com/",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0",
        })
        # 仅识别上游已证实的正文协议，未知正文不视为成功也不打印。
        if text.startswith("阅读愉快"):
            return "success", "签到成功（已核验官方业务响应）"
        if re.match(r"^今天已(?:经)?签", text):
            return "alreadyComplete", "今天已签到（已核验官方业务响应）"
        return "failure", "未收到已知成功标志，请检查 Cookie 或接口是否变更"
    except urllib.error.HTTPError as error:
        return "failure", f"签到 HTTP 状态异常：{error.code}"
    except Exception:
        return "failure", "签到请求失败或响应格式异常（详细响应已抑制）"


def notify_enabled():
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").lower().strip()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True  # 本维护脚本在默认通知列表中。
    selectors = re.split(r"[,;\s]+", os.environ["QINGLONG_NOTIFY_SCRIPTS"].strip())
    path = Path(__file__)
    names = [CATALOG_ID, path.name, "iamtxtsignin.py", "scripts/iamtxtsignin.py"]
    for parent in path.parents:
        if parent.name == "scripts":
            names.append(path.relative_to(parent).as_posix())
            break
    return any(fnmatch.fnmatchcase(name, pattern) for name in names
               for pattern in selectors if pattern)


def qinglong_notify(body):
    """在独立子进程调用宿主通知，隔离其输出并限制执行时间。"""
    paths = []
    custom = os.environ.get("QINGLONG_NOTIFY_DIR")
    if custom:
        paths.append(Path(custom))
    paths.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    targets = []
    try:
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin:
            targets.append(("python", Path(spec.origin)))
    except (ImportError, ValueError, AttributeError):
        pass
    targets.extend(("python", folder / "notify.py") for folder in paths)
    targets.extend(("node", folder / "sendNotify.js") for folder in paths)
    seen = set()
    for runtime, path in targets:
        if not path.is_file() or str(path) in seen:
            continue
        seen.add(str(path))
        if runtime == "python":
            code = (
                "import importlib.util,json,sys; p=json.load(sys.stdin); "
                "sys.path.insert(0,str(__import__('pathlib').Path(sys.argv[1]).parent)); "
                "s=importlib.util.spec_from_file_location('ql_notify',sys.argv[1]); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "r=m.send(p['title'],p['body']); sys.exit(1 if r is False else 0)"
            )
            command = [sys.executable, "-c", code, str(path)]
        else:
            code = (
                "const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));"
                "Promise.resolve(require(process.argv[1]).sendNotify(p.title,p.body))"
                ".then(r=>{if(r===false)process.exitCode=1}).catch(()=>{process.exitCode=1});"
            )
            command = ["node", "-e", code, str(path)]
        try:
            result = subprocess.run(command, input=json.dumps({"title": TITLE, "body": body}),
                                    text=True, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=30, check=False)
            if result.returncode == 0:
                return "已调用青龙通知"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "青龙通知不可用或发送失败"


def serverchan_notify(body, key):
    # 保留 SENDKEY 功能，不再上传原始接口响应。
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return "Server酱密钥格式错误"
    if key.startswith("sctp"):
        match = re.match(r"sctp(\d+)t", key)
        if not match:
            return "Server酱密钥格式错误"
        url = f"https://{match.group(1)}.push.ft07.com/send/{key}.send"
    else:
        url = f"https://sctapi.ftqq.com/{key}.send"
    try:
        result = json.loads(http_post(url, json.dumps({"title": TITLE, "desp": body}).encode(),
                                     {"Content-Type": "application/json;charset=utf-8"}))
        code = result.get("code") if isinstance(result, dict) else None
        if type(code) in (int, str) and str(code) == "0":
            return "Server酱发送成功"
    except Exception:
        pass
    return "Server酱发送失败"


def main():
    started = time.monotonic()
    start_time = time.strftime("%Y-%m-%d %H:%M:%S")
    dry_value = os.environ.get("IAMTXT_DRY_RUN", "0").lower().strip()
    dry = dry_value in TRUE
    value = os.environ.get("IAMTXT_COOKIE") or os.environ.get("COOKIE", "")
    accounts = [line.strip() for line in value.splitlines() if line.strip()]
    errors = []
    if dry_value not in TRUE | FALSE:
        errors.append("IAMTXT_DRY_RUN 必须是 1 或 0 等布尔值")
    if not accounts:
        errors.append("未配置 IAMTXT_COOKIE（兼容 COOKIE），每个非空行一个账号")
    notify_switch = os.environ.get("QINGLONG_NOTIFY", "auto").lower().strip()
    if notify_switch not in TRUE | FALSE | {"auto"}:
        errors.append("QINGLONG_NOTIFY 必须是 auto 或布尔值")
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{start_time} | 模式：{'断网预演' if dry else '正式执行'} | 账号数：{len(accounts)}")
    log("阶段 1/3 配置检查")
    for error in errors:
        log(f"❌ {error}")
    log(f"阶段 1/3 配置检查结束：{'失败' if errors else '通过'} | 耗时 {time.monotonic() - started:.3f} 秒")
    results = []
    if not errors:
        for number, cookie in enumerate(accounts, 1):
            tick = time.monotonic()
            log(f"账号 {number} | 阶段 2/3 每日签到 开始")
            if any(ord(char) < 32 or ord(char) == 127 for char in cookie) or "=" not in cookie:
                state, message = "failure", "Cookie 格式错误"
            elif dry:
                state, message = "skipped", "DRY_RUN_OK：已校验配置，未发送任何网络请求，未验证签到"
            else:
                state, message = sign(cookie)
            elapsed = round(time.monotonic() - tick, 3)
            results.append({"account": number, "status": state, "durationSeconds": elapsed})
            log(f"账号 {number} | {message} | 阶段耗时 {elapsed} 秒")
            counts = {key: int(state == key) for key in ("success", "alreadyComplete", "skipped", "failure")}
            log(f"账号 {number} 统计：总任务 1，成功 {counts['success']}，已完成 {counts['alreadyComplete']}，"
                f"跳过 {counts['skipped']}，失败 {counts['failure']}，耗时 {elapsed} 秒")
    failed = sum(row["status"] == "failure" for row in results)
    verified = sum(row["status"] in ("success", "alreadyComplete") for row in results)
    skipped = sum(row["status"] == "skipped" for row in results)
    status = ("configuration-error" if errors else "partial-failure" if failed and (verified or skipped)
              else "failure" if failed else "dry-run" if dry else "success")
    exit_code = 2 if errors else 1 if failed else 0
    body = (f"{TITLE}：{status}；账号总数 {len(accounts)}，成功 {verified}，"
            f"失败 {failed}，跳过 {skipped}，配置错误 {len(errors)}。")
    log("阶段 3/3 脱敏汇总与通知")
    notify_started = time.monotonic()
    notifications = []
    if dry:
        notifications.append("断网预演：已生成脱敏通知，跳过外部发送")
    elif not notify_enabled():
        notifications.append("通知已由全局开关或选择器关闭")
    else:
        try:
            notifications.append(qinglong_notify(body))
        except Exception:
            notifications.append("青龙通知异常（已抑制详细输出）")
        key = os.environ.get("SENDKEY", "").strip()
        if key:
            notifications.append(serverchan_notify(body, key))
    log(f"阶段 3/3 脱敏汇总与通知结束 | 耗时 {time.monotonic() - notify_started:.3f} 秒")
    log("----------------------------------------")
    log(body)
    log(f"子任务：成功 {sum(r['status'] == 'success' for r in results)}，"
        f"已完成 {sum(r['status'] == 'alreadyComplete' for r in results)}，跳过 {skipped}，失败 {failed}")
    log("通知状态：" + "；".join(notifications))
    log(f"完成时间：{time.strftime('%Y-%m-%d %H:%M:%S')} | 总耗时 {time.monotonic() - started:.3f} 秒 | 最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({
        "task": "iamtxt", "status": status, "mode": "dry-run" if dry else "live",
        "accounts": len(accounts), "success": verified, "failure": failed, "skipped": skipped,
        "configurationErrors": len(errors), "results": results, "notifications": notifications,
        "exitCode": exit_code, "durationSeconds": round(time.monotonic() - started, 3),
    }, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
