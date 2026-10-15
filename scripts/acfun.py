#!/usr/bin/env python3
# name: AcFun每日任务
# cron: 9 0 * * *
# filename: acfun.py
# 发布文件名：acfun.py；不得部署为 scripts/main.py。
# 上游: Sitoi/dailycheckin dailycheckin/acfun/main.py
# 来源提交: 135cc236e59ac4f14bcddc44acb3cbb3ed6010b5
# License: MIT; 原来源文件没有附加版权声明。
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
"""ACFUN_ACCOUNTS: 每行 手机号|密码，仅在首个 | 分割。支持密码包含 |。
手机号和密码来自本人 AcFun 注册账号，请先在官方客户端确认可正常登录。
在青龙环境变量中填写 ACFUN_ACCOUNTS，多账号用换行，不使用 & 或 @。
发布时将本候选命名为 acfun.py，以避免其他产品的 main.py 路径冲突。
默认签到和信息查询。ACFUN_TASKS 可选 sign,info,like,like-cycle,danmu,banana,share。
like-cycle 表示点赞后取消；banana 消耗一根香蕉；danmu 公开发布文本。
ACFUN_DRY_RUN=1 完全断网预演；通知测试请设置 QINGLONG_NOTIFY=0。
接口来自提供的源文件，未进行在线验证；接口变化会失败闭合。
"""
import datetime
import http.cookiejar
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request

TITLE = 'AcFun每日任务'
DISABLED = {'0', 'false', 'no', 'off'}
ACTIONS = {'sign', 'info', 'like', 'like-cycle', 'danmu', 'banana', 'share'}
LABELS = {'sign': '签到', 'info': '等级和香蕉余额查询', 'like': '点赞',
          'like-cycle': '点赞后取消', 'danmu': '发布弹幕', 'banana': '投一根香蕉', 'share': '分享任务上报'}
WEB = 'https://www.acfun.cn'
ID = 'https://id.app.acfun.cn'

class TaskError(Exception):
    pass

def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)

def enabled(name):
    return os.getenv(name, '0').strip().lower() not in DISABLED | {''}

def successful(data, code=0):
    if not isinstance(data, dict) or type(data.get('result')) is not int or data['result'] != code:
        raise TaskError('接口未确认业务成功（响应或业务码不符合源接口契约）')
    return data

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口跳转已拒绝，避免跨域传递凭据')

