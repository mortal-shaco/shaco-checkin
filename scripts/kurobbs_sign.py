#!/usr/bin/env python3
# name: 鸣潮·库街区 每日签到
# cron: 3 0 * * *
"""独立维护版本，来源 yongyeym/AutoSign_QingLong/kurobbs_sign.py。
上游许可：MIT。原始文件没有额外版权声明。
配置 KUROBBS_ACCOUNTS：每个非空行一个账号，格式 社区UID|Token，只分割第一个 |。
登录官方库街区 App，使用本人授权的抓包工具从 api.kurobbs.com 请求头获取 token，
从角色查询 queryUserId 或签到 userId 获取社区 UID（不是鸣潮角色 UID）。不要公开抓包。
兼容旧单账号 kurobbs（Token）和 kuro_uid（社区 UID），不再读取私人 ini 文件。
KUROBBS_DRY_RUN=1 完全断网预演。点赞/分享默认关闭，分别用 KUROBBS_LIKE=1、
KUROBBS_SHARE=1 开启；分享仅提交进度，不发布文字。没有取消点赞、补签或消费操作。
通知使用青龙 notify.py；预演仅演练通知，不调用可能联网的通知函数。

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
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import datetime as dt
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

TITLE = '鸣潮·库街区 每日签到'
SECRETS = []
DISABLED = {'0', 'false', 'no', 'off'}


def enabled(name, default='0'):
    value = os.getenv(name, default).strip().lower()
    if value not in {'1', 'true', 'yes', 'on'} | DISABLED:
        raise ValueError('开关配置无效：' + name)
    return value not in DISABLED


def safe(value):
    text = str(value).replace('\n', ' ').replace('\r', ' ')
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(c for c in text if c.isprintable())


def log(text):
    print('[' + dt.datetime.now().strftime('%H:%M:%S') + '] ' + safe(text), flush=True)


class BusinessError(Exception):
    pass


class Client:
    def __init__(self, uid, token, dry):
        self.uid, self.token, self.dry = uid, token, dry
        self.device = uuid.uuid4().hex
        self.distinct = uuid.uuid4().hex + '_9'
        # 禁止重定向，避免 Token 被转发至其他主机；各账号不共享 Cookie。
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, path, data, style=2, accepted=()):
        if self.dry:
            raise BusinessError('预演禁止 HTTP 请求')
        agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)  KuroGameBox/3.1.4'
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'source': 'ios',
                   'Accept-Language': 'zh-CN,zh-Hans;q=0.9', 'token': self.token}
        if style == 1:
            headers.update({'User-Agent': agent, 'Accept': 'application/json, text/plain, */*',
                            'Origin': 'https://web-static.kurobbs.com', 'Sec-Fetch-Site': 'same-site',
                            'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty', 'Priority': 'u=3, i',
                            'devCode': '119.161.168.10, ' + agent})
        else:
            headers.update({'User-Agent': 'KuroGameBox/20260706191836 CFNetwork/3860.600.12 Darwin/25.5.0',
                            'channelId': '1', 'version': '3.1.4', 'distinct_id': self.distinct,
                            'channel': 'appstore', 'Accept': '*/*', 'devCode': self.device,
                            'ip': '192.168.1.2', 'lang': 'zh-Hans', 'model': 'iPhone15,4', 'osVersion': '26.5.2'})
        req = urllib.request.Request('https://api.kurobbs.com/' + path,
                                     urllib.parse.urlencode(data).encode(), headers, method='POST')
        # 写操作不自动重试，超时后由下次定时任务重新查询状态。
        try:
            with self.opener.open(req, timeout=15) as response:
                raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise BusinessError('响应过大')
                result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise BusinessError('HTTP 状态 ' + str(exc.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise BusinessError('网络失败或超时，未自动重试写操作') from None
        except (ValueError, UnicodeError):
            raise BusinessError('响应不是有效 JSON') from None
        if not isinstance(result, dict) or type(result.get('code')) is not int:
            raise BusinessError('响应缺少有效业务码')
        code = result['code']
        if code not in (200, *accepted):
            raise BusinessError('Token 已失效，请更新凭据' if code == 220 else '业务失败，代码 ' + str(code))
        log('接口 ' + path + '：业务码 ' + str(code))
        # 仅展示明确的公开身份字段，不输出响应正文或设备、会话等字段。
        data = result.get('data')
        if isinstance(data, dict):
            for key in ('nickname', 'nickName', 'username', 'userName', 'displayName', 'userId'):
                if isinstance(data.get(key), (str, int)):
                    log('官方账号身份 ' + key + '：' + str(data[key]))
        return result

    def progress(self):
        tasks = self.call('encourage/level/getTaskProcess', {'gameId': '0'})['data']['dailyTask']
        wanted = {'浏览3篇帖子': 'read', '点赞5次': 'like', '分享1次帖子': 'share', '用户签到': 'bbs'}
        result = {}
        for item in tasks:
            if item['remark'] in wanted:
                need, done = item['needActionTimes'], item['completeTimes']
                if type(need) is not int or type(done) is not int or not 0 <= need <= 100 or done < 0:
                    raise BusinessError('任务进度字段无效')
                result[wanted[item['remark']]] = max(0, need - done)
        if set(result) != set(wanted.values()):
            raise BusinessError('每日任务响应不完整，不能判定完成')
        return result


def game_state(client, role):
    data = client.call('encourage/signIn/initSignInV2', role, 1)['data']
    if type(data['isSigIn']) is not bool or type(data['sigInNum']) is not int:
        raise BusinessError('游戏签到状态无效')
    return data


def show_rewards(data):
    day = data['sigInNum'] + (not data['isSigIn'])
    log('鸣潮本月签到天数（含今日计划）：' + str(day))
    lists = [('普通奖励', data.get('signInGoodsConfigs', []), day)]
    if 'loopSignName' in data:
        lists.append(('限时活动「' + str(data['loopSignName']) + '」', data['signLoopGoodsList'],
                      data['loopSignNum'] + (not data['isSigIn'])))
    for label, items, count in lists:
        for item in items:
            if item['serialNum'] == count - 1:
                log(label + '：' + str(item['goodsName']) + ' × ' + str(item['goodsNum']))
                break


def run_account(index, uid, token, dry, like, share):
    started = time.monotonic()
    stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0)
    client = Client(uid, token, dry)
    state = {}

    def stage(name, action):
        stats['total'] += 1
        tick = time.monotonic()
        log(f'账号 {index} 阶段 {stats["total"]}：{name}')
        try:
            outcome = 'skipped' if dry else action()
            stats[outcome or 'success'] += 1
            log(('⏭️ 预演，不发起请求：' if dry else '阶段结果：' + str(outcome or 'success') + '；') + name)
        except Exception as exc:
            stats['failure'] += 1
            log('❌ ' + (str(exc) if isinstance(exc, BusinessError) else '响应结构异常或步骤执行失败'))
        log(f'阶段耗时 {time.monotonic() - tick:.2f} 秒')

    def inspect():
        state['progress'] = client.progress()
        log('剩余任务：' + '、'.join(k + '=' + str(v) for k, v in state['progress'].items()))

    stage('查询社区任务进度', inspect)

    def community():
        result = client.call('user/signIn', {'gameId': '2', 'geeTestData': ''}, accepted=(1551,))
        if result['code'] == 1551:
            return 'alreadyComplete'
        data = result['data']
        log(f'社区签到成功：连续 {int(data["continueDays"])} 天，累计 {int(data["totalSignInDay"])} 天')
        for gain in data['gainVoList']:
            log(('库洛币' if gain['gainTyp'] == 2 else '签到奖励') + ' × ' + str(int(gain['gainValue'])))
        if client.progress()['bbs'] != 0:
            raise BusinessError('社区签到后进度未完成')
        return 'success'

    stage('库街区社区签到', community)

    def game():
        roles = client.call('user/role/findUserDefaultRole', {'queryUserId': uid})['data']['defaultRoleList']
        found = next((r for r in roles if r.get('gameId') == 3), None)
        if not found or not found.get('roleId') or not found.get('serverId'):
            raise BusinessError('未找到鸣潮默认绑定角色，请先在官方 App 绑定')
        for key in ('nickname', 'nickName', 'username', 'userName', 'displayName', 'roleName', 'userId', 'roleId'):
            if found.get(key) is not None:
                log('官方账号身份 ' + key + '：' + str(found[key]))
        role = {'gameId': '3', 'serverId': found['serverId'], 'roleId': found['roleId'], 'userId': uid}
        before = game_state(client, role)
        show_rewards(before)
        if before['isSigIn']:
            return 'alreadyComplete'
        result = client.call('encourage/signIn/v2', {**role, 'reqMonth': dt.datetime.now().strftime('%m')}, 1, (1511,))
        if not game_state(client, role)['isSigIn']:
            raise BusinessError('鸣潮签到后状态未完成')
        log('鸣潮游戏签到成功' if result['code'] == 200 else '鸣潮游戏今天已经签到')
        return 'success' if result['code'] == 200 else 'alreadyComplete'

    stage('鸣潮角色、签到及普通和限时奖励', game)

    def interact(kind):
        if (kind == 'like' and not like) or (kind == 'share' and not share):
            log('显式开关未开启，跳过互动')
            return 'skipped'
        remaining = client.progress()[kind]
        if remaining == 0:
            return 'alreadyComplete'
        # 最多刷新三页；使用不同帖子，不取消原有点赞，不伪造循环互动。
        for page in range(1, 4):
            posts = client.call('forum/list', {'forumId': '10', 'gameId': '3', 'pageIndex': str(page),
                                              'pageSize': '20', 'searchType': '1', 'timeType': '0', 'topicId': ''})['data']['postList']
            for post in posts:
                base = {'postId': post['postId']}
                if kind == 'read':
                    path, payload = 'forum/getPostDetail', {**base, 'isOnlyPublisher': '0', 'showOrderType': '2'}
                elif kind == 'like':
                    path, payload = 'forum/like', {**base, 'forumId': '10', 'gameId': '3', 'likeType': '1',
                                                  'operateType': '1', 'postCommentId': '0', 'postCommentReplyId': '0',
                                                  'postType': '1', 'toUserId': post['userId']}
                else:
                    path, payload = 'encourage/level/shareTask', {**base, 'gameId': '3'}
                response = client.call(path, payload, accepted=(522,))
                if response['code'] == 522:
                    log('帖子已删除，尝试后续帖子')
                    continue
                time.sleep(3 if kind != 'like' else 1)
                remaining = client.progress()[kind]
                log('互动后的剩余次数：' + str(remaining))
                if remaining == 0:
                    return 'success'
        raise BusinessError('达到安全尝试上限，互动进度仍未完成')

    for kind, name in [('read', '浏览帖子'), ('like', '点赞帖子'), ('share', '提交分享进度')]:
        stage(name, lambda kind=kind: interact(kind))
    stats['elapsedSeconds'] = round(time.monotonic() - started, 2)
    stats['account'] = index
    stats['status'] = 'failure' if stats['failure'] else ('dry-run' if dry else 'success')
    log('账号统计：' + json.dumps(stats, ensure_ascii=False))
    return stats


def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    if dry:
        log('通知预演：' + body)
        return '预演，未联网发送'
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            paths = [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
            if os.getenv('QINGLONG_NOTIFY_DIR'):
                paths.insert(0, Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                log('⚠️ 通知模块不可用；保留业务退出码')
                return '不可用'
            spec = importlib.util.spec_from_file_location('qinglong_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.send(TITLE, safe(body))
        return '已发送'
    except Exception:
        log('⚠️ 通知失败；保留业务退出码')
        return '失败'


def main():
    tick = time.monotonic()
    start = dt.datetime.now().isoformat(timespec='seconds')
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + start)
    accounts, results, config_error = [], [], False
    dry = os.getenv('KUROBBS_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    try:
        dry = enabled('KUROBBS_DRY_RUN')
        like, share = enabled('KUROBBS_LIKE'), enabled('KUROBBS_SHARE')
        raw = os.getenv('KUROBBS_ACCOUNTS', '')
        if raw.strip():
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
        else:
            uid, token = os.getenv('kuro_uid', ''), os.getenv('kurobbs', '')
            lines = [uid + '|' + token] if uid or token else []
        if not lines:
            raise ValueError('缺少 KUROBBS_ACCOUNTS；每行 社区UID|Token')
        for line in lines:
            # 错误账号保留位置，不能阻止其他账号运行。
            uid, delimiter, token = line.partition('|')
            uid, token = uid.strip(), token.strip()
            SECRETS.append(token)
            valid = bool(delimiter and uid.isdecimal() and token and not any(ord(c) < 32 or ord(c) > 126 for c in token))
            accounts.append((uid, token, valid))
    except ValueError as exc:
        config_error = True
        log('❌ 配置错误：' + str(exc))
    log('运行模式：' + ('断网预演' if dry else '正式执行'))
    log('账号数量：' + str(len(accounts)))
    for index, (uid, token, valid) in enumerate(accounts, 1):
        if valid:
            results.append(run_account(index, uid, token, dry, like, share))
        else:
            config_error = True
            log(f'账号 {index} 配置错误：需要数字社区 UID 和非空 Token')
            results.append(dict(account=index, status='configuration-error', total=1, success=0,
                                alreadyComplete=0, skipped=0, failure=1, elapsedSeconds=0))
    failed = sum(r['failure'] > 0 for r in results)
    code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else 'partial-failure' if failed and failed < len(results)
              else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status, 'accounts': len(accounts),
               'successfulAccounts': 0 if dry else len(results) - failed, 'failedAccounts': failed,
               'dryRunAccounts': len(results) - failed if dry else 0, 'accountResults': results, 'exitCode': code}
    body = f'状态：{status}；账号总数：{len(accounts)}；成功：{summary["successfulAccounts"]}；失败：{failed}；预演：{summary["dryRunAccounts"]}'
    summary['notification'] = notify(body, dry)
    summary['elapsedSeconds'] = round(time.monotonic() - tick, 2)
    summary['finishTime'] = dt.datetime.now().isoformat(timespec='seconds')
    summary['taskStatistics'] = {key: sum(r[key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    log('----------------------------------------')
    log('任务统计：' + body + '；子任务：' + json.dumps(summary['taskStatistics'], ensure_ascii=False))
    log(f'总耗时：{summary["elapsedSeconds"]} 秒；通知：{summary["notification"]}')
    log('完成时间：' + summary['finishTime'] + '；最终状态：' + status)
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
