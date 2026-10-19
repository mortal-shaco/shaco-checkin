#!/usr/bin/env python3
# name: SSL证书检查
# cron: 10 2 * * *
# new Env("SSL证书检查")
# SSL 证书检查脚本
# - 通过 Cloudflare API 自动获取域名 A 记录列表
# - 批量检查多个域名的 SSL 证书状态
# - 获取证书到期时间、剩余天数、颁发者等信息
# - 分类显示正常、警告、过期和检查失败的证书
# 上游：CN-Grace/QinglongScripts，SSL.py；许可证：MIT。
# 原始版本：a40a2b080e0160bd8e0b0b807081115537b87153
# 本维护版本继续采用 MIT 许可证，保留上游署名及说明。
"""SSL_ACCOUNTS 每个非空行为一个 JSON 对象：
{"token":"占位凭据","zone_ids":["区域标识"],"domains":["example.com"]}
或使用 email 和 key 字段代替 token。区域及域名顺序一一对应。
兼容 CF_API_TOKEN，或 CF_API_EMAIL + CF_API_KEY，以及逗号分隔的
CF_ZONE_IDS / CF_DOMAINS。SSL_WARNING_DAYS 默认30；SSL_DRY_RUN=1断网预演。
Token 在 Cloudflare 个人资料/API Tokens 创建，授予指定区域 DNS Read 权限；
Zone ID 在区域概览右侧获取，domains 填区域主域名。Global API Key 在个人资料
获取并配登录邮箱；推荐使用范围受限的 Token。预演不验证凭据或证书。
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
        _ql_notify_identities = ('cf6fb60f0d69e9ed', 'scripts/ssl_cert_check.py', 'ssl_cert_check.py', 'ssl_cert_check')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import json
import math
import os
import re
import socket
import ssl
import sys
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

PORTS = [443, 8443, 4443, 4433, 9443]
TIMEOUT = 10
MAX_BYTES = 2 * 1024 * 1024
DISABLED = {"0", "false", "no", "off"}
TRUE = {"1", "true", "yes", "on"}
TITLE = "SSL证书检查"
TZ = timezone(timedelta(hours=8))


def stamp():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def log(message):
    for line in str(message).splitlines():
        print(f"[{stamp()[11:]}] {line}", flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("API 重定向被拒绝")


def domain_name(value):
    if not isinstance(value, str):
        raise TaskError("域名必须为文本")
    try:
        host = value.strip().rstrip('.').encode('idna').decode('ascii').lower()
    except UnicodeError:
        raise TaskError("域名格式无效") from None
    if len(host) > 253 or not host or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
        for part in host.split('.')
    ):
        raise TaskError("域名格式无效")
    return host


def list_value(value):
    if isinstance(value, str):
        value = [s.strip() for s in value.split(',') if s.strip()]
    if not isinstance(value, list) or not value:
        raise TaskError("区域和域名列表不能为空")
    return value


def validate_account(account):
    if not isinstance(account, dict):
        raise TaskError("账号行必须为 JSON 对象")
    token = account.get('token', '')
    email, key = account.get('email', ''), account.get('key', '')
    for item in (token, email, key):
        if not isinstance(item, str) or any(ord(c) < 32 or ord(c) == 127 for c in item):
            raise TaskError("认证字段格式无效")
    if not token.strip() and not (email.strip() and key.strip()):
        raise TaskError("缺少 token 或配套 email/key")
    zones = list_value(account.get('zone_ids'))
    domains = list_value(account.get('domains'))
    if len(zones) != len(domains):
        raise TaskError("区域标识和主域名数量不一致")
    if any(not isinstance(z, str) or not re.fullmatch(r'[a-fA-F0-9]{32}', z) for z in zones):
        raise TaskError("Zone ID 必须为32位十六进制标识")
    return {'token': token, 'email': email, 'key': key,
            'zone_ids': zones, 'domains': [domain_name(d) for d in domains]}


def account_inputs():
    raw = os.environ.get('SSL_ACCOUNTS', '')
    if raw.strip():
        return [line.strip() for line in raw.splitlines() if line.strip()]
    if any(os.environ.get(k, '').strip() for k in ('CF_API_TOKEN', 'CF_API_EMAIL', 'CF_API_KEY')):
        return [json.dumps({'token': os.environ.get('CF_API_TOKEN', ''),
                            'email': os.environ.get('CF_API_EMAIL', ''),
                            'key': os.environ.get('CF_API_KEY', ''),
                            'zone_ids': os.environ.get('CF_ZONE_IDS', ''),
                            'domains': os.environ.get('CF_DOMAINS', '')})]
    raise TaskError("未配置 SSL_ACCOUNTS 或兼容 Cloudflare 认证变量")


def get_cloudflare_a_records(account, zone_id, domain):
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    if account['token'].strip():
        headers['Authorization'] = 'Bearer ' + account['token']
    else:
        headers['X-Auth-Email'] = account['email']
        headers['X-Auth-Key'] = account['key']
    opener = urllib.request.build_opener(NoRedirect())
    names = set()
    page = 1
    while True:
        query = urllib.parse.urlencode({'type': 'A', 'page': page, 'per_page': 100})
        url = f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?{query}'
        try:
            with opener.open(urllib.request.Request(url, headers=headers), timeout=30) as response:
                if response.status != 200:
                    raise TaskError("Cloudflare HTTP 状态异常")
                raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise TaskError("Cloudflare 响应超过安全上限")
            data = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise TaskError(f"Cloudflare HTTP 错误 {exc.code}") from None
        except (urllib.error.URLError, OSError, ValueError):
            raise TaskError("Cloudflare 请求失败、超时或响应不是有效 JSON") from None
        if not isinstance(data, dict) or data.get('success') is not True:
            raise TaskError("Cloudflare 未返回业务成功")
        records = data.get('result')
        info = data.get('result_info')
        if not isinstance(records, list) or not isinstance(info, dict):
            raise TaskError("Cloudflare 响应字段不完整")
        total_pages = info.get('total_pages')
        if (type(total_pages) is not int or total_pages < 0 or total_pages > 10000
                or info.get('page') != page):
            raise TaskError("Cloudflare 分页信息无效")
        if not records and page < total_pages:
            raise TaskError("Cloudflare 分页提前返回空结果")
        for record in records:
            if not isinstance(record, dict) or record.get('type') != 'A':
                raise TaskError("Cloudflare A 记录格式异常")
            name = domain_name(record.get('name'))
            if name != domain and not name.endswith('.' + domain):
                raise TaskError("A 记录不属于配置的区域主域名")
            names.add(name)
        log(f"区域 {domain} 第{page}页：成功读取 {len(records)} 条 A 记录")
        if page >= total_pages:
            break
        page += 1
    return sorted(names)


def get_certificate_info(domain, warning_days):
    host, sep, port_text = domain.partition(':')
    host = domain_name(host)
    if sep:
        if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            raise TaskError("HTTPS 端口无效")
        ports = [int(port_text)]
    else:
        ports = PORTS
    expired = False
    for port in ports:
        started = time.monotonic()
        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
                with context.wrap_socket(sock, server_hostname=host) as tls:
                    cert = tls.getpeercert()
            expiry = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert['notAfter']), timezone.utc)
            seconds = (expiry - datetime.now(timezone.utc)).total_seconds()
            days = math.floor(seconds / 86400)
            issuer = ', '.join(value for rdn in cert.get('issuer', ())
                               for key, value in rdn if key == 'organizationName') or '未知'
            status = 'expired' if seconds <= 0 else ('warning' if days <= warning_days else 'valid')
            log(f"{host}:{port}：{status}，剩余 {days} 天，到期 {expiry.isoformat()}，"
                f"颁发者 {issuer}，耗时 {time.monotonic()-started:.2f}秒")
            return {'domain': host, 'port': port, 'status': status, 'days_left': days,
                    'expiry_date': expiry.isoformat(), 'issuer': issuer}
        except ssl.SSLCertVerificationError as exc:
            is_expired = exc.verify_code == 10
            expired = expired or is_expired
            log(f"{host}:{port}：{'证书已过期' if is_expired else '证书信任或主机名校验失败'}，"
                f"耗时 {time.monotonic()-started:.2f}秒；尝试下一端口")
        except (OSError, ValueError, KeyError):
            log(f"{host}:{port}：连接、握手或证书字段检查失败，"
                f"耗时 {time.monotonic()-started:.2f}秒；尝试下一端口")
    return {'domain': host, 'port': None, 'status': 'expired' if expired else 'error',
            'days_left': None, 'expiry_date': None, 'issuer': None}


def format_certificate_report(results, domains):
    groups = {}
    for result in results:
        host = result['domain']
        root = next((d for d in sorted(domains, key=len, reverse=True)
                     if host == d or host.endswith('.' + d)), '.'.join(host.split('.')[-2:]))
        groups.setdefault(root, []).append(result)
    lines = []
    labels = {'valid': '✅ 正常', 'warning': '⚠️ 即将到期', 'expired': '❌ 已过期', 'error': '❌ 检查失败'}
    for root, certs in groups.items():
        lines.append('主域名：' + root)
        for cert in certs:
            prefix = '@' if cert['domain'] == root else cert['domain'][:-(len(root)+1)]
            days = '' if cert['days_left'] is None else f"，剩余 {cert['days_left']} 天"
            port = str(cert['port']) if cert['port'] else '全部常用端口'
            lines.append(f"{labels[cert['status']]} {prefix} - {port}{days}")
    return '\n'.join(lines)


def send_notification(body, dry_run):
    if os.environ.get('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        log('⏭️ 通知已通过 QINGLONG_NOTIFY 关闭')
        return 'disabled'
    if dry_run:
        log('⏭️ 断网预演：已生成脱敏通知摘要，不调用通知网络通道')
        return 'dry-run-preview'
    # 通知在独立进程执行，屏蔽第三方输出并限制时间，不影响业务退出码。
    code = """
