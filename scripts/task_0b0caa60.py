# -*- coding: utf-8 -*-
# name: 欢太商城每日任务
# cron: 46 10 * * *
# 上游未声明 cron；维护版建议每天北京时间 08:00 执行。
# 上游: https://github.com/tangli159/HeytapTask main.py
# @Time    : 2021/7/13
# @Author  : 丶大K丶
# @Email   : k@hwkxk.cn
# License: MIT (effectiveLicense supplied by source catalog).
# 原文件未附完整许可正文；保留原作者署名，不推定或替换其版权声明。
"""欢太商城：HEYTAP_ACCOUNTS 每行 Cookie<TAB>User-Agent；仅按第一个 TAB 分隔。

登录欢太商城 APP，在自己的 HTTPS 调试会话中获取登录后的 Cookie 与完整
User-Agent，优先核对 www.heytap.com/cn/oapi/users/web/member/info 和
store.oppo.com/cn/oapi/credits/web/credits/show 请求。不分享抓包或凭据。
兼容当前目录 config.json 数组，每项沿用 cookies / User-Agent 字段。
HEYTAP_TASKS 默认 sign,browse；share,push 为显式启用的任务进度上报，
不会实际向微信发送消息，也不会发布任何公开文案。
HEYTAP_DRY_RUN=1 完全离线；预演不核验账号有效性，不发送网络通知。
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
        _ql_notify_identities = ('0b0caa60f0060df6', 'scripts/task_0b0caa60.py', 'task_0b0caa60.py', 'task_0b0caa60')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


TITLE = '欢太商城每日任务'
CATALOG_ID = '0b0caa60f0060df6'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
TASK_NAMES = {'sign': '每日签到', 'browse': '浏览商品及奖励',
              'share': '分享商品进度上报及奖励', 'push': '推送消息进度上报及奖励'}
HOSTS = {'www.heytap.com', 'store.oppo.com', 'msec.opposhop.cn'}
STORE = 'https://store.oppo.com'
MSEC = 'https://msec.opposhop.cn'
SECRETS = []


class TaskError(Exception):
    """只携带可公开的固定错误信息。"""


def safe_identity(value):
    # 保留官方昵称原值；只删除控制字符和确实包含的凭据/手机号。
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(c for c in text if c.isprintable())


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


def register_secrets(cookie, ua):
    SECRETS.extend([cookie, ua])
    for part in cookie.split(';'):
        if '=' in part:
            SECRETS.append(part.split('=', 1)[1].strip())


def read_accounts():
    raw = os.environ.get('HEYTAP_ACCOUNTS', '')
    accounts = []
    if raw.strip():
        for line in raw.splitlines():
            if not line.strip():
                continue
            if '\t' not in line:
                accounts.append(None)
                continue
            cookie, ua = line.split('\t', 1)
            accounts.append((cookie.strip(), ua.strip()))
    else:
        # 旧配置仅为可选兼容入口；不依赖工作流仓库或任何固定私有路径。
        path = Path('config.json')
        if not path.is_file():
            raise TaskError('缺少 HEYTAP_ACCOUNTS：每行填写 Cookie、制表符、User-Agent')
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise TaskError('旧版 config.json 无法读取或 JSON 格式错误') from None
        if not isinstance(data, list):
            raise TaskError('旧版 config.json 必须是账号数组')
        for item in data:
            accounts.append((item.get('cookies'), item.get('User-Agent'))
                            if isinstance(item, dict) else None)
    if not accounts:
        raise TaskError('没有非空账号配置')
    for item in accounts:
        if item and all(isinstance(x, str) and x for x in item):
            register_secrets(*item)
    return accounts


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口返回重定向，已停止以保护凭据')


class Client:
    def __init__(self, cookie, ua):
        self.cookie, self.ua = cookie, ua
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())

    def request(self, url, data=None, mobile=False, reward=False):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
            raise TaskError('请求地址不在官方 HTTPS 白名单')
        headers = {'Accept': 'application/json, text/plain, */*',
                   'Content-Type': 'application/x-www-form-urlencoded',
                   'User-Agent': 'okhttp/3.12.12.200sp1' if mobile else self.ua,
                   'Accept-Language': 'zh-cn', 'Cookie': self.cookie}
        if mobile or reward:
            headers['clientPackage'] = 'com.oppo.store'
        if parsed.hostname == 'store.oppo.com':
            headers['Referer'] = STORE + '/cn/app/taskCenter/index'
        if reward:
            headers.update({'Origin': STORE, 'X-Requested-With': 'com.oppo.store',
                            'Referer': STORE + '/cn/app/taskCenter/index?us=gerenzhongxin&um=hudongleyuan&uc=renwuzhongxin'})
        payload = urllib.parse.urlencode(data).encode() if data is not None else None
        request = urllib.request.Request(url, data=payload, headers=headers)
        try:
            with self.opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态非 200')
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise TaskError('接口响应超过大小限制')
            result = json.loads(raw)
        except TaskError:
            raise
        except urllib.error.HTTPError as exc:
            raise TaskError(f'HTTP 请求失败（状态 {exc.code}）') from None
        except (OSError, ValueError, urllib.error.URLError):
            raise TaskError('请求超时、网络异常或响应不是有效 JSON') from None
        if not isinstance(result, dict):
            raise TaskError('接口 JSON 结构异常')
        code = result.get('code')
        if code is None and isinstance(result.get('meta'), dict):
            code = result['meta'].get('code')
        if type(code) is not int or code != 200:
            raise TaskError('接口未返回已知成功业务码 200；请核对凭据或接口状态')
        return result

    def center(self):
        result = self.request(STORE + '/cn/oapi/credits/web/credits/show')
        data = result.get('data')
        if not isinstance(data, dict):
            raise TaskError('任务中心缺少有效 data')
        return data

    def task(self, name):
        tasks = self.center().get('everydayList')
        if not isinstance(tasks, list):
            raise TaskError('任务中心缺少每日任务列表')
        for task in tasks:
            if isinstance(task, dict) and task.get('name') == name:
                return task
        raise TaskError('服务端未提供对应每日任务，可能已下线')

    def cash(self, task):
        fields = ('marking', 'type', 'credits')
        if any(task.get(key) is None for key in fields):
            raise TaskError('奖励领取缺少任务参数')
        self.request(STORE + '/cn/oapi/credits/web/credits/cashingCredits',
                     {'marking': task['marking'], 'type': task['type'],
                      'amount': task['credits']}, reward=True)
        log('✅ 奖励领取接口确认成功')

    def sign(self):
        report = self.center().get('userReportInfoForm')
        gifts = report.get('gifts') if isinstance(report, dict) else None
        if not isinstance(gifts, list):
            raise TaskError('签到日历缺失')
        today = datetime.date.today().isoformat()
        gift = next((x for x in gifts if isinstance(x, dict) and x.get('date') == today), None)
        if not gift or type(gift.get('today')) is not bool or gift.get('credits') is None:
            raise TaskError('找不到当天签到参数，未发起签到')
        data = {'amount': gift['credits']}
        # 保留上游 today 字段两分支，不把它误判为已签到标志。
        if gift['today']:
            if gift.get('type') is None or gift.get('gift') is None:
                raise TaskError('当天签到缺少 type 或 gift')
            data.update({'type': gift['type'], 'gift': gift['gift']})
        self.request(STORE + '/cn/oapi/credits/web/report/immediately', data)
        log('✅ 签到接口确认成功')
        return 'success'

    def browse(self):
        task = self.task('浏览商品')
        if is_complete(task):
            return 'alreadyComplete'
        result = self.request(MSEC + '/goods/v1/SeckillRound/goods/3016?pageSize=12&currentPage=1', mobile=True)
        items = result.get('detail')
        if not isinstance(items, list) or not items:
            raise TaskError('商品列表为空或格式异常')
        for index, item in enumerate(items, 1):
            if not isinstance(item, dict) or item.get('skuid') is None:
                raise TaskError('商品缺少 SKU 参数')
            url = MSEC + '/goods/v1/info/sku?' + urllib.parse.urlencode({'skuId': item['skuid']})
            self.request(url, mobile=True)
            log(f'✅ 商品浏览 {index}/{len(items)} 业务码确认成功')
            time.sleep(5)
        self.cash(task)
        return 'success'

    def push_task(self, key):
        task = self.task('分享商品到微信' if key == 'share' else '点推送消息')
        if is_complete(task):
            return 'alreadyComplete'
        count, total = task.get('readCount'), task.get('times')
        if type(count) is not int or type(total) is not int or not 0 <= count <= total <= 100:
            raise TaskError('任务次数无效或超出安全范围')
        marking = 'daily_sharegoods' if key == 'share' else 'daily_viewpush'
        # 修正上游 <= 带来的额外一次上报，仅执行剩余次数。
        for index in range(count, total):
            self.request(MSEC + '/users/vi/creditsTask/pushTask?' +
                         urllib.parse.urlencode({'marking': marking}), mobile=True)
            log(f'✅ 进度上报 {index + 1}/{total} 业务码确认成功')
        self.cash(task)
        return 'success'


def is_complete(task):
    status = task.get('completeStatus')
    if type(status) is not int or status < 0:
        raise TaskError('任务完成状态缺失或异常')
    # 沿用上游非零表示无需再执行的行为，不重复领取。
    if status != 0:
        log('☑️ 服务端标记任务已完成，无需重复执行')
        return True
    return False


def selected_for_notification():
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower().strip()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    if 'QINGLONG_NOTIFY_SCRIPTS' not in os.environ:
        return False  # listed-only 默认列表未收录此新脚本
    selectors = re.split(r'[,;\s]+', os.environ['QINGLONG_NOTIFY_SCRIPTS'].strip())
    path = Path(__file__).as_posix()
    relative = path.split('/scripts/', 1)[-1]
    names = (CATALOG_ID, Path(__file__).name, relative, 'scripts/' + relative)
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in selectors if pattern for name in names)


def notify_summary(body, dry):
    if not selected_for_notification():
        return '未选中或已关闭'
    if dry:
        log('⏭️ 断网预演：已生成脱敏通知摘要，未调用通知模块')
        return '断网预演已模拟'
    # 通知模块运行于限时子进程，捕获其输出，避免异常日志泄露配置。
    python_code = """import importlib.util, sys
