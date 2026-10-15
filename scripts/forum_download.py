#!/usr/bin/env python3
# name: Discuz 论坛日常维护
# cron: 29 2 * * *
# 来源：nuthx/auto-sign，src/general/forum_download.py、forum_sign.py、
# forum_sign_plus.py、forum_visit.py、forum_work.py，GPL-3.0；维护版本沿用 GPL-3.0。
"""独立运行，Python 3 标准库，无下载或安装引导。

FORUM_ACCOUNTS：每行一个 JSON 对象，字段 name、url、fid、cookie；
cookie 为完整 Cookie 字符串，不拆分其中的分号、& 或 @。
登录自己的论坛，在浏览器开发者工具网络面板复制同站请求 Cookie；
url 填 HTTPS 论坛根地址（可含安装子目录），fid 从版块地址取得。
FORUM_TASKS：visit,credits（默认）；可添加 download、sign 或 sign_plus。
可添加 work：访问 np_cliworkdz 插件、最多点击八次并领取打工奖励。
work 需要 FORUM_ALLOW_WORK=1；仅适用于已安装该插件的论坛，可能改变积分和广告统计。
work 的 Referer 和表单沿用上游；间隔限制出现后停止点击，再核对领取结果。
两个签到入口择一。download 必须另设 FORUM_ALLOW_DOWNLOAD=1，可能扣积分。
附件仅读取并丢弃，不保存文件；最多读取前三个帖子，每次间隔 2 秒。
上游未声明 cron；本版本建议每日 08:20，可在青龙调整。
FORUM_DRY_RUN=1 完全断网，包括通知；真实运行通知遵守 QINGLONG_NOTIFY。
"""

import importlib
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = 'Discuz 论坛日常维护'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36'
MAX_PAGE = 2 * 1024 * 1024
MAX_ATTACHMENT = 20 * 1024 * 1024


def enabled(name, default='0'):
    return os.getenv(name, default).lower() not in ('0', 'false', 'no', 'off', '')


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


class Failure(Exception):
    """仅使用固定脱敏消息。"""


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []
        self.parts = []

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def text(self):
        return ''.join(x.text() if isinstance(x, Node) else x for x in self.parts)

    def has_class(self, name):
        return name in self.attrs.get('class', '').split()


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.current = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        self.current.parts.append(node)
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.parts.append(data)

    def nodes(self):
        return self.root.walk()


