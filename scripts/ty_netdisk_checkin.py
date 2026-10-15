#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 天翼云盘签到
# cron: 2 1 * * *
# SPDX-License-Identifier: MIT
# 上游：agluo/ql-script-hub，ty_netdisk_checkin.py（MIT）
# 改编自：https://www.52pojie.cn/thread-1231190-1-1.html
# 合并：OreosLab/checkinpanel，ck_cloud189.py（MIT）
# :source https://github.com/MayoBlueSky/My-Actions/blob/master/function/cloud189/checkin.py
# 参考：dailycheckin_scripts/ck_cloud189.py（MIT）；保留上游来源声明。
# 有效许可：MIT；输入文件未包含额外版权声明。
"""天翼云盘每日签到。仅需 Python 3.9+ 标准库，无须安装 requests 或 rsa。
在天翼云盘官方客户端设置或确认账号密码；需要验证码时请先人工登录。
TY_ACCOUNTS：每个非空行填写 用户名|密码，仅切分第一个 |，密码原样保留。
不再接受旧的 TY_USERNAME/TY_PASSWORD 分列与 & 分账号格式。
迁移时将同一账号的用户名和密码合为一行；密码中的 |、&、@ 均原样保留。
登录响应失败不能单凭格式异常判定为密码错误；请按失败阶段和业务码核对。
TY_DRY_RUN=1：只检查配置并模拟流程，不请求网络、不等待、不调用通知传输。
RANDOM_SIGNIN=true（默认），MAX_RANDOM_DELAY=3600（秒）；账号间等待10～30秒。
TY_ACCOUNT_TIMEOUT=60：每账号 HTTP 流程总时限（秒），不包含配置的随机等待。
验证建议 RANDOM_SIGNIN=false；保留日常随机延迟默认值。
TY_DRAW_SIGNIN=1：签到后抽取签到奖励；TY_DRAW_PHOTOS=1：抽取相册任务奖励。
两个开关默认0，仅使用当前已有机会，不开启相册备份、不上传照片、不购买机会。
奖励抽取无机会时记录已完成，未知错误或缺少奖励字段时失败，不自动重试。
原 ck_cloud189.py 使用私有 CLOUD189 列表中的 phone/password，每日09:30；
迁移为 TY_ACCOUNTS 每行用户名|密码；合并后沿用规范任务每日16:01，无需重复任务。
QINGLONG_NOTIFY=0 可关闭通知；可用 QINGLONG_NOTIFY_DIR 指定青龙通知目录。
"""
import os
import re
import sys
import json
import time
import random
import urllib.parse
from datetime import datetime
from contextlib import contextmanager
import signal
from html import unescape
from html.parser import HTMLParser


import base64
import secrets
import socket
import ssl
import urllib.request
import urllib.error
import http.cookiejar


class HttpResponse:
    def __init__(self, response):
        self.status_code = response.code
        self.url = response.geturl()
        self.headers = response.headers
        # 不接受压缩响应，限制正文大小，防止异常页面耗尽内存。
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise TaskError("响应正文超过大小限制")
        self.text = raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")

    def json(self):
        try:
            return json.loads(self.text)
        except (ValueError, TypeError):
            content_type = self.headers.get_content_type()
            kind = ("HTML 页面" if self.text.lstrip().lower().startswith(("<!doctype html", "<html"))
                    or content_type == "text/html" else "空正文" if not self.text.strip() else "非 JSON 正文")
            raise TaskError("响应格式异常：" + kind + "；不能据此判定账号密码错误") from None

    def login_json(self):
        # 上游明确支持 callbackMsg JSONP；只解析该回调，不执行服务端脚本。
        text = self.text.strip()
        match = re.fullmatch(r"callbackMsg\s*\((.*)\)\s*;?", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except ValueError:
                raise TaskError("登录 JSONP 正文不是有效 JSON；不能据此判定账号密码错误") from None
        return self.json()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpSession:
    """独立 Cookie 会话；重定向由业务层验证后执行，无重试。"""
    def __init__(self):
        self.headers = {}
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies), NoRedirect())

    def request(self, method, url, headers=None, params=None, data=None,
                timeout=15, allow_redirects=False):
        if os.getenv("TY_DRY_RUN", "0").lower() in ("1", "true", "yes", "on"):
            raise TaskError("断网预演禁止 HTTP 请求")
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        merged = {**self.headers, **(headers or {})}
        merged["Accept-Encoding"] = "identity"
        if isinstance(data, dict):
            data = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=data, headers=merged, method=method)
        try:
            response = self.opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return HttpResponse(response)

    def close(self):
        self.cookies.clear()


