#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 霸王茶姬签到
# cron: 0 9,18 * * *
# author: 清风
# 上游: Rookie-wb-WH/ql_scripts/bwcj.py
# 原更新记录: 2024-08-30 更新签到; 2024.09.28 删除无效活动
# License: MIT (任务授权的有效许可)
"""霸王茶姬小程序签到，Python 3.8+，仅使用标准库。

bwcjCookie: 每个非空行一个 Qm-User-Token；可用 Token|customerId 补充
同账号用户 ID（仅在积分流水为空时需要）。只在第一个 | 分割，后续文本保留。
在本人微信霸王茶姬小程序登录后，从本人授权的请求中获取 Qm-User-Token；
customerId 来自 customer-points-flow 的 data.data 项，勿使用手机号或设备 ID。
不再支持 @ 或 & 分隔账号，请改为换行。
BWCJ_TASKS: new（默认）, old, 或 new,old；旧版仅按需显式开启。
BWCJ_ACTIVITY_ID: 新版活动 ID，默认保留上游值；活动变更时从本人签到请求获取。
BWCJ_STORE_ID: 签到请求中的 storeId/store_id，默认保留上游 49006。
BWCJ_DRY_RUN=1: 完全断网预演，不发送签到或外部通知，仅展示通知摘要。
QINGLONG_NOTIFY=0: 禁用通知；默认通过青龙 notify.py 发送脱敏总结。
QINGLONG_NOTIFY_DIR: 可选，青龙 notify.py 所在目录。
原定时: 0 9,18 * * *。不会发帖、消费积分或更改用户资料。

静态功能对照：上游默认读取用户资料、积分流水用户 ID、新版签到统计和新版签到；
旧版详情和签到有实现但未在主流程启用。本版全部保留，旧版需显式开关。
任务未提供优化目标、维护覆盖或相关来源。移除远程群公告与混淆执行包装。
接口、请求头、签名字段与响应字段以本地上游静态字节码为依据，未联网验证。
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

APPID = 'wxafec6f8422cb357b'
BASE = 'https://webapi2.qmai.cn'
OLD_BASE = 'https://webapi.qmai.cn'
UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 16_1_2 like Mac OS X) '
      'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
      'MicroMessenger/8.0.40(0x18002831) NetType/WIFI Language/zh_CN')
DISABLED = {'0', 'false', 'no', 'off'}


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() in {'1', 'true', 'yes', 'on'}


def log(text):
    print('[{}] {}'.format(datetime.datetime.now().strftime('%H:%M:%S'), text), flush=True)


class TaskError(Exception):
    """只包含固定的脱敏错误说明。"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向已拒绝，防止凭据发送到其他地址')


def request(token, base, path, payload, method='POST'):
    headers = {'Content-Type': 'application/json', 'Qm-From': 'wechat',
               'Qm-From-Type': 'catering', 'Qm-User-Token': token,
               'Referer': 'https://servicewechat.com/{}/186/page-frame.html'.format(APPID),
               'User-Agent': UA}
    url = base + path
    body = None
    if method == 'GET':
        url += '?' + urllib.parse.urlencode(payload)
    else:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError('接口 HTTP 状态异常')
            raw = response.read(1048577)
        if len(raw) > 1048576:
            raise TaskError('接口响应超过大小限制')
        data = json.loads(raw)
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError('接口 HTTP 错误 {}'.format(exc.code)) from None
    except (urllib.error.URLError, OSError, ValueError):
        raise TaskError('接口网络、超时或 JSON 解析失败') from None
    if not isinstance(data, dict):
        raise TaskError('接口响应结构异常')
    status = data.get('status')
    if not (status is True or (type(status) is int and status == 1)):
        raise TaskError('接口未确认业务成功，请核查登录状态和活动有效期')
    return data.get('data')


def require_object(data):
    if not isinstance(data, dict):
        raise TaskError('业务数据结构异常')
    return data