def public_text(value):
    # 输出身份和积分时保留官方内容，仅过滤明确的敏感值和控制字符。
    return re.sub(r'[\x00-\x1f\x7f]', ' ', value).strip()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, account):
        self.base = account['url'].rstrip('/') + '/'
        self.cookie = account['cookie']
        self.origin = urlsplit(self.base)
        self.opener = build_opener(NoRedirect())

    def safe_url(self, link):
        url = urljoin(self.base, link)
        parts = urlsplit(url)
        if (parts.scheme, parts.netloc) != (self.origin.scheme, self.origin.netloc) or parts.username or parts.password:
            raise Failure('链接不在配置的 HTTPS 站点，已阻止携带凭据访问')
        return url

    def request(self, link='', data=None, attachment=False, referer=None):
        url = self.safe_url(link)
        payload = urlencode(data).encode() if data is not None else None
        for _ in range(6):
            req = Request(url, data=payload, headers={
                'User-Agent': UA, 'Cookie': self.cookie, 'Referer': self.safe_url(referer) if referer else self.base,
                'Content-Type': 'application/x-www-form-urlencoded',
            })
            try:
                response = self.opener.open(req, timeout=20)
            except HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    location = exc.headers.get('Location')
                    exc.close()
                    if not location:
                        raise Failure('重定向缺少地址') from None
                    url = self.safe_url(urljoin(url, location))
                    if exc.code in (301, 302, 303):
                        payload = None
                    continue
                exc.close()
                raise Failure(f'HTTP 请求失败（状态 {exc.code}）') from None
            except (URLError, TimeoutError, OSError):
                raise Failure('网络请求失败或超时') from None
            with response:
                if response.status != 200:
                    raise Failure('响应状态未验证成功')
                limit = MAX_ATTACHMENT if attachment else MAX_PAGE
                raw = response.read(limit + 1)
                if len(raw) > limit:
                    raise Failure('响应超过安全大小限制')
                content_type = response.headers.get_content_type()
                if attachment:
                    # 登录页、扣费确认页、错误页不得冒充附件成功。
                    disposition = response.headers.get('Content-Disposition', '').lower()
                    marked = 'attachment' in disposition and 'filename' in disposition
                    archive = raw.startswith((b'PK\x03\x04', b'Rar!', b'7z\xbc\xaf\x27\x1c', b'\x1f\x8b'))
                    if not raw or content_type in ('text/html', 'application/xhtml+xml', 'application/json', 'application/xml') or raw.lstrip()[:64].lower().startswith((b'<!doctype', b'<html', b'<?xml')) or not (marked or archive):
                        raise Failure('未收到可验证的附件内容（可能需要登录或扣费确认）')
                    return len(raw)
                charset = response.headers.get_content_charset()
                if not charset:
                    found = re.search(br'charset\s*=\s*["\x27]?([\w-]+)', raw[:8192], re.I)
                    charset = found.group(1).decode('ascii') if found else 'utf-8'
                try:
                    return raw.decode(charset, errors='replace')
                except LookupError:
                    raise Failure('页面字符编码不受支持') from None
        raise Failure('重定向次数过多')

    def authenticated(self, html, show_identity=False):
        page = Page(html)
        logout = any(n.tag == 'a' and 'action=logout' in n.attrs.get('href', '') for n in page.nodes())
        if not logout:
            raise Failure('未找到已登录标志，无法确认账号会话有效')
        if show_identity:
            for n in page.nodes():
                if n.tag == 'strong' and n.has_class('vwmy'):
                    text = public_text(n.text())
                    if text and text not in self.cookie and not re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text):
                        log('官方账号身份：' + text)
                        break
        return page

    def visit(self):
        self.authenticated(self.request(), True)
        return 'success', '首页已返回并确认登录；不推断访问奖励到账'

    def credits(self):
        page = self.authenticated(self.request('home.php?mod=spacecp&ac=credit&showcredit=1'))
        values = []
        for n in page.nodes():
            if n.tag == 'li' and n.parent and n.parent.has_class('creditl'):
                text = public_text(n.text())
                match = re.fullmatch(r'\s*([\w\u4e00-\u9fff ]{1,30})[：:]\s*(-?\d+(?:\.\d+)?)\s*', text)
                if match and match.group(1) not in self.cookie and not re.search(r'1[3-9]\d{9}', match.group(0)):
                    values.append(match.group(1).strip() + '：' + match.group(2))
        if not values:
            raise Failure('积分页面缺少可识别的 creditl 积分项目，未猜测余额')
        log('论坛积分：' + '；'.join(values))
        return 'success', '积分已查询'

    def work(self):
        endpoint = 'plugin.php?id=np_cliworkdz:work'
        # 原始端点、GET/POST、act 字段和 Referer 均来自 forum_work.py。
        referer = 'plugin.php?id=dsu_paulsign:sign'
        self.authenticated(self.request(), True)
        page = self.request(endpoint, referer=referer)
        if any(x in Page(page).root.text() for x in ('请先登录', '登录后', '插件不存在', '插件未安装')):
            raise Failure('打工插件不可用或会话未被接受，未执行点击')
        log('打工步骤 1/3：✅ 插件页面已访问；尚未确认奖励')
        clicks = 0
        for index in range(1, 9):
            response = self.request(endpoint, {'act': 'clickad'}, referer=referer)
            text = Page(response).root.text()
            if any(x in text for x in ('请先登录', '登录后', '无权', '权限不足', '打工失败')):
                raise Failure('打工点击被拒绝，已停止，未重复提交')
            if '必须与上一次间隔' in text:
                log(f'打工步骤 2/3：⏭️ 第 {index} 次遇到间隔限制，停止点击并检查领取状态')
                break
            clicks += 1
            log(f'打工步骤 2/3：第 {index}/8 次请求已返回；不推断点击或奖励成功')
        result = self.request(endpoint, {'act': 'getcre'}, referer=referer)
        messages = [n.text().strip() for n in Page(result).nodes() if n.attrs.get('id') == 'messagetext']
        if len(messages) != 1:
            raise Failure('打工领取响应缺少唯一 messagetext，无法验证奖励')
        message = messages[0]
        # 不输出原始提示：插件版本及错误文案可能包含凭据或地址。
        if any(x in message for x in ('失败', '错误', '请先登录', '登录后', '不足', '未完成', '还没有', '尚未', '必须与上一次间隔')):
            raise Failure('打工领取未成功或条件尚未满足；请核对插件状态')
        if any(x in message for x in ('今日已领取', '今天已领取', '今日已经领取', '今天已经领取', '今日已完成打工', '今天已经完成打工')):
            log('打工步骤 3/3：☑️ 服务端明确确认今日已领取或已完成')
            return 'alreadyComplete', '今日打工奖励已经领取或任务已完成'
        if not any(x in message for x in ('打工成功', '领取成功', '成功领取', '成功获得')):
            raise Failure('打工领取响应未提供明确成功标志，请核对插件版本；不会自动重试领取')
        log(f'打工步骤 3/3：✅ 服务端明确确认领取成功；点击请求 {clicks} 次')
        return 'success', '服务端明确确认打工领取成功；积分由独立 credits 阶段查询'

    def sign(self, plus=False):
        endpoint = 'qiandao.php' if plus else 'plugin.php?id=dsu_paulsign:sign'
        html = self.request(endpoint, {})
        page = self.authenticated(html)
        if any(x in page.root.text() for x in ('已经打过卡', '您今天已经签到', '今日已签', '今天已签到')):
            return 'alreadyComplete', '今日已经签到'
        tokens = [n.attrs.get('value', '') for n in page.nodes() if n.tag == 'input' and n.attrs.get('name') == 'formhash']
        token = next((t for t in tokens if re.fullmatch(r'[a-zA-Z0-9]+', t)), '')
        if not token:
            raise Failure('签到页面缺少有效 formhash，未提交')
        if plus:
            result = self.request('qiandao.php?' + urlencode({'sign': token}), {})
        else:
            result = self.request('plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1',
                                  {'formhash': token, 'qdxq': 'kx', 'qdmode': '1', 'todaysay': '签到签到~', 'fastreply': '0'})
        if any(x in result for x in ('已经打过卡', '您今天已经签到', '今日已签', '今天已签到')):
            return 'alreadyComplete', '今日已经签到'
        if any(x in result for x in ('签到成功', '打卡成功', '恭喜你签到成功', '恭喜您签到成功')) and not any(x in result for x in ('签到失败', '登录后', '请先登录')):
            return 'success', '服务端明确确认签到成功'
        raise Failure('签到响应未提供明确成功标志，请核对站点插件版本')

    def download(self, fid):
        page = self.authenticated(self.request('forum.php?' + urlencode({'mod': 'forumdisplay', 'fid': fid})))
        posts = []
        for row in page.nodes():
            if row.tag == 'tbody' and row.attrs.get('id', '').startswith('normalthread_'):
                for n in row.walk():
                    if n.tag == 'a' and n.has_class('s') and n.attrs.get('href'):
                        posts.append(self.safe_url(n.attrs['href']))
                        break
        if not posts:
            raise Failure('未找到版块主题列表，未执行下载')
        failures = 0
        for index, post in enumerate(posts[:3], 1):
            try:
                page = self.authenticated(self.request(post))
                link = None
                for n in page.nodes():
                    if n.attrs.get('id') == 'filelistn' and n.parent:
                        siblings = n.parent.children
                        pos = siblings.index(n)
                        if pos + 1 < len(siblings) and siblings[pos + 1].tag == 'div':
                            link = next((a.attrs.get('href') for a in siblings[pos + 1].walk() if a.tag == 'a' and a.attrs.get('href')), None)
                        break
                if not link:
                    raise Failure('帖子缺少原站附件链接')
                size = self.request(self.safe_url(urljoin(post, link)), attachment=True)
                log(f'附件 {index}：✅ 已读取 {size} 字节，未保存文件')
            except Failure as exc:
                failures += 1
                log(f'附件 {index}：❌ {exc}')
            if index < min(3, len(posts)):
                time.sleep(2)
        if failures:
            raise Failure(f'附件下载部分失败：共 {min(3, len(posts))} 项，失败 {failures} 项')
        return 'success', f'已验证 {min(3, len(posts))} 个附件下载'