def rsa_encrypt_hex(key, value):
    """解析服务端 SPKI RSA 公钥，执行 RSAES-PKCS1-v1_5 公钥加密。
    与上游 rsa.encrypt 的协议相同；随机填充使用操作系统安全随机源。
    仅实施公钥操作，不包含私钥或解密功能。
    """
    def tlv(data, pos=0):
        if pos + 2 > len(data):
            raise ValueError()
        tag, size = data[pos], data[pos + 1]
        pos += 2
        if size & 128:
            count = size & 127
            if not 1 <= count <= 4 or pos + count > len(data):
                raise ValueError()
            size = int.from_bytes(data[pos:pos + count], "big")
            pos += count
        end = pos + size
        if end > len(data):
            raise ValueError()
        return tag, data[pos:end], end

    try:
        der = base64.b64decode("".join(key.split()), validate=True)
        tag, spki, end = tlv(der)
        if tag != 0x30 or end != len(der):
            raise ValueError()
        tag, algorithm, offset = tlv(spki)
        if tag != 0x30 or algorithm not in (
                bytes.fromhex("06092a864886f70d0101010500"),
                bytes.fromhex("06092a864886f70d010101")):
            raise ValueError()
        tag, bits, end = tlv(spki, offset)
        if tag != 3 or end != len(spki) or not bits or bits[0] != 0:
            raise ValueError()
        tag, public, end = tlv(bits[1:])
        if tag != 0x30 or end != len(bits) - 1:
            raise ValueError()
        tag, modulus, offset = tlv(public)
        if tag != 2 or not modulus or modulus[0] & 128:
            raise ValueError()
        tag, exponent, end = tlv(public, offset)
        if tag != 2 or end != len(public) or not exponent or exponent[0] & 128:
            raise ValueError()
        n, e = int.from_bytes(modulus, "big"), int.from_bytes(exponent, "big")
        if not 1024 <= n.bit_length() <= 8192 or not 3 <= e < n or e % 2 != 1:
            raise ValueError()
        size = (n.bit_length() + 7) // 8
        message = value.encode("utf-8")
        if len(message) > size - 11:
            raise TaskError("凭据长度超过服务端 RSA 公钥允许范围")
        padding = bytearray()
        while len(padding) < size - len(message) - 3:
            padding.extend(b for b in secrets.token_bytes(size) if b)
        padding = padding[:size - len(message) - 3]
        encoded = b"\x00\x02" + bytes(padding) + b"\x00" + message
        return pow(int.from_bytes(encoded, "big"), e, n).to_bytes(size, "big").hex()
    except TaskError:
        raise
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise TaskError("服务端 RSA 公钥格式无效") from None


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    """仅允许开发者定义的脱敏错误说明，不携带服务端原文。"""


def diagnostic(error):
    if isinstance(error, TaskError):
        return str(error)
    if isinstance(error, ImportError):
        return "Python 标准库或通知模块不可用"
    if isinstance(error, urllib.error.URLError):
        reason = error.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "请求超时"
        if isinstance(reason, socket.gaierror):
            return "域名解析失败"
        if isinstance(reason, ssl.SSLError):
            return "TLS 验证失败"
        return "网络连接失败"
    # 不输出异常正文，其中可能包含带凭据的 URL。
    name = type(error).__name__
    return {"TimeoutError": "请求超时", "Timeout": "请求超时", "ReadTimeout": "读取超时",
            "ConnectTimeout": "连接超时", "ConnectionError": "连接失败",
            "SSLError": "TLS 验证失败", "JSONDecodeError": "响应不是有效 JSON",
            "ValueError": "参数或响应格式校验失败"}.get(name, "运行或响应格式异常")


