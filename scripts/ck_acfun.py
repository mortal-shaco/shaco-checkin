# -*- coding: utf-8 -*-
# name: AcFun每日签到与可选互动
# cron: 31 7 * * *
# 原始来源：OreosLab/checkinpanel，ck_acfun.py，MIT 许可。
# 原始任务标识：new Env('AcFun每日签到与可选互动');
"""独立的 AcFun 维护脚本（Python 3，仅标准库）。

青龙变量 ACFUN_ACCOUNTS：每个非空行 手机号|密码，只在第一个 | 分割。
参数获取：使用 AcFun 官方网站或客户端中自己的登录手机号及密码，
在青龙环境变量中填写，勿将凭据放入脚本或日志。验证码登录失败时需人工处理。
兼容 ACFUN：同样的逐行格式，或旧 ACFUN 数组的 JSON（phone/password）。
ACFUN_ACTIONS 默认 sign,info；可选 like,danmu,banana，逗号分隔。
like 保留上游点赞再取消流程；banana 每次投一根香蕉；danmu 发布公开弹幕。
ACFUN_DANMU_FALLBACK 可设置本地备用文本；一言获取失败时使用。
ACFUN_DRY_RUN=1 完全断网预演，包括通知；QINGLONG_NOTIFY=0 关闭通知。

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
import contextlib
import http.cookiejar
import importlib
import importlib.util
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

TITLE = 'AcFun每日任务'
WEB = 'https://www.acfun.cn'
ID = 'https://id.app.acfun.cn'
INTERACT = 'https://kuaishouzt.com'
TEXT_URL = 'https://v1.hitokoto.cn/?encode=json'
NAMES = {'login': '登录', 'video': '选择排行榜视频', 'token': '获取互动令牌',
         'sign': '签到', 'like': '点赞并取消', 'danmu': '发送弹幕',
         'banana': '投一根香蕉', 'info': '查询账号信息'}
OFF = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    """错误内容只使用本地固定说明，不传递服务器响应或底层异常。"""


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() not in OFF | {''}


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向，已停止以保护凭据')


class Http:
    def __init__(self, dry):
        self.dry = dry
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, url, data=None, html=False):
        if self.dry:
            raise TaskError('预演模式禁止网络请求')
        if urllib.parse.urlsplit(url).netloc not in {'www.acfun.cn', 'id.app.acfun.cn', 'kuaishouzt.com'}:
            raise TaskError('业务接口域名不在白名单')
        body = None if data is None else urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={
            'User-Agent': 'Mozilla/5.0', 'Referer': WEB + '/',
            'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
        try:
            with self.opener.open(req, timeout=15) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise TaskError('业务响应超出大小限制')
            text = raw.decode('utf-8')
            if html:
                return text
            value = json.loads(text)
            if not isinstance(value, dict):
                raise TaskError('业务响应结构异常')
            return value
        except TaskError:
            raise
        except Exception:
            raise TaskError('请求失败、超时或响应格式异常') from None


def verified(value, code=0):
    result = value.get('result')
    # 不把缺失状态、布尔值或消息文本当成成功。
    if isinstance(result, bool) or result not in (code, str(code)):
        raise TaskError('业务状态未确认成功')
    return value


def normalize(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def public_text(dry=False):
    if dry:
        raise TaskError('预演模式禁止文本服务请求')
    fallback = normalize(os.getenv('ACFUN_DANMU_FALLBACK', '欣赏作品，感谢分享。'))
    if not fallback or len(fallback) > 280:
        raise TaskError('本地弹幕必须为 1 至 280 个字符')
    try:
        # 单独的 opener，无账号 Cookie、令牌、密码或业务请求头。
        opener = urllib.request.build_opener(NoRedirect())
        req = urllib.request.Request(TEXT_URL, headers={'Accept': 'application/json'})
        with opener.open(req, timeout=8) as response:
            if response.status != 200:
                raise ValueError()
            raw = response.read(16385)
        if len(raw) > 16384:
            raise ValueError()
        value = json.loads(raw.decode('utf-8'))
        text = normalize(value.get('hitokoto'))
        author, source = normalize(value.get('from_who')), normalize(value.get('from'))
        if not text:
            raise ValueError()
        if author and source:
            text += f' —— {author}《{source}》'
        elif source:
            text += f' ——《{source}》'
        elif author:
            text += f' —— {author}'
        if len(text) > 280:
            raise ValueError()
        log('弹幕文本：一言获取成功，已按署名格式处理（不输出正文）')
        return text
    except Exception:
        log('⚠️ 弹幕文本服务失败，使用本地备用文本')
        return fallback


def accounts_from_env():
    raw = os.getenv('ACFUN_ACCOUNTS', '')
    legacy = False
    if not raw.strip():
        raw = os.getenv('ACFUN', '')
        legacy = True
    if not raw.strip():
        return []
    if legacy and raw.lstrip().startswith('['):
        try:
            items = json.loads(raw)
        except Exception:
            raise TaskError('兼容变量 ACFUN 的 JSON 格式错误') from None
        if not isinstance(items, list):
            raise TaskError('兼容变量必须是账号数组')
        accounts = []
        for item in items:
            if not isinstance(item, dict):
                accounts.append(('', ''))
            else:
                phone, password = item.get('phone'), item.get('password')
                accounts.append((phone if isinstance(phone, str) else '',
                                 password if isinstance(password, str) else ''))
        return accounts
    accounts = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        phone, delimiter, password = line.partition('|')
        accounts.append((phone.strip(), password if delimiter else ''))
    return accounts


def identity(info, secrets):
    found = []
    for key in ('nickname', 'userName', 'username', 'name', 'displayName', 'userId', 'uid'):
        value = info.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value)
            # 非秘密身份原样显示；拒绝手机号及任何本账号秘密字段。
            if value and not re.search(r'(?<!\d)1\d{10}(?!\d)', value) and not any(s and s in value for s in secrets):
                found.append(f'{key}: {value}')
    return '；'.join(found)


class Account:
    def __init__(self, number, credentials, dry):
        self.number, self.credentials, self.dry = number, credentials, dry
        self.http = Http(dry)
        self.content_id = None
        self.token = None
        self.results = []
        self.start = time.monotonic()

    def stage(self, key, operation, skip=False):
        start = time.monotonic()
        log(f'账号 {self.number} 阶段 {len(self.results)+1}：{NAMES[key]}')
        status, detail = 'success', '已验证业务成功'
        try:
            if skip:
                status, detail = 'skipped', '前置步骤失败，未执行'
            elif self.dry:
                status, detail = 'skipped', '断网预演：仅展示任务计划，未调用接口'
            else:
                detail = operation() or detail
        except TaskError as error:
            status, detail = 'failed', str(error)
        except Exception:
            status, detail = 'failed', '处理异常，已隐藏原始错误内容'
        self.results.append({'stage': key, 'status': status})
        icon = {'success': '✅', 'skipped': '⏭️', 'failed': '❌'}[status]
        log(f'账号 {self.number} {icon} {NAMES[key]}：{detail}；耗时 {time.monotonic()-start:.2f} 秒')
        return status != 'failed' and (not skip)

    def login(self):
        phone, password = self.credentials
        value = verified(self.http.request(ID + '/rest/web/login/signin', {
            'username': phone, 'password': password, 'key': '', 'captcha': ''}))
        who = identity(value, self.credentials)
        return '登录成功' + ('；' + who if who else '')

    def video(self):
        value = self.http.request(WEB + '/rest/pc-direct/rank/channel')
        if 'result' in value:
            verified(value)
        entries = value.get('rankList')
        if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
            raise TaskError('排行榜未返回有效视频')
        content = str(entries[0].get('contentId', ''))
        if not content.isdigit():
            raise TaskError('视频标识无效')
        self.content_id = content
        return '已获取排行榜视频'

    def get_token(self):
        value = verified(self.http.request(ID + '/rest/web/token/get?sid=acfun.midground.api', {}))
        self.token = value.get('acfun.midground.api_st')
        if not isinstance(self.token, str) or not self.token:
            raise TaskError('接口未返回互动令牌')
        return '互动令牌获取成功（不输出令牌）'

    def sign(self):
        verified(self.http.request(WEB + '/rest/pc-direct/user/signIn', {}))
        return '签到成功'

    def like(self):
        data = {'kpn': 'ACFUN_APP', 'kpf': 'PC_WEB', 'subBiz': 'mainApp',
                'interactType': '1', 'objectType': '2', 'objectId': self.content_id,
                'acfun.midground.api_st': self.token, 'extParams[isPlaying]': 'false',
                'extParams[showCount]': '1', 'extParams[otherBtnClickedCount]': '10',
                'extParams[playBtnClickedCount]': '0'}
        verified(self.http.request(INTERACT + '/rest/zt/interact/add', data), 1)
        log(f'账号 {self.number} 点赞接口已确认成功，继续取消点赞')
        try:
            verified(self.http.request(INTERACT + '/rest/zt/interact/delete', data), 1)
        except TaskError:
            raise TaskError('点赞成功但取消未确认成功，可能仍处于点赞状态') from None
        return '点赞成功；取消点赞成功'

    def danmu(self):
        html = self.http.request(WEB + '/v/ac' + self.content_id, html=True)
        video = re.search(r'"currentVideoId"\s*:\s*(\d+)', html)
        channel = re.search(r'subChannelId\s*:\s*(\d+)\s*,\s*subChannelName\s*:\s*"([^"\r\n]+)"', html)
        if not video or not channel:
            raise TaskError('页面缺少视频或分区字段，停止发布弹幕')
        data = {'mode': '1', 'color': '16777215', 'size': '25',
                'body': public_text(self.dry), 'videoId': video.group(1), 'position': '2719',
                'type': 'douga', 'id': self.content_id, 'subChannelId': channel.group(1),
                'subChannelName': channel.group(2)}
        verified(self.http.request(WEB + '/rest/pc-direct/new-danmaku/add', data))
        return '弹幕成功'

    def banana(self):
        verified(self.http.request(WEB + '/rest/pc-direct/banana/throwBanana', {
            'resourceId': self.content_id, 'count': '1', 'resourceType': '2'}))
        return '投香蕉成功（数量 1）'

    def info(self):
        value = verified(self.http.request(WEB + '/rest/pc-direct/user/personalInfo'))
        info = value.get('info')
        if not isinstance(info, dict):
            raise TaskError('账号信息字段缺失')
        details = []
        who = identity(info, self.credentials + (self.token or '',))
        if who:
            details.append(who)
        for key, label in (('level', '当前等级'), ('banana', '持有香蕉')):
            val = info.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool) or isinstance(val, str) and re.fullmatch(r'\d+(?:\.\d+)?', val):
                details.append(f'{label}: {val}')
            else:
                raise TaskError('等级或香蕉余额字段缺失或格式异常')
        return '；'.join(details)

    def run(self, actions):
        phone, password = self.credentials
        if not phone or not password:
            log(f'账号 {self.number} 阶段 1：登录')
            log(f'账号 {self.number} ❌ 登录：账号缺少手机号或密码；耗时 0.00 秒')
            self.results.append({'stage': 'login', 'status': 'failed'})
        else:
            ok = self.stage('login', self.login)
            video_ok = True
            token_ok = True
            if {'like', 'danmu', 'banana'} & set(actions):
                video_ok = self.stage('video', self.video, skip=not ok)
            if 'like' in actions:
                token_ok = self.stage('token', self.get_token, skip=not ok or not video_ok)
            for key in actions:
                prerequisite = ok and (key not in {'like', 'danmu', 'banana'} or video_ok)
                if key == 'like':
                    prerequisite = prerequisite and token_ok
                self.stage(key, getattr(self, key), skip=not prerequisite)
        counts = {state: sum(r['status'] == state for r in self.results)
                  for state in ('success', 'skipped', 'failed')}
        failed = counts['failed'] > 0
        log(f'账号 {self.number} 统计：总任务 {len(self.results)}，成功 {counts["success"]}，'
            f'已完成 0，跳过 {counts["skipped"]}，失败 {counts["failed"]}，耗时 {time.monotonic()-self.start:.2f} 秒')
        return {'account': self.number, 'status': 'failed' if failed else ('dry-run' if self.dry else 'success'),
                'tasks': counts, 'results': self.results}


def notify_summary(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    if dry:
        # notify 插件可能联网；断网预演不能导入或执行任何通知插件。
        return '断网预演：通知已模拟，未调用通知插件'
    paths = []
    directory = os.getenv('QINGLONG_NOTIFY_DIR')
    if directory:
        paths.append(Path(directory) / 'notify.py')
    paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                module = importlib.import_module('notify')
            except ImportError:
                module = None
            if module is None or not callable(getattr(module, 'send', None)):
                for path in paths:
                    if path.is_file():
                        spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        if callable(getattr(module, 'send', None)):
                            break
            if module is None or not callable(getattr(module, 'send', None)):
                return '通知模块不可用，保留业务退出码'
            module.send(TITLE, body)
        return '已发送'
    except Exception:
        return '通知失败，保留业务退出码'


def main():
    start = time.monotonic()
    dry = enabled('ACFUN_DRY_RUN')
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('运行模式：' + ('断网预演' if dry else '正式执行'))
    accounts, results, config_error = [], [], False
    try:
        accounts = accounts_from_env()
        if not accounts:
            raise TaskError('请配置 ACFUN_ACCOUNTS，每个非空行 手机号|密码')
        actions = [v.strip() for v in os.getenv('ACFUN_ACTIONS', 'sign,info').split(',') if v.strip()]
        if not actions or len(actions) != len(set(actions)) or any(v not in {'sign', 'info', 'like', 'danmu', 'banana'} for v in actions):
            raise TaskError('ACFUN_ACTIONS 必须为不重复的 sign,info,like,danmu,banana 子集')
        if 'danmu' in actions:
            fallback = normalize(os.getenv('ACFUN_DANMU_FALLBACK', '欣赏作品，感谢分享。'))
            if not fallback or len(fallback) > 280:
                raise TaskError('本地弹幕必须为 1 至 280 个字符')
        log(f'账号数量：{len(accounts)}')
        for number, credentials in enumerate(accounts, 1):
            results.append(Account(number, credentials, dry).run(actions))
    except TaskError as error:
        config_error = True
        log('❌ 配置错误：' + str(error))
        log(f'账号数量：{len(accounts)}')
    except Exception:
        config_error = True
        log('❌ 任务异常，已隐藏错误内容')
    failed = sum(r['status'] == 'failed' for r in results)
    passed = len(results) - failed
    code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else
              'partial-failure' if failed and passed else 'failure' if failed else
              'dry-run' if dry else 'success')
    body = f'状态：{status}；账号总数 {len(accounts)}，成功 {passed}，失败 {failed}；预演 {dry}'
    notification = notify_summary(body, dry)
    totals = {state: sum(r['tasks'][state] for r in results) for state in ('success', 'skipped', 'failed')}
    finished = time.strftime('%Y-%m-%d %H:%M:%S')
    log('----------------------------------------')
    log(body)
    log(f'子任务统计：成功 {totals["success"]}，已完成 0，跳过 {totals["skipped"]}，失败 {totals["failed"]}')
    log(f'总耗时：{time.monotonic()-start:.2f} 秒；完成时间：{finished}')
    log('通知状态：' + notification)
    log('最终状态：' + status)
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'dryRun': dry,
          'accounts': len(accounts), 'successfulAccounts': passed, 'failedAccounts': failed,
          'configurationError': config_error, 'tasks': totals, 'results': results,
          'notification': notification, 'finishedAt': finished, 'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