title, body, path = sys.argv[1:4]
if path:
    spec = importlib.util.spec_from_file_location('ql_task_notify', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
result = module.send(title, body)
sys.exit(1 if result is False else 0)
"""
    attempts = [[sys.executable, '-c', python_code, TITLE, body, '']]
    dirs = [os.environ.get('QINGLONG_NOTIFY_DIR'), '/ql/data/scripts', '/ql/scripts']
    for directory in dirs:
        if not directory:
            continue
        path = Path(directory) / 'notify.py'
        if path.is_file():
            attempts.append([sys.executable, '-c', python_code, TITLE, body, str(path)])
    for directory in dirs:
        if directory and (Path(directory) / 'sendNotify.js').is_file():
            attempts.append(['node', '-e',
                             'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(r=>{if(r===false)process.exitCode=1}).catch(()=>{process.exitCode=1})',
                             str(Path(directory) / 'sendNotify.js'), TITLE, body])
    for command in attempts:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    log('⚠️ 通知不可用或发送失败，保留业务退出码')
    return '不可用或失败'


def counts():
    return dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0)


def run_account(index, account, tasks, dry):
    started = time.monotonic()
    stats = counts()
    stats['total'] = 1 + len(TASK_NAMES)
    valid = (account is not None and all(isinstance(x, str) and x for x in account)
             and all('\r' not in x and '\n' not in x for x in account)
             and all(ord(c) <= 255 for x in account for c in x))
    if not valid:
        stats['failure'] = 1
        stats['skipped'] = len(TASK_NAMES)
        log(f'账号 {index} 阶段 1/5：参数核验')
        log(f'❌ 账号 {index} 配置错误：Cookie 与 User-Agent 必须非空且可作为 HTTP 头；其余阶段跳过')
        log(f'账号 {index} 阶段 1 耗时 {time.monotonic() - started:.2f} 秒')
        return stats, round(time.monotonic() - started, 3)
    client = None if dry else Client(*account)
    authenticated = False
    for stage, key in enumerate(['login'] + list(TASK_NAMES), 1):
        stage_start = time.monotonic()
        name = '登录核验' if key == 'login' else TASK_NAMES[key]
        log(f'账号 {index} 阶段 {stage}/5：{name}')
        try:
            if key != 'login' and (key not in tasks or not authenticated):
                state = 'skipped'
                log('⏭️ 未启用该任务或登录未通过')
            elif dry:
                state = 'skipped'
                authenticated = True
                log('⏭️ 离线预演：参数有效，模拟执行；未请求接口，未改变账号状态')
            elif key == 'login':
                result = client.request('https://www.heytap.com/cn/oapi/users/web/member/info')
                data = result.get('data')
                if not isinstance(data, dict):
                    raise TaskError('登录响应缺少账号信息')
                for field in ('nickname', 'nickName', 'username', 'userName', 'displayName', 'realName', 'uid'):
                    if data.get(field) is not None and data[field] != '':
                        log('账号身份：' + safe_identity(data[field]))
                authenticated = True
                log('✅ 登录业务码确认成功')
                state = 'success'
            elif key == 'sign':
                state = client.sign()
                time.sleep(1)
            elif key == 'browse':
                state = client.browse()
            else:
                state = client.push_task(key)
            stats[state] += 1
        except TaskError as exc:
            stats['failure'] += 1
            log('❌ ' + str(exc))
        except Exception:
            stats['failure'] += 1
            log('❌ 执行异常，已隐藏异常详情及请求信息')
        log(f'账号 {index} 阶段 {stage} 耗时 {time.monotonic() - stage_start:.2f} 秒')
    return stats, round(time.monotonic() - started, 3)


def main(event=None, context=None):
    started = time.monotonic()
    start_time = datetime.datetime.now().isoformat(timespec='seconds')
    dry = os.environ.get('HEYTAP_DRY_RUN', '').strip().lower() in TRUE
    log('=== ' + TITLE + ' ===')
    log(f'开始时间：{start_time}；模式：' + ('断网预演' if dry else '真实执行'))
    results, error, accounts = [], None, []
    try:
        accounts = read_accounts()
        tasks = {x.strip() for x in os.environ.get('HEYTAP_TASKS', 'sign,browse').split(',') if x.strip()}
        if not tasks or not tasks <= set(TASK_NAMES):
            raise TaskError('HEYTAP_TASKS 必须为 sign,browse,share,push 的非空逗号分隔子集')
        log(f'账号数量：{len(accounts)}；已启用任务：' + ','.join(k for k in TASK_NAMES if k in tasks))
        for index, account in enumerate(accounts, 1):
            stats, elapsed = run_account(index, account, tasks, dry)
            results.append({'account': index, **stats, 'elapsedSeconds': elapsed})
            log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，'
                f'已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failure"]}，耗时 {elapsed:.2f} 秒')
    except TaskError as exc:
        error = str(exc)
        log(f'账号数量：{len(accounts)}')
        log('❌ 配置错误：' + error)
    except Exception:
        error = '执行器异常，已隐藏异常详情'
        log('❌ ' + error)
    failed = sum(r['failure'] > 0 for r in results)
    passed = len(results) - failed
    status = ('configuration-error' if error else 'partial-failure' if failed and passed else
              'failure' if failed else 'dry-run' if dry else 'success')
    exit_code = 1 if error or failed else 0
    body = (f'{TITLE}：{status}；账号总数 {len(accounts)}，'
            f'{"预演通过" if dry else "成功"} {passed}，失败 {failed}；'
            f'配置或执行器错误 {1 if error else 0}。')
    try:
        notification = notify_summary(body, dry)
    except Exception:
        notification = '不可用或失败'
    totals = {key: sum(r[key] for r in results) for key in counts()}
    finish = datetime.datetime.now().isoformat(timespec='seconds')
    elapsed = round(time.monotonic() - started, 3)
    log('----------------------------------------')
    log(body)
    log(f'子任务统计：总数 {totals["total"]}，成功 {totals["success"]}，已完成 {totals["alreadyComplete"]}，跳过 {totals["skipped"]}，失败 {totals["failure"]}')
    log(f'总耗时 {elapsed:.2f} 秒；完成时间：{finish}；通知状态：{notification}；最终状态：{status}')
    summary = {'task': TITLE, 'status': status, 'dryRun': dry, 'accountCount': len(accounts),
               'successfulAccounts': 0 if dry else passed, 'dryRunAccounts': passed if dry else 0,
               'failedAccounts': failed, 'configurationError': bool(error),
               'accounts': results, 'steps': totals, 'startTime': start_time, 'finishTime': finish,
               'elapsedSeconds': elapsed, 'notification': notification, 'exitCode': exit_code}
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
