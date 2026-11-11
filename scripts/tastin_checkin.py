# -*- coding: utf-8 -*-
# name: 塔斯汀每日签到
# cron: 4 11 * * *
"""塔斯汀小程序每日签到，Python 3.9+，仅标准库。
来源：syx-love-you/tastin-checkin / tastin_checkin.py，MIT。
原始功能说明：塔斯汀小程序每日自动签到（本地版，仅用 Python 标准库）。

参数获取：在本人微信塔斯汀小程序登录后，用自行授权的 HTTPS 调试工具查看
sss-web.tastientech.com 请求头 user-token。memberPhone 可从
/api/sign/member/signV2/sign 请求体取得，也可留空由会员详情接口获取。
TASTIN_ACCOUNTS 每个非空行一个账号：user-token 或 user-token|memberPhone。
只在第一个 | 分隔，后续内容属于 memberPhone。不得使用 & 或 @ 分隔账号。
可选 TASTIN_SHOP_ID=28416、TASTIN_VERSION=3.78.0、TASTIN_ACTIVITY_ID=74，
TASTIN_STATUS=1 只读查询；默认每天签到，建议北京时间 09:00。
TASTIN_DRY_RUN=1 完全离线预演（包括通知，不导入通知模块）。
支持旧 --token、--phone、--shop-id、--status 参数和同目录 config.json 只读配置；
命令行 token 优先，其次环境账号，再读旧配置。不再自动保存任何凭据。
QINGLONG_NOTIFY=auto/1/0 控制通知；auto 默认选择本任务，可用
QINGLONG_NOTIFY_SCRIPTS 按 catalog-id、文件名、scripts 相对路径或通配符替换。
通知目录可由 QINGLONG_NOTIFY_DIR 指定，通知不可用不改变业务退出码。

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
        _ql_notify_identities = ('e95a788a158b7b85', 'scripts/tastin_checkin.py', 'tastin_checkin.py', 'tastin_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
import contextlib
import fnmatch
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE_URL = "https://sss-web.tastientech.com"
CONFIG_PATH = Path(__file__).resolve().with_name("config.json")
CATALOG_ID = "e95a788a158b7b85"
TITLE = "塔斯汀每日签到"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
SECRETS = []


def enabled(name):
    return os.getenv(name, "").strip().lower() in TRUE


def now():
    return datetime.now(timezone(timedelta(hours=8)))


def safe(value):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return " ".join(text.split())[:400]


def log(text):
    print(f"[{now():%H:%M:%S}] {safe(text)}", flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口重定向，已阻止凭据转发")


def build_headers(cfg: dict) -> dict:
    return {
        "Content-Type": "application/json",
        "user-token": cfg["token"],
        "gray-shop-id": str(cfg.get("shop_id", "28416")),
        "channel": "1",
        "version": str(cfg.get("version", "3.78.0")),
        "xweb_xhr": "1",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 "
            "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
            "MiniProgramEnv/Windows WindowsWechat/WMPF "
            "WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541b36) XWEB/20089"
        ),
        "Referer": "https://servicewechat.com/wx557473f23153a429/537/page-frame.html",
    }



def request(cfg, method, path, body=None):
    if enabled("TASTIN_DRY_RUN"):
        raise TaskError("离线预演禁止 HTTP 请求")
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=build_headers(cfg), method=method,
    )
    try:
        # 不跟随重定向，不把 user-token 转发给其他站点。
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as resp:
            raw = resp.read(1048577)
        if len(raw) > 1048576:
            raise TaskError("响应过大")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise TaskError("响应结构异常")
        return result
    except urllib.error.HTTPError as exc:
        raise TaskError(f"HTTP 错误 {exc.code}，未展示响应内容") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError("网络请求失败或超时") from None
    except (ValueError, UnicodeError):
        raise TaskError("响应不是有效 JSON") from None


def checked(res):
    if res.get("code") != 200:
        raise TaskError("业务接口未确认成功，请核对凭据、活动及网络")
    return res.get("result")


def identity(result):
    if isinstance(result, dict):
        for key in ("nickName", "nickname", "userName", "username", "displayName", "publicUid"):
            if result.get(key) is not None and str(result[key]):
                log(f"账号身份（{key}）：{result[key]}")


def points(cfg):
    result = checked(request(cfg, "POST", "/api/wx/point/myPoint", {}))
    if not isinstance(result, dict) or not isinstance(result.get("point"), (int, float, str)):
        raise TaskError("积分响应字段缺失")
    identity(result)
    log(f"当前积分：{result['point']}")


def member(cfg):
    try:
        result = checked(request(cfg, "GET", "/api/intelligence/member/getMemberDetail/sign"))
        if not isinstance(result, dict):
            raise TaskError("会员详情字段缺失")
        identity(result)
        if not cfg.get("phone"):
            cfg["phone"] = result.get("phone") or result.get("phoneEncrypted") or ""
            if cfg["phone"]:
                SECRETS.append(str(cfg["phone"]))
                log("已自动取得 memberPhone（不显示内容）")
    except TaskError:
        # 原脚本允许手机号为空，由签到接口确认最终业务结果。
        log("⚠️ 会员详情不可用，保留现有 memberPhone；由签到接口确认结果")


def activity_info(cfg, aid):
    result = checked(request(cfg, "POST", "/api/sign/member/signInfoV2", {"activityId": aid}))
    if not isinstance(result, dict) or not isinstance(result.get("activityInfo"), dict):
        raise TaskError("活动响应字段缺失")
    return result["activityInfo"]


def discover(cfg):
    try:
        items = checked(request(cfg, "POST", "/api/minic/shop/intelligence/banner/c/list/sign", {
            "shopId": cfg["shop_id"], "birthday": "", "gender": 0,
            "nickName": None, "phone": cfg.get("phone", ""),
        }))
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("jumpCode") == "SIGN":
                    try:
                        aid = int(json.loads(item.get("jumpPara") or "{}")["activityId"])
                        if aid > 0:
                            log(f"banner 获取签到活动 ID：{aid}")
                            return aid
                    except (ValueError, TypeError, KeyError):
                        continue
    except TaskError:
        log("⚠️ banner 不可用，继续原有活动探测链")
    current = int(time.time() * 1000)
    for aid in range(cfg["activity_id"], cfg["activity_id"] + 30):
        try:
            info = activity_info(cfg, aid)
            if float(info.get("startTime", 0)) <= current <= float(info.get("endTime", 0)):
                log(f"探测到有效活动 ID：{aid}")
                return aid
        except (TaskError, ValueError, TypeError):
            continue
    log(f"⚠️ 未探测到活动，保留原回退 ID：{cfg['activity_id']}，最终由业务接口确认")
    return cfg["activity_id"]


def fmt_ms(value):
    try:
        return datetime.fromtimestamp(float(value) / 1000, now().tzinfo).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OverflowError, OSError):
        return "未知"


def status(cfg, aid):
    info = activity_info(cfg, aid)
    log(f"活动：{info.get('name', '未知')}；每日签到开关：{'开启' if info.get('daySignOpen') else '关闭'}")
    log(f"活动时间：{fmt_ms(info.get('startTime'))} ~ {fmt_ms(info.get('endTime'))}")


def sign(cfg, aid):
    for attempt in range(1, 4):
        try:
            res = request(cfg, "POST", "/api/sign/member/signV2/sign", {
                "activityId": aid, "memberName": "", "memberPhone": cfg.get("phone", ""),
            })
            msg = res.get("msg", "")
            # 仅接受明确的已签到提示，排除包含否定词的错误消息。
            if (isinstance(msg, str) and len(msg) <= 100
                    and re.search(r"今天.*(?:已经签过|已签到)|今日.*(?:已签到|已签过)|^(?:已签到|已经签到|今天已经签过了)[！!。.]?$", msg)
                    and not re.search(r"未|失败|错误|不能|无权|过期", msg)):
                log("☑️ 今天已签到")
                return "alreadyComplete"
            result = checked(res)
            if not isinstance(result, dict) or not result:
                raise TaskError("签到响应缺少成功结果")
            log(f"✅ 签到成功；连续签到 {result.get('continuousNum', '未知')} 天")
            for reward in result.get("rewardInfoList") or []:
                if not isinstance(reward, dict):
                    continue
                log(f"奖励：{reward.get('rewardName', '未知')}")
                for coupon in reward.get("couponInfo") or []:
                    if isinstance(coupon, dict):
                        log(f"优惠券：{coupon.get('name', '未知')}；{coupon.get('couponContent', '')}；{coupon.get('couponTime', '')}")
                if isinstance(reward.get("point"), (int, float)) and reward["point"] > 0:
                    log(f"奖励积分：+{reward['point']}")
            return "success"
        except TaskError:
            log(f"⚠️ 签到尝试 {attempt}/3 未确认成功")
            if attempt < 3:
                log(f"等待 {20 * attempt} 秒后重试同一签到任务")
                time.sleep(20 * attempt)
    raise TaskError("三次签到均未确认成功")


def accounts(args):
    defaults = {"shop_id": os.getenv("TASTIN_SHOP_ID", "28416"),
                "version": os.getenv("TASTIN_VERSION", "3.78.0"),
                "activity_id": os.getenv("TASTIN_ACTIVITY_ID", "74")}
    rows = []
    if args.token:
        rows = [{"token": args.token, "phone": args.phone or ""}]
    elif os.getenv("TASTIN_ACCOUNTS", "").strip():
        for line in os.environ["TASTIN_ACCOUNTS"].splitlines():
            if line.strip():
                token, _, phone = line.strip().partition("|")
                rows.append({"token": token.strip(), "phone": phone})
    elif CONFIG_PATH.exists():
        try:
            row = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if not isinstance(row, dict):
                raise ValueError()
            rows = [row]
        except (OSError, ValueError):
            raise TaskError("旧 config.json 无法读取；建议改用 TASTIN_ACCOUNTS") from None
    if not rows:
        raise TaskError("缺少 TASTIN_ACCOUNTS；请按说明提供本人 user-token")
    output = []
    for row in rows:
        cfg = {**defaults, **row}
        if args.shop_id:
            cfg["shop_id"] = args.shop_id
        if args.phone:
            cfg["phone"] = args.phone
        cfg["token"] = str(cfg.get("token", "")).strip()
        cfg["phone"] = str(cfg.get("phone", ""))
        SECRETS.extend([cfg["token"], cfg["phone"]])
        # 每个账号独立校验，不能使其他有效账号被配置错误阻断。
        try:
            cfg["shop_id"] = int(cfg["shop_id"])
            cfg["activity_id"] = int(cfg["activity_id"])
            if (not cfg["token"] or cfg["shop_id"] <= 0 or cfg["activity_id"] <= 0
                    or any(c in cfg["token"] for c in "\r\n")
                    or any(ord(c) < 32 for c in str(cfg["version"]))):
                raise ValueError()
        except (TypeError, ValueError):
            cfg["invalid"] = True
        output.append(cfg)
    return output


def notify(summary, dry):
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    selection = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    selected = True  # 本任务属于需通知的已列出账号任务。
    if selection is not None:
        p = Path(__file__).resolve().as_posix()
        aliases = [CATALOG_ID, Path(__file__).name, p]
        if "/scripts/" in p:
            aliases.append(p.split("/scripts/", 1)[1])
        selected = any(fnmatch.fnmatch(alias, pattern)
                       for pattern in re.split(r"[,;\s]+", selection.strip()) if pattern
                       for alias in aliases)
    if switch in FALSE or (switch not in TRUE and not selected):
        return "已关闭"
    if dry:
        log("通知阶段：离线预演，仅展示脱敏通知摘要，不加载通知组件")
        log(summary)
        return "离线模拟"
    body = summary
    # 隔离通知模块输出，禁止其调试日志影响单行汇总及泄漏通知配置。
    worker = '''import contextlib, importlib.util, io, sys
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    if sys.argv[1] == "import":
        import notify
    else:
        spec = importlib.util.spec_from_file_location("notify", sys.argv[1])
        notify = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(notify)
    notify.send(sys.argv[2], sys.argv[3])
'''
    paths = ["import"]
    dirs = [os.getenv("QINGLONG_NOTIFY_DIR"), "/ql/data/scripts", "/ql/scripts"]
    paths += [str(Path(d) / "notify.py") for d in dirs if d and (Path(d) / "notify.py").is_file()]
    for path in paths:
        try:
            result = subprocess.run([sys.executable, "-c", worker, path, TITLE, body],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if result.returncode == 0:
                return "已发送"
        except (OSError, subprocess.TimeoutExpired):
            pass
    for directory in dirs:
        if directory and (Path(directory) / "sendNotify.js").is_file():
            js = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
            try:
                result = subprocess.run(["node", "-e", js, str(Path(directory) / "sendNotify.js"), TITLE, body],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                if result.returncode == 0:
                    return "已发送"
            except (OSError, subprocess.TimeoutExpired):
                pass
    return "通知组件不可用或发送失败（保留业务退出码）"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError("命令行参数错误，请使用 --help 查看参数说明")


def main():
    begin = time.monotonic()
    dry = enabled("TASTIN_DRY_RUN")
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "accounts": 0,
               "success": 0, "failed": 0, "results": []}
    log(f"=== {TITLE} ===")
    log(f"开始时间：{now():%Y-%m-%d %H:%M:%S %z}；运行模式：{summary['mode']}")
    config_error = False
    try:
        ap = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        ap.add_argument("--token", help="旧版单账号 user-token，仅使用、不保存")
        ap.add_argument("--phone", help="旧版 memberPhone，仅使用、不保存")
        ap.add_argument("--shop-id", help="门店 ID")
        ap.add_argument("--status", action="store_true", help="只读查询状态")
        args = ap.parse_args()
        rows = accounts(args)
        summary["accounts"] = len(rows)
        log(f"账号数：{len(rows)}")
        for index, cfg in enumerate(rows, 1):
            started = time.monotonic()
            stats = {"account": index, "total": 0, "success": 0, "alreadyComplete": 0,
                     "skipped": 0, "failed": 0}
            readonly = args.status or enabled("TASTIN_STATUS")
            steps = [("参数校验", lambda: None), ("凭据验证及积分查询", lambda: points(cfg)),
                     ("会员详情及手机号获取", lambda: member(cfg)),
                     ("活动发现", lambda: discover(cfg))]
            aid = None
            steps += [("活动状态查询" if readonly else "每日签到",
                       lambda: status(cfg, aid) if readonly else sign(cfg, aid))]
            if not readonly:
                steps.append(("签到后积分查询", lambda: points(cfg)))
            for number, (name, action) in enumerate(steps, 1):
                stats["total"] += 1
                tick = time.monotonic()
                log(f"账号 {index} / 阶段 {number}：{name}")
                try:
                    if cfg.get("invalid"):
                        raise TaskError("账号参数无效，请核对 token、门店及活动 ID")
                    if dry:
                        log("⏭️ DRY_RUN_OK：已校验任务计划，不请求接口、不执行签到、不保存凭据")
                        stats["skipped"] += 1
                    else:
                        result = action()
                        if number == 4:
                            aid = result
                        key = "alreadyComplete" if result == "alreadyComplete" else "success"
                        stats[key] += 1
                        log("☑️ 已完成" if key == "alreadyComplete" else "✅ 阶段完成")
                except TaskError as exc:
                    stats["failed"] += 1
                    log(f"❌ {exc}")
                except Exception:
                    stats["failed"] += 1
                    log("❌ 响应处理异常（不展示原始数据）")
                log(f"阶段耗时：{time.monotonic() - tick:.2f} 秒")
                if stats["failed"]:
                    stats["skipped"] += len(steps) - number
                    stats["total"] += len(steps) - number
                    break
            stats["seconds"] = round(time.monotonic() - started, 2)
            summary["results"].append(stats)
            summary["failed" if stats["failed"] else "success"] += 1
            log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {stats['seconds']} 秒")
    except TaskError as exc:
        config_error = True
        log(f"❌ 配置错误：{exc}")
        log(f"账号数：{summary['accounts']}")
    code = 1 if config_error or summary["failed"] else 0
    summary["status"] = ("configuration-error" if config_error else
                         "partial-failure" if summary["failed"] and summary["success"] else
                         "failure" if summary["failed"] else "dry-run" if dry else "success")
    summary["subtasks"] = {k: sum(r[k] for r in summary["results"])
                           for k in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log("----------------------------------------")
    body = f"账号总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}；状态 {summary['status']}"
    try:
        summary["notification"] = notify(body, dry)
    except Exception:
        summary["notification"] = "通知失败（保留业务退出码）"
    summary["seconds"] = round(time.monotonic() - begin, 2)
    summary["finishedAt"] = now().isoformat(timespec="seconds")
    log(body)
    log(f"子任务统计：{json.dumps(summary['subtasks'], ensure_ascii=False)}")
    log(f"总耗时：{summary['seconds']} 秒；通知状态：{summary['notification']}")
    log(f"完成时间：{summary['finishedAt']}；最终状态：{summary['status']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
