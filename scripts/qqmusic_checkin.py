#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: QQ音乐超级会员福利站签到
# cron: 22 9 * * *
#
# 来源：cbywyz/ha-qqmusic-checkin qqmusic_checkin.py（MIT）
# https://github.com/cbywyz/ha-qqmusic-checkin
# 提交：84511ec5a8b82a453cea8ec28492dfe8a68b0b29
#
# 协议与签名算法出处见上游 THIRD_PARTY_NOTICES.md（LDP924/auto-checkin，
# @jixunmoe/qmweb-sign）。本维护版去掉 Home Assistant 部署依赖、外置通知渠道
# 与默认磁盘凭据落盘，改为青龙环境变量、断网预演、时间轴日志与青龙通知。
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) cbywyz / ha-qqmusic-checkin contributors
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
"""QQ音乐「超级会员 / 会员星动福利站」每日签到（青龙独立维护版）。

功能：
  1. 任务中心每日签到（成长值）
  2. 福利站每日签到 + 成长值 / 周·月里程碑提示
  3. 星愿礼券（502 任务）探券池并领取当日可领券
  4. 星愿赛季旅程激励（心愿值达标档位）
  5. 月度里程碑（签满目标天数后领取）
  6. 月度好礼池（有库存才领）
  7. 会员臻享抽奖（有抽奖券时抽至清零，上限 50）

环境变量：
  QM_ACCOUNT     必填（规范）。每行一个账号：uin|qm_keyst
                 只按第一个 | 分割；禁止用 &、@ 分账号。
                 uin 为 QQ 号 / musicid；qm_keyst 以 Q_H_L_ 开头，
                 可从已登录 QQ音乐 Web/App 请求 Cookie 中抓取。
  QM_KEY         可选兼容。多行 qm_keyst；需配合 QM_UIN。
  QM_UIN         可选兼容。单行共用 UIN，或多行与 QM_KEY 一一对应。
  QM_FEATURES    可选。逗号分隔启用模块，缺省全部启用：
                 task_center_sign,vip_station_sign,coupon,incentives,
                 month_milestone,monthly_gift,lottery
  QM_CHECK_ONLY  1/true/yes/on 只查询状态，不执行签到/领取/抽奖
                 （凭证续期仍可能发生；断网预演下不联网）。
  QM_CACHE_DIR   可选。启用时缓存续期后的 musickey（权限 0600）；
                 未设置则不落盘，仅会话内续期。
  QM_TIMEOUT     单次 HTTP 超时秒数，默认 20，范围 5~60。
  QM_RETRY       单次请求失败重试次数，默认 2，范围 0~5。
  QM_DRY_RUN     1/true/yes/on 完全断网预演。
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略

设计原则（沿用上游）：
  * 先探后做：写操作前先查状态，已签 / 已领不重复写请求
  * 单项隔离：任一模块出错不影响其余模块
  * 不伪造播放、不刷量、不碰补签
  * 绝不打印 qm_keyst / Cookie / Token / 原始响应
"""

from __future__ import annotations

# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re

if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "1560f1e922d139e6",
            "scripts/qqmusic_checkin.py",
            "qqmusic_checkin.py",
            "qqmusic_checkin",
            "candidate.py",
        )
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
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "1560f1e922d139e6"
TASK_NAME = "QQ音乐超级会员福利站签到"
PUBLISH_PATH = "scripts/qqmusic_checkin.py"
PUBLISH_FILENAME = "qqmusic_checkin.py"
API_URL = "https://u6.y.qq.com/cgi-bin/musics.fcg"
UA = "QQMusic 20090008(android 15)"
CN_TZ = timezone(timedelta(hours=8))

CODE_OK = 0
CODE_ALREADY_SIGNED = 14822150
CODE_COUPON_CLAIMED = 14816772
CODE_LOGIN_EXPIRED = 2000

SENSITIVE_RE = re.compile(r"Q_H_L_[A-Za-z0-9_\-=+/]{6,}")
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
DEFAULT_FEATURES = {
    "task_center_sign": True,
    "vip_station_sign": True,
    "coupon": True,
    "incentives": True,
    "month_milestone": True,
    "monthly_gift": True,
    "lottery": True,
}
FEATURE_ORDER = [
    ("task_center_sign", "任务中心签到"),
    ("vip_station_sign", "福利站签到"),
    ("coupon", "星愿礼券"),
    ("incentives", "旅程激励"),
    ("month_milestone", "月里程碑"),
    ("monthly_gift", "月度好礼"),
    ("lottery", "臻享抽奖"),
]
SECRETS: List[str] = []


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def now_text() -> str:
    return now_cn().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return now_cn().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def remember_secret(value: str) -> None:
    value = (value or "").strip()
    if not value:
        return
    SECRETS.append(value)
    if len(value) >= 8:
        SECRETS.append(value)
    for part in re.split(r"[;&]", value):
        part = part.strip()
        if "=" in part:
            _, rhs = part.split("=", 1)
            rhs = rhs.strip()
            if len(rhs) >= 4:
                SECRETS.append(rhs)
        elif len(part) >= 8:
            SECRETS.append(part)


