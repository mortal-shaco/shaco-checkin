#!/usr/bin/env python3
# name: 申工社每日任务
# cron: 43 0 * * *
# 上游：Rookie-wb-WH/ql_scripts / sgs.py
# 上游提交：08e5c06461c4a0112ea3735f48fe671734bb7707；许可：MIT
# 原始说明：VX公众号 -- 申工社；抓包 fwdt.shengongshe.org 的 token。
# 原始变量 sgs 保留名称；账号改为每个非空行一个 Token，不再使用 #。
# 上游未提供 cron；此处建议每日 08:00，可在青龙调整。
"""申工社独立维护版（Python 3.9+，仅标准库）。
微信打开“申工社”公众号的服务大厅，登录后在本人授权的抓包工具中，
找到 fwdt.shengongshe.org 的请求头 Token，将值填写至青龙变量 sgs。
多个账号以换行分隔，不粘贴整个请求头、Cookie 或其他设备信息。
SGS_TASKS 默认 info,sign；可选 read,service,activity 会写入阅读/访问计数，
只在确认需要这些动作时开启，如 info,sign,read,service,activity。
SGS_DRY_RUN=1 完全断网预演；不验证凭据或真实业务。
QINGLONG_NOTIFY=0 关闭通知。预演通知同样禁止网络，只尝试本地通知适配器。

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
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('45e40e4a3ee37968', 'scripts/sgs.py', 'sgs.py', 'sgs')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://fwdt.shengongshe.org'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 NetType/WIFI '
      'MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x6309092b) XWEB/8555 Flue')
SIGN_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 15_6_1 like Mac OS X) '
           'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
           'MicroMessenger/8.0.42(0x18002a2f) NetType/WIFI Language/zh_CN')
LABELS = {'info': '账号信息', 'sign': '每日签到', 'read': '阅读文章',
          'service': '畅享工社服务', 'activity': '浏览热门活动'}


def log(message):
    print('[{}] {}'.format(datetime.datetime.now().strftime('%H:%M:%S'), message), flush=True)


def enabled(value):
    return value.lower().strip() in ('1', 'true', 'yes', 'on')


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('拒绝接口重定向，防止凭据转发')


class Account:
    def __init__(self, token, dry):
        self.token, self.dry = token, dry
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, payload=None, rest=False, sign=False):
        if self.dry:
            raise TaskError('预演禁止 HTTP 请求')
        headers = {'Host': 'fwdt.shengongshe.org', 'Token': self.token,
                   'User-Agent': SIGN_UA if sign else UA}
        body = None
        if rest:
            headers['Token-Source'] = 'SGS_TOKEN_REQUEST'
        if payload is not None:
            headers['Origin'] = BASE
            headers['Content-Type'] = ('application/json;charset=UTF-8' if rest
                                       else 'application/x-www-form-urlencoded')
            body = (json.dumps(payload, ensure_ascii=False).encode('utf-8') if rest
                    else urllib.parse.urlencode(payload).encode('utf-8'))
        req = urllib.request.Request(BASE + path, data=body, headers=headers)
        try:
            with self.opener.open(req, timeout=15) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('接口响应超过大小限制')
            result = json.loads(raw)
        except TaskError:
            raise
        except urllib.error.HTTPError as exc:
            raise TaskError('HTTP 请求失败，状态码 {}'.format(exc.code)) from None
        except Exception:
            raise TaskError('请求超时、网络异常或响应格式错误') from None
        if not isinstance(result, dict):
            raise TaskError('接口响应结构错误')
        expected = 0 if rest and payload is None else 200
        ok = (result.get('success') is True if rest and payload is not None
              else type(result.get('code')) is int and result['code'] == expected)
        if not ok:
            raise TaskError('业务接口未确认成功（请核对凭据或接口）')
        return result.get('data')

    def info(self):
        data = self.request('/sgsWchartApi/api/My/initPage')
        if not isinstance(data, dict) or 'name' not in data or 'integral' not in data:
            raise TaskError('账号信息缺少姓名或积分字段')
        name = data['name']
        if not isinstance(name, str) or not isinstance(data['integral'], (int, float)):
            raise TaskError('账号信息字段格式异常')
        # 非秘密官方身份原样显示；避免异常接口把凭据或手机号作为姓名返回。
        if self.token in name or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', name):
            log('官方身份字段含敏感信息，已抑制显示')
        else:
            log('🎁当前用户:{}，积分: {}'.format(name, data['integral']))

    def sign(self):
        self.request('/sgsWchartApi/api/My/sign', sign=True)

    def read(self):
        articles = {}
        # 原版无限随机分页；限制 20 页，保留随机页和最多五篇阅读能力。
        for attempt in range(20):
            data = self.request('/sgsWchartApi/api/ImageText/list',
                                {'page': str(random.randint(1, 255))})
            if not isinstance(data, dict) or not isinstance(data.get('news'), list):
                raise TaskError('文章列表结构异常')
            for item in data['news']:
                if not isinstance(item, dict) or not all(k in item for k in ('is_read', 'media_id', 'title')):
                    raise TaskError('文章字段缺失')
                if item['is_read'] == 0:
                    if not isinstance(item['media_id'], (str, int)):
                        raise TaskError('文章标识格式异常')
                    articles[item['media_id']] = item['title']
            log('文章检索 {}/20：未读候选 {} 篇'.format(attempt + 1, len(articles)))
            if len(articles) >= 10:
                break
            time.sleep(random.uniform(1, 4))
        if not articles:
            raise TaskError('未找到可执行文章；无法确认阅读任务完成')
        failures = 0
        for idx, media_id in enumerate(random.sample(list(articles), min(5, len(articles))), 1):
            try:
                self.request('/sgsWchartApi/api/ImageText/read', {'media_id': media_id})
                log('阅读子任务 {}：✅ 接口确认成功'.format(idx))
            except TaskError as exc:
                failures += 1
                log('阅读子任务 {}：❌ {}'.format(idx, exc))
            time.sleep(random.uniform(1, 4))
        if failures:
            raise TaskError('阅读子任务失败 {} 项'.format(failures))

    def browse(self, kind):
        data = self.request('/fwdt-rest/gateway/mobile-center/api/home/management/show', rest=True)
        if not isinstance(data, dict):
            raise TaskError('服务列表结构异常')
        items = []
        if kind == 'service':
            entries = data.get('navigationList')
            name_key, modular_type = 'appName', 1
        else:
            modules = data.get('modularList')
            if not isinstance(modules, list):
                raise TaskError('活动列表缺失')
            entries = []
            for module in modules[1:]:
                if not isinstance(module, dict) or not isinstance(module.get('dataList'), list):
                    raise TaskError('活动模块结构异常')
                entries.extend(module['dataList'])
            name_key, modular_type = 'title', 2
        if not isinstance(entries, list):
            raise TaskError('服务列表缺失')
        for item in entries:
            if not isinstance(item, dict) or not all(k in item for k in ('id', name_key)):
                raise TaskError('服务或活动字段缺失')
            if not isinstance(item['id'], (str, int)) or not isinstance(item[name_key], str):
                raise TaskError('服务或活动字段格式异常')
            items.append(item)
        if not items:
            raise TaskError('无可执行服务或活动；无法确认任务完成')
        failures = 0
        # 保留五次动作；优先不同项目，项目不足时保持上游五次计数。
        chosen = random.sample(items, min(5, len(items)))
        chosen += random.choices(items, k=5-len(chosen))
        for idx, item in enumerate(chosen, 1):
            try:
                self.request('/fwdt-rest/count/modularCount', {
                    'modularId': item['id'], 'modularType': modular_type,
                    'modularName': item[name_key]}, rest=True)
                log('浏览子任务 {}：✅ 接口确认成功'.format(idx))
            except TaskError as exc:
                failures += 1
                log('浏览子任务 {}：❌ {}'.format(idx, exc))
            time.sleep(random.uniform(1, 4))
        if failures:
            raise TaskError('浏览子任务失败 {} 项'.format(failures))


def notify(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in ('0', 'false', 'no', 'off'):
        return '已关闭'
    # 隔离通知导入、输出与异常；避免通知插件泄漏参数或改变业务退出码。
    helper = r'''
import contextlib, importlib, importlib.util, io, json, os, pathlib, socket, sys
body, dry = json.loads(sys.stdin.read())
if dry:
    def deny(*args, **kwargs): raise RuntimeError('dry-run network disabled')
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    try:
        module = importlib.import_module('notify')
    except ImportError:
        paths = []
        if os.getenv('QINGLONG_NOTIFY_DIR'):
            paths.append(pathlib.Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
        paths.extend([pathlib.Path('/ql/data/scripts/notify.py'), pathlib.Path('/ql/scripts/notify.py')])
        module = None
        for path in paths:
            if path.is_file():
                spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                break
        if module is None: sys.exit(3)
    module.send('申工社每日任务', body)
'''
    body = '账号总数：{accounts}；成功数：{success}；失败数：{failed}；状态：{status}'.format(**summary)
    if dry:
        body += '；断网预演，不代表真实业务成功'
    try:
        result = subprocess.run([sys.executable, '-c', helper], input=json.dumps([body, dry]),
                                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=20)
        return '已调用本地适配器（预演禁止网络）' if dry and result.returncode == 0 else (
            '已发送' if result.returncode == 0 else '不可用或发送失败，业务退出码保持不变')
    except Exception:
        return '通知异常或超时，业务退出码保持不变'


def main():
    start = time.monotonic()
    dry = enabled(os.getenv('SGS_DRY_RUN', '0'))
    tokens = [line.strip() for line in os.getenv('sgs', '').splitlines() if line.strip()]
    tasks = [x.strip() for x in os.getenv('SGS_TASKS', 'info,sign').split(',') if x.strip()]
    log('========== 申工社每日任务 ==========')
    log('开始时间：{}'.format(datetime.datetime.now().isoformat(timespec='seconds')))
    log('模式：{}；账号数：{}'.format('断网预演' if dry else '真实执行', len(tokens)))
    summary = {'accounts': len(tokens), 'success': 0, 'failed': 0, 'status': '',
               'mode': 'dry-run' if dry else 'live', 'taskSuccess': 0, 'taskFailed': 0,
               'taskSkipped': 0, 'alreadyComplete': 0}
    config_error = (not tokens or not tasks or len(tasks) != len(set(tasks))
                    or any(t not in LABELS for t in tasks))
    if config_error:
        summary['failed'] = len(tokens)
        log('❌ 配置错误：请填写 sgs（每行一个 Token）及有效、无重复的 SGS_TASKS')
    else:
        for index, token in enumerate(tokens, 1):
            account_start = time.monotonic()
            log('---------- 账号 {} ----------'.format(index))
            good = bad = skipped = 0
            invalid = any(c.isspace() or ord(c) < 32 or ord(c) > 126 for c in token) or '#' in token
            account = Account(token, dry)
            for stage, task in enumerate(tasks, 1):
                stamp = time.monotonic()
                log('阶段 {}/{}：{}'.format(stage, len(tasks), LABELS[task]))
                try:
                    if invalid:
                        raise TaskError('Token 格式异常；禁止旧版 # 多账号分隔，请改为换行')
                    if dry:
                        log('⏭️ DRY_RUN_OK：参数与动作规划通过，未发起网络请求')
                        skipped += 1
                    else:
                        if task in ('service', 'activity'):
                            account.browse(task)
                        else:
                            getattr(account, task)()
                        log('✅ {}：接口确认成功'.format(LABELS[task]))
                        good += 1
                except TaskError as exc:
                    log('❌ {}：{}'.format(LABELS[task], exc))
                    bad += 1
                except Exception:
                    log('❌ {}：执行异常（详情已抑制，保护凭据）'.format(LABELS[task]))
                    bad += 1
                log('阶段 {} 耗时 {:.2f} 秒'.format(stage, time.monotonic() - stamp))
            summary['failed' if bad else 'success'] += 1
            summary['taskSuccess'] += good
            summary['taskFailed'] += bad
            summary['taskSkipped'] += skipped
            log('账号 {}：总任务 {}，成功 {}，已完成 0，跳过 {}，失败 {}，耗时 {:.2f} 秒'.format(
                index, len(tasks), good, skipped, bad, time.monotonic()-account_start))
    code = 2 if config_error else (1 if summary['failed'] else 0)
    summary['status'] = ('configuration-error' if config_error else
                         'partial-failure' if summary['failed'] and summary['success'] else
                         'failure' if summary['failed'] else 'dry-run' if dry else 'success')
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic()-start, 2)
    summary['finishTime'] = datetime.datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log('账号总数 {accounts}，成功 {success}，失败 {failed}'.format(**summary))
    log('子任务：成功 {taskSuccess}，已完成 {alreadyComplete}，跳过 {taskSkipped}，失败 {taskFailed}'.format(**summary))
    log('通知：{}'.format(summary['notification']))
    log('总耗时：{} 秒；完成时间：{}；最终状态：{}'.format(
        summary['elapsedSeconds'], summary['finishTime'], summary['status']))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
