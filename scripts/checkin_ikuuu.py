#!/usr/bin/env python3
# name: ikuuu每日签到
# cron: 0 8 * * *
# 来源: cloudcranes/some_scripts, ikuuu/checkin_ikuuu.py
# 原始提交: f62b50fe0a961ea8a8707682723b080c0a5d1142
# 许可证: MIT（上游文件没有额外版权声明）
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""ikuuu 签到。Python 3，无第三方依赖。

在官方网站注册账号；使用登录邮箱及密码设置青龙变量 ikuuu。
每个非空行格式为 邮箱#密码，仅在第一个 # 处分隔，密码可包含 #。
旧变量名称保持不变，多账号不再使用 & 分隔（密码中的 & 保持原样）。
IKUUU_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
可用 QINGLONG_NOTIFY_DIR 指定青龙通知模块目录。无通知模块不影响业务退出码。
预演只展示通知摘要，不调用可能联网的通知模块。
上游没有 cron；本维护版建议每日北京时间 08:00，青龙时区需自行配置。
"""

import contextlib
import http.cookiejar
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

BASE = 'https://ikuuu.me'
TITLE = 'ikuuu每日签到'
DISABLED = {'0', 'false', 'no', 'off'}


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口发生重定向，未发送后续请求')


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())

    def request(self, path, data=None, as_json=True):
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(BASE + path, data=body, headers={
            'Origin': BASE, 'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json' if as_json else 'text/html',
        })
        try:
            with self.opener.open(req, timeout=20) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                payload = response.read(1048577)
            if len(payload) > 1048576:
                raise TaskError('响应超过大小限制')
            if not as_json:
                if not payload.strip():
                    raise TaskError('个人资料响应为空')
                return None
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise TaskError('接口响应结构异常')
            return value
        except urllib.error.HTTPError as exc:
            raise TaskError(f'HTTP 请求失败（状态 {exc.code}）') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError('网络请求失败或超时') from None
        except (ValueError, UnicodeError):
            raise TaskError('接口未返回有效 JSON') from None


def verified(value):
    # SSPanel 的 ret=1 是明确业务成功；不以 HTTP 200 或任意 msg 代替。
    return type(value.get('ret')) in (int, str) and value['ret'] in (1, '1')


def identity(value, secrets):
    sources = [value]
    if isinstance(value.get('data'), dict):
        sources.append(value['data'])
    for source in sources:
        for key in ('nickname', 'username', 'display_name', 'uid'):
            raw = source.get(key)
            if not isinstance(raw, (str, int)) or isinstance(raw, bool):
                continue
            text = str(raw)
            if (not text or any(secret in text for secret in secrets if secret)
                    or '@' in text or re.search(r'\d{11,}', text)
                    or any(ord(ch) < 32 for ch in text)):
                continue
            return text
    return None


def notify(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').lower() in DISABLED:
        return '已关闭'
    if dry:
        log('通知预演：' + summary)
        return '断网预演，已展示摘要'
    try:
        # 防止通知库自行输出环境、请求或异常细节。
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                module = importlib.import_module('notify')
            except ImportError:
                module = None
                paths = []
                if os.getenv('QINGLONG_NOTIFY_DIR'):
                    paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
                paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
                for path in paths:
                    if path.is_file():
                        spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        break
            if module is None or not callable(getattr(module, 'send', None)):
                return '不可用（未找到 notify.py）'
            module.send(TITLE, summary)
        return '已发送'
    except Exception:
        return '发送失败（业务退出码保持不变）'


def main():
    started = time.monotonic()
    dry = os.getenv('IKUUU_DRY_RUN', '0').lower() in {'1', 'true', 'yes', 'on'}
    lines = [line.strip() for line in os.getenv('ikuuu', '').splitlines() if line.strip()]
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S} | 模式：{"断网预演" if dry else "实际执行"} | 账号数：{len(lines)}')
    results = []
    config_error = not lines
    if config_error:
        log('❌ 配置错误：请设置 ikuuu，每行填写邮箱#密码')
    for index, line in enumerate(lines, 1):
        account_start = time.monotonic()
        stats = dict(total=3, success=0, alreadyComplete=0, skipped=0, failed=0)
        log(f'账号 {index} 开始')
        email, delimiter, password = line.partition('#')
        valid = bool(delimiter and email and password and '@' in email)
        if not valid:
            config_error = True
            stats.update(failed=1, skipped=2)
            log(f'❌ 账号 {index} 配置错误：需要邮箱#密码')
        else:
            client = None if dry else Client()
            for stage, name in enumerate(('登录', '读取个人资料', '签到'), 1):
                step_start = time.monotonic()
                log(f'账号 {index} 阶段 {stage}/3：{name}')
                try:
                    if dry:
                        log(f'⏭️ 参数及请求计划有效，断网跳过{name}')
                        stats['skipped'] += 1
                    elif stage == 1:
                        response = client.request('/auth/login', {'email': email, 'passwd': password})
                        if not verified(response):
                            raise TaskError('登录未获明确业务成功，停止该账号后续动作')
                        display = identity(response, (email, password))
                        if display:
                            log('官方账号身份：' + display)
                        stats['success'] += 1
                        log('✅ 登录成功（ret=1）')
                    elif stage == 2:
                        client.request('/user/profile', as_json=False)
                        stats['success'] += 1
                        log('✅ 个人资料读取完成（仅确认响应，不输出页面）')
                    else:
                        response = client.request('/user/checkin', {})
                        if not verified(response):
                            raise TaskError('签到未获明确业务成功；不凭提示文本推断已签到')
                        stats['success'] += 1
                        log('✅ 签到成功（ret=1）')
                except Exception as exc:
                    stats['failed'] += 1
                    log('❌ ' + (str(exc) if isinstance(exc, TaskError) else '执行异常（详情已脱敏）'))
                    if stage != 2:
                        stats['skipped'] += 3 - stage
                        break
                finally:
                    log(f'阶段 {stage} 耗时：{time.monotonic() - step_start:.2f} 秒')
        stats['account'] = index
        stats['elapsedSeconds'] = round(time.monotonic() - account_start, 3)
        results.append(stats)
        log(f'账号 {index} 统计：总任务 3，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["elapsedSeconds"]} 秒')
    failed = sum(item['failed'] > 0 for item in results)
    passed = len(results) - failed
    status = 'configuration-error' if config_error else ('partial-failure' if failed and passed else 'failure' if failed else 'dry-run' if dry else 'success')
    exit_code = 1 if config_error or failed else 0
    summary = f'账号总数 {len(lines)}，成功 {passed if not dry else 0}，失败 {failed}，预演通过 {passed if dry else 0}；状态 {status}'
    notification = notify(summary, dry)
    log('----------------------------------------')
    log(summary)
    totals = {key: sum(item[key] for item in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log(f'子任务统计：总计 {totals["total"]}，成功 {totals["success"]}，已完成 {totals["alreadyComplete"]}，跳过 {totals["skipped"]}，失败 {totals["failed"]}')
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S} | 总耗时：{time.monotonic() - started:.2f} 秒 | 通知：{notification} | 最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(dict(task=TITLE, mode='dry-run' if dry else 'live', status=status, accountCount=len(lines), successfulAccounts=passed if not dry else 0, failedAccounts=failed, dryRunPassedAccounts=passed if dry else 0, configurationError=config_error, subtasks=totals, accounts=results, notification=notification, exitCode=exit_code), ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