def redact(text: Any, limit: int = 220) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    value = SENSITIVE_RE.sub("Q_H_L_***REDACTED***", value)
    for secret in sorted({item for item in SECRETS if item}, key=len, reverse=True):
        if secret and secret in value:
            value = value.replace(secret, "[已隐藏]")
    value = re.sub(
        r"(?i)(cookie|token|authorization|qm_keyst|musickey|access_token|openid)\s*[:=]\s*[^\s,;|&]+",
        "[敏感字段已隐藏]",
        value,
    )
    value = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", value)
    return value[:limit] if value else "未提供业务消息"


def parse_timeout() -> float:
    raw = os.getenv("QM_TIMEOUT", "20").strip() or "20"
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("QM_TIMEOUT 必须是 5 到 60 的整数") from exc
    if value < 5 or value > 60:
        raise ValueError("QM_TIMEOUT 必须是 5 到 60 的整数")
    return float(value)


def parse_retry() -> int:
    raw = os.getenv("QM_RETRY", "2").strip() or "2"
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("QM_RETRY 必须是 0 到 5 的整数") from exc
    if value < 0 or value > 5:
        raise ValueError("QM_RETRY 必须是 0 到 5 的整数")
    return value


def parse_features() -> Dict[str, bool]:
    raw = os.getenv("QM_FEATURES", "").strip()
    features = dict(DEFAULT_FEATURES)
    if not raw:
        return features
    enabled = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = enabled - set(DEFAULT_FEATURES)
    if unknown:
        raise ValueError("QM_FEATURES 含未知模块：" + ",".join(sorted(unknown)))
    for key in features:
        features[key] = key in enabled
    if not any(features.values()):
        raise ValueError("QM_FEATURES 至少需要启用一个模块")
    return features


