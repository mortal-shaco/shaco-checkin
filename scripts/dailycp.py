#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 今日校园信息收集
# cron: 57 8 * * *
#
# 来源：mikuzhangping/mikuDailyCP DailyCP.py（MIT）
# https://github.com/mikuzhangping/mikuDailyCP
# 提交：2d8eeeb8f127864ba2ec0f549eefb6204d381e5b
# SPDX-License-Identifier: MIT
#
# Copyright (c) HuangXu, FengXinYang, ZhouYuYang / AUST HACKER
# Copyright (c) mikuzhangping/mikuDailyCP contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""今日校园信息收集（青龙维护版）。

功能清点（相对上游 DailyCP.py）：
- 按学校全名查询今日校园租户并解析登录域名
- 支持 campusphere IAP 登录与 AuthServer 表单登录
- 查询待处理信息收集任务，按本地 formdb 模板自动填写并提交
- 上游注释掉的待办通知确认改为可选开关（默认关闭，保持原默认行为）
- 移除硬编码学号/密码/学校/地址、Cookie 打印与无超时请求
- 增加换行多账号、DAILYCP_DRY_RUN 断网预演、超时、业务成功核验、
  时间轴日志、TASK_SUMMARY、青龙脱敏通知与任一账号失败非零退出

DAILYCP_ACCOUNTS（必填）：每个非空行一个账号。
  格式：学校全名|学号|密码|定位地址
  仅按前三个 | 分割，定位地址中后续 | 原样保留；密码勿含 |。
兼容：DAILYCP_SCHOOL + DAILYCP_USERNAME + DAILYCP_PASSWORD + DAILYCP_ADDRESS
      （仅当规范变量为空时组成单账号）。
