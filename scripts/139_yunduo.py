#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 139云盘云朵任务
# cron: 11 0 * * *
# new Env('139云盘云朵任务')
# 来源: deeplee/personal-scripts / 139_yunduo.py
# 上游与维护版本许可: MIT
"""
139云盘(中国移动云盘) 云朵任务自动执行脚本
适配青龙面板,纯 Python 标准库实现,无需 pip 安装任何依赖。

维护说明：上传、回收站清理和未知任务尝试默认关闭，需明确启用。
预演只检查配置与流程，不代表真实业务成功。无需下载、安装或导入其他仓库。

功能:
  - 全自动认证链: querySpecToken -> ssoToken -> tyrzLogin -> jwtToken
  - AI豆(原云朵)余额统计(getCloudNum)
  - 每日签到(startSignIn,+3豆,基于 infoV3 防重复)
  - 拉取带豆数的云朵任务列表(taskListV3)
  - 自动完成纯接口可完成的任务:
      * 319 小云互动礼(循环点击直至完成,送云朵)
      * 118 调查问卷(单次点击即完成)
      * 605/606/431 等点击即完成的任务(YDYP_TRY_ALL)
      * 106 手动上传一个文件(上传后 FINISH,完成后可自动删除)
  - 只读展示当前 AI豆余额可兑换的奖品清单(exchangeList,不执行兑换)
  - 运行结束发送通知总结(青龙内置通知 / PushPlus / Server酱)

环境变量(在青龙面板配置):
  YDYP_ACCOUNTS          多账号,每行一个,格式: 手机号|Basic <token> (优先)
  YDYP_PHONE             单账号手机号 (与 YDYP_AUTH 配合)
  YDYP_AUTH              单账号 Authorization 值(Basic 开头,可省略 Basic 前缀)
  YDYP_TRY_ALL           是否尝试所有未完成任务,默认 false
  YDYP_INTERACT_LIMIT    小云互动礼最大点击次数,默认 30
  YDYP_UPLOAD            是否执行上传任务(106),默认 false
  YDYP_DELETE_AFTER      上传完成后是否删除文件,默认 false
  YDYP_DRY_RUN           设为 1 时完全断网预演，不验证真实业务
  QINGLONG_NOTIFY        全局通知开关，未设置时按上架状态
  QINGLONG_NOTIFY_DIR    可选，青龙通知模块目录
  PUSHPLUS_TOKEN         PushPlus 推送 token(可选)
  SENDKEY                Server酱 SendKey(可选)

如何获取 token(Authorization):
  1. 浏览器登录 https://yun.139.com (网页版)
  2. 打开开发者工具(F12) → 网络(Network)
  3. 刷新页面,任选一个 api.yun.139.com 或 yun.139.com 的请求
  4. 查看请求头 Authorization 字段(形如 Basic xxxxxx)
  5. 连同手机号填入青龙面板环境变量
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
        _ql_notify_identities = ('117317c83fa5c3cc', 'scripts/139_yunduo.py', '139_yunduo.py', '139_yunduo')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
# MIT License — 上游许可，来源 deeplee/personal-scripts。
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

import base64
import hashlib
import json
import os
import random
import re
import string
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BASE_URL = "https://yun.139.com/orchestration/auth-rebuild/token/v1.0/querySpecToken"
TYRZ_URL = "https://caiyun.feixin.10086.cn/portal/auth/tyrzLogin.action"
TASKLIST_URL = "https://caiyun.feixin.10086.cn/market/signin/task/taskList"
CLICK_URL = "https://caiyun.feixin.10086.cn/market/signin/task/click"

# H5 云朵中心(ycloud 域)
H5_BASE = "https://m.mcloud.139.com/ycloud"
H5_GET_CLOUD_NUM = H5_BASE + "/signin/page/getCloudNum"
H5_INFO_V3 = H5_BASE + "/signin/page/infoV3"
H5_START_SIGN_IN = H5_BASE + "/signin/page/startSignIn"
H5_TASK_LIST_V3 = H5_BASE + "/signin/task/taskListV3"
H5_EXCHANGE_LIST = H5_BASE + "/signin/page/exchangeList"

# 兑换奖品分类映射(exchangeList result 的 key)
EXCHANGE_CATEGORIES = {
    "0": "云盘", "1": "视频", "2": "音乐", "5": "外卖", "7": "快递",
    "8": "转存券", "9": "工具", "11": "美食", "15": "流量",
}

# 新平台 personal 上传/删除域
PERSONAL_HOST = "https://personal-kd-njs.yun.139.com/hcy"
FILE_CREATE_URL = PERSONAL_HOST + "/file/create"
FILE_COMPLETE_URL = PERSONAL_HOST + "/file/complete"
RECYCLE_TRASH_URL = PERSONAL_HOST + "/recyclebin/batchTrash"

MARKET_NAME = "sign_in_3"

# 纯接口即可完成的任务(其余任务需要真实操作:上传/分享/PC端/阅读等)
AUTO_TASKS = {
    319: "小云互动礼",   # 循环点击直至 FINISH,每次送云朵
    118: "调查问卷",     # 单次点击即 FINISH
}
# 点击即完成的任务(try_all 时也会尝试) —— 经验证 605/606/431
CLICK_DONE_TASKS = {605, 606, 431}

# 上传文件名前缀(可被识别并清理)
UPLOAD_PREFIX = "yunduo_task_"

# 完整 x-DeviceInfo / X-Yun-Client-Info(必须与此一致,否则 00010014)
X_DEVICE_INFO = "||9|7.14.0|chrome|120.0.0.0|||windows 10||zh-CN|||"
X_YUN_CLIENT_INFO = "||9|7.14.0|chrome|120.0.0.0|||windows 10||zh-CN|||dW5kZWZpbmVk||"


# ---------------------------------------------------------------------------
# HTTP 工具
# ---------------------------------------------------------------------------
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.URLError("拒绝重定向")


HTTP = urllib.request.build_opener(NoRedirect())
SECRETS = []
DRY = False


def safe_text(value):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    text = re.sub(r"(?<!\d)1\d{10}(?!\d)", "[手机号已隐藏]", text)
    return text.replace("\r", " ").replace("\n", " ")


def identity(d):
    if not isinstance(d, dict):
        return
    for obj in (d, d.get("data"), d.get("result")):
        if isinstance(obj, dict):
            for field in ("nickname", "nickName", "username", "displayName", "publicUid"):
                value = obj.get(field)
                if isinstance(value, (str, int)) and value:
                    log("官方账号身份: " + safe_text(value))
                    return


def _http(url, method="GET", data=None, headers=None, timeout=15):
    if DRY:
        raise RuntimeError("断网预演禁止 HTTP")
    if urllib.parse.urlsplit(url).scheme != "https":
        return -1, ""
    h = {"Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9",
         "User-Agent": UA, "Referer": "https://yun.139.com/w/"}
    h.update(headers or {})
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            h.setdefault("Content-Type", "application/json;charset=UTF-8")
        elif isinstance(data, bytes):
            body = data
        else:
            body = data.encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with HTTP.open(req, timeout=timeout) as resp:
            raw = resp.read(1048577)
            if len(raw) > 1048576:
                return -1, ""
            return resp.status, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        return -1, ""


def _basic(phone, auth_token):
    """
    构造 Authorization 值。
    用户提供的 token 通常已是 base64("pc:phone:authToken") 完整值;
    若为裸 authToken 则自动包装。
    """
    t = auth_token.strip()
    try:
        dec = base64.b64decode(t + "=" * (-len(t) % 4)).decode("utf-8", "replace")
        if dec.startswith("pc:"):
            return "Basic " + t
    except Exception:  # noqa: BLE001
        pass
    return "Basic " + base64.b64encode(
        ("pc:%s:%s" % (phone, t)).encode("utf-8")
    ).decode("utf-8")


def sanitize_token(val):
    """去掉 Basic 前缀、引号与空白"""
    if not val:
        return val
    v = val.strip().strip("'").strip('"')
    if v.lower().startswith("basic "):
        v = v[6:].strip()
    return v


# ---------------------------------------------------------------------------
# mcloud-sign 签名(新平台 personal 上传/删除接口)
# ---------------------------------------------------------------------------
def _esc(s):
    """encodeURIComponent 等价实现(保留 ! ' ( ) * )"""
    s = urllib.parse.quote(s, safe="")
    return (s.replace("%21", "!").replace("%27", "'")
             .replace("%28", "(").replace("%29", ")").replace("%2A", "*"))


def _mcloud_sign(body_str):
    """
    sign = md5( md5( base64( sort-chars( encodeURIComponent(body) ) ) ) + md5(ts + ":" + rand) ).upper()
    返回 "ts,rand,sign"
    """
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    rand = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
    eb = _esc(body_str)
    sorted_eb = "".join(sorted(eb))
    b64 = base64.b64encode(sorted_eb.encode("utf-8")).decode("ascii")
    h1 = hashlib.md5(b64.encode("utf-8")).hexdigest()
    h2 = hashlib.md5((ts + ":" + rand).encode("utf-8")).hexdigest()
    sign = hashlib.md5((h1 + h2).encode("utf-8")).hexdigest().upper()
    return "%s,%s,%s" % (ts, rand, sign)


# ---------------------------------------------------------------------------
# 认证链: SSO Token -> JWT Token
# ---------------------------------------------------------------------------
def get_sso_token(phone, basic):
    """POST querySpecToken -> ssoToken"""
    payload = {
        "toSourceId": "001005",
        "account": phone,
        "commonAccountInfo": {"account": phone, "accountType": 1},
    }
    hdrs = {"Authorization": basic, "Content-Type": "application/json;charset=UTF-8"}
    st, txt = _http(BASE_URL, method="POST", data=payload, headers=hdrs)
    if st != 200:
        return None, "SSO接口HTTP %s" % st
    try:
        d = json.loads(txt)
    except ValueError:
        return None, "SSO返回非JSON"
    if d.get("success") is not True and d.get("code") not in ("0", 0):
        return None, "SSO失败: %s %s" % (d.get("code"), "业务拒绝")
    identity(d)
    tok = (d.get("data") or {}).get("token")
    if not tok:
        return None, "SSO无token字段"
    SECRETS.append(tok)
    return tok, None


def get_jwt_token(sso, basic):
    """GET tyrzLogin.action?ssoToken= -> jwtToken"""
    url = TYRZ_URL + "?ssoToken=" + urllib.parse.quote(sso, safe="")
    hdrs = {"Authorization": basic}
    st, txt = _http(url, method="GET", headers=hdrs)
    if st != 200:
        return None, "JWT接口HTTP %s" % st
    try:
        d = json.loads(txt)
    except ValueError:
        return None, "JWT返回非JSON"
    if d.get("code") != 0:
        return None, "JWT失败: %s %s" % (d.get("code"), "业务拒绝")
    identity(d)
    tok = (d.get("result") or {}).get("token")
    if not tok:
        return None, "JWT无token字段"
    SECRETS.append(tok)
    return tok, None


def jwt_headers(jwt):
    """老平台任务接口需要的 jwt 双头"""
    return {"Cookie": "jwtToken=%s" % jwt, "jwtToken": jwt}


def h5_headers(jwt):
    """H5 ycloud 接口头: jwttoken + activityid + deviceid"""
    return {
        "jwttoken": jwt,
        "activityid": MARKET_NAME,
        "deviceid": "ql_%s" % random.randint(100000, 999999),
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://m.mcloud.139.com/",
        "Referer": "https://m.mcloud.139.com/",
    }


# ---------------------------------------------------------------------------
# H5 云朵中心接口
# ---------------------------------------------------------------------------
def h5_get(jwt, url):
    st, txt = _http(url, method="GET", headers=h5_headers(jwt))
    if st != 200:
        return None, "H5 HTTP %s" % st
    try:
        d = json.loads(txt)
        if not isinstance(d, dict):
            return None, "H5响应格式错误"
        identity(d)
        return d, None
    except ValueError:
        return None, "H5返回非JSON"


def get_cloud_num(jwt):
    """AI豆余额。result 为数字"""
    d, err = h5_get(jwt, H5_GET_CLOUD_NUM)
    if err:
        return None, err
    if d.get("code") != 0:
        return None, "getCloudNum失败: %s %s" % (d.get("code"), "业务拒绝")
    return d.get("result"), None


def get_sign_info(jwt):
    """infoV3: 返回 (result, err)。result 含 beforeTotal, signInPoints, cal[]"""
    d, err = h5_get(jwt, H5_INFO_V3)
    if err:
        return None, err
    if d.get("code") != 0:
        return None, "infoV3失败: %s %s" % (d.get("code"), "业务拒绝")
    result = d.get("result") or {}
    return result, None


def get_exchange_list(jwt):
    """兑换奖品列表(exchangeList,只读)。result 为 {分类ID: 奖品数组}"""
    d, err = h5_get(jwt, H5_EXCHANGE_LIST)
    if err:
        return None, err
    if d.get("code") != 0:
        return None, "exchangeList失败: %s %s" % (d.get("code"), "业务拒绝")
    return d.get("result") or {}, None


def is_signed_today(result):
    """根据 cal 判断今天是否已签到"""
    cal = result.get("cal") or []
    today = int(time.strftime("%d"))
    for c in cal:
        if str(c.get("d")) == str(today) and c.get("currentMonth") in (1, "1"):
            value = c.get("s")
            if value in (True, 1, "1"):
                return True
            if value in (False, 0, "0"):
                return False
            return None
    return None  # 未知


def start_sign_in(jwt):
    """每日签到,+signInPoints 豆。result 含 todaySignIn"""
    d, err = h5_get(jwt, H5_START_SIGN_IN)
    if err:
        return None, err
    if d.get("code") != 0:
        return None, "startSignIn失败: %s %s" % (d.get("code"), "业务拒绝")
    return d.get("result") or {}, None


def task_list_v3(jwt):
    """taskListV3: 返回 (list_of_tasks, err)。每任务含 description(豆数)/state"""
    payload = {"marketname": MARKET_NAME, "clientVersion": ""}
    st, txt = _http(H5_TASK_LIST_V3, method="POST", data=payload, headers=h5_headers(jwt))
    if st != 200:
        return None, "taskListV3 HTTP %s" % st
    try:
        d = json.loads(txt)
    except ValueError:
        return None, "taskListV3返回非JSON"
    if d.get("code") != 0:
        return None, "taskListV3失败: %s %s" % (d.get("code"), "业务拒绝")
    result = d.get("result") or []
    # result 可能是数组,也可能包了一层
    tasks = []
    if isinstance(result, list):
        tasks = result
    elif isinstance(result, dict):
        for v in result.values():
            if isinstance(v, list):
                tasks.extend(v)
            elif isinstance(v, dict):
                tasks.append(v)
    return tasks, None


# ---------------------------------------------------------------------------
# 新平台上传/删除
# ---------------------------------------------------------------------------
def _personal_headers(basic, body_str):
    """file/create、file/complete、recyclebin/batchTrash 通用头"""
    return {
        "Accept": "application/json,text/plain,*/*",
        "Authorization": basic,
        "Caller": "web",
        "Cms-Device": "default",
        "Mcloud-Channel": "1000101",
        "Mcloud-Client": "10701",
        "Mcloud-Route": "001",
        "Mcloud-Sign": _mcloud_sign(body_str),
        "Mcloud-Version": "7.14.0",
        "Origin": "https://yun.139.com/",
        "Referer": "https://yun.139.com/",
        "x-DeviceInfo": X_DEVICE_INFO,
        "x-huawei-channelSrc": "10000034",
        "x-inner-ntwk": "2",
        "x-m4c-caller": "PC",
        "x-m4c-src": "10002",
        "x-SvcType": "1",
        "X-Yun-Api-Version": "v1",
        "X-Yun-App-Channel": "10000034",
        "X-Yun-Channel-Source": "10000034",
        "X-Yun-Client-Info": X_YUN_CLIENT_INFO,
        "X-Yun-Module-Type": "100",
        "X-Yun-Svc-Type": "1",
        "Content-Type": "application/json",
    }


def _personal_post(basic, url, payload):
    body_str = json.dumps(payload, separators=(",", ":"))
    st, txt = _http(url, method="POST", data=body_str, headers=_personal_headers(basic, body_str))
    if st != 200:
        return None, "personal HTTP %s" % st
    try:
        d = json.loads(txt)
    except ValueError:
        return None, "personal返回非JSON"
    if d.get("code") != "0000" and d.get("code") != 0:
        return d, "personal失败: code=%s msg=%s" % (d.get("code"), "业务拒绝")
    return d, None


def upload_small_file(basic, name, size=10):
    """上传一个随机小文件,返回 (fileId, err)。成功后可触发 106 任务 FINISH"""
    data = os.urandom(size)
    sha = hashlib.sha256(data).hexdigest()
    payload = {
        "contentHash": sha,
        "contentHashAlgorithm": "SHA256",
        "contentType": "application/octet-stream",
        "parallelUpload": False,
        "partInfos": [{"partNumber": 1, "partSize": size}],
        "size": size,
        "parentFileId": "/",
        "name": name,
        "type": "file",
        "fileRenameMode": "auto_rename",
    }
    d, err = _personal_post(basic, FILE_CREATE_URL, payload)
    if err:
        return None, err
    dat = d.get("data") or {}
    file_id = dat.get("fileId")
    upload_id = dat.get("uploadId")
    parts = dat.get("partInfos") or []
    if not file_id or not parts:
        return None, "create 未返回 uploadUrl"
    url = parts[0].get("uploadUrl")
    if not url:
        return None, "create 未返回 uploadUrl"

    # 分片不携带账号凭据，使用服务端签名的 HTTPS 地址。
    st, _ = _http(url, method="PUT", data=data, timeout=30,
                  headers={"Content-Type": "application/octet-stream"})
    if st != 200:
        return None, "PUT 分片失败 HTTP %s" % st

    # file/complete
    comp = {"contentHash": sha, "contentHashAlgorithm": "SHA256",
            "fileId": file_id, "uploadId": upload_id}
    d2, err2 = _personal_post(basic, FILE_COMPLETE_URL, comp)
    if err2:
        return None, "complete失败: %s" % err2
    return file_id, None


def trash_files(basic, file_ids):
    """删除(移入回收站)文件"""
    if not file_ids:
        return True, None
    payload = {"fileIds": file_ids}
    d, err = _personal_post(basic, RECYCLE_TRASH_URL, payload)
    if err:
        return False, err
    return True, None


# ---------------------------------------------------------------------------
# 单账号执行
# ---------------------------------------------------------------------------
# 老平台 click 任务接口
# ---------------------------------------------------------------------------
def click_task(jwt, tid):
    """点击任务,返回 (ok, msg)"""
    url = "%s?key=task&id=%s" % (CLICK_URL, tid)
    st, txt = _http(url, method="GET", headers=jwt_headers(jwt))
    if st != 200:
        return False, "click HTTP %s" % st
    try:
        d = json.loads(txt)
    except ValueError:
        return False, "click返回非JSON"
    if d.get("code") == 0:
        result = d.get("result") or d.get("data") or ""
        return True, "业务接口已接受，需复查 FINISH"
    return False, "click失败: %s %s" % (d.get("code"), "业务拒绝")


# ---------------------------------------------------------------------------
# 通知
# ---------------------------------------------------------------------------
def log(message):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), safe_text(message)), flush=True)