class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': WEB + '/'}

    def request(self, url, data=None, method='GET', headers=None, raw=False):
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        h = dict(self.headers)
        if body is not None:
            h['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        h.update(headers or {})
        try:
            req = urllib.request.Request(url, data=body, headers=h, method=method)
            with self.opener.open(req, timeout=15) as response:
                if response.geturl().split('/', 3)[:3] != url.split('/', 3)[:3]:
                    raise TaskError('接口发生跨域跳转')
                content = response.read(2 * 1024 * 1024 + 1)
                if len(content) > 2 * 1024 * 1024:
                    raise TaskError('接口响应过大')
            decoded = content.decode('utf-8')
            return decoded if raw else json.loads(decoded)
        except TaskError:
            raise
        except Exception:
            raise TaskError('网络、HTTP 或响应解析失败；未输出原始错误与响应') from None

    def login(self, phone, password):
        return successful(self.request(ID + '/rest/web/login/signin',
                         {'username': phone, 'password': password, 'key': '', 'captcha': ''}, 'POST'))

    def video(self):
        data = successful(self.request(WEB + '/rest/pc-direct/rank/channel'))
        ranks = data.get('rankList')
        if not isinstance(ranks, list) or not ranks or not isinstance(ranks[0], dict):
            raise TaskError('排行榜没有可用视频')
        value = str(ranks[0].get('contentId', ''))
        if not value.isdigit():
            raise TaskError('视频标识不符合契约')
        return value

    def action(self, action, phone, password, content):
        if action == 'sign':
            successful(self.request(WEB + '/rest/pc-direct/user/signIn', method='POST'))
        elif action == 'info':
            info = successful(self.request(WEB + '/rest/pc-direct/user/personalInfo')).get('info')
            if not isinstance(info, dict):
                raise TaskError('账户信息缺失')
            for key, label in [('level', '等级'), ('banana', '香蕉余额')]:
                value = info.get(key)
                if type(value) not in (int, float) or value < 0:
                    raise TaskError('账户统计字段缺失或无效')
                log(f'{label}：{value}')
            show_identity(info, phone, password)
        elif action in ('like', 'like-cycle'):
            token = successful(self.request(ID + '/rest/web/token/get?sid=acfun.midground.api', method='POST')).get('acfun.midground.api_st')
            if not isinstance(token, str) or not token:
                raise TaskError('点赞令牌缺失')
            body = {'kpn': 'ACFUN_APP', 'kpf': 'PC_WEB', 'subBiz': 'mainApp', 'interactType': '1',
                    'objectType': '2', 'objectId': content, 'acfun.midground.api_st': token,
                    'extParams[isPlaying]': 'false', 'extParams[showCount]': '1',
                    'extParams[otherBtnClickedCount]': '10', 'extParams[playBtnClickedCount]': '0'}
            successful(self.request('https://kuaishouzt.com/rest/zt/interact/add', body, 'POST'), 1)
            log('点赞接口确认成功')
            if action == 'like-cycle':
                successful(self.request('https://kuaishouzt.com/rest/zt/interact/delete', body, 'POST'), 1)
                log('取消点赞接口确认成功')
        elif action == 'banana':
            successful(self.request(WEB + '/rest/pc-direct/banana/throwBanana',
                                    {'resourceId': content, 'count': '1', 'resourceType': '2'}, 'POST'))
        elif action == 'danmu':
            page = self.request(WEB + '/v/ac' + content, raw=True)
            video = re.search(r'"currentVideoId"\s*:\s*(\d+)', page)
            channel = re.search(r'\{subChannelId:(\d+),subChannelName:"([^"\r\n]+)"\}', page)
            if not video or not channel:
                raise TaskError('视频或分区字段缺失，禁止使用硬编码目标发弹幕')
            text = public_text()
            successful(self.request(WEB + '/rest/pc-direct/new-danmaku/add',
                {'mode': '1', 'color': '16777215', 'size': '25', 'body': text,
                 'videoId': video[1], 'position': '2719', 'type': 'douga', 'id': content,
                 'subChannelId': channel[1], 'subChannelName': channel[2]}, 'POST'))
        elif action == 'share':
            app = successful(self.request(ID + '/rest/app/login/signin',
                {'password': password, 'username': phone}, 'POST',
                {'User-Agent': 'AcFun/6.39.0 (iPhone; iOS 14.3; Scale/2.00)', 'devicetype': '0'}))
            token, key = app.get('acPassToken'), app.get('auth_key')
            if not isinstance(token, str) or not token or key is None or str(key) in ('', 'None'):
                raise TaskError('App 登录配套凭据缺失')
            cookie = 'acPasstoken=' + token + '; auth_key=' + str(key)
            successful(self.request('https://api-ipv6.acfunchina.com/rest/app/task/reportTaskAction?taskType=1&market=tencent&product=ACFUN_APP&appMode=0',
                                    headers={'Cookie': cookie}))

def show_identity(data, phone, password):
    # 只读取官方非秘密身份字段；遇到手机号或账户凭据时抑制。
    for key in ('nickname', 'userName', 'username', 'displayName', 'userId', 'uid'):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value)
            if text and phone not in text and password not in text and not re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text):
                log(f'账号身份（{key}）：{json.dumps(text, ensure_ascii=False)}')
                return

