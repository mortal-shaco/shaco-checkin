#!/usr/bin/env python3
# name: 掌瓦每日商店推送
# cron: 10 0 * * *
# new Env("掌瓦每日商店推送")
# 来源：CN-Grace/QinglongScripts / ValorantStore.py
# 上游提交：a40a2b080e0160bd8e0b0b807081115537b87153；许可证：MIT
# 原源码没有内嵌版权声明；保留原作者归属。
# MIT License
# Copyright (c) CN-Grace/QinglongScripts contributors
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""VALORANT_COOKIE：每个非空行一个完整 Cookie，附加 ct=客户端票据。
在本人授权设备上登录掌上无畏契约，抓取 app.mval.qq.com 商店请求的
Cookie，及 refresh_client_ticket 请求体的 ct；同一账号合并在同一行。
至少需要 userId、openid、access_token、ct；保留抓包中的其他 Cookie。
不读写上游共享票据文件。刷新票据仅在本次会话使用，失效后重新抓包。
可选 TG_BOT_TOKEN/TG_USER_ID 启用 Telegram 商店长图；图片失败回退文字。
可选 VALORANT_FONT_PATH 指定已安装中文字体；不下载字体或其他程序。
VALORANT_DRY_RUN=1：模拟完整流程，绝不调用网络或外部通知模块。
QINGLONG_NOTIFY 默认 1，关闭值 0/false/no/off 同时关闭文字与图片推送。
"""
import os
import sys
import re
import json
import time
import tempfile
import importlib.util
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

TZ_BEIJING = timezone(timedelta(hours=8))
API_BASE = "https://app.mval.qq.com"
COMMON_PARAMS = "source_game_zone=agame&game_zone=agame"
TITLE = "掌瓦每日商店推送"
SECRETS = []
requests = None
PILImage = ImageDraw = ImageFont = ImageOps = None
QUALITY_MAP = {"orange": ("传奇", "🟧"), "purple": ("卓越", "🟪"),
               "blue": ("精选", "🟦"), "green": ("奢华", "🟩"), "yellow": ("终极", "🟨")}

class TaskError(Exception):
    pass

def beijing_time_str():
    return datetime.now(TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S")

def clean(value):
    text = str(value).replace("\r", " ")
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    # 不输出手机号、控制字符或服务端原始响应。
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)

def log_info(message):
    print(f"[{beijing_time_str()[11:]}] {clean(message)}", flush=True)

def log_warning(message):
    log_info("⚠️ " + message)

def log_error(message):
    log_info("❌ " + message)

def enabled(name, default="1"):
    return os.environ.get(name, default).strip().lower() not in {"0", "false", "no", "off", ""}

def parse_cookie(line):
    fields = {}
    for entry in line.split(";"):
        if not entry.strip():
            continue
        if "=" not in entry:
            raise TaskError("Cookie 格式错误，字段必须使用 名称=值")
        key, value = entry.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            raise TaskError("Cookie 含空字段")
        if key in fields:
            raise TaskError("Cookie 含重复字段")
        fields[key] = value
    return fields

def api_post(session, path, body=None):
    try:
        response = session.post(API_BASE + path + "?" + COMMON_PARAMS,
                                json=body or {}, timeout=(8, 15), allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200 or len(response.content) > 2000000:
            raise TaskError("接口 HTTP 状态或响应大小不符合预期")
        # 保留上游重复 JSON 响应的第一个对象解析兼容。
        data, _ = json.JSONDecoder().raw_decode(response.text.strip())
        if not isinstance(data, dict):
            raise TaskError("接口响应结构异常")
        return data
    except TaskError:
        raise
    except Exception:
        raise TaskError("接口网络请求或 JSON 解析失败") from None

def checked(result):
    code = result.get("result")
    if type(code) is not int or code != 0:
        raise TaskError("接口未确认业务成功（请检查登录状态）")
    return result.get("data")

def create_session(fields):
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "mval/2.6.0.10062 Channel/5 Mozilla/5.0 (Linux; Android 16; wv) AppleWebKit/537.36",
                            "Content-Type": "application/json; charset=utf-8"})
    for key, value in fields.items():
        if key != "ct":
            session.cookies.set(key, value, domain="app.mval.qq.com", path="/")
    return session

def refresh_token(session, fields):
    data = checked(api_post(session, "/go/auth/refresh_third_token", {
        "type": fields.get("acctype", "qc"), "uuid": fields["userId"],
        "openid": fields["openid"], "source_game_zone": "agame", "game_zone": "agame"}))
    token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token:
        raise TaskError("刷新接口未返回有效 access_token")
    SECRETS.append(token)
    session.cookies.set("access_token", token, domain="app.mval.qq.com", path="/")
    return "access_token 已刷新，仅用于当前会话"

def refresh_ticket(session, fields):
    data = checked(api_post(session, "/go/auth/refresh_client_ticket", {
        "config_params": {"lang_type": 0}, "ct": fields["ct"], "local_is_new_user": 0,
        "user_id": fields["userId"], "source_game_zone": "agame", "game_zone": "agame"}))
    info = data.get("ct_info", data) if isinstance(data, dict) else {}
    ct, wt = info.get("ct"), info.get("wt")
    if not all(isinstance(x, str) and x for x in (ct, wt)):
        raise TaskError("票据刷新未返回有效 ct 和 wt")
    SECRETS.extend([ct, wt])
    session.cookies.set("tid", wt, domain="app.mval.qq.com", path="/")
    checked(api_post(session, "/go/auth/get_client_tmp_ticket", {
        "config_params": {"lang_type": 0}, "ct": ct}))
    return "client ticket、web ticket 和临时票据刷新已确认"

def identity(session):
    data = checked(api_post(session, "/go/auth/bind_relation_list"))
    records = data.get("list") if isinstance(data, dict) else None
    if not isinstance(records, list):
        raise TaskError("绑定账号响应结构异常")
    if records and isinstance(records[0], dict):
        name = records[0].get("nickName")
        if isinstance(name, str) and name:
            return name
    return ""

def get_daily_store(session):
    data = checked(api_post(session, "/go/mlol_store/agame/user_store", {
        "scene": "", "source_game_zone": "agame", "game_zone": "agame"}))
    if not isinstance(data, list):
        raise TaskError("商店响应结构异常")
    for section in data:
        if isinstance(section, dict) and section.get("key") == "dailystore":
            items = section.get("list")
            if not isinstance(items, list) or not items:
                raise TaskError("每日商店为空，不能确认查询成功")
            if len(items) > 20 or any(not isinstance(i, dict) or not i.get("goods_name") or "rmb_price" not in i for i in items):
                raise TaskError("商店商品字段异常")
            end_ts = section.get("end_ts", 0)
            if isinstance(end_ts, str) and end_ts.isdigit():
                end_ts = int(end_ts)
            if type(end_ts) not in (int, float) or not 0 <= end_ts <= 4102444800:
                raise TaskError("商店刷新时间字段异常")
            return items, end_ts
    raise TaskError("响应中没有每日商店")

def build_report(items, nickname, end_ts):
    end_time = datetime.fromtimestamp(end_ts, TZ_BEIJING).strftime("%Y-%m-%d %H:%M") if end_ts else "未知"
    lines = [f"👤 账号: {nickname}", f"⏰ 刷新时间: {end_time}"]
    for i, item in enumerate(items, 1):
        quality, icon = QUALITY_MAP.get(item.get("quality"), ("未知", "⬜️"))
        lines.extend([f"{i}. {icon} {item.get('goods_name', '未知')}（{quality}）",
                      f"   💰 {item.get('rmb_price', '?')} 点券 | ❤️ {item.get('like_num', '?')}"])
    lines.append(f"🕒 执行时间: {beijing_time_str()}")
    return clean("\n".join(lines))

def public_image(url, timeout):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise TaskError("图片地址必须为无凭据 HTTPS 地址")
    # 图片请求使用独立无 Cookie 会话，绝不向图片服务传递账号认证。
    with requests.Session() as session:
        session.trust_env = False
        with session.get(url, timeout=(8, timeout), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise TaskError("图片状态异常")
            payload = bytearray()
            for part in response.iter_content(65536):
                payload.extend(part)
                if len(payload) > 10000000:
                    raise TaskError("图片过大")
            return bytes(payload)
CARD_W = 720
HEADER_H = 140
GAP = 16
BG_COLOR = (20, 20, 24)
GOODS_WIDTH_RATIO = 0.78
GOODS_PADDING = 40
BG_TEXT_RATIO = 0.18


def _download_image_pil(url: str, timeout: int = 10):
    """下载图片并返回 PIL Image 对象，失败返回 None"""
    if not url:
        return None
    try:
        payload = public_image(url, timeout)
        img = PILImage.open(BytesIO(payload))
        if img.width * img.height > 16000000:
            raise TaskError("图片尺寸过大")
        img.load()
        img = ImageOps.exif_transpose(img)
        return img
    except Exception:
        log_warning("图片下载或解码失败，使用卡片兜底")
        return None


def _contain_resize(img, target_w: int, target_h: int):
    """等比缩放使整图完整放入目标尺寸，不裁切，返回 (缩放图, 居中x, 居中y)"""
    scale = min(target_w / img.width, target_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img_resized = img.resize((new_w, new_h), PILImage.Resampling.LANCZOS)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    return img_resized, x, y


def _draw_text_with_outline(draw, position, text, font, fill, outline=(0, 0, 0, 255), offset: int = 2):
    """绘制带描边的文字（8 方向偏移）"""
    x, y = position
    for dx in (-offset, 0, offset):
        for dy in (-offset, 0, offset):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, fill=outline, font=font)
    draw.text((x, y), text, fill=fill, font=font)


def _fit_font(text: str, font_path: str, base_size: int, max_width: int, min_size: int = 16):
    """根据最大宽度动态缩放字号，返回合适字体"""
    size = base_size
    while size > min_size:
        try:
            font = ImageFont.truetype(font_path, size)
        except (OSError, ValueError):
            return ImageFont.load_default()
        bbox = font.getbbox(text)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    try:
        return ImageFont.truetype(font_path, min_size)
    except (OSError, ValueError):
        return ImageFont.load_default()


def _load_fonts(font_path: str) -> dict:
    """一次性加载所有字体"""
    def make(size):
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, ValueError):
            return ImageFont.load_default()
    return {
        "font_path": font_path,
        "title": make(40),
        "subtitle": make(28),
        "card_name": make(36),
        "price": make(34),
    }


def ensure_font():
    """使用可选本地字体或 Pillow 内置字体；不下载、不安装。"""
    configured = os.environ.get("VALORANT_FONT_PATH", "").strip()
    if configured:
        if not Path(configured).is_file():
            raise TaskError("配置的字体文件不可读")
        return configured
    return ""


def _render_card(item: dict, bg_img, goods_img, fonts: dict):
    """渲染单张商品卡片，返回 RGBA Image。利用背景自带底部文字条，不加额外 footer"""
    name = item.get("goods_name", "未知")
    price = item.get("rmb_price", "0")

    # 卡片高度由背景图决定（宽度 CARD_W，高度按背景原始比例），无额外 footer
    if bg_img is not None:
        bg = bg_img.convert("RGBA")
        bg_h = int(CARD_W * bg.height / bg.width)
        bg_resized = bg.resize((CARD_W, bg_h), PILImage.Resampling.LANCZOS)
    else:
        bg_h = 400
        bg_resized = None

    card = PILImage.new("RGBA", (CARD_W, bg_h), BG_COLOR + (255,))

    # 背景图（铺满整卡）
    if bg_resized is not None:
        card.alpha_composite(bg_resized, (0, 0))

    # 背景底部自带文字条区域
    text_strip_h = int(bg_h * BG_TEXT_RATIO)
    text_strip_top = bg_h - text_strip_h

    # 商品图（contain 模式，限制在文字条上方区域，留 PADDING 不顶住背景边和文字条）
    if goods_img is not None:
        goods = goods_img.convert("RGBA")
        max_w = int(CARD_W * GOODS_WIDTH_RATIO)
        max_h = max(text_strip_top - 2 * GOODS_PADDING, 1)
        goods_resized, _, _ = _contain_resize(goods, max_w, max_h)
        x = (CARD_W - goods_resized.width) // 2
        y = (text_strip_top - goods_resized.height) // 2
        card.alpha_composite(goods_resized, (x, y))

    # 缺图兜底：底部文字条加半透明黑条保证文字可读
    if bg_resized is None:
        fallback_bar = PILImage.new("RGBA", (CARD_W, text_strip_h), (0, 0, 0, 175))
        card.alpha_composite(fallback_bar, (0, text_strip_top))

    draw = ImageDraw.Draw(card)

    # 文字颜色：有背景用深色（背景文字条偏白），无背景用浅色
    if bg_resized is not None:
        name_color = (40, 40, 50, 255)
        price_color = (120, 80, 10, 255)
        outline_color = (255, 255, 255, 200)
    else:
        name_color = (255, 255, 255, 255)
        price_color = (255, 215, 0, 255)
        outline_color = (0, 0, 0, 255)

    # 价格（右下，文字条内）
    price_text = f"{price} 点券"
    price_font = fonts["price"]
    pbbox = draw.textbbox((0, 0), price_text, font=price_font)
    pw = pbbox[2] - pbbox[0]
    ph = pbbox[3] - pbbox[1]
    px = CARD_W - pw - 28
    py = text_strip_top + (text_strip_h - ph) // 2
    _draw_text_with_outline(draw, (px, py), price_text, price_font, price_color, outline=outline_color)

    # 名称（左下，动态缩放避免与价格重叠）
    name_max_w = px - 28 - 28
    name_font = _fit_font(name, fonts["font_path"], 36, name_max_w)
    nbbox = draw.textbbox((0, 0), name, font=name_font)
    nh = nbbox[3] - nbbox[1]
    ny = text_strip_top + (text_strip_h - nh) // 2
    _draw_text_with_outline(draw, (28, ny), name, name_font, name_color, outline=outline_color)

    return card


def _render_header(nickname: str, fonts: dict):
    """渲染标题头，返回 RGBA Image"""
    header = PILImage.new("RGBA", (CARD_W, HEADER_H), BG_COLOR + (255,))
    draw = ImageDraw.Draw(header)

    _draw_text_with_outline(draw, (28, 20), "掌瓦每日商店", fonts["title"], (255, 255, 255, 255))
    _draw_text_with_outline(draw, (28, 78), f"账号: {nickname}", fonts["subtitle"], (200, 200, 200, 255))

    return header


def build_shop_image(items: list, nickname: str, end_ts: int) -> str:
    """构建商店长图，返回 PNG 文件路径"""
    font_path = ensure_font()
    fonts = _load_fonts(font_path)

    # 并行下载所有图片（bg + goods 交替入队）
    urls = []
    for item in items:
        urls.append(item.get("bg_image", ""))
        urls.append(item.get("goods_pic", ""))
    with ThreadPoolExecutor(max_workers=8) as ex:
        downloaded = list(ex.map(_download_image_pil, urls))

    # 配对为 (bg, goods)
    item_imgs = [(downloaded[i * 2], downloaded[i * 2 + 1]) for i in range(len(items))]

    # 渲染卡片（缺图时用纯色兜底，保证 4 格完整）
    cards = []
    for idx, (item, (bg, goods)) in enumerate(zip(items, item_imgs)):
        try:
            card = _render_card(item, bg, goods, fonts)
        except Exception:
            log_warning("商品卡片渲染失败，使用纯色卡片")
            card = _render_card(item, None, None, fonts)
        cards.append(card)
        log_info(f"商品 {item.get('goods_name', '未知')} 卡片处理完成")

    if not cards:
        log_error("没有商品卡片渲染成功")
        return None

    # 标题头
    header = _render_header(nickname, fonts)

    # 垂直拼接（标题头 + 卡片，间隙用深色填充）
    sections = [header] + cards
    total_h = sum(s.height for s in sections) + (len(sections) - 1) * GAP
    merged = PILImage.new("RGB", (CARD_W, total_h), BG_COLOR)

    y = 0
    for s in sections:
        merged.paste(s.convert("RGB"), (0, y))
        y += s.height + GAP

    # 保存为 PNG
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
            merged.save(f, format="PNG")
            merged_path = f.name
        log_info("商店图片生成完成（临时文件）")
        return merged_path
    except Exception:
        log_error("商店图片保存失败")
        return None


def telegram_photo(path, caption):
    token = os.environ.get("TG_BOT_TOKEN", "").strip()
    target = os.environ.get("TG_USER_ID", "").strip()
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token) or not re.fullmatch(r"-?\d+", target):
        raise TaskError("Telegram 参数格式错误")
    with requests.Session() as session, open(path, "rb") as photo:
        session.trust_env = False
        response = session.post("https://api.telegram.org/bot" + token + "/sendPhoto",
                                data={"chat_id": target, "caption": clean(caption)[:1024]},
                                files={"photo": ("store.png", photo, "image/png")},
                                timeout=(8, 25), allow_redirects=False)
        response.raise_for_status()
        data = response.json()
        if data.get("ok") is not True:
            raise TaskError("Telegram 未确认图片发送成功")

def notify_summary(body, dry):
    if not enabled("QINGLONG_NOTIFY"):
        return "已关闭"
    if dry:
        log_info("⏭️ 通知预演：已生成脱敏总结，不执行外部模块（断网模式）")
        return "断网预演"
    # 可选青龙通知集成。子进程隔离输出、限制等待，不改变业务退出码。
    import subprocess
    program = '''import json,sys,os,importlib.util
payload=json.load(sys.stdin)
paths=[]
if os.environ.get("QINGLONG_NOTIFY_DIR"):
    paths.append(os.path.join(os.environ["QINGLONG_NOTIFY_DIR"],"notify.py"))
paths.extend([os.path.join(payload["script_dir"],"notify.py"),"/ql/data/scripts/notify.py","/ql/scripts/notify.py"])
module=None
for path in paths:
    if os.path.isfile(path):
        spec=importlib.util.spec_from_file_location("ql_notify",path)
        module=importlib.util.module_from_spec(spec)
        sys.path.insert(0,os.path.dirname(path))
        spec.loader.exec_module(module)
        break
if module is None:
    import notify as module
result=module.send(payload["title"],payload["body"])
if result is False:
    sys.exit(1)
'''
    try:
        result = subprocess.run([sys.executable, "-c", program],
                                input=json.dumps({"title": TITLE, "body": clean(body),
                                                  "script_dir": str(Path(__file__).resolve().parent)}),
                                text=True, capture_output=True, timeout=40, check=False)
        if result.returncode != 0:
            raise TaskError("通知模块不可用或发送失败")
        return "已调用青龙通知"
    except Exception:
        log_warning("青龙通知不可用或发送失败，保留业务退出码；商店文字报告见日志")
        return "发送失败或不可用"

class AccountRun:
    def __init__(self, number):
        self.number = number
        self.started = time.monotonic()
        self.stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        self.errors = []

    def step(self, label, action=None, skip=None):
        self.stats["total"] += 1
        stage = self.stats["total"]
        began = time.monotonic()
        log_info(f"账号 {self.number} · 阶段 {stage} {label} 开始")
        value = None
        try:
            if skip:
                self.stats["skipped"] += 1
                log_info("⏭️ " + skip)
            else:
                value = action()
                self.stats["success"] += 1
                log_info(f"✅ {label} 已确认")
        except TaskError as error:
            self.stats["failed"] += 1
            self.errors.append(label + "：" + str(error))
            log_error(str(error))
        except Exception:
            self.stats["failed"] += 1
            self.errors.append(label + "：处理失败")
            log_error("处理失败（不输出异常详情或服务端响应）")
        log_info(f"账号 {self.number} · 阶段 {stage} {label} 结束，耗时 {time.monotonic()-began:.2f} 秒")
        return value

    def finish(self):
        self.stats["elapsedSeconds"] = round(time.monotonic() - self.started, 3)
        state = "失败" if self.stats["failed"] else "成功"
        log_info(f"账号 {self.number} 统计：总任务 {self.stats['total']}，成功 {self.stats['success']}，"
                 f"已完成 {self.stats['alreadyComplete']}，跳过 {self.stats['skipped']}，"
                 f"失败 {self.stats['failed']}，耗时 {self.stats['elapsedSeconds']} 秒，{state}")
        return {"account": self.number, "status": "failure" if self.stats["failed"] else "success",
                "statistics": self.stats, "errors": self.errors}

def fixture():
    return [{"goods_name": f"预演皮肤 {i}", "rmb_price": 1000 + i,
             "quality": "purple", "like_num": i, "bg_image": "", "goods_pic": ""}
            for i in range(1, 5)], 1800000000

def run_account(number, line, dry, dependency_error):
    run = AccountRun(number)
    def config():
        fields = parse_cookie(line)
        if any(not fields.get(key) for key in ("userId", "openid", "access_token", "ct")):
            raise TaskError("缺少 userId/openid/access_token/ct；请重新获取同一账号完整 Cookie 和 ct")
        if not dry and dependency_error:
            raise TaskError("缺少公开依赖 requests；请通过青龙依赖管理安装")
        return fields
    fields = run.step("参数校验", config)
    if fields is None:
        return run.finish(), ""
    session = None
    report = ""
    try:
        if not dry:
            session = create_session(fields)
        run.step("刷新 access_token", lambda: "预演刷新" if dry else refresh_token(session, fields))
        run.step("刷新 client/web/临时票据", lambda: "预演刷新" if dry else refresh_ticket(session, fields))
        nickname = run.step("查询绑定账号", lambda: "预演账号" if dry else identity(session))
        nickname = nickname or f"账号 {number}"
        log_info(f"绑定账号：{nickname}")
        store = run.step("查询每日商店", lambda: fixture() if dry else get_daily_store(session))
        if store:
            items, end_ts = store
            report = build_report(items, nickname, end_ts)
            log_info(report)
            run.step("商店长图与 Telegram 推送", skip="断网预演，不下载图片、不发送通知" if dry else
                     ("QINGLONG_NOTIFY 已关闭" if not enabled("QINGLONG_NOTIFY") else
                      "未配置 Telegram，使用文字报告" if not (os.environ.get("TG_BOT_TOKEN") or os.environ.get("TG_USER_ID")) else None),
                     action=lambda: send_shop_image(items, nickname, end_ts))
        else:
            run.step("商店长图与 Telegram 推送", skip="商店查询失败")
    except Exception:
        run.step("会话处理", lambda: (_ for _ in ()).throw(TaskError("账号会话处理失败")))
    finally:
        if session is not None:
            session.close()
    return run.finish(), report

def send_shop_image(items, nickname, end_ts):
    global PILImage, ImageDraw, ImageFont, ImageOps
    try:
        from PIL import Image as PILImage, ImageDraw, ImageFont, ImageOps
        path = build_shop_image(items, nickname, end_ts)
        if not path:
            raise TaskError("商店长图生成失败，文字报告保留")
        try:
            telegram_photo(path, build_report(items, nickname, end_ts))
        finally:
            Path(path).unlink(missing_ok=True)
    except TaskError:
        raise
    except Exception:
        raise TaskError("图片生成或 Telegram 推送失败，文字报告保留；请检查 Pillow、字体及推送配置") from None

def main():
    global requests
    began = time.monotonic()
    started = beijing_time_str()
    dry = enabled("VALORANT_DRY_RUN", "0")
    lines = [line.strip() for line in os.environ.get("VALORANT_COOKIE", "").splitlines() if line.strip()]
    # 先建立脱敏表；不记录完整 Cookie 或账号认证字段。
    for line in lines:
        SECRETS.append(line)
        for entry in line.split(";"):
            if "=" in entry:
                SECRETS.append(entry.split("=", 1)[1].strip())
    SECRETS.extend([os.environ.get("TG_BOT_TOKEN", ""), os.environ.get("TG_USER_ID", "")])
    log_info("========== " + TITLE + " ==========")
    log_info(f"开始时间：{started}；运行模式：{'断网预演' if dry else '实时'}；账号数：{len(lines)}")
    dependency_error = False
    if not dry:
        try:
            import requests as http_requests
            requests = http_requests
        except ImportError:
            dependency_error = True
    results, reports = [], []
    if not lines:
        log_error("配置错误：未配置 VALORANT_COOKIE，每个非空行填写一个账号")
    for index, line in enumerate(lines, 1):
        result, report = run_account(index, line, dry, dependency_error)
        results.append(result)
        if report:
            reports.append(report)
    succeeded = sum(r["status"] == "success" for r in results)
    failed = len(results) - succeeded
    exit_code = 0 if lines and not failed else 1
    status = ("configuration-error" if not lines else "partial-failure" if failed and succeeded else
              "failure" if failed else "dry-run" if dry else "success")
    stats = {key: sum(r["statistics"][key] for r in results)
             for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    body = f"账号总数：{len(lines)}，成功：{succeeded}，失败：{failed}；最终状态：{status}"
    if not lines:
        body += "\n配置错误：缺少 VALORANT_COOKIE"
    for result in results:
        if result["errors"]:
            body += f"\n账号 {result['account']}：" + "；".join(result["errors"])
    if reports:
        body += "\n\n" + "\n\n".join(reports)
    notification = notify_summary(body, dry)
    finished = beijing_time_str()
    elapsed = round(time.monotonic() - began, 3)
    log_info("----------------------------------------")
    log_info(f"任务统计：账号总数 {len(lines)}，成功 {succeeded}，失败 {failed}；子任务 {json.dumps(stats, ensure_ascii=False)}")
    log_info(f"完成时间：{finished}；总耗时：{elapsed} 秒；通知状态：{notification}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "mode": "dry-run" if dry else "live",
          "status": status, "accountCount": len(lines), "successCount": succeeded, "failureCount": failed,
          "statistics": stats, "accounts": results, "notification": notification,
          "startTime": started, "finishTime": finished, "elapsedSeconds": elapsed,
          "exitCode": exit_code}, ensure_ascii=False, separators=(",", ":")))
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
