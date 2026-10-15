#!/usr/bin/env python3
# name: Epic免费游戏
# cron: 11 8 * * 6
# new Env("Epic免费游戏")
# 来源: CN-Grace/QinglongScripts, EpicFreeGames.py
# 上游许可及本维护版本许可: MIT
# Copyright (c) CN-Grace/QinglongScripts contributors
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
"""Epic Games 每周免费游戏提醒（不会登录或自动领取游戏）。
EPIC_TG_ACCOUNTS 必填，每个非空行一个机器人令牌|会话编号，只按首个 | 分割。
通过 Telegram 的 BotFather 创建机器人获取令牌；向机器人发送消息后，
在 Telegram 官方 Bot API getUpdates 的 message.chat.id 获取会话编号。
兼容 TG_BOT_TOKEN / TG_USER_ID（仅单账号）；不要使用 & 或 @ 分隔账号。
EPIC_LOCALE=zh-CN, EPIC_COUNTRY=CN；每周六 08:00，按青龙时区调度。
EPIC_FONT_PATH 可选，填写自行安装的中文字体路径；不下载字体。
图像需要公开 PyPI 包 Pillow；无可用中文字体或图像失败则推送完整文字。
EPIC_DRY_RUN=1 完全断网预演，使用本地数据，不实际推送任何通知。
QINGLONG_NOTIFY=0 关闭青龙汇总通知；不影响 Telegram 业务提醒。
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, quote
from urllib.request import Request, urlopen

TZ = timezone(timedelta(hours=8))
EPIC_URL = 'https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions'
DISABLED = {'0', 'false', 'no', 'off'}
DRY = os.getenv('EPIC_DRY_RUN', '0').lower() in {'1', 'true', 'yes', 'on'}
LOCALE = os.getenv('EPIC_LOCALE', 'zh-CN')
COUNTRY = os.getenv('EPIC_COUNTRY', 'CN')


def log(message):
    print(f'[{datetime.now(TZ):%H:%M:%S}] {message}', flush=True)


def http(url, payload=None, content_type=None, limit=8 * 1024 * 1024):
    if DRY:
        raise RuntimeError('断网预演禁止 HTTP')
    if urlparse(url).scheme != 'https':
        raise ValueError('只允许 HTTPS')
    headers = {'User-Agent': 'EpicFreeGames/maintained', 'Accept': 'application/json'}
    if content_type:
        headers['Content-Type'] = content_type
    req = Request(url, data=payload, headers=headers)
    with urlopen(req, timeout=30) as response:
        if response.status != 200:
            raise ValueError('HTTP 状态异常')
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError('响应超过大小限制')
        return body


def bj_time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('促销时间缺少时区')
    return parsed.astimezone(TZ).strftime('%m-%d %H:%M')


def dates(blocks):
    result = []
    for block in blocks:
        for offer in block.get('promotionalOffers', []):
            setting = offer.get('discountSetting', {})
            pct = setting.get('discountPercentage') if isinstance(setting, dict) else None
            if isinstance(setting, str):
                match = re.search(r'discountPercentage=(\d+)', setting)
                pct = match.group(1) if match else None
            if str(pct) == '0':
                start, end = offer.get('startDate'), offer.get('endDate')
                if not start or not end:
                    raise ValueError('免费促销缺少时间字段')
                # 校验后按完整日期排序，避免跨年顺序错误。
                bj_time(start)
                bj_time(end)
                result.append((start, end))
    return sorted(result, key=lambda pair: datetime.fromisoformat(pair[1].replace('Z', '+00:00')))


def parse_free_games(data):
    if not isinstance(data, dict) or data.get('errors'):
        raise ValueError('官方业务响应异常')
    elements = data['data']['Catalog']['searchStore']['elements']
    if not isinstance(elements, list):
        raise ValueError('商品列表结构异常')
    current, upcoming = [], []
    for elem in elements:
        if elem.get('offerType') != 'BASE_GAME' or elem.get('status') != 'ACTIVE':
            continue
        promotions = elem.get('promotions')
        if not promotions:
            continue
        price = elem.get('price', {}).get('totalPrice', {})
        slug = elem.get('urlSlug') or elem.get('productSlug', '').replace('/home', '')
        images = elem.get('keyImages', [])
        cover = ''
        for kind in ('DieselStoreFrontWide', 'OfferImageTall', 'Thumbnail', 'OfferImageWide', 'featuredMedia'):
            cover = next((item.get('url', '') for item in images if item.get('type') == kind), '')
            if cover:
                break
        if not cover and images:
            cover = images[0].get('url', '')
        game = {'title': elem.get('title', 'Unknown'), 'image': cover,
                'price': {'original': price.get('fmtPrice', {}).get('originalPrice', 'N/A')},
                'url': f'https://store.epicgames.com/{quote(LOCALE)}/p/{quote(slug)}' if slug else ''}
        now_dates = dates(promotions.get('promotionalOffers', []))
        future_dates = dates(promotions.get('upcomingPromotionalOffers', []))
        if price.get('discountPrice', -1) == 0 and now_dates:
            start, end = now_dates[0]
            current.append(dict(game, free_start=bj_time(start), free_end=bj_time(end)))
        if future_dates and game['title'] not in {g['title'] for g in current}:
            start, end = future_dates[0]
            upcoming.append(dict(game, free_start=bj_time(start), free_end=bj_time(end)))
    return current, upcoming


def build_text_report(current, upcoming):
    lines = ['Epic Games 每周免费游戏', '']
    for games, title in ((current, '本周免费'), (upcoming, '即将免费')):
        if games:
            lines.append(f'[ {title} {len(games)} 款 ]')
            for game in games:
                lines.append(f"{game['title']} (原价 {game['price']['original']}) {game['free_start']} ~ {game['free_end']} 北京时间")
                if game['url']:
                    lines.append(game['url'])
    if not current and not upcoming:
        lines.append('暂无免费游戏')
    lines.append(f'https://store.epicgames.com/{LOCALE}/free-games')
    return '\n'.join(lines)


def build_image(current, upcoming):
    from PIL import Image, ImageDraw, ImageFont
    # 本地公开安装的字体可选；没有中文字体就沿用文字降级，不做安装引导。
    paths = [os.getenv('EPIC_FONT_PATH', ''), '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
             '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    font_path = next((p for p in paths if p and Path(p).is_file()), None)
    if not font_path:
        raise ValueError('缺少本地中文字体')
    large = ImageFont.truetype(font_path, 26)
    small = ImageFont.truetype(font_path, 18)
    sections = [(current, '本周免费', (70, 130, 220)), (upcoming, '即将免费', (220, 160, 60))]
    rows = sum((len(games) + 1) // 2 for games, _, _ in sections)
    if rows > 30:
        raise ValueError('图片内容过多')
    canvas = Image.new('RGB', (800, 100 + rows * 510 + 2 * 65), (22, 22, 28))
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 18), 'Epic Games 免费游戏', font=large, fill='white')
    draw.text((590, 28), f'{datetime.now(TZ):%Y-%m-%d}', font=small, fill='white')
    y = 70
    for games, title, color in sections:
        if not games:
            continue
        draw.rectangle((0, y, 800, y + 55), fill=color)
        draw.text((24, y + 12), f'{title} {len(games)} 款', font=large, fill='white')
        y += 65
        for index in range(0, len(games), 2):
            for col, game in enumerate(games[index:index + 2]):
                x = 24 + col * 390
                draw.rectangle((x, y, x + 350, y + 340), fill=(32, 32, 40))
                try:
                    body = http(game['image'], limit=8 * 1024 * 1024)
                    with Image.open(io.BytesIO(body)) as cover:
                        cover.load()
                        canvas.paste(cover.convert('RGB').resize((350, 340)), (x, y))
                except Exception:
                    log('⚠️ 封面不可用，保留游戏资料卡片')
                # 按像素宽度断行，最多两行。
                remaining = game['title']
                for line in range(2):
                    n = len(remaining)
                    while n and draw.textbbox((0, 0), remaining[:n], font=large)[2] > 350:
                        n -= 1
                    text = remaining[:n]
                    remaining = remaining[n:]
                    if line == 1 and remaining:
                        text = text[:-1] + '…'
                    draw.text((x, y + 350 + line * 32), text, font=large, fill='white')
                draw.text((x, y + 420), f"FREE  原价 {game['price']['original']}", font=small, fill=(80, 200, 120))
                draw.text((x, y + 450), f"{game['free_start']} 起", font=small, fill='white')
                draw.text((x, y + 475), f"{game['free_end']} 截止", font=small, fill='white')
            y += 510
    buffer = io.BytesIO()
    canvas.crop((0, 0, 800, y + 10)).save(buffer, format='JPEG', quality=75)
    result = buffer.getvalue()
    if len(result) > 10 * 1024 * 1024:
        raise ValueError('图片超过 Telegram 限制')
    return result


def telegram(token, chat, action, text, photo=None):
    url = f'https://api.telegram.org/bot{token}/{action}'
    if photo is None:
        body = urlencode({'chat_id': chat, 'text': text}).encode()
        content_type = 'application/x-www-form-urlencoded'
    else:
        boundary = 'EpicFreeGames' + os.urandom(12).hex()
        parts = []
        for key, value in (('chat_id', chat), ('caption', text)):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="epic.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode() + photo + b'\r\n')
        body = b''.join(parts) + f'--{boundary}--\r\n'.encode()
        content_type = f'multipart/form-data; boundary={boundary}'
    result = json.loads(http(url, body, content_type, limit=1024 * 1024))
    if result.get('ok') is not True or not isinstance(result.get('result'), dict) or not result['result'].get('message_id'):
        raise ValueError('Telegram 未确认消息成功')
    identity = result['result'].get('from', {})
    if isinstance(identity, dict):
        label = identity.get('username') or identity.get('first_name')
        if isinstance(label, str) and label:
            log(f'Telegram 官方机器人身份：{label}')


def split_messages(text, limit=3500):
    # 限制 UTF-16 长度，适配 Telegram 对非 BMP 字符的计数。
    part, count = '', 0
    for char in text:
        size = len(char.encode('utf-16-le')) // 2
        if count + size > limit:
            yield part
            part, count = '', 0
        part += char
        count += size
    if part:
        yield part


def read_accounts():
    value = os.getenv('EPIC_TG_ACCOUNTS', '')
    if not value.strip():
        token, chat = os.getenv('TG_BOT_TOKEN', ''), os.getenv('TG_USER_ID', '')
        if token or chat:
            value = token + '|' + chat
    return [line.strip() for line in value.splitlines() if line.strip()]


def parse_account(line):
    token, chat = line.split('|', 1)
    token, chat = token.strip(), chat.strip()
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token) or not re.fullmatch(r'-?\d+|@[A-Za-z0-9_]+', chat):
        raise ValueError('账号参数格式错误')
    return token, chat


def notify_summary(summary):
    if os.getenv('QINGLONG_NOTIFY', '1').lower() in DISABLED:
        return '已关闭'
    if DRY:
        log('⏭️ 断网预演：青龙通知仅模拟，不加载通知模块')
        return '预演已模拟'
    title = 'Epic免费游戏'
    body = (f"账号总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}\n"
            f"状态 {summary['status']}；本周 {summary['current']} 款，即将 {summary['upcoming']} 款")
    paths = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths.extend([Path(__file__).parent / 'notify.py', Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    # 通知器可能输出包含凭据的底层错误，抑制其输出并仅报告状态。
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import importlib
            try:
                module = importlib.import_module('notify')
            except ImportError:
                path = next((p for p in paths if p.is_file()), None)
                if path is None:
                    return '不可用（业务退出码保持不变）'
                spec = importlib.util.spec_from_file_location('epic_ql_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            result = module.send(title, body)
            if result is False:
                return '失败（业务退出码保持不变）'
        return '已调用青龙通知'
    except Exception:
        return '失败（业务退出码保持不变）'


def fixture():
    def game(title, upcoming=False):
        return {'title': title, 'status': 'ACTIVE', 'offerType': 'BASE_GAME', 'keyImages': [],
                'price': {'totalPrice': {'discountPrice': 100 if upcoming else 0, 'fmtPrice': {'originalPrice': '¥100'}}},
                'promotions': {'upcomingPromotionalOffers' if upcoming else 'promotionalOffers': [{'promotionalOffers': [
                    {'discountSetting': {'discountPercentage': 0}, 'startDate': '2026-10-15T15:00:00Z', 'endDate': '2026-10-22T15:00:00Z'}]}]}}
    return {'data': {'Catalog': {'searchStore': {'elements': [game('本地预演游戏'), game('预演即将免费游戏', True)]}}}}


def main():
    started = time.monotonic()
    lines = read_accounts()
    summary = {'accounts': len(lines), 'success': 0, 'failed': 0, 'current': 0, 'upcoming': 0,
               'mode': 'dry-run' if DRY else 'live', 'status': 'failure'}
    log('===== Epic免费游戏 =====')
    log(f"开始时间 {datetime.now(TZ):%Y-%m-%d %H:%M:%S %z}；模式 {summary['mode']}；账号数 {len(lines)}")
    config_error = not lines
    data_error = False
    current, upcoming, photo = [], [], None
    if not lines:
        log('❌ 阶段 1 参数检查：缺少 EPIC_TG_ACCOUNTS（或兼容的 TG_BOT_TOKEN/TG_USER_ID）')
    else:
        stage = time.monotonic()
        try:
            if not re.fullmatch(r'[A-Za-z]{2}(?:-[A-Za-z]{2})?', LOCALE) or not re.fullmatch(r'[A-Za-z]{2}', COUNTRY):
                config_error = True
                raise ValueError('地区参数错误')
            data = fixture() if DRY else json.loads(http(EPIC_URL + '?' + urlencode({'locale': LOCALE, 'country': COUNTRY, 'allowCountries': COUNTRY})))
            current, upcoming = parse_free_games(data)
            summary.update(current=len(current), upcoming=len(upcoming))
            log(f'✅ 阶段 1 {"本地样例" if DRY else "官方商品"}结构核验：本周 {len(current)} 款，即将 {len(upcoming)} 款；耗时 {time.monotonic()-stage:.2f}s')
        except Exception:
            data_error = True
            log(f'❌ 阶段 1 查询失败或响应契约异常；耗时 {time.monotonic()-stage:.2f}s；不输出原始响应')
        stage = time.monotonic()
        if not data_error and not DRY and (current or upcoming):
            try:
                photo = build_image(current, upcoming)
                log('✅ 阶段 2 合成图片成功')
            except Exception:
                log('⚠️ 阶段 2 图片不可用，降级完整文字报告')
        else:
            log('⏭️ 阶段 2 图片处理跳过（断网预演、空列表或查询失败）')
        log(f'阶段 2 耗时 {time.monotonic()-stage:.2f}s')
    for index, line in enumerate(lines, 1):
        stage = time.monotonic()
        ok = False
        try:
            token, chat = parse_account(line)
            if data_error:
                raise ValueError('查询失败')
            log(f'账号 {index} / 阶段 3：参数格式有效；开始提醒')
            if DRY:
                report = build_text_report(current, upcoming)
                assert '本地预演游戏' in report and '预演即将免费游戏' in report
                log(f'✅ 账号 {index} DRY_RUN_OK：解析本周/即将免费、北京时间、原价；模拟图片及文字推送，不联网')
            else:
                delivered = False
                if photo:
                    try:
                        telegram(token, chat, 'sendPhoto', f'🎮 Epic Games 每周免费游戏\n🆓 {len(current)} 款 | ⏳ {len(upcoming)} 款\n{datetime.now(TZ):%Y-%m-%d %H:%M}', photo)
                        delivered = True
                        log(f'✅ 账号 {index} Telegram 图片推送已确认')
                    except Exception:
                        log(f'⚠️ 账号 {index} 图片推送失败，降级文字')
                if not delivered:
                    for chunk in split_messages(build_text_report(current, upcoming)):
                        telegram(token, chat, 'sendMessage', chunk)
                    log(f'✅ 账号 {index} Telegram 文字推送已确认')
            ok = True
        except Exception:
            log(f'❌ 账号 {index} 阶段 3 失败（参数、查询或 Telegram 确认失败）；凭据与响应已隐藏')
        summary['success' if ok else 'failed'] += 1
        log(f"账号 {index} 统计：总任务 1，成功 {int(ok)}，已完成 0，跳过 0，失败 {int(not ok)}；阶段 3 耗时 {time.monotonic()-stage:.2f}s")
    if config_error:
        summary['status'] = 'configuration-error'
    elif summary['failed']:
        summary['status'] = 'partial-failure' if summary['success'] else 'failure'
    else:
        summary['status'] = 'dry-run' if DRY else 'success'
    code = 1 if config_error or data_error or summary['failed'] else 0
    summary['notification'] = notify_summary(summary)
    summary['elapsedSeconds'] = round(time.monotonic() - started, 3)
    summary['exitCode'] = code
    log('----------------------------------------')
    log(f"账号统计：总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}")
    log(f"子任务统计：总数 {summary['accounts']}，成功 {summary['success']}，已完成 0，跳过 0，失败 {summary['failed']}")
    log(f"通知状态：{summary['notification']}；总耗时 {summary['elapsedSeconds']}s")
    log(f"完成时间 {datetime.now(TZ):%Y-%m-%d %H:%M:%S %z}；最终状态 {summary['status']}")
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