def normalize(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''

def public_text():
    fallback = normalize(os.getenv('ACFUN_LOCAL_TEXT', '今天也要保持好心情。'))
    if not fallback or len(fallback) > 280:
        raise TaskError('本地备用文案必须为 1 至 280 字符')
    try:
        # 使用独立、无 Cookie、无认证头的请求，绝不复用账户客户端。
        req = urllib.request.Request('https://v1.hitokoto.cn/?encode=json', headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as response:
            content = response.read(16385)
        if len(content) > 16384:
            raise ValueError()
        data = json.loads(content)
        text, author, source = (normalize(data.get(k)) for k in ('hitokoto', 'from_who', 'from'))
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
        log('文案：一言内容与署名已校验（不输出正文）')
        return text
    except Exception:
        log('⚠️ 文案提供方不可用或内容无效，使用本地备用文案')
        return fallback

def notify(body):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    try:
        try:
            sender = importlib.import_module('notify').send
        except (ImportError, AttributeError):
            paths = []
            if os.getenv('QINGLONG_NOTIFY_DIR'):
                paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                raise RuntimeError()
            spec = importlib.util.spec_from_file_location('qinglong_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = module.send
        sender(TITLE, body)
        return '已发送'
    except Exception:
        log('⚠️ 通知不可用或发送失败，保留业务退出码')
        return '不可用或失败'

def main():
    started = time.monotonic()
    dry = enabled('ACFUN_DRY_RUN')
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}；模式：' + ('断网预演' if dry else '正式运行'))
    lines = [s for s in os.getenv('ACFUN_ACCOUNTS', '').splitlines() if s.strip()]
    log(f'账号总数：{len(lines)}')
    tasks = [s.strip() for s in os.getenv('ACFUN_TASKS', 'sign,info').split(',') if s.strip()]
    results = []
    total = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    configuration_error = not lines or not tasks or bool(set(tasks) - ACTIONS) or len(tasks) != len(set(tasks)) or {'like', 'like-cycle'} <= set(tasks)
    if 'danmu' in tasks and not 1 <= len(normalize(os.getenv('ACFUN_LOCAL_TEXT', '今天也要保持好心情。'))) <= 280:
        configuration_error = True
    if configuration_error:
        log('❌ 配置错误：检查账号、任务列表、重复动作或备用文案；不输出配置值')
    else:
        for index, line in enumerate(lines, 1):
            t0 = time.monotonic()
            stats = {'total': len(tasks) + 1, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
            log(f'账号 {index} 开始')
            fields = line.split('|', 1)
            auth_ok = False
            client = None
            phone = password = ''
            stage_start = time.monotonic()
            try:
                if len(fields) != 2 or not fields[0].strip() or not fields[1]:
                    raise TaskError('账号配置需为 手机号|密码')
                phone, password = fields[0].strip(), fields[1]
                log(f'账号 {index} 阶段 1/{len(tasks)+1}：登录与参数校验')
                if not dry:
                    client = Client()
                    login = client.login(phone, password)
                    show_identity(login, phone, password)
                auth_ok = True
                stats['success'] += 1
                log(f'✅ 登录阶段' + ('断网校验通过（未验证真实登录）' if dry else '业务成功') + f'；耗时 {time.monotonic()-stage_start:.2f} 秒')
            except TaskError as exc:
                stats['failed'] += 1
                log(f'❌ 登录阶段：{exc}；耗时 {time.monotonic()-stage_start:.2f} 秒')
            content = None
            for stage, action in enumerate(tasks, 2):
                st = time.monotonic()
                log(f'账号 {index} 阶段 {stage}/{len(tasks)+1}：{LABELS[action]}')
                if not auth_ok:
                    stats['skipped'] += 1
                    log('⏭️ 登录或配置失败，跳过；耗时 0.00 秒')
                    continue
                try:
                    if dry:
                        log('断网预演：参数和执行计划通过；未发送请求、未执行副作用')
                    else:
                        if action in ('like', 'like-cycle', 'danmu', 'banana') and content is None:
                            content = client.video()
                            log('排行榜视频选择成功')
                        client.action(action, phone, password, content)
                    stats['success'] += 1
                    log(f'✅ {LABELS[action]}：' + ('预演通过' if dry else '业务成功') + f'；耗时 {time.monotonic()-st:.2f} 秒')
                except TaskError as exc:
                    stats['failed'] += 1
                    log(f'❌ {LABELS[action]}：{exc}；耗时 {time.monotonic()-st:.2f} 秒')
                except Exception:
                    stats['failed'] += 1
                    log(f'❌ {LABELS[action]}：响应字段或运行异常（已脱敏）；耗时 {time.monotonic()-st:.2f} 秒')
            for key in total:
                total[key] += stats[key]
            ok = stats['failed'] == 0 and stats['skipped'] == 0
            results.append(ok)
            log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}；耗时 {time.monotonic()-t0:.2f} 秒')
    successes = sum(results)
    failures = len(lines) - successes
    code = 1 if configuration_error or failures else 0
    status = 'configuration-error' if configuration_error else ('partial-failure' if failures and successes else 'failure' if failures else 'dry-run' if dry else 'success')
    body = f'模式：{"断网预演" if dry else "正式运行"}；账号总数 {len(lines)}，成功 {successes}，失败 {failures}；状态 {status}；子任务成功 {total["success"]}，失败 {total["failed"]}，跳过 {total["skipped"]}。' + ('预演未验证真实业务。' if dry else '')
    if dry:
        # 通知也不能破坏断网保证；仍尝试调用通知入口，网络传输失败不改变退出码。
        # 审计钩子覆盖通知模块重新导入 socket、UDP、DNS 和子进程等绕过方式。
        # 钩子持续到本进程退出；不影响青龙中的其他任务进程。
        def deny_external_io(event, args):
            if event.startswith('socket.') or event in (
                'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn',
                'os.fork', 'os.forkpty', 'pty.spawn', 'ctypes.dlopen',
            ):
                raise RuntimeError('断网预演禁止网络及外部通知进程')
        sys.addaudithook(deny_external_io)
        notification = notify(body)
    else:
        notification = notify(body)
    log('----------------------------------------')
    log(body)
    log(f'子任务统计：{json.dumps(total, ensure_ascii=False)}')
    log(f'总耗时：{time.monotonic()-started:.2f} 秒；完成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'通知状态：{notification}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'accounts': len(lines),
          'success': successes, 'failed': failures, 'steps': total, 'status': status, 'notification': notification, 'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code

if __name__ == '__main__':
    sys.exit(main())
