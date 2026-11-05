# -*- coding: utf-8 -*-
# name: AcFun每日签到与可选互动
# cron: 44 2 * * *
"""AcFun 每日任务（建议产品专属发布路径：scripts/ck_acfun_daily.py）。

来源：yuxian158/check dailycheckin_scripts/ck_AcFun.py
维护许可：MIT；保留上游归属。原文件无额外版权声明。

MIT License
Copyright holders: the original upstream authors and contributors.
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

ACFUN_ACCOUNTS：每行“手机号|密码”，仅按第一个“|”分割。
ACF：兼容旧版配置，可使用上述逐行格式，或由 phone/password 对象组成的 JSON。
ACFUN_ACTIONS：sign 默认；可选 like,unlike,share,banana,danmu。
互动须指定 ACFUN_CONTENT_ID；弹幕还须指定视频和分区参数，避免默认操作他人作品。
ACFUN_DRY_RUN=1：完全断网预演，包括通知预览。
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
        _ql_notify_identities = ('f3d4c9cbaf4b9ce7', 'scripts/yuxian158_check_acfun.py', 'yuxian158_check_acfun.py', 'yuxian158_check_acfun')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request


TITLE = "AcFun每日签到与可选互动"
CATALOG_ID = "f3d4c9cbaf4b9ce7"
RELEASE_PATH = "scripts/ck_acfun_daily.py"
UA = "AcFun/6.39.0 (iPhone; iOS 14.3; Scale/2.00)"
OFF = {"0", "false", "no", "off"}
ON = {"1", "true", "yes", "on"}
VALID_ACTIONS = {"sign", "like", "unlike", "share", "banana", "danmu"}
ACTION_NAMES = {
    "sign": "签到",
    "like": "点赞",
    "unlike": "取消点赞",
    "share": "分享任务上报",
    "banana": "投一个香蕉",
    "danmu": "发布弹幕",
}


class SafeError(Exception):
    """可安全展示且不包含响应或凭据的错误。"""


def log(message):
    print("[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), message), flush=True)


def is_dry_run():
    return os.environ.get("ACFUN_DRY_RUN", "0").strip().lower() not in OFF


def request(url, data=None, cookies=None, method="POST", limit=262144, timeout=15):
    """发送不跟随重定向、验证 TLS、限制大小且带超时的 JSON 请求。"""
    if is_dry_run():
        raise SafeError("预演禁止网络请求")
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if cookies:
        headers["Cookie"] = "; ".join("%s=%s" % pair for pair in cookies.items())
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            raw = response.read(limit + 1)
        if len(raw) > limit:
            raise SafeError("响应超过大小限制")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise SafeError("响应结构无效")
        return result
    except SafeError:
        raise
    except Exception:
        raise SafeError("HTTP、超时或响应解析失败") from None


def verified(result, code=0):
    value = result.get("result")
    if type(value) is not int or value != code:
        raise SafeError("接口未返回明确业务成功码")


def public_text():
    """按公共内容策略获取弹幕文案；请求绝不携带账号 Cookie。"""
    fallback = os.environ.get("ACFUN_LOCAL_TEXT", "今天也要开心呀！")

    def normalize(value):
        return " ".join(value.split()) if isinstance(value, str) else ""

    fallback = normalize(fallback)
    if not fallback or len(fallback) > 280:
        fallback = "今天也要开心呀！"
    try:
        data = request(
            "https://v1.hitokoto.cn/?encode=json",
            method="GET",
            timeout=8,
            limit=16384,
        )
        text = normalize(data.get("hitokoto"))
        author = normalize(data.get("from_who"))
        source = normalize(data.get("from"))
        if not text:
            raise SafeError("缺少文本")
        if author and source:
            text += " —— %s《%s》" % (author, source)
        elif source:
            text += " ——《%s》" % source
        elif author:
            text += " —— %s" % author
        if len(text) > 280:
            raise SafeError("文本过长")
        log("弹幕文案：一言获取成功，保留作者和来源")
        return text
    except SafeError:
        log("⚠️ 弹幕文案：远端不可用，采用本地文本")
        return fallback


def notification_selected():
    """实现全局通知开关及目录脚本选择器。"""
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in OFF:
        return False, "已由全局开关关闭"
    if switch not in ON and switch != "auto":
        log("⚠️ QINGLONG_NOTIFY 值无法识别，按 auto 处理")

    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True, "使用默认名单"
    configured = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not configured.strip():
        return False, "脚本名单为空"
    selectors = [item for item in re.split(r"[,;\s]+", configured.strip()) if item]
    actual_path = Path(__file__).as_posix()
    names = {
        CATALOG_ID,
        RELEASE_PATH,
        Path(RELEASE_PATH).name,
        Path(__file__).name,
        actual_path,
    }
    for selector in selectors:
        normalized = selector.replace("\\", "/")
        if normalized == "*":
            return True, "匹配全部脚本"
        if any(fnmatch.fnmatchcase(name, normalized) for name in names):
            return True, "匹配脚本名单"
    return False, "未匹配脚本名单"


def notification_environment():
    """通知进程可继承推送配置，但不可继承 AcFun 账号凭据。"""
    child = os.environ.copy()
    for key in list(child):
        if key == "ACF" or key.startswith("ACFUN_"):
            child.pop(key, None)
    return child


def run_notifier(command, env):
    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=20,
        check=True,
        env=env,
    )


def notify(summary, dry):
    selected, selection_reason = notification_selected()
    if not selected:
        log("⏭️ 通知：" + selection_reason)
        return selection_reason
    body = "账号总数：{accounts}；成功：{success}；失败：{failed}；状态：{status}".format(**summary)
    if dry:
        log("⏭️ 完全断网通知预览：" + body)
        return "断网预览"

    env = notification_environment()
    python_import = [
        sys.executable,
        "-c",
        "import notify,sys; notify.send(sys.argv[1],sys.argv[2])",
        TITLE,
        body,
    ]
    try:
        run_notifier(python_import, env)
        return "已发送"
    except Exception:
        pass

    directory = os.environ.get("QINGLONG_NOTIFY_DIR")
    python_paths = []
    if directory:
        python_paths.append(Path(directory) / "notify.py")
    python_paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    runner = (
        "import importlib.util,sys;"
        "s=importlib.util.spec_from_file_location('ql_notify',sys.argv[1]);"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "m.send(sys.argv[2],sys.argv[3])"
    )
    for path in python_paths:
        if not path.is_file():
            continue
        try:
            run_notifier([sys.executable, "-c", runner, str(path), TITLE, body], env)
            return "已发送"
        except Exception:
            continue

    node = shutil.which("node")
    javascript_paths = []
    if directory:
        javascript_paths.append(Path(directory) / "sendNotify.js")
    javascript_paths.extend((Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")))
    js_runner = (
        "const m=require(process.argv[1]);const f=m.sendNotify||m;"
        "Promise.resolve(f(process.argv[2],process.argv[3]))"
        ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
    )
    if node:
        for path in javascript_paths:
            if not path.is_file():
                continue
            try:
                run_notifier([node, "-e", js_runner, str(path), TITLE, body], env)
                return "已发送"
            except Exception:
                continue
    log("⚠️ 通知不可用或发送失败，保留业务退出码")
    return "不可用或失败"


def parse_accounts():
    """读取规范逐行账号，并兼容旧 ACF JSON/逐行格式。"""
    canonical = os.environ.get("ACFUN_ACCOUNTS", "")
    if canonical.strip():
        return [("line", line) for line in canonical.splitlines() if line.strip()], "ACFUN_ACCOUNTS"

    legacy = os.environ.get("ACF", "")
    if not legacy.strip():
        return [], "ACFUN_ACCOUNTS"
    try:
        parsed = json.loads(legacy)
    except (TypeError, ValueError):
        return [("line", line) for line in legacy.splitlines() if line.strip()], "ACF"
    if isinstance(parsed, dict):
        parsed = [parsed]
    if isinstance(parsed, list):
        return [("object", item) for item in parsed], "ACF"
    return [("invalid", None)], "ACF"


def account_credentials(entry):
    kind, value = entry
    if kind == "line" and isinstance(value, str):
        phone, separator, password = value.partition("|")
        if separator and phone.strip() and password and "\r" not in password and "\n" not in password:
            return phone.strip(), password
    elif kind == "object" and isinstance(value, dict):
        phone, password = value.get("phone"), value.get("password")
        if (
            isinstance(phone, (str, int))
            and not isinstance(phone, bool)
            and str(phone).strip()
            and isinstance(password, str)
            and password
            and "\r" not in password
            and "\n" not in password
        ):
            return str(phone).strip(), password
    return None


def account_run(index, phone, password, actions, dry):
    started = time.monotonic()
    stats = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0, "total": 0}
    cookies, token = {}, None
    label = "账号%d" % index

    def stage(name, callback):
        stats["total"] += 1
        stage_number = stats["total"]
        tick = time.monotonic()
        log("%s 阶段%d %s 开始" % (label, stage_number, name))
        try:
            if dry:
                log("⏭️ 预演：参数有效，不发起请求或修改账号")
                stats["skipped"] += 1
            else:
                callback()
                stats["success"] += 1
                log("✅ %s 成功（明确业务响应）" % name)
            return True
        except SafeError as exc:
            stats["failed"] += 1
            log("❌ %s：%s" % (name, exc))
            return False
        except Exception:
            stats["failed"] += 1
            log("❌ %s：运行异常（详情已脱敏）" % name)
            return False
        finally:
            log("%s 阶段%d %s耗时 %.2f秒" % (label, stage_number, name, time.monotonic() - tick))

    def login():
        nonlocal cookies
        result = request(
            "https://id.app.acfun.cn/rest/app/login/signin",
            {"username": phone, "password": password},
            method="POST",
        )
        pass_token, auth_key = result.get("acPassToken"), result.get("auth_key")
        if (
            not isinstance(pass_token, str)
            or not pass_token
            or not isinstance(auth_key, (str, int))
            or isinstance(auth_key, bool)
            or not str(auth_key)
        ):
            raise SafeError("登录未取得完整凭据")
        if "result" in result:
            verified(result)
        if any(character in str(pass_token) + str(auth_key) for character in "\r\n;"):
            raise SafeError("登录凭据格式无效")
        cookies = {"acPasstoken": pass_token, "auth_key": str(auth_key)}
        for key in ("nickname", "userName", "username", "userId", "uid"):
            identity = result.get(key)
            if not isinstance(identity, (str, int)) or isinstance(identity, bool):
                continue
            normalized = " ".join(str(identity).split())
            if not normalized or normalized == phone or len(normalized) > 120:
                continue
            log("%s 官方身份 %s：%s" % (label, key, json.dumps(normalized, ensure_ascii=False)))

    def get_token():
        nonlocal token
        result = request(
            "https://id.app.acfun.cn/rest/web/token/get",
            {"sid": "acfun.midground.api"},
            cookies,
        )
        token = result.get("acfun.midground.api_st")
        if not isinstance(token, str) or not token or any(character in token for character in "\r\n;"):
            raise SafeError("未取得互动凭据")
        if "result" in result:
            verified(result)

    authenticated = stage("登录", login)
    token_ready = True
    if authenticated and any(action in actions for action in ("like", "unlike")):
        token_ready = stage("获取互动凭据", get_token)

    content = os.environ.get("ACFUN_CONTENT_ID", "")

    def get_video():
        nonlocal content
        result = request(
            "https://www.acfun.cn/rest/pc-direct/rank/channel",
            {"channelId": 0, "rankPeriod": "DAY"},
        )
        if "result" in result:
            verified(result)
        ranking = result.get("rankList")
        if not isinstance(ranking, list) or not ranking or not isinstance(ranking[0], dict):
            raise SafeError("榜单响应缺少视频")
        value = ranking[0].get("contentId")
        if not isinstance(value, (int, str)) or isinstance(value, bool) or not str(value).isdigit():
            raise SafeError("榜单视频编号无效")
        content = str(value)
        log("榜单视频编号：" + content)

    target_ready = True
    if authenticated and content == "rank":
        target_ready = stage("读取每日榜单首个视频", get_video)

    for action in actions:
        prerequisites_ready = authenticated
        if action in ("like", "unlike"):
            prerequisites_ready = prerequisites_ready and token_ready
        if action in ("like", "unlike", "banana", "danmu"):
            prerequisites_ready = prerequisites_ready and target_ready
        if not prerequisites_ready:
            stats["total"] += 1
            stats["skipped"] += 1
            log(
                "⏭️ %s 阶段%d %s：前置步骤失败，耗时 0秒"
                % (label, stats["total"], ACTION_NAMES[action])
            )
            continue

        def perform(selected_action=action):
            if selected_action == "sign":
                verified(request("https://www.acfun.cn/rest/pc-direct/user/signIn", cookies=cookies))
            elif selected_action in ("like", "unlike"):
                endpoint = "add" if selected_action == "like" else "delete"
                verified(
                    request(
                        "https://api.kuaishouzt.com/rest/zt/interact/" + endpoint,
                        {
                            "interactType": 1,
                            "objectId": content,
                            "objectType": 2,
                            "subBiz": "mainApp",
                        },
                        {"acfun.midground.api_st": token, "kpn": "ACFUN_APP"},
                    ),
                    1,
                )
            elif selected_action == "share":
                verified(
                    request(
                        "https://api-ipv6.acfunchina.com/rest/app/task/reportTaskAction"
                        "?taskType=1&market=tencent&product=ACFUN_APP&appMode=0",
                        cookies=cookies,
                        method="GET",
                    )
                )
            elif selected_action == "banana":
                verified(
                    request(
                        "https://www.acfun.cn/rest/pc-direct/banana/throwBanana",
                        {"count": 1, "resourceId": content, "resourceType": 2},
                        cookies,
                    )
                )
            elif selected_action == "danmu":
                verified(
                    request(
                        "https://www.acfun.cn/rest/pc-direct/new-danmaku/add",
                        {
                            "body": public_text(),
                            "color": 16777215,
                            "id": content,
                            "mode": 1,
                            "position": 5019,
                            "size": 25,
                            "subChannelId": os.environ["ACFUN_SUBCHANNEL_ID"],
                            "subChannelName": os.environ["ACFUN_SUBCHANNEL_NAME"],
                            "type": "douga",
                            "videoId": os.environ["ACFUN_VIDEO_ID"],
                        },
                        cookies,
                    )
                )

        stage(ACTION_NAMES[action], perform)

    log("%s 统计：%s；耗时 %.2f秒" % (label, json.dumps(stats, ensure_ascii=False), time.monotonic() - started))
    return stats


def main():
    start = time.monotonic()
    dry = is_dry_run()
    log("========== " + TITLE + " ==========")
    log("开始时间：" + datetime.datetime.now().isoformat(timespec="seconds"))
    log("模式：" + ("完全断网预演" if dry else "正式执行"))
    entries, account_source = parse_accounts()
    log("账号参数来源：%s；账号总数：%d" % (account_source, len(entries)))
    summary = {
        "accounts": len(entries),
        "success": 0,
        "failed": 0,
        "dryRun": dry,
        "status": "",
        "steps": {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0},
    }
    actions = [action.strip() for action in os.environ.get("ACFUN_ACTIONS", "sign").split(",") if action.strip()]
    config_error = (
        not entries
        or not actions
        or len(set(actions)) != len(actions)
        or any(action not in VALID_ACTIONS for action in actions)
    )
    if any(action in actions for action in ("like", "unlike", "banana", "danmu")):
        content = os.environ.get("ACFUN_CONTENT_ID", "")
        config_error |= not (content.isdigit() or content == "rank")
    if "danmu" in actions:
        config_error |= not os.environ.get("ACFUN_CONTENT_ID", "").isdigit()
        config_error |= any(
            not os.environ.get(key, "").strip()
            for key in ("ACFUN_VIDEO_ID", "ACFUN_SUBCHANNEL_ID", "ACFUN_SUBCHANNEL_NAME")
        )
        config_error |= any(
            not os.environ.get(key, "").isdigit()
            for key in ("ACFUN_VIDEO_ID", "ACFUN_SUBCHANNEL_ID")
        )

    if config_error:
        log("❌ 阶段1 参数检查：缺少账号、动作无效或互动目标参数不完整；耗时 0秒")
        summary["failed"] = len(entries)
        summary["steps"]["total"] = 1
        summary["steps"]["failed"] = 1
        summary["status"] = "configuration-error"
        exit_code = 1
    else:
        for index, entry in enumerate(entries, 1):
            credentials = account_credentials(entry)
            if credentials is None:
                log("❌ 账号%d 阶段1 参数检查失败；统计：总任务1，失败1，耗时0秒" % index)
                summary["failed"] += 1
                summary["steps"]["total"] += 1
                summary["steps"]["failed"] += 1
                continue
            stats = account_run(index, credentials[0], credentials[1], actions, dry)
            summary["failed" if stats["failed"] else "success"] += 1
            for key in stats:
                summary["steps"][key] += stats[key]
        exit_code = int(summary["failed"] > 0)
        if exit_code:
            summary["status"] = "partial-failure" if summary["success"] else "failure"
        else:
            summary["status"] = "dry-run" if dry else "success"

    try:
        summary["notification"] = notify(summary, dry)
    except Exception:
        # 通知属于附加能力；任何发现或执行异常都不得覆盖既有业务退出码。
        log("⚠️ 通知流程异常，保留业务退出码")
        summary["notification"] = "不可用或失败"
    summary["elapsedSeconds"] = round(time.monotonic() - start, 2)
    summary["finishTime"] = datetime.datetime.now().isoformat(timespec="seconds")
    log("----------------------------------------")
    log(
        "最终统计：账号总数 {accounts}，成功 {success}，失败 {failed}；子任务 {steps}".format(
            **summary
        )
    )
    log(
        "总耗时：{elapsedSeconds}秒；完成时间：{finishTime}；通知：{notification}；最终状态：{status}".format(
            **summary
        )
    )
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
