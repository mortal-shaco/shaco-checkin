#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: GreatSQL论坛签到
# cron: 13 10 * * *
# 上游: redgreat/autosign / greatsql_checkin.py
# https://github.com/redgreat/autosign (MIT)
# 上游输入未附版权行；保留上游作者及许可归属。
# SPDX-License-Identifier: MIT
"""GreatSQL 论坛自动签到脚本，适用于青龙面板定时任务。

GREATSQL_ACCOUNTS 必填：每个非空行一个「登录账号|密码」，仅在首个 | 分割。
账号和密码来自本人在 https://greatsql.cn/ 注册的论坛账号；先在浏览器确认可登录。
兼容 GREATSQL_USER / GREATSQL_PWD：两变量逐行对应，也兼容原来的 # 分隔格式；
推荐迁移到合并变量，以支持密码中的 #。不能混合两套配置，账号数必须相等。
依赖（仅正式模式加载）：requests、ddddocr、Pillow，均来自公开 PyPI。
GREATSQL_DRY_RUN=1 完全离线，既不加载 OCR，也不发送任何通知。
PUSH_PLUS_TOKEN 为可选旧版通知参数，从 PushPlus 官网个人中心获取。
QINGLONG_NOTIFY=auto 默认仅通知 QINGLONG_NOTIFY_SCRIPTS 所选脚本；可用 1/0 强制开关。
通知选择支持目录路径、文件名、catalogId、通配符，以逗号/分号/空白分隔。
QINGLONG_NOTIFY_DIR 可指定青龙 notify.py/sendNotify.js 目录。
仅签到会改变积分和签到记录，不发帖、不评论、不修改资料、不保存凭据或验证码。
上游未声明调度；提供每日 08:17 的可调整调度，不启用上游已注释的随机延迟。
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
        _ql_notify_identities = ('29830e363680c655', 'scripts/greatsql_checkin.py', 'greatsql_checkin.py', 'greatsql_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import contextlib
import fnmatch
import html
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, parse_qs

TITLE = 'GreatSQL论坛签到'
CATALOG = '29830e363680c655'
BASE = 'https://greatsql.cn/'
LOGIN = BASE + 'member.php?mod=logging&action=login&referer='
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


def now():
    return datetime.now(timezone(timedelta(hours=8)))


def log(message):
    print(f'[{now():%H:%M:%S}] {message}', flush=True)


class TaskError(Exception):
    """仅允许固定、无凭据的错误消息。"""


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.inputs = {}
        self.actions = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name'):
            self.inputs[attrs['name']] = attrs.get('value', '')
        if tag == 'form' and attrs.get('action'):
            self.actions.append(html.unescape(attrs['action']))


def lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]


def accounts_from_env():
    combined = os.getenv('GREATSQL_ACCOUNTS', '')
    old_user, old_pwd = os.getenv('GREATSQL_USER', ''), os.getenv('GREATSQL_PWD', '')
    if combined.strip():
        if old_user.strip() or old_pwd.strip():
            raise TaskError('合并变量和旧版变量不能同时配置')
        result = []
        for line in lines(combined):
            if '|' not in line:
                result.append(None)
                continue
            username, password = line.split('|', 1)
            result.append((username.strip(), password) if username.strip() and password else None)
        return result
    if old_user.strip() or old_pwd.strip():
        # 原 # 格式仅在单行兼容；新配置始终使用换行分隔账号。
        users = lines(old_user) if '\n' in old_user else old_user.split('#')
        passwords = lines(old_pwd) if '\n' in old_pwd else old_pwd.split('#')
        if len(users) != len(passwords):
            raise TaskError('旧版账号与密码数量不一致，禁止截断处理')
        return [(u.strip(), p) if u.strip() and p else None for u, p in zip(users, passwords)]
    raise TaskError('缺少 GREATSQL_ACCOUNTS；请填写每行一个登录账号|密码')


def sign_result(text):
    plain = html.unescape(re.sub(r'<[^>]*>', ' ', text.replace('<![CDATA[', '').replace(']]>', '')))
    # 失败标志优先，绝不将通用“签到”按钮或失败页当作成功。
    if re.search(r'未登录|请先登录|签到失败|签到未成功|签到不成功|签到异常|无权|拒绝|错误|error|failed', plain, re.I):
        raise TaskError('签到响应报告失败或未登录')
    if re.search(r'已经签到|今日已签到|今天已签到|今日已经签到|今天已经签到|重复签到', plain):
        return 'alreadyComplete', '今日已签到'
    if re.search(r'签到成功|成功签到', plain):
        days = re.search(r'(?:连续签到|签到)\s*(\d+)\s*天', plain)
        return 'success', '签到成功' + (f'，连续 {int(days.group(1))} 天' if days else '')
    raise TaskError('签到响应缺少明确成功标志，未确认成功')


class GreatSQLClient:
    def __init__(self, username, password):
        # 延迟导入，离线预演无需安装业务依赖，也不会初始化模型。
        try:
            import requests
            import ddddocr
            from PIL import Image, ImageEnhance, ImageFilter
        except ImportError:
            raise TaskError('缺少运行依赖，请从公开 PyPI 安装 requests、ddddocr、Pillow') from None
        self.requests, self.ddddocr = requests, ddddocr
        self.Image, self.ImageEnhance, self.ImageFilter = Image, ImageEnhance, ImageFilter
        self.username, self.password = username, password
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 GreatSQL-checkin/1.0',
                                     'Accept-Language': 'zh-CN,zh;q=0.9'})
        self.models = []
        for config in ({'beta': True}, {'old': True}, {}, {'det': False}):
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.models.append(ddddocr.DdddOcr(show_ad=False, **config))
            except Exception:
                continue
        if not self.models:
            self.session.close()
            raise TaskError('OCR 模型初始化失败，请检查公开包版本及内置模型')

    def request(self, method, url, **kwargs):
        if os.getenv('GREATSQL_DRY_RUN', '').lower() in TRUE:
            raise TaskError('离线模式禁止网络请求')
        if not url.startswith(BASE) or urlparse(url).netloc != 'greatsql.cn':
            raise TaskError('拒绝非论坛地址')
        try:
            # 不将账号密码或会话经重定向传给其他主机。
            for _ in range(5):
                response = self.session.request(method, url, timeout=(10, 25),
                                                allow_redirects=False, **kwargs)
                if response.is_redirect:
                    location = urljoin(url, response.headers.get('Location', ''))
                    response.close()
                    if method != 'GET' or not location.startswith(BASE) or urlparse(location).netloc != 'greatsql.cn':
                        raise TaskError('拒绝异常重定向')
                    url = location
                    kwargs.pop('params', None)
                    continue
                response.raise_for_status()
                if len(response.content) > 4 * 1024 * 1024:
                    raise TaskError('论坛响应过大')
                return response
            raise TaskError('论坛重定向次数过多')
        except self.requests.RequestException:
            raise TaskError('论坛请求失败或超时，请检查服务和网络') from None

    def captcha(self, page):
        match = re.search(r'seccode_([A-Za-z0-9]+)', page)
        if not match:
            raise TaskError('登录页缺少验证码标识，接口需复核')
        code_hash = match.group(1)
        headers = {'X-Requested-With': 'XMLHttpRequest', 'Referer': LOGIN}
        update = self.request('GET', BASE + 'misc.php', params={
            'mod': 'seccode', 'action': 'update', 'idhash': code_hash}, headers=headers).text
        match = re.search(r'misc\.php\?mod=seccode&update=(\d+)&idhash=' + re.escape(code_hash), html.unescape(update))
        if not match:
            raise TaskError('验证码图片地址缺失')
        image = self.request('GET', BASE + 'misc.php', params={
            'mod': 'seccode', 'update': match.group(1), 'idhash': code_hash}, headers=headers)
        if 'image/' not in image.headers.get('Content-Type', '').lower():
            raise TaskError('验证码响应不是图片')
        images = [image.content]
        try:
            with self.Image.open(io.BytesIO(image.content)) as original:
                for transform in (
                    lambda x: x.copy(), lambda x: x.convert('L'), lambda x: x.convert('RGB'),
                    lambda x: self.ImageEnhance.Contrast(x.convert('RGB')).enhance(2),
                    lambda x: self.ImageEnhance.Contrast(x.convert('L')).enhance(3),
                    lambda x: x.convert('L').filter(self.ImageFilter.MedianFilter()),
                ):
                    data = io.BytesIO()
                    transform(original).save(data, format='PNG')
                    images.append(data.getvalue())
        except Exception:
            log('⚠️ 图片预处理失败，继续原图 OCR')
        results = []
        for data in images:
            for model in self.models:
                try:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        value = model.classification(data).strip()
                    if re.fullmatch(r'[A-Za-z0-9]{4}', value):
                        results.append(value)
                except Exception:
                    continue
        if not results:
            raise TaskError('验证码识别失败')
        log('验证码图片及 OCR 处理完成（不输出验证码）')
        return code_hash, Counter(results).most_common(1)[0][0]

    def security_question(self, text, inputs):
        qhash = inputs.get('secqaahash')
        match = re.search(r'secqaa_([A-Za-z0-9]+)', text)
        if not qhash and match:
            qhash = match.group(1)
        if not qhash:
            return {}
        text = html.unescape(self.request('GET', BASE + 'misc.php', params={
            'mod': 'secqaa', 'action': 'update', 'idhash': qhash},
            headers={'Referer': LOGIN, 'X-Requested-With': 'XMLHttpRequest'}).text)
        answer = None
        for pattern, value in (
            (r'冗余索引.*?sys\.schema_redundant_indexes', 'sys.schema_redundant_indexes'),
            (r'DML操作统计.*?sys\.schema_table_statistics', 'sys.schema_table_statistics'),
            (r'默认字符集.*?utf8mb4', 'utf8mb4'),
        ):
            if re.search(pattern, text, re.S):
                answer = value
                break
        if not answer:
            hint = re.search(r'提示[：:]\s*([^<）)\r\n]+)', text)
            schema = re.search(r'\bsys\.(\w+)', text)
            if hint:
                answer = hint.group(1).strip()
            elif schema:
                answer = 'sys.' + schema.group(1)
        if not answer or len(answer) > 200:
            raise TaskError('安全问答无法识别，停止猜测，请先人工检查论坛登录')
        return {'secqaahash': qhash, 'secanswer': answer}

    def identity(self):
        text = self.request('GET', BASE + 'home.php?mod=space').text
        if not re.search(r'(?:action=logout|mod=logging[^\s<>]*logout)', html.unescape(text)):
            raise TaskError('用户中心未确认有效登录状态')
        # Discuz 登录导航中的官方非敏感用户名；手机或输入凭据始终不回显。
        match = re.search(r'class=[\"\'][^\"\']*\bvwmy\b[^\"\']*[\"\'][^>]*>\s*(?:<a\b[^>]*>)?([^<]+)', text)
        if match:
            name = html.unescape(match.group(1)).strip()
            if name and name != self.password and not re.search(r'\d{7,}', name) and not any(c in name for c in '\r\n'):
                log('官方账号名称：' + name)
        uid = re.search(r'\bdiscuz_uid\s*=\s*[\"\']?(\d+)', text)
        if uid and uid.group(1) != '0':
            log('官方公开 UID：' + uid.group(1))

    def login(self):
        for attempt in range(3):
            page = self.request('GET', LOGIN).text
            form = Page(page)
            if not form.inputs.get('formhash'):
                raise TaskError('登录表单缺少 formhash')
            code_hash, code = self.captcha(page)
            data = {'formhash': form.inputs['formhash'], 'referer': BASE,
                    'fastloginfield': 'username', 'logintype': 'l0', 'cookietime': '2592000',
                    'phone': self.username, 'password': self.password,
                    'seccodehash': code_hash, 'seccodemodid': 'member::logging', 'seccodeverify': code}
            data.update(self.security_question(page, form.inputs))
            # 优先使用页面中的 loginhash；无该字段时保持上游已知接口参数。
            loginhash = 'LyTqt'
            for action in form.actions:
                parsed = parse_qs(urlparse(action).query)
                if 'loginhash' in parsed:
                    loginhash = parsed['loginhash'][0]
                    break
            text = self.request('POST', BASE + 'member.php', params={
                'mod': 'logging', 'action': 'login', 'loginsubmit': 'yes',
                'loginhash': loginhash, 'inajax': '1'}, data=data,
                headers={'Referer': LOGIN, 'Origin': BASE.rstrip('/'),
                         'X-Requested-With': 'XMLHttpRequest'}).text
            if re.search(r'密码错误次数过多|分钟后重新登录|用户名或密码错误|密码错误|问答错误|验证问答错误', text):
                raise TaskError('登录被拒绝：请检查凭据、安全问答或账号锁定状态')
            if re.search(r'验证码错误|验证码填写错误', text):
                log(f'⚠️ 验证码未通过，第 {attempt + 1}/3 次')
                continue
            # 无论登录响应文本如何，都通过独立用户中心确认会话。
            self.identity()
            log('✅ 用户中心已确认登录')
            return
        raise TaskError('验证码连续验证失败，停止登录')

    def checkin(self):
        response = self.request('GET', BASE + 'plugin.php', params={
            'id': 'smx_sign:do', 'inajax': '1', 'ajaxtarget': 'do_sign'}, headers={
            'Accept': '*/*', 'X-Requested-With': 'XMLHttpRequest',
            'Referer': BASE + 'home.php?mod=spacecp&ac=credit&op=base'})
        return sign_result(response.text)


def notification_selected():
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', '').strip())
    names = (CATALOG, 'greatsql_checkin.py', 'candidate.py', 'scripts/greatsql_checkin.py',
             'output/candidate.py', Path(__file__).name)
    return any(pattern and any(fnmatch.fnmatchcase(name, pattern) for name in names) for pattern in selectors)


def notify_summary(body, dry):
    # dry-run 不导入宿主通知脚本、不启动子进程，避免通知模块暗中联网。
    if dry:
        log('⏭️ 通知：离线预演，仅生成脱敏摘要，未调用任何通知通道')
        return '离线预演'
    if os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower() in FALSE:
        return '全局关闭'
    states = []
    if notification_selected():
        dirs = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
        helper = next((Path(d) / 'notify.py' for d in dirs if d and (Path(d) / 'notify.py').is_file()), None)
        js = next((Path(d) / 'sendNotify.js' for d in dirs if d and (Path(d) / 'sendNotify.js').is_file()), None)
        code = ('import importlib.util,sys; p=sys.argv[1]; '
                's=importlib.util.spec_from_file_location("notify",p); '
                'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                'm.send(sys.argv[2],sys.argv[3])')
        if helper:
            command = [sys.executable, '-c', code, str(helper), TITLE, body]
        elif js:
            command = ['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(js), TITLE, body]
        else:
            command = [sys.executable, '-c', 'import notify,sys; notify.send(sys.argv[1],sys.argv[2])', TITLE, body]
        try:
            completed = subprocess.run(command, capture_output=True, timeout=30, check=False)
            states.append('青龙通知已调用' if completed.returncode == 0 else '青龙通知不可用或失败')
        except Exception:
            states.append('青龙通知不可用或超时')
    else:
        states.append('青龙通知未被列表选中')
    token = os.getenv('PUSH_PLUS_TOKEN', '').strip()
    if token:
        try:
            import requests
            with requests.Session() as session:
                session.trust_env = False
                response = session.post('https://www.pushplus.plus/send', json={
                    'token': token, 'title': TITLE, 'content': body}, timeout=(10, 15), allow_redirects=False)
                ok = response.status_code == 200 and response.json().get('code') == 200
                states.append('PushPlus通知成功' if ok else 'PushPlus通知失败')
        except Exception:
            states.append('PushPlus通知失败')
    return '；'.join(states)


def main():
    started = time.monotonic()
    dry = os.getenv('GREATSQL_DRY_RUN', '').strip().lower() in TRUE
    log('========== GreatSQL论坛签到 ==========')
    log(f'开始时间：{now():%Y-%m-%d %H:%M:%S %z}；模式：' + ('离线预演' if dry else '正式执行'))
    results, config_error = [], False
    try:
        accounts = accounts_from_env()
    except TaskError as exc:
        log('❌ 配置错误：' + str(exc))
        accounts, config_error = [], True
    log(f'账号数量：{len(accounts)}')
    for index, account in enumerate(accounts, 1):
        begin = time.monotonic()
        stats = dict(total=2, success=0, alreadyComplete=0, skipped=0, failure=0)
        client = None
        log(f'--- 账号 {index} ---')
        stage = time.monotonic()
        try:
            if account is None:
                raise TaskError('账号行格式错误，应为登录账号|密码，且两字段非空')
            log('阶段 1/2：登录与安全验证')
            if dry:
                log('⏭️ 已验证账号格式；模拟验证码、安全问答及登录，不加载依赖、不联网')
                stats['skipped'] += 1
            else:
                client = GreatSQLClient(*account)
                client.login()
                stats['success'] += 1
            log(f'阶段 1/2 耗时 {time.monotonic() - stage:.2f} 秒')
            stage = time.monotonic()
            log('阶段 2/2：每日签到')
            if dry:
                log('⏭️ DRY_RUN_OK：模拟签到，未修改论坛状态')
                stats['skipped'] += 1
                state = 'dry-run'
            else:
                state, message = client.checkin()
                stats[state] += 1
                log(('☑️ ' if state == 'alreadyComplete' else '✅ ') + message)
            log(f'阶段 2/2 耗时 {time.monotonic() - stage:.2f} 秒')
        except TaskError as exc:
            state = 'failure'
            log('❌ ' + str(exc))
        except Exception:
            state = 'failure'
            log('❌ 运行异常，已隐藏异常详情以防泄漏凭据')
        finally:
            if client is not None:
                client.session.close()
        if state == 'failure':
            stats['failure'] = 1
            stats['skipped'] = stats['total'] - stats['success'] - stats['alreadyComplete'] - 1
            log(f'失败阶段耗时 {time.monotonic() - stage:.2f} 秒；后续阶段已跳过')
        elapsed = round(time.monotonic() - begin, 2)
        results.append(dict(account=index, status=state, tasks=stats, seconds=elapsed))
        log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failure"]}，耗时 {elapsed:.2f} 秒')
    failed = sum(item['status'] == 'failure' for item in results)
    good = len(results) - failed
    status = ('configuration-error' if config_error else 'partial-failure' if failed and good else
              'failure' if failed else 'dry-run' if dry else 'success')
    exit_code = 1 if config_error or failed else 0
    body = f'状态：{status}；账号总数 {len(results)}，成功 {0 if dry else good}，预演 {good if dry else 0}，失败 {failed}；配置错误 {int(config_error)}。'
    log('----------------------------------------')
    log(body)
    notification = notify_summary(body, dry)
    totals = {key: sum(r['tasks'][key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    log('子任务统计：' + '，'.join(f'{key}={value}' for key, value in totals.items()))
    log('通知状态：' + notification)
    elapsed = round(time.monotonic() - started, 2)
    log(f'完成时间：{now():%Y-%m-%d %H:%M:%S %z}；总耗时 {elapsed:.2f} 秒；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(dict(task=TITLE, status=status, mode='dry-run' if dry else 'live',
          accounts=len(results), success=0 if dry else good, dryRun=good if dry else 0,
          failure=failed, configurationError=config_error, results=results, tasks=totals,
          notification=notification, seconds=elapsed, exitCode=exit_code), ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
