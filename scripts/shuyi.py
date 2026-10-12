#!/usr/bin/env python3
# name: 书亦烧仙草签到
# cron: 0 9 * * *
# 上游：Rookie-wb-WH/ql_scripts，shuyi.py，MIT 许可。
# 原始声明：脚本仅供学习交流使用, 请在下载后24h内删除。
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
# 上游未声明 cron；本维护版建议每天北京时间 09:00 执行。
"""书亦烧仙草签到（Python 3.9+）。
登录书亦烧仙草小程序，用自己授权的抓包工具查找
scrm-prod.shuyi.org.cn 请求头中的 auth，将原值填入 sysxc_auth。
每个非空行一个账号，不再使用 # 分隔；凭据中的 # 原样保留。
青龙 Python 依赖：opencv-python-headless、numpy、Pillow、pycryptodome。
SHUYI_DRY_RUN=1 完全断网预演，不调用业务、推送或通知网络。
QINGLONG_NOTIFY=0 关闭通知；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
PUSH_PLUS_TOKEN 为可选的既有 PushPlus 通知参数，填写自己的推送令牌。
不发表公共内容，不购物、不兑换积分、不修改用户资料。
"""
import base64
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import time
import uuid
from datetime import datetime
from io import BytesIO
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = '书亦烧仙草签到'
BASE = 'https://scrm-prod.shuyi.org.cn/saas-gateway/api/agg-trade/v1/signIn/'
DISABLED = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def stamp():
    return datetime.now().strftime('%H:%M:%S')


def log(text):
    print(f'[{stamp()}] {text}', flush=True)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('拒绝接口重定向，防止凭据发送至其他地址')


def request_json(url, payload, headers=None, dry=False):
    if dry:
        raise TaskError('预演模式禁止网络请求')
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = Request(url, data=raw, headers={'Content-Type': 'application/json', **(headers or {})}, method='POST')
    try:
        with build_opener(NoRedirect()).open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError('接口 HTTP 状态异常')
            data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise TaskError('接口响应超出大小限制')
        obj = json.loads(data)
        if not isinstance(obj, dict):
            raise TaskError('接口响应结构异常')
        return obj
    except TaskError:
        raise
    except Exception:
        raise TaskError('网络请求失败、超时或响应不是有效 JSON') from None


def accepted(result, code):
    # 仅使用上游已证实的业务码，不能以 HTTP 200 代替业务成功。
    if type(result.get('resultCode')) is not type(code) or result.get('resultCode') != code:
        raise TaskError('接口未返回预期业务成功码，请检查凭据有效期或接口变更')


def identity(result, credential):
    data = result.get('data')
    if not isinstance(data, dict):
        return
    for key in ('nickname', 'nickName', 'username', 'displayName', 'uid', 'publicUid'):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value)
            # 防止意外回显凭据、手机号和日志控制字符；正常官方身份原样显示。
            if credential in text or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text):
                continue
            if any(ord(ch) < 32 for ch in text):
                continue
            log(f'官方账号身份（{key}）：{text}')


def load_dependencies():
    try:
        import cv2
        import numpy as np
        from PIL import Image
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        return cv2, np, Image, AES, pad
    except ImportError:
        raise TaskError('缺少公开依赖：opencv-python-headless、numpy、Pillow 或 pycryptodome') from None


