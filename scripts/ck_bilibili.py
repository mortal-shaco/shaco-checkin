# -*- coding: utf-8 -*-
# name: Bilibili 每日任务
# cron: 30 8 * * *
# 上游：OreosLab/checkinpanel ck_bilibili.py
# 来源提交：911402e4b2e559ffd62c4949a971ddd6834edd7d
# SPDX-License-Identifier: MIT
# 上游提供的源文件没有额外版权声明；原有接口文档出处保留如下：
# https://github.com/SocialSisterYi/bilibili-API-collect
"""独立维护版。配置说明见配套 contract.json；仅依赖 Python 标准库。
Cookie 从本人登录后的 www.bilibili.com 浏览器开发者工具请求头获取，
须含 SESSDATA 和 bili_jct。BILIBILI_COOKIES 每行完整 Cookie，等号后原样保留。
BILIBILI 兼容原配置的 JSON 数组或 {"BILIBILI": [...]}；每项含 cookie、
coin_num、coin_type、silver2coin。改变状态的高风险动作必须显式配置。
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
import datetime
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = 'Bilibili 每日任务'
FALSE = {'0', 'false', 'no', 'off'}
TRUE = {'1', 'true', 'yes', 'on'}


class TaskError(Exception):
    """只含安全的本地错误文本。"""


def log(text):
    print(f'[{time.strftime("%H:%M:%S")}] {text}', flush=True)


def flag(name, default=False):
    value = os.getenv(name, '1' if default else '0').strip().lower()
    if value not in FALSE | TRUE:
        raise TaskError(f'{name} 必须是 1 或 0')
    return value in TRUE


def integer(value, name, low, high):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise TaskError(f'{name} 必须是整数')
    value = int(value)
    if not low <= value <= high:
        raise TaskError(f'{name} 超出允许范围 {low}~{high}')
    return value


def parse_cookie(raw):
    if not isinstance(raw, str) or any(c in raw for c in '\r\n'):
        raise TaskError('Cookie 必须是单行字符串')
    fields = {}
    for part in raw.split(';'):
        if not part.strip():
            continue
        key, sep, value = part.strip().partition('=')
        if not sep or not key or not value or not re.fullmatch(r'[A-Za-z0-9_]+', key):
            raise TaskError('Cookie 字段格式错误')
        fields[key] = value
    if not fields.get('SESSDATA') or not fields.get('bili_jct'):
        raise TaskError('Cookie 缺少 SESSDATA 或 bili_jct')
    return fields


def account_inputs():
    raw = os.getenv('BILIBILI_COOKIES') or os.getenv('BILIBILI_COOKIE')
    if raw and raw.strip():
        return [{'cookie': line.strip()} for line in raw.splitlines() if line.strip()]
    legacy = os.getenv('BILIBILI', '')
    if legacy.strip():
        try:
            result = json.loads(legacy)
        except (ValueError, TypeError):
            raise TaskError('BILIBILI JSON 格式错误') from None
        if isinstance(result, dict):
            result = result.get('BILIBILI')
        if not isinstance(result, list) or not result:
            raise TaskError('BILIBILI 必须包含非空账号数组')
        return result
    raise TaskError('请设置 BILIBILI_COOKIES，每个非空行一个账号')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口发生重定向，已阻止凭据转发')


class HTTP:
    HOSTS = {'api.bilibili.com', 'api.live.bilibili.com', 'manga.bilibili.com'}

    def __init__(self, cookies, dry):
        self.cookies = cookies
        self.dry = dry
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, path, method='GET', data=None, json_body=False, accepted=(0,)):
        if self.dry:
            raise TaskError('预演禁止调用 HTTP')
        url = urllib.parse.urlsplit(path)
        if url.scheme != 'https' or url.hostname not in self.HOSTS:
            raise TaskError('请求地址不在服务白名单')
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/',
                   'Cookie': '; '.join(f'{k}={v}' for k, v in self.cookies.items())}
        payload = None
        if method == 'POST':
            if json_body:
                payload = json.dumps(data or {}).encode()
                headers['Content-Type'] = 'application/json'
            else:
                payload = urllib.parse.urlencode(data or {}).encode()
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
        request = urllib.request.Request(path, data=payload, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise TaskError('响应过大')
            result = json.loads(body)
        except TaskError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise TaskError('网络、超时或响应解析失败') from None
        if not isinstance(result, dict) or type(result.get('code')) is not int:
            raise TaskError('响应缺少有效业务码')
        if result['code'] not in accepted:
            # 漫画上游唯一明确的重复签到响应，不打印服务端原文。
            if path.endswith('/ClockIn') and result.get('msg') == 'clockin clockin is duplicate':
                return {'code': result['code'], 'already': True}
            raise TaskError(f'业务失败（代码 {result["code"]}）')
        return result


def data_dict(result):
    data = result.get('data')
    if not isinstance(data, dict):
        raise TaskError('响应缺少业务数据')
    return data


class Account:
    def __init__(self, index, config, dry):
        self.index, self.config, self.dry = index, config, dry
        self.counts = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
        self.stage = 0
        self.start = time.monotonic()
        self.nav = None
        self.videos = []
        self.http = None

    def step(self, name, action, enabled=True):
        self.stage += 1
        began = time.monotonic()
        log(f'账号 {self.index} 阶段 {self.stage}：{name}')
        try:
            if not enabled:
                status, detail = 'skipped', '未启用'
            elif self.dry:
                status, detail = 'skipped', 'DRY_RUN_OK：配置验证通过，未发送请求、未改变状态'
            else:
                status, detail = action()
            self.counts[status] += 1
            icon = {'success': '✅', 'alreadyComplete': '☑️', 'skipped': '⏭️'}[status]
            log(f'{icon} {name}：{detail}；耗时 {time.monotonic()-began:.2f} 秒')
            return status != 'skipped'
        except TaskError as error:
            self.counts['failure'] += 1
            log(f'❌ {name}：{error}；耗时 {time.monotonic()-began:.2f} 秒')
        except Exception:
            self.counts['failure'] += 1
            log(f'❌ {name}：响应字段或本地处理异常；耗时 {time.monotonic()-began:.2f} 秒')
        return False

    def nav_info(self):
        result = data_dict(self.http.call('https://api.bilibili.com/x/web-interface/nav'))
        if result.get('isLogin') is not True or not isinstance(result.get('mid'), int):
            raise TaskError('账号未登录或用户信息无效')
        self.nav = result
        # 仅打印官方非凭据身份；折叠换行以免伪造日志。
        identity = ' '.join(str(result.get('uname', '')).split())
        log(f'账号 {self.index} 昵称：{identity}；公开 UID：{result["mid"]}')
        return 'success', '已验证登录状态'

    def sign(self, manga=False):
        if manga:
            result = self.http.call('https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn',
                                    'POST', {'platform': 'android'})
        else:
            result = self.http.call('https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign',
                                    accepted=(0, 1011040))
        if result.get('already') or result['code'] == 1011040:
            return 'alreadyComplete', '今天已签到'
        return 'success', '签到业务码为 0'

    def load_videos(self):
        data = data_dict(self.http.call('https://api.bilibili.com/x/web-interface/dynamic/region?ps=6&rid=1'))
        videos = data.get('archives')
        if not isinstance(videos, list) or not videos:
            raise TaskError('分区视频列表为空或无效')
        self.videos = videos
        return 'success', f'获取 {len(videos)} 个分区视频'

    def video(self):
        if not self.videos:
            raise TaskError('缺少有效视频，未执行动作')
        aid = integer(self.videos[0].get('aid'), '视频 aid', 1, 10**15)
        cid = integer(self.videos[0].get('cid'), '视频 cid', 1, 10**15)
        return aid, cid

    def watch(self):
        aid, cid = self.video()
        self.http.call('https://api.bilibili.com/x/v2/history/report', 'POST',
                       {'aid': aid, 'cid': cid, 'progress': 300, 'csrf': self.csrf})
        return 'success', '观看进度 300 秒上报成功'

    def share(self):
        aid, _ = self.video()
        self.http.call('https://api.bilibili.com/x/web-interface/share/add', 'POST',
                       {'aid': aid, 'csrf': self.csrf})
        return 'success', '视频分享任务成功（不发布文本）'

    def exp_list(self):
        data = data_dict(self.http.call('https://api.bilibili.com/x/member/web/exp/log?jsonp=jsonp'))
        entries = data.get('list')
        if not isinstance(entries, list) or any(not isinstance(x, dict) for x in entries):
            raise TaskError('经验明细格式错误')
        today = time.strftime('%Y-%m-%d')
        return [x for x in entries if str(x.get('time', '')).split(' ')[0] == today]

    def coins(self):
        entries = self.exp_list()
        # 每 10 经验对应一枚币，避免一条记录含多枚币而重复花费。
        deltas = [x.get('delta') for x in entries if x.get('reason') == '视频投币奖励']
        if any(type(x) is not int or x <= 0 or x % 10 for x in deltas):
            raise TaskError('投币经验记录不明确，停止花费')
        already = sum(deltas) // 10
        remaining = max(0, self.coin_num - already)
        if not remaining:
            return 'alreadyComplete', f'今日投币目标已完成 {already}/{self.coin_num}'
        balance = self.nav.get('money')
        if not isinstance(balance, (int, float)) or balance < remaining:
            raise TaskError('硬币余额不足以完成目标，未投币')
        videos = list(self.videos)
        if self.coin_type == 1:
            uid = self.nav['mid']
            following = data_dict(self.http.call(f'https://api.bilibili.com/x/relation/followings?vmid={uid}&pn=1&ps=50&order=desc&order_type=attention'))
            people = following.get('list')
            if not isinstance(people, list):
                raise TaskError('关注列表无效')
            for person in people:
                mid = integer(person.get('mid'), '关注 UID', 1, 10**15)
                arcs = data_dict(self.http.call(f'https://api.bilibili.com/x/space/arc/search?mid={mid}&pn=1&ps=100&tid=0&order=pubdate&keyword='))
                vlist = arcs.get('list', {}).get('vlist')
                if not isinstance(vlist, list):
                    raise TaskError('关注投稿列表无效')
                videos.extend(vlist)
        seen = set()
        completed = 0
        for video in reversed(videos):
            aid = integer(video.get('aid'), '投币 aid', 1, 10**15)
            if aid in seen:
                continue
            seen.add(aid)
            result = self.http.call('https://api.bilibili.com/x/web-interface/coin/add', 'POST',
                                    {'aid': aid, 'multiply': 1, 'select_like': 1,
                                     'cross_domain': 'true', 'csrf': self.csrf}, accepted=(0, 34005))
            if result['code'] == 34005:
                log('⏭️ 此视频投币已达上限，尝试下一个')
                continue
            completed += 1
            log(f'✅ 投币并点赞：成功 {completed}/{remaining}')
            if completed == remaining:
                return 'success', f'今日投币目标完成 {already+completed}/{self.coin_num}'
        raise TaskError(f'投币目标未完成，新增 {completed}/{remaining}')

    def silver(self):
        self.http.call('https://api.live.bilibili.com/pay/v1/Exchange/silver2coin', 'POST',
                       {'csrf_token': self.csrf, 'csrf': self.csrf})
        return 'success', '银瓜子兑换硬币成功'

    def stats(self):
        self.nav_info()
        today = self.exp_list()
        deltas = [x.get('delta') for x in today]
        if any(type(x) is not int for x in deltas):
            raise TaskError('经验增量无效')
        exp = self.nav.get('level_info', {}).get('current_exp')
        if type(exp) is not int:
            raise TaskError('当前经验无效')
        live = data_dict(self.http.call('https://api.live.bilibili.com/pay/v1/Exchange/getStatus'))
        values = [live.get(k) for k in ('silver', 'gold', 'coin')]
        if any(not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', str(v)) for v in values):
            raise TaskError('直播余额字段无效')
        delta = sum(deltas)
        days = max(0, (28800-exp + delta-1)//delta) if delta > 0 else '无法预测'
        return 'success', (f'今日经验 {delta}；当前经验 {exp}；到六级预计 {days} 天；'
                           f'银瓜子 {values[0]}；金瓜子 {values[1]}；硬币 {values[2]}')

    def vip(self, kind):
        self.http.call('https://api.bilibili.com/x/vip/privilege/receive', 'POST',
                       {'type': kind, 'csrf': self.csrf})
        return 'success', f'大会员福利类型 {kind} 领取成功'

    def manga_reward(self):
        self.http.call('https://manga.bilibili.com/twirp/user.v1.User/GetVipReward', 'POST',
                       {'reason_id': 1}, json_body=True)
        return 'success', '漫画大会员福利领取成功'

    def charge(self):
        self.http.call('https://api.bilibili.com/x/ugcpay/trade/elec/pay/quick', 'POST',
                       {'bp_num': self.charge_num, 'is_bp_remains_prior': 'true',
                        'up_mid': self.charge_uid, 'otype': 'up', 'oid': self.charge_uid,
                        'csrf': self.csrf})
        return 'success', f'已向公开 UID {self.charge_uid} 充电 {self.charge_num} 贝壳'

    def configure(self):
        if not isinstance(self.config, dict):
            raise TaskError('账号配置必须是对象')
        cookies = parse_cookie(self.config.get('cookie'))
        self.csrf = cookies['bili_jct']
        self.http = HTTP(cookies, self.dry)
        self.coin_num = integer(self.config.get('coin_num', os.getenv('BILIBILI_COIN_NUM', '0')), 'coin_num', 0, 5)
        self.coin_type = integer(self.config.get('coin_type', os.getenv('BILIBILI_COIN_TYPE', '1')), 'coin_type', 0, 1)
        self.silver_on = self.config.get('silver2coin', flag('BILIBILI_SILVER2COIN'))
        if type(self.silver_on) is not bool:
            raise TaskError('silver2coin 必须为布尔值')
        self.watch_on = flag('BILIBILI_WATCH')
        self.share_on = flag('BILIBILI_SHARE')
        self.manga_on = flag('BILIBILI_MANGA', True)
        self.live_on = flag('BILIBILI_LIVE', True)
        self.reward_on = flag('BILIBILI_MANGA_VIP_REWARD')
        self.vip_types = []
        value = os.getenv('BILIBILI_VIP_TYPES', '').strip()
        if value:
            self.vip_types = list(dict.fromkeys(integer(v.strip(), 'BILIBILI_VIP_TYPES', 1, 5) for v in value.split(',')))
        self.charge_num = integer(os.getenv('BILIBILI_CHARGE_NUM', '0'), 'BILIBILI_CHARGE_NUM', 0, 9999)
        self.charge_uid = None
        if self.charge_num:
            if self.charge_num < 2:
                raise TaskError('充电金额至少为 2 贝壳')
            self.charge_uid = integer(os.getenv('BILIBILI_CHARGE_UID', ''), 'BILIBILI_CHARGE_UID', 1, 10**15)
        return 'success', '账号凭据与动作设置有效'

    def run(self):
        # 配置校验也在预演中实际执行。
        self.stage += 1
        log(f'账号 {self.index} 阶段 {self.stage}：配置校验')
        try:
            self.configure()
            self.counts['success'] += 1
            log('✅ 配置校验：必需字段齐全；耗时 %.2f 秒' % (time.monotonic()-self.start))
        except TaskError as error:
            self.counts['failure'] += 1
            log(f'❌ 配置校验：{error}')
            return self.finish()
        if not self.step('登录验证', self.nav_info) and not self.dry:
            log('⏭️ 登录失败，该账号停止；其他账号继续')
            return self.finish()
        self.step('漫画签到', lambda: self.sign(True), self.manga_on)
        self.step('直播签到', self.sign, self.live_on)
        self.step('获取分区视频', self.load_videos, self.watch_on or self.share_on or self.coin_num > 0)
        self.step('投币并点赞', self.coins, self.coin_num > 0)
        self.step('观看进度上报', self.watch, self.watch_on)
        self.step('视频分享', self.share, self.share_on)
        self.step('银瓜子兑换', self.silver, self.silver_on)
        for kind in self.vip_types:
            self.step(f'大会员福利 {kind}', lambda k=kind: self.vip(k))
        self.step('漫画大会员福利', self.manga_reward, self.reward_on)
        self.step('B 币充电', self.charge, bool(self.charge_num))
        self.step('经验、等级预测与余额', self.stats)
        return self.finish()

    def finish(self):
        counts = self.counts
        log(f'账号 {self.index} 统计：总任务 {sum(counts.values())}；成功 {counts["success"]}；'
            f'已完成 {counts["alreadyComplete"]}；跳过 {counts["skipped"]}；失败 {counts["failure"]}；'
            f'耗时 {time.monotonic()-self.start:.2f} 秒')
        return {'account': self.index, 'ok': counts['failure'] == 0, 'tasks': counts,
                'elapsedSeconds': round(time.monotonic()-self.start, 2)}


def notify(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in FALSE:
        log('通知：QINGLONG_NOTIFY 已关闭')
        return 'disabled'
    body = (f'状态：{summary["status"]}；账号总数 {summary["accountCount"]}；'
            f'成功 {summary["successCount"]}；失败 {summary["failureCount"]}')
    if dry:
        # dry-run 严格禁止任何网络，包括通知服务。
        log(f'通知预演：{body}（断网模式未发送）')
        return 'dry-run'
    paths = []
    directory = os.getenv('QINGLONG_NOTIFY_DIR')
    if directory:
        paths.append(Path(directory) / 'notify.py')
    paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, 'send', None)):
            log('⚠️ 通知不可用：未发现青龙 notify.py；业务退出码保持不变')
            return 'unavailable'
        # 通知库不获得 Cookie；抑制其不可控原始日志。
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            module.send(TITLE, body)
        log('通知：已调用青龙 notify.send')
        return 'sent'
    except Exception:
        log('⚠️ 通知失败；业务退出码保持不变')
        return 'failed'


def main():
    started = time.monotonic()
    start_time = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{start_time}')
    results = []
    error = False
    dry = False
    try:
        dry = flag('BILIBILI_DRY_RUN')
        log('运行模式：' + ('断网预演' if dry else '正式执行'))
        configs = account_inputs()
        log(f'账号总数：{len(configs)}')
        for index, config in enumerate(configs, 1):
            results.append(Account(index, config, dry).run())
    except TaskError as failure:
        error = True
        log(f'❌ 配置错误：{failure}')
        log('账号总数：0')
    good = sum(r['ok'] for r in results)
    bad = len(results)-good
    code = 1 if error or bad else 0
    status = 'configuration-error' if error else ('partial-failure' if bad and good else 'failure' if bad else 'dry-run' if dry else 'success')
    totals = {key: sum(r['tasks'][key] for r in results) for key in ('success', 'alreadyComplete', 'skipped', 'failure')}
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status,
               'accountCount': len(results), 'successCount': good, 'failureCount': bad,
               'configurationErrors': int(error), 'accounts': results, 'tasks': totals,
               'startTime': start_time, 'exitCode': code}
    summary['notification'] = notify(summary, dry)
    summary['finishTime'] = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    summary['elapsedSeconds'] = round(time.monotonic()-started, 2)
    log('----------------------------------------')
    log(f'任务统计：账号 {len(results)}；成功 {good}；失败 {bad}；配置错误 {int(error)}')
    log(f'子任务统计：{json.dumps(totals, ensure_ascii=False)}')
    log(f'耗时：{summary["elapsedSeconds"]} 秒；通知状态：{summary["notification"]}')
    log(f'完成时间：{summary["finishTime"]}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