def boolean(name, default=False):
    value = os.environ.get(name, "1" if default else "0").strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off", ""):
        return False
    raise ValueError(name + " 必须为布尔值")


def parse_accounts():
    multi = os.environ.get("YDYP_ACCOUNTS", "").strip()
    if multi:
        lines = [x.strip() for x in multi.splitlines() if x.strip() and not x.strip().startswith("#")]
    else:
        phone = os.environ.get("YDYP_PHONE", "").strip()
        auth = os.environ.get("YDYP_AUTH", "").strip()
        lines = [phone + "|" + auth] if phone or auth else []
    accounts = []
    for line in lines:
        if "|" not in line:
            accounts.append(None)
            continue
        phone, token = line.split("|", 1)
        phone, token = phone.strip(), sanitize_token(token)
        SECRETS.extend([phone, token, line])
        accounts.append((phone, token) if re.fullmatch(r"1\d{10}", phone) and token else None)
    return accounts


def send_notify(title, content):
    if os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in ("0", "false", "no", "off"):
        return "已关闭"
    # 子进程限制通知耗时，禁止第三方模块输出凭据；预演通知模块禁用网络。
    code = r'''
import sys, json, os, importlib.util, socket
payload = json.loads(sys.stdin.read())
if payload['dry']:
    def denied(*a, **k): raise RuntimeError('dry-run forbids network')
    socket.socket = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied
paths = [os.path.join(os.environ.get('QINGLONG_NOTIFY_DIR', ''), 'notify.py'), '/ql/data/scripts/notify.py', '/ql/scripts/notify.py']
try:
    import notify
except ImportError:
    notify = None
    for path in paths:
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location('ql_notify', path)
            notify = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(notify)
            break
if notify is None: sys.exit(2)
notify.send(payload['title'], payload['content'])
'''
    try:
        result = subprocess.run([sys.executable, "-c", code],
            input=json.dumps({"title": title, "content": content, "dry": DRY}),
            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if result.returncode == 0:
            return "青龙通知已调用" if not DRY else "预演青龙通知已调用（网络禁用）"
    except Exception:
        pass
    js_paths = [os.path.join(os.environ.get("QINGLONG_NOTIFY_DIR", ""), "sendNotify.js"),
                "/ql/data/scripts/sendNotify.js", "/ql/scripts/sendNotify.js"]
    for path in js_paths:
        if not os.path.isfile(path):
            continue
        js = """const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));
if(p.dry){const deny=()=>{throw Error('dry-run forbids network')};
for(const mod of ['http','https']){const m=require(mod);m.request=deny;m.get=deny;}
require('net').Socket.prototype.connect=deny;require('tls').connect=deny;
require('dns').lookup=deny;global.fetch=deny;}
Promise.resolve(require(p.path).sendNotify(p.title,p.content)).catch(()=>process.exit(1));"""
        try:
            proc = subprocess.run(["node", "-e", js], input=json.dumps({"path": os.path.abspath(path),
                "title": title, "content": content, "dry": DRY}), text=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if proc.returncode == 0:
                return "青龙JS通知已调用" if not DRY else "预演青龙JS通知已调用（网络禁用）"
        except Exception:
            pass
    if DRY:
        return "预演通知已尝试，模块不可用或网络被禁止"
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if token:
        SECRETS.append(token)
        st, text = _http("https://www.pushplus.plus/send", "POST",
                         {"token": token, "title": title, "content": content})
        try:
            if st == 200 and json.loads(text).get("code") == 200:
                return "PushPlus"
        except Exception:
            pass
    key = os.environ.get("SENDKEY", "").strip()
    if key:
        SECRETS.append(key)
        st, text = _http("https://sctapi.ftqq.com/" + urllib.parse.quote(key, safe="") + ".send",
                         "POST", urllib.parse.urlencode({"title": title, "desp": content}),
                         {"Content-Type": "application/x-www-form-urlencoded"})
        try:
            if st == 200 and json.loads(text).get("code") == 0:
                return "Server酱"
        except Exception:
            pass
    return "通知不可用或失败（保留业务退出码）"


class Stages:
    def __init__(self, index):
        self.index = index
        self.counts = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
        self.started = time.monotonic()
        self.number = 0

    def run(self, name, action):
        self.number += 1
        start = time.monotonic()
        log("账号%d 阶段%d %s 开始" % (self.index, self.number, name))
        try:
            status, detail = action()
            if status not in self.counts:
                raise ValueError("阶段状态错误")
        except Exception:
            status, detail = "failure", "响应格式、参数或运行错误（原始内容已隐藏）"
        self.counts[status] += 1
        icon = {"success": "✅", "alreadyComplete": "☑️", "skipped": "⏭️", "failure": "❌"}[status]
        log("账号%d 阶段%d %s %s：%s；耗时 %.2f秒" %
            (self.index, self.number, name, icon, detail, time.monotonic() - start))
        return status

    def finish(self):
        log("账号%d 统计：总任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒" %
            (self.index, self.number, self.counts['success'], self.counts['alreadyComplete'],
             self.counts['skipped'], self.counts['failure'], time.monotonic() - self.started))
        return self.counts


def run_account(index, account, options):
    stages = Stages(index)
    if account is None:
        stages.run("参数校验", lambda: ("failure", "账号格式错误，应为手机号|Authorization"))
        return stages.finish()
    phone, token = account
    if DRY:
        for name in ("认证链", "AI豆余额", "每日签到", "云朵任务列表与点击完成复查", "文件上传与清理", "最新余额与只读兑换清单"):
            stages.run(name, lambda: ("skipped", "DRY_RUN_OK：参数已解析，未调用网络或修改云盘"))
        return stages.finish()
    basic = _basic(phone, token)
    SECRETS.append(basic)
    context = {}
    def auth():
        sso, err = get_sso_token(phone, basic)
        if err: return "failure", err
        jwt, err = get_jwt_token(sso, basic)
        if err: return "failure", err
        context['jwt'] = jwt
        return "success", "SSO与JWT业务认证成功"
    if stages.run("认证链", auth) == "failure":
        return stages.finish()
    jwt = context['jwt']
    def balance():
        value, err = get_cloud_num(jwt)
        if err: return "failure", err
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            return "failure", "余额字段格式错误"
        context['balance'] = value
        return "success", "当前AI豆余额：%s" % value
    stages.run("AI豆余额", balance)
    def sign():
        info, err = get_sign_info(jwt)
        if err: return "failure", err
        signed = is_signed_today(info)
        if signed is True: return "alreadyComplete", "今天已签到"
        if signed is None: return "failure", "无法确认当天状态，不发送签到变更"
        result, err = start_sign_in(jwt)
        if err: return "failure", err
        if result.get('todaySignIn') not in (True, 1): return "failure", "签到未确认"
        return "success", "签到已确认；奖励AI豆：%s" % result.get('signInPoints', '未提供')
    stages.run("每日签到", sign)
    def listing():
        tasks, err = task_list_v3(jwt)
        if err: return "failure", err
        if not all(isinstance(x, dict) and str(x.get("id", "")).isdigit() and 'state' in x for x in tasks):
            return "failure", "任务字段格式错误"
        context['tasks'] = tasks
        return "success", "获取%d项云朵任务" % len(tasks)
    stages.run("云朵任务列表", listing)
    def state(tid):
        tasks, err = task_list_v3(jwt)
        if err: return None
        return next((x.get('state') for x in tasks if str(x.get('id')) == str(tid)), None)
    for task in context.get('tasks', []):
        tid = int(task['id'])
        name = re.sub(r'<[^>]+>', '', str(task.get('name') or '云朵任务'))
        desc = re.sub(r'<[^>]+>', '', str(task.get('description') or ''))
        label = "%s[%d] %s" % (name, tid, desc)
        def action(task=task, tid=tid):
            if task.get('state') == 'FINISH': return "alreadyComplete", "任务状态 FINISH"
            if task.get('enable') in (0, '0', False): return "skipped", "任务停用"
            if tid == 106:
                if not options['upload']: return "skipped", "上传需显式设置 YDYP_UPLOAD=1"
                fname = UPLOAD_PREFIX + time.strftime('%Y%m%d%H%M%S') + '_%d.txt' % random.randint(1000,9999)
                fid, err = upload_small_file(basic, fname)
                if err: return "failure", err
                time.sleep(1.5)
                complete = state(tid) == 'FINISH'
                cleanup = True
                if options['delete']:
                    cleanup, err = trash_files(basic, [fid])
                    log("本次上传文件清理：" + ("已移入回收站" if cleanup else "失败"))
                else:
                    log("本次上传文件保留在云盘；未启用清理")
                return ("success", "上传任务 FINISH 已确认") if complete and cleanup else ("failure", "上传完成状态或清理未确认")
            if tid not in AUTO_TASKS and tid not in CLICK_DONE_TASKS and not options['try_all']:
                return "skipped", "需要真实操作，默认不尝试未知任务"
            limit = options['limit'] if tid == 319 else 1
            for n in range(limit):
                ok, msg = click_task(jwt, tid)
                if not ok: return "failure", msg
                time.sleep(0.3)
                current = state(tid)
                log("任务%d 点击%d/%d：接口已接受，状态%s" % (tid, n+1, limit, 'FINISH' if current == 'FINISH' else '未完成'))
                if current == 'FINISH': return "success", "完成状态 FINISH 已复查"
                if current is None: return "failure", "复查失败，不继续点击"
            return "failure", "达到点击上限仍未完成"
        stages.run(label, action)
    stages.run("最新AI豆余额", balance)
    def exchange():
        if 'balance' not in context: return "failure", "无有效余额，不能计算可兑换奖品"
        prizes, err = get_exchange_list(jwt)
        if err: return "failure", err
        if not isinstance(prizes, dict): return "failure", "兑换清单格式错误"
        affordable = []
        for cat, items in prizes.items():
            if not isinstance(items, list): continue
            for p in items:
                try: price = int(p.get('POrder'))
                except (TypeError, ValueError): continue
                if 0 < price <= context['balance'] and p.get('onLine', 1) not in (0, '0', False):
                    affordable.append((price, str(p.get('prizeName', '?')), EXCHANGE_CATEGORIES.get(str(cat), '其他'), p.get('dailyRemainderCount', '?')))
        for price, name, cat, remaining in sorted(affordable, key=lambda x: x[0]):
            log("可兑换：%s %d豆 [%s] 今日剩余%s" % (name, price, cat, remaining))
        return "success", "可兑换%d项，仅展示，未兑换" % len(affordable)
    stages.run("只读兑换清单", exchange)
    return stages.finish()


def main():
    global DRY
    start = time.monotonic()
    log("========== 139云盘云朵任务 ==========")
    log("开始时间：" + time.strftime('%Y-%m-%d %H:%M:%S'))
    accounts = parse_accounts()
    results = []
    config_error = None
    try:
        DRY = boolean('YDYP_DRY_RUN')
        limit = int(os.environ.get('YDYP_INTERACT_LIMIT', '30'))
        if not 1 <= limit <= 100: raise ValueError('YDYP_INTERACT_LIMIT 必须为1至100')
        options = {'limit': limit, 'upload': boolean('YDYP_UPLOAD'),
                   'delete': boolean('YDYP_DELETE_AFTER'), 'try_all': boolean('YDYP_TRY_ALL')}
        if not accounts: raise ValueError('未配置 YDYP_ACCOUNTS；兼容 YDYP_PHONE 与 YDYP_AUTH')
    except ValueError as exc:
        config_error = str(exc)
    log("运行模式：" + ('断网预演' if DRY else '正式执行'))
    log("账号总数：%d" % len(accounts))
    if config_error:
        log("阶段1 参数校验 ❌ 配置错误：" + config_error + "；耗时 %.2f秒" % (time.monotonic() - start))
    else:
        for i, account in enumerate(accounts, 1):
            try:
                results.append(run_account(i, account, options))
            except Exception:
                stages = Stages(i)
                stages.run('账号执行', lambda: ('failure', '运行异常，已隐藏详细内容'))
                results.append(stages.finish())
    failed = len(accounts) if config_error else sum(x['failure'] > 0 for x in results)
    success = 0 if config_error else len(results) - failed
    code = 1 if config_error or failed else 0
    status = 'configuration-error' if config_error else ('partial-failure' if failed and success else 'failure' if failed else 'dry-run' if DRY else 'success')
    totals = {k: sum(x[k] for x in results) for k in ('success', 'alreadyComplete', 'skipped', 'failure')}
    body = '模式：%s；状态：%s；账号总数%d 成功%d 失败%d；子任务%s' % ('断网预演，未验证业务' if DRY else '正式执行', status, len(accounts), success, failed, json.dumps(totals, ensure_ascii=False))
    notification = send_notify('139云盘云朵任务', body)
    log('--------------------------------------------------')
    log(body)
    log('通知状态：' + notification)
    log('总耗时：%.2f秒' % (time.monotonic() - start))
    finish = time.strftime('%Y-%m-%d %H:%M:%S')
    log('完成时间：' + finish)
    log('最终状态：' + ('DRY_RUN_OK' if DRY and code == 0 else 'TASK_SUCCESS' if code == 0 else 'TASK_FAILED'))
    print('TASK_SUMMARY=' + json.dumps({'task': '139云盘云朵任务', 'status': status, 'dryRun': DRY,
        'accountCount': len(accounts), 'successCount': success, 'failureCount': failed,
        'stages': totals, 'notification': notification, 'finishTime': finish, 'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
