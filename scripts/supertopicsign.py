# name: 微博超话签到
# cron: 0 8 * * *
# Source: Hellager/weibo_supertopic_sign, supertopicsign.py
# Upstream license: MIT. Original supplied source contains no copyright notice.
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
"""独立标准库版本。WEIBO_SUPERTOPIC_ACCOUNTS 每行一份 cardlist URL 或查询参数。
抓包微博国际版已登录账号的关注超话页 HTTPS /2/cardlist 请求，复制完整 URL；
保留原请求所有参数（包括 gsid、s、aid、containerid 等），不要公开分享。
兼容 ROW_URL，但账号同样以换行分隔，不再以分号分隔。
IS_SORT 支持 INCREASE/DECREASE/NONE；SIGN_ONCE_COUNT 为每账号请求上限，
0 表示不限。上游配置默认值未随源码提供，本版本默认保持列表顺序、处理全部。
WEIBO_SUPERTOPIC_DRY_RUN=1 完全离线，仅校验参数、模拟流程和通知。
"""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = '微博超话签到'
BASE = 'https://api.weibo.cn'
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


def safe_identity(value, secrets):
    # 身份原样显示；若响应意外混入凭据或手机号则拒绝该字段。
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    value = str(value)
    if not value or len(value) > 120 or re.search(r'[\r\n\x00-\x1f]|1[3-9]\d{9}', value):
        return None
    if any(secret and secret in value for secret in secrets):
        return None
    return value


def parse_account(line):
    if line.startswith(('http://', 'https://')):
        url = urllib.parse.urlsplit(line)
        if url.scheme != 'https' or url.hostname != 'api.weibo.cn' or url.path != '/2/cardlist':
            raise TaskError('凭据 URL 必须是官方 HTTPS /2/cardlist 请求')
        query = url.query
    else:
        query = line.lstrip('?')
    pairs = urllib.parse.parse_qsl(query, keep_blank_values=True, strict_parsing=True)
    params = dict(pairs)
    if len(params) != len(pairs):
        raise TaskError('抓包参数包含重复字段，请重新获取完整请求')
    if not params.get('gsid') or not params.get('s') or not params.get('containerid'):
        raise TaskError('缺少 gsid、s 或 containerid，请重新抓取关注超话页请求')
    return params


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口发生重定向，已阻止凭据转发')


