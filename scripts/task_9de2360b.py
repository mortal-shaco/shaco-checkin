#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 今日校园问卷
# cron: 36 9 * * *
# SPDX-License-Identifier: Apache-2.0
# Derived from ZimoLoveShuang/auto-submit, index.py
# https://github.com/ZimoLoveShuang/auto-submit
# Upstream revision: 16b41fa0b47c7aef2875170a915df5db55f9a5cf
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy at https://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
"""每行一个 CPDAILY_ACCOUNTS JSON 对象。默认仅查询；提交必须显式设置
CPDAILY_ACTION=submit，并提供本人确认的答案、地址与当前 Cpdaily-Extension。
不再把学号密码发送到第三方登录代理，不读取 config.yml，不记录答案或凭据。
图片路径仅在显式提交时读取及上传；图片字段也可使用已有 HTTPS 附件地址。
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
        _ql_notify_identities = ('9de2360bf4ea8141', 'scripts/task_9de2360b.py', 'task_9de2360b.py', 'task_9de2360b')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import copy
import fnmatch
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from urllib.parse import urlencode, urlsplit, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = '今日校园问卷'
CATALOG = '9de2360bf4ea8141'
PREFIX = '/wec-counselor-collector-apps/stu/collector/'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
MAX_BYTES = 2 * 1024 * 1024


class TaskError(Exception):
    """只携带可公开的静态错误描述。"""


def stamp():
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')


def log(text):
    print('[' + stamp()[11:] + '] ' + text, flush=True)


class NoRedirect(HTTPRedirectHandler):
    # 不把 Cookie、上传签名或认证信息转发给其他地址。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def https_url(value, suffixes=None):
    if not isinstance(value, str):
        raise TaskError('地址必须为 HTTPS 地址')
    p = urlsplit(value)
    if (p.scheme != 'https' or not p.hostname or p.username or p.password
            or p.port not in (None, 443) or p.fragment):
        raise TaskError('地址不符合 HTTPS 安全约束')
    if suffixes and not any(p.hostname.endswith('.' + s) for s in suffixes):
        raise TaskError('服务域名不在允许范围')
    return p


def http(url, payload=None, headers=None, method=None, raw=False):
    if os.environ.get('CPDAILY_DRY_RUN', '').lower() in TRUE:
        raise TaskError('预演禁止网络请求')
    https_url(url)
    body = payload
    req_headers = {'User-Agent': 'Mozilla/5.0 cpdaily/8.1.11 wisedu/8.1.11'}
    req_headers.update(headers or {})
    if isinstance(payload, dict):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req_headers['Content-Type'] = 'application/json;charset=UTF-8'
    req = Request(url, data=body, headers=req_headers, method=method)
    try:
        with build_opener(NoRedirect()).open(req, timeout=20) as res:
            data = res.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise TaskError('响应超过大小限制')
            if not 200 <= res.status < 300:
                raise TaskError('HTTP 状态未通过检查')
            if raw:
                return data
            obj = json.loads(data)
    except TaskError:
        raise
    except Exception:
        raise TaskError('请求失败：网络、认证、超时或响应格式异常') from None
    if not isinstance(obj, dict):
        raise TaskError('响应不是业务对象')
    return obj


def business(obj):
    # 无原始响应输出；缺失成功标记不能视为成功。
    code = obj.get('code')
    if code is not None:
        if str(code) not in {'0', '200'}:
            raise TaskError('业务码未通过成功检查，请检查登录状态或接口版本')
    elif obj.get('message') != 'SUCCESS':
        raise TaskError('响应缺少可确认的成功标记')
    if 'datas' not in obj:
        raise TaskError('响应缺少业务数据')
    return obj['datas']


def api(account, host, name, payload):
    obj = http('https://' + host + PREFIX + name, payload,
               {'Cookie': account['cookie']})
    # 仅识别响应明确标注的身份，不遍历问卷题目、答案或原始响应。
    identities = [obj]
    if isinstance(obj.get('datas'), dict):
        identities.append(obj['datas'])
        if isinstance(obj['datas'].get('userInfo'), dict):
            identities.append(obj['datas']['userInfo'])
    secrets = [account['cookie'], account.get('extension', '')]
    secrets += [v.strip() for part in account['cookie'].split(';')
                for k, sep, v in [part.partition('=')] if sep]
    for identity in identities:
        for key in ('nickname', 'username', 'displayName', 'uid'):
            value = identity.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            text = str(value)
            if (not text or any(secret and secret in text for secret in secrets)
                    or re.search(r'(?<![0-9])(?:\+?86[- ]?)?1[3-9][0-9]{9}(?![0-9])', text)):
                continue
            log('官方账号身份（%s）：%s' % (key, text.replace('\r', ' ').replace('\n', ' ')))
            return obj
    return obj


def discover(account):
    if account.get('host'):
        p = https_url('https://' + account['host'], ('campusphere.net', 'cpdaily.com'))
        if p.path or p.query:
            raise TaskError('host 只能填写域名')
        return p.hostname
    schools = http('https://www.cpdaily.com/v6/config/guest/tenant/list')
    data = schools.get('data')
    if not isinstance(data, list):
        raise TaskError('院校列表结构异常')
    matches = [x for x in data if x.get('name') == account['school']]
    if len(matches) != 1 or matches[0].get('joinType') == 'NONE':
        raise TaskError('未找到唯一已接入的院校，请核对学校全称')
    obj = http('https://www.cpdaily.com/v6/config/guest/tenant/info?' +
               urlencode({'ids': matches[0]['id']}))
    rows = obj.get('data')
    if not isinstance(rows, list) or not rows:
        raise TaskError('院校详情结构异常')
    # 与上游相同，优先使用有效的 ampUrl2。
    for key in ('ampUrl2', 'ampUrl'):
        url = rows[0].get(key)
        if url:
            try:
                return https_url(url, ('campusphere.net', 'cpdaily.com')).hostname
            except TaskError:
                continue
    raise TaskError('未发现可信院校服务域名；可配置抓包得到的 host')


def query(account, host):
    data = business(api(account, host, 'queryCollectorProcessingList',
                        {'pageSize': 6, 'pageNumber': 1}))
    if not isinstance(data, dict) or not isinstance(data.get('rows'), list):
        raise TaskError('待填列表结构异常')
    if not data['rows']:
        return None
    row = data['rows'][0]
    if not row.get('wid') or not row.get('formWid'):
        raise TaskError('问卷标识缺失')
    result = {'collectWid': row['wid'], 'formWid': row['formWid']}
    detail = business(api(account, host, 'detailCollector', {'collectorWid': row['wid']}))
    try:
        result['schoolTaskWid'] = detail['collector']['schoolTaskWid']
    except (TypeError, KeyError):
        raise TaskError('问卷详情结构异常') from None
    fields = business(api(account, host, 'getFormFields',
                          {'pageSize': 100, 'pageNumber': 1,
                           'formWid': row['formWid'], 'collectorWid': row['wid']}))
    if not isinstance(fields, dict) or not isinstance(fields.get('rows'), list):
        raise TaskError('问卷字段结构异常')
    if len(fields['rows']) >= 100 or int(fields.get('totalSize', len(fields['rows']))) > len(fields['rows']):
        raise TaskError('字段可能被分页截断，拒绝提交不完整问卷')
    result['form'] = fields['rows']
    return result


def plan_form(form, defaults):
    required = [copy.deepcopy(x) for x in form if x.get('isRequired') == 1]
    if len(required) != len(defaults):
        raise TaskError('必填题数量与已确认答案数量不一致')
    pictures = []
    for index, (item, default) in enumerate(zip(required, defaults), 1):
        # 兼容上游 defaults[].default 包装。
        default = default.get('default', default)
        if item.get('title') != default.get('title') or 'value' not in default:
            raise TaskError('第 %d 题标题或答案配置不匹配' % index)
        value = default['value']
        kind = item.get('fieldType')
        if kind in (1, 5):
            if not isinstance(value, str) or not value.strip():
                raise TaskError('文本答案不能为空')
            item['value'] = value
        elif kind in (2, 3):
            values = value.split(',') if kind == 3 and isinstance(value, str) else [value]
            if not all(isinstance(v, str) and v for v in values) or len(set(values)) != len(values):
                raise TaskError('选择题答案格式无效')
            options = item.get('fieldItems', [])
            selected = [x for x in options if x.get('content') in values]
            if len(selected) != len(values):
                raise TaskError('选择题答案不在当前选项中')
            item['fieldItems'] = selected
            item['value'] = value if kind == 2 else ''.join(v + ' ' for v in values)
        elif kind == 4:
            if not isinstance(value, str) or not value:
                raise TaskError('图片答案格式无效')
            if value.startswith('https://'):
                https_url(value)
                item['value'] = value
            else:
                image = Path(value).expanduser()
                if not image.is_file() or image.stat().st_size > 10 * 1024 * 1024:
                    raise TaskError('图片文件不存在或超过 10 MiB')
                pictures.append((item, image))
        else:
            raise TaskError('存在不支持的必填题类型，拒绝猜测答案')
    return required, pictures


def upload(account, host, image):
    data = image.read_bytes()
    if not data or len(data) > 10 * 1024 * 1024:
        raise TaskError('图片为空或超过大小限制')
    sts = business(api(account, host, 'getStsAccess', {}))
    keys = ('fileName', 'accessKeyId', 'accessKeySecret', 'securityToken', 'endPoint', 'bucket')
    if not isinstance(sts, dict) or not all(isinstance(sts.get(k), str) and sts[k] for k in keys):
        raise TaskError('上传临时授权结构异常')
    endpoint = sts['endPoint']
    if '://' not in endpoint:
        endpoint = 'https://' + endpoint
    p = https_url(endpoint, ('aliyuncs.com',))
    bucket = sts['bucket']
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', bucket):
        raise TaskError('上传桶名称无效')
    key = sts['fileName']
    if key.startswith('/') or '?' in key or '#' in key or '\n' in key:
        raise TaskError('附件标识无效')
    date = formatdate(usegmt=True)
    content_type = 'application/octet-stream'
    token = sts['securityToken']
    canonical = ('PUT\n\n' + content_type + '\n' + date + '\n' +
                 'x-oss-security-token:' + token + '\n/' + bucket + '/' + key)
    signature = base64.b64encode(hmac.new(sts['accessKeySecret'].encode(),
                                        canonical.encode(), hashlib.sha1).digest()).decode()
    http('https://' + bucket + '.' + p.hostname + '/' + quote(key, safe='/'), data,
         {'Content-Type': content_type, 'Date': date, 'x-oss-security-token': token,
          'Authorization': 'OSS ' + sts['accessKeyId'] + ':' + signature}, method='PUT', raw=True)
    preview = business(api(account, host, 'previewAttachment', {'ossKey': key}))
    https_url(preview)
    return preview


def parse_account(line, action):
    try:
        account = json.loads(line)
    except (ValueError, TypeError):
        raise TaskError('账号行必须为完整 JSON 对象') from None
    if not isinstance(account, dict):
        raise TaskError('账号必须为 JSON 对象')
    if not isinstance(account.get('cookie'), str) or not account['cookie'].strip():
        raise TaskError('账号缺少 cookie')
    if '\r' in account['cookie'] or '\n' in account['cookie']:
        raise TaskError('Cookie 不得包含换行')
    if not account.get('host') and not account.get('school'):
        raise TaskError('账号缺少院校全称或服务 host')
    if action == 'submit':
        if not isinstance(account.get('address'), str) or not account['address'].strip():
            raise TaskError('提交需要本人确认的 address')
        if not isinstance(account.get('defaults'), list):
            raise TaskError('提交需要 defaults 答案列表')
        extension = account.get('extension')
        if not isinstance(extension, str) or not extension.strip() or re.search(r'[\r\n]', extension):
            raise TaskError('提交需要当前账号合法的 extension 请求头')
    return account


def notify(body, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower()
    if switch in FALSE:
        return '已关闭'
    if switch not in TRUE | {'auto'}:
        return '开关无效，未发送'
    selection = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    names = (CATALOG, Path(__file__).name, 'scripts/' + Path(__file__).name)
    selected = selection is not None and any(
        fnmatch.fnmatch(n, s) for s in re.split(r'[,;\s]+', selection.strip()) if s for n in names)
    if (selection is not None and not selected) or (switch == 'auto' and not selected):
        return '未选中'
    if dry:
        return '预演：已模拟通知，未联网'
    # 单独子进程隔离通知模块输出，超时或失败不覆盖业务退出码。
    helper = '''import importlib.util, json, sys
payload=json.loads(sys.stdin.read())
if sys.argv[1] == 'module':
 import notify
else:
 spec=importlib.util.spec_from_file_location('notify', sys.argv[1])
 notify=importlib.util.module_from_spec(spec)
 spec.loader.exec_module(notify)
notify.send(payload[0], payload[1])
'''
    paths = ['module']
    folder = os.environ.get('QINGLONG_NOTIFY_DIR')
    if folder:
        paths.append(str(Path(folder) / 'notify.py'))
    paths += ['/ql/data/scripts/notify.py', '/ql/scripts/notify.py']
    js_paths = ([str(Path(folder) / 'sendNotify.js')] if folder else []) + [
        '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js']
    payload = json.dumps([TITLE, body], ensure_ascii=False)
    for path in paths:
        if path != 'module' and not Path(path).is_file():
            continue
        try:
            result = subprocess.run([sys.executable, '-c', helper, path], input=payload,
                                    text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                return '已发送'
        except Exception:
            pass
    for path in js_paths:
        if not Path(path).is_file():
            continue
        try:
            code = "let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',async()=>{try{const p=JSON.parse(s);await require(process.argv[1]).sendNotify(p[0],p[1]);}catch(e){process.exitCode=1;}});"
            result = subprocess.run(['node', '-e', code, path], input=payload, text=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                return '已发送'
        except Exception:
            pass
    return '不可用或发送失败（保留业务退出码）'


def main():
    started = time.monotonic()
    dry = os.environ.get('CPDAILY_DRY_RUN', '').lower() in TRUE
    action = os.environ.get('CPDAILY_ACTION', 'query').strip()
    lines = [x.strip() for x in os.environ.get('CPDAILY_ACCOUNTS', '').splitlines() if x.strip()]
    print('========== ' + TITLE + ' ==========')
    print('开始时间：' + stamp())
    print('运行模式：' + ('断网预演' if dry else '正式执行') + '；动作：' +
          (action if action in {'query', 'submit'} else '无效配置'))
    print('账号数量：%d' % len(lines))
    results = []
    config_error = not lines or action not in {'query', 'submit'}
    if config_error:
        log('❌ 阶段 1 配置检查：缺少账号或动作无效')
    else:
        for number, line in enumerate(lines, 1):
            begin = time.monotonic()
            stats = {'account': number, 'total': 0, 'success': 0,
                     'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
            stage = 0
            def step(label, fn):
                nonlocal stage
                stage += 1
                stats['total'] += 1
                tick = time.monotonic()
                log('账号 %d 阶段 %d %s：开始' % (number, stage, label))
                try:
                    value = fn()
                except Exception:
                    stats['failed'] += 1
                    log('❌ 账号 %d 阶段 %d 失败，耗时 %.2f 秒' %
                        (number, stage, time.monotonic() - tick))
                    raise
                stats['success'] += 1
                log('✅ 账号 %d 阶段 %d %s：通过，耗时 %.2f 秒' %
                    (number, stage, label, time.monotonic() - tick))
                return value
            try:
                account = step('参数校验', lambda: parse_account(line, action))
                if dry:
                    # 不读取图片，不导入通知，不调用随机文本或任何网络接口。
                    def rehearse():
                        if action == 'submit':
                            for default in account['defaults']:
                                if not isinstance(default, dict):
                                    raise TaskError('答案项必须为对象')
                                item = default.get('default', default)
                                if not isinstance(item, dict) or not item.get('title') or 'value' not in item:
                                    raise TaskError('答案项缺少 title 或 value')
                        if account.get('host'):
                            https_url('https://' + account['host'], ('campusphere.net', 'cpdaily.com'))
                    step('断网流程预演', rehearse)
                    stats['skipped'] += 1
                    stats['total'] += 1
                    log('⏭️ 账号 %d：已模拟院校发现、问卷读取及所选动作；未验证登录或业务成功' % number)
                    stats['status'] = 'dry-run'
                else:
                    host = step('院校服务发现', lambda: discover(account))
                    form = step('读取当前首份待填问卷', lambda: query(account, host))
                    if form is None:
                        stats['skipped'] += 1
                        stats['total'] += 1
                        log('☑️ 账号 %d：已验证无待填问卷（不推断历史提交结果）' % number)
                    elif action == 'query':
                        log('✅ 账号 %d：查询成功，发现待填问卷；未执行提交' % number)
                    else:
                        prepared, pictures = step('核对题目和确认答案', lambda: plan_form(form['form'], account['defaults']))
                        for item, image in pictures:
                            item['value'] = step('上传已确认图片', lambda: upload(account, host, image))
                        def submit():
                            payload = {k: v for k, v in form.items() if k != 'form'}
                            payload.update({'address': account['address'], 'form': prepared})
                            response = http('https://' + host + PREFIX + 'submitForm', payload,
                                            {'Cookie': account['cookie'], 'CpdailyStandAlone': '0',
                                             'extension': '1', 'Cpdaily-Extension': account['extension']})
                            if response.get('message') == '该收集已填写无需再次填写':
                                return 'already'
                            if response.get('message') != 'SUCCESS' or (
                                    'code' in response and str(response['code']) not in {'0', '200'}):
                                raise TaskError('未取得明确提交成功标记；不自动重试，请在官方页面核对')
                            return 'submitted'
                        outcome = step('提交已确认问卷', submit)
                        if outcome == 'already':
                            stats['success'] -= 1
                            stats['alreadyComplete'] += 1
                        log(('☑️ 今日已提交！' if outcome == 'already' else '✅ 自动提交成功！'))
                    stats['status'] = 'success'
            except TaskError as exc:
                stats['status'] = 'failure'
                log('❌ 账号 %d：%s' % (number, exc))
            except Exception:
                stats['status'] = 'failure'
                log('❌ 账号 %d：配置或响应结构异常；未输出原始数据' % number)
            stats['elapsedSeconds'] = round(time.monotonic() - begin, 3)
            log('账号 %(account)d 统计：总任务 %(total)d，成功 %(success)d，已完成 %(alreadyComplete)d，跳过 %(skipped)d，失败 %(failed)d，耗时 %(elapsedSeconds).3f 秒' % stats)
            results.append(stats)
    failed = sum(x['status'] == 'failure' for x in results)
    good = len(results) - failed
    status = ('configuration-error' if config_error else 'partial-failure' if failed and good
              else 'failure' if failed else 'dry-run' if dry else 'success')
    code = 1 if config_error or failed else 0
    body = '账号总数 %d，成功 %d，失败 %d；状态 %s%s' % (
        len(lines), good, failed, status, '；预演仅校验配置' if dry else '')
    delivery = notify(body, dry)
    print('----------------------------------------')
    print(body)
    totals = {k: sum(x[k] for x in results) for k in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    print('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    print('通知状态：' + delivery)
    print('总耗时：%.3f 秒；完成时间：%s；最终状态：%s' % (time.monotonic() - started, stamp(), status))
    if code == 0 and not dry:
        print('success')  # 保留上游成功输出；预演不得伪装为业务成功。
    if code == 0 and dry:
        print('DRY_RUN_OK')
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'mode': 'dry-run' if dry else 'live',
          'accounts': len(lines), 'successfulAccounts': good, 'failedAccounts': failed,
          'configurationError': config_error, 'tasks': totals, 'results': results,
          'notification': delivery, 'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