def load_accounts() -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    primary = os.getenv("QM_ACCOUNT", "")
    if primary.strip():
        for line_no, line in enumerate(primary.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                raise ValueError(
                    "QM_ACCOUNT 第 {} 行格式无效，应为 uin|qm_keyst（只按首个 | 分割）".format(
                        line_no
                    )
                )
            uin, key = line.split("|", 1)
            uin = uin.strip()
            key = key.strip()
            if not uin.isdigit() or len(uin) < 5:
                raise ValueError("QM_ACCOUNT 第 {} 行 UIN 无效".format(line_no))
            if not key.startswith("Q_H_L_") or len(key) < 16:
                raise ValueError(
                    "QM_ACCOUNT 第 {} 行 qm_keyst 无效（应以 Q_H_L_ 开头）".format(line_no)
                )
            remember_secret(key)
            accounts.append({"uin": uin, "qm_keyst": key, "source": "QM_ACCOUNT"})
        if accounts:
            return accounts
        raise ValueError("QM_ACCOUNT 已设置但没有有效账号行")

    keys = [k.strip() for k in (os.getenv("QM_KEY") or "").splitlines() if k.strip()]
    uin_raw = (os.getenv("QM_UIN") or "").strip()
    if keys and uin_raw:
        uins = [u.strip() for u in uin_raw.splitlines() if u.strip()]
        if len(uins) == 1:
            pairs = [(uins[0], k) for k in keys]
        elif len(uins) == len(keys):
            pairs = list(zip(uins, keys))
        else:
            raise ValueError("兼容模式要求 QM_UIN 单行共用，或与 QM_KEY 行数一致")
        for idx, (uin, key) in enumerate(pairs, 1):
            if not uin.isdigit() or len(uin) < 5:
                raise ValueError("QM_UIN 第 {} 个 UIN 无效".format(idx))
            if not key.startswith("Q_H_L_") or len(key) < 16:
                raise ValueError("QM_KEY 第 {} 行 qm_keyst 无效".format(idx))
            remember_secret(key)
            accounts.append({"uin": uin, "qm_keyst": key, "source": "QM_KEY+QM_UIN"})
        return accounts

    raise ValueError(
        "未配置凭证：请设置 QM_ACCOUNT（每行 uin|qm_keyst），"
        "或兼容别名 QM_KEY + QM_UIN"
    )


def time33(s: str) -> int:
    h = 5381
    for c in s:
        h += (h << 5) + ord(c)
        h &= 0xFFFFFFFF
    return h & 0x7FFFFFFF


def zzc(payload: str) -> str:
    h = sha1(payload.encode()).hexdigest().upper()
    p1 = "".join(h[i] for i in (23, 14, 6, 36, 16, 7, 19))
    p2 = "".join(h[i] for i in (16, 1, 32, 12, 19, 27, 8, 5))
    p3 = bytes(
        v ^ int(h[i * 2 : i * 2 + 2], 16)
        for i, v in enumerate(
            (
                89,
                39,
                179,
                150,
                218,
                82,
                58,
                252,
                177,
                52,
                186,
                123,
                120,
                64,
                242,
                133,
                143,
                161,
                121,
                179,
            )
        )
    )
    return "zzc{}{}{}".format(
        p1, re.sub(rb"[\\/+=]", b"", b64encode(p3)).decode(), p2
    ).lower()


@dataclass
class StepResult:
    key: str
    name: str
    ok: bool
    detail: str
    state: str = "success"
    gained: int = 0


@dataclass
class AccountResult:
    index: int
    identity: str
    ok: bool
    steps: List[StepResult] = field(default_factory=list)
    elapsed: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def stats(self) -> Dict[str, int]:
        stats = {
            "total": len(self.steps),
            "success": 0,
            "already": 0,
            "skipped": 0,
            "failed": 0,
        }
        for step in self.steps:
            if step.state == "alreadyComplete":
                stats["already"] += 1
            elif step.state == "skipped":
                stats["skipped"] += 1
            elif step.ok:
                stats["success"] += 1
            else:
                stats["failed"] += 1
        return stats


class QMClient:
    def __init__(
        self,
        key: str,
        uin: str,
        timeout: float,
        retry: int,
        cache_dir: Optional[str] = None,
    ):
        self.uin = str(uin).strip()
        self.key = str(key).strip()
        self.timeout = timeout
        self.retry = retry
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache = (
            self.cache_dir / "qmkey_{}.txt".format(self.uin) if self.cache_dir else None
        )
        self.rescue: Dict[str, str] = {}
        if self.cache:
            cached = self._read_cache()
            if cached:
                self.key, self.rescue = cached
                remember_secret(self.key)

    def _read_cache(self) -> Optional[Tuple[str, Dict[str, str]]]:
        if not self.cache:
            return None
        try:
            lines = self.cache.read_text(encoding="utf-8").splitlines()
            if lines and lines[0].strip().startswith("Q_H_L_"):
                rescue: Dict[str, str] = {}
                if len(lines) > 1:
                    try:
                        data = json.loads(lines[1])
                        if data.get("openid") and data.get("access_token"):
                            rescue = {
                                "openid": str(data["openid"]),
                                "access_token": str(data["access_token"]),
                            }
                            remember_secret(rescue["access_token"])
                            remember_secret(rescue["openid"])
                    except (ValueError, TypeError):
                        pass
                return lines[0].strip(), rescue
        except OSError:
            pass
        return None

    def _save_cache(self, rescue: Optional[Dict[str, str]] = None) -> None:
        if not self.cache or not self.cache_dir:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            extra = (
                json.dumps(rescue or {}, separators=(",", ":")) if rescue else ""
            )
            self.cache.write_text(
                self.key + ("\n" + extra if extra else ""), encoding="utf-8"
            )
            try:
                os.chmod(self.cache, 0o600)
            except OSError:
                pass
        except OSError as exc:
            log("{} 凭证缓存写入失败（不影响本次）：{}".format(ICONS["warning"], redact(exc)))

    def _cookie(self) -> str:
        return "qm_keyst={k}; qqmusic_key={k}; p_lskey={k}; uin=o{u}".format(
            k=self.key, u=self.uin
        )

    def _open(self, url: str, data: Optional[bytes], headers: Dict[str, str], tag: str) -> str:
        last: Optional[BaseException] = None
        for i in range(self.retry + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read(512 * 1024).decode("utf-8", "replace")
                return raw
            except Exception as exc:  # noqa: BLE001 - 收敛网络异常
                last = exc
                if i < self.retry:
                    log(
                        "{} {} 第 {} 次请求失败，稍后重试".format(
                            ICONS["warning"], tag, i + 1
                        )
                    )
                    time.sleep(min(2 * (i + 1), 6))
        raise RuntimeError("{} 请求失败：{}".format(tag, redact(last)))

    def api(self, module: str, method: str, param: Dict[str, Any], comm: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = json.dumps(
            {
                "comm": comm
                or {
                    "g_tk": time33(self.key),
                    "uin": int(self.uin),
                    "format": "json",
                    "inCharset": "utf-8",
                    "outCharset": "utf-8",
                    "notice": 0,
                    "platform": "h5",
                    "needNewCode": 1,
                    "ct": 23,
                    "cv": 0,
                },
                "req_0": {"module": module, "method": method, "param": param},
            },
            separators=(",", ":"),
        )
        url = "{}?_={}&sign={}".format(API_URL, int(time.time() * 1000), zzc(body))
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": self._cookie(),
            "Referer": "https://y.qq.com/",
            "Origin": "https://y.qq.com",
            "User-Agent": UA,
        }
        raw = self._open(url, body.encode(), headers, method)
        try:
            payload = json.loads(raw).get("req_0", {}) or {}
        except ValueError as exc:
            raise RuntimeError("{} 响应不是 JSON".format(method)) from exc
        if payload.get("code") == CODE_LOGIN_EXPIRED:
            raise RuntimeError("登录态失效（code 2000）：请重新抓包更新 qm_keyst")
        return payload

    def _qq_login(self, param: Dict[str, Any], tag: str = "refresh") -> Dict[str, Any]:
        ds = json.dumps(
            {
                "req1": {
                    "module": "QQConnectLogin.LoginServer",
                    "method": "QQLogin",
                    "param": param,
                }
            },
            separators=(",", ":"),
        )
        url = "{}?sign={}&format=json&inCharset=utf8&outCharset=utf-8&data={}".format(
            API_URL, zzc(ds), urllib.parse.quote(ds)
        )
        headers = {
            "Cookie": self._cookie(),
            "Referer": "https://y.qq.com/",
            "Origin": "https://y.qq.com",
            "User-Agent": UA,
        }
        try:
            raw = self._open(url, None, headers, "QQLogin/" + tag)
            return json.loads(raw).get("req1", {}).get("data", {}) or {}
        except Exception as exc:  # noqa: BLE001
            log("{} 续期 {} 异常，沿用当前 key：{}".format(ICONS["warning"], tag, redact(exc)))
            return {}

    def refresh(self) -> None:
        param = {
            "expired_in": 7776000,
            "musicid": int(self.uin),
            "musickey": self.key,
        }
        result = self._qq_login(param)
        new = result.get("musickey", "")
        rescue = {
            "openid": result.get("openid", ""),
            "access_token": result.get("access_token", ""),
        }
        if (not new or new == self.key) and self.rescue:
            param2 = dict(
                param,
                openid=self.rescue["openid"],
                access_token=self.rescue["access_token"],
            )
            result = self._qq_login(param2, tag="rescue")
            new = result.get("musickey", "")
            rescue = {
                "openid": result.get("openid", "") or self.rescue["openid"],
                "access_token": result.get("access_token", "")
                or self.rescue["access_token"],
            }
        if new and new != self.key:
            remember_secret(str(new))
            self.key = str(new)
            if rescue.get("openid") and rescue.get("access_token"):
                remember_secret(str(rescue["access_token"]))
                remember_secret(str(rescue["openid"]))
                self.rescue = {
                    "openid": str(rescue["openid"]),
                    "access_token": str(rescue["access_token"]),
                }
            else:
                self.rescue = {}
            self._save_cache(self.rescue)
            log("{} 凭证续期成功（会话内已更新）".format(ICONS["success"]))
        else:
            log("凭证续期：未取得新 key，沿用当前 key")


class VipStationSigner(QMClient):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._season_value: Optional[int] = None
        self._task_list: List[Dict[str, Any]] = []

    def _season(self) -> int:
        if self._season_value is None:
            data = self.api(
                "music.vipcgi.StarWishTaskCgi",
                "ListStarWishTask",
                {"source": "renewalplay_station"},
            )
            season = (data.get("data") or {}) or {}
            self._season_value = season.get("seasonID") or 7
            self._task_list = season.get("tasks") or []
        return int(self._season_value)

    def module_task_center_sign(self, check_only: bool = False) -> StepResult:
        data = self.api(
            "music.lvz.MuFest13TaskSvr", "EveryDaySignLvzScore", {"Cmd": "qry"}
        )
        ret = (data.get("data") or {}).get("Ret")
        if ret == 20019:
            return StepResult(
                "task_center_sign",
                "任务中心签到",
                True,
                "今日已签到",
                "alreadyComplete",
            )
        if check_only:
            return StepResult(
                "task_center_sign",
                "任务中心签到",
                True,
                "今日未签到（Ret={}）".format(ret),
                "skipped",
            )
        result = self.api(
            "music.lvz.MuFest13TaskSvr", "EveryDaySignLvzScore", {"Cmd": "get"}
        )
        body = result.get("data") or {}
        if body.get("Ret") == 0:
            got = body.get("Total") if isinstance(body.get("Total"), int) else 0
            detail = (
                "签到成功 成长值+{}".format(got)
                if got
                else "签到成功（数值见 App 明细）"
            )
            return StepResult(
                "task_center_sign", "任务中心签到", True, detail, "success", got
            )
        return StepResult(
            "task_center_sign",
            "任务中心签到",
            False,
            "Ret={} {}".format(body.get("Ret"), body.get("Msg", "")),
            "failure",
        )

    def module_vip_sign(self, check_only: bool = False) -> StepResult:
        month = int(now_cn().strftime("%Y%m"))
        data = self.api(
            "music.vipcgi.RenewalPlaySignInCgi",
            "GetMonthSignInData",
            {"month": month},
        )
        body = data.get("data") or {}
        days = {x.get("day"): x.get("signInStatus") for x in (body.get("days") or [])}
        month_days = body.get("signInDays") or sum(1 for v in days.values() if v == 2)
        today = int(now_cn().strftime("%d"))
        if days.get(today) == 2:
            return StepResult(
                "vip_station_sign",
                "福利站签到",
                True,
                "今日已签（本月 {} 天）".format(month_days),
                "alreadyComplete",
            )
        if check_only:
            return StepResult(
                "vip_station_sign",
                "福利站签到",
                True,
                "今日未签（本月 {} 天）".format(month_days),
                "skipped",
            )
        result = self.api(
            "music.vipcgi.RenewalPlaySignInCgi", "RenewalPlaySignIn", {}
        )
        code = result.get("code")
        if code == CODE_OK:
            rd = result.get("data") or {}
            name = ((rd.get("todayIncentive") or {}).get("incentiveName")) or "奖励"
            gained = 0
            match = re.match(r"(\d+)成长值", name)
            if match:
                gained = int(match.group(1))
            extras = []
            for mk, label in (
                ("weekMilestoneIncentive", "周里程碑"),
                ("monthMilestoneIncentive", "月里程碑"),
            ):
                inc = rd.get(mk) or {}
                if inc.get("incentiveName"):
                    extras.append("{}达成：{}".format(label, inc["incentiveName"]))
            detail = "签到成功 {}（本月 {} 天）".format(name, int(month_days or 0) + 1)
            if extras:
                detail += "；" + "；".join(extras)
            return StepResult(
                "vip_station_sign", "福利站签到", True, detail, "success", gained
            )
        if code == CODE_ALREADY_SIGNED:
            return StepResult(
                "vip_station_sign",
                "福利站签到",
                True,
                "今日已签（幂等，本月 {} 天）".format(month_days),
                "alreadyComplete",
            )
        return StepResult(
            "vip_station_sign",
            "福利站签到",
            False,
            "code={}".format(code),
            "failure",
        )

    def module_coupon(self, check_only: bool = False) -> StepResult:
        self._season()
        t502 = next(
            (t for t in (self._task_list or []) if t.get("taskType") == 502), None
        )
        if t502 and t502.get("taskStatus") == 2:
            return StepResult(
                "coupon", "星愿礼券", True, "今日已完成", "alreadyComplete"
            )
        pool = self.api(
            "music.vipcgi.VipRenewalCouponCgi", "QueryVipRenewCouponInfo", {}
        )
        infos = ((pool.get("data") or {}).get("couponInfos")) or []
        ok = [c for c in infos if c.get("status") == 1]
        if check_only:
            return StepResult(
                "coupon",
                "星愿礼券",
                True,
                "可领 {} 张 / 券池共 {} 张".format(len(ok), len(infos)),
                "skipped",
            )
        if not ok:
            return StepResult(
                "coupon",
                "星愿礼券",
                True,
                "券池今日无可领（{} 张全非可领态）".format(len(infos)),
                "skipped",
            )
        pick = ok[int(now_cn().strftime("%d")) % len(ok)]
        result = self.api(
            "music.vipcgi.VipRenewalCouponCgi",
            "ClaimVipRenewCoupon",
            {"couponID": pick.get("couponID")},
        )
        code = result.get("code")
        if code == CODE_OK:
            reward = (t502 or {}).get("taskReward") or 10
            return StepResult(
                "coupon",
                "星愿礼券",
                True,
                "{} 领取成功 +{} 心愿值".format(
                    pick.get("couponName") or "星愿礼券", reward
                ),
                "success",
            )
        if code == CODE_COUPON_CLAIMED:
            return StepResult(
                "coupon", "星愿礼券", True, "今日已领取", "alreadyComplete"
            )
        return StepResult(
            "coupon", "星愿礼券", False, "code={}".format(code), "failure"
        )

    def module_incentives(self, check_only: bool = False) -> StepResult:
        season = self._season()
        data = self.api(
            "music.vipcgi.StarWishLotteryCgi",
            "GetIncentives",
            {"seasonID": season},
        )
        idata = data.get("data") or {}
        score = idata.get("currentScore") or 0
        unlock = [x for x in (idata.get("incentives") or []) if x.get("status") == 1]
        nxt = next(
            (x for x in (idata.get("incentives") or []) if x.get("status") == 5), None
        )
        if check_only:
            return StepResult(
                "incentives",
                "旅程激励",
                True,
                "心愿值 {}，可领档位 {} 个".format(score, len(unlock)),
                "skipped",
            )
        if unlock:
            result = self.api(
                "music.vipcgi.StarWishLotteryCgi",
                "ClaimIncentives",
                {"seasonID": season},
            )
            if result.get("code") == CODE_OK:
                names = "、".join(
                    "{}({}分)".format(x.get("name"), x.get("score")) for x in unlock
                )
                return StepResult(
                    "incentives",
                    "旅程激励",
                    True,
                    "领取成功：{}".format(names),
                    "success",
                )
            return StepResult(
                "incentives",
                "旅程激励",
                False,
                "code={}".format(result.get("code")),
                "failure",
            )
        if nxt:
            return StepResult(
                "incentives",
                "旅程激励",
                True,
                "心愿值 {}/{}（下档 {}）".format(
                    score, nxt.get("score"), nxt.get("name")
                ),
                "skipped",
            )
        return StepResult(
            "incentives",
            "旅程激励",
            True,
            "心愿值 {}，暂无可领档位".format(score),
            "skipped",
        )

    def module_milestone(self, check_only: bool = False) -> StepResult:
        month = int(now_cn().strftime("%Y%m"))
        data = self.api(
            "music.vipcgi.RenewalPlaySignInCgi",
            "GetMonthSignInMilestoneIncentive",
            {"month": month},
        )
        ms = ((data.get("data") or {}).get("incentives")) or []
        if not ms:
            return StepResult(
                "month_milestone", "月里程碑", True, "本月无里程碑配置", "skipped"
            )
        target = ms[0]
        need = target.get("signInDay") or 28
        status = target.get("incentiveStatus")
        md = self.api(
            "music.vipcgi.RenewalPlaySignInCgi",
            "GetMonthSignInData",
            {"month": month},
        )
        mdata = md.get("data") or {}
        days = {x.get("day"): x.get("signInStatus") for x in (mdata.get("days") or [])}
        signed_cnt = mdata.get("signInDays") or sum(1 for v in days.values() if v == 2)
        label = target.get("incentiveName") or "月度奖励"
        if signed_cnt < need and status not in (2, 3):
            return StepResult(
                "month_milestone",
                "月里程碑",
                True,
                "{}/{} 天（{}）".format(signed_cnt, need, label),
                "skipped",
            )
        if check_only:
            return StepResult(
                "month_milestone",
                "月里程碑",
                True,
                "已达标 {}/{} 天（{}）".format(signed_cnt, need, label),
                "skipped",
            )
        result = self.api(
            "music.vipcgi.RenewalPlaySignInCgi",
            "ClaimMilestoneIncentive",
            {"month": month},
        )
        if result.get("code") == CODE_OK:
            return StepResult(
                "month_milestone",
                "月里程碑",
                True,
                "领取：{}".format(label),
                "success",
            )
        return StepResult(
            "month_milestone",
            "月里程碑",
            False,
            "code={}（{}/{} 天达标待领）".format(
                result.get("code"), signed_cnt, need
            ),
            "failure",
        )

    def module_monthly_gift(self, check_only: bool = False) -> StepResult:
        data = self.api(
            "music.vipcgi.VipRenewalMonthGiftCgi",
            "QueryVipRenewalMonthlyGiftPool",
            {},
        )
        pools = (data.get("data") or {}).get("giftPools") or []
        notes: List[str] = []
        claimed: List[str] = []
        for pool in pools:
            gift = pool.get("gift") or {}
            name = gift.get("giftName") or "月度好礼"
            stock = gift.get("availableStock") or 0
            if pool.get("poolStatus") != 3:
                continue
            if stock <= 0:
                ts = gift.get("nextStockRefreshTime") or 0
                nxt = (
                    datetime.fromtimestamp(ts, CN_TZ).strftime("%H:%M")
                    if ts
                    else "未知"
                )
                notes.append("{} 库存0（{} 补货）".format(name, nxt))
                continue
            if check_only:
                notes.append("{} 可领（库存 {}）".format(name, stock))
                continue
            result = self.api(
                "music.vipcgi.VipRenewalMonthGiftCgi",
                "ReceiveVipRenewalMonthlyGift",
                {"giftPoolType": pool.get("poolType"), "tab": "cjhy"},
            )
            if result.get("code") == CODE_OK:
                claimed.append(name)
            else:
                notes.append("{} code={}".format(name, result.get("code")))
        if claimed:
            detail = "领取：" + "、".join(claimed)
            if notes:
                detail += "；" + "；".join(notes)
            return StepResult(
                "monthly_gift", "月度好礼", True, detail, "success"
            )
        detail = "；".join(notes) if notes else "今日无可领好礼"
        return StepResult("monthly_gift", "月度好礼", True, detail, "skipped")

    def module_lottery(self, check_only: bool = False) -> StepResult:
        data = self.api(
            "music.vipcgi.VipRenewalLotteryCgi", "QueryVipRenewDrawInfo", {}
        )
        draws = (data.get("data") or {}).get("lotteryCount") or 0
        if check_only:
            return StepResult(
                "lottery",
                "臻享抽奖",
                True,
                "可用抽奖券 {} 张".format(draws),
                "skipped",
            )
        if not draws:
            return StepResult("lottery", "臻享抽奖", True, "暂无抽奖券", "skipped")
        prizes: List[str] = []
        for _ in range(min(int(draws), 50)):
            result = self.api(
                "music.vipcgi.VipRenewalLotteryCgi",
                "DrawVipRenewActivity",
                {"lotteryPageType": 1},
            )
            if result.get("code") != CODE_OK:
                return StepResult(
                    "lottery",
                    "臻享抽奖",
                    False,
                    "抽奖中断 code={}；已出：{}".format(
                        result.get("code"), "、".join(prizes) or "无"
                    ),
                    "failure",
                )
            prize = ((result.get("data") or {}).get("prize") or {}).get("prizeName")
            prizes.append(prize or "未具名奖品")
            time.sleep(1)
        return StepResult(
            "lottery",
            "臻享抽奖",
            True,
            "抽 {} 次：{}".format(len(prizes), "、".join(prizes)),
            "success",
        )

    def run_modules(
        self, features: Dict[str, bool], check_only: bool
    ) -> List[StepResult]:
        self.refresh()
        handlers = {
            "task_center_sign": self.module_task_center_sign,
            "vip_station_sign": self.module_vip_sign,
            "coupon": self.module_coupon,
            "incentives": self.module_incentives,
            "month_milestone": self.module_milestone,
            "monthly_gift": self.module_monthly_gift,
            "lottery": self.module_lottery,
        }
        results: List[StepResult] = []
        enabled = [(k, n) for k, n in FEATURE_ORDER if features.get(k, True)]
        total = len(enabled)
        for index, (key, label) in enumerate(enabled, 1):
            stage_started = time.monotonic()
            log("[阶段 {}/{}] 开始：{}".format(index, total, label))
            try:
                step = handlers[key](check_only=check_only)
            except Exception as exc:  # noqa: BLE001
                step = StepResult(
                    key, label, False, "异常：{}".format(redact(exc)), "failure"
                )
            elapsed = time.monotonic() - stage_started
            icon = ICONS.get(step.state, ICONS["success" if step.ok else "failure"])
            log(
                "[阶段 {}/{}] {} {}：{}（耗时 {:.2f}s）".format(
                    index, total, icon, step.name, step.detail, elapsed
                )
            )
            results.append(step)
        return results


def dry_run_modules(features: Dict[str, bool], check_only: bool) -> List[StepResult]:
    mode = "体检预演" if check_only else "签到预演"
    results: List[StepResult] = []
    enabled = [(k, n) for k, n in FEATURE_ORDER if features.get(k, True)]
    total = len(enabled)
    for index, (key, label) in enumerate(enabled, 1):
        stage_started = time.monotonic()
        log("[阶段 {}/{}] 开始：{}".format(index, total, label))
        detail = "DRY_RUN {}：跳过真实请求，假定配置可解析".format(mode)
        step = StepResult(key, label, True, detail, "skipped")
        elapsed = time.monotonic() - stage_started
        log(
            "[阶段 {}/{}] {} {}：{}（耗时 {:.2f}s）".format(
                index, total, ICONS["skipped"], step.name, step.detail, elapsed
            )
        )
        results.append(step)
    return results


def notification_selected() -> bool:
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False
    selectors = [part for part in re.split(r"[,;\s]+", raw.strip()) if part]
    script_path = str(Path(__file__).as_posix())
    names = {
        CATALOG_ID,
        Path(__file__).name,
        "candidate.py",
        "qqmusic_checkin.py",
        PUBLISH_FILENAME,
        PUBLISH_PATH,
        script_path,
    }
    for selector in selectors:
        if selector == "*":
            return True
        if any(fnmatch.fnmatch(name, selector) for name in names):
            return True
    return False


def notification_enabled() -> bool:
    value = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return notification_selected()
    if value not in {"", "auto"}:
        log("{} QINGLONG_NOTIFY 值无效，按 auto 处理".format(ICONS["warning"]))
    return notification_selected()


def python_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    return paths


def js_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "sendNotify.js")
    paths.extend(
        [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
    )
    return paths


def send_notification(title: str, body: str, dry_run: bool) -> str:
    if not notification_enabled():
        log("通知状态：已按 QINGLONG_NOTIFY 或脚本选择规则关闭")
        return "disabled"
    if dry_run:
        log("通知状态：断网预演中仅生成脱敏通知摘要，不调用通知网络")
        return "dry-run"

    python_runner = (
        "import importlib,importlib.util,json,sys;"
        "sys.path.insert(0,sys.argv[2]);"
        "p=sys.argv[1];"
        "s=importlib.util.spec_from_file_location('qinglong_notify',p) if p else None;"
        "m=importlib.util.module_from_spec(s) if s else importlib.import_module('notify');"
        "s.loader.exec_module(m) if s else None;"
        "a=json.load(sys.stdin);m.send(a['title'],a['body'])"
    )
    paths: List[Optional[Path]] = [None] + [
        path for path in python_notifier_paths() if path.is_file()
    ]
    for path in paths:
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    python_runner,
                    str(path) if path else "",
                    str(Path(__file__).resolve().parent),
                ],
                input=json.dumps({"title": title, "body": body}, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                log(
                    "通知状态：{} 已调用".format(
                        "notify.py" if path else "notify.send"
                    )
                )
                return "sent"
        except Exception:
            continue

    node = shutil.which("node")
    if node:
        js_runner = (
            "const n=require(process.argv[1]);"
            "Promise.resolve(n.sendNotify(process.argv[2],process.argv[3]))"
            ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
        )
        for path in js_notifier_paths():
            if not path.is_file():
                continue
            try:
                result = subprocess.run(
                    [node, "-e", js_runner, str(path), title, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知状态：sendNotify.js 已调用")
                    return "sent"
            except Exception:
                continue

    log(
        "{} 通知状态：未找到可用通知器或通知发送失败，不改变业务退出码".format(
            ICONS["warning"]
        )
    )
    return "unavailable"


def print_summary(summary: Dict[str, Any]) -> None:
    print(
        "TASK_SUMMARY="
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )


def finish_config_error(
    started_at: str, overall_started: float, dry_run: bool, message: str
) -> int:
    log("账号数量：0")
    log("[0/0] {} 配置错误：{}".format(ICONS["failure"], message))
    body = "账号总数：0；成功：0；失败：1；状态：配置错误"
    notify_state = send_notification(TASK_NAME, body, dry_run)
    finished_at = now_text()
    print("-" * 56, flush=True)
    print("账号结果：总数 0，成功 0，失败 1", flush=True)
    print("子任务结果：总数 0，成功 0，已完成 0，跳过 0，失败 0", flush=True)
    print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started), flush=True)
    print("完成时间：{}".format(finished_at), flush=True)
    print("通知状态：{}".format(notify_state), flush=True)
    print("最终状态：CONFIG_ERROR", flush=True)
    print_summary(
        {
            "status": "configuration-error",
            "mode": "dry-run" if dry_run else "live",
            "accounts": {"total": 0, "success": 0, "failed": 1},
            "tasks": {
                "total": 0,
                "success": 0,
                "alreadyComplete": 0,
                "skipped": 0,
                "failed": 0,
            },
            "notification": notify_state,
            "startedAt": started_at,
            "finishedAt": finished_at,
        }
    )
    return 1


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = truthy("QM_DRY_RUN")
    check_only = truthy("QM_CHECK_ONLY")

    print("=" * 56, flush=True)
    print("{} | 独立维护版".format(TASK_NAME), flush=True)
    print("开始时间：{}".format(started_at), flush=True)
    if dry_run:
        mode_text = "DRY_RUN（完全断网）"
    elif check_only:
        mode_text = "LIVE / CHECK_ONLY（只查不领）"
    else:
        mode_text = "LIVE"
    print("运行模式：{}".format(mode_text), flush=True)
    print("=" * 56, flush=True)

    try:
        timeout = parse_timeout()
        retry = parse_retry()
        features = parse_features()
        accounts = load_accounts()
    except ValueError as exc:
        return finish_config_error(started_at, overall_started, dry_run, str(exc))

    cache_dir = os.getenv("QM_CACHE_DIR", "").strip() or None
    enabled_names = [name for key, name in FEATURE_ORDER if features.get(key, True)]
    log("账号数量：{}".format(len(accounts)))
    log("启用模块：" + "、".join(enabled_names))
    if cache_dir:
        log("凭证缓存目录已启用（仅写入续期后的 musickey）")
    else:
        log("凭证缓存：未启用 QM_CACHE_DIR（不落盘）")

    results: List[AccountResult] = []
    for index, account in enumerate(accounts, 1):
        started = time.monotonic()
        identity = account["uin"]
        log("----- 账号 {}/{} | UID {} -----".format(index, len(accounts), identity))
        log("账号身份：{}".format(identity))
        if dry_run:
            steps = dry_run_modules(features, check_only)
            item = AccountResult(
                index=index,
                identity=identity,
                ok=True,
                steps=steps,
                elapsed=time.monotonic() - started,
            )
        else:
            try:
                signer = VipStationSigner(
                    account["qm_keyst"],
                    account["uin"],
                    timeout=timeout,
                    retry=retry,
                    cache_dir=cache_dir,
                )
                steps = signer.run_modules(features, check_only)
                ok = all(step.ok for step in steps)
                errors = [step.detail for step in steps if not step.ok]
                item = AccountResult(
                    index=index,
                    identity=identity,
                    ok=ok,
                    steps=steps,
                    elapsed=time.monotonic() - started,
                    errors=errors,
                )
            except Exception as exc:  # noqa: BLE001
                err = redact(exc)
                log("{} 账号运行失败：{}".format(ICONS["failure"], err))
                item = AccountResult(
                    index=index,
                    identity=identity,
                    ok=False,
                    steps=[StepResult("overall", "整体", False, err, "failure")],
                    elapsed=time.monotonic() - started,
                    errors=[err],
                )
        stats = item.stats
        log(
            "账号统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}s".format(
                stats["total"],
                stats["success"],
                stats["already"],
                stats["skipped"],
                stats["failed"],
                item.elapsed,
            )
        )
        results.append(item)

    success_accounts = sum(1 for item in results if item.ok)
    failed_accounts = len(results) - success_accounts
    task_totals = {"total": 0, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    for item in results:
        for key in task_totals:
            task_totals[key] += item.stats[key]

    if dry_run:
        final_status = "DRY-RUN"
        summary_status = "dry-run"
        exit_code = 0 if failed_accounts == 0 else 1
        print("DRY_RUN_OK", flush=True)
    elif failed_accounts == 0:
        final_status = "SUCCESS"
        summary_status = "success"
        exit_code = 0
    elif success_accounts == 0:
        final_status = "FAILURE"
        summary_status = "failure"
        exit_code = 1
    else:
        final_status = "PARTIAL_FAILURE"
        summary_status = "partial-failure"
        exit_code = 1

    body = "账号总数：{}；成功：{}；失败：{}；状态：{}".format(
        len(results), success_accounts, failed_accounts, final_status
    )
    notify_state = send_notification(TASK_NAME, body, dry_run)
    finished_at = now_text()

    print("-" * 56, flush=True)
    print(
        "账号结果：总数 {}，成功 {}，失败 {}".format(
            len(results), success_accounts, failed_accounts
        ),
        flush=True,
    )
    print(
        "子任务结果：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
            task_totals["total"],
            task_totals["success"],
            task_totals["already"],
            task_totals["skipped"],
            task_totals["failed"],
        ),
        flush=True,
    )
    print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started), flush=True)
    print("完成时间：{}".format(finished_at), flush=True)
    print("通知状态：{}".format(notify_state), flush=True)
    print("最终状态：{}".format(final_status), flush=True)
    print_summary(
        {
            "status": summary_status,
            "mode": "dry-run" if dry_run else "live",
            "accounts": {
                "total": len(results),
                "success": success_accounts,
                "failed": failed_accounts,
            },
            "tasks": {
                "total": task_totals["total"],
                "success": task_totals["success"],
                "alreadyComplete": task_totals["already"],
                "skipped": task_totals["skipped"],
                "failed": task_totals["failed"],
            },
            "notification": notify_state,
            "startedAt": started_at,
            "finishedAt": finished_at,
        }
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