def request(path, params, method='GET'):
    parsed = urllib.parse.urlsplit(path)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith('/2/') or parsed.fragment:
        raise TaskError('签到动作路径不符合官方接口边界')
    query = urllib.parse.urlencode(params)
    url = BASE + path
    data = None
    if method == 'GET':
        url += ('&' if parsed.query else '?') + query
    else:
        data = query.encode('utf-8')
    headers = {'Accept': '*/*', 'Accept-Language': 'zh-Hans-CN;q=1, en-CN;q=0.9',
               'User-Agent': 'WeiboOverseas/4.4.1 (iPhone; iOS 14.7.1; Scale/3.00)',
               'Content-Type': 'application/x-www-form-urlencoded'}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as resp:
            raw = resp.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise TaskError('接口响应超过大小限制')
        result = json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise TaskError(f'官方接口 HTTP {exc.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError('官方接口网络或超时错误') from None
    except (ValueError, UnicodeError):
        raise TaskError('官方接口返回非有效 JSON') from None
    if not isinstance(result, dict):
        raise TaskError('官方接口返回结构错误')
    for field in ('errno', 'error_code'):
        if result.get(field) not in (None, 0, '0'):
            raise TaskError('官方接口业务失败，检查凭据有效性及接口参数')
    return result


def cards_in(cards):
    if not isinstance(cards, list):
        raise TaskError('超话列表 cards 结构错误')
    for card in cards:
        if not isinstance(card, dict):
            raise TaskError('超话卡片结构错误')
        if str(card.get('card_type')) == '8':
            yield card
        if 'card_group' in card:
            yield from cards_in(card['card_group'])


def follow_list(params, secrets):
    topics, seen_topics, seen_cursors = [], set(), set()
    page, cursor, identity = '1', '', None
    for _ in range(100):
        data = dict(params, v_f=page, since_id=cursor)
        result = request('/2/cardlist', data)
        user = result.get('userInfo', result.get('user', {}))
        if isinstance(user, dict):
            for field in ('screen_name', 'name', 'idstr', 'id'):
                identity = safe_identity(user.get(field), secrets)
                if identity:
                    log(f'官方账号身份：{identity}')
                    break
        info = result.get('cardlistInfo')
        if 'cards' not in result or not isinstance(info, dict) or 'since_id' not in info:
            raise TaskError('缺少列表或分页字段，无法确认关注列表完整性')
        next_cursor = info['since_id']
        if not isinstance(next_cursor, (str, int)) or isinstance(next_cursor, bool):
            raise TaskError('分页游标格式错误')
        next_cursor = str(next_cursor)
        for card in cards_in(result['cards']):
            buttons = card.get('buttons')
            if not isinstance(buttons, list) or not buttons or not isinstance(buttons[0], dict):
                raise TaskError('超话签到按钮缺失')
            button = buttons[0]
            status = button.get('name')
            if status not in ('签到', '已签'):
                raise TaskError('未知超话签到状态，无法确认业务成功')
            action = (button.get('params') or {}).get('action', '')
            if status == '签到' and (not isinstance(action, str) or not action):
                raise TaskError('超话签到动作缺失')
            key = card.get('itemid') or action or card.get('title_sub')
            if not key:
                raise TaskError('超话标识缺失')
            if key in seen_topics:
                continue
            seen_topics.add(key)
            level = re.search(r'LV\.?\s*(\d+)', str(card.get('desc1', '')), re.I)
            item_page = re.search(r'super_follow_(\d+)', str(card.get('itemid', '')))
            topics.append({'status': status, 'action': action, 'level': int(level[1]) if level else 0,
                           'page': item_page[1] if item_page else page, 'cursor': next_cursor})
        log(f'列表第 {page} 页读取成功，累计 {len(topics)} 个超话')
        if next_cursor == '':
            return topics
        if next_cursor in seen_cursors:
            raise TaskError('分页游标重复，已停止循环')
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        try:
            page = str(int(json.loads(cursor)['page']))
        except (ValueError, TypeError, KeyError):
            page = str(int(page) + 1)
        time.sleep(random.randint(5, 10))
    raise TaskError('列表超过 100 页安全上限，未确认完整性')


def notify(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').lower() in FALSE:
        return '已关闭'
    if dry:
        log('通知：离线预演摘要已生成，未调用可能联网的通知模块')
        return '离线模拟'
    body = (f"账号总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}；"
            f"状态 {summary['status']}；子任务 {summary['tasks']}")
    try:
        try:
            import notify as module
        except ImportError:
            module = None
            roots = [os.getenv('QINGLONG_NOTIFY_DIR'), '/ql/data/scripts', '/ql/scripts']
            for root in roots:
                if root and (Path(root) / 'notify.py').is_file():
                    spec = importlib.util.spec_from_file_location('ql_notify', Path(root) / 'notify.py')
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, 'send', None)):
            log('⚠️ 通知不可用：未找到 Qinglong notify.py/send')
            return '不可用'
        delivered = []
        def deliver():
            try:
                module.send(TITLE, body)
                delivered.append(True)
            except Exception:
                delivered.append(False)
        worker = threading.Thread(target=deliver, daemon=True)
        worker.start()
        worker.join(timeout=15)
        if worker.is_alive():
            log('⚠️ 通知超过 15 秒，保留业务退出码')
            return '超时'
        if delivered != [True]:
            log('⚠️ 通知失败，保留业务退出码')
            return '失败'
        return '已发送'
    except Exception:
        log('⚠️ 通知失败，保留业务退出码')
        return '失败'