def days(data, field):
    value = require_object(data).get(field)
    if type(value) is not int or value < 0:
        raise TaskError('签到天数字段缺失或格式异常')
    return value


def signature(payload, uid):
    # 上游排序规则与反转活动 ID 密钥；统一使用同一个毫秒时间戳。
    fields = {'activityId': payload['activityId'], 'sellerId': payload['storeId'],
              'timestamp': payload['timestamp'], 'userId': uid}
    text = '&'.join('{}={}'.format(k, fields[k]) for k in sorted(fields))
    text += '&key=' + payload['activityId'][::-1]
    return dict(payload, signature=hashlib.md5(text.encode()).hexdigest().upper())


def safe_identity(value, credentials):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = str(value)
    if any(secret and secret in text for secret in credentials):
        return None
    # 保留官方非秘密身份原值；禁止手机号和日志控制符。
    if re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text) or any(ord(c) < 32 for c in text):
        return None
    return text


def notify(summary, dry):
    body = '账号总数 {accounts}，成功 {succeeded}，失败 {failed}；状态 {status}。'.format(**summary)
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        log('⏭️ 通知已关闭')
        return 'disabled'
    if dry:
        log('⏭️ 断网预演：通知摘要 ' + body)
        return 'dry-run'
    # 使用当前 Python 运行时加载青龙通知适配器，隔离其输出及运行时错误。
    worker = '''import importlib, importlib.util, os, sys
try:
    module = importlib.import_module("notify")
except ImportError:
    module = None
    paths = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(os.path.join(directory, "notify.py"))
    paths.extend(["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"])
    for path in paths:
        if os.path.isfile(path):
            sys.path.insert(0, os.path.dirname(path))
            spec = importlib.util.spec_from_file_location("notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            break
if module is None or not callable(getattr(module, "send", None)):
    sys.exit(2)
module.send(sys.argv[1], sys.argv[2])
'''
    try:
        result = subprocess.run([sys.executable, '-c', worker, '霸王茶姬签到', body],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=30, check=False)
        if result.returncode == 0:
            log('✅ 通知适配器调用完成')
            return 'sent'
    except (OSError, subprocess.TimeoutExpired):
        pass
    log('⚠️ 青龙通知不可用或调用失败，保留业务退出码')
    return 'unavailable-or-failed'


