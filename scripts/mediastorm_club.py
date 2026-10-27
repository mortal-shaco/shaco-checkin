#!/usr/bin/env python3
# name: 影视飓风会员签到
# cron: 3 9 * * *
# License: MIT
# Upstream: Transmigration-zhou/mediastorm-club-checkin, checkin.py
# Commit: d89811f1122aa4d0a441c4cf5340df50a80f15fc
"""影视飓风会员签到（Python 3.9+，仅使用标准库）。

推荐环境变量 MEDIASTORM_ACCOUNTS：每个非空行一个账号，格式 access_token|sid，
仅按第一个 | 分割，sid 后续字符原样保留。兼容单账号 ACCESS_TOKEN + SESSION_ID；
组合变量一旦设置，优先使用且不回退旧参数。兼容脚本同目录 .env 中的凭据，
仅在进程环境未设置对应项时读取，保留上游行尾空格加 # 注释处理。
获取参数：登录微信的影视飓风会员小程序，在本人授权的 HTTPS 抓包工具中查看
checkinV2.json 请求；access_token 在查询参数中，sid 在 Extra-Data JSON 请求头中。
二者须来自同一账号同一次会话，不要使用公开示例或分享抓包；失效时重新登录获取。
原输入未提供 cron，建议每天北京时间 09:00 运行，元数据使用青龙面板时区。
MEDIASTORM_DRY_RUN=1：校验参数和构造请求，不联网、不签到、不调用通知模块。
QINGLONG_NOTIFY=auto 按 QINGLONG_NOTIFY_SCRIPTS 选择；1 强制启用，0 关闭。
选择器支持目录路径、文件名、通配符和目录编号；设置空串关闭全部通知。
可选 QINGLONG_NOTIFY_DIR 指向青龙通知脚本目录；通知失败不改变业务退出码。
此脚本只签到，不写入 .env、不刷新凭据、不更新 GitHub Secrets、不执行安装。

MIT License
Original source and attribution: Transmigration-zhou/mediastorm-club-checkin.
The supplied source files contained no additional copyright notices.

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
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('e559f6b278de9d78', 'scripts/mediastorm_club.py', 'mediastorm_club.py', 'mediastorm_club')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import json
import os
from pathlib import Path
import random
import re
import shutil
import string
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

CHECKIN_URL = "https://h5.youzan.com/wscump/checkin/checkinV2.json"
APP_ID = "wx92782ef90ebc836d"
KDT_ID = "149536603"
CHECKIN_ID = "6287727"
TITLE = "影视飓风会员签到"
CATALOG_ID = "e559f6b278de9d78"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
    "MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) "
    "UnifiedPCMacWechat(0xf2641702) XWEB/18788"
)
ENABLED = {"1", "true", "yes", "on"}
DISABLED = {"0", "false", "no", "off"}
MAX_RESPONSE_BYTES = 262144


class TaskError(Exception):
    """仅携带预定义的安全错误文本。"""


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def build_extra_data(sid):
    ftime = int(time.time() * 1000)
    uuid = "".join(random.choices(string.ascii_letters, k=15)) + str(ftime)
    return json.dumps({"is_weapp": 1, "sid": sid, "version": "2.226.7.101",
                       "client": "weapp", "bizEnv": "wsc", "uuid": uuid,
                       "ftime": ftime}, separators=(",", ":"), ensure_ascii=True)


def build_headers(sid):
    return {"User-Agent": USER_AGENT, "xweb_xhr": "1",
            "Content-Type": "application/json",
            "Referer": "https://servicewechat.com/wx92782ef90ebc836d/17/page-frame.html",
            "Extra-Data": build_extra_data(sid)}


def build_request(access_token, sid):
    params = {"checkinId": CHECKIN_ID, "app_id": APP_ID, "kdt_id": KDT_ID,
              "access_token": access_token}
    return urllib.request.Request(CHECKIN_URL + "?" + urllib.parse.urlencode(params),
                                  headers=build_headers(sid), method="GET")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 防止查询凭据和会话头随重定向发送至其他目标。
        raise TaskError("拒绝接口重定向，请核对服务端接口")


def request_json(request):
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=30) as response:
            if response.status != 200:
                raise TaskError("签到接口 HTTP 状态异常")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise TaskError("签到响应超过大小限制")
        body = json.loads(payload.decode("utf-8"))
        if not isinstance(body, dict):
            raise TaskError("签到响应结构异常")
        return body
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError(f"签到接口 HTTP 错误（{exc.code}），未自动重试") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError("签到网络失败或超时，结果未核实，未自动重试") from None
    except (ValueError, UnicodeError):
        raise TaskError("签到响应不是有效 JSON") from None


def safe_text(value, secrets):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    # 标题和身份值不接受 Cookie、令牌、会话或设备字段。
    if re.search(r"(?i)(cookie|token|session|device|imei|\bsid\b)\s*[:=]", text):
        return "[敏感字段已隐藏]"
    return " ".join(text.split())


def show_identity(body, secrets):
    data = body.get("data")
    containers = [body]
    if isinstance(data, dict):
        containers.append(data)
        for key in ("user", "userInfo", "user_info"):
            if isinstance(data.get(key), dict):
                containers.append(data[key])
    for item in containers:
        for key in ("nickname", "nickName", "username", "displayName", "display_name", "uid", "public_uid"):
            identity = safe_text(item.get(key), secrets)
            if identity:
                log(f"官方账号身份（{key}）：{identity}")
                return


def do_checkin(access_token, sid, secrets=()):
    body = request_json(build_request(access_token, sid))
    secrets = tuple(secrets) + (access_token, sid)
    show_identity(body, secrets)
    code = body.get("code")
    if type(code) is int and code == 1000030071:
        log("☑️ 今日已签到，跳过")
        return "already_complete"
    data = body.get("data")
    if type(code) is not int or code != 0 or not isinstance(data, dict) or data.get("success") is not True:
        suffix = f"（业务码 {code}）" if type(code) is int else "（业务码缺失或格式异常）"
        raise TaskError("签到失败" + suffix)
    log("✅ 签到成功！")
    awards = data.get("list")
    if isinstance(awards, list):
        for award in awards:
            infos = award.get("infos") if isinstance(award, dict) else None
            title = safe_text(infos.get("title"), secrets) if isinstance(infos, dict) else ""
            log("签到成功！获得: " + (title or "奖励"))
    return "success"


def _load_env(env_file=""):
    path = Path(env_file) if env_file else Path(__file__).resolve().parent / ".env"
    try:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key.strip() in {"MEDIASTORM_ACCOUNTS", "ACCESS_TOKEN", "SESSION_ID"}:
                    os.environ.setdefault(key.strip(), value.split(" #")[0].strip())
    except (OSError, UnicodeError):
        raise TaskError("无法读取本地 .env 凭据文件") from None


def load_accounts():
    if "MEDIASTORM_ACCOUNTS" in os.environ:
        lines = [line.strip() for line in os.environ["MEDIASTORM_ACCOUNTS"].splitlines() if line.strip()]
        if not lines:
            raise TaskError("MEDIASTORM_ACCOUNTS 未包含任何账号")
        return [tuple(line.split("|", 1)) if "|" in line else (line, "") for line in lines]
    token = os.environ.get("ACCESS_TOKEN", "").strip()
    sid = os.environ.get("SESSION_ID", "").strip()
    if not token and not sid:
        raise TaskError("缺少 MEDIASTORM_ACCOUNTS，或旧参数 ACCESS_TOKEN 与 SESSION_ID")
    return [(token, sid)]


def validate_account(account):
    token, sid = account
    if not token or not sid or token != token.strip() or sid != sid.strip():
        raise TaskError("账号格式错误：每行应为同一账号的 access_token|sid，两项均不能为空或带首尾空格")
    if any(ord(c) < 32 or ord(c) == 127 for c in token + sid):
        raise TaskError("账号凭据含不支持的控制字符")


def notification_selected():
    mode = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if mode in DISABLED:
        return False
    if mode not in ENABLED | {"auto"}:
        return False
    selection = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selection is None:
        return mode in ENABLED
    path = Path(__file__).resolve()
    aliases = {CATALOG_ID, path.name, "candidate.py", "checkin.py", path.as_posix()}
    for parent in path.parents:
        aliases.add(path.relative_to(parent).as_posix())
    selectors = re.split(r"[,;\s]+", selection.strip())
    return any(selector and any(fnmatch.fnmatchcase(alias, selector) for alias in aliases)
               for selector in selectors)


def send_notification(summary, dry_run):
    selected = notification_selected()
    if dry_run:
        log("⏭️ 通知预演：已生成脱敏摘要；断网模式不加载或调用通知模块")
        return "dry-run"
    if not selected:
        log("⏭️ 通知未启用：QINGLONG_NOTIFY 或脚本选择列表未命中")
        return "disabled"
    body = (f"状态：{summary['status']}；账号总数：{summary['accounts']}；"
            f"成功：{summary['succeeded']}；失败：{summary['failed']}；"
            f"配置错误：{summary['configuration_errors']}；已签到：{summary['already_complete']}")
    # 在独立子进程调用可选青龙通知组件；不传递业务凭据、不输出组件原始日志。
    child_env = {k: v for k, v in os.environ.items()
                 if k not in {"MEDIASTORM_ACCOUNTS", "ACCESS_TOKEN", "SESSION_ID"}}
    roots = []
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        roots.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]))
    roots.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    py_runner = (
        "import importlib.util,os,sys; "
        "sys.path.insert(0,os.path.dirname(os.path.abspath(sys.argv[1]))); "
        "s=importlib.util.spec_from_file_location('ql_notify',sys.argv[1]); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "m.send(sys.argv[2],sys.argv[3])"
    )
    commands = [[sys.executable, "-c",
                 "import sys; sys.path.insert(0,sys.argv[1]); from notify import send; send(sys.argv[2],sys.argv[3])",
                 str(Path(__file__).resolve().parent), TITLE, body]]
    for root in roots:
        if (root / "notify.py").is_file():
            commands.append([sys.executable, "-c", py_runner, str(root / "notify.py"), TITLE, body])
    node = shutil.which("node")
    if node:
        for root in roots:
            if (root / "sendNotify.js").is_file():
                commands.append([node, "-e", "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                                 str((root / "sendNotify.js").resolve()), TITLE, body])
    for command in commands:
        try:
            result = subprocess.run(command, env=child_env, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=20, check=False)
            if result.returncode == 0:
                log("✅ 脱敏任务摘要通知已发送")
                return "sent"
        except (OSError, subprocess.TimeoutExpired):
            continue
    log("⚠️ 青龙通知组件不可用或发送失败，保留业务退出码")
    return "unavailable-or-failed"


def main():
    started = time.monotonic()
    dry_run = os.environ.get("MEDIASTORM_DRY_RUN", "0").strip().lower() in ENABLED
    print("=" * 50)
    log(f"任务：{TITLE}；开始时间：{datetime.now().isoformat(timespec='seconds')}")
    log("运行模式：" + ("断网预演" if dry_run else "正式签到"))
    results = []
    config_errors = 0
    accounts = []
    try:
        _load_env()
        accounts = load_accounts()
    except TaskError as exc:
        config_errors = 1
        log(f"❌ 配置错误：{exc}")
    except Exception:
        config_errors = 1
        log("❌ 配置解析异常（详情已隐藏）")
    log(f"账号数量：{len(accounts)}")
    all_secrets = tuple(value for account in accounts for value in account)
    for index, account in enumerate(accounts, 1):
        account_start = time.monotonic()
        steps = {"total": 2, "success": 0, "already_complete": 0, "skipped": 0, "failed": 0}
        stage = 1
        stage_start = time.monotonic()
        status = "failure"
        try:
            log(f"账号 {index} / 阶段 1：参数检查")
            validate_account(account)
            steps["success"] += 1
            log(f"✅ 参数完整；阶段 1 耗时 {time.monotonic() - stage_start:.3f} 秒")
            stage = 2
            stage_start = time.monotonic()
            log(f"账号 {index} / 阶段 2：" + ("构造签到请求" if dry_run else "签到请求"))
            if dry_run:
                build_request(*account)
                steps["skipped"] += 1
                status = "dry-run"
                log("✅ DRY_RUN_OK：请求构造通过，未联网、未执行签到")
            else:
                status = do_checkin(*account, secrets=all_secrets)
                steps["already_complete" if status == "already_complete" else "success"] += 1
        except TaskError as exc:
            steps["failed"] += 1
            if stage == 1:
                steps["skipped"] += 1
            log(f"❌ {exc}")
        except Exception:
            steps["failed"] += 1
            if stage == 1:
                steps["skipped"] += 1
            log("❌ 执行异常，详情已隐藏；账号未通过验证")
        log(f"阶段 {stage} 结束；耗时 {time.monotonic() - stage_start:.3f} 秒")
        elapsed = round(time.monotonic() - account_start, 3)
        log(f"账号 {index} 统计：总任务 {steps['total']}，成功 {steps['success']}，"
            f"已完成 {steps['already_complete']}，跳过 {steps['skipped']}，失败 {steps['failed']}；"
            f"耗时 {elapsed:.3f} 秒；状态 {status}")
        results.append({"account": index, "status": status, "steps": steps, "elapsed_seconds": elapsed})
    failed = sum(result["status"] == "failure" for result in results)
    succeeded = sum(result["status"] in {"success", "already_complete"} for result in results)
    exit_code = int(bool(config_errors or failed))
    status = ("configuration-error" if config_errors else "partial-failure" if failed and failed < len(results)
              else "failure" if failed else "dry-run" if dry_run else "success")
    summary = {"task": TITLE, "status": status, "mode": "dry-run" if dry_run else "live",
               "accounts": len(accounts), "succeeded": succeeded, "failed": failed,
               "already_complete": sum(r["status"] == "already_complete" for r in results),
               "dry_run_accounts": sum(r["status"] == "dry-run" for r in results),
               "configuration_errors": config_errors, "results": results, "exit_code": exit_code}
    try:
        summary["notification"] = send_notification(summary, dry_run)
    except Exception:
        log("⚠️ 通知处理异常，保留业务退出码")
        summary["notification"] = "unavailable-or-failed"
    summary["elapsed_seconds"] = round(time.monotonic() - started, 3)
    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    print("-" * 50)
    totals = {key: sum(r["steps"][key] for r in results)
              for key in ("total", "success", "already_complete", "skipped", "failed")}
    summary["steps"] = totals
    log(f"最终账号统计：总数 {len(accounts)}，成功 {succeeded}，预演 {summary['dry_run_accounts']}，失败 {failed}，配置错误 {config_errors}")
    log(f"子任务统计：总数 {totals['total']}，成功 {totals['success']}，已完成 {totals['already_complete']}，跳过 {totals['skipped']}，失败 {totals['failed']}")
    log(f"总耗时：{summary['elapsed_seconds']:.3f} 秒；完成时间：{summary['finished_at']}；通知状态：{summary['notification']}")
    log(f"最终状态：{status}；退出码：{exit_code}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
