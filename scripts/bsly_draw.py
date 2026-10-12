#!/usr/bin/env python3
# name: 百事乐元抽奖
# cron: 0 9 * * *
# 来源: cloudcranes/some_scripts/bsly_draw.py
# 上游提交: f62b50fe0a961ea8a8707682723b080c0a5d1142
# 许可: MIT（任务提供的 effectiveLicense；原文件无版权或许可声明）
"""百事乐元独立维护版。
bsly: 每行 token#User-Agent#账号备注；抓包本人授权的微信小程序
wx1a72addb7ee74f67 抽奖请求，读取 token 和 User-Agent 请求头。
备注自填，不能含 #；User-Agent 中的 # 会保留。禁止用 & 分隔账号。
BSLY_DRY_RUN=1: 完全断网预演（通知仅本地模拟）。
BSLY_ENABLE_DRAW=1: 明确允许消耗抽奖机会；默认关闭，关闭的实跑非零退出。
BSLY_MAX_DRAWS: 每账号最多请求次数，默认 1，范围 1..100。
上游没有 cron；维护版建议每天 09:00，用户应根据活动规则调整。
"""
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler

URL = 'https://pepcoinbhhpre.pepcoinbypepsico.com.cn/mp/draw'
REFERER = 'https://servicewechat.com/wx1a72addb7ee74f67/126/page-frame.html'
TITLE = '百事乐元抽奖'
DISABLED = {'0', 'false', 'no', 'off'}


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不将 token 转发给重定向目标，也不重复执行有副作用的 GET。
        return None