class Account:
    def __init__(self, number, line, tasks, dry, activity, store, secrets):
        self.number = number
        self.token, sep, self.uid = line.partition('|')
        self.token = self.token.strip()
        self.uid = self.uid.strip()
        self.tasks, self.dry = tasks, dry
        self.activity, self.store = activity, store
        self.secrets = secrets
        self.profile = None
        self.counts = dict(success=0, alreadyComplete=0, skipped=0, failed=0)
        self.started = time.monotonic()
        self.stage_number = 0

    def stage(self, name, operation, validate=False):
        self.stage_number += 1
        start = time.monotonic()
        log('账号 {} 阶段 {}：{}'.format(self.number, self.stage_number, name))
        try:
            if self.dry and not validate:
                log('⏭️ DRY_RUN：参数与流程检查通过，不发送请求')
                self.counts['skipped'] += 1
                return None
            result = operation()
            self.counts['success'] += 1
            log('✅ {}完成'.format(name))
            return result
        except TaskError as exc:
            self.counts['failed'] += 1
            log('❌ {}：{}'.format(name, exc))
        except Exception:
            self.counts['failed'] += 1
            log('❌ {}：响应契约或本地处理异常（已隐藏原始数据）'.format(name))
        finally:
            log('账号 {} 阶段 {} 耗时 {:.2f} 秒'.format(self.number, self.stage_number, time.monotonic()-start))
        return None

    def skip(self, name):
        self.stage_number += 1
        self.counts['skipped'] += 1
        log('账号 {} 阶段 {}：⏭️ {}，前置步骤失败；耗时 0.00 秒'.format(self.number, self.stage_number, name))

    def info(self):
        self.profile = require_object(request(self.token, BASE,
            '/web/catering2-apiserver/crm/personal-info', {'appid': APPID}, 'GET'))
        for field in ('name', 'nickname', 'username', 'displayName', 'uid'):
            identity = safe_identity(self.profile.get(field), self.secrets)
            if identity is not None:
                log('账号 {} 官方身份 {}：{}'.format(self.number, field, identity))
        return self.profile

    def user_id(self):
        data = require_object(request(self.token, BASE,
            '/web/mall-apiserver/integral/user/page/customer-points-flow',
            {'pageNo': 1, 'pageSize': 15, 'appid': APPID}))
        rows = data.get('data')
        if not isinstance(rows, list):
            raise TaskError('积分流水列表字段异常')
        ids = [str(row['customerId']) for row in rows if isinstance(row, dict)
               and isinstance(row.get('customerId'), (str, int))
               and not isinstance(row.get('customerId'), bool) and str(row['customerId']) not in ('', '0')]
        if len(set(ids)) > 1:
            raise TaskError('积分流水出现多个用户 ID，拒绝签到')
        if ids:
            if self.uid and self.uid != ids[0]:
                raise TaskError('配套用户 ID 与接口不一致，拒绝签到')
            self.uid = ids[0]
        if not self.uid:
            raise TaskError('积分流水没有用户 ID，请在同账号行补充 Token|customerId')
        return self.uid

    def new_detail(self):
        value = days(request(self.token, BASE, '/web/cmk-center/sign/userSignStatistics',
                            {'activityId': self.activity, 'appid': APPID}), 'signDays')
        log('新版累计签到 {} 天'.format(value))
        return value

    def new_sign(self, before):
        payload = {'activityId': self.activity, 'storeId': self.store,
                   'timestamp': str(int(time.time()*1000)), 'appid': APPID, 'store_id': self.store}
        data = require_object(request(self.token, BASE, '/web/cmk-center/sign/takePartInSign',
                                      signature(payload, self.uid)))
        rewards = data.get('rewardDetailList')
        if not isinstance(rewards, list) or not rewards:
            raise TaskError('签到成功状态缺少奖励明细，无法核验结果')
        for reward in rewards:
            if not isinstance(reward, dict) or 'rewardName' not in reward or 'sendNum' not in reward:
                raise TaskError('签到奖励字段异常')
            name = safe_identity(reward['rewardName'], self.secrets)
            quantity = reward['sendNum']
            if not name or type(quantity) not in (int, float) or quantity < 0:
                raise TaskError('签到奖励名称或数量异常')
            log('✅[新版签到]: {}，数量 {}'.format(name, quantity))
        log('新版签到已确认，预计连续签到 {} 天'.format(before + 1))
        return True

    def old_detail(self):
        data = require_object(request(self.token, OLD_BASE, '/web/catering/integral/sign/detail', {'appid': APPID}))
        activity = data.get('activityId')
        if not isinstance(activity, (str, int)) or isinstance(activity, bool) or str(activity) in ('', '0'):
            raise TaskError('旧版活动 ID 缺失')
        value = days(data, 'continuityTotal')
        log('旧版连续签到 {} 天'.format(value))
        return activity

    def old_sign(self, activity):
        phone, name = self.profile.get('mobilePhone'), self.profile.get('name')
        if not isinstance(phone, str) or not re.fullmatch(r'1[3-9]\d{9}', phone) or not isinstance(name, str):
            raise TaskError('旧版签到所需已绑定手机号或用户名缺失')
        request(self.token, OLD_BASE, '/web/catering/integral/sign/signIn',
                {'activityId': activity, 'mobilePhone': phone, 'userName': name, 'appid': APPID})
        log('✅[旧版签到]: 接口已确认业务成功')
        return True

    def run(self):
        if not self.token or any(ord(c) < 32 for c in self.token) or '@' in self.token or '&' in self.token:
            self.stage('账号参数检查', lambda: fail('账号格式错误，请使用每行一个 Token'), validate=True)
        elif '|' in self.uid or (self.uid and not re.fullmatch(r'[0-9]+', self.uid)):
            self.stage('账号参数检查', lambda: fail('配套 customerId 必须为数字'), validate=True)
        else:
            self.stage('读取用户信息', self.info)
            if 'new' in self.tasks:
                uid = self.stage('获取签到用户 ID', self.user_id)
                detail = self.stage('查询新版签到详情', self.new_detail)
                if self.dry or (uid is not None and detail is not None and self.profile is not None):
                    self.stage('执行新版签到', lambda: self.new_sign(detail))
                else:
                    self.skip('执行新版签到')
            if 'old' in self.tasks:
                activity = self.stage('查询旧版签到详情', self.old_detail)
                if self.dry or (activity is not None and self.profile is not None):
                    self.stage('执行旧版签到', lambda: self.old_sign(activity))
                else:
                    self.skip('执行旧版签到')
        duration = round(time.monotonic()-self.started, 2)
        log('账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {} 秒'.format(
            self.number, sum(self.counts.values()), self.counts['success'], self.counts['alreadyComplete'],
            self.counts['skipped'], self.counts['failed'], duration))
        return dict(account=self.number, **self.counts, durationSeconds=duration)


