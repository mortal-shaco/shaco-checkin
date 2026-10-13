# name: 华润通Ole签到
# cron: 1 1 1 1 1
# 上游：Cat-zaizai/ZaiZaiCat-Checkin，script/huaruntong/ole/main.py 和 api.py
# 上游提交：d6a334e43d0a0c8f41b039cd410be33593efc35b；许可证：MIT
"""独立签到任务。OLE_ACCOUNTS 每个非空行为一个 JSON 账号对象。

字段：session_id、device_name、unique、ole_wx_open_id 必填；shop_code、
city_id、user_agent 可选。旧 token.json 内容可直接放入 OLE_CONFIG_JSON，
保留 huaruntong.ole.accounts 结构；不读取私有仓库文件。
在本人授权的 Ole 微信小程序请求中获取对应请求头；不要分享凭据。
OLE_DRY_RUN=1 完全断网，仅验证参数并模拟请求与通知，不表示真实签到成功。

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
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime
import urllib.request
import urllib.error

URL = 'https://ole-app.crvole.com.cn/vgdt_app_api/v1/vgdt-fea-app-member/front_api/member_sign'
USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 '
              'MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI '
              'MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) '
              'UnifiedPCMacWechat(0xf26405f0) XWEB/13910')
REQUIRED = ('session_id', 'device_name', 'unique', 'ole_wx_open_id')
FALSE_VALUES = ('0', 'false', 'no', 'off')


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def load_accounts():
    raw = os.getenv('OLE_ACCOUNTS', '')
    if raw.strip():
        # Keep malformed lines as independent account failures.
        return [line for line in raw.splitlines() if line.strip()]
    legacy = os.getenv('OLE_CONFIG_JSON', '')
    if legacy.strip():
        config = json.loads(legacy)
        accounts = config['huaruntong']['ole']['accounts']
        if not isinstance(accounts, list):
            raise ValueError('配置结构无效')
        return accounts
    return []


def parse_account(raw):
    account = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(account, dict):
        raise ValueError('账号必须是 JSON 对象')
    for key in REQUIRED:
        value = account.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'缺少非空字符串字段 {key}')
    for key in (*REQUIRED, 'shop_code', 'city_id', 'user_agent'):
        if key in account and (not isinstance(account[key], str)
                               or not account[key].strip()
                               or '\r' in account[key] or '\n' in account[key]):
            raise ValueError(f'字段 {key} 格式无效')
    return account


def request_for(account):
    shop = account.get('shop_code', '205368')
    headers = {
        'User-Agent': account.get('user_agent', USER_AGENT),
        'Content-Type': 'application/json', 'Tenant-Channel': 'OLE',
        'cityId': account.get('city_id', 'c_region_11122'),
        'oleWxOpenId': account['ole_wx_open_id'], 'Tenant': 'VGDT',
        'sessionId': account['session_id'], 'Device-Name': account['device_name'],
        'unique': account['unique'], 'channel': 'wxmini', 'shopCode': shop,
        'os': 'ios', 'appVersion': '1.10.17',
        'Referer': 'https://servicewechat.com/wx6c61aaeba1551439/93/page-frame.html',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    return urllib.request.Request(URL, data=json.dumps(
        {'enter_shop_code': shop}).encode('utf-8'), headers=headers, method='POST')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward account headers to a redirect target.
        return None


def sign_in(account):
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request_for(account), timeout=15) as response:
            if response.status != 200:
                return False, 'HTTP 状态不符合预期', None
            raw = response.read(65537)
        if len(raw) > 65536:
            return False, '响应过大', None
        result = json.loads(raw)
        if not isinstance(result, dict):
            return False, '响应结构无效', None
        # No documented business codes are present in the supplied sources.
        # Do not equate transport success or an arbitrary code with check-in.
        identity = None
        data = result.get('data')
        for container in (result, data):
            if isinstance(container, dict):
                for field in ('nickname', 'username', 'displayName', 'publicUid'):
                    value = container.get(field)
                    if isinstance(value, (str, int)) and not isinstance(value, bool):
                        value = str(value)
                        # Suppress credential echoes, phone numbers and control characters.
                        if (value and not any(str(account[k]) in value for k in REQUIRED)
                                and not any(c in value for c in '\r\n\x1b')
                                and not (value.isdigit() and len(value) == 11)):
                            identity = value
                            break
        ok = result.get('success') is True and not result.get('error')
        return ok, '签到成功（业务 success=true）' if ok else '业务未明确确认成功', identity
    except urllib.error.HTTPError as exc:
        return False, f'HTTP 请求失败，状态码 {exc.code}', None
    except (urllib.error.URLError, TimeoutError, OSError):
        return False, '网络请求失败或超时', None
    except (ValueError, UnicodeError):
        return False, '响应不是有效 JSON', None


def notify_summary(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in FALSE_VALUES:
        return '已关闭'
    if dry:
        log('⏭️ 断网预演：已生成通知摘要，模拟通知投递')
        return '预演模拟'
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            paths = []
            if os.getenv('QINGLONG_NOTIFY_DIR'):
                paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            paths.extend((Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')))
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('ql_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
            if module is None:
                log('⚠️ 未发现青龙 notify.py，保留业务退出码')
                return '不可用'
        module.send('华润通Ole签到', body)
        return '已发送'
    except Exception:
        log('⚠️ 通知投递失败，保留业务退出码')
        return '失败'


def main():
    begin = time.monotonic()
    dry = os.getenv('OLE_DRY_RUN', '0').strip().lower() in ('1', 'true', 'yes', 'on')
    log('========== 华润通Ole签到 ==========')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if dry else "正式签到"}')
    configuration_error = False
    try:
        accounts = load_accounts()
    except Exception:
        accounts = []
        configuration_error = True
        log('❌ 账号配置结构无效（已隐藏输入）')
    if not accounts:
        configuration_error = True
        log('❌ 请配置 OLE_ACCOUNTS，每个非空行一个 JSON 账号对象')
    log(f'账号总数：{len(accounts)}')
    results = []
    for index, raw in enumerate(accounts, 1):
        start = time.monotonic()
        ok = False
        log(f'账号 {index} / 阶段 1：参数检查')
        try:
            account = parse_account(raw)
            log(f'账号 {index} / 阶段 1：✅ 参数检查通过；耗时 {time.monotonic()-start:.2f} 秒')
            stage = time.monotonic()
            log(f'账号 {index} / 阶段 2：签到')
            if dry:
                request_for(account)
                ok, message, identity = True, 'DRY_RUN_OK：请求构造通过，未发起网络请求', None
            else:
                ok, message, identity = sign_in(account)
            if identity is not None:
                log(f'账号 {index} 官方身份：{identity}')
            log(f'账号 {index} / 阶段 2：{"✅" if ok else "❌"} {message}；耗时 {time.monotonic()-stage:.2f} 秒')
        except ValueError:
            log(f'账号 {index} / 阶段 1：❌ JSON 或必需字段无效；耗时 {time.monotonic()-start:.2f} 秒')
        except Exception:
            log(f'账号 {index}：❌ 执行异常（已隐藏敏感详情）')
        results.append(ok)
        log(f'账号 {index} 统计：总任务 1，成功 {int(ok and not dry)}，已完成 0，跳过 {int(ok and dry)}，失败 {int(not ok)}；耗时 {time.monotonic()-start:.2f} 秒')
    passed = sum(results)
    failed = len(results) - passed
    exit_code = int(configuration_error or failed > 0)
    status = ('configuration-error' if configuration_error else
              'partial-failure' if failed and passed else
              'failure' if failed else 'dry-run' if dry else 'success')
    body = f'状态：{status}；账号总数：{len(results)}；成功数：{passed if not dry else 0}；失败数：{failed}；预演通过数：{passed if dry else 0}'
    log('----------------------------------------')
    log(body)
    notification = notify_summary(body, dry)
    log(f'通知状态：{notification}')
    log(f'子任务统计：总计 {len(results)}，成功 {passed if not dry else 0}，已完成 0，跳过 {passed if dry else 0}，失败 {failed}')
    log(f'总耗时：{time.monotonic()-begin:.2f} 秒；完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({
        'status': status, 'accounts': len(results), 'success': passed if not dry else 0,
        'failed': failed, 'dryRunPassed': passed if dry else 0,
        'configurationError': configuration_error, 'notification': notification,
        'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
