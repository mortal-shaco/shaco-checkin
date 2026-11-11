#!/usr/bin/env python3
# name: 昆明医科大学健康登记
# cron: 49 10 * * *
# 上游未声明 cron，维护版建议每天北京时间 08:00 检查。
# 来源: 2657753129/Epidemic main.py
# 上游提交: 17829c1563f57560b16ef79a7e683e7ded14e513
# 许可: MIT（任务提供的有效许可）。原始输入没有单独的版权或许可正文。
"""独立维护版。默认只检查，真实申报须显式选择 submit 并提供当天完整表单。
EPIDEMIC_ACCOUNTS 每个非空行是 学号|密码，仅在第一个 | 处分割。
EPIDEMIC_REPORTS 是按账号非空行顺序排列的 JSON 数组，每项为
{"date":"当天北京时间 YYYY-MM-DD", "form":{浏览器实际提交的完整键值表单}}。
只使用本人当天核实的真实数据。不得复用旧健康答案、他人表单或旧日期。
HTTPS 不可用、字段缺失、接口变化或无法确认当日登记时均失败退出。
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
        _ql_notify_identities = ('eddc6997bb5dba67', 'scripts/task_eddc6997.py', 'task_eddc6997.py', 'task_eddc6997')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime as dt
import fnmatch
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from urllib import error, parse, request

TITLE = '昆明医科大学健康登记'
CATALOG_ID = 'eddc6997bb5dba67'
BASE = 'https://xg.kmmu.edu.cn/SPCP/Web/'
REPORT = BASE + 'Report/Index'
ZONE = dt.timezone(dt.timedelta(hours=8))
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
IDENTITY_FIELDS = ('StudentId', 'Name', 'Sex', 'SpeType', 'CollegeNo', 'SpeGrade',
                   'SpecialtyName', 'ClassName', 'MoveTel', 'IdCard')
FORM_FIELDS = set(IDENTITY_FIELDS) | {
    'Province', 'City', 'County', 'ComeWhere', 'FaProvince', 'FaCity', 'FaCounty',
    'FaComeWhere', 'ProvinceName', 'CityName', 'CountyName', 'FaProvinceName',
    'FaCityName', 'FaCountyName', 'radio_1', 'radio_2', 'radio_3', 'radio_4',
    'radio_5', 'radio_6', 'text_1', 'Other', 'GetAreaUrl', 'radioCount',
    'checkboxCount', 'blackCount', 'PZData', 'ReSubmiteFlag',
}


class TaskError(Exception):
    pass


def now():
    return dt.datetime.now(ZONE)


def log(message):
    print(f'[{now():%H:%M:%S}] {message}', flush=True)


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.inputs = {}
        self.scripts = []
        self.in_script = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input':
            for key in ('id', 'name'):
                if attrs.get(key):
                    self.inputs[attrs[key]] = attrs.get('value', '')
        if tag == 'script':
            self.in_script = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.scripts.append(data)

    def says(self, message):
        return any(message in script for script in self.scripts)

    def token(self):
        value = self.inputs.get('ReSubmiteFlag', '')
        if not value:
            raise TaskError('页面缺少防重复提交字段，接口待核验')
        return value


class SafeRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = parse.urlsplit(newurl)
        if (target.scheme != 'https' or target.netloc != 'xg.kmmu.edu.cn'
                or not target.path.startswith('/SPCP/Web/')):
            raise TaskError('拒绝跨站或降级跳转')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Service:
    def __init__(self):
        self.opener = request.build_opener(
            SafeRedirect(), request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def page(self, url, form=None):
        data = None if form is None else parse.urlencode(form).encode('utf-8')
        req = request.Request(url, data=data, headers={
            'User-Agent': os.environ.get('EPIDEMIC_USER_AGENT', 'Mozilla/5.0'),
            'Accept': 'text/html,application/xhtml+xml',
        })
        try:
            with self.opener.open(req, timeout=20) as response:
                if response.status != 200:
                    raise TaskError('学校接口未返回 HTTP 200')
                body = response.read(1024 * 1024 + 1)
                if len(body) > 1024 * 1024:
                    raise TaskError('学校响应超过大小限制')
                encoding = response.headers.get_content_charset() or 'utf-8'
                return Page(body.decode(encoding))
        except (error.URLError, TimeoutError, OSError, UnicodeError, LookupError):
            raise TaskError('学校 HTTPS 请求失败或响应无法解析，请人工检查服务') from None


def checked_report(record):
    if not isinstance(record, dict) or record.get('date') != now().date().isoformat():
        raise TaskError('申报数据必须明确标记为当天北京时间日期')
    form = record.get('form')
    if not isinstance(form, dict) or not FORM_FIELDS.issubset(form):
        raise TaskError('申报表单不完整，请从本人当天浏览器请求获取完整表单')
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in form.items()):
        raise TaskError('申报表单所有键和值必须为字符串')
    if any(not form[f'radio_{i}'] for i in range(1, 7)):
        raise TaskError('六项健康答案必须显式提供')
    try:
        answers = json.loads(form['PZData'])
    except (ValueError, TypeError):
        raise TaskError('PZData 必须为本人真实表单的 JSON 数组') from None
    if not isinstance(answers, list) or len(answers) != 6:
        raise TaskError('PZData 必须包含完整六项答案')
    if any(not isinstance(answer, dict) or not all(
            isinstance(answer.get(key), str) and answer[key]
            for key in ('OptionName', 'SelectId', 'TitleId', 'OptionType'))
            for answer in answers):
        raise TaskError('PZData 答案字段不完整')
    if sorted(a['SelectId'] for a in answers) != sorted(form[f'radio_{i}'] for i in range(1, 7)):
        raise TaskError('健康答案与 PZData 不一致')
    if form['radioCount'] != '6' or form['GetAreaUrl'] != '/SPCP/Web/Report/GetArea':
        raise TaskError('表单结构已变化，需要重新核验接口')
    return dict(form)


def run_account(username, password, action, record, dry, secrets, stats):
    stage = time.monotonic()
    log('阶段 1 · 登录与表单校验')
    if dry:
        if action == 'submit':
            checked_report(record)
        log(f'阶段 1 完成 · 参数有效，耗时 {time.monotonic() - stage:.2f} 秒')
        log('阶段 2 · 断网预演，跳过学校请求和申报提交')
        stats['skipped'] = 1
        return 'dry-run'
    service = Service()
    login = service.page(BASE)
    logged_in = service.page(BASE, {
        'ReSubmiteFlag': login.token(), 'txtUid': username, 'txtPwd': password,
        'StuLoginMode': '1', 'codeInput': '',
    })
    if logged_in.says('用户名或者密码错误'):
        raise TaskError('学校拒绝登录，请核对账号密码')
    page = service.page(REPORT)
    log(f'阶段 1 完成 · 已取得登记页，耗时 {time.monotonic() - stage:.2f} 秒')
    stage = time.monotonic()
    log('阶段 2 · 核对当日登记状态')
    # 只显示官方姓名，不输出学号、手机号、设备标识或完整页面。
    identity = page.inputs.get('Name', '')
    if identity:
        identity = ''.join(c for c in identity if c.isprintable())
        for secret in secrets:
            if secret:
                identity = identity.replace(secret, '[已隐藏]')
        identity = re.sub(r'(?<!\d)1\d{10}(?!\d)', '[手机号已隐藏]', identity)
        log(f'官方姓名 · {identity}')
    if page.says('当前采集日期已登记'):
        stats['alreadyComplete'] = 1
        log(f'☑️ 当前采集日期已登记，耗时 {time.monotonic() - stage:.2f} 秒')
        return 'already-complete'
    if page.says('只能1点至18点可以填报'):
        raise TaskError('当前不在学校填报窗口内，无法核实完成状态')
    if not page.inputs.get('StudentId') or 'txtPwd' in page.inputs:
        raise TaskError('未取得有效账号申报表单，登录或接口状态待核验')
    if action == 'check':
        raise TaskError('当天尚未登记，请人工填报或提供真实表单并显式选择 submit')
    log(f'阶段 2 完成 · 当天待登记，耗时 {time.monotonic() - stage:.2f} 秒')
    stage = time.monotonic()
    log('阶段 3 · 提交已明确提供的当天真实表单')
    form = checked_report(record)
    for field in IDENTITY_FIELDS:
        if field not in page.inputs or form[field] != page.inputs[field]:
            raise TaskError('申报身份资料与当前账号页面不一致，停止提交')
    form['ReSubmiteFlag'] = page.token()
    service.page(REPORT, form)
    # 提交后的独立读取必须出现上游明确的当日已登记标记。
    verified = service.page(REPORT)
    if not verified.says('当前采集日期已登记'):
        raise TaskError('提交后未确认当日已登记，请人工核验，禁止盲目重试')
    stats['success'] = 1
    log(f'✅ 提交后已核实当日登记，耗时 {time.monotonic() - stage:.2f} 秒')
    return 'success'


def notify(summary, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return '已关闭'
    if switch not in TRUE | {'auto'}:
        return '通知开关无效，未发送'
    selection = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    if selection is not None:
        selectors = re.split(r'[,;\s]+', selection.strip())
        names = [CATALOG_ID, Path(__file__).name, str(Path(__file__)),
                 'output/' + Path(__file__).name]
        if not any(fnmatch.fnmatch(name, pattern) for pattern in selectors if pattern for name in names):
            return '未被通知选择器选中'
    if dry:
        return '断网预演已生成通知摘要，投递已跳过'
    body = (f"状态 {summary['status']}，账号总数 {summary['accounts']}，"
            f"成功 {summary['succeeded']}，失败 {summary['failed']}，"
            f"配置错误 {summary['configurationErrors']}")
    # 子进程隔离通知库输出和异常，超时或投递失败均保留业务退出码。
    worker = '''import importlib, importlib.util, os, sys
from pathlib import Path
try:
    module = importlib.import_module('notify')
except ImportError:
    paths = []
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    module = None
    for path in paths:
        if path.is_file():
            spec = importlib.util.spec_from_file_location('ql_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            break
    if module is None:
        sys.exit(2)
module.send(sys.argv[1], sys.argv[2])
'''
    try:
        result = subprocess.run([sys.executable, '-c', worker, TITLE, body],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=30, check=False)
        return '已调用青龙通知' if result.returncode == 0 else '青龙通知不可用或失败'
    except (OSError, subprocess.TimeoutExpired):
        return '青龙通知不可用或超时'


def main():
    started = time.monotonic()
    dry_value = os.environ.get('EPIDEMIC_DRY_RUN', '0').strip().lower()
    dry = dry_value in TRUE
    action = os.environ.get('EPIDEMIC_ACTION', 'check').strip().lower()
    lines = [line.strip() for line in os.environ.get('EPIDEMIC_ACCOUNTS', '').splitlines() if line.strip()]
    log(f'========== {TITLE} ==========')
    log(f'开始时间 {now():%Y-%m-%d %H:%M:%S %z} · 模式 {"断网预演" if dry else "实际执行"} / {action if action in {"check", "submit"} else "配置无效"}')
    log(f'账号数量 {len(lines)}')
    summary = {'accounts': len(lines), 'succeeded': 0, 'failed': 0,
               'configurationErrors': 0, 'dryRun': dry, 'results': [],
               'tasks': {'total': len(lines), 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}}
    configuration_error = None
    records = []
    if dry_value not in TRUE | FALSE:
        configuration_error = 'EPIDEMIC_DRY_RUN 取值无效'
    if action not in {'check', 'submit'}:
        configuration_error = 'EPIDEMIC_ACTION 只接受 check 或 submit'
    if not lines:
        configuration_error = '缺少 EPIDEMIC_ACCOUNTS，每个非空行填写学号|密码'
    if action == 'submit':
        try:
            records = json.loads(os.environ.get('EPIDEMIC_REPORTS', ''))
            if not isinstance(records, list) or len(records) != len(lines):
                raise ValueError
        except ValueError:
            configuration_error = 'EPIDEMIC_REPORTS 必须是与账号行数相同的 JSON 数组'
    secrets = []
    for line in lines:
        secrets.extend(line.split('|', 1))
    if configuration_error:
        log(f'❌ 配置错误 · {configuration_error}')
        summary['configurationErrors'] = 1
        summary['failed'] = len(lines)
        summary['tasks']['failed'] = len(lines)
    else:
        for index, line in enumerate(lines, 1):
            account_started = time.monotonic()
            stats = {'total': 1, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
            log(f'---------- 账号 {index}/{len(lines)} ----------')
            try:
                if '|' not in line:
                    raise TaskError('账号格式错误，应为学号|密码')
                username, password = line.split('|', 1)
                if not username.strip() or not password:
                    raise TaskError('账号和密码均须填写')
                result = run_account(username, password, action,
                                     records[index - 1] if records else None,
                                     dry, secrets, stats)
                summary['succeeded'] += 1
            except TaskError as exc:
                result = 'failure'
                stats['failed'] = 1
                summary['failed'] += 1
                log(f'❌ {exc}')
            except Exception:
                result = 'failure'
                stats['failed'] = 1
                summary['failed'] += 1
                log('❌ 执行异常，已隐藏异常内容，请人工核验接口')
            summary['results'].append({'account': index, 'status': result, 'tasks': stats})
            for key in ('success', 'alreadyComplete', 'skipped', 'failed'):
                summary['tasks'][key] += stats[key]
            log(f'账号 {index} 统计 · 总任务 1，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {time.monotonic() - account_started:.2f} 秒')
    code = 1 if summary['failed'] or summary['configurationErrors'] else 0
    summary['status'] = ('configuration-error' if summary['configurationErrors'] else
                         'partial-failure' if summary['failed'] and summary['succeeded'] else
                         'failure' if summary['failed'] else 'dry-run' if dry else 'success')
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['finishedAt'] = now().isoformat()
    log('----------------------------------------')
    log(f'任务统计 · 账号 {summary["accounts"]}，成功 {summary["succeeded"]}，失败 {summary["failed"]}，配置错误 {summary["configurationErrors"]}')
    log(f'子任务统计 · {json.dumps(summary["tasks"], ensure_ascii=False)}')
    log(f'通知状态 · {summary["notification"]}')
    log(f'完成时间 {summary["finishedAt"]} · 总耗时 {summary["elapsedSeconds"]} 秒 · 最终状态 {summary["status"]}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