@contextmanager
def request_deadline(seconds):
    """青龙 Linux/POSIX 实时时限覆盖 DNS、连接、重定向和响应读取。"""
    def expired(signum, frame):
        raise TaskError("账号 HTTP 总时限已到；未确认业务成功，不自动重试")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def business_code(data, key):
    value = data.get(key)
    # 只输出短整数业务码，不输出消息、未知字符串、身份或原始响应。
    if type(value) in (str, int) and re.fullmatch(r"-?[0-9]{1,6}", str(value)):
        return str(value)
    return "缺失或非数字"


def response_shape(data):
    """只记录固定协议字段的存在性和类型；不输出值或未知字段名。"""
    def kind(value):
        return {dict: "对象", list: "数组", str: "文本", int: "整数",
                float: "小数", bool: "布尔", type(None): "空值"}.get(type(value), "其他")
    if not isinstance(data, dict):
        return "正文类型=" + kind(data)
    fields = ("result", "data", "res_code", "code", "errorCode", "toUrl", "isSign", "netdiskBonus")
    return "协议字段类型=" + ",".join(k + ":" + (kind(data[k]) if k in data else "缺失") for k in fields)


class LoginFields(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.key = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("id") == "j_rsaKey":
            self.key = attrs.get("value")


class TianYiYunPan:
    def __init__(self, username, password, index):
        self.username, self.password, self.index = username, password, index
        self.session = HttpSession()
        self.phase = "初始化"
        self.last_error = None
        self.deadline = time.monotonic() + int(os.getenv("TY_ACCOUNT_TIMEOUT", "60"))

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", 15)
        # 认证重定向仅允许官方 HTTPS 域名；禁止凭据随非官方跳转发送。
        for _ in range(8):
            parsed = urllib.parse.urlsplit(url)
            host = parsed.hostname or ""
            if parsed.scheme != "https" or not (host == "189.cn" or host.endswith(".189.cn")) or parsed.username or parsed.password:
                raise TaskError("拒绝非官方 HTTPS 地址")
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TaskError("账号 HTTP 总时限已到；未确认业务成功")
            log(f"账号{self.index} {self.phase}：开始请求；剩余总时限{remaining:.1f}秒；无自动重试")
            stamp = time.monotonic()
            with request_deadline(remaining):
                response = self.session.request(method, url, allow_redirects=False, **kwargs)
            log(f"账号{self.index} {self.phase}：请求耗时{time.monotonic()-stamp:.2f}秒")
            log(f"账号{self.index} {self.phase}：HTTP {response.status_code}")
            if response.status_code >= 400:
                raise TaskError(f"HTTP 请求失败，状态码 {response.status_code}")
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            url = urllib.parse.urljoin(response.url, response.headers["Location"])
            kwargs.pop("params", None)
            if response.status_code in (301, 302, 303):
                method = "GET"
                kwargs.pop("data", None)
        raise TaskError("重定向次数过多")

    def rsa_encode(self, key, value):
        return rsa_encrypt_hex(key, value)

    def identity(self, result):
        for data in (result, result.get("data")):
            if not isinstance(data, dict):
                continue
            for key in ("nickname", "nickName", "displayName", "userName", "username", "publicUid"):
                value = data.get(key)
                if isinstance(value, (str, int)) and not isinstance(value, bool):
                    value = str(value)
                    if self.password in value or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value):
                        continue
                    if any(ord(c) < 32 for c in value):
                        continue
                    log(f"账号{self.index} 官方身份：{value}")

    def login(self):
        """登录天翼云盘：兼容 2026 新版 wap 登录页"""
        try:
            import json
            import urllib.parse

            log(f"账号{self.index}: 请求官方登录页面")

            headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            self.session.headers.update(headers)

            def add_param(url, key, value):
                if key + "=" in url:
                    return url
                sep = "&" if "?" in url else "?"
                return url + sep + key + "=" + urllib.parse.quote(str(value))

            urlToken = "https://m.cloud.189.cn/udb/udb_login.jsp?pageId=1&pageKey=default&clientType=wap&redirectURL=https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html"
            self.phase = "登录入口"
            r = self.request("GET", urlToken, headers=headers, timeout=15)

            # 已经由 HTTP 重定向抵达密码页时直接解析；不要误取页面中的资源 URL。
            if LoginFields(r.text).key is None:
                links = re.findall(r"https?://[^\s'\"<>]+", r.text)
                links = [unescape(link) for link in links
                         if urllib.parse.urlsplit(unescape(link)).hostname == "open.e.189.cn"]
                if not links:
                    raise TaskError("登录入口未找到官方认证地址或公钥；需核对页面接口")
                auto_url = links[0]
                self.phase = "认证跳转"
                r = self.request("GET", auto_url, headers={**headers, "Referer": urlToken}, timeout=15)
                login_page_url = r.url.replace("/index.html", "/login.html")
                login_page_url = add_param(login_page_url, "protocol", "https")
                login_page_url = add_param(login_page_url, "showback", "true")
                self.phase = "密码登录页"
                r = self.request("GET", login_page_url,
                                 headers={**headers, "Referer": auto_url}, timeout=15)
            j_rsakey = LoginFields(r.text).key
            if not j_rsakey:
                raise TaskError("密码登录页缺少 j_rsaKey 公钥")

            query = urllib.parse.urlsplit(r.url).query
            conf_url = "https://open.e.189.cn/api/logbox/oauth2/wap/appConf.do?" + query

            self.phase = "登录配置 appConf"
            rc = self.request("POST", 
                conf_url,
                headers={**headers, "Referer": r.url},
                timeout=15
            )

            conf = rc.json()
            if not isinstance(conf, dict):
                raise TaskError("登录配置响应不是对象；" + response_shape(conf))
            if str(conf.get("result")) != "0":
                raise TaskError("登录配置业务校验失败，result=" + business_code(conf, "result") + "；" + response_shape(conf))

            data_conf = conf.get("data") or {}
            if not isinstance(data_conf, dict):
                raise TaskError("登录配置 data 不是对象")

            appKey = data_conf.get("appKey", "cloud")
            accountType = data_conf.get("accountType", "02")
            paramId = data_conf.get("paramId", "")
            lt = data_conf.get("lt", "")
            reqId = data_conf.get("reqId", "")
            state = data_conf.get("state", "")
            isOauth2 = str(data_conf.get("isOauth2", True)).lower()
            returnUrl = urllib.parse.quote(data_conf.get("returnUrl", ""), safe="")

            if not paramId or not lt or not reqId or not returnUrl:
                raise TaskError("appConf 关键字段缺失：" + ",".join(k for k, v in (("paramId", paramId), ("lt", lt), ("reqId", reqId), ("returnUrl", returnUrl)) if not v))

            self.session.headers.update({"lt": lt})

            username_plain = self.username
            if str(data_conf.get("hasAt", "false")).lower() == "true" and "@" not in username_plain:
                username_plain = username_plain + "@189.cn"

            username_encrypted = self.rsa_encode(j_rsakey, username_plain)
            password_encrypted = self.rsa_encode(j_rsakey, self.password)

            login_url = "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do"

            params = {
                "apptype": "wap",
                "appKey": appKey,
                "accountType": accountType,
                "dynamicCheck": "false",
                "userName": "{RSA}" + username_encrypted,
                "epd": "{RSA}" + password_encrypted,
                "version": "v2.0",
                "returnUrl": returnUrl,
                "isConfigurable": "true",
                "isOauth2": isOauth2,
                "state": state,
                "paramId": paramId,
                "lt": lt,
                "REQID": reqId,
                "callbackMsg": "callbackMsg",
            }

            self.phase = "提交密码登录"
            r = self.request("GET", 
                login_url,
                params=params,
                headers={
                    **headers,
                    "Referer": r.url,
                    "Accept": "*/*",
                },
                timeout=15
            )

            result = r.login_json()

            if not isinstance(result, dict):
                raise TaskError("登录响应不是对象；" + response_shape(result))
            if str(result.get("result")) == "0":
                log(f"✅ 账号{self.index}: 登录业务校验成功")
                self.identity(result)
                redirect_url = result.get("toUrl")
                if redirect_url:
                    self.phase = "建立云盘会话"
                    self.request("GET", redirect_url, headers=headers, timeout=15)
                return True

            raise TaskError("登录业务校验失败，result=" + business_code(result, "result") + "；" + response_shape(result)
                            + "；未确认密码错误，请核对官方登录或验证码要求")

        except Exception as e:
            self.last_error = self.phase + "：" + diagnostic(e)
            log(f"❌ 账号{self.index}: {self.last_error}")
            return False

    def sign_in(self):
        self.phase = "每日签到"
        response = self.request("GET", "https://api.cloud.189.cn/mkt/userSign.action",
            params={"rand": str(round(time.time()*1000)), "clientType": "TELEANDROID",
                    "version": "8.6.3", "model": "SM-G930K"},
            headers={"User-Agent": "Mozilla/5.0 Ecloud/8.6.3 Android/22",
                     "Referer": "https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1"}, timeout=15)
        result = response.json()
        if not isinstance(result, dict):
            raise TaskError("签到响应不是对象；" + response_shape(result))
        for key in ("res_code", "result", "code", "errorCode"):
            if key in result and str(result[key]) != "0":
                raise TaskError("签到业务返回失败，" + key + "=" + business_code(result, key))
        flag = result.get("isSign")
        bonus = result.get("netdiskBonus")
        if not (type(flag) is bool or type(flag) is str and flag in ("true", "false")):
            raise TaskError("签到响应缺少明确 isSign 标志；" + response_shape(result))
        if isinstance(bonus, bool) or not isinstance(bonus, (int, float, str)) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", str(bonus)):
            raise TaskError("签到响应缺少有效 netdiskBonus 奖励字段；" + response_shape(result))
        self.identity(result)
        already = flag is True or flag == "true"
        log(f"{'☑️ 今日已签到' if already else '✅ 签到成功'}，获得 {bonus}M 空间")
        return "already" if already else "success"


    def draw_prize(self, task_id):
        # 两份同功能参考一致：GET，ACT_SIGNIN，description=1 表示50M，
        # User_Not_Chance 表示无剩余机会。未知业务错误一律失败，不猜测成功码。
        if task_id not in ("TASK_SIGNIN", "TASK_SIGNIN_PHOTOS"):
            raise TaskError("不支持的奖励任务")
        self.phase = "签到奖励抽取" if task_id == "TASK_SIGNIN" else "相册奖励抽取"
        response = self.request("GET", "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action",
            params={"taskId": task_id, "activityId": "ACT_SIGNIN"},
            headers={"User-Agent": "Mozilla/5.0 Ecloud/8.6.3 Android/22",
                     "Referer": "https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1"},
            timeout=15)
        result = response.json()
        if not isinstance(result, dict):
            raise TaskError("奖励响应不是对象；" + response_shape(result))
        # 不把未知错误文本、description 原文或响应对象写入日志。
        for key in ("res_code", "result", "code"):
            if key in result and str(result[key]) != "0":
                raise TaskError("奖励业务返回失败，" + key + "=" + business_code(result, key))
        if result.get("errorCode") == "User_Not_Chance":
            log(f"☑️ 账号{self.index} {self.phase}：没有剩余抽奖机会")
            return "already"
        if "errorCode" in result:
            # 上游未证明任何带 errorCode 的响应是成功；包括0也不能推定成功。
            raise TaskError("奖励业务返回错误，errorCode=" + business_code(result, "errorCode"))
        description = result.get("description")
        if not (type(description) is int and description > 0
                or isinstance(description, str) and description.strip()
                and not re.fullmatch(r"-?[0-9]+", description.strip())
                or isinstance(description, str) and re.fullmatch(r"[1-9][0-9]*", description)):
            raise TaskError("奖励响应缺少明确 description 奖励字段；" + response_shape(result))
        self.identity(result)
        if description in (1, "1"):
            reward = "50M 空间"
        elif isinstance(description, str) and re.fullmatch(r"[0-9]{1,6}\s*[MG]B?\s*空间", description.strip()):
            reward = description.strip()
        else:
            reward = "已确认奖励（服务端自由文本不写入日志）"
        log(f"✅ 账号{self.index} {self.phase}成功：{reward}")
        return "success"