def safe_text(value, secrets):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ''
    text = str(value)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, '[已脱敏]')
    text = re.sub(r'https?://\S+', '[链接已隐藏]', text)
    text = re.sub(r'(?i)(cookie|token|session|device|authorization|signature)\s*[:=]\s*\S+', '[敏感字段已隐藏]', text)
    text = re.sub(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', text)
    return text[:200]


def parse_account(line):
    token, remainder = line.split('#', 1)
    agent, label = remainder.rsplit('#', 1)
    if not token.strip() or not agent.strip() or not label.strip():
        raise ValueError('账号字段缺失')
    if any(c in token + agent for c in '\r\n'):
        raise ValueError('请求头格式无效')
    token.encode('latin-1')
    agent.encode('latin-1')
    return token, agent, label


def fetch_draw(token, agent):
    request = Request(URL, headers={'token': token, 'User-Agent': agent,
                                   'Referer': REFERER}, method='GET')
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError('HTTP 状态异常')
        payload = response.read(65537)
    if len(payload) > 65536:
        raise ValueError('响应过大')
    result = json.loads(payload)
    if not isinstance(result, dict):
        raise ValueError('响应结构异常')
    return result


def notify_summary(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').lower().strip() in DISABLED:
        log('⏭️ 通知：全局开关已关闭')
        return 'disabled'
    if dry:
        log('⏭️ 通知：断网预演仅模拟脱敏摘要，不调用联网通知模块')
        return 'dry-run-local'
    # Qinglong 公共通知桥接可选；缺失或发送失败不改变业务退出码。
    candidates = []
    try:
        found = importlib.util.find_spec('notify')
        if found and found.origin:
            candidates.append(Path(found.origin))
    except Exception:
        pass
    directory = os.getenv('QINGLONG_NOTIFY_DIR')
    if directory:
        candidates.append(Path(directory) / 'notify.py')
    candidates.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        # 在子进程执行通知，限定时间并隐藏通知桥接输出，避免泄露配置。
        import subprocess
        bridge = ('import importlib.util,json,sys; '
                  's=importlib.util.spec_from_file_location("ql_notify",sys.argv[1]); '
                  'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                  'p=json.load(sys.stdin); m.send(p["title"],p["body"])')
        try:
            subprocess.run([sys.executable, '-c', bridge, str(path)],
                           input=json.dumps({'title': TITLE, 'body': body}), text=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30, check=True)
            log('✅ 通知：摘要已提交青龙通知模块')
            return 'sent'
        except Exception:
            log('⚠️ 通知：发送失败，保留业务退出码')
            return 'failed'
    log('⚠️ 通知：未发现 notify.py，保留业务退出码')
    return 'unavailable'


def main():
    started = time.monotonic()
    dry = os.getenv('BSLY_DRY_RUN', '0').strip() == '1'
    lines = [s.strip() for s in os.getenv('bsly', '').splitlines() if s.strip()]
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if dry else "实跑"}；账号数：{len(lines)}')
    config_errors = []
    try:
        limit = int(os.getenv('BSLY_MAX_DRAWS', '1'))
        if not 1 <= limit <= 100:
            raise ValueError()
    except ValueError:
        limit = 1
        config_errors.append('BSLY_MAX_DRAWS 必须为 1 至 100 的整数')
    if not lines:
        config_errors.append('缺少 bsly，每行应为 token#User-Agent#账号备注')
    if not dry and os.getenv('BSLY_ENABLE_DRAW', '0').strip() != '1':
        config_errors.append('抽奖未授权：请显式设置 BSLY_ENABLE_DRAW=1')
    for message in config_errors:
        log(f'❌ 配置错误：{message}')
    totals = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
    account_success = 0
    for index, line in enumerate(lines, 1):
        account_started = time.monotonic()
        stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
        log(f'账号[{index}] 阶段 1：参数校验')
        stage_started = time.monotonic()
        try:
            token, agent, label = parse_account(line)
        except (ValueError, UnicodeError):
            log(f'❌ 账号[{index}] 参数格式无效；耗时 {time.monotonic()-stage_started:.2f} 秒')
            stats.update(total=1, failed=1)
        else:
            log(f'✅ 账号[{index}] 参数校验通过；耗时 {time.monotonic()-stage_started:.2f} 秒')
            if config_errors:
                stats.update(total=1, failed=1)
                log(f'❌ 账号[{index}] 阶段 2：配置错误，未发送抽奖请求')
            elif dry:
                stats.update(total=1, skipped=1)
                log(f'✅ DRY_RUN_OK 账号[{index}] 阶段 2：将最多抽奖 {limit} 次；未发送网络请求；耗时 0.00 秒')
            else:
                for attempt in range(1, limit + 1):
                    stats['total'] += 1
                    stage_started = time.monotonic()
                    log(f'账号[{index}] 阶段 {attempt+1}：抽奖 {attempt}/{limit}')
                    try:
                        result = fetch_draw(token, agent)
                        # 上游仅证明数字 code=0 为成功；500 不可假定为已完成。
                        if type(result.get('code')) is not int or result['code'] != 0:
                            raise ValueError('业务未确认成功')
                        data = result.get('data')
                        if not isinstance(data, dict) or not isinstance(data.get('name'), str) or not data['name'].strip():
                            raise ValueError('成功响应缺少奖品名称')
                        secrets = [token, agent, label]
                        for container in (result, data):
                            for key in ('nickname', 'username', 'displayName', 'uid'):
                                if container.get(key) is not None:
                                    log(f'账号[{index}] 官方身份 {key}：{safe_text(container[key], secrets)}')
                        log(f'✅ 抽奖成功：获得 {safe_text(data["name"], secrets)}；提示：{safe_text(data.get("remark", ""), secrets)}；耗时 {time.monotonic()-stage_started:.2f} 秒')
                        stats['success'] += 1
                    except Exception:
                        stats['failed'] += 1
                        log(f'❌ 账号[{index}] 请求或业务校验失败，停止该账号抽奖，不重试有副作用请求；耗时 {time.monotonic()-stage_started:.2f} 秒')
                        break
        account_ok = stats['failed'] == 0
        account_success += int(account_ok)
        for key in totals:
            totals[key] += stats[key]
        log(f'账号[{index}] 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}；耗时 {time.monotonic()-account_started:.2f} 秒')
    failed_accounts = len(lines) - account_success
    exit_code = int(bool(config_errors or failed_accounts))
    status = ('configuration-error' if config_errors else
              'partial-failure' if failed_accounts and account_success else
              'failure' if failed_accounts else 'dry-run' if dry else 'success')
    body = f'账号总数 {len(lines)}，成功数 {account_success}，失败数 {failed_accounts}；状态 {status}；子任务成功 {totals["success"]}，失败 {totals["failed"]}，跳过 {totals["skipped"]}'
    notification = notify_summary(body, dry)
    log('----------------------------------------')
    log(body)
    log(f'子任务总数 {totals["total"]}，已完成 {totals["alreadyComplete"]}；通知状态 {notification}')
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {time.monotonic()-started:.2f} 秒；最终状态 {status}')
    print('TASK_SUMMARY=' + json.dumps(dict(task=TITLE, mode='dry-run' if dry else 'live',
          accounts=len(lines), success=account_success, failed=failed_accounts,
          tasks=totals, status=status, notification=notification, exitCode=exit_code), ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