def main():
    started = time.monotonic()
    dry = os.getenv('WEIBO_SUPERTOPIC_DRY_RUN', '0').lower() not in FALSE
    lines = [line.strip() for line in os.getenv('WEIBO_SUPERTOPIC_ACCOUNTS', os.getenv('ROW_URL', '')).splitlines() if line.strip()]
    stats = {'total': 0, 'success': 0, 'already': 0, 'skipped': 0, 'failed': 0}
    summary = {'accounts': len(lines), 'success': 0, 'failed': 0, 'tasks': stats}
    log(f'===== {TITLE} =====')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；模式：{"离线预演" if dry else "实网"}；账号数：{len(lines)}')
    config_error = False
    try:
        sort = os.getenv('IS_SORT', 'NONE').upper()
        limit = int(os.getenv('SIGN_ONCE_COUNT', '0'))
        if sort not in ('NONE', 'INCREASE', 'DECREASE') or limit < 0:
            raise ValueError
        if not lines:
            raise TaskError('未配置 WEIBO_SUPERTOPIC_ACCOUNTS（兼容 ROW_URL）')
    except (ValueError, TaskError):
        config_error = True
        log('❌ 配置错误：需要账号抓包参数、有效排序方式及非负签到上限')
    if not config_error:
        for index, line in enumerate(lines, 1):
            begin = time.monotonic()
            account = dict.fromkeys(stats, 0)
            failed = False
            stage_start = time.monotonic()
            try:
                log(f'账号 {index} / 阶段 1：校验凭据')
                params = parse_account(line)
                log(f'✅ 凭据格式通过；阶段耗时 {time.monotonic() - stage_start:.2f} 秒')
                stage_start = time.monotonic()
                log(f'账号 {index} / 阶段 2：分页读取关注超话')
                topics = ([{'status': '已签', 'level': 2}, {'status': '签到', 'level': 1}] if dry
                          else follow_list(params, [params.get(key, '') for key in ('gsid', 's', 'aid', 'i', 'token', 'access_token')]))
                if sort != 'NONE':
                    topics.sort(key=lambda x: x['level'], reverse=sort == 'DECREASE')
                log(f'✅ 列表读取完成：{len(topics)} 个；阶段耗时 {time.monotonic() - stage_start:.2f} 秒')
                stage_start = time.monotonic()
                log(f'账号 {index} / 阶段 3：{"模拟" if dry else "执行"}签到')
                account['total'] = len(topics)
                attempted = 0
                for number, topic in enumerate(topics, 1):
                    if topic['status'] == '已签':
                        account['already'] += 1
                        log(f'☑️ 超话 {number} 已签到')
                        continue
                    if limit and attempted >= limit:
                        account['skipped'] += 1
                        failed = True
                        log(f'⏭️ 超话 {number} 达到签到上限，任务未全部完成')
                        continue
                    attempted += 1
                    try:
                        if not dry:
                            time.sleep(random.randint(15, 30))
                            result = request(topic['action'], dict(params, v_f=topic['page'], since_id=topic['cursor']), 'POST')
                            if result.get('msg') != '已签到':
                                raise TaskError('未返回已签到确认，签到结果未验证')
                        account['success'] += 1
                        log(f'✅ 超话 {number} {"模拟签到通过" if dry else "签到成功"}')
                    except TaskError as exc:
                        failed = True
                        account['failed'] += 1
                        log(f'❌ 超话 {number}：{exc}')
                log(f'阶段 3 耗时 {time.monotonic() - stage_start:.2f} 秒')
            except (TaskError, ValueError):
                failed = True
                account['failed'] += 1
                log(f'❌ 账号流程失败：凭据、列表或响应未通过校验；阶段耗时 {time.monotonic() - stage_start:.2f} 秒')
            except Exception:
                failed = True
                account['failed'] += 1
                log(f'❌ 账号流程发生未预期错误；阶段耗时 {time.monotonic() - stage_start:.2f} 秒；继续其他账号')
            for key in stats:
                stats[key] += account[key]
            summary['failed' if failed else 'success'] += 1
            log(f'账号 {index} 统计：总任务 {account["total"]}，成功 {account["success"]}，已完成 {account["already"]}，跳过 {account["skipped"]}，失败 {account["failed"]}；耗时 {time.monotonic() - begin:.2f} 秒')
    code = 1 if config_error or summary['failed'] else 0
    summary['status'] = ('configuration-error' if config_error else 'partial-failure' if summary['failed'] and summary['success'] else 'failure' if code else 'dry-run' if dry else 'success')
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['finishTime'] = datetime.datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log(f'最终统计：账号总数 {len(lines)}，成功 {summary["success"]}，失败 {summary["failed"]}；子任务 {stats}')
    log(f'完成时间：{summary["finishTime"]}；总耗时 {summary["elapsedSeconds"]} 秒；通知：{summary["notification"]}；最终状态：{summary["status"]}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