def notify(body, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in ("0", "false", "no", "off"):
        return "已关闭"
    if dry:
        log("⏭️ 断网预演通知摘要：" + body)
        return "预演已生成（不传输）"
    # 通知在独立进程执行，限制耗时且不转发第三方模块输出。
    import subprocess
    code = """import importlib.util, sys
from pathlib import Path
body = sys.stdin.read()
try:
    from notify import send
    send('天翼云盘签到', body)
    sys.exit(0)
except Exception:
    pass
for folder in sys.argv[1:]:
    path = Path(folder) / 'notify.py'
    if not path.is_file():
        continue
    try:
        sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location('ql_notify', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.send('天翼云盘签到', body)
        sys.exit(0)
    except Exception:
        pass
# 青龙的可选 JavaScript 通知兜底不参与业务 HTTP，也不是业务依赖。
import subprocess, shutil
node = shutil.which('node')
if node:
    for folder in sys.argv[1:]:
        path = Path(folder) / 'sendNotify.js'
        if not path.is_file():
            continue
        try:
            proc = subprocess.run([node, '-e',
                "const fs=require('fs');Promise.resolve(require(process.argv[1]).sendNotify('天翼云盘签到',fs.readFileSync(0,'utf8'))).catch(()=>process.exit(1));",
                str(path)], input=body, text=True, timeout=8)
            if proc.returncode == 0:
                sys.exit(0)
        except Exception:
            pass
sys.exit(2)
"""
    try:
        dirs = [p for p in (os.getenv("QINGLONG_NOTIFY_DIR"), "/ql/data/scripts", "/ql/scripts") if p]
        proc = subprocess.run([sys.executable, "-c", code, *dirs], input=body, text=True,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return "已发送" if proc.returncode == 0 else "不可用或发送失败"
    except Exception:
        return "不可用或发送失败"


def main():
    started = time.monotonic()
    dry = os.getenv("TY_DRY_RUN", "0").lower() in ("1", "true", "yes", "on")
    lines = [line for line in os.getenv("TY_ACCOUNTS", "").splitlines() if line.strip()]
    log("==== 天翼云盘签到 ====")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry else '正式执行'}；账号数：{len(lines)}")
    results = []
    config_error = False
    config_detail = ""
    totals = dict(success=0, already=0, skipped=0, failed=0)
    draw_signin = draw_photos = False
    try:
        def draw_switch(name):
            value = os.getenv(name, "0").lower()
            if value not in ("1", "true", "yes", "on", "0", "false", "no", "off"):
                raise ValueError()
            return value in ("1", "true", "yes", "on")
        draw_signin = draw_switch("TY_DRAW_SIGNIN")
        draw_photos = draw_switch("TY_DRAW_PHOTOS")
        maximum = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
        account_timeout = int(os.getenv("TY_ACCOUNT_TIMEOUT", "60"))
        if not 10 <= account_timeout <= 600 or not 0 <= maximum <= 86400 or not lines:
            raise ValueError()
    except ValueError:
        config_error = True
        config_detail = "需要 TY_ACCOUNTS，MAX_RANDOM_DELAY 须为0～86400的整数，TY_ACCOUNT_TIMEOUT 须为10～600的整数，奖励开关须为1/0或true/false/yes/no/on/off"
        if not lines and (os.getenv("TY_USERNAME") or os.getenv("TY_PASSWORD")):
            config_detail += "；检测到旧变量，请将同一账号合为 TY_ACCOUNTS 每行用户名|密码，密码原样保留"
        log("❌ 配置错误：" + config_detail)
    if not config_error and not dry and os.getenv("RANDOM_SIGNIN", "true").lower() == "true":
        delay = random.randint(0, maximum)
        log(f"阶段0 随机延迟：{delay}秒")
        while delay > 0:
            step = min(delay, 30)
            time.sleep(step)
            delay -= step
            log(f"阶段0 随机延迟剩余：{delay}秒")
    enabled_draws = []
    if draw_signin:
        enabled_draws.append(("签到奖励抽取", "TASK_SIGNIN"))
    if draw_photos:
        enabled_draws.append(("相册奖励抽取", "TASK_SIGNIN_PHOTOS"))
    task_count = 2 + len(enabled_draws)
    log(f"任务开关：签到奖励={'开启' if draw_signin else '关闭'}；相册奖励={'开启' if draw_photos else '关闭'}；每账号{task_count}个阶段")
    for index, line in enumerate(lines if not config_error else [], 1):
        begin = time.monotonic()
        stats = dict(success=0, already=0, skipped=0, failed=0)
        client = None
        failure_detail = ""
        stage = 1
        stamp = time.monotonic()
        try:
            log(f"账号{index} 阶段1/{task_count}：配置与登录")
            username, sep, password = line.partition("|")
            if not sep or not username.strip() or not password:
                raise TaskError("TY_ACCOUNTS 行格式无效：必须填写非空用户名|非空密码，仅切分第一个 |")
            if dry:
                log("✅ 凭据格式检查通过；登录与签到仅模拟")
                stats["skipped"] += 1
            else:
                if index > 1:
                    time.sleep(random.uniform(10, 30))
                client = TianYiYunPan(username.strip(), password, index)
                if not client.login():
                    raise TaskError(client.last_error or "登录未通过")
                stats["success"] += 1
            log(f"账号{index} 阶段1/{task_count}结束，耗时{time.monotonic()-stamp:.2f}秒")
            stage, stamp = 2, time.monotonic()
            log(f"账号{index} 阶段2/{task_count}：{'模拟签到（无网络、无副作用）' if dry else '每日签到'}")
            if dry:
                stats["skipped"] += 1
            else:
                stats[client.sign_in()] += 1
            log(f"账号{index} 阶段2/{task_count}结束，耗时{time.monotonic()-stamp:.2f}秒")
            # 奖励任务独立失败不会阻止后续奖励；登录或签到未确认则不尝试奖励。
            for stage, (label, task_id) in enumerate(enabled_draws, 3):
                stamp = time.monotonic()
                log(f"账号{index} 阶段{stage}/{task_count}：{'模拟' if dry else ''}{label}")
                try:
                    if dry:
                        stats["skipped"] += 1
                        log("⏭️ 仅模拟已有机会的奖励抽取；无网络、无副作用")
                    else:
                        stats[client.draw_prize(task_id)] += 1
                except Exception as error:
                    detail = label + "：" + diagnostic(error)
                    failure_detail += ("；" if failure_detail else "") + detail
                    stats["failed"] += 1
                    log(f"❌ 账号{index} {detail}；未确认业务成功")
                log(f"账号{index} 阶段{stage}/{task_count}结束，耗时{time.monotonic()-stamp:.2f}秒")
        except Exception as error:
            failure_detail = diagnostic(error)
            if stage == 2 and client:
                failure_detail = client.phase + "：" + failure_detail
            stats["failed"] += 1
            remaining = task_count - stage
            stats["skipped"] += remaining
            log(f"❌ 账号{index} 阶段{stage}/{task_count}失败，耗时{time.monotonic()-stamp:.2f}秒；{diagnostic(error)}；未确认业务成功")
            for skipped_stage in range(stage + 1, task_count + 1):
                log(f"⏭️ 账号{index} 阶段{skipped_stage}/{task_count}：前置阶段失败，跳过；耗时0.00秒")
        finally:
            if client:
                client.session.close()
        for key in totals:
            totals[key] += stats[key]
        results.append({"account": index, "ok": stats["failed"] == 0, **stats, "failure": failure_detail})
        log(f"账号{index} 统计：总任务{task_count}，成功{stats['success']}，已完成{stats['already']}，跳过{stats['skipped']}，失败{stats['failed']}，耗时{time.monotonic()-begin:.2f}秒")
    success = sum(r["ok"] for r in results)
    failed = len(lines)-success
    status = "configuration-error" if config_error else ("partial-failure" if failed and success else "failure" if failed else "dry-run" if dry else "success")
    body = f"状态：{status}；账号总数：{len(lines)}；成功：{success}；失败：{failed}；子任务：成功{totals['success']}、已完成{totals['already']}、跳过{totals['skipped']}、失败{totals['failed']}"
    if config_detail:
        body += "\n配置说明：" + config_detail
    for result in results:
        if result["failure"]:
            body += f"\n账号{result['account']}：{result['failure']}"
    delivery = notify(body, dry)
    log("----------------------------------------")
    log(body)
    log(f"完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；总耗时：{time.monotonic()-started:.2f}秒；通知：{delivery}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"status": status, "mode": "dry-run" if dry else "live", "accounts": len(lines), "success": success, "failed": failed, "tasks": totals, "results": results, "notification": delivery}, ensure_ascii=False))
    return 1 if config_error or failed else 0


if __name__ == "__main__":
    sys.exit(main())
