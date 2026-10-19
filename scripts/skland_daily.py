#!/usr/bin/env python3
# name: 森空岛每日任务
# cron: 33 1 * * *
# SPDX-License-Identifier: MIT
# 合并来源：AdiEcho/skyland-auto-sign-ql，skyland.py，Author: AdiEcho，Update: 2026/1/29
# 来源提交：2497b43c9b764e054dadd2dd86e354dacaffc840
# 终末地接口交叉参考：e02ed814df52c998、0bde30a1db078051（MIT）。
# 合并来源：bwmgd/skyland-auto-sign，skyland.py，Author: Bwmgd，Update: 2024/10/09
# 原始归属：https://github.com/xxyz30/skyland-auto-sign
# 镜像归属：https://gitee.com/FancyCabbage/skyland-auto-sign
# 原始签到调度：0 30 8 * * *（青龙六字段）；仅签到可配置 30 8 * * *。
# 上游：siwuli/skland-daily，skland_daily.py
# 来源提交：c6159b4ca574b4493ae8b94e56a861c7e9e06955
# 原文件未包含版权声明；保留原功能实现及作者归属。
# MIT License
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
"""森空岛每日任务：版区检票、浏览、点赞、分享。

森空岛的每个版区都有独立的每日检票，检票之后还可以通过浏览、点赞、分享
版区帖子领取当天的社区任务奖励。本脚本使用鹰角网络通行证凭据登录，自动
完成上述操作，支持单账号与多账号。

既可作为青龙面板的定时任务运行，也可在命令行独立运行。

环境变量及获取方法:
    SKLAND_TOKEN 必填规范账号变量，每个非空行一个账号，禁止用分号、逗号、&或@分隔账号。
      登录官方鹰角通行证网页后，在开发者工具中查看本人登录响应里的 token；
      或在森空岛官方客户端抓取本人授权响应的 cred 和 token，写为 cred:token；
      也支持单行 JSON {"cred":"本人凭据","token":"本人签名凭据"}，
      以及官方 web-api 返回的 {"data":{"content":"本人通行证凭据"}}。
      账密登录可使用单行 JSON {"phone":"本人手机号","password":"本人密码"}，
      两项须属于同一个账号；不要将凭据发给他人。
    SKLAND_PHONE / SKLAND_PASSWORD 兼容旧账密输入，必须成对设置。
    SKLAND_TOKEN_N / SKLAND_PHONE_N / SKLAND_PASSWORD_N 兼容旧序号输入。
    SKLAND_DID 可选，本人官方客户端请求头的 dId；未设置时自动注册设备标识。
    SKLAND_ZONE_IDS 逗号分隔的 gameId，从官方版区列表接口获取；默认全部。
    SKLAND_ACTIONS 默认 checkin,view；点赞和分享改变账号状态，显式添加 like,share。
    attendance 为明日方舟绑定角色签到（领取游戏奖励），与社区 checkin 不同。
    SKLAND_ACTIONS=attendance 可只运行原始签到；attendance,checkin,view 可一起运行。
    endfield 为终末地绑定角色签到，必须显式开启，不改变 attendance 的明日方舟语义。
    SKLAND_ACTIONS=attendance,endfield 可运行上游两种游戏签到，调度可设 30 8 * * *。
    终末地自动读取绑定接口中的 roles，无需另配角色凭据；单角色失败继续其余角色。
    SKLAND_ZONE_IDS 只筛选社区版区，不筛选游戏绑定角色。
    SKYLAND_TYPE 为原脚本未使用的兼容变量，无业务效果。
    SKLAND_VIEW_COUNT / SKLAND_LIKE_COUNT / SKLAND_SHARE_COUNT 默认 5/10/1。
    SKLAND_NOTIFY_URL 可选 HTTPS 自有通知服务，发送脱敏 JSON 汇总。
    SKLAND_DRY_RUN=1 完全断网，只校验配置和模拟流程，不登录、不发通知请求。
    QINGLONG_NOTIFY 未设置时按上架状态，0/false/no/off 关闭通知。
    QINGLONG_NOTIFY_DIR 可选，青龙 notify.py 所在目录。

命令行:
    python3 candidate.py [--dry-run] [--actions checkin,view] [--zones 1,2]
建议每天 08:00 运行；上游未给出定时表达式。分享接口只记任务次数，不发布文本。

退出码:
    0 全部账号成功；1 存在失败或配置错误，便于定时任务判断执行结果。
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
        _ql_notify_identities = ('96b3c22e1eff9659', 'scripts/skland_daily.py', 'skland_daily.py', 'skland_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
import base64
import hashlib
import hmac
import json
import logging
import io
import signal
import importlib.util
import importlib
from pathlib import Path
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlencode

from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError


class HttpFailure(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpResponse:
    def __init__(self, status, body):
        self.status_code = status
        self.body = body

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    def raise_for_status(self):
        if not 200 <= self.status_code < 300:
            raise HttpFailure("HTTP 请求失败")


class HttpClient:
    """标准库 HTTP 实现：TLS 校验、超时、响应大小限制、禁止重定向。"""
    def request(self, method, url, *, params=None, data=None, headers=None,
                timeout=30, allow_redirects=False, json=None):
        if params:
            url += ("&" if "?" in url else "?") + params
        headers = dict(headers or {})
        if json is not None:
            data = compact_json(json)
            headers["content-type"] = "application/json"
        if isinstance(data, str):
            data = data.encode("utf-8")
        request = Request(url, data=data, headers=headers, method=method)
        try:
            try:
                response = build_opener(NoRedirect()).open(request, timeout=timeout)
            except HTTPError as exc:
                response = exc
            with response:
                body = response.read(2097153)
                if len(body) > 2097152:
                    raise HttpFailure("响应过大")
                return HttpResponse(response.code, body)
        except (URLError, OSError, ValueError):
            raise HttpFailure("网络请求失败") from None

    def close(self):
        pass

    @classmethod
    def post(cls, url, **kwargs):
        return cls().request("POST", url, **kwargs)


__version__ = "1.0.0"

# --------------------------------------------------------------- 服务常量 --

ZONAI_BASE = "https://zonai.skland.com"
HYPERGRYPH_BASE = "https://as.hypergryph.com"
DEVICE_PROFILE_URL = "https://fp-it.portal101.cn/deviceprofile/v4"

#: 森空岛应用标识，用于把鹰角通行证 token 换成授权码
SKLAND_APP_CODE = "4ca99fa6b56cc2ba"

#: 设备指纹服务使用的应用标识
DEVICE_ORGANIZATION = "UWXspnCCJN4sfYlNfqps"
DEVICE_APP_ID = "default"

PLATFORM = "3"
VERSION_NAME = "1.0.0"

#: 签名时间戳相对服务端的时间补偿（秒）
TIMESTAMP_OFFSET = 2

APP_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Version/4.0 Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1"
)
WEB_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 30.0
DEVICE_PROFILE_TIMEOUT = 10.0

#: 连续请求之间的间隔，避免对接口造成无谓压力
REQUEST_INTERVAL = 0.3

#: 网络异常与 5xx 的重试次数
REQUEST_RETRIES = 2

#: 点赞动作的接口动作码
ACTION_CODE_LIKE = 12

#: 帖子流使用的分类类型，kind=20 为综合讨论区
POST_CATE_KIND = 20
#: 帖子排序方式，4 表示按最新回复
POST_SORT_TYPE = "4"
POST_PAGE_SIZE = "10"
#: 单页取不满时的最大翻页次数
POST_MAX_PAGES = 3

ACTION_CHECKIN = "checkin"
ACTION_VIEW = "view"
ACTION_LIKE = "like"
ACTION_SHARE = "share"
ACTION_ATTENDANCE = "attendance"
ACTION_ENDFIELD = "endfield"
ALL_ACTIONS = (ACTION_CHECKIN, ACTION_VIEW, ACTION_LIKE, ACTION_SHARE, ACTION_ATTENDANCE, ACTION_ENDFIELD)

#: 服务端提示"今天已经签到过"的文案特征
ALREADY_SIGNED_HINTS = ("重复签到", "已签到", "已检票")

log = logging.getLogger("skland")


# ----------------------------------------------------------------- 异常 --

class SklandError(Exception):
    """脚本可预期的错误：配置、网络或接口返回异常。"""


class SklandApiError(SklandError):
    """接口返回了业务错误码。"""

    def __init__(self, message: str, code: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code


# ----------------------------------------------------------------- 签名 --

def compact_json(value: Dict[str, Any]) -> str:
    """按签名要求序列化：无多余空白，保留非 ASCII 字符原样。"""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


class Signer:
    """森空岛接口签名。

    签名内容由「请求路径 + 查询串 + 请求体 + 时间戳 + 公共头」拼接而成，
    再依次经过 HMAC-SHA256（密钥为签名 token）与 MD5 两级摘要。
    公共头的字段顺序参与签名，构造时不可调整。
    """

    @staticmethod
    def sign(
        path: str,
        *,
        token: str,
        timestamp: str,
        headers: Dict[str, str],
        query: Optional[Dict[str, Any]] = None,
        body: Optional[str] = None,
    ) -> str:
        payload = "{}{}{}{}{}".format(
            path,
            urlencode(query or {}),
            body or "",
            timestamp,
            compact_json(headers),
        )
        digest = hmac.new(
            token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hashlib.md5(digest.encode("utf-8")).hexdigest()

    @classmethod
    def build_headers(
        cls,
        path: str,
        *,
        cred: str,
        token: str,
        did: str,
        query: Optional[Dict[str, Any]] = None,
        body: Optional[str] = None,
        now: Optional[int] = None,
    ) -> Dict[str, str]:
        """生成一次请求所需的完整请求头（含签名）。"""
        timestamp = str((int(time.time()) if now is None else now) - TIMESTAMP_OFFSET)
        common = {
            "platform": PLATFORM,
            "timestamp": timestamp,
            "dId": did,
            "vName": VERSION_NAME,
        }
        headers = {
            "user-agent": APP_USER_AGENT,
            "accept-encoding": "identity",
            "connection": "close",
            "x-requested-with": "com.hypergryph.skland",
            "cred": cred,
            "sign": cls.sign(
                path, token=token, timestamp=timestamp, headers=common, query=query, body=body
            ),
        }
        headers.update(common)
        return headers


def fetch_device_id(
    timeout: float = DEVICE_PROFILE_TIMEOUT, retries: int = REQUEST_RETRIES
) -> str:
    """向设备指纹服务注册一个设备标识。

    森空岛换取凭据时会校验设备标识的来源，必须是设备指纹服务签发的 ID，
    自行构造的值会返回「设备信息无效」。该标识只在当前进程内使用，不落盘。
    """
    raw = {
        "appId": DEVICE_APP_ID,
        "organization": DEVICE_ORGANIZATION,
        "os": "web",
        "sdkver": "3.0.0",
        "version": "3.0.0",
        "subVersion": "1.0.0",
        "rtype": "all",
        "smid": "",
        "box": "",
        "gBox": "",
        "tn": "",
        "time": 0,
    }
    payload = {
        "appId": DEVICE_APP_ID,
        "organization": DEVICE_ORGANIZATION,
        "ep": "",
        "data": base64.b64encode(compact_json(raw).encode("utf-8")).decode("ascii"),
        "os": "web",
        "encode": 1,
        "compress": 0,
    }

    last_error = "设备标识获取失败"
    for attempt in range(retries + 1):
        try:
            response = HttpClient.post(
                DEVICE_PROFILE_URL,
                json=payload,
                headers={
                    "content-type": "application/json",
                    "user-agent": WEB_USER_AGENT,
                    "referer": "https://www.skland.com/",
                    "origin": "https://www.skland.com",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError
            detail = payload.get("detail") or {}
            if not isinstance(detail, dict):
                raise ValueError
            if detail.get("deviceId"):
                return "B{}".format(detail["deviceId"])
            last_error = "设备标识获取失败：响应中缺少 deviceId"
        except (HttpFailure, ValueError) as exc:
            last_error = "设备标识获取失败：网络或响应异常"

        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))

    raise SklandError("{}，可设置环境变量 SKLAND_DID 手动指定".format(last_error))


# ----------------------------------------------------------------- 配置 --

def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def _split_entries(value: str) -> List[str]:
    return [item.strip() for item in re.split(r"[;,\n]", value) if item.strip()]


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
        if value < 0:
            raise ValueError
        return value
    except ValueError:
        raise SklandError("环境变量 {} 需要是非负整数".format(name))


@dataclass
class Account:
    """一个账号的凭据与运行状态。

    凭据可以是 ``entry``（现成的 token 或 cred:token），也可以是
    ``phone`` 与 ``password``（登录时自动换取），两者取其一。
    """

    configuration_error: str = ""
    entry: str = ""
    phone: str = ""
    password: str = ""
    cred: str = ""
    token: str = ""
    user_id: Optional[str] = None
    did: str = ""

    @property
    def label(self) -> str:
        return "uid={}".format(self.user_id) if self.user_id else "未登录"


def _account_indexes() -> List[str]:
    """SKLAND_TOKEN_N / SKLAND_PHONE_N 的序号后缀，无后缀的排在最前。"""
    indexes = [""]
    for key in os.environ:
        match = re.fullmatch(r"SKLAND_(?:TOKEN|PHONE|PASSWORD)_(\d+)", key)
        if match and match.group(1) not in indexes:
            indexes.append(match.group(1))
    return sorted(indexes, key=lambda item: (item != "", int(item or 0)))


def _env_accounts() -> List[Account]:
    """收集账号：先取直接凭据，再补账密登录，相同序号视为同一个账号。"""
    accounts: List[Account] = []
    seen: Set[str] = set()

    for index in _account_indexes():
        suffix = "_{}".format(index) if index else ""
        for entry in _env("SKLAND_TOKEN" + suffix).splitlines():
            entry = entry.strip()
            if not entry:
                continue
            if entry not in seen:
                seen.add(entry)
                try:
                    accounts.append(parse_account(entry))
                except SklandError as exc:
                    accounts.append(Account(configuration_error=str(exc)))

        phone = _env("SKLAND_PHONE" + suffix)
        password = _env("SKLAND_PASSWORD" + suffix)
        if not phone and not password:
            continue
        if not (phone and password):
            accounts.append(Account(configuration_error="SKLAND_PHONE 与 SKLAND_PASSWORD 需要成对设置"))
            continue
        if phone not in seen:
            seen.add(phone)
            accounts.append(Account(phone=phone, password=password))

    return accounts


@dataclass
class Config:
    """运行配置，来自环境变量与命令行参数的合并结果。"""

    accounts: List[Account] = field(default_factory=list)
    did: str = ""
    zone_ids: Set[str] = field(default_factory=set)
    actions: Set[str] = field(default_factory=lambda: {ACTION_CHECKIN, ACTION_VIEW})
    view_count: int = 5
    like_count: int = 10
    share_count: int = 1
    notify_url: str = ""

    @classmethod
    def from_env(cls, args: argparse.Namespace) -> "Config":
        actions = _split_entries(args.actions) if args.actions else _split_entries(
            _env("SKLAND_ACTIONS", "checkin,view")
        )
        unknown = [a for a in actions if a not in ALL_ACTIONS]
        if unknown or not actions:
            raise SklandError(
                "SKLAND_ACTIONS 只能是 {} 的组合，当前为 {!r}".format(
                    "/".join(ALL_ACTIONS), "无效动作"
                )
            )

        zone_ids = _split_entries(args.zones) if args.zones else _split_entries(_env("SKLAND_ZONE_IDS"))

        did = _env("SKLAND_DID")
        accounts = _env_accounts()
        for account in accounts:
            account.did = did

        return cls(
            accounts=accounts,
            did=did,
            zone_ids=set(zone_ids),
            actions=set(actions),
            view_count=_env_int("SKLAND_VIEW_COUNT", 5),
            like_count=_env_int("SKLAND_LIKE_COUNT", 10),
            share_count=_env_int("SKLAND_SHARE_COUNT", 1),
            notify_url=_env("SKLAND_NOTIFY_URL"),
        )


# ------------------------------------------------------------- 接口客户端 --

class SklandClient:
    """森空岛接口客户端：负责凭据换取、签名与请求重试。"""

    def __init__(
        self,
        account: Account,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = REQUEST_RETRIES,
    ) -> None:
        self.account = account
        self.timeout = timeout
        self.retries = retries
        self.session = HttpClient()

    # -- 鉴权 ------------------------------------------------------------

    def authenticate(self) -> None:
        """换取可用的 cred 与签名 token。重复调用是安全的。"""
        if not self.account.did:
            self.account.did = fetch_device_id()
        source = self.account.entry or self._login_by_password()
        entry = self._unwrap(source)
        direct = self._direct_credential(entry)
        if direct is None:
            direct = self._exchange_credential(entry)
        self.account.cred, self.account.token, self.account.user_id = direct

    def _login_by_password(self) -> str:
        """用手机号与密码换取鹰角通行证 token。"""
        payload = {"phone": self.account.phone, "password": self.account.password}
        data = self._send(
            "POST",
            "{}/user/auth/v1/token_by_phone_password".format(HYPERGRYPH_BASE),
            headers={"user-agent": APP_USER_AGENT, "content-type": "application/json"},
            body=compact_json(payload),
            action="登录鹰角通行证",
        )
        if data.get("status") != 0:
            raise SklandError("登录鹰角通行证失败：{}".format("业务状态不为零"))
        token = (data.get("data") or {}).get("token")
        if not token:
            raise SklandError("登录鹰角通行证失败：响应中缺少 token")
        return str(token)

    @staticmethod
    def _unwrap(entry: str) -> str:
        """兼容直接粘贴 web-api 接口响应的情况，取出其中的 token 文本。"""
        try:
            parsed = json.loads(entry)
        except ValueError:
            return entry
        if isinstance(parsed, dict):
            data = parsed.get("data")
            if isinstance(data, dict) and data.get("content"):
                return str(data["content"]).strip()
        return entry

    @staticmethod
    def _direct_credential(entry: str) -> Optional[Tuple[str, str, Optional[str]]]:
        """识别 cred/token 直接提供凭据的两种写法。"""
        try:
            parsed = json.loads(entry)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and parsed.get("cred") and parsed.get("token"):
            return str(parsed["cred"]), str(parsed["token"]), None

        parts = entry.split(":", 1)
        if len(parts) == 2 and all(part.strip() for part in parts):
            return parts[0].strip(), parts[1].strip(), None
        return None

    def _exchange_credential(self, hypergryph_token: str) -> Tuple[str, str, Optional[str]]:
        did = self.account.did
        code = self._grant_code(hypergryph_token, did)
        return self._generate_cred(code, did)

    def _grant_code(self, hypergryph_token: str, did: str) -> str:
        """用鹰角通行证 token 换取森空岛授权码。"""
        payload = {"appCode": SKLAND_APP_CODE, "token": hypergryph_token, "type": 0}
        data = self._send(
            "POST",
            "{}/user/oauth2/v2/grant".format(HYPERGRYPH_BASE),
            headers={
                "user-agent": APP_USER_AGENT,
                "dId": did,
                "x-requested-with": "com.hypergryph.skland",
                "content-type": "application/json",
            },
            body=compact_json(payload),
            action="登录鹰角通行证",
        )
        if data.get("status") != 0:
            raise SklandError("登录鹰角通行证失败：{}".format("业务状态不为零"))
        code = (data.get("data") or {}).get("code")
        if not code:
            raise SklandError("登录鹰角通行证失败：响应中缺少授权码")
        return str(code)

    def _generate_cred(self, code: str, did: str) -> Tuple[str, str, Optional[str]]:
        """用授权码换取森空岛 cred 与签名 token。"""
        body = compact_json({"code": code, "kind": 1})
        data = self._send(
            "POST",
            "{}/web/v1/user/auth/generate_cred_by_code".format(ZONAI_BASE),
            headers={
                "content-type": "application/json",
                "user-agent": WEB_USER_AGENT,
                "referer": "https://www.skland.com/",
                "origin": "https://www.skland.com",
                "dId": did,
                "platform": PLATFORM,
                "timestamp": str(int(time.time())),
                "vName": VERSION_NAME,
            },
            body=body,
            action="换取森空岛凭据",
        )
        if data.get("code") != 0:
            raise SklandApiError(
                "换取森空岛凭据失败：{}".format("业务状态不为零"),
                code=data.get("code"),
            )
        result = data.get("data") or {}
        cred, token = result.get("cred"), result.get("token")
        if not cred or not token:
            raise SklandError("换取森空岛凭据失败：响应中缺少 cred 或 token")
        for key in ("nickname", "username", "displayName"):
            identity = result.get(key)
            if isinstance(identity, str) and identity:
                stamp("官方账号 {}：{}".format(key, identity))
        user_id = result.get("userId")
        return str(cred), str(token), (str(user_id) if user_id else None)

    # -- 请求 ------------------------------------------------------------

    def _send(
        self,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        body: Optional[str] = None,
        params: Optional[str] = None,
        action: str,
    ) -> Dict[str, Any]:
        """发送请求并返回解析后的 JSON，网络异常与 5xx 会自动重试。"""
        last_error = "{}失败".format(action)
        for attempt in range((self.retries if method == "GET" else 0) + 1):
            try:
                response = self.session.request(
                    method, url, params=params, data=body, headers=headers, timeout=self.timeout,
                    allow_redirects=False
                )
            except HttpFailure as exc:
                last_error = "{}网络异常（未输出响应或凭据）".format(action)
            else:
                try:
                    payload = response.json()
                except ValueError:
                    last_error = "{}失败：HTTP {} 响应不是有效 JSON".format(
                        action, response.status_code
                    )
                else:
                    if not isinstance(payload, dict):
                        raise SklandError("{}失败：响应结构无效".format(action))
                    if response.status_code >= 500:
                        last_error = "{}失败：HTTP {}".format(action, response.status_code)
                    elif not 200 <= response.status_code < 300:
                        raise SklandError(
                            "{}失败：HTTP {} {}".format(
                                action, response.status_code, "业务状态不为零"
                            )
                        )
                    else:
                        stamp("{}：HTTP {}，已解析响应".format(action, response.status_code))
                        return payload

            if method == "GET" and attempt < self.retries:
                time.sleep(1.5 * (attempt + 1))
        raise SklandError(last_error)

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        action: str = "请求接口",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """发起带签名的接口请求，返回响应中的 data 字段。"""
        body = compact_json(json_body) if json_body is not None else None
        headers = Signer.build_headers(
            path,
            cred=self.account.cred,
            token=self.account.token,
            did=self.account.did,
            query=query,
            body=body,
        )
        if extra_headers:
            # 仅允许游戏角色路由头；签名、凭据和签名公共头不能被覆盖。
            allowed = {"content-type", "sk-game-role", "referer", "origin"}
            if any(key.lower() not in allowed for key in extra_headers):
                raise SklandError("游戏请求包含不允许覆盖的请求头")
            headers.update(extra_headers)
        if body is not None:
            headers["content-type"] = "application/json"

        payload = self._send(
            method,
            ZONAI_BASE + path,
            headers=headers,
            body=body,
            params=urlencode(query or {}) or None,
            action=action,
        )
        if payload.get("code") != 0:
            raise SklandApiError(
                "{}失败：{}".format(action, "业务状态不为零"),
                code=payload.get("code"),
            )
        result = payload.get("data")
        if result is not None and not isinstance(result, dict):
            raise SklandError("{}失败：data 结构无效".format(action))
        stamp("{}：业务码 0，已确认成功".format(action))
        return result or {}

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)


# --------------------------------------------------------------- 每日任务 --

@dataclass
class Zone:
    """一个版区，对应森空岛里的一款游戏板块。"""

    game_id: int
    name: str
    cate_id: Optional[int] = None


@dataclass
class ZoneReport:
    """单个版区的执行结果。"""

    zone: Zone
    checked: Optional[bool] = None
    already_checked: bool = False
    viewed: int = 0
    liked: int = 0
    shared: int = 0
    note: Optional[str] = None
    failed: bool = False


@dataclass
class AccountReport:
    """单个账号的执行结果。"""

    account: Account
    error: Optional[str] = None
    zones: List[ZoneReport] = field(default_factory=list)
    attendance: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (self.error is None and not any(zone.failed for zone in self.zones)
                and all(item["ok"] for item in self.attendance))


class DailyTasks:
    """按配置执行森空岛每日任务。"""

    def __init__(self, client: SklandClient, config: Config, dry_run: bool = False) -> None:
        self.client = client
        self.config = config
        self.dry_run = dry_run

    # -- 版区与检票状态 --------------------------------------------------

    def zones(self) -> List[Zone]:
        """获取账号可见的全部版区，并挑出用于社区任务的帖子版块。"""
        data = self.client.get("/api/v1/game", action="获取版区列表")
        zones: List[Zone] = []
        for item in data.get("list") or []:
            game = item.get("game") or {}
            game_id = game.get("gameId")
            if game_id is None:
                continue
            zones.append(
                Zone(
                    game_id=int(game_id),
                    name=str(game.get("name") or game_id),
                    cate_id=self._pick_post_cate(item.get("cates") or []),
                )
            )
        return zones

    @staticmethod
    def _pick_post_cate(cates: Sequence[Dict[str, Any]]) -> Optional[int]:
        """帖子流需要一个分类 id，优先取综合讨论区。"""
        for cate in cates:
            if cate.get("kind") == POST_CATE_KIND and cate.get("id") is not None:
                return int(cate["id"])
        for cate in cates:
            if cate.get("id") is not None:
                return int(cate["id"])
        return None

    def checked_zones(self) -> Dict[int, bool]:
        """查询各版区今天的检票状态。"""
        data = self.client.get("/api/v1/score/ischeckin", action="查询检票状态")
        result: Dict[int, bool] = {}
        for item in data.get("list") or []:
            game_id = item.get("gameId")
            if game_id is not None:
                result[int(game_id)] = item.get("checked") is True or item.get("checked") == 1
        return result

    # -- 执行 ------------------------------------------------------------

    def run(self) -> AccountReport:
        report = AccountReport(account=self.client.account)
        if self._wants(ACTION_ATTENDANCE):
            try:
                with stage("获取绑定角色及明日方舟签到"):
                    self._attendance(report)
            except Exception:
                report.attendance.append({"ok": False, "message": "绑定角色接口或签到结构异常"})
        if self._wants(ACTION_ENDFIELD):
            try:
                with stage("获取绑定角色及终末地签到"):
                    self._endfield(report)
            except Exception:
                stamp("❌ 终末地绑定角色接口或签到结构异常")
                report.attendance.append({"ok": False, "message": "终末地绑定角色接口或签到结构异常"})
        if not any(self._wants(a) for a in
                   (ACTION_CHECKIN, ACTION_VIEW, ACTION_LIKE, ACTION_SHARE)):
            return report

        try:
            with stage("获取版区列表"):
                zones = self.zones()
        except SklandError as exc:
            report.error = str(exc)
            return report

        if self.config.zone_ids:
            zones = [zone for zone in zones if str(zone.game_id) in self.config.zone_ids]
        if not zones:
            report.error = "没有匹配到任何版区，请检查 SKLAND_ZONE_IDS 配置"
            return report

        try:
            with stage("查询检票状态"):
                checked = self.checked_zones() if self._wants(ACTION_CHECKIN) else {}
        except SklandError as exc:
            report.error = str(exc)
            return report

        for zone in zones:
            report.zones.append(self._run_zone(zone, checked))
        return report

    def _attendance(self, report: AccountReport) -> None:
        """原始游戏签到：逐角色独立执行，业务码与奖励结构均须有效。"""
        data = self.client.get("/api/v1/game/player/binding", action="获取游戏绑定角色")
        games = data.get("list")
        if not isinstance(games, list):
            raise SklandError("绑定角色列表结构无效")
        characters = []
        for game in games:
            if not isinstance(game, dict):
                raise SklandError("绑定游戏结构无效")
            if game.get("appCode") == "arknights":
                bindings = game.get("bindingList")
                if not isinstance(bindings, list):
                    raise SklandError("明日方舟角色列表结构无效")
                characters.extend(bindings)
        if not characters:
            report.attendance.append({"ok": False, "message": "未绑定明日方舟角色，未执行游戏签到"})
            return
        for index, character in enumerate(characters, 1):
            try:
                with stage("明日方舟角色 {} 签到".format(index)):
                    if not isinstance(character, dict) or not character.get("uid"):
                        raise SklandError("绑定角色缺少公开 UID")
                    identity = character.get("nickName")
                    stamp("官方角色：{}；公开 UID：{}".format(
                        identity if identity is not None else "未返回昵称", character["uid"]))
                    result = self.client.post(
                        "/api/v1/game/attendance",
                        json_body={"gameId": 1, "uid": character["uid"]},
                        action="明日方舟角色签到")
                    awards = result.get("awards")
                    if not isinstance(awards, list) or not awards:
                        raise SklandError("签到响应缺少有效奖励列表，无法核验奖励")
                    rewards = []
                    for award in awards:
                        if not isinstance(award, dict) or not isinstance(award.get("resource"), dict):
                            raise SklandError("签到奖励结构无效")
                        name = award["resource"].get("name")
                        count = award.get("count") or 1
                        if not isinstance(name, str) or not name or not isinstance(count, (int, str)):
                            raise SklandError("签到奖励名称或数量无效")
                        rewards.append("{}×{}".format(name, count))
                    stamp("✅ 明日方舟签到成功，奖励：" + "，".join(rewards))
                    report.attendance.append({"ok": True, "message": "明日方舟签到成功"})
            except Exception:
                # 不显示服务端错误文案、请求值或异常详情；继续处理其余角色。
                stamp("❌ 角色 {} 签到失败，未确认业务成功或奖励结构".format(index))
                report.attendance.append({"ok": False, "message": "明日方舟签到未通过核验"})

    def _endfield(self, report: AccountReport) -> None:
        """终末地签到：保留上游空请求体、角色路由头和奖励映射契约。"""
        data = self.client.get("/api/v1/game/player/binding", action="获取终末地绑定角色")
        games = data.get("list")
        if not isinstance(games, list):
            raise SklandError("绑定角色列表结构无效")
        attempted = 0
        for game in games:
            if not isinstance(game, dict):
                report.attendance.append({"ok": False, "message": "绑定游戏结构无效"})
                continue
            if game.get("appCode") != "endfield":
                continue
            bindings = game.get("bindingList")
            if not isinstance(bindings, list):
                report.attendance.append({"ok": False, "message": "终末地绑定列表结构无效"})
                continue
            for binding in bindings:
                roles = binding.get("roles") if isinstance(binding, dict) else None
                if not isinstance(roles, list) or not roles:
                    stamp("❌ 终末地绑定记录缺少角色列表")
                    report.attendance.append({"ok": False, "message": "终末地绑定记录缺少角色列表"})
                    continue
                for role in roles:
                    attempted += 1
                    try:
                        with stage("终末地角色 {} 签到".format(attempted)):
                            if not isinstance(role, dict):
                                raise SklandError("终末地角色结构无效")
                            role_id, server_id = role.get("roleId"), role.get("serverId")
                            # 来自官方绑定接口；只允许明确的数字角色路由，避免请求头注入。
                            if (role_id is None or server_id is None or
                                    not str(role_id).isdigit() or not str(server_id).isdigit()):
                                raise SklandError("终末地角色缺少有效角色或服务器编号")
                            nickname = role.get("nickname")
                            stamp("官方终末地角色：{}".format(
                                nickname if nickname is not None else "未返回昵称"))
                            if role.get("uid") is not None:
                                stamp("公开 UID：{}".format(role["uid"]))
                            result = self.client.post(
                                "/web/v1/game/endfield/attendance",
                                extra_headers={
                                    "content-type": "application/json",
                                    "sk-game-role": "3_{}_{}".format(role_id, server_id),
                                    "referer": "https://game.skland.com/",
                                    "origin": "https://game.skland.com/",
                                },
                                action="终末地角色签到")
                            award_ids, resources = result.get("awardIds"), result.get("resourceInfoMap")
                            if not isinstance(award_ids, list) or not award_ids or not isinstance(resources, dict):
                                raise SklandError("终末地签到响应缺少有效奖励映射")
                            rewards = []
                            for award in award_ids:
                                if not isinstance(award, dict) or "id" not in award:
                                    raise SklandError("终末地奖励编号结构无效")
                                resource = resources.get(str(award["id"]))
                                if not isinstance(resource, dict):
                                    raise SklandError("终末地奖励映射缺失")
                                name, count = resource.get("name"), resource.get("count")
                                if (not isinstance(name, str) or not name or
                                        isinstance(count, bool) or
                                        not isinstance(count, (int, str)) or not str(count).isdigit()):
                                    raise SklandError("终末地奖励名称或数量无效")
                                rewards.append("{}×{}".format(name, count))
                            stamp("✅ 终末地签到成功，奖励：" + "，".join(rewards))
                            report.attendance.append({"ok": True, "message": "终末地签到成功"})
                    except Exception:
                        stamp("❌ 终末地角色 {} 签到未通过核验，继续其余角色".format(attempted))
                        report.attendance.append({"ok": False, "message": "终末地签到未通过核验"})
        if not attempted:
            stamp("❌ 未找到可签到的终末地角色")
            report.attendance.append({"ok": False, "message": "未绑定可用终末地角色，未执行签到"})

    def _run_zone(self, zone: Zone, checked: Dict[int, bool]) -> ZoneReport:
        report = ZoneReport(zone=zone, checked=checked.get(zone.game_id, False))
        report.already_checked = bool(report.checked)

        if self._wants(ACTION_CHECKIN):
            try:
                with stage("版区检票"):
                    self._checkin(zone, report)
            except SklandError as exc:
                report.failed = True
                report.note = str(exc)
                return report

        if not (self._wants(ACTION_VIEW) or self._wants(ACTION_LIKE) or self._wants(ACTION_SHARE)):
            return report

        if zone.cate_id is None:
            report.note = "该版区没有可用的帖子版块，无法完成已选择的社区任务"
            report.failed = True
            return report

        if not self.dry_run:
            self._browse(zone, report)
            if not self._browse_done(report):
                report.failed = True
                report.note = report.note or "可用帖子不足，未完成配置数量"
        return report

    def _checkin(self, zone: Zone, report: ZoneReport) -> None:
        """完成版区检票，今天已检票的版区直接跳过。"""
        if report.already_checked or self.dry_run:
            return
        try:
            self.client.post(
                "/api/v1/score/checkin",
                json_body={"gameId": str(zone.game_id)},
                action="版区检票",
            )
        except SklandApiError as exc:
            # 不依赖可能含敏感信息的服务端文案，重新查询官方状态。
            if self.checked_zones().get(zone.game_id) is not True:
                raise
            report.already_checked = True
            return
        report.checked = True

    def _browse(self, zone: Zone, report: ZoneReport) -> None:
        """按配置数量浏览、点赞、分享版区帖子，必要时翻页。"""
        page_token = ""
        for _ in range(POST_MAX_PAGES):
            if self._browse_done(report):
                return
            try:
                data = self.client.get(
                    "/api/v1/home/index",
                    query={
                        "gameId": str(zone.game_id),
                        "cateId": str(zone.cate_id),
                        "sortType": POST_SORT_TYPE,
                        "pageToken": page_token,
                        "pageSize": POST_PAGE_SIZE,
                    },
                    action="获取版区帖子",
                )
            except SklandError as exc:
                report.note = report.note or str(exc)
                report.failed = True
                return

            posts = data.get("list") or []
            if not posts:
                return

            for post in posts:
                if self._browse_done(report):
                    return
                self._handle_post(zone, post, report)

            page_token = str(data.get("pageToken") or "")
            if not data.get("hasMore") or not page_token:
                return

    def _handle_post(self, zone: Zone, post: Dict[str, Any], report: ZoneReport) -> None:
        item = post.get("item") or {}
        post_id = item.get("id")
        if not post_id:
            return

        if self._wants(ACTION_VIEW) and report.viewed < self.config.view_count:
            if self._attempt(
                report,
                lambda: self.client.get(
                    "/api/v1/item/list", query={"ids": str(post_id)}, action="浏览帖子"
                ),
                "浏览",
            ):
                report.viewed += 1
            self._pause()

        liked = bool((post.get("itemRel") or {}).get("like"))
        if self._wants(ACTION_LIKE) and report.liked < self.config.like_count and not liked:
            if str(post_id).isdigit():
                if self._attempt(
                    report,
                    lambda: self.client.post(
                        "/api/v1/action/trigger",
                        json_body={"objectId": int(post_id), "action": ACTION_CODE_LIKE},
                        action="点赞帖子",
                    ),
                    "点赞",
                ):
                    report.liked += 1
                self._pause()

        if self._wants(ACTION_SHARE) and report.shared < self.config.share_count:
            if self._attempt(
                report,
                lambda: self.client.post(
                    "/api/v1/score/share",
                    json_body={"gameId": str(zone.game_id)},
                    action="分享帖子",
                ),
                "分享",
            ):
                report.shared += 1
            self._pause()

    @staticmethod
    def _attempt(report: ZoneReport, call: Any, action: str) -> bool:
        try:
            with stage(action):
                call()
            return True
        except SklandError as exc:
            report.failed = True
            report.note = report.note or "{}失败：{}".format(action, exc)
            return False

    def _browse_done(self, report: ZoneReport) -> bool:
        return (
            (not self._wants(ACTION_VIEW) or report.viewed >= self.config.view_count)
            and (not self._wants(ACTION_LIKE) or report.liked >= self.config.like_count)
            and (not self._wants(ACTION_SHARE) or report.shared >= self.config.share_count)
        )

    def _wants(self, action: str) -> bool:
        return action in self.config.actions

    @staticmethod
    def _pause() -> None:
        time.sleep(REQUEST_INTERVAL)


# --------------------------------------------------------------- 结果输出 --

SEPARATOR = "-" * 52


def format_report(reports: Sequence[AccountReport], config: Config, dry_run: bool = False) -> Tuple[str, bool]:
    """把执行结果整理成可读文本，同时返回是否全部成功。"""
    lines = ["森空岛每日任务{}".format("（预演）" if dry_run else ""), SEPARATOR]
    succeeded = 0

    for index, report in enumerate(reports, start=1):
        lines.append("账号 {}/{}  {}".format(index, len(reports), report.account.label))
        for item in report.attendance:
            lines.append("  " + item["message"])
        if report.error:
            lines.append("  [!] {}".format(report.error))
        for zone in report.zones:
            lines.append("  {}".format(_format_zone(zone, config, dry_run)))
        if report.ok:
            succeeded += 1

    lines.append(SEPARATOR)
    lines.append(
        "汇总：{} 个账号，成功 {}，失败 {}".format(len(reports), succeeded, len(reports) - succeeded)
    )
    return "\n".join(lines), succeeded == len(reports) and bool(reports)


def _format_zone(zone_report: ZoneReport, config: Config, dry_run: bool) -> str:
    zone = zone_report.zone
    segments: List[str] = []

    if ACTION_CHECKIN in config.actions:
        if dry_run:
            segments.append("检票 {}".format("今日已检票" if zone_report.already_checked else "待检票"))
        elif zone_report.failed:
            segments.append("检票 失败")
        elif zone_report.already_checked:
            segments.append("检票 今日已检票")
        elif zone_report.checked:
            segments.append("检票 完成")
        else:
            segments.append("检票 未执行")

    if ACTION_VIEW in config.actions:
        segments.append("浏览 {}/{}".format(zone_report.viewed, config.view_count))
    if ACTION_LIKE in config.actions:
        segments.append("点赞 {}/{}".format(zone_report.liked, config.like_count))
    if ACTION_SHARE in config.actions:
        segments.append("分享 {}/{}".format(zone_report.shared, config.share_count))

    line = "{}（gameId={}）  {}".format(zone.name, zone.game_id, " | ".join(segments))
    if zone_report.note:
        line += "  [!] {}".format(zone_report.note)
    return line


# ----------------------------------------------------------------- 入口 --

def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="skland_daily.py",
        description="森空岛每日任务：版区检票、浏览、点赞、分享",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="完全断网校验配置并模拟任务，不登录或发送请求",
    )
    parser.add_argument("--actions", help="覆盖 SKLAND_ACTIONS，例如 checkin,view")
    parser.add_argument("--zones", help="覆盖 SKLAND_ZONE_IDS，例如 1,2")
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    return parser.parse_args(argv)


STAGE_NUMBER = 0


def stamp(message: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), message), flush=True)


@contextmanager
def stage(name: str):
    global STAGE_NUMBER
    STAGE_NUMBER += 1
    number = STAGE_NUMBER
    started = time.monotonic()
    stamp("阶段 {}：{}".format(number, name))
    try:
        yield
    except Exception:
        stamp("❌ 阶段 {} 失败，耗时 {:.2f} 秒".format(number, time.monotonic() - started))
        raise
    else:
        stamp("✅ 阶段 {} 完成，耗时 {:.2f} 秒".format(number, time.monotonic() - started))


def parse_account(entry: str) -> Account:
    if entry.startswith("{"):
        try:
            value = json.loads(entry)
        except ValueError:
            raise SklandError("账号 JSON 无效，请每个账号使用一个完整非空行")
        if not isinstance(value, dict):
            raise SklandError("账号 JSON 必须是对象")
        if "phone" in value or "password" in value:
            if not all(isinstance(value.get(k), str) and value[k].strip() for k in ("phone", "password")):
                raise SklandError("账号手机号和密码必须为非空字符串且成对配置")
            return Account(phone=value["phone"], password=value["password"])
        if not ((isinstance(value.get("cred"), str) and value["cred"] and
                 isinstance(value.get("token"), str) and value["token"]) or
                (isinstance(value.get("data"), dict) and
                 isinstance(value["data"].get("content"), str) and value["data"]["content"])):
            raise SklandError("账号 JSON 缺少 cred/token 或 data.content")
    elif ":" in entry:
        # 只在第一个字段分隔符拆分，后续签名凭据原样保留。
        if not all(part.strip() for part in entry.split(":", 1)):
            raise SklandError("cred:token 两部分必须非空")
    elif any(c in entry for c in ";,&@\t "):
        raise SklandError("账号必须每行一个，不接受分号或逗号分隔")
    return Account(entry=entry)


@contextmanager
def notification_timeout():
    if not hasattr(signal, "SIGALRM"):
        yield
        return
    def expired(signum, frame):
        raise TimeoutError("通知超时")
    old_handler = signal.signal(signal.SIGALRM, expired)
    old_timer = signal.setitimer(signal.ITIMER_REAL, 15)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        signal.signal(signal.SIGALRM, old_handler)


def qinglong_notify(content: str, dry_run: bool, url: str = "") -> str:
    if _env("QINGLONG_NOTIFY", "1").lower() in ("0", "false", "no", "off"):
        return "已关闭"
    if dry_run:
        stamp("⏭️ 预演通知摘要已生成，断网模式不调用通知渠道")
        return "预演仅本地摘要"
    delivered = False
    try:
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                module = importlib.import_module("notify")
        except ImportError:
            module = None
        if module is None or not callable(getattr(module, "send", None)):
            paths = []
            if _env("QINGLONG_NOTIFY_DIR"):
                paths.append(Path(_env("QINGLONG_NOTIFY_DIR")) / "notify.py")
            paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notification", path)
                    module = importlib.util.module_from_spec(spec)
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        spec.loader.exec_module(module)
                    if callable(getattr(module, "send", None)):
                        break
        if module is not None and callable(getattr(module, "send", None)):
            with notification_timeout(), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                module.send("森空岛每日任务", content)
            delivered = True
        else:
            stamp("⚠️ 青龙通知模块不可用，保留业务退出码")
    except Exception:
        stamp("⚠️ 青龙通知失败，保留业务退出码")
    if url:
        try:
            from urllib.parse import urlsplit
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError
            response = HttpClient.post(url, json={"title": "森空岛每日任务", "content": content},
                                     timeout=10, allow_redirects=False)
            if not 200 <= response.status_code < 300:
                raise ValueError
            delivered = True
        except Exception:
            stamp("⚠️ 自定义通知失败，保留业务退出码")
    return "已发送" if delivered else "不可用或失败"


def account_stats(report: AccountReport, config: Config) -> Dict[str, int]:
    stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    for item in report.attendance:
        stats["total"] += 1
        stats["success" if item["ok"] else "failed"] += 1
    if report.error:
        stats["total"] += 1
        stats["failed"] += 1
        return stats
    for zone in report.zones:
        if ACTION_CHECKIN in config.actions:
            stats["total"] += 1
            key = "alreadyComplete" if zone.already_checked else "success" if zone.checked else "failed"
            stats[key] += 1
        for action, done, count in ((ACTION_VIEW, zone.viewed, config.view_count),
                                    (ACTION_LIKE, zone.liked, config.like_count),
                                    (ACTION_SHARE, zone.shared, config.share_count)):
            if action in config.actions:
                stats["total"] += count
                stats["success"] += done
                stats["failed"] += max(0, count - done)
    return stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.monotonic()
    dry_run = _env("SKLAND_DRY_RUN").lower() in ("1", "true", "yes", "on")
    stamp("========== 森空岛每日任务 ==========")
    stamp("开始时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
    config = None
    reports = []
    account_results = []
    code = 1
    status = "configuration-error"
    count = succeeded = 0
    try:
        args = parse_args(argv)
        dry_run = dry_run or args.dry_run
        stamp("运行模式：" + ("断网预演" if dry_run else "正式执行"))
        with stage("校验配置"):
            config = Config.from_env(args)
            if not config.accounts:
                raise SklandError("未配置账号：请设置 SKLAND_TOKEN，每个非空行一个账号")
        count = len(config.accounts)
        stamp("账号数量：{}".format(count))
        for index, account in enumerate(config.accounts, 1):
            account_start = time.monotonic()
            stamp("账号 {}/{} 开始".format(index, count))
            if account.configuration_error:
                stamp("❌ " + account.configuration_error)
                stats = {"total": 1, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 1}
                ok = False
            elif dry_run:
                with stage("账号配置预演"):
                    stamp("DRY_RUN_OK：已校验账号格式；动作 {}；不访问任何网络".format(
                        ",".join(a for a in ALL_ACTIONS if a in config.actions)))
                stats = {"total": len(config.actions), "success": 0, "alreadyComplete": 0,
                         "skipped": len(config.actions), "failed": 0}
                ok = True
            else:
                client = SklandClient(account)
                try:
                    with stage("账号登录"):
                        client.authenticate()
                        stamp("账号 {}：{}".format(index, account.label))
                    report = DailyTasks(client, config).run()
                except SklandError as exc:
                    report = AccountReport(account=account, error=str(exc))
                except Exception:
                    report = AccountReport(account=account, error="接口结构或执行异常（未输出敏感数据）")
                finally:
                    client.session.close()
                reports.append(report)
                ok = report.ok
                stats = account_stats(report, config)
                for zone in report.zones:
                    stamp(_format_zone(zone, config, False))
                if report.error:
                    stamp("❌ " + report.error)
            succeeded += int(ok)
            account_results.append({"account": index, "ok": ok, **stats})
            stamp("账号 {} 统计：总任务 {total}，成功 {success}，已完成 {alreadyComplete}，跳过 {skipped}，失败 {failed}；耗时 {:.2f} 秒".format(
                index, time.monotonic() - account_start, **stats))
        code = 0 if succeeded == count else 1
        status = "dry-run" if dry_run else "success" if code == 0 else "partial-failure" if succeeded else "failure"
    except SklandError as exc:
        stamp("❌ 配置错误：" + str(exc))
    except SystemExit as exc:
        code = int(exc.code or 0)
        status = "configuration-error" if code else "skipped"
    except Exception:
        stamp("❌ 执行异常（未输出敏感数据）")
        status = "failure"
    if config is None:
        stamp("账号数量：0")
    failed = count - succeeded
    body = "状态：{}；账号总数 {}，成功 {}，失败 {}".format(status, count, succeeded, failed)
    if status == "configuration-error":
        body += "；配置错误，未执行账号任务"
    notification = qinglong_notify(body, dry_run, config.notify_url if config else "")
    stamp(SEPARATOR)
    stamp(body)
    totals = {key: sum(r[key] for r in account_results) for key in
              ("total", "success", "alreadyComplete", "skipped", "failed")}
    stamp("子任务统计：总任务 {total}，成功 {success}，已完成 {alreadyComplete}，跳过 {skipped}，失败 {failed}".format(**totals))
    stamp("通知状态：" + notification)
    stamp("完成时间：{}；总耗时 {:.2f} 秒；最终状态 {}".format(
        time.strftime("%Y-%m-%d %H:%M:%S"), time.monotonic() - started, status))
    print("TASK_SUMMARY=" + compact_json({"status": status, "dryRun": dry_run,
          "accounts": count, "success": succeeded, "failed": failed, "exitCode": code,
          "accountResults": account_results, "taskStatistics": totals, "notification": notification}))
    return code


if __name__ == "__main__":
    sys.exit(main())
