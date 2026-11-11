# -*- coding: utf-8 -*-
# name: 每日打卡签到
# cron: 34 10 * * *
# 来源 Maratrain/DailyCheckIn, checkin.py
# https://github.com/Maratrain/DailyCheckIn
# 上游许可 MIT，保留其源码中的接口参考及署名。
"""独立青龙维护版。每个 QL_CHECKIN_ACCOUNTS 非空行是一个 JSON 账号对象。
仅为对象中明确提供的 mihoyo、kuro、weibo 模块执行原有签到动作。
run 默认签到；test 只验证现有凭据；QL_CHECKIN_DRY_RUN=1 完全离线校验。
凭据通过各官方客户端本人登录后的请求获取，获取说明及字段见 contract.json。

原始接口参考
米游社 https://github.com/Womsxd/MihoyoBBSTools
库街区 https://github.com/mxyooR/Kuro-autosignin
库街区登录 https://github.com/mxyooR/Kuro_login
微博超话 swtmaxx/weibo-auto-checkin

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
        _ql_notify_identities = ('0c4949f3b1b01793', 'scripts/task_0c4949f3.py', 'task_0c4949f3.py', 'task_0c4949f3')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import random
import re
import string
import sys
import time
import uuid
from datetime import datetime
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import URLError


TIMEOUT = 20

# ──────────────────────────── 米游社常量 ────────────────────────────
# Salt 与版本相互对应，跟随米游社客户端更新（参考 MihoyoBBSTools 2026-06-30 更新）
MI_SALT_APP = "47f15f1b66bee46b816115d8e8e6ebb6"
MI_SALT_WEB = "d9200c846b10886e8c874fc33c8f308b"
MI_SALT_X6 = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"
MI_VERSION = "2.109.0"
MI_UA = (
    "Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 "
    f"miHoYoBBS/{MI_VERSION}"
)

MI_QR_CREATE_URL = "https://passport-api.mihoyo.com/account/ma-cn-passport/app/createQRLogin"
MI_QR_QUERY_URL = "https://passport-api.mihoyo.com/account/ma-cn-passport/app/queryQRLoginStatus"
MI_COOKIE_TOKEN_URL = "https://api-takumi.mihoyo.com/auth/api/getCookieAccountInfoBySToken"
MI_ROLES_URL = "https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie"
MI_TASKS_URL = "https://bbs-api.miyoushe.com/apihub/wapi/getUserMissionsState"
MI_BBS_SIGN_URL = "https://bbs-api.miyoushe.com/apihub/app/api/signIn"
MI_SMS_SEND_URL = "https://passport-api.mihoyo.com/account/ma-cn-verifier/verifier/createLoginCaptcha"
MI_SMS_LOGIN_URL = "https://passport-api.mihoyo.com/account/ma-cn-passport/app/loginByMobileCaptcha"
MI_COOKIE_TOKEN_V2_URL = "https://passport-api.mihoyo.com/account/auth/api/getCookieAccountInfoBySToken"
MI_PASSPORT_X4_SALT = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"
MI_RSA_KEY_URLS = [
    "https://passport-api.mihoyo.com/account/ma-cn-passport/app/getRSAKey",
    "https://passport-api.mihoyo.com/account/ma-cn-passport/app/get_by_rsa_key",
    "https://passport-api.mihoyo.com/account/ma-cn-passport/web/rsa_public_key",
]

# 游戏签到：act_id 来自 MihoyoBBSTools setting.py，base 为官方签到活动域名
# extra_headers：米哈游对原神(hk4e)/绝区零(zzz)的签到接口校验专属请求头，缺失会报 -500001
MI_GAMES = {
    "genshin": {"name": "原神", "biz": "hk4e_cn", "act_id": "e202311201442471",
                "base": "https://api-takumi.mihoyo.com/event/luna",
                "extra_headers": {"x-rpc-signgame": "hk4e"}},
    "honkaisr": {"name": "崩坏：星穹铁道", "biz": "hkrpg_cn", "act_id": "e202304121516551",
                 "base": "https://api-takumi.mihoyo.com/event/luna",
                 "extra_headers": {}},
    "zzz": {"name": "绝区零", "biz": "nap_cn", "act_id": "e202406242138391",
            "base": "https://act-nap-api.mihoyo.com/event/luna/zzz",
            "extra_headers": {"x-rpc-signgame": "zzz"}},
    "honkai3rd": {"name": "崩坏3", "biz": "bh3_cn", "act_id": "e202306201626331",
                  "base": "https://api-takumi.mihoyo.com/event/luna",
                  "extra_headers": {}},
}

# 米游币打卡分区（id 与名称来自 MihoyoBBSTools mihoyobbs_List）
MI_BBS_PARTITIONS = {
    "1": "崩坏3", "2": "原神", "3": "崩坏2", "4": "未定事件簿",
    "5": "大别野", "6": "崩坏：星穹铁道", "8": "绝区零",
    "9": "崩坏：因缘精灵", "10": "星布谷地",
}

# ──────────────────────────── 库街区常量 ────────────────────────────
KURO_BASE = "https://api.kurobbs.com"
KURO_SDK_LOGIN_URL = f"{KURO_BASE}/user/sdkLogin"
KURO_MINE_URL = f"{KURO_BASE}/user/mineV2"
KURO_ROLE_LIST_URL = f"{KURO_BASE}/user/role/findRoleList"
KURO_GAME_SIGN_URL = f"{KURO_BASE}/encourage/signIn/v2"
KURO_GAME_SIGN_RECORD_URL = f"{KURO_BASE}/encourage/signIn/queryRecordV2"

KURO_GAMES = {
    "wuwa": {"name": "鸣潮", "game_id": "3", "server_id": "76402e5b20be2c39f095a152090afddc"},
    "pgr": {"name": "战双帕弥什", "game_id": "2", "server_id": "1000"},
}

KURO_GAME_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) KuroGameBox/2.2.0"
)

# ──────────────────────────── 微博超话常量 ────────────────────────────
# 走 m.weibo.cn 移动网页版容器接口（参考 swtmaxx/weibo-auto-checkin 2026-09 实现）
WB_BASE = "https://m.weibo.cn"
WB_FOLLOW_REFERER = f"{WB_BASE}/p/index?containerid=100803_-_followsuper"
WB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

def ds1() -> str:
    """米游社网页端 DS 签名（salt={web}&t={t}&r={r}）"""
    t = str(int(time.time()))
    r = "".join(random.sample(string.ascii_lowercase + string.digits, 6))
    return f"{t},{r},{md5(f'salt={MI_SALT_WEB}&t={t}&r={r}')}"

def ds2(body: str, query: str = "") -> str:
    """米游社 App 端 DS2 签名（salt={x6}&t={t}&r={r}&b={body}&q={query}）"""
    t = str(int(time.time()))
    r = str(random.randint(100001, 200000))
    return f"{t},{r},{md5(f'salt={MI_SALT_X6}&t={t}&r={r}&b={body}&q={query}')}"

def mi_stoken_cookie(m: dict) -> str:
    cookie = f"stoken={m['stoken']};stuid={m['stuid']}"
    if m["stoken"].startswith("v2_"):
        cookie += f";mid={m['mid']}"
    return cookie

def mi_web_cookie(m: dict) -> str:
    account_id = m.get("account_id") or m.get("stuid", "")
    return f"account_id={account_id};cookie_token={m['cookie_token']}"

def mi_web_headers(m: dict) -> dict:
    return {
        "Accept": "application/json, text/plain, */*",
        "DS": ds1(),
        "x-rpc-channel": "miyousheluodi",
        "Origin": "https://webstatic.mihoyo.com",
        "x-rpc-app_version": MI_VERSION,
        "User-Agent": MI_UA,
        "x-rpc-client_type": "5",
        "Referer": "https://act.mihoyo.com/",
        "Accept-Language": "zh-CN,en-US;q=0.8",
        "X-Requested-With": "com.mihoyo.hyperion",
        "Cookie": mi_web_cookie(m),
        "x-rpc-device_id": m["device_id"],
    }

def mi_app_headers(m: dict, body: str) -> dict:
    return {
        "DS": ds2(body),
        "cookie": mi_stoken_cookie(m),
        "x-rpc-client_type": "2",
        "x-rpc-app_version": MI_VERSION,
        "x-rpc-app_id": "bll8iq97cem8",
        "x-rpc-sys_version": "12",
        "x-rpc-channel": "miyousheluodi",
        "x-rpc-device_id": m["device_id"],
        "x-rpc-device_name": "ZCode-Tool",
        "x-rpc-device_model": "PC",
        "x-rpc-h265_supported": "1",
        "Referer": "https://app.mihoyo.com",
        "x-rpc-verify_key": "bll8iq97cem8",
        "Content-Type": "application/json; charset=UTF-8",
        "Accept-Encoding": "gzip",
        "User-Agent": "okhttp/4.9.3",
    }

def ds_x4(query: str = "") -> str:
    """passport 接口专用 DS 签名（x4 salt，DS2 风格）"""
    t = str(int(time.time()))
    r = str(random.randint(100000, 200000))
    return f"{t},{r},{md5(f'salt={MI_PASSPORT_X4_SALT}&t={t}&r={r}&b=&q={query}')}"

def mi_exchange_cookie_token(m: dict) -> bool:
    """新登录的 stoken 换 cookie_token：走 passport 专用接口（对齐 MiyoQian 现网实现）。

    旧接口 api-takumi/auth/api 对刚签发的 stoken 会拒绝（2026-09 收紧），
    此接口要求 stoken 同时出现在查询参数与 cookie 中，并携带 DS(x4) 签名。
    """
    query = f"stoken={m['stoken']}"
    headers = {
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) miHoYoBBS/{MI_VERSION}",
        "x-rpc-app_version": MI_VERSION,
        "x-rpc-client_type": "2",
        "x-requested-with": "com.mihoyo.hyperion",
        "Referer": "https://webstatic.mihoyo.com",
        "x-rpc-device_id": m["device_id"],
        "x-rpc-device_fp": "38d814469b1e4",
        "cookie": f"mid={m['mid']};stoken={m['stoken']}",
        "ds": ds_x4(query),
        "x-rpc-aigis": "",
    }
    data = http_request("GET", MI_COOKIE_TOKEN_V2_URL, headers=headers,
                        params={"stoken": m["stoken"]})
    if data.get("retcode") == 0 and data.get("data", {}).get("cookie_token"):
        m["cookie_token"] = data["data"]["cookie_token"]
        if not m.get("account_id"):
            m["account_id"] = m.get("stuid", "")
        save_config(CONFIG)
        log.info("米游社 cookie_token 已通过 passport 接口兑换成功")
        return True
    log.warning(f"passport 兑换 cookie_token 失败：{data.get('retcode')} {data.get('message')}")
    return False

def mi_refresh_cookie_token(m: dict) -> bool:
    """用 stoken 换新的 cookie_token：先走 passport 兑换接口，失败回退旧接口"""
    if not m.get("stoken"):
        return False
    if mi_exchange_cookie_token(m):
        return True
    # 回退：旧接口（对已建立会话的 stoken 通常有效）
    data = http_request("GET", MI_COOKIE_TOKEN_URL,
                        headers={"Accept": "application/json",
                                 "Cookie": mi_stoken_cookie(m)})
    if data.get("retcode") == 0 and data.get("data", {}).get("cookie_token"):
        m["cookie_token"] = data["data"]["cookie_token"]
        if not m.get("account_id"):
            m["account_id"] = m.get("stuid", "")
        save_config(CONFIG)
        log.info("米游社 cookie_token 已自动刷新")
        return True
    log.warning(f"cookie_token 续期失败：{data.get('retcode')} {data.get('message')}")
    return False

def mi_roles_call(m: dict) -> dict:
    result = http_request("GET", MI_ROLES_URL, headers=mi_web_headers(m),
                          params={"game_biz": "hk4e_cn"})
    if result.get("retcode") == 0:
        for role in (result.get("data") or {}).get("list", []):
            identity = role.get("nickname") or role.get("game_uid")
            if identity:
                log.info(f"米游社官方角色身份：{identity}")
    return result


def mi_ensure_web_auth(m: dict) -> bool:
    """确保网页端登录态可用；失效时用 stoken 续期一次并延迟重试。

    注意：每次换取 cookie_token 都会使旧 token 作废（服务端单活轮换），
    因此不要在无关流程里调用换取接口，续期后稍等片刻再重试。
    """
    log.info("正在检查米游社登录态...")
    if m.get("cookie_token") and mi_roles_call(m).get("retcode") == 0:
        return True
    log.info("cookie_token 无效，尝试用 stoken 续期...")
    if not mi_refresh_cookie_token(m):
        return False
    time.sleep(2)
    return mi_roles_call(m).get("retcode") == 0

def mi_bbs_checkin(m: dict) -> tuple:
    """米游币打卡：逐个分区调用签到接口，返回 (是否全部成功, 失败明细)"""
    # 先查任务状态：米游币已拿满说明含打卡在内的任务全部完成，直接跳过，
    # 避免无谓的打卡请求触发风控验证码
    tasks = http_request("GET", MI_TASKS_URL,
                         headers={"Accept": "application/json, text/plain, */*",
                                  "User-Agent": MI_UA,
                                  "Referer": "https://webstatic.mihoyo.com",
                                  "Cookie": mi_web_cookie(m)},
                         params={"point_sn": "myb"})
    if tasks.get("retcode") == 0:
        t = tasks.get("data", {})
        if t.get("can_get_points") == 0:
            log.info(f"米游币：今日已拿满（已获得 {t.get('already_received_points', '?')}，"
                     f"共 {t.get('total_points', '?')}），打卡跳过")
            return True, []

    all_ok = True
    errors = []
    for gid in m["bbs_gids"]:
        name = MI_BBS_PARTITIONS.get(str(gid), f"分区{gid}")
        log.info(f"正在米游币打卡 [{name}]...")
        body = json.dumps({"gids": str(gid)}, separators=(",", ":"))
        data = http_request("POST", MI_BBS_SIGN_URL,
                            headers=mi_app_headers(m, body), data=body)
        code = data.get("retcode")
        if code == 0:
            log.info(f"米游币打卡 [{name}]：成功")
        elif code == 1008:
            log.info(f"米游币打卡 [{name}]：今日已打卡")
        elif code == 1034:
            log.warning(f"米游币打卡 [{name}]：触发风控验证码，今天请在 App 里手动打卡一次")
            errors.append(f"米游币打卡 [{name}]：触发风控验证码，请在 App 里手动打卡")
            all_ok = False
        elif code == -100:
            log.error(f"米游币打卡 [{name}]：stoken 无权限或已失效"
                      f"（扫码获取的 token 已被米哈游限制权限，请用短信验证码方式重新登录："
                      f"python checkin.py login）")
            return False, [f"米游币打卡 [{name}]：stoken 无权限或已失效，请重新登录"]
        else:
            msg = data.get("message", "")
            if msg in ("今日已签到", "今日已打卡"):
                log.info(f"米游币打卡 [{name}]：今日已打卡")
            else:
                log.warning(f"米游币打卡 [{name}]：失败（{code} {msg}）")
                errors.append(f"米游币打卡 [{name}]：失败（{code} {msg}）")
                all_ok = False
        time.sleep(random.randint(2, 6))
    return all_ok, errors

def mi_game_sign(m: dict) -> tuple:
    """游戏签到领福利：原神/星穹铁道/绝区零/崩坏3，返回 (是否全部成功, 失败明细)"""
    all_ok = True
    errors = []
    for game_key in m["game_sign"]:
        game = MI_GAMES.get(game_key)
        if not game:
            log.warning(f"未知游戏配置项：{game_key}，已跳过")
            continue
        name = game["name"]
        log.info(f"正在检查 {name} 签到...")

        roles_data = http_request("GET", MI_ROLES_URL,
                                  headers=mi_web_headers(m),
                                  params={"game_biz": game["biz"]})
        if roles_data.get("retcode") == -100 and mi_ensure_web_auth(m):
            roles_data = http_request("GET", MI_ROLES_URL,
                                      headers=mi_web_headers(m),
                                      params={"game_biz": game["biz"]})
        if roles_data.get("retcode") != 0:
            log.warning(f"{name}：获取账号角色列表失败（{roles_data.get('retcode')} "
                        f"{roles_data.get('message')}），可能未绑定该游戏")
            errors.append(f"{name}：获取账号角色列表失败（{roles_data.get('retcode')} "
                          f"{roles_data.get('message')}），可能未绑定该游戏")
            all_ok = False
            continue
        roles = roles_data.get("data", {}).get("list", [])
        if not roles:
            log.info(f"{name}：账号未绑定该游戏，跳过")
            continue

        headers = mi_web_headers(m)
        headers.update(game.get("extra_headers", {}))
        rewards = []
        home = http_request("GET", f"{game['base']}/home",
                            headers=headers,
                            params={"lang": "zh-cn", "act_id": game["act_id"]})
        if home.get("retcode") == 0:
            rewards = home["data"].get("awards", [])

        for role in roles:
            uid, region, nick = role["game_uid"], role["region"], role["nickname"]
            time.sleep(random.randint(2, 6))
            info = http_request("GET", f"{game['base']}/info",
                                headers=headers,
                                params={"lang": "zh-cn", "act_id": game["act_id"],
                                        "region": region, "uid": uid})
            if info.get("retcode") != 0:
                log.warning(f"{name} [{nick}]：获取签到信息失败（{info.get('message')}）")
                errors.append(f"{name} [{nick}]：获取签到信息失败（{info.get('message')}）")
                all_ok = False
                continue
            info_data = info["data"]
            if info_data.get("first_bind"):
                log.warning(f"{name} [{nick}]：首次绑定米游社，请先手动签到一次")
                all_ok = False
                errors.append(f"{name}：首次绑定尚未签到")
                continue

            total_day = info_data.get("total_sign_day", 0)
            if info_data.get("is_sign"):
                award = rewards[total_day - 1] if rewards and total_day <= len(rewards) else {}
                log.info(f"{name} [{nick}]：今日已签到"
                         + (f"，奖励「{award.get('name')}」x{award.get('cnt')}" if award else ""))
                continue

            time.sleep(random.randint(2, 6))
            sign = http_request("POST", f"{game['base']}/sign",
                                headers=headers,
                                json={"act_id": game["act_id"], "region": region, "uid": uid})
            if sign.get("retcode") == 0 and sign.get("data", {}).get("success") == 1:
                award = rewards[total_day] if rewards and total_day < len(rewards) else {}
                log.info(f"{name} [{nick}]：签到成功（本月第 {total_day + 1} 天）"
                         + (f"，获得「{award.get('name')}」x{award.get('cnt')}" if award else ""))
            elif sign.get("retcode") == 0:
                # 风控可能返回 retcode=0，必须查询服务端最终签到状态。
                verified = http_request("GET", f"{game['base']}/info", headers=headers,
                                        params={"lang": "zh-cn", "act_id": game["act_id"],
                                                "region": region, "uid": uid})
                if verified.get("retcode") == 0 and verified.get("data", {}).get("is_sign") is True:
                    log.info(f"{name} [{nick}]：签到完成（复核通过）")
                else:
                    all_ok = False
                    errors.append(f"{name}：未能确认签到结果")
                    log.error(f"{name} [{nick}]：未能确认签到结果")
            else:
                msg = sign.get("message", "")
                if msg in ("今日已签到", "今日已打卡"):
                    log.info(f"{name} [{nick}]：今日已签到")
                else:
                    log.warning(f"{name} [{nick}]：签到失败（{sign.get('retcode')} {msg}）")
                    errors.append(f"{name} [{nick}]：签到失败（{sign.get('retcode')} {msg}）")
                    all_ok = False
    return all_ok, errors

def mihoyo_run() -> tuple:
    """米游社模块入口：米游币打卡 + 游戏签到，返回 (是否全部成功, 失败明细)"""
    m = CONFIG["mihoyo"]
    if not m["enabled"]:
        log.info("米游社模块未启用，跳过")
        return True, []
    if not m["stoken"]:
        log.warning("米游社尚未登录（缺少 stoken），请先执行：python checkin.py login")
        return False, ["尚未登录（缺少 stoken），请先执行登录"]

    ok = True
    errors = []
    fp_bbs = ",".join(sorted(str(g) for g in m["bbs_gids"]))
    fp_game = ",".join(sorted(m["game_sign"]))
    # 米游币打卡只依赖 stoken，放在最前且不依赖网页端登录态
    if m["bbs_checkin"]:
        if is_done("mihoyo_bbs", fp_bbs):
            log.info("米游币打卡：今日已完成（本地记录），跳过")
        else:
            bbs_ok, bbs_errors = mi_bbs_checkin(m)
            if bbs_ok:
                mark_done("mihoyo_bbs", fp_bbs)
            else:
                ok = False
                errors.extend(bbs_errors)
    if not m["game_sign"]:
        return ok, errors
    if mi_ensure_web_auth(m):
        if is_done("mihoyo_game", fp_game):
            log.info("游戏签到：今日已完成（本地记录），跳过")
        else:
            game_ok, game_errors = mi_game_sign(m)
            if game_ok:
                mark_done("mihoyo_game", fp_game)
            else:
                ok = False
                errors.extend(game_errors)
    else:
        log.error("米游社网页端登录态不可用，本次跳过游戏签到（cookie_token 会在下次运行时自动重试）")
        ok = False
        errors.append("网页端登录态不可用，本次游戏签到未执行")
    return ok, errors

def kuro_user_headers(k: dict) -> dict:
    return {
        "osversion": "Android",
        "countrycode": "CN",
        "ip": get_lan_ip(),
        "model": "2211133C",
        "source": "android",
        "lang": "zh-Hans",
        "version": "1.0.9",
        "versioncode": "1090",
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "okhttp/3.10.0",
        "devcode": k["devcode"],
        "distinct_id": k["distinct_id"],
        "token": k["token"],
    }

def kuro_game_headers(k: dict) -> dict:
    return {
        "Accept": "application/json, text/plain, */*",
        "source": "ios",
        "Origin": "https://web-static.kurobbs.com",
        "User-Agent": KURO_GAME_UA,
        "devCode": f"{get_lan_ip()}, {KURO_GAME_UA}",
        "token": k["token"],
        "content-type": "application/x-www-form-urlencoded",
    }

def kuro_request(url: str, headers: dict, data: dict) -> dict:
    result = http_request("POST", url, headers=headers, data=data)
    if not isinstance(result, dict) or "code" not in result:
        return {"code": -1, "message": "响应解析失败", "data": None}
    return result

def kuro_sign() -> tuple:
    """库街区每日补给签到，返回 (是否全部成功, 失败明细)"""
    k = CONFIG["kuro"]
    if not k["enabled"]:
        log.info("库街区模块未启用，跳过")
        return True, []
    if not k["token"]:
        log.warning("库街区尚未登录（缺少 token），请先执行：python checkin.py login")
        return False, ["尚未登录（缺少 token），请先执行登录"]

    log.info("正在检查库街区登录态...")
    mine = kuro_request(KURO_MINE_URL, kuro_user_headers(k), {})
    if mine.get("code") == 220:
        log.error("库街区 token 已过期，请重新执行：python checkin.py login")
        return False, ["token 已过期，请重新登录"]
    if mine.get("code") != 200:
        return False, ["库街区登录校验失败"]
    mine_data = (mine.get("data") or {}).get("mine") or {}
    identity = mine_data.get("nickname") or mine_data.get("userName") or mine_data.get("userId")
    if identity:
        log.info(f"库街区登录身份：{identity}")
    user_id = k["user_id"]
    if mine.get("code") == 200 and mine.get("data", {}).get("mine", {}).get("userId"):
        user_id = str(mine["data"]["mine"]["userId"])
        if user_id != k["user_id"]:
            k["user_id"] = user_id
            save_config(CONFIG)
    if not user_id:
        log.error("库街区：无法获取用户 ID，请重新登录")
        return False, ["无法获取用户 ID，请重新登录"]

    all_ok = True
    errors = []
    current_month = datetime.now().strftime("%m")
    fp = ",".join(sorted(k["games"]))
    if is_done("kuro", fp):
        log.info("库街区每日补给：今日已完成（本地记录），跳过")
        return True, []
    for game_key in k["games"]:
        game = KURO_GAMES.get(game_key)
        if not game:
            log.warning(f"未知库街区游戏配置项：{game_key}，已跳过")
            continue
        name = game["name"]
        log.info(f"正在处理库街区 {name} 每日补给...")

        roles = kuro_request(KURO_ROLE_LIST_URL, kuro_user_headers(k),
                             {"gameId": game["game_id"]})
        if roles.get("code") != 200:
            all_ok = False
            errors.append(f"库街区 {name}：角色查询失败")
            log.error(f"库街区 {name}：角色查询失败")
            continue
        role_list = roles.get("data")
        if not role_list:
            log.info(f"库街区 {name}：未查询到绑定角色，跳过")
            continue

        for role in role_list:
            role_id = str(role.get("roleId", ""))
            server_id = str(role.get("serverId", "")) or game["server_id"]
            role_name = role.get("roleName", role_id)
            time.sleep(random.randint(2, 6))

            sign_data = {
                "gameId": game["game_id"],
                "serverId": server_id,
                "roleId": role_id,
                "userId": user_id,
                "reqMonth": current_month,
            }
            result = kuro_request(KURO_GAME_SIGN_URL, kuro_game_headers(k), sign_data)
            code = result.get("code")
            if code == 200:
                reward = ""
                record = kuro_request(KURO_GAME_SIGN_RECORD_URL, kuro_game_headers(k),
                                      {key: val for key, val in sign_data.items()
                                       if key != "reqMonth"})
                if record.get("code") == 200 and isinstance(record.get("data"), list) and record["data"]:
                    reward = f"，奖励：{record['data'][0].get('goodsName', '未知')}"
                log.info(f"库街区 {name} [{role_name}]：每日补给签到成功{reward}")
            elif code == 1511:
                log.info(f"库街区 {name} [{role_name}]：今日已签到")
            elif code == 220:
                log.error("库街区 token 已过期，请重新执行：python checkin.py login")
                errors.append(f"{name} [{role_name}]：token 已过期，请重新登录")
                return False, errors
            elif code == 1513:
                log.warning(f"库街区 {name} [{role_name}]：用户信息异常，请检查账号绑定")
                errors.append(f"{name} [{role_name}]：用户信息异常，请检查账号绑定")
                all_ok = False
            else:
                log.warning(f"库街区 {name} [{role_name}]：签到失败"
                            f"（{code} {result.get('message')}）")
                errors.append(f"{name} [{role_name}]：签到失败"
                              f"（{code} {result.get('message')}）")
                all_ok = False
    if all_ok:
        mark_done("kuro", fp)
    return all_ok, errors

def _wb_ok(payload: dict) -> bool:
    return payload.get("ok") in (True, 1, "1")

def wb_headers(w: dict) -> dict:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": WB_UA,
        "Referer": WB_FOLLOW_REFERER,
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": w["cookie"],
    }
    for part in w["cookie"].split(";"):
        name, _, value = part.strip().partition("=")
        if name == "XSRF-TOKEN" and value:
            headers["X-XSRF-TOKEN"] = value
            break
    return headers

def wb_get(path: str, w: dict, params: dict = None) -> dict:
    url = path if path.startswith("http") else f"{WB_BASE}{path}"
    return http_request("GET", url, headers=wb_headers(w), params=params)

def wb_normalize_cookie(raw: str) -> str:
    """规范化粘贴内容：支持整行 Cookie 请求头（cookie: xxx）或原始键值对"""
    raw = (raw or "").strip()
    for line in raw.splitlines():
        if re.match(r"^\s*cookie\s*:", line, flags=re.IGNORECASE):
            raw = line.split(":", 1)[1].strip()
            break
    pairs, seen = [], set()
    for part in raw.replace("\n", ";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, value = part.partition("=")
        name, value = name.strip(), value.strip()
        if name and name not in seen:
            seen.add(name)
            pairs.append(f"{name}={value}")
    return "; ".join(pairs)

def wb_verify_login(w: dict) -> tuple:
    """校验微博 Cookie，返回 (是否有效, 昵称或说明)"""
    data = wb_get("/api/config", w)
    d = data.get("data") or {}
    if d.get("login") in (True, 1, "1"):
        name = d.get("screen_name") or str(d.get("uid") or "未知用户")
        return True, name
    return False, "Cookie 已失效或未登录"

def wb_fetch_st(w: dict) -> str:
    data = wb_get("/api/config", w)
    return str((data.get("data") or {}).get("st") or "")

def wb_list_topics(w: dict) -> list:
    """拉取关注的所有超话及其签到状态，返回 [{name, status, scheme}]"""
    topics, seen, since_id = [], set(), None
    for _ in range(100):
        params = {"containerid": "100803_-_followsuper"}
        if since_id:
            params["since_id"] = since_id
        payload = wb_get("/api/container/getIndex", w, params=params)
        if not _wb_ok(payload):
            raise ValueError(payload.get("message") or payload.get("msg") or "接口返回异常")
        cards = (payload.get("data") or {}).get("cards") or []
        for card in cards:
            for item in (card.get("card_group") or []) if isinstance(card, dict) else []:
                name = str(item.get("title_sub") or item.get("title") or "").strip()
                if not name:
                    continue
                status, scheme = "unknown", None
                for b in (item.get("buttons") or []):
                    bname = str(b.get("name") or "").strip()
                    if bname == "签到":
                        sch = str(b.get("scheme") or "").strip()
                        if sch.startswith("/api/container/button"):
                            status, scheme = "available", sch
                        break
                    if "已签" in bname or bname == "明日再来":
                        status = "signed"
                        break
                key = str(item.get("oid") or item.get("topic_id") or item.get("id") or name)
                if key not in seen:
                    seen.add(key)
                    topics.append({"name": name, "status": status, "scheme": scheme})
        info = (payload.get("data") or {}).get("cardlistInfo") or {}
        nxt = str(info.get("since_id") or "")
        if not nxt or nxt == (since_id or ""):
            break
        since_id = nxt
    else:
        raise ValueError("超话分页超过安全上限，未完整查询")
    return topics

def wb_do_checkin(w: dict, scheme: str) -> tuple:
    """执行单个超话签到，返回 (结果状态, 提示信息)；状态：success/already/failed"""
    payload = wb_get(scheme, w)
    data = payload.get("data") or {}
    message = str(data.get("msg") or data.get("tipMessage")
                  or payload.get("msg") or payload.get("message") or "")
    if str(payload.get("errno") or "") == "100015" or "验签" in message:
        st = wb_fetch_st(w)
        if st:
            payload = wb_get(scheme, w, params={"st": st})
            data = payload.get("data") or {}
            message = str(data.get("msg") or data.get("tipMessage")
                          or payload.get("msg") or payload.get("message") or "")
    code = str(payload.get("code") or "")
    if _wb_ok(payload) or data.get("ok") in (True, 1, "1") or code in ("100000", "382010"):
        return "success", message or "签到成功"
    if code == "382004" or "已签" in message or "明日再来" in message:
        return "already", message or "今日已签到"
    return "failed", message or "签到失败"

def weibo_run() -> tuple:
    """微博超话签到：自动签到所有关注且可签的超话（含原神超话），返回 (是否全部成功, 失败明细)"""
    w = CONFIG["weibo"]
    if not w["enabled"]:
        log.info("微博超话模块未启用，跳过")
        return True, []
    if not w["cookie"]:
        log.warning("微博尚未登录（缺少 Cookie），请先执行：python checkin.py login")
        return False, ["尚未登录（缺少 Cookie），请先执行登录"]
    if is_done("weibo"):
        log.info("微博超话：今日已完成（本地记录），跳过")
        return True, []

    log.info("正在检查微博登录态...")
    ok, who = wb_verify_login(w)
    if not ok:
        log.error("微博 Cookie 已失效，请重新登录（python checkin.py login 或图形界面）")
        return False, ["Cookie 已失效，请重新登录"]
    log.info(f"微博登录有效：{who}")

    try:
        topics = wb_list_topics(w)
    except Exception as e:
        log.error(f"获取超话列表失败：{e}")
        return False, [f"获取超话列表失败：{e}"]

    if any(t["status"] == "unknown" for t in topics):
        return False, ["部分超话签到状态未知"]
    todo = [t for t in topics if t["status"] == "available"]
    already = [t for t in topics if t["status"] == "signed"]
    log.info(f"共关注 {len(topics)} 个超话：待签 {len(todo)}，今日已签 {len(already)}")

    all_ok, success_count = True, 0
    errors = []
    for t in todo:
        try:
            status, msg = wb_do_checkin(w, t["scheme"])
            if status in ("success", "already"):
                log.info(f"超话签到 [{t['name']}]：{msg}")
                success_count += status == "success"
            else:
                log.warning(f"超话签到 [{t['name']}]：失败（{msg}）")
                errors.append(f"超话签到 [{t['name']}]：失败（{msg}）")
                all_ok = False
        except Exception as e:
            log.warning(f"超话签到 [{t['name']}]：异常（{e}）")
            errors.append(f"超话签到 [{t['name']}]：异常（{e}）")
            all_ok = False
        time.sleep(random.randint(2, 5))
    log.info(f"微博超话：本次成功 {success_count}，之前已签 {len(already)}")
    if all_ok:
        mark_done("weibo")
    return all_ok, errors


TITLE = "每日打卡签到"
CATALOG_ID = "0c4949f3b1b01793"
CONFIG = {}
DRY_RUN = os.getenv("QL_CHECKIN_DRY_RUN", "0").lower() in ("1", "true", "yes", "on")
SECRETS = set()
log = logging.getLogger("checkin")


class RedactedOutput(logging.StreamHandler):
    def emit(self, record):
        message = record.getMessage().replace("\r", " ").replace("\n", " ")
        for secret in sorted(SECRETS, key=len, reverse=True):
            message = message.replace(secret, "[凭据已隐藏]")
        record.msg, record.args = message, ()
        super().emit(record)


def setup_logging():
    log.setLevel(logging.INFO)
    handler = RedactedOutput(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
    log.handlers = [handler]
    log.propagate = False


def get_lan_ip():
    # 协议请求头占位值，避免为探测本地地址访问额外服务。
    return "127.0.0.1"


def save_config(cfg):
    # 刷新只更新本进程内存，避免把环境凭据落盘。
    return None


def is_done(module, fingerprint=""):
    # 以服务端当日状态为准，避免旧本地记录跨账号误跳过。
    return False


def mark_done(module, fingerprint=""):
    return None


def safe_messages(value):
    """只保留用于业务判定的精确提示，不打印服务端任意诊断内容。"""
    if isinstance(value, list):
        return [safe_messages(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in ("message", "msg", "tipMessage"):
            if item in ("今日已签到", "今日已打卡", "已签到", "明日再来"):
                result[key] = "今日已签到"
            elif isinstance(item, str) and "验签" in item:
                result[key] = "验签失败"
            else:
                result[key] = "接口返回业务结果，请查看状态码"
        else:
            result[key] = safe_messages(item)
    return result


def http_request(method, url, **kwargs):
    if DRY_RUN:
        raise RuntimeError("离线预演禁止 HTTP 请求")
    parsed = urlsplit(url)
    allowed = {
        "passport-api.mihoyo.com", "api-takumi.mihoyo.com", "bbs-api.miyoushe.com",
        "act-nap-api.mihoyo.com", "api.kurobbs.com", "m.weibo.cn",
    }
    if parsed.scheme != "https" or parsed.hostname not in allowed or parsed.username or parsed.port not in (None, 443):
        raise ValueError("拒绝非官方 HTTPS 接口")
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    headers = kwargs.get("headers", {}).copy()
    params = kwargs.get("params")
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    data = kwargs.get("data")
    if "json" in kwargs:
        data = json.dumps(kwargs["json"], separators=(",", ":")).encode()
        headers.setdefault("Content-Type", "application/json")
    elif isinstance(data, dict):
        data = urlencode(data).encode()
    elif isinstance(data, str):
        data = data.encode()
    # urllib 不自动解压响应，明确请求未压缩 JSON。
    headers["Accept-Encoding"] = "identity"
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        request = Request(url, data=data, headers=headers, method=method)
        with opener.open(request, timeout=TIMEOUT) as response:
            if not 200 <= response.status < 300:
                raise ValueError("接口状态异常")
            body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise ValueError("响应超出安全限制")
            payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("响应结构异常")
        return safe_messages(payload)
    except (URLError, OSError, ValueError):
        log.error("❌ HTTP 请求或响应校验失败，未输出请求参数及响应正文")
        return {"retcode": -1, "code": -1, "ok": 0, "message": "请求失败"}


# 续期会使已有 cookie_token 作废，必须显式授权才执行原上游回退链。
_original_refresh = mi_refresh_cookie_token


def mi_refresh_cookie_token(m):
    if os.getenv("QL_CHECKIN_REFRESH_AUTH", "0").lower() not in ("1", "true", "yes", "on"):
        log.error("凭据需要续期；如接受旧 cookie_token 失效，可设置 QL_CHECKIN_REFRESH_AUTH=1")
        return False
    return _original_refresh(m)


DEFAULTS = {
    "mihoyo": {
        "enabled": True, "device_id": "", "stoken": "", "stuid": "", "mid": "",
        "cookie_token": "", "account_id": "", "bbs_checkin": True,
        "bbs_gids": ["2", "6", "8"], "game_sign": ["genshin", "honkaisr", "zzz"],
    },
    "kuro": {"enabled": True, "token": "", "user_id": "", "devcode": "",
             "distinct_id": "", "games": ["wuwa", "pgr"]},
    "weibo": {"enabled": True, "cookie": ""},
}
SECRET_FIELDS = {"device_id", "stoken", "mid", "cookie_token", "token", "devcode", "distinct_id", "cookie"}


def account_config(raw):
    if not isinstance(raw, dict) or not raw or set(raw) - set(DEFAULTS):
        raise ValueError("账号必须是包含 mihoyo、kuro 或 weibo 的 JSON 对象")
    config = {}
    for name, defaults in DEFAULTS.items():
        supplied = raw.get(name)
        if supplied is None:
            config[name] = dict(defaults, enabled=False)
            continue
        if not isinstance(supplied, dict) or set(supplied) - set(defaults):
            raise ValueError("模块字段未知或类型错误")
        values = dict(defaults, **supplied)
        for key, value in values.items():
            if isinstance(defaults[key], bool):
                if not isinstance(value, bool):
                    raise ValueError("开关字段必须为布尔值")
            elif isinstance(defaults[key], str):
                if not isinstance(value, str):
                    raise ValueError("凭据和标识字段必须为字符串")
                if "\n" in value or "\r" in value:
                    raise ValueError("凭据字段不能包含换行")
            elif not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError("任务选项必须为字符串数组")
        if values["enabled"]:
            required = {"mihoyo": ("stoken", "stuid", "device_id"),
                        "kuro": ("token", "devcode", "distinct_id"), "weibo": ("cookie",)}[name]
            if any(not values[key].strip() for key in required):
                raise ValueError("已启用模块缺少必填凭据或设备字段")
            if name == "mihoyo":
                if values["stoken"].startswith("v2_") and not values["mid"]:
                    raise ValueError("v2 stoken 需要同账号 mid")
                if set(values["game_sign"]) - set(MI_GAMES) or set(values["bbs_gids"]) - set(MI_BBS_PARTITIONS):
                    raise ValueError("米游社任务选项未知")
            if name == "kuro" and set(values["games"]) - set(KURO_GAMES):
                raise ValueError("库街区游戏选项未知")
            if name == "weibo":
                values["cookie"] = wb_normalize_cookie(values["cookie"])
                if not any(part.strip().startswith("SUB=") and part.strip()[4:] for part in values["cookie"].split(";")):
                    raise ValueError("微博 Cookie 缺少 SUB")
        for key in SECRET_FIELDS:
            secret = values.get(key)
            if secret:
                SECRETS.add(secret)
        if name == "weibo":
            for part in values["cookie"].split(";"):
                _, _, secret = part.partition("=")
                if secret.strip():
                    SECRETS.add(secret.strip())
        config[name] = values
    if not any(values["enabled"] for values in config.values()):
        raise ValueError("账号未启用任何模块")
    return config


def verify_module(name):
    values = CONFIG[name]
    if name == "mihoyo":
        # 只查询模式绝不轮换登录凭据。
        return mi_roles_call(values).get("retcode") == 0
    if name == "kuro":
        result = kuro_request(KURO_MINE_URL, kuro_user_headers(values), {})
        mine = (result.get("data") or {}).get("mine") or {}
        identity = mine.get("nickname") or mine.get("userName") or mine.get("userId")
        if identity:
            log.info(f"官方账号身份：{identity}")
        return result.get("code") == 200
    ok, identity = wb_verify_login(values)
    if ok:
        log.info(f"官方账号身份：{identity}")
    return ok


def notify_summary(summary):
    switch = os.getenv("QINGLONG_NOTIFY", "auto").lower()
    if switch in ("0", "false", "no", "off"):
        return "全局关闭"
    selection = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if switch not in ("1", "true", "yes", "on") or selection is not None:
        selectors = re.split(r"[,;\s]+", selection or "")
        identities = [CATALOG_ID, Path(__file__).name, Path(__file__).as_posix()]
        # 支持青龙 scripts 目录相对路径选择器。
        script_path = Path(__file__).as_posix()
        if "/scripts/" in script_path:
            identities.append(script_path.split("/scripts/", 1)[1])
        if not any(fnmatch.fnmatch(identity, pattern) for pattern in selectors if pattern for identity in identities):
            return "未选中此脚本"
    if DRY_RUN:
        log.info("离线预演：通知摘要已生成，网络投递跳过")
        return "离线预演已生成"
    import subprocess
    body = (f"状态 {summary['status']}；账号总数 {summary['accounts']}；"
            f"成功 {summary['success']}；失败 {summary['failed']}；"
            f"模块任务成功 {summary['tasks']['success']}；失败 {summary['tasks']['failed']}")
    paths = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory) / "notify.py")
    paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    loader = "import notify; notify.send(__import__('sys').argv[1], __import__('sys').argv[2])"
    try:
        spec = importlib.util.find_spec("notify")
        if spec is None:
            path = next((path for path in paths if path.is_file()), None)
            if path is None:
                log.warning("⚠️ 未找到青龙 notify.py，业务退出码保持")
                return "通知不可用"
            loader = ("import importlib.util,sys; s=importlib.util.spec_from_file_location('notify',sys.argv[3]); "
                      "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[1],sys.argv[2])")
            command = [sys.executable, "-c", loader, TITLE, body, str(path)]
        else:
            command = [sys.executable, "-c", loader, TITLE, body]
        delivered = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25, check=False)
        return "已调用通知" if delivered.returncode == 0 else "通知失败"
    except Exception:
        log.warning("⚠️ 通知不可用或超时，业务退出码保持")
        return "通知失败"


def main():
    setup_logging()
    started = time.monotonic()
    command = sys.argv[1] if len(sys.argv) == 2 else "run"
    invalid_command = len(sys.argv) > 2 or command not in ("run", "test")
    log.info(f"════ {TITLE} ════")
    log.info(f"开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}；模式 {'离线预演' if DRY_RUN else command}")
    lines = [line.strip() for line in os.getenv("QL_CHECKIN_ACCOUNTS", "").splitlines() if line.strip()]
    log.info(f"账号数量 {len(lines)}")
    summary = {"accounts": len(lines), "success": 0, "failed": 0, "dryRun": DRY_RUN,
               "tasks": {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}}
    configuration_error = invalid_command or not lines
    if invalid_command:
        log.error("❌ 参数错误，仅支持 run 或 test；请在官方客户端获取凭据并配置账号环境变量")
    if not lines:
        log.error("❌ 配置错误，缺少 QL_CHECKIN_ACCOUNTS")
    runners = {"mihoyo": mihoyo_run, "kuro": kuro_sign, "weibo": weibo_run}
    global CONFIG
    for index, line in enumerate(lines, 1):
        account_start = time.monotonic()
        counts = dict.fromkeys(("total", "success", "alreadyComplete", "skipped", "failed"), 0)
        ok = not invalid_command
        log.info(f"账号 {index} 开始")
        try:
            CONFIG = account_config(json.loads(line))
        except (ValueError, TypeError):
            log.error(f"账号 {index} ❌ 配置错误，请检查契约中的 JSON 字段说明")
            configuration_error = True
            ok = False
            CONFIG = {}
        if ok:
            for stage, (name, run) in enumerate(runners.items(), 1):
                before = time.monotonic()
                counts["total"] += 1
                log.info(f"账号 {index} 阶段 {stage}/3 {name} 开始")
                if not CONFIG[name]["enabled"]:
                    counts["skipped"] += 1
                    log.info(f"⏭️ {name} 未配置或已关闭；耗时 {time.monotonic() - before:.2f} 秒")
                    continue
                try:
                    if DRY_RUN:
                        result = True
                        log.info("DRY_RUN_OK 配置校验通过；未发起业务请求或写入凭据")
                    elif command == "test":
                        result = verify_module(name)
                    else:
                        result, _ = run()
                except Exception as error:
                    result = False
                    log.error(f"❌ 模块执行异常 {type(error).__name__}，详情已抑制以保护凭据")
                counts["success" if result else "failed"] += 1
                ok = ok and result
                log.info(f"{'✅' if result else '❌'} 阶段 {stage}/3 {name} {'校验通过' if DRY_RUN else '完成' if result else '失败'}；耗时 {time.monotonic() - before:.2f} 秒")
        if not ok and not counts["total"]:
            counts["total"] = 1
            counts["failed"] = 1
        summary["success" if ok else "failed"] += 1
        for key in counts:
            summary["tasks"][key] += counts[key]
        log.info(f"账号 {index} 模块任务统计 {json.dumps(counts, ensure_ascii=False)}；耗时 {time.monotonic() - account_start:.2f} 秒")
    code = 1 if configuration_error or summary["failed"] else 0
    summary["status"] = ("configuration-error" if configuration_error else "partial-failure" if summary["failed"] and summary["success"] else "failure" if summary["failed"] else "dry-run" if DRY_RUN else "success")
    summary["notification"] = notify_summary(summary)
    summary["elapsedSeconds"] = round(time.monotonic() - started, 2)
    summary["finishTime"] = datetime.now().isoformat(timespec="seconds")
    summary["exitCode"] = code
    log.info("----------------------------------------")
    log.info(f"账号总数 {summary['accounts']}；成功 {summary['success']}；失败 {summary['failed']}")
    log.info(f"模块任务统计 {json.dumps(summary['tasks'], ensure_ascii=False)}；通知 {summary['notification']}")
    log.info(f"总耗时 {summary['elapsedSeconds']} 秒；完成时间 {summary['finishTime']}；最终状态 {summary['status']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
