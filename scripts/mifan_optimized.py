#!/usr/bin/env python3
# name: 米饭APP日常维护
# cron: 59 0 * * *
# 上游: eggv/MeeFan-DailyCheckIn, mifan_optimized.py
# 来源提交: dd3668c8b870fe172ac97bcf96055ddcfceb6d49; 许可: MIT
# 原文件未包含额外版权或许可声明。
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
"""米饭APP独立维护脚本（Python 3.9+，仅标准库）。
MIFAN_ACCOUNTS 必填：每行 用户名|密码，只在第一个 | 分割。
账号密码在米饭APP/https://mifan.61.com 的本人账户注册或密码设置处获取。
兼容 MIFAN_USER / MIFAN_PASSWORD：分别每行一个且行数一致，不再以分号分账号。
MIFAN_TASKS=sign 默认只签到；可选 sign,like,comment,repair，以逗号组合。
ENABLE_REPAIR=true 兼容开启补签（可能消耗资源）；点赞、评论必须显式选择。
MIFAN_DRY_RUN=1 完全断网预演，不加载通知模块、不创建进度文件。
评论优先一言 HTTPS 服务，失败回退本地；MIFAN_LOCAL_TEXT 可设置本地文本。
旧 AI_PROVIDER、MOONSHOT_API_KEY、DEEPSEEK_API_KEY 不再用于自动发布，避免
额外付费及将动态内容发送第三方；公开评论遵从任务指定的一言/本地策略。
MIFAN_STATE_DIR 默认为脚本旁 .mifan-state，按账号哈希隔离进度。
QINGLONG_NOTIFY 未设置时按上架状态；设为 0/false/no/off 关闭。通知失败不改变业务退出码。
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
        _ql_notify_identities = ('68feda0fb9579305', 'scripts/mifan_optimized.py', 'mifan_optimized.py', 'mifan_optimized')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

BASE = 'https://mifan.61.com/api/v1/'
URLS = {'login': 'login', 'logout': 'logout', 'profile': 'profile',
        'sign': 'event/dailysign/', 'feed': 'feed',
        'comment': 'article/comment', 'recent': 'event/dailysign/recent',
        'repair': 'event/dailysign/complement'}
LOCAL = ['不错！', '学习到了！', '给力👍', '有意思！', '太棒了！', '好厉害呀！',
         '赞一个！', '收藏了～', '这个好！', '谢谢分享！', '确实如此！', '学到了！',
         '哈哈不错', '支持一下！']
OFF = {'0', 'false', 'no', 'off'}


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() not in OFF | {''}


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 避免凭据随重定向发往其他地址。
        return None


def http(url, method='POST', headers=None, data=None, timeout=15, limit=1048576):
    if enabled('MIFAN_DRY_RUN'):
        raise TaskError('预演禁止网络请求')
    body = None if data is None else urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(limit + 1)
        if len(raw) > limit:
            raise TaskError('响应过大')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise TaskError('响应结构异常')
        return result
    except TaskError:
        raise
    except Exception:
        # 异常可能含请求地址、服务端内容或认证信息，禁止直接输出。
        raise TaskError('网络、超时或 JSON 解析失败') from None


def verified(result):
    if result.get('code') != 200:
        raise TaskError('业务码未确认成功')
    return result


def normalized(value):
    return re.sub(r'\s+', ' ', value).strip() if isinstance(value, str) else ''


def public_text():
    try:
        # 独立请求，无米饭 Cookie、Token 或账号字段。
        result = http('https://v1.hitokoto.cn/?encode=json', 'GET',
                      {'Accept': 'application/json'}, timeout=8, limit=16384)
        text = normalized(result.get('hitokoto'))
        author = normalized(result.get('from_who'))
        source = normalized(result.get('from'))
        if not text:
            raise TaskError('缺少文本')
        if author and source:
            text += f' —— {author}《{source}》'
        elif source:
            text += f' ——《{source}》'
        elif author:
            text += f' —— {author}'
        if len(text) > 280:
            raise TaskError('文本过长')
        log('评论文本：一言获取成功，已保留作者/出处')
        return text
    except TaskError:
        log('⚠️ 一言不可用，回退本地文本')
        return normalized(os.getenv('MIFAN_LOCAL_TEXT', '')) or random.choice(LOCAL)


class Account:
    def __init__(self, index, user, password, tasks, dry):
        self.index, self.user, self.password = index, user, password
        self.tasks, self.dry, self.token = tasks, dry, ''
        self.counts = dict(success=0, alreadyComplete=0, skipped=0, failed=0)
        self.stage_number = 0
        self.state_path = Path(os.getenv('MIFAN_STATE_DIR', str(Path(__file__).resolve().parent / '.mifan-state'))) / (hashlib.sha256(user.encode()).hexdigest() + '.json')
        self.state = {'liked': [], 'commented': [], 'offset': -1}

    def request(self, action, data=None, method='POST'):
        path = URLS.get(action, action)
        headers = {'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest',
                   'Referer': 'https://mifan.61.com/dist/', 'Origin': 'https://mifan.61.com',
                   'Content-Type': 'application/x-www-form-urlencoded'}
        if self.token:
            headers['Authorization'] = self.token
        return http(BASE + path, method, headers, data)

    def login(self):
        result = verified(self.request('login', {'gid': 689, 'uid': self.user,
                          'password': hashlib.md5(self.password.encode()).hexdigest(),
                          'tad': '', 'encrypt': 'true'}))
        token = result.get('token')
        if not isinstance(token, str) or not token:
            raise TaskError('登录成功响应缺少 Token')
        self.token = token
        return 'success'

    def profile(self):
        result = self.request('profile')
        # 原接口返回顶层 gold/nickname；出现业务码时仍必须验证。
        if 'code' in result:
            verified(result)
        gold = result.get('gold')
        if isinstance(gold, bool) or not isinstance(gold, (int, float)) or gold < 0:
            raise TaskError('余额响应未确认有效')
        for key in ('nickname', 'username', 'display_name', 'uid'):
            value = result.get(key)
            if isinstance(value, (str, int)) and value != '':
                # 官方公开身份按返回值展示；JSON 转义控制字符，避免伪造日志行。
                log(f'账号 {self.index} 官方{key}: {json.dumps(value, ensure_ascii=False)}')
        log(f'米粒余额：{gold}')
        return 'success'

    def sign(self):
        result = self.request('sign')
        if result.get('data') == '已签到':
            return 'alreadyComplete'
        verified(result)
        return 'success'

    def feed(self, count, offset=-1):
        result = self.request('feed', {'type': 'latest', 'offset': offset, 'count': count,
                                      'start_time': 0, 'end_time': 0, 'tag_id': 'undefined',
                                      'timestamp': int(time.time())})
        if 'code' in result:
            verified(result)
        data = result.get('data')
        if not isinstance(data, dict) or not isinstance(data.get('current_page'), list):
            raise TaskError('动态流响应结构异常')
        items = []
        for item in data['current_page']:
            if not isinstance(item, dict) or item.get('cmd_id') != 7003:
                continue
            entry = item.get('data')
            if not isinstance(entry, dict):
                raise TaskError('文章响应结构异常')
            aid = str(entry.get('article_id', ''))
            if not aid.isdigit() or int(aid) <= 0:
                raise TaskError('文章标识无效')
            items.append((aid, bool(normalized(entry.get('text')))))
        return items, data.get('next_offset', -1)

    def save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state), encoding='utf-8')
        temporary.replace(self.state_path)

    def like(self):
        items, _ = self.feed(20)
        selected = [aid for aid, _ in items if aid not in self.state['liked']][:20]
        if not selected:
            return 'skipped'
        failures = 0
        for aid in selected:
            try:
                verified(self.request(f'article/likes/{aid}/'))
                self.state['liked'].append(aid)
                self.save()
                log(f'✅ 点赞文章 {aid}，进度已保存')
            except (TaskError, OSError):
                failures += 1
                log(f'❌ 点赞文章 {aid} 未确认成功')
            time.sleep(random.uniform(3, 10))
        if failures:
            raise TaskError(f'点赞失败 {failures} 次')
        return 'success'

    def comment(self):
        items, offset = self.feed(15, self.state['offset'])
        selected = [aid for aid, has_text in items if has_text and aid not in self.state['commented']][:10]
        if not selected:
            return 'skipped'
        failures = 0
        for aid in selected:
            try:
                result = verified(self.request('comment', {'comment_article_id': aid,
                                  'post_text': public_text(), 'post_atcount': 0}))
                if not result.get('data'):
                    raise TaskError('评论结果未确认')
                self.state['commented'].append(aid)
                self.save()
                log(f'✅ 评论文章 {aid}，进度已保存')
                if result.get('gold') == -1:
                    log('⏭️ 官方返回无米粒奖励，停止后续评论')
                    break
                time.sleep(random.uniform(30, 60))
            except (TaskError, OSError):
                failures += 1
                log(f'❌ 评论文章 {aid} 未确认成功')
        if failures:
            raise TaskError(f'评论失败 {failures} 次；保留游标以便下次重试')
        # 达到数量上限时不跳过当前页剩余文章。
        if len(selected) < 10:
            self.state['offset'] = offset
            self.save()
        return 'success'

    def repair(self):
        result = self.request('recent', method='GET')
        if 'code' in result:
            verified(result)
        days = result.get('data')
        if not isinstance(days, list):
            raise TaskError('补签日期响应结构异常')
        failures, done = 0, 0
        for day in days:
            if not isinstance(day, dict) or len(day) != 1:
                raise TaskError('补签日期结构异常')
            date, status = next(iter(day.items()))
            if status != 0:
                continue
            if not isinstance(date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
                raise TaskError('补签日期无效')
            try:
                verified(self.request('repair', {'complement_date': date}))
                done += 1
                log(f'✅ 补签 {date}')
            except TaskError:
                failures += 1
                log(f'❌ 补签 {date} 未确认成功')
            time.sleep(3)
        if failures:
            raise TaskError(f'补签失败 {failures} 次')
        return 'success' if done else 'alreadyComplete'

    def logout(self):
        verified(self.request('logout'))
        self.token = ''
        return 'success'

    def stage(self, label, function):
        self.stage_number += 1
        start = time.monotonic()
        log(f'账号 {self.index} 阶段 {self.stage_number}：{label}')
        try:
            status = 'success' if self.dry else function()
            self.counts[status] += 1
            log(f'{"预演通过（未发送请求）" if self.dry else {"success":"✅ 成功", "alreadyComplete":"☑️ 已完成", "skipped":"⏭️ 无待处理项"}[status]}；耗时 {time.monotonic()-start:.2f}秒')
            return True
        except Exception as exc:
            self.counts['failed'] += 1
            message = str(exc) if isinstance(exc, TaskError) else '本地进度或响应处理失败'
            log(f'❌ {message}；耗时 {time.monotonic()-start:.2f}秒')
            return False

    def run(self):
        start = time.monotonic()
        if self.dry:
            log(f'账号 {self.index}：凭据格式有效；预演不读写进度，不执行公开操作')
        elif self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text(encoding='utf-8'))
                if not isinstance(state, dict) or not all(isinstance(state.get(k), list) for k in ('liked', 'commented')):
                    raise ValueError()
                self.state.update(state)
            except Exception:
                self.stage('加载进度', lambda: (_ for _ in ()).throw(TaskError('进度损坏，停止账号以避免重复公开操作')))
                return self.result(start)
        if self.stage('登录', self.login):
            try:
                self.stage('任务前余额与身份', self.profile)
                for action in self.tasks:
                    self.stage({'sign':'每日签到', 'like':'动态点赞', 'comment':'公开评论', 'repair':'补签'}[action], getattr(self, action))
                self.stage('任务后余额与身份', self.profile)
            finally:
                self.stage('登出', self.logout)
        return self.result(start)

    def result(self, start):
        result = {'account': self.index, 'status': self.counts['failed'] == 0,
                  **self.counts, 'total': sum(self.counts.values()), 'seconds': round(time.monotonic()-start, 2)}
        log(f'账号 {self.index} 统计：总任务 {result["total"]}，成功 {result["success"]}，已完成 {result["alreadyComplete"]}，跳过 {result["skipped"]}，失败 {result["failed"]}，耗时 {result["seconds"]}秒')
        return result


def accounts():
    canonical = os.getenv('MIFAN_ACCOUNTS', '')
    if canonical.strip():
        pairs = []
        for line in canonical.splitlines():
            if not line.strip():
                continue
            user, separator, password = line.partition('|')
            if not separator or not user.strip() or not password:
                raise TaskError('MIFAN_ACCOUNTS 每行必须为用户名|密码')
            pairs.append((user.strip(), password))
        return pairs
    users = [line.strip() for line in os.getenv('MIFAN_USER', '').splitlines() if line.strip()]
    passwords = [line for line in os.getenv('MIFAN_PASSWORD', '').splitlines() if line.strip()]
    if not users or len(users) != len(passwords):
        raise TaskError('请设置 MIFAN_ACCOUNTS；兼容变量必须每行对应且数量一致')
    return list(zip(users, passwords))


def notify(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    if dry:
        log('通知预演：摘要已准备，不加载通知模块或联网')
        return '预演'
    # 通知模块为可选青龙集成，业务逻辑无外部文件依赖。
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            from notify import send
            send('米饭APP日常维护', body)
            return '已发送'
        except Exception:
            pass
        roots = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
        for root in filter(None, roots):
            path = Path(root) / 'notify.py'
            if path.is_file():
                try:
                    spec = importlib.util.spec_from_file_location('mifan_ql_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.send('米饭APP日常维护', body)
                    return '已发送'
                except Exception:
                    pass
            js = Path(root) / 'sendNotify.js'
            if js.is_file():
                try:
                    subprocess.run(['node', '-e', 'require(process.argv[1]).sendNotify(process.argv[2],process.argv[3]).catch(()=>process.exit(1))', str(js), '米饭APP日常维护', body], check=True, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return '已发送'
                except Exception:
                    pass
    return '不可用或发送失败（不影响业务退出码）'


def main():
    start, dry = time.monotonic(), enabled('MIFAN_DRY_RUN')
    log('🍚 米饭APP日常维护')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if dry else "正式执行"}')
    results, total, config_error = [], 0, False
    try:
        pairs = accounts()
        total = len(pairs)
        tasks = list(dict.fromkeys(x.strip() for x in os.getenv('MIFAN_TASKS', 'sign').split(',') if x.strip()))
        if enabled('ENABLE_REPAIR') and 'repair' not in tasks:
            tasks.append('repair')
        if not tasks or any(x not in {'sign', 'like', 'comment', 'repair'} for x in tasks):
            raise TaskError('MIFAN_TASKS 仅允许 sign,like,comment,repair')
        local = normalized(os.getenv('MIFAN_LOCAL_TEXT', ''))
        if len(local) > 280:
            raise TaskError('MIFAN_LOCAL_TEXT 不能超过280字')
        log(f'账号总数：{total}；任务：{",".join(tasks)}')
        for index, (user, password) in enumerate(pairs, 1):
            results.append(Account(index, user, password, tasks, dry).run())
    except TaskError as exc:
        config_error = True
        log(f'❌ 配置错误：{exc}')
        log(f'账号总数：{total}')
    success = sum(result['status'] for result in results)
    failed = total - success
    status = 'configuration-error' if config_error else ('dry-run' if dry and not failed else 'success' if not failed else 'partial-failure' if success else 'failure')
    exit_code = 1 if config_error or failed else 0
    body = f'状态：{status}\n账号总数：{total}\n成功：{success}\n失败：{failed}\n配置错误：{int(config_error)}'
    notification = notify(body, dry)
    log('------------------------------------------------')
    log(body.replace('\n', '；'))
    counters = {key: sum(r[key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log(f'子任务统计：{json.dumps(counters, ensure_ascii=False)}')
    log(f'通知状态：{notification}；总耗时：{time.monotonic()-start:.2f}秒')
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}')
    summary = {'status': status, 'accounts': total, 'success': success, 'failed': failed,
               'configurationError': config_error, 'results': results, 'tasks': counters,
               'notification': notification, 'exitCode': exit_code}
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