import importlib.util, json, os, sys
from pathlib import Path
title, body = json.load(sys.stdin)
try:
    import notify
except ImportError:
    notify = None
if notify is None or not callable(getattr(notify, 'send', None)):
    paths = []
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    for path in paths:
        if path.is_file():
            spec = importlib.util.spec_from_file_location('qinglong_notify', path)
            notify = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(notify)
            break
if notify is None or not callable(getattr(notify, 'send', None)):
    sys.exit(3)
notify.send(title, body)
"""
    try:
        result = subprocess.run([sys.executable, '-c', code],
                                input=json.dumps([TITLE, body]), text=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=30, check=False)
        if result.returncode == 0:
            log('✅ 通知发送完成')
            return 'sent'
        if result.returncode == 3:
            log('⚠️ 未找到青龙 notify.py，保留业务退出码')
            return 'unavailable'
        log('⚠️ 通知发送失败，保留业务退出码')
        return 'failed'
    except Exception:
        log('⚠️ 通知发送失败或超时，保留业务退出码')
        return 'failed'


def main():
    started = time.monotonic()
    dry = os.environ.get('SSL_DRY_RUN', '').strip().lower() in TRUE
    log('=' * 50)
    log(f'{TITLE} | 开始时间 {stamp()} | 模式 {"断网预演" if dry else "实际检查"}')
    counts = {'valid': 0, 'warning': 0, 'expired': 0, 'error': 0}
    total = success = failed = 0
    reports = []
    config_error = False
    try:
        log('阶段1：参数检查')
        inputs = account_inputs()
        total = len(inputs)
        warning = int(os.environ.get('SSL_WARNING_DAYS', '30'))
        if warning < 0:
            raise TaskError('SSL_WARNING_DAYS 必须为非负整数')
    except (TaskError, ValueError) as exc:
        # 不输出转换异常，避免无效参数中夹带敏感值。
        log('❌ 配置错误：' + (str(exc) if isinstance(exc, TaskError) else 'SSL_WARNING_DAYS 必须为非负整数'))
        inputs = []
        failed = total
        config_error = True
    log(f'账号总数：{total}')
    for index, raw in enumerate(inputs, 1):
        start = time.monotonic()
        account_failed = False
        results = []
        errors = 0
        skipped = 0
        log(f'账号{index} / 阶段1：校验账号配置')
        try:
            try:
                account = validate_account(json.loads(raw))
            except (ValueError, TypeError):
                raise TaskError('账号 JSON 格式无效') from None
            log(f'账号{index} / 阶段1完成，耗时 {time.monotonic()-start:.2f}秒')
            stage = time.monotonic()
            log(f'账号{index} / 阶段2：分页获取 A 记录')
            names = set()
            for zone, domain in zip(account['zone_ids'], account['domains']):
                if dry:
                    log(f'⏭️ 区域 {domain}：预演跳过 API 请求')
                    skipped += 1
                    continue
                try:
                    records = get_cloudflare_a_records(account, zone, domain)
                    names.update(records)
                    if not records:
                        raise TaskError('区域未返回任何 A 记录，无法完成证书检查')
                except TaskError as exc:
                    errors += 1
                    account_failed = True
                    log(f'❌ 区域 {domain}：{exc}')
            log(f'账号{index} / 阶段2完成：{len(names)}个不重复域名，耗时 {time.monotonic()-stage:.2f}秒')
            stage = time.monotonic()
            log(f'账号{index} / 阶段3：SSL 证书检查')
            if dry:
                log('✅ DRY_RUN_OK：账号参数检查通过，API、DNS、TLS、通知网络调用均未执行')
                skipped += 1
            else:
                for name in sorted(names):
                    result = get_certificate_info(name, warning)
                    results.append(result)
                    counts[result['status']] += 1
                    if result['status'] in ('error', 'expired'):
                        account_failed = True
                report = format_certificate_report(results, account['domains'])
                if report:
                    log(report)
                    reports.append(f'账号{index}\n' + report)
            log(f'账号{index} / 阶段3完成，耗时 {time.monotonic()-stage:.2f}秒')
        except TaskError as exc:
            account_failed = True
            errors += 1
            log(f'❌ 账号{index}：{exc}')
        except Exception:
            account_failed = True
            errors += 1
            log(f'❌ 账号{index}：处理异常，已隐藏异常内容')
        if account_failed:
            failed += 1
        else:
            success += 1
        good = sum(r['status'] in ('valid', 'warning') for r in results)
        bad = sum(r['status'] in ('expired', 'error') for r in results) + errors
        log(f'账号{index}统计：总任务 {len(results)+errors+skipped}，成功 {good}，已完成 0，'
            f'跳过 {skipped}，失败 {bad}，耗时 {time.monotonic()-start:.2f}秒，'
            f'结果 {"失败" if account_failed else "预演通过" if dry else "成功"}')
    exit_code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else 'partial-failure' if failed and success
              else 'failure' if failed else 'dry-run' if dry else 'success')
    body = f'状态：{status}\n账号总数：{total}，成功：{success}，失败：{failed}\n' + (
        '预演仅验证配置，没有验证业务成功。' if dry else
        f"正常：{counts['valid']}，警告：{counts['warning']}，过期：{counts['expired']}，检查失败：{counts['error']}")
    notification = send_notification(body + ('\n' + '\n'.join(reports) if reports else ''), dry)
    log('─' * 50)
    log(body)
    log(f'完成时间：{stamp()} | 总耗时：{time.monotonic()-started:.2f}秒 | 通知：{notification} | 最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'dryRun': dry,
          'accounts': total, 'success': success, 'failed': failed, 'certificates': counts,
          'notification': notification, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
