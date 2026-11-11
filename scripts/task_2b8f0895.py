#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NewAPI 自动签到
# cron: 55 10 * * *
"""NewAPI 自动签到，Python 3.9+，仅使用标准库。
来源：Tamichyan/tamichyan.github.io，checkin.py
上游提交：9beb7aa27d5342e035776dd912562055169859c6；许可证：MIT。
原文说明：NewAPI 自动签到脚本，支持多账号签到，通过 GitHub Actions 定时执行。
原文通知补丁：DINGTALK NOTIFICATION PATCH — added to send DingTalk notifications.
上游文件未附具名版权声明，保留上述归属。

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
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

配置 NEWAPI_ACCOUNTS：每个非空行一个账号，格式为 HTTPS站点#Session值，
仅按第一个 # 拆分。需要用户ID或cf_clearance时，每行使用JSON对象：
{"url":"https://example.invalid","session":"占位","user_id":"123","cf_clearance":"占位"}
登录自己的 NewAPI 站点后在浏览器开发者工具 Application/Cookies 中复制
session（只取值）和可选 cf_clearance；用户ID从自己的个人资料或
/api/user/self 的已认证响应 data.id 获取；不从第三方登录ID猜测。
兼容原JSON数组配置及name字段；旧逗号分隔简写须改成换行。
每日09:00为建议青龙时间表，上游没有固定cron。运行时区由青龙决定。
NEWAPI_DRY_RUN=1 进行完全离线预演（包括通知）；不证明业务成功。
QINGLONG_NOTIFY=auto|1|0，auto默认仅本脚本；QINGLONG_NOTIFY_SCRIPTS
设置后替换默认名单，支持逗号/分号/空白分隔的目录相对路径、文件名、glob、
catalogId或*，空值关闭。支持QINGLONG_NOTIFY_DIR和青龙标准通知路径。
可选DINGTALK_WEBHOOK从钉钉群机器人获取，签名机器人另配DINGTALK_SECRET。
通知失败不改变业务退出码，任意账号或配置失败时非零退出。
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
        _ql_notify_identities = ('2b8f08952817263d', 'scripts/task_2b8f0895.py', 'task_2b8f0895.py', 'task_2b8f0895')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import base64
from datetime import datetime
from urllib import request, parse, error

TITLE = 'NewAPI 自动签到'
CATALOG_ID = '2b8f08952817263d'
TIMEOUT = 30
MAX_BYTES = 1024 * 1024


class TaskError(Exception):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 禁止凭据随重定向离开原接口


def log(text):
    print(f'[{datetime.now():%H:%M:%S}] {text}', flush=True)


def https_url(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise TaskError('站点地址格式错误')
    try:
        p = parse.urlsplit(value)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise ValueError()
        _ = p.port
    except ValueError:
        raise TaskError('站点必须为无内嵌凭据、查询参数和片段的HTTPS地址') from None
    return value.rstrip('/')


def token(value):
    if not isinstance(value, str) or not value or re.search(r'[\x00-\x20\x7f;]', value):
        raise TaskError('Cookie字段缺失或含非法字符，请只复制Cookie值')
    try:
        value.encode('ascii')
    except UnicodeError:
        raise TaskError('Cookie值必须为有效ASCII文本') from None
    return value


def account_lines(raw):
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith('['):
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError()
            return data
        except (ValueError, TypeError):
            return [None]
    return [line.strip() for line in raw.splitlines() if line.strip()]


def parse_account(item):
    if isinstance(item, str):
        if item.startswith('{'):
            try:
                item = json.loads(item)
            except ValueError:
                raise TaskError('账号JSON格式错误') from None
        elif '#' in item:
            url, session = item.split('#', 1)
            if re.search(r',\s*https?://', session):
                raise TaskError('旧逗号多账号配置须改为每行一个账号')
            item = {'url': url.strip(), 'session': session.strip()}
    if not isinstance(item, dict):
        raise TaskError('账号格式错误，请使用站点#Session或单行JSON对象')
    result = {'url': https_url(item.get('url')), 'session': token(item.get('session'))}
    uid = item.get('user_id')
    if uid is not None and uid != '':
        if isinstance(uid, bool) or not re.fullmatch(r'[1-9][0-9]*', str(uid)):
            raise TaskError('用户ID必须为正整数')
        result['user_id'] = str(uid)
    cf = item.get('cf_clearance')
    if cf:
        result['cf_clearance'] = token(cf)
    if isinstance(item.get('name'), str):
        result['name'] = item['name']
    return result


def http_json(url, method='GET', headers=None, payload=None):
    req = request.Request(url, data=payload, headers=headers or {}, method=method)
    try:
        # 禁用环境代理和重定向，避免Cookie被意外转发。
        opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=TIMEOUT) as resp:
            if resp.status != 200:
                raise TaskError(f'HTTP {resp.status}')
            raw = resp.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise TaskError('响应超过安全大小限制')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TaskError('接口响应不是JSON对象')
        return data
    except error.HTTPError as exc:
        raise TaskError(f'HTTP {exc.code}，请检查认证或站点接口') from None
    except (error.URLError, TimeoutError, OSError):
        raise TaskError('网络请求失败或超时') from None
    except (ValueError, UnicodeError):
        raise TaskError('接口响应不是有效JSON') from None


class NewAPICheckin:
    def __init__(self, account):
        self.base = account['url']
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-store', 'Pragma': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cookie': 'session=' + account['session'],
        }
        if account.get('cf_clearance'):
            self.headers['Cookie'] += '; cf_clearance=' + account['cf_clearance']
        if account.get('user_id'):
            self.headers['new-api-user'] = account['user_id']

    def call(self, path, method='GET'):
        data = http_json(self.base + path, method, self.headers)
        if data.get('success') is not True:
            raise TaskError('接口未明确确认业务成功（success不为true）')
        body = data.get('data')
        if not isinstance(body, dict):
            raise TaskError('接口data结构异常')
        return body

    def get_user_info(self):
        body = self.call('/api/user/self')
        uid = body.get('id')
        if isinstance(uid, bool) or not re.fullmatch(r'[1-9][0-9]*', str(uid)):
            raise TaskError('个人资料缺少有效用户ID，请核对站点接口')
        self.headers['new-api-user'] = str(uid)
        return body

    def checkin(self):
        return self.call('/api/user/checkin', 'POST')

    def get_checkin_history(self, month=None):
        month = month or datetime.now().strftime('%Y-%m')
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
            raise TaskError('查询月份格式应为YYYY-MM')
        return self.call('/api/user/checkin?' + parse.urlencode({'month': month}))


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def quota(value):
    if value >= 1000000:
        return f'{value / 1000000:.2f}M'
    if value >= 1000:
        return f'{value / 1000:.2f}K'
    return str(value)


def identity(info, account):
    for key in ('display_name', 'nickname', 'username', 'id'):
        value = info.get(key)
        if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value):
            continue
        text = str(value)
        # 官方身份原样显示；排除凭据回显、手机号及日志控制字符。
        if any(account.get(k) and str(account[k]) in text for k in ('session', 'cf_clearance')):
            continue
        if re.search(r'[\x00-\x1f\x7f]|(?:\+?86[- ]?)?1[3-9]\d{9}', text):
            continue
        log(f'官方身份（{key}）：{text}')


def notify(summary, dry):
    mode = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if mode not in ('auto', '1', 'true', 'yes', 'on', '0', 'false', 'no', 'off'):
        log('⚠️ 通知开关无效，跳过通知')
        return '配置无效'
    if mode in ('0', 'false', 'no', 'off'):
        return '已关闭'
    if mode == 'auto':
        selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', CATALOG_ID).strip())
        here = Path(__file__)
        names = [CATALOG_ID, here.name]
        for base in ('/ql/data/scripts', '/ql/scripts'):
            try:
                names.append(here.resolve().relative_to(base).as_posix())
            except ValueError:
                pass
        if not any(fnmatch.fnmatchcase(name, pat) for pat in selectors if pat for name in names):
            return '未选中'
    if dry:
        log('⏭️ 离线预演：已生成通知摘要，不调用通知模块或钉钉')
        return '离线模拟'
    body = (f"状态：{summary['status']}；账号总数 {summary['accounts']}，"
            f"成功 {summary['success']}，失败 {summary['failed']}；"
            f"子任务成功 {summary['steps_success']}，失败 {summary['steps_failed']}")
    # 在子进程运行可选青龙通知，限制时间并丢弃可能含凭据的通知模块输出。
    code = '''import importlib.util,json,sys
p=json.loads(sys.stdin.read())
if p['path']:
 s=importlib.util.spec_from_file_location('qinglong_notify',p['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
else:
 import notify as m
m.send(p['title'],p['body'])
'''
    folders = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    paths = [str(Path(f) / 'notify.py') for f in folders if f and (Path(f) / 'notify.py').is_file()]
    js_paths = [str(Path(f) / 'sendNotify.js') for f in folders if f and (Path(f) / 'sendNotify.js').is_file()]
    delivered = False
    for path in [None] + paths:
        try:
            proc = subprocess.run([sys.executable, '-c', code], input=json.dumps({'path': path, 'title': TITLE, 'body': body}), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if proc.returncode == 0:
                delivered = True
                break
        except (OSError, subprocess.TimeoutExpired):
            pass
    if not delivered:
        for path in js_paths:
            try:
                js = "const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));Promise.resolve(require(p.path).sendNotify(p.title,p.body)).catch(()=>process.exit(1));"
                proc = subprocess.run(['node', '-e', js], input=json.dumps({'path': path, 'title': TITLE, 'body': body}), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                if proc.returncode == 0:
                    delivered = True
                    break
            except (OSError, subprocess.TimeoutExpired):
                pass
    log('✅ 青龙通知已发送' if delivered else '⚠️ 青龙通知不可用或发送失败，保留业务退出码')
    if os.getenv('DINGTALK_WEBHOOK'):
        try:
            url = os.environ['DINGTALK_WEBHOOK']
            p = parse.urlsplit(url)
            if p.scheme != 'https' or p.hostname != 'oapi.dingtalk.com' or p.path != '/robot/send' or p.username or p.password or p.fragment or p.port not in (None, 443):
                raise TaskError('钉钉地址配置无效')
            secret = os.getenv('DINGTALK_SECRET')
            if secret:
                stamp = str(int(time.time() * 1000))
                sign = base64.b64encode(hmac.new(secret.encode(), (stamp + '\n' + secret).encode(), hashlib.sha256).digest()).decode()
                url += '&' + parse.urlencode({'timestamp': stamp, 'sign': sign})
            result = http_json(url, 'POST', {'Content-Type': 'application/json'}, json.dumps({'msgtype': 'text', 'text': {'content': TITLE + '\n' + body}}).encode())
            if result.get('errcode') != 0:
                raise TaskError('钉钉未确认成功')
            log('✅ 钉钉通知已发送')
        except Exception:
            log('⚠️ 钉钉通知失败，保留业务退出码')
    return '已发送' if delivered else '不可用或失败'


def main():
    started = time.monotonic()
    dry_value = os.getenv('NEWAPI_DRY_RUN', '0').strip().lower()
    dry = dry_value in ('1', 'true', 'yes', 'on')
    items = account_lines(os.getenv('NEWAPI_ACCOUNTS', ''))
    summary = {'accounts': len(items), 'success': 0, 'failed': 0, 'dry_run': dry,
               'steps_success': 0, 'steps_failed': 0, 'steps_skipped': 0}
    print('=' * 50)
    log(TITLE + f' | 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'模式：{"离线预演" if dry else "正式签到"} | 账号总数：{len(items)}')
    config_error = dry_value not in ('0', 'false', 'no', 'off', '1', 'true', 'yes', 'on')
    if config_error:
        log('❌ NEWAPI_DRY_RUN值无效，停止请求')
        items = []
    if not summary['accounts']:
        config_error = True
        log('❌ 未配置NEWAPI_ACCOUNTS，每行填写HTTPS站点#Session值')
    for i, item in enumerate(items, 1):
        begin = time.monotonic()
        ok = failed = skipped = 0
        log(f'账号 {i}/{len(items)} 开始')
        try:
            account = parse_account(item)
            label = account.get('name', '')
            if label and not re.search(r'[\x00-\x1f\x7f]|(?:\+?86[- ]?)?1[3-9]\d{9}', label) and not any(account.get(k) and account[k] in label for k in ('session', 'cf_clearance')):
                log('账号备注：' + label)
            log('阶段 1/4 配置校验 ✅（耗时 %.2f秒）' % (time.monotonic() - begin))
            ok += 1
            if dry:
                for n, title in ((2, '读取官方身份'), (3, '提交签到'), (4, '查询本月统计')):
                    log(f'阶段 {n}/4 {title} ⏭️ 离线预演，不发请求（耗时 0.00秒）')
                skipped = 3
                log('DRY_RUN_OK：账号配置有效，业务请求及通知均未发送')
            else:
                client = NewAPICheckin(account)
                for n, title, action in ((2, '读取官方身份', client.get_user_info), (3, '提交签到', client.checkin), (4, '查询本月统计', client.get_checkin_history)):
                    step = time.monotonic()
                    try:
                        data = action()
                        if n == 2:
                            identity(data, account)
                        elif n == 3:
                            date = data.get('checkin_date')
                            if isinstance(date, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
                                log('签到日期：' + date)
                            awarded = data.get('quota_awarded')
                            if number(awarded):
                                log(f'奖励：+{quota(awarded)} 额度（{awarded:,} tokens）')
                        else:
                            stats = data.get('stats')
                            if not isinstance(stats, dict) or not all(number(stats.get(k)) for k in ('checkin_count', 'total_quota')):
                                raise TaskError('本月统计字段缺失或格式异常')
                            log(f"统计：本月已签 {stats['checkin_count']} 天，累计 {quota(stats['total_quota'])} 额度")
                        ok += 1
                        log(f'阶段 {n}/4 {title} ✅ 业务成功（耗时 {time.monotonic() - step:.2f}秒）')
                    except TaskError as exc:
                        failed += 1
                        skipped += 4 - n
                        log(f'阶段 {n}/4 {title} ❌ {exc}（耗时 {time.monotonic() - step:.2f}秒）')
                        break
        except TaskError as exc:
            failed += 1
            skipped = 3
            log(f'阶段 1/4 配置校验 ❌ {exc}（耗时 {time.monotonic() - begin:.2f}秒）')
        except Exception:
            failed += 1
            skipped = max(0, 4 - ok - failed)
            log('❌ 执行异常，已隐藏异常详情以保护凭据')
        summary['failed' if failed else 'success'] += 1
        summary['steps_success'] += ok
        summary['steps_failed'] += failed
        summary['steps_skipped'] += skipped
        log(f'账号 {i} 统计：总任务4，成功{ok}，已完成0，跳过{skipped}，失败{failed}，耗时{time.monotonic() - begin:.2f}秒')
    code = 1 if config_error or summary['failed'] else 0
    summary['status'] = ('configuration-error' if config_error else 'partial-failure' if summary['failed'] and summary['success'] else 'failure' if code else 'dry-run' if dry else 'success')
    try:
        summary['notification'] = notify(summary, dry or config_error and dry_value not in ('0', 'false', 'no', 'off'))
    except Exception:
        summary['notification'] = '不可用或失败'
        log('⚠️ 通知执行异常，保留业务退出码')
    summary['elapsed_seconds'] = round(time.monotonic() - started, 2)
    summary['exit_code'] = code
    print('-' * 50)
    log(f"账号统计：总数{summary['accounts']}，成功{summary['success']}，失败{summary['failed']}")
    log(f"子任务统计：成功{summary['steps_success']}，已完成0，跳过{summary['steps_skipped']}，失败{summary['steps_failed']}")
    log(f"总耗时：{summary['elapsed_seconds']}秒 | 通知：{summary['notification']}")
    log(f"完成时间：{datetime.now():%Y-%m-%d %H:%M:%S} | 最终状态：{summary['status']}")
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
