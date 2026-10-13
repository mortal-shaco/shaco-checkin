#!/usr/bin/env python3
# name: LINUX DO 登录与浏览统计
# cron: 5 */5 * * *
# 来源: lzylipu/l-checkin main.py, commit 2c71083614d6ef87c8b502e1440fec3b08ab59c3
# 原始通知参考: lzylipu/l-checkin notify.py。原源码未附版权声明。
# SPDX-License-Identifier: MIT
"""LINUX DO 维护版（Python 标准库，无浏览器或私有仓库依赖）。
LINUXDO_COOKIES: 浏览器登录 https://linux.do 后，从开发者工具网络面板
复制本站请求的完整 Cookie 请求头；每个非空行一个账号，不用 & 或 @ 分隔。
BROWSE_ENABLED=true、TOPIC_LIMIT=50、BROWSE_COUNT=20 保持上游参数默认值。
仅读取登录状态、话题和统计；不随机点赞，不伪造阅读时长，不承诺签到积分。
LINUXDO_DRY_RUN=1 完全断网，使用本地样例验证流程，不验证真实凭据。
QINGLONG_NOTIFY=0 关闭通知；可用 QINGLONG_NOTIFY_DIR 指定青龙通知模块目录。

MIT License (upstream: lzylipu/l-checkin)
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
import datetime as dt
import json
import os
from pathlib import Path
import random
import re
import sys
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

TITLE = 'LINUX DO 登录与浏览统计'
HOME = 'https://linux.do'
DISABLED = {'0', 'false', 'no', 'off'}
METRICS = {'days_visited': '访问天数', 'topics_entered': '浏览话题',
           'posts_read_count': '已读帖子', 'time_read': '阅读时长（秒）',
           'likes_given': '给出点赞', 'likes_received': '收到点赞', 'post_count': '发帖数'}
REQUIREMENTS = {0: {'topics_entered': 5, 'posts_read_count': 30, 'time_read': 600},
                1: {'days_visited': 15, 'likes_given': 1, 'likes_received': 1,
                    'post_count': 3, 'topics_entered': 20, 'posts_read_count': 100, 'time_read': 3600}}

class TaskError(Exception):
    pass

def log(message):
    print(f'[{dt.datetime.now():%H:%M:%S}] {message}', flush=True)

def boolean(name, default):
    value = os.getenv(name, default).strip().lower()
    if value not in DISABLED | {'1', 'true', 'yes', 'on'}:
        raise TaskError(f'{name} 必须为布尔值')
    return value not in DISABLED

def integer(name, default, low, high):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise TaskError(f'{name} 必须为整数') from None
    if not low <= value <= high:
        raise TaskError(f'{name} 必须在 {low} 至 {high} 之间')
    return value

def validate_cookie(cookie):
    for part in cookie.split(';'):
        if not part.strip():
            continue
        name, sep, value = part.strip().partition('=')
        if not sep or not re.fullmatch(r'[!#$%&\'*+.^_`|~0-9A-Za-z-]+', name) or not value:
            raise TaskError('Cookie 格式无效，请复制完整请求头')
    if not cookie or any(ord(c) < 32 or ord(c) > 126 for c in cookie):
        raise TaskError('Cookie 包含无效字符')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class Client:
    def __init__(self, cookie):
        self.cookie = cookie
        self.opener = urllib.request.build_opener(NoRedirect())

    def get(self, path, as_json=True):
        if not path.startswith('/') or path.startswith('//'):
            raise TaskError('拒绝非本站地址')
        request = urllib.request.Request(HOME + path, headers={
            'Cookie': self.cookie, 'User-Agent': 'Mozilla/5.0 Qinglong-LinuxDo/1.0',
            'Accept': 'application/json' if as_json else 'text/html',
            'Accept-Language': 'zh-CN,zh;q=0.9'})
        try:
            with self.opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise TaskError('接口 HTTP 状态异常')
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise TaskError('接口响应超出大小限制')
                text = raw.decode('utf-8')
        except urllib.error.HTTPError as exc:
            raise TaskError(f'接口 HTTP {exc.code}，请检查 Cookie 或站点访问限制') from None
        except (urllib.error.URLError, TimeoutError, OSError, UnicodeError):
            raise TaskError('接口网络、超时或编码错误') from None
        if not as_json:
            return text
        try:
            data = json.loads(text)
        except ValueError:
            raise TaskError('接口未返回有效 JSON，可能遇到登录或访问验证页面') from None
        if not isinstance(data, dict) or data.get('errors') or data.get('error') or data.get('success') is False:
            raise TaskError('接口业务失败或响应结构异常')
        return data

class TopicParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}
        self.has_heading = False
        self.has_post = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h1':
            self.has_heading = True
        if re.fullmatch(r'post_\d+', attrs.get('id', '')):
            self.has_post = True
        if tag == 'a':
            href = attrs.get('href', '')
            parsed = urllib.parse.urlsplit(href)
            if parsed.netloc and (parsed.scheme != 'https' or parsed.netloc != 'linux.do'):
                return
            match = re.fullmatch(r'/t/(?:[^/]+/)?(\d+)(?:/\d+)?/?', parsed.path)
            if match:
                self.links.setdefault(match.group(1), parsed.path)

def stage(stats, number, name, operation):
    started = time.monotonic()
    log(f'阶段 {number}：{name}')
    try:
        operation()
        stats['success'] += 1
        log(f'✅ 阶段 {number} 完成，耗时 {time.monotonic() - started:.2f} 秒')
    except TaskError as exc:
        stats['failed'] += 1
        log(f'❌ 阶段 {number}：{exc}，耗时 {time.monotonic() - started:.2f} 秒')
        raise

def account(cookie, dry, browse, limit, count, stats):
    client = None if dry else Client(cookie)
    user = {}
    def login():
        nonlocal user
        data = {'current_user': {'username': '断网预演账号', 'trust_level': 0}} if dry else client.get('/session/current.json')
        user = data.get('current_user')
        if not isinstance(user, dict) or not isinstance(user.get('username'), str) or not user['username'].strip():
            raise TaskError('未取得已登录账号身份，Cookie 可能过期')
        level = user.get('trust_level')
        if type(level) is not int or not 0 <= level <= 4:
            raise TaskError('信任等级字段无效')
        # 官方公开用户名按原值输出；不输出其他可能含敏感字段的数据。
        log(f'账号身份：{user["username"]}；信任等级 TL{level}')
    stage(stats, 1, '登录身份校验' if not dry else '本地登录结构预演', login)
    def browsing():
        if dry:
            log(f'本地预演：发现上限 {limit}，浏览目标 {count}；不请求站点')
            return
        parser = TopicParser()
        parser.feed(client.get('/', False))
        links = list(parser.links.values())[:limit]
        if not links:
            raise TaskError('首页未发现话题；不把访问验证页面视为浏览成功')
        selected = random.sample(links, min(count, len(links)))
        log(f'发现 {len(links)} 个话题，读取 {len(selected)} 个')
        failures = 0
        for index, path in enumerate(selected, 1):
            try:
                page = TopicParser()
                page.feed(client.get(path, False))
                if not (page.has_heading and page.has_post):
                    raise TaskError('话题正文校验失败')
                log(f'✅ 话题 {index}/{len(selected)}：正文读取成功')
            except TaskError as exc:
                failures += 1
                log(f'❌ 话题 {index}/{len(selected)}：{exc}')
        if failures:
            raise TaskError(f'{failures} 个话题读取失败')
    browsing_failed = False
    if browse and count:
        try:
            stage(stats, 2, '话题浏览（不点赞、不上报模拟时长）', browsing)
        except TaskError:
            browsing_failed = True
    else:
        stats['skipped'] += 1
        log('阶段 2：⏭️ 话题浏览已按配置跳过')
    def summary():
        if dry:
            data = {'user_summary': {key: 0 for key in METRICS}}
        else:
            data = client.get('/u/' + urllib.parse.quote(user['username'], safe='') + '/summary.json')
        values = data.get('user_summary')
        if not isinstance(values, dict):
            raise TaskError('缺少用户统计数据')
        for key in METRICS:
            value = values.get(key)
            if type(value) not in (int, float) or value < 0 or not value < float('inf'):
                raise TaskError('统计指标缺失或格式无效')
        for key, label in METRICS.items():
            requirement = REQUIREMENTS.get(user['trust_level'], {}).get(key)
            result = str(values[key])
            if requirement is not None:
                result += f' / 参考要求 {requirement}（' + ('达标' if values[key] >= requirement else '未达标') + '）'
            log(f'{label}：{result}')
        log('升级要求为上游参考值，站点实际审核结果以官方为准')
    # 登录失败禁止后续请求；浏览失败仍查询统计，最后保持失败。
    stage(stats, 3, '用户统计与升级参考', summary)
    if browsing_failed:
        raise TaskError('浏览阶段失败，统计已完成')

def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    if dry:
        log('断网预演：已生成脱敏通知摘要，跳过通知模块联网发送')
        return '断网预演未发送'
    paths = [Path(__file__).resolve().parent / 'notify.py']
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.insert(0, Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
    for path in paths:
        if not path.is_file():
            continue
        try:
            # 独立进程限制通知耗时并抑制第三方模块的输出。
            code = ("import importlib.util,sys; "
                    "s=importlib.util.spec_from_file_location('notify',sys.argv[1]); "
                    "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                    "r=m.send(sys.argv[2],sys.argv[3]); sys.exit(1 if r is False else 0)")
            result = subprocess.run([sys.executable, '-c', code, str(path), TITLE, body],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=20, check=False)
            if result.returncode == 0:
                return '已调用青龙通知'
        except (OSError, subprocess.TimeoutExpired):
            continue
    return '通知模块不可用或发送失败（保留业务退出码）'

def main():
    started = time.monotonic()
    dry = os.getenv('LINUXDO_DRY_RUN', '0').strip().lower() not in DISABLED
    cookies = [line.strip() for line in os.getenv('LINUXDO_COOKIES', '').splitlines() if line.strip()]
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{dt.datetime.now().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "正式运行"}；账号数：{len(cookies)}')
    results = []
    config_error = False
    try:
        dry = boolean('LINUXDO_DRY_RUN', '0')
        browse = boolean('BROWSE_ENABLED', 'true')
        limit = integer('TOPIC_LIMIT', 50, 1, 500)
        count = integer('BROWSE_COUNT', 20, 0, 500)
        if not cookies:
            raise TaskError('请设置必填 LINUXDO_COOKIES，每个非空行一个账号')
    except TaskError as exc:
        config_error = True
        log(f'❌ 配置错误：{exc}')
    if not config_error:
        for number, cookie in enumerate(cookies, 1):
            begin = time.monotonic()
            stats = {'account': number, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
            log(f'---------- 账号 {number}/{len(cookies)} ----------')
            try:
                validate_cookie(cookie)
                account(cookie, dry, browse, limit, count, stats)
            except TaskError as exc:
                if not stats['failed']:
                    stats['failed'] += 1
                    log(f'❌ 账号配置错误：{exc}')
            except Exception:
                stats['failed'] += 1
                log('❌ 未预期的运行或响应结构异常（已抑制敏感详情）')
            stats['total'] = sum(stats[key] for key in ('success', 'alreadyComplete', 'skipped', 'failed'))
            stats['seconds'] = round(time.monotonic() - begin, 2)
            stats['status'] = 'failed' if stats['failed'] else 'success'
            results.append(stats)
            log(f'账号 {number} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["seconds"]} 秒')
    good = sum(item['status'] == 'success' for item in results)
    bad = len(results) - good
    status = 'configuration-error' if config_error else ('partial-failure' if bad and good else 'failure' if bad else 'dry-run' if dry else 'success')
    code = 1 if config_error or bad else 0
    body = f'状态：{status}；账号总数：{len(cookies)}；成功：{good}；失败：{bad}；配置错误：{int(config_error)}'
    delivery = notify(body, dry)
    log('----------------------------------------')
    log(body)
    totals = {key: sum(item[key] for item in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log(f'通知状态：{delivery}')
    finish = dt.datetime.now().isoformat(timespec='seconds')
    elapsed = round(time.monotonic() - started, 2)
    log(f'完成时间：{finish}；总耗时：{elapsed} 秒；最终状态：{status}')
    if dry and code == 0:
        log('DRY_RUN_OK：本地预演通过，未验证真实业务')
    elif code == 0:
        log('LINUXDO_TASK_SUCCESS：已验证登录及启用任务')
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'mode': 'dry-run' if dry else 'live',
          'accounts': len(cookies), 'success': good, 'failed': bad, 'configurationError': config_error,
          'tasks': totals, 'accountResults': results, 'notification': delivery, 'seconds': elapsed,
          'finishTime': finish, 'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code

if __name__ == '__main__':
    sys.exit(main())