def distance(data, libs):
    cv2, np, Image, _, _ = libs
    arrays = []
    for field in ('originalImageBase64', 'jigsawImageBase64'):
        encoded = data.get(field)
        if not isinstance(encoded, str) or not encoded or len(encoded) > 3 * 1024 * 1024:
            raise TaskError('验证码图片字段缺失或过大')
        try:
            raw = base64.b64decode(encoded, validate=True)
            with Image.open(BytesIO(raw)) as image:
                if image.width * image.height > 4_000_000:
                    raise TaskError('验证码图片尺寸超限')
                arrays.append(cv2.cvtColor(np.asarray(image.convert('RGB')), cv2.COLOR_RGB2BGR))
        except TaskError:
            raise
        except Exception:
            raise TaskError('验证码图片无法解码') from None
    background, puzzle = arrays
    if puzzle.shape[0] > background.shape[0] or puzzle.shape[1] > background.shape[1]:
        raise TaskError('滑块图片尺寸与背景不兼容')
    try:
        matches = cv2.matchTemplate(background, puzzle, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(matches)
        if not math.isfinite(score):
            raise TaskError('滑块识别结果无效')
        return int(location[0])
    except TaskError:
        raise
    except Exception:
        raise TaskError('滑块识别失败') from None


def encrypt(key, text, libs):
    _, _, _, AES, pad = libs
    if not isinstance(key, str) or len(key.encode('utf-8')) not in (16, 24, 32):
        raise TaskError('验证码加密密钥结构异常')
    ciphertext = AES.new(key.encode('utf-8'), AES.MODE_ECB).encrypt(pad(text.encode('utf-8'), 16))
    return base64.b64encode(ciphertext).decode('ascii')


def run_account(index, credential, dry):
    began = time.monotonic()
    stats = {'account': index, 'total': 4, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    headers = {'auth': credential, 'hostname': 'scrm-prod.shuyi.org.cn',
               'User-Agent': 'Mozilla/5.0 MicroMessenger/8.0.30 MiniProgramEnv/android'}
    data, point, verification, libs = None, None, None, None
    names = ('获取验证码', '识别滑块并加密', '校验滑块', '签到并核对积分')
    log(f'账号 {index} 开始')
    for stage, name in enumerate(names, 1):
        started = time.monotonic()
        log(f'账号 {index} 阶段 {stage}/4：{name}')
        try:
            if any(ord(ch) < 32 or ord(ch) > 255 for ch in credential):
                raise TaskError('auth 格式异常：应为请求头原值，不能包含控制字符')
            if dry:
                log(f'⏭️ 账号 {index} {name}：预演计划检查通过，未发送请求')
                stats['skipped'] += 1
            elif stage == 1:
                libs = load_dependencies()
                result = request_json(BASE + 'getVCode', {'captchaType': 'blockPuzzle',
                    'clientUid': 'slider-' + str(uuid.uuid4()), 'ts': int(time.time() * 1000)}, headers)
                accepted(result, 0)
                identity(result, credential)
                data = result.get('data')
                if not isinstance(data, dict) or not isinstance(data.get('token'), str) or not data['token']:
                    raise TaskError('验证码数据或令牌缺失')
                log('✅ 验证码接口业务成功，数据结构通过检查')
            elif stage == 2:
                time.sleep(1.5)
                point = json.dumps({'x': distance(data, libs), 'y': 5}, separators=(',', ':'))
                verification = encrypt(data.get('secretKey'), data['token'] + '---' + point, libs)
                log('✅ 滑块识别和加密完成，不输出坐标签名或会话值')
            elif stage == 3:
                time.sleep(1.5)
                result = request_json(BASE + 'checkVCode', {'captchaType': 'blockPuzzle',
                    'pointJson': encrypt(data.get('secretKey'), point, libs), 'token': data['token']}, headers)
                accepted(result, '0000')
                identity(result, credential)
                log('✅ 滑块校验业务成功')
            else:
                time.sleep(0.5)
                result = request_json(BASE + 'insertSignInV3', {'captchaVerification': verification}, headers)
                accepted(result, 0)
                identity(result, credential)
                reward = result.get('data')
                if not isinstance(reward, dict):
                    raise TaskError('签到结果字段缺失，不能确认积分结果')
                days, points = reward.get('days'), reward.get('pointRewardNum')
                if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in (days, points)):
                    raise TaskError('签到天数或积分结果异常')
                log(f'✅ 签到成功：第 {days} 天，获得 {points} 积分')
            if not dry:
                stats['success'] += 1
        except TaskError as exc:
            stats['failed'] += 1
            stats['skipped'] += 4 - stage
            log(f'❌ 账号 {index} {name}：{exc}；后续 {4-stage} 个阶段跳过')
            break
        except Exception:
            stats['failed'] += 1
            stats['skipped'] += 4 - stage
            log(f'❌ 账号 {index} {name}：本地处理异常，后续阶段跳过')
            break
        finally:
            log(f'账号 {index} 阶段 {stage} 耗时 {time.monotonic()-started:.2f} 秒')
    stats['elapsedSeconds'] = round(time.monotonic() - began, 3)
    stats['status'] = 'failure' if stats['failed'] else ('dry-run' if dry else 'success')
    log(f"账号 {index} 统计：总任务 4，成功 {stats['success']}，已完成 0，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {stats['elapsedSeconds']} 秒")
    return stats


def notify_summary(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        log('⏭️ 通知已通过 QINGLONG_NOTIFY 关闭')
        return 'disabled'
    if dry:
        log('⏭️ 预演通知：已生成脱敏总结，断网模式不加载通知模块或发送推送')
        return 'dry-run'
    delivered = False
    module = None
    try:
        module = importlib.import_module('notify')
    except Exception:
        pass
    if not callable(getattr(module, 'send', None)):
        paths = []
        if os.getenv('QINGLONG_NOTIFY_DIR'):
            paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
        paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
        for path in paths:
            if not path.is_file():
                continue
            try:
                spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if callable(getattr(module, 'send', None)):
                    break
            except Exception:
                module = None
    try:
        if not callable(getattr(module, 'send', None)):
            raise TaskError('青龙通知模块不可用')
        # 通知模块自身可能打印推送响应；隔离其输出，防止凭据泄漏。
        import contextlib
        def timeout_handler(signum, frame):
            raise TaskError('通知发送超时')
        previous_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(20)
        try:
            with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                result = module.send(TITLE, body)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)
        if result is False:
            raise TaskError('通知模块返回失败')
        delivered = True
        log('✅ 青龙通知调用完成')
    except Exception:
        log('⚠️ 青龙通知不可用或发送失败，保留业务退出码')
    if os.getenv('PUSH_PLUS_TOKEN', '').strip():
        try:
            result = request_json('https://www.pushplus.plus/send/', {
                'token': os.environ['PUSH_PLUS_TOKEN'], 'title': TITLE, 'content': body})
            if type(result.get('code')) is not int or result['code'] != 200:
                raise TaskError('PushPlus 业务失败')
            log('✅ PushPlus 推送成功')
        except Exception:
            log('⚠️ PushPlus 推送失败，保留业务退出码')
    return 'sent' if delivered else 'unavailable-or-failed'


def main():
    started = time.monotonic()
    start_time = datetime.now().isoformat(timespec='seconds')
    dry = os.getenv('SHUYI_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    credentials = [line.strip() for line in os.getenv('sysxc_auth', '').splitlines() if line.strip()]
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{start_time}；模式：{"断网预演" if dry else "实际执行"}；账号数：{len(credentials)}')
    results = []
    if not credentials:
        log('❌ 配置错误：请设置 sysxc_auth，每个非空行一个账号的 auth 请求头原值')
    else:
        for index, credential in enumerate(credentials, 1):
            results.append(run_account(index, credential, dry))
    failed = sum(r['failed'] > 0 for r in results)
    successful = sum(r['status'] == 'success' for r in results)
    code = 2 if not credentials else (1 if failed else 0)
    status = 'configuration-error' if not credentials else ('partial-failure' if failed and failed < len(results) else 'failure' if failed else 'dry-run' if dry else 'success')
    body = f'账号总数：{len(credentials)}；成功：{successful}；失败：{failed}；预演：{sum(r["status"] == "dry-run" for r in results)}；最终状态：{status}'
    log('----------------------------------------')
    log(body)
    subtasks = {key: sum(r[key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log('子任务统计：' + json.dumps(subtasks, ensure_ascii=False))
    notification = notify_summary(body, dry)
    finish = datetime.now().isoformat(timespec='seconds')
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status,
        'accountCount': len(credentials), 'successCount': successful, 'failureCount': failed,
        'dryRunCount': sum(r['status'] == 'dry-run' for r in results), 'accounts': results,
        'subtasks': subtasks, 'notification': notification, 'exitCode': code,
        'startTime': start_time, 'finishTime': finish, 'elapsedSeconds': round(time.monotonic()-started, 3)}
    log(f'完成时间：{finish}；总耗时：{summary["elapsedSeconds"]} 秒；通知状态：{notification}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