def fail(message):
    raise TaskError(message)


def main():
    start = time.monotonic()
    dry = enabled('BWCJ_DRY_RUN')
    lines = [line.strip() for line in os.getenv('bwcjCookie', '').splitlines() if line.strip()]
    tasks = [v.strip() for v in os.getenv('BWCJ_TASKS', 'new').split(',')]
    activity = os.getenv('BWCJ_ACTIVITY_ID', '947079313798000641').strip()
    store_text = os.getenv('BWCJ_STORE_ID', '49006').strip()
    print('========== 霸王茶姬签到 ==========', flush=True)
    log('开始时间：' + datetime.datetime.now().isoformat(timespec='seconds'))
    log('模式：{}；账号数：{}'.format('断网预演' if dry else '正式运行', len(lines)))
    config_error = (not lines or not tasks or any(v not in ('new', 'old') for v in tasks)
                    or len(set(tasks)) != len(tasks) or not activity.isdigit()
                    or not store_text.isdigit() or int(store_text) <= 0)
    results = []
    if config_error:
        log('❌ 阶段 1：配置错误；请检查 bwcjCookie、BWCJ_TASKS、活动 ID 和门店 ID；耗时 0.00 秒')
    else:
        secrets = [line.partition('|')[0].strip() for line in lines]
        for i, line in enumerate(lines, 1):
            results.append(Account(i, line, tasks, dry, activity, int(store_text), secrets).run())
    failed = sum(r['failed'] > 0 for r in results)
    succeeded = len(results) - failed
    status = ('configuration-error' if config_error else 'partial-failure' if failed and succeeded
              else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = dict(accounts=len(lines), succeeded=succeeded, failed=failed, status=status,
                   mode='dry-run' if dry else 'live', configurationErrors=int(bool(config_error)),
                   accountResults=results,
                   subtasks={k: sum(r[k] for r in results) for k in ('success', 'alreadyComplete', 'skipped', 'failed')})
    # 配置错误也体现在通知失败数中，避免“零失败”误导。
    if config_error:
        summary['failed'] = len(lines) or 1
    summary['notification'] = notify(summary, dry)
    summary['durationSeconds'] = round(time.monotonic()-start, 2)
    summary['finishedAt'] = datetime.datetime.now().isoformat(timespec='seconds')
    print('----------------------------------------', flush=True)
    log('任务统计：账号总数 {}，成功 {}，失败 {}；子任务 {}'.format(
        summary['accounts'], summary['succeeded'], summary['failed'], json.dumps(summary['subtasks'], ensure_ascii=False)))
    log('总耗时 {} 秒；完成时间 {}；通知状态 {}'.format(summary['durationSeconds'], summary['finishedAt'], summary['notification']))
    log('最终状态：' + status)
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return 1 if config_error or failed else 0


if __name__ == '__main__':
    sys.exit(main())
