# -*- coding: utf-8 -*-
# name: 网易云全能打卡
# cron: 53 1 * * *
# SPDX-License-Identifier: MIT
# 来源：Han-cy77/Qinglong_auto，netease_task.py
# 合并来源：deeplee/personal-scripts，netease_music_checkin.py
# 合并提交：c8c7c0f4fd1802df86c32a86c26b5c26cfef5023（MIT）
# 原始提交：4bac7c4f709db60a648c4bd498e99f9c7e66b63b
# 新合并来源：Tsuki-polaris/qinglong-netease-full-sign--，ql_netease_full_sign.js
# 原来源声明：@author Your Name；@version 1.0.0；@license MIT
# 原来源免责声明：本脚本仅供学习交流使用，请勿用于商业用途；
# 使用本脚本造成的任何后果由使用者自行承担；本脚本不存储、不上传任何用户数据；
# 使用前请确认遵守网易云音乐用户服务条款。
"""网易云全能打卡（独立 Python 标准库版本）。

NETEASE_COOKIE：登录网易云音乐网页版，在浏览器开发者工具的网络请求中
复制本账号 Cookie，至少保留 MUSIC_U 和 __csrf；每个非空行为一个账号，
Cookie 内的分号、&、@ 原样保留，禁止跨行拼接账号。
NETEASE_API_BASE：显式配置已信任、兼容网易云 Node.js API 接口的 HTTPS
服务地址。该服务会接收 Cookie；本脚本不安装或调用任何外部应用。
每天 09:30 执行签到、已完成任务奖励领取和等级查询。
NETEASE_SCROBBLE=1 才提交模拟听歌记录（最多 300 首）；默认关闭，避免
未经选择修改播放历史。接口接受记录不代表实际听歌、升级或经验已到账。
NETEASE_DRY_RUN=1 完全断网预演，包括通知和 Bark 都只模拟，不验证账号。
QINGLONG_NOTIFY 默认开启；设为 0/false/no/off 关闭。可选
QINGLONG_NOTIFY_DIR 指向青龙通知模块所在目录，BARK_URL 保留兼容。
日志仅写标准输出，不创建上游的账号昵称日志文件。
兼容 NETEASE_COOKIES（设置时优先于 NETEASE_COOKIE）；每行完整 Cookie，
支持空行、# 注释和包裹整行的引号，不以 & 或 @ 分割账号。
NETEASE_WEB_SIGN_WEAPI=1 使用官方 weapi 网页签到并显示积分，需安装公开
包 pycryptodome；默认仍使用已有 API 网页签到，其他任务保持原有接口。
主来源的连签奖励、云贝余额、黑胶乐签、VIP 每日任务和成长值详情通过
网易云官方 weapi 请求，需安装同一公开包 pycryptodome。若缺少包，这些
阶段明确失败，不会被当作业务成功。
兼容 NETEASE_MUSIC_U：仅在未设置 NETEASE_COOKIE/NETEASE_COOKIES 时
使用；每行仅填写同一账号的 MUSIC_U 值。完整 Cookie 仍是维护版首选。
登录网页 music.163.com 后，F12 → Application → Cookies，复制 MUSIC_U
及 __csrf（同一账号）；API 服务请使用自行信任的兼容 HTTPS 服务，该服务
将接收 Cookie。不能使用来源不明的公共服务。
通知兼容 PUSHPLUS_TOKEN（PushPlus 官网个人中心获取）、SENDKEY
（Server酱官网登录后获取），青龙不可用时依次尝试，Bark 保持独立通知。
默认定时保持 30 9 * * *；原签到订阅为 15 9 * * *，可在面板覆盖为此时间，
不要同时建立两份相同任务。NETEASE_SCROBBLE 只接受 1 开启。
功能盘点：原来源网页签到与维护版网页签到相同，补入直接 weapi 传输、
积分显示、旧 Cookie 解析、PushPlus 与 Server酱通知；维护版全部八个阶段、
四榜单听歌链路、VIP 批量及按 ID 备用链路、Bark 和成功判定均保留。
本次加入上游原有的连签奖励、云贝余额、黑胶乐签、VIP 逐项奖励与成长值
详情，沿用每日 09:30 定时；上游原定时为每日 09:00。

MIT License
Copyright notice: upstream source contains no explicit copyright notice.
Attribution: Han-cy77/Qinglong_auto
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
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
        _ql_notify_identities = ('a8a311f3f5aaa2e6', 'scripts/netease_task.py', 'netease_task.py', 'netease_task')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import datetime
import fnmatch
import importlib.util
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# 青龙容器可能使用 ASCII locale，确保中文日志仍可输出。
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TITLE = '网易云全能打卡'
DISABLED = {'0', 'false', 'no', 'off'}
LIMIT = 2 * 1024 * 1024
SECRETS = []


def log(text, public_uid=False):
    text = str(text)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[凭据已隐藏]')
    if not public_uid:
        text = re.sub(r'1[3-9]\d{9}', '[手机号已隐藏]', text)
    text = ''.join(c if c >= ' ' else ' ' for c in text)
    print(f'[{time.strftime("%H:%M:%S")}] {text}', flush=True)


def nested(data, *paths, default=None):
    for path in paths:
        value = data
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if value is not None:
            return value
    return default


def code(data):
    return nested(data, ('code',), ('data', 'code'))


def good(data):
    return code(data) in (0, 200)


def number(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


class RequestFailure(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, status, msg, headers, newurl):
        return None  # 不把 Cookie 通过重定向转交其他节点


def secure_url(value):
    url = urllib.parse.urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('需配置不含认证信息、查询参数或片段的 HTTPS 地址')
    return value.rstrip('/')


def http_json(url, values, timeout=15, as_json=False, headers=None):
    body = json.dumps(values).encode() if as_json else urllib.parse.urlencode(values).encode()
    request = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json' if as_json else 'application/x-www-form-urlencoded',
        'User-Agent': 'Qinglong-Netease-Maintained/1.0',
        **(headers or {}),
    })
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise RequestFailure('响应超过大小上限')
            value = json.loads(raw)
        if not isinstance(value, dict):
            raise RequestFailure('响应不是 JSON 对象')
        return value
    except RequestFailure:
        raise
    except Exception as exc:
        # 异常文本可能含 URL、Cookie 或服务器内容，禁止输出。
        raise RequestFailure(f'网络或响应异常（{type(exc).__name__}）') from None


def walk(data):
    if isinstance(data, dict):
        yield data
        for child in data.values():
            yield from walk(child)
    elif isinstance(data, list):
        for child in data:
            yield from walk(child)


def collect_task_items(data):
    return list({str(item['userTaskId']): item for item in walk(data)
                 if item.get('userTaskId') is not None}.values())


def collect_unget_ids(data):
    ids = []
    for item in walk(data):
        value = item.get('unGetIds', [])
        if isinstance(value, str):
            value = value.split(',')
        if isinstance(value, list):
            ids.extend(str(v).strip() for v in value if str(v).strip())
    return list(dict.fromkeys(ids))


def claimable(task):
    status = task.get('taskStatus', task.get('status', task.get('taskStatusCode')))
    return task.get('needReceive') is True or str(status).strip().lower() in {
        '1', '2', '20', 'completed', 'done', 'finished'}


MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7"
    "b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280"
    "104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932"
    "575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b"
    "3ece0462db0a22b8e7"
)
PUBKEY = "010001"
_NONCE = b"0CoJUm6Qyw8W8jud"
_IV = b"0102030405060708"


def _aes_encrypt(plaintext, key, iv):
    """AES-128-CBC 加密,带 PKCS7 填充,返回 bytes"""
    padlen = 16 - (len(plaintext) % 16)
    plaintext = plaintext + bytes([padlen]) * padlen
    from Crypto.Cipher import AES
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(plaintext)


def _rsa_encrypt(text):
    """原始 RSA 公钥加密(weapi 专用: 反转字节 → int → pow → 256 hex)"""
    c = pow(int.from_bytes(text[::-1], "big"), int(PUBKEY, 16), int(MODULUS, 16))
    return format(c, "x").zfill(256)


def weapi_encrypt(plain_dict):
    """weapi 加密: 双层 AES-128-CBC + RSA,返回 {'params','encSecKey'}
    第1层: 加密原始 JSON → 输出 base64 字符串
    第2层: 加密第1层的 base64 字符串(utf-8 字节,同样 PKCS7 填充)→ 输出 base64
    """
    data = json.dumps(plain_dict, separators=(",", ":")).encode("utf-8")
    secret = base64.b64encode(os.urandom(16)).decode()[:16].encode()  # 16字节随机key
    inner_b64 = base64.b64encode(_aes_encrypt(data, _NONCE, _IV)).decode()
    params = base64.b64encode(
        _aes_encrypt(inner_b64.encode("utf-8"), secret, _IV)
    ).decode()
    return {
        "params": params,
        "encSecKey": _rsa_encrypt(secret),
    }



def parse_accounts():
    raw = os.getenv('NETEASE_COOKIES', '').strip() or os.getenv('NETEASE_COOKIE', '')
    legacy_music_u = not raw.strip()
    if legacy_music_u:
        raw = os.getenv('NETEASE_MUSIC_U', '')
    accounts = []
    for line in raw.splitlines():
        line = line.strip()
        if len(line) >= 2 and line[0] == line[-1] and line[0] in ('"', "'"):
            line = line[1:-1].strip()
        if line and not line.startswith('#'):
            # 上游仅接受 MUSIC_U 值。分号属于 Cookie 字段分隔，不能作为账号分隔。
            accounts.append('MUSIC_U=' + line + '; os=pc; appver=2.10.6;' if legacy_music_u else line)
    return accounts


def cookie_fields(cookie):
    return dict((k.strip(), v.strip()) for part in cookie.split(';') if '=' in part
                for k, v in [part.split('=', 1)])


class Account:
    def __init__(self, index, cookie, base):
        self.index, self.cookie, self.base = index, cookie, base
        self.stats = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
        self.stage = 0

    def api(self, path, **values):
        return http_json(self.base + path, {'cookie': self.cookie, **values})

    def weapi(self, host, path, values=None):
        if host not in {'music.163.com', 'interface3.music.163.com'}:
            raise RequestFailure('官方接口主机无效')
        fields = dict(values or {})
        fields.setdefault('csrf_token', cookie_fields(self.cookie).get('__csrf', ''))
        try:
            encrypted = weapi_encrypt(fields)
        except ImportError:
            raise RequestFailure('官方 weapi 阶段缺少公开依赖 pycryptodome，请在青龙依赖管理中安装') from None
        return http_json('https://' + host + path, encrypted, headers={
            'Cookie': self.cookie, 'Origin': 'https://music.163.com',
            'Referer': 'https://music.163.com/', 'User-Agent': 'Mozilla/5.0',
        })

    def require(self, data):
        if not good(data):
            raise RequestFailure('接口未返回约定成功码 0/200')
        return data

    def step(self, title, action):
        self.stage += 1
        start = time.monotonic()
        log(f'账号 {self.index} 阶段 {self.stage}：{title}')
        try:
            status, detail = action()
        except Exception as exc:
            status = 'failure'
            detail = str(exc) if isinstance(exc, RequestFailure) else f'处理异常（{type(exc).__name__}）'
        self.stats[status] += 1
        icon = {'success': '✅', 'alreadyComplete': '☑️', 'skipped': '⏭️', 'failure': '❌'}[status]
        log(f'{icon} {title}：{detail}；耗时 {time.monotonic() - start:.2f} 秒')
        return status != 'failure'

    def login(self):
        res = self.require(self.api('/login/status'))
        profile = nested(res, ('data', 'profile'), ('profile',))
        if not isinstance(profile, dict) or not profile:
            raise RequestFailure('登录未确认，请重新获取 MUSIC_U 和 __csrf')
        self.vip = number(profile.get('vipType')) > 0
        name = profile.get('nickname') or profile.get('username') or profile.get('displayName')
        identity = name or profile.get('userId') or f'账号 {self.index}'
        log(f'账号 {self.index} 官方身份：{identity}；会员：{"是" if self.vip else "否"}',
            public_uid=not name and profile.get('userId') is not None)
        return 'success', '登录状态已确认'

    def sign(self, kind):
        if kind == 1 and os.getenv('NETEASE_WEB_SIGN_WEAPI', '0') == '1':
            try:
                values = weapi_encrypt({'type': 1, 'csrf_token': cookie_fields(self.cookie).get('__csrf', '')})
            except ImportError:
                raise RequestFailure('官方 weapi 模式缺少公开依赖 pycryptodome，请在青龙依赖管理中安装') from None
            result = http_json('https://music.163.com/weapi/point/dailyTask', values, headers={
                'Cookie': self.cookie, 'Origin': 'https://music.163.com',
                'Referer': 'https://music.163.com/',
                'User-Agent': 'Mozilla/5.0',
            })
        else:
            result = self.api('/daily_signin', type=kind)
        if code(result) == -2:
            return 'alreadyComplete', '今日已签到'
        self.require(result)
        points = nested(result, ('point',), ('data', 'point'))
        return 'success', '签到接口已确认成功' + (f'，新增积分 {number(points)}' if points is not None else '')

    def yunbei_sign(self):
        result = self.require(self.api('/yunbei/sign'))
        points = number(nested(result, ('point',), ('data', 'point'), default=0))
        return 'success', f'签到接口已确认成功，新增云贝 {points}'

    def yunbei_progress(self):
        result = self.require(self.weapi('music.163.com', '/weapi/pointmall/user/sign/progress'))
        configs = nested(result, ('data', 'lotteryConfig'))
        if not isinstance(configs, list):
            raise RequestFailure('连签奖励列表缺失或格式无效')
        eligible = [item for item in configs if isinstance(item, dict)
                    and number(item.get('baseLotteryId')) > 0
                    and number(item.get('baseLotteryStatus')) == 1]
        received = 0
        failed = 0
        for item in eligible:
            try:
                claim = self.require(self.weapi('music.163.com',
                    '/weapi/pointmall/user/lottery/get',
                    {'userLotteryId': str(item['baseLotteryId'])}))
                if 'data' not in claim or claim['data'] is None:
                    raise RequestFailure('领取响应缺少奖励数据')
                received += 1
                log(f'连签奖励 {received + failed}/{len(eligible)}：✅ 领取已确认')
            except RequestFailure:
                failed += 1
                log(f'连签奖励 {received + failed}/{len(eligible)}：❌ 领取未确认')
        if failed:
            return 'failure', f'可领取 {len(eligible)}，成功 {received}，失败 {failed}'
        if not eligible:
            return 'alreadyComplete', '当前没有可领取的连签奖励'
        return 'success', f'可领取 {len(eligible)}，成功 {received}'

    def yunbei_balance(self):
        result = self.require(self.weapi('music.163.com', '/weapi/v1/user/info'))
        balance = nested(result, ('userPoint', 'balance'), ('data', 'userPoint', 'balance'))
        if balance is None:
            raise RequestFailure('云贝余额字段缺失')
        return 'success', f'当前云贝余额 {number(balance)}'

    def yunbei_tasks(self):
        tasks = collect_task_items(self.require(self.api('/yunbei/tasks/todo')))
        ready = [task for task in tasks if claimable(task)]
        received, failed = 0, 0
        for task in ready:
            values = {'userTaskId': str(task['userTaskId'])}
            if task.get('depositCode') is not None:
                values['depositCode'] = str(task['depositCode'])
            try:
                self.require(self.api('/yunbei/task/finish', **values))
                received += 1
                log(f'云贝奖励 {received + failed}/{len(ready)}：✅ 领取已确认')
            except RequestFailure:
                failed += 1
                log(f'云贝奖励 {received + failed}/{len(ready)}：❌ 领取未确认')
        return ('failure' if failed else 'success'), f'任务 {len(tasks)}，可领取 {len(ready)}，成功 {received}，失败 {failed}'

    def vip_growth(self):
        if not self.vip:
            return 'skipped', '普通账号无 VIP 专属任务'
        tasks = None
        try:
            tasks = self.require(self.api('/vip/tasks'))
        except RequestFailure:
            log('⚠️ VIP 任务查询失败，继续尝试批量领取接口')
        try:
            res = self.require(self.api('/vip/growthpoint/getall'))
        except RequestFailure:
            if tasks is None:
                raise RequestFailure('VIP 查询及批量领取均失败，无法确认成长值')
            ids = collect_unget_ids(tasks)
            if not ids:
                return 'alreadyComplete', '任务查询已确认，无待领取成长值'
            log('⚠️ 批量领取失败，尝试按任务 ID 领取备用接口')
            res = self.require(self.api('/vip/growthpoint/get', ids=','.join(ids)))
        value = number(nested(res, ('growthPoint',), ('score',), ('point',),
                              ('data', 'growthPoint'), ('data', 'score'), ('data', 'point'), default=0))
        return 'success', f'成长值领取接口已确认，新增 {value}'

    def vip_sign(self):
        if not self.vip:
            return 'skipped', '普通账号无黑胶乐签资格'
        result = self.require(self.weapi('interface3.music.163.com',
                                         '/weapi/vip-center-bff/task/sign'))
        if result.get('data') is True:
            return 'success', '黑胶乐签已确认成功，预计新增 3 成长值'
        if result.get('data') is False:
            return 'alreadyComplete', '黑胶乐签今日已完成'
        raise RequestFailure('黑胶乐签响应缺少明确结果')

    def vip_missions(self):
        if not self.vip:
            return 'skipped', '普通账号无 VIP 成长任务'
        result = self.require(self.weapi('interface3.music.163.com',
            '/weapi/middle/vip/mission/user/progress/list'))
        missions = result.get('data')
        if not isinstance(missions, list):
            raise RequestFailure('VIP 成长任务列表缺失或格式无效')
        eligible = []
        for mission in missions:
            if not isinstance(mission, dict):
                continue
            stages = mission.get('stageProgressDTOS')
            if not isinstance(stages, list):
                continue
            eligible.extend(stage for stage in stages if isinstance(stage, dict)
                            and number(stage.get('stageStatus')) == 100
                            and stage.get('userRewardId') and stage.get('userProgressId'))
        received = 0
        failed = 0
        growth = 0
        for stage in eligible:
            try:
                self.require(self.weapi('interface3.music.163.com',
                    '/weapi/middle/vip/mission/user/reward/receive', {
                        'userRewardId': str(stage['userRewardId']),
                        'userProgressId': str(stage['userProgressId']),
                    }))
                received += 1
                growth += number(stage.get('worth') or stage.get('rewardCount'))
                log(f'VIP 每日奖励 {received + failed}/{len(eligible)}：✅ 领取已确认')
            except RequestFailure:
                failed += 1
                log(f'VIP 每日奖励 {received + failed}/{len(eligible)}：❌ 领取未确认')
        if failed:
            return 'failure', f'可领取 {len(eligible)}，成功 {received}，失败 {failed}'
        if not eligible:
            return 'alreadyComplete', '当前没有可领取的 VIP 每日奖励'
        return 'success', f'领取 {received} 项，预计新增成长值 {growth}'

    def vip_info(self):
        if not self.vip:
            return 'skipped', '普通账号无 VIP 成长值详情'
        result = self.require(self.weapi('music.163.com',
            '/weapi/vipnewcenter/app/level/growhpoint/basic'))
        info = nested(result, ('data', 'userLevel'), ('data',))
        if not isinstance(info, dict) or info.get('growthPoint') is None:
            raise RequestFailure('VIP 成长值详情缺失')
        level = info.get('levelName') or ('Lv.' + str(info['level']) if info.get('level') is not None else '未知')
        return 'success', f'VIP 等级 {level}；成长值 {number(info["growthPoint"])}；昨日新增 {number(info.get("yesterdayPoint"))}'

    def scrobble(self):
        if os.getenv('NETEASE_SCROBBLE', '0') != '1':
            return 'skipped', '未显式开启模拟听歌，播放历史不变'
        songs = set()
        for playlist in [3778678, 3779629, 19723756, 2884035]:
            try:
                res = self.require(self.api('/playlist/track/all', id=playlist))
                values = nested(res, ('songs',), ('data', 'songs'), default=[])
                if not isinstance(values, list):
                    raise RequestFailure('榜单歌曲字段无效')
                songs.update(str(s['id']) for s in values if isinstance(s, dict) and s.get('id') is not None)
            except RequestFailure:
                log('⚠️ 榜单读取失败，尝试后续榜单')
            if len(songs) >= 300:
                break
        selected = list(songs)
        random.shuffle(selected)
        selected = selected[:300]
        if not selected:
            raise RequestFailure('未获取可提交的歌曲')
        ok = 0
        for i, song in enumerate(selected, 1):
            try:
                self.require(self.api('/scrobble', id=song, sourceid='al', time=random.randint(60, 250)))
                ok += 1
                log(f'播放记录 {i}/{len(selected)}：✅ 接口接受')
            except RequestFailure:
                log(f'播放记录 {i}/{len(selected)}：❌ 未确认')
            time.sleep(0.15)
        status = 'success' if ok == 300 else 'failure'
        return status, f'已接受 {ok}/300，获取 {len(selected)} 首；不代表真实听歌或经验到账'

    def level(self):
        res = self.require(self.api('/user/level'))
        data = res.get('data')
        if not isinstance(data, dict) or 'level' not in data:
            raise RequestFailure('等级数据缺失')
        count = nested(data, ('nowPlayCount',), ('playCount',), default='未知')
        return 'success', f'当前等级 Lv.{number(data["level"])}；累计听歌 {number(count) if count != "未知" else count} 首'


def notify(summary, dry):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').lower().strip()
    if switch in DISABLED:
        return '已关闭'
    selection = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if selection is not None:
        selectors = re.split(r'[,;\s]+', selection.strip()) if selection.strip() else []
        names = {'6509b5485be83574', 'a8a311f3f5aaa2e6', 'candidate.py',
                 'netease_task.py', 'scripts/netease_task.py'}
        if not any(fnmatch.fnmatch(name, pattern) for name in names for pattern in selectors):
            return '未列入通知名单'
    if dry:
        log('⏭️ 通知预演：青龙、PushPlus、Server酱与 Bark 均不联网')
        return '断网预演'
    body = f'账号总数 {summary["accounts"]}，成功 {summary["succeeded"]}，失败 {summary["failed"]}；状态 {summary["status"]}'
    delivered = False
    try:
        import notify as ql_notify
        ql_notify.send(TITLE, body)
        delivered = True
    except Exception:
        roots = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
        for root in roots:
            if not root:
                continue
            path = Path(root) / 'notify.py'
            if not path.is_file():
                continue
            try:
                spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.send(TITLE, body)
                delivered = True
                break
            except Exception:
                continue
    if not delivered:
        token = os.getenv('PUSHPLUS_TOKEN', '').strip()
        if token:
            try:
                result = http_json('https://www.pushplus.plus/send',
                                   {'token': token, 'title': TITLE, 'content': body}, as_json=True)
                delivered = result.get('code') == 200
                log('✅ PushPlus 已确认送达' if delivered else '⚠️ PushPlus 未确认送达')
            except Exception:
                log('⚠️ PushPlus 不可用，不改变业务退出码')
    if not delivered:
        key = os.getenv('SENDKEY', '').strip()
        if key:
            try:
                result = http_json('https://sctapi.ftqq.com/' + urllib.parse.quote(key, safe='') + '.send',
                                   {'title': TITLE, 'desp': body})
                delivered = result.get('code') == 0
                log('✅ Server酱已确认送达' if delivered else '⚠️ Server酱未确认送达')
            except Exception:
                log('⚠️ Server酱不可用，不改变业务退出码')
    bark = os.getenv('BARK_URL', '').strip()
    if bark:
        try:
            secure_url(bark)
            http_json(bark, {'title': TITLE, 'body': body, 'group': '网易云打卡'}, as_json=True)
            log('✅ Bark 通知已送达')
        except Exception:
            log('⚠️ Bark 通知不可用，不改变业务退出码')
    if not delivered:
        log('⚠️ 青龙通知不可用或发送失败，不改变业务退出码')
    return '已发送' if delivered else '不可用或失败'


def main():
    started = time.monotonic()
    dry = os.getenv('NETEASE_DRY_RUN', '0') == '1'
    legacy_alias = not (os.getenv('NETEASE_COOKIES', '').strip() or os.getenv('NETEASE_COOKIE', '').strip())
    cookies = parse_accounts()
    SECRETS.extend(os.getenv(key, '').strip() for key in ('PUSHPLUS_TOKEN', 'SENDKEY', 'BARK_URL'))
    for cookie in cookies:
        SECRETS.append(cookie)
        SECRETS.extend(part.split('=', 1)[1].strip() for part in cookie.split(';') if '=' in part)
    log(f'===== {TITLE} =====')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "正式"}；账号数：{len(cookies)}')
    results = []
    configuration_error = not cookies
    base = ''
    if not cookies:
        log('❌ 配置错误：缺少必填 NETEASE_COOKIE；兼容 NETEASE_COOKIES 或 NETEASE_MUSIC_U，每行一个账号')
    if not dry:
        try:
            base = secure_url(os.getenv('NETEASE_API_BASE', '').strip())
        except ValueError:
            configuration_error = True
            log('❌ 配置错误：请显式设置可信 NETEASE_API_BASE HTTPS 服务地址')
    for index, cookie in enumerate(cookies, 1):
        account = Account(index, cookie, base)
        before = time.monotonic()
        if configuration_error:
            account.step('配置检查', lambda: ('failure', '全局 API 地址无效，未发送请求'))
        elif not cookie_fields(cookie).get('MUSIC_U') or (
            not legacy_alias and not cookie_fields(cookie).get('__csrf')):
            account.step('凭据格式检查', lambda: ('failure', '缺少 MUSIC_U 或 __csrf；未发送请求'))
        elif dry:
            for title in ['登录状态', '手机签到', '网页签到', '云贝签到', '云贝连签奖励',
                          '云贝奖励领取', '云贝余额', '黑胶乐签', 'VIP 每日奖励',
                          'VIP 成长值及备用接口', 'VIP 成长值详情', '模拟听歌开关', '等级查询']:
                account.step(title, lambda: ('skipped', 'DRY_RUN_OK：未发送请求，未执行副作用，不验证业务成功'))
        elif account.step('登录状态', account.login):
            for title, action in [('手机签到', lambda: account.sign(0)), ('网页签到', lambda: account.sign(1)),
                                  ('云贝签到', account.yunbei_sign), ('云贝连签奖励', account.yunbei_progress),
                                  ('云贝奖励领取', account.yunbei_tasks), ('云贝余额', account.yunbei_balance),
                                  ('黑胶乐签', account.vip_sign), ('VIP 每日奖励', account.vip_missions),
                                  ('VIP 成长值', account.vip_growth), ('VIP 成长值详情', account.vip_info),
                                  ('模拟听歌', account.scrobble), ('等级查询', account.level)]:
                account.step(title, action)
        elapsed = round(time.monotonic() - before, 2)
        log(f'账号 {index} 统计：总任务 {sum(account.stats.values())}，成功 {account.stats["success"]}，已完成 {account.stats["alreadyComplete"]}，跳过 {account.stats["skipped"]}，失败 {account.stats["failure"]}；耗时 {elapsed} 秒')
        results.append({'index': index, **account.stats, 'elapsedSeconds': elapsed})
    failed = sum(r['failure'] > 0 for r in results)
    exit_code = 1 if configuration_error or failed else 0
    status = 'configuration-error' if configuration_error else ('partial-failure' if failed and failed < len(cookies) else 'failure') if failed else 'dry-run' if dry else 'success'
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status,
               'accounts': len(cookies), 'succeeded': len(cookies) - failed if not configuration_error else 0,
               'failed': len(cookies) if configuration_error else failed, 'accountResults': results,
               'exitCode': exit_code}
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    log('----------------------------------------')
    log(f'最终状态：{status}；账号总数 {len(cookies)}，成功 {summary["succeeded"]}，失败 {summary["failed"]}')
    log('子任务统计：' + '，'.join(f'{key}={sum(r[key] for r in results)}' for key in ['success', 'alreadyComplete', 'skipped', 'failure']))
    log(f'总耗时 {summary["elapsedSeconds"]} 秒；通知：{summary["notification"]}；完成时间：{datetime.datetime.now().isoformat(timespec="seconds")}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