DAILYCP_FORMDB：本地已填表单模板目录（真实执行必填；首次缺失模板时写入空白稿供手工填写）。
DAILYCP_CONFIRM_NOTICE=1：额外确认待办通知（上游默认未启用）。
DAILYCP_TIMEOUT：单次请求超时秒数，默认 20，范围 5..60。
DAILYCP_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求。
建议 Cron：0 8 * * *。不打印密码、Cookie、Token 或原始响应。
本脚本不发布帖子、评论或分享文字。
"""
from __future__ import annotations

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
        _ql_notify_identities = ('88e6a9f7651b1566', 'scripts/dailycp.py', 'dailycp.py', 'dailycp')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import http.cookiejar
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from Crypto.Cipher import AES, DES
    from Crypto.Util.Padding import pad as pkcs_pad
except ImportError as _crypto_import_error:  # pragma: no cover
    raise SystemExit(
        "缺少依赖 pycryptodome，请先安装：pip install pycryptodome"
    ) from _crypto_import_error

TITLE = "今日校园信息收集"
CATALOG_ID = "88e6a9f7651b1566"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 1024 * 1024
DES_KEY = "ST83=@XV"
AES_PREFIX = "TdEEGazAXQMBzEAisrYaxRRax5kmnMJnpbKxcE6jxQfWRwP2J78adKYm8WzSkfXJ"
AES_IV = b"ya8C45aRrBEn8sZH"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TRUE_VALUES = {"1", "true", "yes", "on", "y"}
FALSE_VALUES = {"0", "false", "no", "off", "n"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
STATES = ("success", "alreadyComplete", "skipped", "failure")


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


AccountSpec = Dict[str, str]


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def redact(text: str, secrets: List[str]) -> str:
    out = str(text).replace("\r", " ").replace("\n", " ")
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        if len(secret) >= 2:
            out = out.replace(secret, "[敏感值]")
    out = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号]", out)
    out = re.sub(
        r"(?i)(cookie|token|authorization|session|password)=([^;\s&]+)",
        r"\1=[敏感值]",
        out,
    )
    return "".join(ch for ch in out if ch.isprintable())[:240]


def resolve_timeout() -> float:
    raw = env("DAILYCP_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("DAILYCP_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("DAILYCP_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_formdb(required: bool) -> Path:
    raw = env("DAILYCP_FORMDB")
    if not raw:
        if required:
            raise SafeError(
                "请设置 DAILYCP_FORMDB 为本地已填表单模板目录（真实执行必填）"
            )
        return Path(".")
    path = Path(raw).expanduser()
    if required and not path.is_dir():
        raise SafeError("DAILYCP_FORMDB 目录不存在或不可用")
    return path


def load_accounts() -> List[AccountSpec]:
    raw = env("DAILYCP_ACCOUNTS")
    accounts: List[AccountSpec] = []
    if raw:
        for line_no, line in enumerate(raw.splitlines(), 1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            parts = text.split("|", 3)
            if len(parts) != 4:
                raise SafeError(
                    "第 {} 行账号格式无效，须为 学校全名|学号|密码|定位地址".format(
                        line_no
                    )
                )
            school, username, password, address = [p.strip() for p in parts]
            if not school or not username or not password or not address:
                raise SafeError("第 {} 行账号字段存在空值".format(line_no))
            accounts.append(
                {
                    "school": school,
                    "username": username,
                    "password": password,
                    "address": address,
                }
            )
    else:
        school = env("DAILYCP_SCHOOL")
        username = env("DAILYCP_USERNAME")
        password = env("DAILYCP_PASSWORD")
        address = env("DAILYCP_ADDRESS")
        if any([school, username, password, address]):
            if not all([school, username, password, address]):
                raise SafeError(
                    "兼容单账号别名须同时提供 DAILYCP_SCHOOL、DAILYCP_USERNAME、"
                    "DAILYCP_PASSWORD、DAILYCP_ADDRESS"
                )
            accounts.append(
                {
                    "school": school,
                    "username": username,
                    "password": password,
                    "address": address,
                }
            )
    if not accounts:
        raise SafeError(
            "未配置账号：请设置 DAILYCP_ACCOUNTS，或兼容别名 "
            "DAILYCP_SCHOOL/USERNAME/PASSWORD/ADDRESS"
        )
    return accounts


def des_encrypt(text: str, key: str = DES_KEY) -> str:
    cipher = DES.new(key.encode("utf-8"), DES.MODE_CBC, b"\x01\x02\x03\x04\x05\x06\x07\x08")
    encrypted = cipher.encrypt(pkcs_pad(text.encode("utf-8"), 8))
    return base64.b64encode(encrypted).decode("ascii")


def password_encrypt(text: str, key: str) -> bytes:
    def _pad(s: str) -> str:
        pad_len = len(key) - len(s) % len(key)
        return s + pad_len * chr(pad_len)

    payload = _pad(AES_PREFIX + text).encode("utf-8")
    aes = AES.new(key.encode("utf-8"), AES.MODE_CBC, AES_IV)
    return base64.b64encode(aes.encrypt(payload))


class HttpClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.headers: Dict[str, str] = {
            "User-Agent": UA,
            "Pragma": "no-cache",
            "Accept": "application/json, text/plain, */*",
        }
        extension = {
            "deviceId": str(uuid.uuid4()),
            "systemName": "未来操作系统",
            "userId": "5201314",
            "appVersion": "8.1.13",
            "model": "红星一号量子计算机",
            "lon": 0.0,
            "systemVersion": "初号机",
            "lat": 0.0,
        }
        self.headers["Cpdaily-Extension"] = des_encrypt(json.dumps(extension))
        self.host = ""
        self.login_url = ""

    def request(
        self,
        url: str,
        body: Any = None,
        *,
        parse_json: bool = True,
        json_body: bool = True,
        referer: Optional[str] = None,
        allow_redirects: bool = True,
    ) -> Any:
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
        data: Optional[bytes] = None
        method = "GET"
        if body is not None:
            method = "POST"
            if json_body:
                headers["Content-Type"] = "application/json"
                data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, dict):
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                data = urllib.parse.urlencode(body).encode("utf-8")
            elif isinstance(body, str):
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                data = body.encode("utf-8")
            else:
                data = body
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read(MAX_BYTES + 1)
                final_url = resp.geturl()
                status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_BYTES + 1) if exc.fp else b""
            final_url = exc.geturl() if hasattr(exc, "geturl") else url
            status = exc.code
            if status >= 400 and not parse_json:
                raise SafeError("HTTP 请求失败（状态 {}）".format(status)) from exc
        except urllib.error.URLError as exc:
            raise SafeError("网络请求失败") from exc
        if len(raw) > MAX_BYTES:
            raise SafeError("响应体积过大")
        text = raw.decode("utf-8", errors="replace")
        if not parse_json:
            class _Resp:
                def __init__(self) -> None:
                    self.text = text
                    self.content = raw
                    self.url = final_url
                    self.status_code = status

            return _Resp()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SafeError("响应不是合法 JSON") from exc


def set_host_by_school(client: HttpClient, school_name: str) -> str:
    payload = client.request("https://static.campushoy.com/apicache/tenantListSort")
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise SafeError("学校列表接口返回异常")
    matched = [
        item
        for group in data
        if isinstance(group, dict)
        for item in group.get("datas") or []
        if isinstance(item, dict) and item.get("name") == school_name
    ]
    if not matched:
        raise SafeError("不支持的学校或学校名称错误")
    school_id = matched[0].get("id")
    if not school_id:
        raise SafeError("学校标识缺失")
    info = client.request(
        "https://mobile.campushoy.com/v6/config/guest/tenant/info?ids={}".format(
            urllib.parse.quote(str(school_id))
        )
    )
    rows = info.get("data") if isinstance(info, dict) else None
    if not isinstance(rows, list) or not rows:
        raise SafeError("学校未入驻今日校园平台或租户信息为空")
    login_url = rows[0].get("ampUrl") if isinstance(rows[0], dict) else None
    if not login_url or not isinstance(login_url, str):
        raise SafeError("学校登录地址缺失")
    hosts = re.findall(r"//(.*?)/", login_url)
    if not hosts:
        raise SafeError("无法从登录地址解析主机名")
    client.login_url = login_url
    client.host = hosts[0]
    return client.host


def login_iap(client: HttpClient, username: str, password: str) -> bool:
    client.headers["X-Requested-With"] = "XMLHttpRequest"
    entry = client.request(
        "https://{host}/iap/login?service=https://{host}/portal/login".format(
            host=client.host
        ),
        parse_json=False,
    )
    query = urllib.parse.urlsplit(entry.url).query
    client_id = urllib.parse.parse_qs(query).get("lt", [""])[0]
    if not client_id and "=" in entry.url:
        client_id = entry.url[entry.url.find("=") + 1 :]
    lt_payload = client.request(
        "https://{host}/iap/security/lt".format(host=client.host),
        "lt={}".format(client_id),
        parse_json=True,
        json_body=False,
    )
    lt = ((lt_payload.get("result") or {}) if isinstance(lt_payload, dict) else {}).get(
        "_lt"
    )
    if not lt:
        raise SafeError("IAP 登录票据获取失败")
    body = {
        "username": username,
        "password": password,
        "lt": lt,
        "captcha": "",
        "rememberMe": "true",
        "dllt": "",
        "mobile": "",
    }
    result = client.request(
        "https://{host}/iap/doLogin".format(host=client.host),
        body,
        parse_json=True,
        json_body=False,
    )
    if not isinstance(result, dict):
        raise SafeError("IAP 登录响应异常")
    if result.get("resultCode") == "REDIRECT" and result.get("url"):
        client.request(str(result["url"]), parse_json=False)
        return True
    return False


def login_authserver(client: HttpClient, username: str, password: str) -> bool:
    page = client.request(client.login_url, parse_json=False)
    hidden = dict(
        re.findall(
            r'''<input type="hidden" name="(.*?)" value="(.*?)"''',
            page.text,
        )
    )
    salts = dict(
        re.findall(
            r'''<input type="hidden" id="(.*?)" value="(.*?)"''',
            page.text,
        )
    )
    body = dict(hidden)
    body["username"] = username
    body["dllt"] = "userNamePasswordLogin"
    if "pwdDefaultEncryptSalt" in salts:
        body["password"] = password_encrypt(
            password, salts["pwdDefaultEncryptSalt"]
        ).decode("ascii")
    else:
        body["password"] = password
    resp = client.request(
        page.url,
        body,
        parse_json=False,
        json_body=False,
        referer=client.login_url,
    )
    # 登录成功后通常会跳转到业务域并写入会话 Cookie。
    cookie_names = {c.name.lower() for c in client.cookie_jar}
    if any(
        name in cookie_names
        for name in ("castgc", "moder_auth", "session", "jsessionid", "campusession")
    ):
        return True
    if "authserver" not in (resp.url or "").lower() and resp.status_code < 400:
        return True
    return False


def login(client: HttpClient, username: str, password: str) -> None:
    if "campusphere" in client.login_url:
        ok = login_iap(client, username, password)
    else:
        ok = login_authserver(client, username, password)
    if not ok:
        raise SafeError("登录失败（账号或密码错误，或学校登录流程变更）")


def get_collector_list(client: HttpClient) -> List[Dict[str, Any]]:
    body = {"pageSize": 10, "pageNumber": 1}
    ret = client.request(
        "https://{host}/wec-counselor-collector-apps/stu/collector/queryCollectorProcessingList".format(
            host=client.host
        ),
        body,
    )
    rows = ((ret.get("datas") or {}) if isinstance(ret, dict) else {}).get("rows")
    if rows is None:
        raise SafeError("信息收集列表字段缺失")
    if not isinstance(rows, list):
        raise SafeError("信息收集列表格式异常")
    return [row for row in rows if isinstance(row, dict)]


def get_notice_list(client: HttpClient) -> List[Dict[str, Any]]:
    body = {"pageSize": 10, "pageNumber": 1}
    ret = client.request(
        "https://{host}/wec-counselor-stu-apps/stu/notice/queryProcessingNoticeList".format(
            host=client.host
        ),
        body,
    )
    rows = ((ret.get("datas") or {}) if isinstance(ret, dict) else {}).get("rows")
    if rows is None:
        raise SafeError("通知列表字段缺失")
    if not isinstance(rows, list):
        raise SafeError("通知列表格式异常")
    return [row for row in rows if isinstance(row, dict)]


def confirm_notice(client: HttpClient, wid: str) -> bool:
    ret = client.request(
        "https://{host}/wec-counselor-stu-apps/stu/notice/confirmNotice".format(
            host=client.host
        ),
        {"wid": wid},
    )
    return isinstance(ret, dict) and ret.get("message") == "SUCCESS"


def get_collector_detail(client: HttpClient, collector_wid: str) -> Dict[str, Any]:
    ret = client.request(
        "https://{host}/wec-counselor-collector-apps/stu/collector/detailCollector".format(
            host=client.host
        ),
        {"collectorWid": collector_wid},
    )
    datas = ret.get("datas") if isinstance(ret, dict) else None
    if not isinstance(datas, dict):
        raise SafeError("信息收集详情缺失")
    return datas


def get_collector_form_fields(
    client: HttpClient, form_wid: str, collector_wid: str
) -> List[Dict[str, Any]]:
    body = {
        "pageSize": 50,
        "pageNumber": 1,
        "formWid": form_wid,
        "collectorWid": collector_wid,
    }
    ret = client.request(
        "https://{host}/wec-counselor-collector-apps/stu/collector/getFormFields".format(
            host=client.host
        ),
        body,
    )
    rows = ((ret.get("datas") or {}) if isinstance(ret, dict) else {}).get("rows")
    if not isinstance(rows, list):
        raise SafeError("表单字段列表缺失")
    return [row for row in rows if isinstance(row, dict)]


def submit_collector_form(
    client: HttpClient,
    form_wid: str,
    collect_wid: str,
    school_task_wid: Any,
    rows: List[Dict[str, Any]],
    address: str,
) -> bool:
    body = {
        "formWid": form_wid,
        "collectWid": collect_wid,
        "schoolTaskWid": school_task_wid,
        "form": rows,
        "address": address,
        "uaIsCpadaily": True,
    }
    ret = client.request(
        "https://{host}/wec-counselor-collector-apps/stu/collector/submitForm".format(
            host=client.host
        ),
        body,
    )
    return isinstance(ret, dict) and ret.get("message") == "SUCCESS"


def auto_fill(rows: List[Dict[str, Any]]) -> None:
    for item in rows:
        field_items = item.get("fieldItems")
        if not isinstance(field_items, list):
            continue
        index = 0
        while index < len(field_items):
            field = field_items[index]
            if isinstance(field, dict) and field.get("isSelected") == 1:
                index += 1
            else:
                field_items.pop(index)


def find_local_item(
    local_rows: List[Dict[str, Any]], key_value_list: List[Tuple[str, Any]]
) -> Optional[Dict[str, Any]]:
    for item in local_rows:
        if not isinstance(item, dict):
            continue
        matched = True
        for key, value in key_value_list:
            if item.get(key) != value:
                matched = False
                break
        if matched:
            return item
    return None


def merge_form_from_template(
    remote_form: List[Dict[str, Any]], local_form: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    for item in remote_form:
        local = find_local_item(local_form, [("title", item.get("title"))])
        if local is None:
            raise SafeError("本地表单模板缺少对应题目，请手工补全后重试")
        item["value"] = local.get("value")
        remote_fields = item.get("fieldItems")
        local_fields = local.get("fieldItems")
        if isinstance(remote_fields, list) and isinstance(local_fields, list):
            for field in remote_fields:
                if not isinstance(field, dict):
                    continue
                matched = find_local_item(
                    [f for f in local_fields if isinstance(f, dict)],
                    [("content", field.get("content"))],
                )
                if matched is None:
                    raise SafeError("本地表单选项与线上不一致，请更新模板")
                field["isSelected"] = matched.get("isSelected")
    auto_fill(remote_form)
    return remote_form


def process_collectors(
    client: HttpClient, address: str, formdb: Path
) -> Tuple[str, str]:
    collect_list = get_collector_list(client)
    pending = [item for item in collect_list if not item.get("isHandled")]
    if not pending:
        return "alreadyComplete", "无待处理信息收集任务"

    submitted = 0
    for item in pending:
        detail = get_collector_detail(client, str(item.get("wid")))
        collector = detail.get("collector")
        if not isinstance(collector, dict):
            raise SafeError("信息收集任务详情缺少 collector")
        form_wid = collector.get("formWid")
        collect_wid = collector.get("wid")
        school_task_wid = collector.get("schoolTaskWid")
        remote_form = get_collector_form_fields(
            client, str(form_wid), str(collect_wid)
        )
        sender = str(item.get("senderUserName") or collect_wid or "unknown")
        # 仅用发送者用户名作为模板文件名（上游约定），禁止路径穿越。
        safe_name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", sender)[:80] or "form"
        form_path = formdb / "{}.json".format(safe_name)
        if not form_path.is_file():
            form_path.write_text(
                json.dumps(remote_form, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            raise SafeError(
                "已写入空白表单模板 {}，请手工填写后重新运行".format(form_path.name)
            )
        try:
            local_form = json.loads(form_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SafeError("本地表单模板无法读取或不是合法 JSON") from exc
        if not isinstance(local_form, list):
            raise SafeError("本地表单模板须为 JSON 数组")
        filled = merge_form_from_template(remote_form, local_form)
        ok = submit_collector_form(
            client,
            str(form_wid),
            str(collect_wid),
            school_task_wid,
            filled,
            address,
        )
        if not ok:
            raise SafeError("信息收集提交未确认成功")
        submitted += 1
    return "success", "已提交 {} 份信息收集".format(submitted)


def process_notices(client: HttpClient) -> Tuple[str, str]:
    notices = get_notice_list(client)
    if not notices:
        return "alreadyComplete", "无待确认通知"
    success = 0
    failed = 0
    for item in notices:
        wid = item.get("noticeWid") or item.get("wid")
        if not wid:
            failed += 1
            continue
        if confirm_notice(client, str(wid)):
            success += 1
        else:
            failed += 1
    if failed:
        return "failure", "通知确认成功 {}，失败 {}".format(success, failed)
    if success:
        return "success", "已确认 {} 条通知".format(success)
    return "alreadyComplete", "无待确认通知"


def notification_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", env("QINGLONG_NOTIFY_SCRIPTS"))
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "DailyCP.py",
        "dailycp_collector.py",
        "candidate.py",
        "scripts/dailycp_collector.py",
        "dailycp",
    }
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
    enabled = any(
        selector
        and any(fnmatch.fnmatchcase(identity, selector) for identity in identities)
        for selector in selectors
    )
    return enabled, "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"


def notify(body: str, dry_run: bool) -> str:
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    if dry_run:
        log("通知：⏭️ 断网预演禁止执行可能联网的通知模块；摘要已生成")
        return "dry-run-skipped"
    paths: List[Path] = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser() / "notify.py")
    paths.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    try:
        module = None
        try:
            import notify as imported  # type: ignore

            module = imported
        except Exception:
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location(
                        "qinglong_notify", path
                    )
                    if spec is None or spec.loader is None:
                        continue
                    candidate = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(candidate)
                    module = candidate
                    break
        if module is not None and callable(getattr(module, "send", None)):
            outcome: List[bool] = []

            def deliver() -> None:
                try:
                    module.send(TITLE, body)
                    outcome.append(True)
                except Exception:
                    outcome.append(False)

            worker = threading.Thread(target=deliver, daemon=True)
            worker.start()
            worker.join(20)
            if outcome and outcome[0]:
                log("通知：✅ 脱敏总结已交给青龙 notify.py")
                return "sent"
            log("通知：⚠️ 投递失败或超时；保留业务退出码")
            return "unavailable-or-failed"
        node = shutil.which("node")
        if node:
            for path in paths:
                js_path = path.with_name("sendNotify.js")
                if not js_path.is_file():
                    continue
                result = subprocess.run(
                    [
                        node,
                        "-e",
                        "Promise.resolve(require(process.argv[1]).sendNotify("
                        "process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                        str(js_path),
                        TITLE,
                        body,
                    ],
                    timeout=20,
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知：✅ 脱敏总结已交给青龙 sendNotify.js")
                    return "sent"
        log("通知：⚠️ 青龙适配器不可用；保留业务退出码")
        return "unavailable-or-failed"
    except Exception:
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
        return "unavailable-or-failed"


class AccountResult:
    def __init__(self, number: int) -> None:
        self.number = number
        self.status = "failure"
        self.identity = "账号{}".format(number)
        self.stats = {key: 0 for key in STATES}
        self.started = time.monotonic()
        self.message = ""


def secrets_for(account: AccountSpec) -> List[str]:
    return [
        item
        for item in (
            account.get("username", ""),
            account.get("password", ""),
        )
        if item
    ]


def run_account(
    result: AccountResult,
    account: AccountSpec,
    formdb: Path,
    timeout: float,
    dry_run: bool,
    confirm_notice_flag: bool,
) -> None:
    secrets = secrets_for(account)
    stages = [
        (1, "解析学校租户并登录"),
        (2, "处理信息收集任务"),
    ]
    if confirm_notice_flag:
        stages.append((3, "确认待办通知"))
    total = len(stages)
    # 学号本身是登录凭据，不当作公开身份打印；仅显示学校名辅助核对。
    result.identity = account["school"]
    log(
        "账号 {}：开始处理（学校 {}）；子任务 {} 项".format(
            result.number, account["school"], total
        )
    )
    client: Optional[HttpClient] = None
    for index, name in stages:
        tick = time.monotonic()
        log("账号 {} 阶段 {}/{}：{}".format(result.number, index, total, name))
        if dry_run:
            result.stats["skipped"] += 1
            log(
                "{} 参数及流程有效，未发送请求；耗时 {:.2f} 秒".format(
                    ICONS["skipped"], time.monotonic() - tick
                )
            )
            continue
        try:
            if index == 1:
                client = HttpClient(timeout)
                host = set_host_by_school(client, account["school"])
                login(client, account["username"], account["password"])
                result.stats["success"] += 1
                log(
                    "{} 已登录主机 {}；耗时 {:.2f} 秒".format(
                        ICONS["success"], host, time.monotonic() - tick
                    )
                )
            elif index == 2:
                assert client is not None
                outcome, detail = process_collectors(
                    client, account["address"], formdb
                )
                result.stats[outcome] += 1
                log(
                    "{} {}；耗时 {:.2f} 秒".format(
                        ICONS[outcome], detail, time.monotonic() - tick
                    )
                )
                if outcome == "failure":
                    raise SafeError(detail)
            else:
                assert client is not None
                outcome, detail = process_notices(client)
                result.stats[outcome] += 1
                log(
                    "{} {}；耗时 {:.2f} 秒".format(
                        ICONS[outcome], detail, time.monotonic() - tick
                    )
                )
                if outcome == "failure":
                    raise SafeError(detail)
        except SafeError as error:
            result.stats["failure"] += 1
            for pending in range(index + 1, total + 1):
                result.stats["skipped"] += 1
                log(
                    "账号 {} 阶段 {}/{}：⏭️ 因前置失败跳过".format(
                        result.number, pending, total
                    )
                )
            result.status = "failure"
            result.message = redact(str(error), secrets)
            log(
                "{} 账号 {} 阶段 {} 失败：{}；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    result.message,
                    time.monotonic() - tick,
                )
            )
            return
        except Exception:
            result.stats["failure"] += 1
            for pending in range(index + 1, total + 1):
                result.stats["skipped"] += 1
            result.status = "failure"
            result.message = "未预期本地错误"
            log(
                "{} 账号 {} 阶段 {} 失败：未预期本地错误，详情已抑制；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    time.monotonic() - tick,
                )
            )
            return

    if dry_run:
        result.status = "dry-run"
        result.message = "DRY_RUN_OK"
    elif result.stats["failure"]:
        result.status = "failure"
    elif result.stats["success"]:
        result.status = "success"
    else:
        result.status = "alreadyComplete"
    elapsed = time.monotonic() - result.started
    log(
        "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f} 秒".format(
            result.number,
            result.identity,
            total,
            result.stats["success"],
            result.stats["alreadyComplete"],
            result.stats["skipped"],
            result.stats["failure"],
            elapsed,
        )
    )


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("DAILYCP_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[AccountSpec] = []
    timeout = float(DEFAULT_TIMEOUT)
    formdb = Path(".")
    confirm_notice_flag = False
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("DAILYCP_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        accounts_data = load_accounts()
        formdb = resolve_formdb(required=not dry_run)
        notice_raw = env("DAILYCP_CONFIRM_NOTICE", "0").lower()
        if notice_raw not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("DAILYCP_CONFIRM_NOTICE 配置无效")
        confirm_notice_flag = notice_raw in TRUE_VALUES
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；表单目录：{}；通知确认：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                str(formdb) if env("DAILYCP_FORMDB") else "预演未要求",
                "开" if confirm_notice_flag else "关",
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    results: List[AccountResult] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            item = AccountResult(number)
            results.append(item)
            run_account(
                item, account, formdb, timeout, dry_run, confirm_notice_flag
            )
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        "success": sum(1 for item in results if item.status == "success"),
        "alreadyComplete": sum(
            1 for item in results if item.status == "alreadyComplete"
        ),
        "failure": sum(1 for item in results if item.status == "failure"),
        "dry-run": sum(1 for item in results if item.status == "dry-run"),
    }
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    if config_error:
        status = "configuration-error"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
    elif failed:
        status = "failure"
    elif dry_run:
        status = "dry-run"
    else:
        status = "success"
    tasks = {key: sum(item.stats[key] for item in results) for key in STATES}
    body = (
        "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
            status,
            account_total,
            succeeded,
            failed,
            counts["dry-run"],
            "是" if config_error else "否",
        )
    )
    log("阶段 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log("阶段 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started))
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total,
            succeeded,
            counts["alreadyComplete"],
            failed,
            counts["dry-run"],
        )
    )
    log(
        "子任务统计：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
            sum(tasks.values()),
            tasks["success"],
            tasks["alreadyComplete"],
            tasks["skipped"],
            tasks["failure"],
        )
    )
    final_label = {
        "success": "SUCCESS",
        "partial-failure": "PARTIAL_FAILURE",
        "failure": "FAILURE",
        "configuration-error": "CONFIG_ERROR",
        "dry-run": "DRY-RUN",
    }.get(status, status.upper())
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态：{}".format(
            finished_at, elapsed, notification, final_label
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total,
                "success": succeeded,
                "alreadyComplete": counts["alreadyComplete"],
                "failure": failed,
                "dryRun": counts["dry-run"],
                "configurationError": bool(config_error),
                "tasks": tasks,
                "notification": notification,
                "startTime": started_at,
                "finishTime": finished_at,
                "durationSeconds": elapsed,
                "exitCode": exit_code,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
