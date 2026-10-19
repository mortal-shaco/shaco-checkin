#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 领克App每日签到分享
# cron: 1 2 * * *
"""
领克App独立维护版；来源 zhaosongbing/LynkCoHelper-QingLong，MIT 许可。
保留原生网关签名、AppCode→HMAC续期、静态令牌回退、签到、积分及文章分享。
原始文件未附独立版权声明；原作者署名及 MIT 许可在本文件保留。

参数：LYNKCO_ACCOUNTS 每个非空行是一个 JSON 对象：
  refreshToken、deviceId 配套，或 token；可同时设置 token 作续期失败回退。
从本人领克App登录/刷新请求中获取 centerTokenDto.token、refreshToken 与 deviceId。
LYNKCO_APP_SECRETS 是 JSON 对象，字段 nativeAppKey、nativeAppSecret、
nativeAppCode、glDevId；从本人合法获取的App配置/请求头取得，不提供内置密钥。
兼容旧 LYNKCO_REFRESH_TOKEN、LYNKCO_DEVICE_ID、LYNKCO_TOKEN，每行一个值，
按行配对；不以 & 或 @ 分账号，不广播单个设备标识到多个账号。
LYNKCO_ENV_FILE 仅在显式设置时读取旧配置，不回写；多账号不读取其 user 段。
LYNKCO_DO_SHARE 默认1，设0只签到和查积分；分享只上报文章，不发布文本。
LYNKCO_SHARE_MODE 默认simple，设full使用完整三步链，需 LYNKCO_CONTENT_ID；
simple失败且提供CONTENT_ID时保留完整链回退。可用LYNKCO_ARTICLE_ID固定文章。
LYNKCO_TIMEOUT默认30秒，LYNKCO_ENERGY_DELAY默认5秒。
LYNKCO_DRY_RUN=1完全断网，检查配置与演练步骤，不宣称真实业务成功。
QINGLONG_NOTIFY 未设置时按上架状态；兼容LYNKCO_QL_NOTIFY。可选Bark通知变量保留。
不自动安装依赖，不运行交互短信登录/验证码服务器，不缓存或写入凭据。
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
        _ql_notify_identities = ('c087eb48daa78349', 'scripts/lynkco_qinglong_single.py', 'lynkco_qinglong_single.py', 'lynkco_qinglong_single')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
# MIT License — upstream: zhaosongbing/LynkCoHelper-QingLong
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import base64
import hashlib
import hmac
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlencode

BASE_URL = "https://app-api-gw-toc.lynkco.com"
NATIVE_BASE_URL = "https://app-services.lynkco.com.cn"
NATIVE_ANDROID_UA = "ALIYUN-ANDROID-UA"
APP_VERSION = "4.2.7"
ANDROID_APP_BUILD = "402071520"
IOS_APP_BUILD = "40203073"
EP_SIGN_DAY_INFO = "/up/api/v1/user/sign/day/info"
EP_SIGN_UPGRADE = "/up/api/v1/user/sign/upgrade"
EP_CONTINUE_DAYS = "/up/api/v1/userReward/getContinueDaysAndSignCard"
EP_MY_ENERGY = "/app/energy/myEnergy"
EP_GET_SHARE_CODE = "/app/v1/task/getShareCode"
EP_SHARE_LOOKUP = "/app/v1/task/shareCodeToUserId"
EP_SHARE_CHECK = "/app/v1/task/shareContentContectCheck"
EP_SHARE_REPORT = "/app/v1/task/shareContentContectReporting"
EP_SHARE_REPORTING_SIMPLE = "/app/v1/task/shareReporting"
EP_EXPLORE_SQUARE_INDEX = "/app/explore/home-page/square/index2"
DEFAULT_SHARE_ARTICLE_ID = "2075054309774663680"
H5_SHARE_ORIGIN = "https://h5.lynkco.com"
SECRETS = {}
TIMEOUT = 30
DRY_RUN = False

class TaskError(Exception):
    pass


def enabled(name, default="1"):
    return os.getenv(name, default).strip().lower() not in ("0", "false", "no", "off")


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def _get_secret(name):
    keys = {"NATIVE_APP_KEY": "nativeAppKey", "NATIVE_APP_SECRET": "nativeAppSecret",
            "NATIVE_APP_CODE": "nativeAppCode", "LOGIN_APP_CODE": "loginAppCode",
            "NATIVE_GL_DEV_ID": "glDevId"}
    value = SECRETS.get(keys[name])
    if not isinstance(value, str) or not value.strip():
        raise TaskError("签名配置缺少 " + keys[name])
    return value


def _format_gmt_date():
    # HTTP日期必须使用英文星期和月份，避免本地语言影响签名。
    from email.utils import formatdate
    return formatdate(usegmt=True)


def device_headers():
    return {"gl_dev_name": "sdk_gphone64_arm64", "gl_dev_model": "sdk_gphone64_arm64",
            "gl_dev_brand": "Google", "gl_dev_platform": "android", "gl_os_version": "33",
            "gl_app_version": APP_VERSION, "gl_app_build": ANDROID_APP_BUILD,
            "gl_dev_id": _get_secret("NATIVE_GL_DEV_ID")}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("拒绝重定向，防止凭据发送到其他地址")


class Response:
    def __init__(self, data):
        self.data = data
    def json(self):
        return self.data


def http(method, url, headers=None, params=None, data=None):
    if DRY_RUN:
        raise TaskError("预演禁止网络请求")
    if params:
        url += "?" + urlencode(params)
    # 凭据只发送到固定领克HTTPS服务；Bark有独立固定目标。
    if not url.startswith((BASE_URL + "/", NATIVE_BASE_URL + "/", "https://api.day.app/")):
        raise TaskError("请求目标未获允许")
    safe_headers = {k: v for k, v in (headers or {}).items() if not k.startswith("_")}
    try:
        req = Request(url, data=data, headers=safe_headers, method=method)
        with build_opener(NoRedirect).open(req, timeout=TIMEOUT) as response:
            if not 200 <= response.status < 300:
                raise TaskError("HTTP请求失败")
            payload = response.read(1024 * 1024 + 1)
        if len(payload) > 1024 * 1024:
            raise TaskError("响应超过大小限制")
        result = json.loads(payload.decode("utf-8"))
        if not isinstance(result, dict):
            raise TaskError("响应结构异常")
        return Response(result)
    except TaskError:
        raise
    except Exception:
        # 异常可能包含URL查询中的凭据；禁止打印异常正文。
        raise TaskError("网络、HTTP或JSON响应失败，请核对网络及凭据") from None


def accepted(value, kind="code"):
    if not isinstance(value, dict):
        return False
    if value.get("success") is False:
        return False
    if kind == "sign":
        return value.get("success") is True
    return str(value.get("code")) in ("success", "200") or value.get("success") is True


def checked(value, kind="code"):
    if not accepted(value, kind):
        raise TaskError("接口未确认业务成功")
    return value


class ClientBase:
    def __init__(self, token):
        if not token:
            raise TaskError("缺少账号令牌")
        self.token = token if token.startswith("bearer") else "bearer" + token

    def _request(self, method, path, **kwargs):
        extra = kwargs.pop("extra_headers", {})
        body = kwargs.pop("json", None)
        body = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode() if body is not None else None
        headers = build_native_signature(method, path, query=kwargs.get("params"),
            content_type="application/json; charset=utf-8",
            signature_headers_order="x-ca-nonce,x-ca-key,x-ca-timestamp", body=body)
        headers.update({"token": self.token, "ca_version": "1", "x-requiretoken": "false",
                        "User-Agent": NATIVE_ANDROID_UA})
        if isinstance(self, LynkCoShareClient):
            headers.update(device_headers())
            headers.update({"Origin": "https://h5.lynkco.cn", "Referer": "https://h5.lynkco.cn/"})
        headers.update(extra)
        return http(method, BASE_URL + path, headers=headers, data=body, **kwargs)

    def _native_request(self, method, path, body=None, **kwargs):
        extra = kwargs.pop("extra_headers", {}) or {}
        share = isinstance(self, LynkCoShareClient)
        headers = build_native_signature(method, path, query=kwargs.get("params"),
            content_type=("application/x-www-form-urlencoded; charset=utf-8" if share else "application/json; charset=utf-8"),
            signature_headers_order="x-ca-nonce,x-ca-key,x-ca-timestamp", body=body)
        headers.update({"token": self.token, "ca_version": "1", "User-Agent": NATIVE_ANDROID_UA})
        if share:
            headers.update({"svcsid": self.token, "appversion": APP_VERSION,
                "appVersionCode": APP_VERSION, "appVersionName": ANDROID_APP_BUILD, "publicPlatform": "android"})
            headers.update(device_headers())
        else:
            headers["x-requiretoken"] = "false"
        headers.update(extra)
        return http(method, BASE_URL + path, headers=headers, data=body, **kwargs)


class LynkCoSignClient(ClientBase):
    def get_sign_day_info(self):
        return checked(self._request("GET", EP_SIGN_DAY_INFO).json(), "sign")
    def do_sign(self):
        return checked(self._native_request("POST", EP_SIGN_UPGRADE, body=b"{}").json(), "sign")
    def get_continue_days(self):
        return checked(self._request("GET", EP_CONTINUE_DAYS).json())


def build_native_signature(method: str, path: str, query: dict = None,
                            accept: str = "application/json; charset=utf-8",
                            content_type: str = "application/x-www-form-urlencoded; charset=utf-8",
                            signature_headers_order: str = "x-ca-nonce,x-ca-timestamp,x-ca-key",
                            body: bytes = None,
                            extra_ca_headers: dict = None,
                            signature_header_items: list = None) -> dict:
    """
    复刻领克 App 原生 SDK 访问 app-services.lynkco.com.cn 网关的签名逻辑，
    对照阿里云官方 SDK `SignUtil.buildStringToSign` 实现：

        METHOD\\n Accept\\n Content-MD5\\n Content-Type\\n Date\\n
        (参与签名的 header，每行 "name:value\\n") path(?排序后的query)

    参数说明：
        extra_ca_headers: 额外的 x-ca- 前缀头，与默认的 x-ca-key/nonce/timestamp
            一起按字典序排序参与签名。
        signature_header_items: 传入 [(name, value), ...] 可完全自定义参与签名
            的 header 集合/顺序/大小写（部分接口如 iOS 端登录需要），不传则用默认模式。
        body: 传入则计算 Content-MD5 = Base64(MD5(body))，部分登录接口会校验，
            默认接口（refresh/getShareCode）无需传。

    签名 = Base64(HMAC-SHA256(待签名字符串, appSecret))
    """
    nonce = str(uuid.uuid4())
    timestamp = str(int(time.time() * 1000))
    date_str = _format_gmt_date()

    content_md5 = ""
    if body:
        content_md5 = base64.b64encode(hashlib.md5(body).digest()).decode()

    parts = [method.upper(), "\n", accept, "\n", content_md5, "\n", content_type, "\n", date_str, "\n"]

    if signature_header_items is not None:
        header_items = signature_header_items
        result_headers = {}
        for name, value in header_items:
            parts.append(f"{name}:{value}")
            parts.append("\n")
            result_headers[name] = value
    else:
        ca_headers = {
            "x-ca-key": _get_secret("NATIVE_APP_KEY"),
            "x-ca-nonce": nonce,
            "x-ca-timestamp": timestamp,
        }
        if extra_ca_headers:
            ca_headers.update(extra_ca_headers)
        for k in sorted(ca_headers.keys()):
            parts.append(f"{k}:{ca_headers[k]}")
            parts.append("\n")
        result_headers = dict(ca_headers)

    parts.append(path)
    if query:
        sorted_query = "&".join(f"{k}={v}" for k, v in sorted(query.items()) if v is not None and v != "")
        if sorted_query:
            parts.append("?")
            parts.append(sorted_query)

    string_to_sign = "".join(parts)
    digest = hmac.new(_get_secret("NATIVE_APP_SECRET").encode(), string_to_sign.encode(), hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode()

    result = dict(result_headers)
    result["x-ca-signature-headers"] = signature_headers_order
    result["x-ca-signature"] = signature
    result["date"] = date_str
    result["accept"] = accept
    result["content-type"] = content_type
    if content_md5:
        result["content-md5"] = content_md5
    result["_nonce"] = nonce
    result["_timestamp"] = timestamp
    return result

def _find_article(value) -> dict:
    """递归查找广场文章流中第一个“文章”类型内容，返回 {"articleId", "title"}，未找到则返回空 dict。"""
    if isinstance(value, dict):
        article_id = value.get("articleId")
        content_type = value.get("contentType") or value.get("contentTypeCode")
        if article_id and (not content_type or content_type in ("文章", "article")):
            return {"articleId": str(article_id), "title": value.get("title") if isinstance(value.get("title"), str) else ""}
        for child in value.values():
            found = _find_article(child)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_article(item)
            if found:
                return found
    return {}

class LynkCoShareClient(ClientBase):
    def get_share_code(self, article_id: str = None, account_id: str = None) -> dict:
            """
            获取本次分享专属的一次性 shareCode（GET /app/v1/task/getShareCode，走原生
            AppKey 签名）。请求头 risk_request_info 里携带了被分享文章的 id，之后必须原样
            作为 businessNo 传给 share_reporting()，网关会校验两者一致，否则虽返回 success
            但不会真正加分。

            参数:
                article_id: 被分享文章/内容的 id，不传则用 DEFAULT_SHARE_ARTICLE_ID 兜底（推荐
                    通过 do_share() 调用，会自动取最新文章）。
                account_id: 当前账号 accountId，用于填充 gl_user_id 风控头，不传则留空。
            """
            article_id = article_id or DEFAULT_SHARE_ARTICLE_ID
            share_content_url = (
                "https://h5.lynkco.com/app-h5/dist/web/pages/exploration/article/index.html"
                f"?id={article_id}&isShare=lynkco%3A%2F%2Fwx%2F%3FrouteUrl%3D%2Fpages%2Fexploration%2Farticle%2Findex.js%3Fid%3D{article_id}"
            )
            risk_request_info = json.dumps(
                {
                    "openTimeStamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "shareContentType": 1,
                    "shareContentURL": share_content_url,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            sweet_security_info = json.dumps(
                {
                    "appVersion": APP_VERSION, "platform": "android", "battery": "100",
                    "isCharging": "4", "isSetProxy": "true", "isUsbDebug": "false",
                    "isMockLocation": "false", "isRoot": "false",
                    "appSignature": "4F8393A255313DE42799571ABDF33A60",
                    # channel 为 URL-encoded 后的值（"%E5%90%89%E5%88%A9" = 吉利），
                    # HTTP 头只能是 ASCII 字符，直接放中文会被 requests 库报编码错。
                    "channel": "%E5%90%89%E5%88%A9", "screenResolution": "2400*1080", "brand": "google",
                    "model": "sdk_gphone64_arm64",
                    "geelyDeviceId": _get_secret("NATIVE_GL_DEV_ID"), "os": "android",
                    "osVersion": "13", "androidVersion": "33", "networkType": "WIFI",
                    "ip": "10.0.2.16", "wifiName": "AndroidWifi", "wifiSignalLevel": "-50",
                    "isLbsEnabled": "true", "lbsLatitude": "", "lbsLongitude": "",
                    "deviceToken": "",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            extra_headers = {
                "risk_type": "1",
                "risk_request_info": risk_request_info,
                "sweet_security_info": sweet_security_info,
                "os": "13",
            }
            if account_id:
                extra_headers["gl_user_id"] = account_id
            resp = self._native_request("GET", EP_GET_SHARE_CODE, extra_headers=extra_headers)
            return resp.json()

    def share_reporting(self, share_code: str, business_no: str = None,
                             first_classification: str = "文章", second_classification: str = "") -> dict:
            """
            分享上报（POST /app/v1/task/shareReporting?shareCode=<shareCode>，Origin 需为
            https://h5.lynkco.com）。网关会校验 businessNo 与 getShareCode 时的文章 id 是否
            一致。返回 success 不代表真正加分成功，需自行对比 myEnergy 的 point 字段确认。
            """
            business_no = business_no or DEFAULT_SHARE_ARTICLE_ID
            body = {
                "businessNo": business_no,
                "eventData": {
                    "firstClassification": first_classification,
                    "secondClassification": second_classification,
                },
            }
            resp = self._request(
                "POST", EP_SHARE_REPORTING_SIMPLE,
                params={"shareCode": share_code},
                json=body,
                extra_headers={"Origin": H5_SHARE_ORIGIN, "Referer": H5_SHARE_ORIGIN + "/"},
            )
            return resp.json()

    def share_lookup(self, share_code: str) -> dict:
            """（完整三步法-第1步）通过 shareCode 反查分享人 userId"""
            resp = self._request("POST", EP_SHARE_LOOKUP, json={"shareCode": share_code})
            return resp.json()

    def share_check(self, content_id: str, share_code: str) -> dict:
            """（完整三步法-第2步）分享前置校验"""
            resp = self._request("POST", EP_SHARE_CHECK, json={"contentId": content_id, "shareCode": share_code})
            return resp.json()

    def share_report(self, content_id: str, share_code: str) -> dict:
            """（完整三步法-第3步）真正上报分享、加能量体"""
            resp = self._request("POST", EP_SHARE_REPORT, json={"contentId": content_id, "shareCode": share_code})
            return resp.json()

    def get_latest_article(self):
        for page in range(1, 6):
            try:
                response = checked(self._request("POST", EP_EXPLORE_SQUARE_INDEX,
                    json={"dynamicSort": "new", "uniqueId": "", "refreshType": "MORE", "pageNo": page}).json())
                found = _find_article(response.get("data"))
                if found:
                    log(f"文章查询：第{page}页找到可分享文章")
                    return found
                log(f"文章查询：第{page}页未找到文章")
            except TaskError:
                log(f"文章查询：第{page}页失败，继续分页")
        log("⚠️ 动态文章不可用，使用上游备用文章")
        return {}

    def do_share(self, article_id=None, account_id=None, content_id=None, use_simple=True):
        article = self.get_latest_article() if not article_id else {}
        article_id = article_id or article.get("articleId") or DEFAULT_SHARE_ARTICLE_ID
        def code():
            info = checked(self.get_share_code(article_id, account_id))
            value = info.get("data")
            if not isinstance(value, str) or not value:
                raise TaskError("接口没有返回有效分享码")
            return value
        if use_simple:
            try:
                checked(self.share_reporting(code(), business_no=article_id))
                return {"ok": True, "via": "simple", "articleId": article_id,
                        "articleTitle": article.get("title", "")}
            except TaskError:
                if not content_id:
                    raise TaskError("分享两步链失败；未配置完整链所需内容编号") from None
                log("⚠️ 简化分享失败，回退完整三步链")
        if not content_id:
            raise TaskError("完整分享链需要 LYNKCO_CONTENT_ID")
        share_code = code()
        checked(self.share_lookup(share_code))
        checked(self.share_check(content_id, share_code))
        checked(self.share_report(content_id, share_code))
        return {"ok": True, "via": "full", "articleId": article_id,
                "articleTitle": article.get("title", "")}


def parse_refresh(data):
    if data.get("code") != "success":
        raise TaskError("续期接口未确认成功")
    payload = data.get("data")
    if not isinstance(payload, dict):
        raise TaskError("续期响应字段结构异常")
    dto = payload.get("centerTokenDto") or {}
    if not isinstance(dto, dict):
        raise TaskError("续期响应字段结构异常")
    if not isinstance(dto.get("token"), str) or not dto["token"]:
        raise TaskError("续期接口没有返回令牌")
    return dto["token"]


def load_token(account):
    refresh = account.get("refreshToken")
    device = account.get("deviceId")
    if refresh:
        path = "/auth/login/refresh"
        try:
            headers = {"Authorization": "APPCODE " + _get_secret("NATIVE_APP_CODE"),
                "accept": "application/json", "content-type": "application/json; charset=UTF-8",
                "publicplatform": "iOS", "user-agent": "CA_iOS_SDK_2.0", "token": "",
                "gl_dev_id": device, "appversioncode": APP_VERSION, "appversionname": IOS_APP_BUILD,
                "gl_app_version": APP_VERSION, "gl_app_build": IOS_APP_BUILD, "x-ca-version": "1"}
            token = parse_refresh(http("GET", NATIVE_BASE_URL + path, headers=headers,
                params={"refreshToken": refresh, "deviceId": device, "deviceType": "IOS", "appVersion": APP_VERSION}).json())
            log("✅ AppCode续期成功；令牌仅保存在本次进程内存")
            return token
        except TaskError:
            log("⚠️ AppCode续期失败，尝试HMAC签名续期")
        try:
            params = {"deviceId": device, "refreshToken": refresh}
            headers = build_native_signature("GET", path, params)
            headers.update({"ca_version": "1", "x-requiretoken": "false", "oauth": "false", "User-Agent": NATIVE_ANDROID_UA})
            headers.update(device_headers())
            token = parse_refresh(http("GET", NATIVE_BASE_URL + path, headers=headers, params=params).json())
            log("✅ HMAC签名续期成功；令牌仅保存在本次进程内存")
            return token
        except TaskError:
            log("⚠️ 两种续期方式均失败")
    if account.get("token"):
        log("使用配置的静态令牌，后续请求将核验有效性")
        return account["token"]
    raise TaskError("无法获得有效令牌，请重新从本人App获取凭据")


def lines(name):
    return [line.strip() for line in os.getenv(name, "").splitlines() if line.strip()]


def read_configuration():
    global SECRETS, TIMEOUT
    file_data = {}
    path = os.getenv("LYNKCO_ENV_FILE", "").strip()
    if path:
        try:
            file_data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(file_data, dict):
                raise ValueError()
        except Exception:
            raise TaskError("LYNKCO_ENV_FILE不是可读取的JSON对象") from None
    try:
        bundle = json.loads(os.getenv("LYNKCO_APP_SECRETS", "{}"))
        if not isinstance(bundle, dict):
            raise ValueError()
        SECRETS = dict(file_data.get("secrets") or {})
        SECRETS.update(bundle)
    except Exception:
        raise TaskError("LYNKCO_APP_SECRETS必须是JSON对象") from None
    for key, env in {"nativeAppKey": "LYNKCO_NATIVE_APP_KEY", "nativeAppSecret": "LYNKCO_NATIVE_APP_SECRET",
                     "nativeAppCode": "LYNKCO_NATIVE_APP_CODE", "loginAppCode": "LYNKCO_LOGIN_APP_CODE",
                     "glDevId": "LYNKCO_NATIVE_GL_DEV_ID"}.items():
        if os.getenv(env):
            SECRETS[key] = os.environ[env]
    # 同一行JSON可完整保留包含任何分隔符的凭据。
    accounts = []
    if os.getenv("LYNKCO_ACCOUNTS", "").strip():
        for line in lines("LYNKCO_ACCOUNTS"):
            try:
                account = json.loads(line)
                if not isinstance(account, dict):
                    raise ValueError()
                accounts.append(account)
            except Exception:
                accounts.append({"configurationError": True})
    else:
        refresh, devices, tokens = lines("LYNKCO_REFRESH_TOKEN"), lines("LYNKCO_DEVICE_ID"), lines("LYNKCO_TOKEN")
        count = max(len(refresh), len(devices), len(tokens))
        for index in range(count):
            accounts.append({"refreshToken": refresh[index] if index < len(refresh) else "",
                             "deviceId": devices[index] if index < len(devices) else "",
                             "token": tokens[index] if index < len(tokens) else ""})
        if not accounts and file_data.get("user"):
            accounts = [file_data["user"]]
    if not accounts:
        raise TaskError("未配置账号，请设置 LYNKCO_ACCOUNTS")
    for name in ("NATIVE_APP_KEY", "NATIVE_APP_SECRET"):
        _get_secret(name)
    if enabled("LYNKCO_DO_SHARE") or any(a.get("refreshToken") for a in accounts):
        _get_secret("NATIVE_GL_DEV_ID")
    try:
        TIMEOUT = float(os.getenv("LYNKCO_TIMEOUT", "30"))
        delay = float(os.getenv("LYNKCO_ENERGY_DELAY", "5"))
        if not (0 < TIMEOUT <= 120 and 0 <= delay <= 120):
            raise ValueError()
    except ValueError:
        raise TaskError("超时必须在(0,120]秒，积分等待必须在[0,120]秒") from None
    mode = os.getenv("LYNKCO_SHARE_MODE", "simple")
    if mode not in ("simple", "full"):
        raise TaskError("LYNKCO_SHARE_MODE必须是simple或full")
    if enabled("LYNKCO_DO_SHARE") and mode == "full" and not os.getenv("LYNKCO_CONTENT_ID"):
        raise TaskError("完整分享链必须配置 LYNKCO_CONTENT_ID")
    return accounts, delay


def validate_account(account):
    if account.get("configurationError"):
        raise TaskError("账号行不是有效JSON对象")
    for key in ("token", "refreshToken", "deviceId"):
        if key in account and not isinstance(account[key], str):
            raise TaskError("账号凭据字段必须是字符串")
    if account.get("refreshToken") and not account.get("deviceId"):
        raise TaskError("refreshToken必须配套同账号deviceId")
    if not (account.get("refreshToken") or account.get("token")):
        raise TaskError("账号缺少token或refreshToken")


def identity(response):
    data = response.get("data")
    if isinstance(data, dict):
        # 只展示官方明确的非秘密身份字段，不打印任意响应内容。
        for key in ("nickname", "nickName", "username", "displayName", "publicUid", "uid", "userId", "accountId"):
            value = data.get(key)
            if isinstance(value, (str, int)) and value != "":
                text = str(value)
                if key in ("nickname", "nickName", "username", "displayName"):
                    import re
                    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
                # 防止错误响应把已知凭据放入身份字段。
                secrets = list(SECRETS.values()) + list(ACTIVE_ACCOUNT.values())
                if any(isinstance(s, str) and s and s in text for s in secrets):
                    continue
                log("官方账号身份：" + text.replace("\n", " ").replace("\r", " "))
                return


def public_title(value):
    import re
    text = str(value).replace("\n", " ").replace("\r", " ")
    for secret in list(SECRETS.values()) + list(ACTIVE_ACCOUNT.values()):
        if isinstance(secret, str) and secret:
            text = text.replace(secret, "[REDACTED]")
    return re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[REDACTED]", text)


ACTIVE_ACCOUNT = {}


def energy(client):
    result = checked(client._request("GET", EP_MY_ENERGY).json())
    identity(result)
    data = result.get("data")
    if not isinstance(data, dict) or "point" not in data:
        raise TaskError("积分响应缺少point字段")
    try:
        value = float(data["point"])
        if not __import__("math").isfinite(value):
            raise ValueError()
    except (TypeError, ValueError):
        raise TaskError("积分字段格式异常") from None
    log(f"当前能量体积分：{value:g}")
    return value


def run_account(index, account, delay):
    global ACTIVE_ACCOUNT
    ACTIVE_ACCOUNT = account
    start = time.monotonic()
    stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    result = {"already_signed": False, "day_info": None, "sign_result": None, "share_result": None,
              "energy_before": None, "energy_after": None, "continue_info": None}
    def stage(name, function, skip=False):
        stats["total"] += 1
        clock = time.monotonic()
        log(f"账号{index} · 阶段{stats['total']}：{name}")
        state = "skipped" if skip or DRY_RUN else "success"
        value = None
        try:
            if DRY_RUN:
                log("⏭️ 断网预演：检查流程，不发送请求、不改变业务状态")
            elif skip:
                log("⏭️ 配置关闭或前置条件未满足")
            else:
                value = function()
                if isinstance(value, dict) and value.get("already_signed"):
                    state = "alreadyComplete"
                log("☑️ 今日已完成" if state == "alreadyComplete" else "✅ 业务结果已核验")
        except Exception as exc:
            state = "failed"
            # 只允许本程序定义的固定错误信息进入日志。
            log("❌ " + (str(exc) if isinstance(exc, TaskError) else "处理失败，响应字段或运行环境异常"))
        stats[state] += 1
        log(f"账号{index} · 阶段{stats['total']}结束：{state}，耗时{time.monotonic()-clock:.2f}秒")
        return value
    log(f"===== 账号{index}开始 =====")
    try:
        validate_account(account)
    except TaskError as exc:
        log("❌ 账号配置错误：" + str(exc))
        stats.update(total=1, failed=1)
    else:
        token = stage("令牌获取与续期", lambda: load_token(account))
        if token:
            ACTIVE_ACCOUNT = dict(account, token=token)
        if DRY_RUN:
            # 预演同时构造原生签名，检查凭据类型及签名契约，不请求接口。
            try:
                build_native_signature("POST", EP_SIGN_UPGRADE, content_type="application/json; charset=utf-8", body=b"{}")
                log("✅ DRY_RUN 签名构造检查通过")
            except Exception:
                stats["failed"] += 1
                stats["total"] += 1
                log("❌ DRY_RUN 签名配置异常")
        client = LynkCoSignClient(token) if token else None
        result["energy_before"] = stage("查询任务前积分", lambda: energy(client), skip=not token)
        def sign():
            info = client.get_sign_day_info()
            identity(info)
            status = (info.get("data") or {}).get("signStatus")
            result["day_info"] = {"success": True, "data": {"signStatus": status}}
            if status not in (0, 1):
                raise TaskError("签到状态不明确，停止写操作")
            if status == 1:
                result["already_signed"] = True
                return {"already_signed": True}
            sign_response = client.do_sign()
            if (client.get_sign_day_info().get("data") or {}).get("signStatus") != 1:
                raise TaskError("签到请求已提交，但复查未确认今日签到")
            reward = (sign_response.get("data") or {}).get("rewardEnergyNumber")
            result["sign_result"] = {"success": True, "data": {}}
            if isinstance(reward, (int, float)):
                result["sign_result"]["data"]["rewardEnergyNumber"] = reward
                log(f"签到奖励能量体：{reward}")
        stage("查询签到状态并签到", sign, skip=not token)
        def continued():
            data = client.get_continue_days()
            identity(data)
            info = data.get("data") or {}
            safe = {}
            if isinstance(info, dict):
                for key in ("continueDays", "signCard", "signCardCount", "signCardNumber", "continueSignDays"):
                    if isinstance(info.get(key), (int, float)):
                        log(f"连续签到信息 {key}：{info[key]}")
                        safe[key] = info[key]
            return {"success": True, "data": safe}
        result["continue_info"] = stage("连续签到天数及签到卡查询", continued, skip=not token)
        def share():
            before = energy(client)
            share_client = LynkCoShareClient(token)
            response = share_client.do_share(article_id=os.getenv("LYNKCO_ARTICLE_ID") or None,
                content_id=os.getenv("LYNKCO_CONTENT_ID") or None,
                use_simple=os.getenv("LYNKCO_SHARE_MODE", "simple") == "simple")
            time.sleep(delay)
            after = energy(client)
            log(f"分享链路：{response['via']}；分享前后积分变化：{after-before:g}")
            if after <= before:
                raise TaskError("分享上报已受理，但未核验到加分；可能已达每日上限，请在App核对")
            title = public_title(response.get("articleTitle", ""))
            if title:
                log("分享文章：" + title)
            return {"ok": True, "via": response["via"], "pointsDelta": after-before,
                    "articleId": response["articleId"], "articleTitle": title}
        result["share_result"] = stage("文章分享上报及积分核验", share, skip=not token or not enabled("LYNKCO_DO_SHARE"))
        def after():
            time.sleep(delay)
            return energy(client)
        result["energy_after"] = stage("查询任务后积分", after, skip=not token)
    ok = stats["failed"] == 0 and (DRY_RUN or stats["skipped"] <= (0 if enabled("LYNKCO_DO_SHARE") else 1))
    stats["seconds"] = round(time.monotonic()-start, 3)
    log(f"账号{index}统计：总任务{stats['total']}，成功{stats['success']}，已完成{stats['alreadyComplete']}，跳过{stats['skipped']}，失败{stats['failed']}，耗时{stats['seconds']}秒")
    # 保留原编排结果字段，输出只包含核验摘要而非服务端原始响应。
    for key in ("energy_before", "energy_after"):
        value = result[key]
        if value is not None:
            result[key] = {"success": True, "data": {"point": value}}
    print(json.dumps({"account": index, "ok": ok, "mode": "dry-run" if DRY_RUN else "live", **result}, ensure_ascii=False))
    return {"account": index, "ok": ok, "statistics": stats}


def notify_summary(body):
    if not enabled("QINGLONG_NOTIFY"):
        log("⏭️ QINGLONG_NOTIFY已关闭通知")
        return "disabled"
    delivered = False
    if enabled("LYNKCO_QL_NOTIFY"):
        paths = []
        directory = os.getenv("QINGLONG_NOTIFY_DIR", "")
        if directory:
            paths.append(Path(directory) / "notify.py")
        paths += [Path(__file__).parent / "notify.py", Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
        try:
            spec = importlib.util.find_spec("notify")
            if spec and spec.origin:
                paths.insert(0, Path(spec.origin))
        except Exception:
            pass
        # 子进程隔离通知模块，限定超时、禁止其输出，保护业务退出码。
        code = '''import sys, socket, importlib.util
if sys.argv[4] == "1":
    def deny(*a, **k): raise RuntimeError("dry-run: network disabled")
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
    socket.socket.sendto = deny
spec = importlib.util.spec_from_file_location("ql_notify", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.send(sys.argv[2], sys.argv[3])
'''
        for path in dict.fromkeys(paths):
            if path.is_file():
                try:
                    subprocess.run([sys.executable, "-c", code, str(path), "领克App每日签到分享", body, "1" if DRY_RUN else "0"],
                        timeout=20, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    delivered = True
                    break
                except Exception:
                    log("⚠️ 青龙Python通知不可用，业务退出码保持不变")
        if not delivered and not DRY_RUN:
            node_paths = ([Path(directory) / "sendNotify.js"] if directory else []) + [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
            for path in node_paths:
                if path.is_file():
                    try:
                        subprocess.run(["node", "-e", "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1));", str(path), "领克App每日签到分享", body],
                            timeout=20, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        delivered = True
                        break
                    except Exception:
                        log("⚠️ 青龙Node通知不可用，业务退出码保持不变")
    key = os.getenv("LYNKCO_BARK_KEY", "")
    if key and not DRY_RUN:
        try:
            payload = {"title": "领克App每日签到分享", "markdown": body, "group": "LynkCo签到", "level": "active"}
            if os.getenv("LYNKCO_BARK_ICON"):
                payload["icon"] = os.environ["LYNKCO_BARK_ICON"]
            # Key只出现在固定目标URL，不记录请求URL和异常。
            from urllib.parse import quote
            checked(http("POST", "https://api.day.app/" + quote(key, safe=""),
                headers={"Content-Type": "application/json; charset=utf-8"}, data=json.dumps(payload).encode()).json())
            log("✅ Bark摘要通知已发送")
        except Exception:
            log("⚠️ Bark通知失败，业务退出码保持不变")
    state = "delivered" if delivered else ("dry-run-unavailable" if DRY_RUN else "unavailable")
    log("通知状态：" + state + ("（预演禁止联网）" if DRY_RUN else ""))
    return state


def main():
    global DRY_RUN
    DRY_RUN = enabled("LYNKCO_DRY_RUN", "0")
    if DRY_RUN:
        def deny(*args, **kwargs):
            raise TaskError("预演禁止网络")
        socket.socket.connect = deny
        socket.socket.connect_ex = deny
        socket.create_connection = deny
        socket.getaddrinfo = deny
        socket.socket.sendto = deny
    start = time.monotonic()
    log("========== 领克App每日签到分享 ==========")
    log("开始时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
    log("运行模式：" + ("完全断网预演" if DRY_RUN else "正式运行"))
    summaries = []
    count = max(len(lines("LYNKCO_ACCOUNTS")), len(lines("LYNKCO_REFRESH_TOKEN")), len(lines("LYNKCO_DEVICE_ID")), len(lines("LYNKCO_TOKEN")))
    configuration_error = False
    try:
        accounts, delay = read_configuration()
        count = len(accounts)
        log(f"账号总数：{count}")
        for index, account in enumerate(accounts, 1):
            summaries.append(run_account(index, account, delay))
    except Exception as exc:
        configuration_error = True
        log(f"账号总数：{count}")
        log("❌ 配置或执行错误：" + (str(exc) if isinstance(exc, TaskError) else "配置格式或运行环境异常"))
    success = sum(item["ok"] for item in summaries)
    failed = count - success
    status = ("configuration-error" if configuration_error else "failure" if failed == count and failed else
              "partial-failure" if failed else "dry-run" if DRY_RUN else "success")
    code = 1 if configuration_error or failed else 0
    log("--------------------------------------------------------")
    log(f"任务统计：账号总数{count}，成功{success}，失败{failed}")
    totals = {key: sum(item["statistics"][key] for item in summaries) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log("子任务统计：" + json.dumps(totals, ensure_ascii=False))
    body = f"状态：{status}\n账号总数：{count}\n成功：{success}\n失败：{failed}\n配置错误：{'是' if configuration_error else '否'}"
    notification = notify_summary(body)
    elapsed = round(time.monotonic()-start, 3)
    finish = time.strftime("%Y-%m-%d %H:%M:%S")
    log(f"总耗时：{elapsed}秒；完成时间：{finish}")
    log("最终状态：" + status)
    if DRY_RUN and not code:
        log("✅ DRY_RUN_OK：断网预演通过；未验证真实业务")
    elif not code:
        log("✅ LYNKCO_TASK_SUCCESS：所有账号业务核验通过")
    print("TASK_SUMMARY=" + json.dumps({"status": status, "mode": "dry-run" if DRY_RUN else "live",
        "accounts": count, "success": success, "failed": failed, "configurationError": configuration_error,
        "accountResults": summaries, "tasks": totals, "notification": notification,
        "elapsedSeconds": elapsed, "finishTime": finish, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
