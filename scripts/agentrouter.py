#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: AgentRouter签到
# cron: 17 1 * * *
"""AgentRouter 登录签到；Author: Assistant; Date: 2026-09-10.
维护来源：Cat-zaizai/ZaiZaiCat-Checkin script/agentrouter/main.py、api.py。
原作者和许可声明保留。有效许可证：MIT。

AGENTROUTER_ACCOUNTS 每个非空行一个 user_session 值或 JSON 账号对象。
JSON 支持 github_session、account_name、base_url、user_id、proxy、verify。
也可显式指定 AGENTROUTER_CONFIG 或 --config 读取原 agentrouter.accounts 格式。
GitHub 浏览器登录后在开发者工具 Application/Cookies/github.com 获取
user_session 的值。先在浏览器手动完成 AgentRouter GitHub 授权。
首次授权自动提交默认关闭，可通过 AGENTROUTER_ALLOW_AUTHORIZE=1 显式启用。
代理优先级：账号 proxy、AGENTROUTER_PROXY、HTTPS_PROXY/HTTP_PROXY。
证书校验始终开启，verify 只能为 true 或 CA 文件路径。
AGENTROUTER_DRY_RUN=1 或 --dry-run 完全离线，通知仅预演不发送。

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
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import ssl
import tempfile
import sys
import time
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

BASE = 'https://ps.air-outer.com'
FALLBACK_CLIENT_ID = 'Ov23lidtiR4LeVZvVRNL'
DISABLED = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


class TaskParser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError('命令行参数无效')


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def enabled(name, default='0'):
    return os.getenv(name, default).lower() not in DISABLED | {''}


def secure_url(value, proxy=False):
    p = urlsplit(value)
    if p.scheme not in ({'http', 'https'} if proxy else {'https'}) or not p.hostname:
        raise TaskError('地址格式错误，站点必须使用 HTTPS')
    if not proxy and (p.username or p.password or p.query or p.fragment or p.path not in ('', '/')):
        raise TaskError('站点地址必须是无凭据、无参数的 HTTPS 根地址')
    return value.rstrip('/')


def account_config(raw):
    if isinstance(raw, str):
        raw = json.loads(raw) if raw.lstrip().startswith('{') else {'github_session': raw}
    if not isinstance(raw, dict):
        raise TaskError('账号必须为登录态值或 JSON 对象')
    credential = raw.get('github_session')
    if not isinstance(credential, str) or not credential.strip() or re.search(r'[\s;\x00-\x1f]', credential):
        raise TaskError('缺少或无效的 github_session，请填写单独 Cookie 值')
    raw = dict(raw, github_session=credential.strip())
    raw['base_url'] = secure_url(raw.get('base_url') or os.getenv('AGENTROUTER_BASE_URL', BASE))
    proxy = raw.get('proxy') or os.getenv('AGENTROUTER_PROXY', '')
    # 显式支持文档声明的标准代理变量，requests 同时支持 NO_PROXY。
    for name in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
        if os.getenv(name):
            secure_url(os.environ[name], proxy=True)
    if proxy:
        secure_url(proxy, proxy=True)
    raw['proxy'] = proxy
    verify = raw.get('verify')
    if verify is False or (verify is not None and verify is not True and not isinstance(verify, str)):
        raise TaskError('禁止关闭 TLS 校验')
    ca = verify if isinstance(verify, str) else os.getenv('AGENTROUTER_CA_BUNDLE', '')
    if ca and not Path(ca).is_file():
        raise TaskError('CA 证书文件不存在')
    raw['verify'] = ca or True
    return raw


class OAuthForms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            self.current = {'action': a.get('action', ''), 'method': a.get('method', '').lower(), 'fields': {}}
        elif tag == 'input' and self.current is not None and a.get('type') == 'hidden' and a.get('name'):
            self.current['fields'][a['name']] = a.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form' and self.current is not None:
            self.forms.append(self.current)
            self.current = None


class API:
    def __init__(self, account):
        import requests
        self.account = account
        self.ca_path = None
        # 保留上游 Windows 系统根证书兼容能力，始终验证 TLS。
        if account['verify'] is True and hasattr(ssl, 'enum_certificates'):
            try:
                import certifi
                pem = Path(certifi.where()).read_text(encoding='ascii')
                for der, encoding, trust in ssl.enum_certificates('ROOT'):
                    if encoding == 'x509_asn' and (trust is True or '1.3.6.1.5.5.7.3.1' in trust):
                        pem += '\n' + ssl.DER_cert_to_PEM_cert(der)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                    f.write(pem)
                    self.ca_path = f.name
            except Exception:
                log('⚠️ 系统证书合并不可用，沿用标准受信任 CA')
        self.site = requests.Session()
        self.github = requests.Session()
        for s in (self.site, self.github):
            s.verify = self.ca_path or account['verify']
            s.headers.update({'User-Agent': 'Mozilla/5.0 AgentRouter-maintained', 'Accept': 'application/json, text/html'})
            if account['proxy']:
                s.proxies.update({'http': account['proxy'], 'https': account['proxy']})
        for name, value in {'user_session': account['github_session'], 'logged_in': 'yes',
                            '__Host-user_session_same_site': account['github_session']}.items():
            self.github.cookies.set(name, value, domain='github.com', path='/')
        if account.get('user_id'):
            self.site.headers['new-api-user'] = str(account['user_id'])
        self.unit = 500000

    def close(self):
        self.site.close()
        self.github.close()
        if self.ca_path:
            Path(self.ca_path).unlink(missing_ok=True)

    def request(self, session, method, url, **kw):
        try:
            r = session.request(method, url, timeout=30, allow_redirects=False, **kw)
        except Exception:
            raise TaskError('网络或 TLS 请求失败，请检查代理、证书及网络') from None
        if r.status_code not in (200, 301, 302, 303):
            raise TaskError(f'HTTP 请求失败，状态码 {r.status_code}')
        return r

    def business(self, path, **kw):
        r = self.request(self.site, 'GET', self.account['base_url'] + path, **kw)
        try:
            body = r.json()
        except ValueError:
            raise TaskError('接口未返回有效 JSON') from None
        if r.status_code != 200 or not isinstance(body, dict) or body.get('success') is not True:
            raise TaskError('接口未明确确认业务成功')
        return body.get('data')

    def code(self, r, state):
        if r.status_code not in (301, 302, 303):
            return None
        location = urljoin('https://github.com/', r.headers.get('Location', ''))
        p = urlsplit(location)
        # 仅从已知回调取 code，从不访问回调；不接受任意域或登录跳转。
        if p.scheme != 'https' or p.hostname not in {'agentrouter.org', urlsplit(self.account['base_url']).hostname}:
            raise TaskError('GitHub 登录态失效或 OAuth 回调域名不符合预期')
        q = parse_qs(p.query)
        if q.get('state') != [state] or len(q.get('code', [])) != 1:
            raise TaskError('OAuth 回调缺少授权码或 state 不匹配')
        return q['code'][0]

    def login(self):
        client = FALLBACK_CLIENT_ID
        try:
            status = self.business('/api/status')
            if isinstance(status, dict):
                client = status.get('github_client_id') or client
                unit = status.get('quota_per_unit')
                if isinstance(unit, (float, int)) and not isinstance(unit, bool) and math.isfinite(unit) and unit > 0:
                    self.unit = unit
            log('公开配置读取完成')
        except TaskError:
            log('⚠️ 公开配置读取失败，使用原客户端与额度比例兜底')
        state = self.business('/api/oauth/state')
        if not isinstance(state, str) or not state:
            raise TaskError('接口缺少有效 OAuth state')
        url = 'https://github.com/login/oauth/authorize'
        r = self.request(self.github, 'GET', url, params={'client_id': client, 'state': state, 'scope': 'user:email'})
        code = self.code(r, state)
        if not code:
            if not enabled('AGENTROUTER_ALLOW_AUTHORIZE'):
                raise TaskError('需要首次授权或额外验证，请在浏览器手动授权；自动同意默认关闭')
            parser = OAuthForms()
            parser.feed(r.text)
            forms = [f for f in parser.forms if f['method'] == 'post' and
                     urljoin(url, f['action']) == url and f['fields'].get('authenticity_token')]
            if len(forms) != 1:
                raise TaskError('未找到可信 GitHub OAuth 授权表单，请手动授权')
            fields = forms[0]['fields']
            fields['authorize'] = '1'
            r = self.request(self.github, 'POST', url, data=fields, headers={'Referer': r.url})
            code = self.code(r, state)
        if not code:
            raise TaskError('未获取有效 OAuth 授权码')
        user = self.business('/api/oauth/github', params={'code': code, 'state': state, 'mode': 'login'})
        if not isinstance(user, dict):
            raise TaskError('登录响应缺少用户信息')
        for key in ('id', 'user_id', 'uid'):
            if user.get(key):
                self.site.headers['new-api-user'] = str(user[key])
                break
        return user


def identity(user, credential):
    for key in ('display_name', 'username', 'id', 'user_id', 'uid'):
        if user.get(key) is not None and str(user[key]):
            value = str(user[key])
            if credential in value or re.search(r'(?i)cookie|token|session', value) or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value):
                continue
            return value.replace('\n', ' ').replace('\r', ' ')
    return ''


def notify(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    if dry:
        return '离线预演，未发送'
    # 独立子进程限制通知耗时并抑制通知组件输出，异常不改变业务退出码。
    code = '''import importlib.util,sys
try:
 import notify
except ImportError:
 spec=importlib.util.spec_from_file_location("notify",sys.argv[1])
 notify=importlib.util.module_from_spec(spec);spec.loader.exec_module(notify)
notify.send("AgentRouter签到",sys.stdin.read())
'''
    roots = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    path = next((str(Path(p) / 'notify.py') for p in roots if p and (Path(p) / 'notify.py').is_file()), '')
    try:
        p = subprocess.run([sys.executable, '-c', code, path], input=body, text=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        if p.returncode == 0:
            return '已发送'
    except Exception:
        pass
    js = next((str(Path(p) / 'sendNotify.js') for p in roots if p and (Path(p) / 'sendNotify.js').is_file()), '')
    if js:
        try:
            code_js = 'const fs=require("fs"); Promise.resolve(require(process.argv[1]).sendNotify("AgentRouter签到",fs.readFileSync(0,"utf8"))).catch(()=>process.exit(1));'
            p = subprocess.run(['node', '-e', code_js, js], input=body, text=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if p.returncode == 0:
                return '已发送'
        except Exception:
            pass
    return '不可用或发送失败（业务退出码保留）'


def main():
    start = time.monotonic()
    dry = enabled('AGENTROUTER_DRY_RUN') or '--dry-run' in sys.argv
    log('========== AgentRouter签到 ==========')
    log(f'开始时间：{time.strftime("%Y-%m-%d %H:%M:%S")}；模式：{"离线预演" if dry else "正式执行"}')
    results = []
    config_error = False
    raw_accounts = []
    try:
        parser = TaskParser(description='AgentRouter签到')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--config', default=os.getenv('AGENTROUTER_CONFIG', ''))
        args = parser.parse_args()
        raw = os.getenv('AGENTROUTER_ACCOUNTS', '')
        if raw.strip():
            raw_accounts = [line.strip() for line in raw.splitlines() if line.strip()]
        elif args.config:
            data = json.loads(Path(args.config).read_text(encoding='utf-8'))
            raw_accounts = data['agentrouter']['accounts']
            if not isinstance(raw_accounts, list):
                raise TaskError('配置 accounts 必须为数组')
        if not raw_accounts:
            raise TaskError('请填写 AGENTROUTER_ACCOUNTS，每行一个账号')
    except Exception:
        config_error = True
        log('❌ 配置读取失败，请检查账号变量或显式配置文件')
    log(f'账号总数：{len(raw_accounts)}')
    for index, raw in enumerate(raw_accounts, 1):
        account_start = time.monotonic()
        counts = {'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
        api = None
        try:
            stage = time.monotonic()
            log(f'账号 {index} 阶段 1/3：检查配置')
            account = account_config(raw)
            log(f'✅ 配置检查通过；耗时 {time.monotonic()-stage:.2f} 秒')
            if dry:
                counts['skipped'] = 2
                log(f'账号 {index} 阶段 2/3：⏭️ 离线跳过 OAuth 登录签到；耗时 0 秒')
                log(f'账号 {index} 阶段 3/3：⏭️ 离线跳过身份与余额查询；耗时 0 秒')
            else:
                api = API(account)
                stage = time.monotonic()
                log(f'账号 {index} 阶段 2/3：GitHub OAuth 登录签到')
                user = api.login()
                name = identity(user, account['github_session'])
                if name:
                    log(f'官方账号身份：{name}')
                if user.get('checked_in') is not True:
                    raise TaskError('登录成功但服务端未明确确认 checked_in，签到未验证')
                counts['success'] += 1
                log(f'✅ 今日签到已确认；耗时 {time.monotonic()-stage:.2f} 秒')
                stage = time.monotonic()
                log(f'账号 {index} 阶段 3/3：身份与余额查询')
                user = api.business('/api/user/self')
                if not isinstance(user, dict):
                    raise TaskError('余额响应缺少用户信息')
                name = identity(user, account['github_session'])
                if name:
                    log(f'官方账号身份：{name}')
                quota = user.get('quota')
                if not isinstance(quota, (int, float)) or isinstance(quota, bool) or not math.isfinite(quota):
                    raise TaskError('余额字段无效')
                counts['success'] += 1
                log(f'✅ 当前余额 ${quota/api.unit:.2f}；已用额度：{user.get("used_quota") if isinstance(user.get("used_quota"), (int, float)) else "未返回"}；耗时 {time.monotonic()-stage:.2f} 秒')
        except Exception as exc:
            counts['failed'] = 1
            counts['skipped'] = max(0, 2-counts['success']-counts['failed'])
            message = str(exc) if isinstance(exc, TaskError) else '配置、依赖或响应处理失败，请检查参数及 requests 安装'
            log(f'❌ 账号 {index}：{message}；阶段耗时 {time.monotonic()-stage:.2f} 秒')
        finally:
            if api:
                try:
                    api.close()
                except Exception:
                    log("⚠️ 会话清理失败，业务结果保留")
        elapsed = round(time.monotonic()-account_start, 2)
        log(f'账号 {index} 统计：总任务 2；成功 {counts["success"]}；已完成 0；跳过 {counts["skipped"]}；失败 {counts["failed"]}；耗时 {elapsed} 秒')
        results.append({'account': index, 'success': counts['failed'] == 0, 'tasks': counts, 'elapsedSeconds': elapsed})
        if not dry and index < len(raw_accounts):
            time.sleep(5)
    succeeded = sum(r['success'] for r in results)
    failed = len(results)-succeeded
    exit_code = int(config_error or failed > 0)
    status = 'configuration-error' if config_error else ('partial-failure' if failed and succeeded else 'failure' if failed else 'dry-run' if dry else 'success')
    body = f'账号总数：{len(raw_accounts)}；成功：{succeeded}；失败：{failed}；状态：{status}'
    notification = notify(body, dry)
    log('----------------------------------------')
    log(body)
    totals = {key: sum(r['tasks'][key] for r in results) for key in ('success', 'alreadyComplete', 'skipped', 'failed')}
    log(f'子任务统计：{json.dumps(totals, ensure_ascii=False)}')
    log(f'通知状态：{notification}')
    elapsed = round(time.monotonic()-start, 2)
    log(f'完成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}；总耗时 {elapsed} 秒；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'dryRun': dry, 'total': len(raw_accounts), 'success': succeeded,
          'failed': failed, 'configurationError': config_error, 'tasks': totals, 'accounts': results,
          'notification': notification, 'elapsedSeconds': elapsed}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