def notify(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    if dry:
        log('通知预演：' + body)
        return '断网预演，未发送'
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            directories = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
            module = None
            for directory in directories:
                if not directory:
                    continue
                path = Path(directory) / 'notify.py'
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
            if module is None:
                raise ImportError
        # 青龙通知异常和第三方输出均不暴露给业务日志。
        import contextlib
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            module.send(TITLE, body)
        return '已发送'
    except Exception:
        log('⚠️ 通知不可用或发送失败，保留业务退出码')
        return '失败或不可用'


def account_config(line, tasks):
    try:
        account = json.loads(line)
    except (ValueError, TypeError):
        raise Failure('账号行必须是 JSON 对象') from None
    if not isinstance(account, dict):
        raise Failure('账号行必须是 JSON 对象')
    if any(not isinstance(account.get(k), str) or not account[k].strip() for k in ('url', 'cookie')):
        raise Failure('账号缺少 url 或 cookie 字符串')
    parts = urlsplit(account['url'])
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise Failure('url 必须是无内嵌凭据、查询或片段的 HTTPS 论坛根地址')
    if '\n' in account['cookie'] or '\r' in account['cookie']:
        raise Failure('Cookie 含非法换行')
    if 'download' in tasks and not re.fullmatch(r'\d+', str(account.get('fid', ''))):
        raise Failure('下载任务需要数字版块 fid')
    return account


def main():
    started = time.monotonic()
    dry = enabled('FORUM_DRY_RUN')
    lines = [s for s in os.getenv('FORUM_ACCOUNTS', '').splitlines() if s.strip()]
    tasks = list(dict.fromkeys(s.strip() for s in os.getenv('FORUM_TASKS', 'visit,credits').split(',') if s.strip()))
    log(f'=== {TITLE} ===')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if dry else "真实运行"}；账号数：{len(lines)}')
    results = []
    config_error = None
    if not lines:
        config_error = '缺少必填 FORUM_ACCOUNTS'
    elif not tasks or set(tasks) - {'visit', 'credits', 'sign', 'sign_plus', 'download', 'work'}:
        config_error = 'FORUM_TASKS 包含未知动作或为空'
    elif 'sign' in tasks and 'sign_plus' in tasks:
        config_error = '同一账号的两种签到入口只能选择一种'
    elif 'download' in tasks and not enabled('FORUM_ALLOW_DOWNLOAD'):
        config_error = '附件下载可能扣积分，需显式设置 FORUM_ALLOW_DOWNLOAD=1'
    elif 'work' in tasks and not enabled('FORUM_ALLOW_WORK'):
        config_error = '打工会提交广告点击及领取奖励，需显式设置 FORUM_ALLOW_WORK=1'
    totals = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
    if config_error:
        log('❌ 配置错误：' + config_error)
    else:
        for index, line in enumerate(lines, 1):
            begin = time.monotonic()
            counts = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
            log(f'账号 {index}：开始')
            try:
                account = account_config(line, tasks)
                client = None if dry else Client(account)
                for step, action in enumerate(tasks, 1):
                    tick = time.monotonic()
                    log(f'账号 {index} 阶段 {step}/{len(tasks)}：{action}')
                    try:
                        if dry:
                            status, detail = 'skipped', 'DRY_RUN_OK 参数有效；模拟流程通过，未访问网络或执行副作用'
                        elif action == 'download':
                            status, detail = client.download(str(account['fid']))
                        elif action in ('sign', 'sign_plus'):
                            status, detail = client.sign(action == 'sign_plus')
                        else:
                            status, detail = getattr(client, action)()
                    except Failure as exc:
                        status, detail = 'failure', str(exc)
                    except Exception:
                        status, detail = 'failure', '请求或解析出现未预期错误，已隐藏原始异常'
                    counts[status] += 1
                    icon = {'success': '✅', 'alreadyComplete': '☑️', 'skipped': '⏭️', 'failure': '❌'}[status]
                    log(f'账号 {index} 阶段 {step}：{icon} {detail}；耗时 {time.monotonic() - tick:.2f} 秒')
            except Exception:
                counts['failure'] += 1
                log(f'账号 {index}：❌ 配置无效，请核对 JSON、HTTPS 根地址、Cookie 和 fid；未输出输入内容')
            for key in totals:
                totals[key] += counts[key]
            failed = bool(counts['failure'])
            results.append({'account': index, 'failed': failed, 'statistics': counts})
            log(f'账号 {index} 统计：总任务 {sum(counts.values())}，成功 {counts["success"]}，已完成 {counts["alreadyComplete"]}，跳过 {counts["skipped"]}，失败 {counts["failure"]}，耗时 {time.monotonic() - begin:.2f} 秒')
    failed = len(lines) if config_error else sum(r['failed'] for r in results)
    succeeded = len(lines) - failed
    status = 'configuration-error' if config_error else ('partial-failure' if failed and succeeded else 'failure' if failed else 'dry-run' if dry else 'success')
    exit_code = 1 if config_error or failed else 0
    body = f'状态：{status}；账号总数 {len(lines)}，成功 {succeeded}，失败 {failed}；子任务成功 {totals["success"]}，已完成 {totals["alreadyComplete"]}，跳过 {totals["skipped"]}，失败 {totals["failure"]}。' + ('预演成功仅表示参数与流程有效。' if dry else '')
    delivery = notify(body, dry)
    log('----------------------------------------')
    log(body)
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {time.monotonic() - started:.2f} 秒；通知：{delivery}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'dryRun': dry, 'accounts': len(lines), 'succeeded': succeeded, 'failed': failed, 'statistics': totals, 'results': results, 'notification': delivery, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
