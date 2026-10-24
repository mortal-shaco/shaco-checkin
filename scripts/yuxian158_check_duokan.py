# -*- coding: utf-8 -*-
# name: 多看阅读
# cron: 25 2 * * *
# 规范发布路径：scripts/yuxian158_check_duokan.py
# 上游：yuxian158/check，dailycheckin_scripts/ck_duokan.py；
# 关联来源：OreosLab/checkinpanel，ck_duokan.py，提交 911402e4b2e559ffd62c4949a971ddd6834edd7d。
# 两份来源许可均为 MIT；保留上游归属，原文件没有单独版权声明。
# SPDX-License-Identifier: MIT
"""多看阅读独立维护版。

DUOKAN_COOKIE：登录多看阅读后，使用自己的浏览器开发者工具网络面板，
复制 www.duokan.com 请求的完整 Cookie（必须含 device_id 和登录会话）。
每行一个账号，Cookie 字段以分号分隔，仅在第一个等号处分割。
兼容 DUOKAN：逐行 Cookie，或旧版 [{"cookie":"..."}] JSON 列表。
DUOKAN_TASKS 默认 sign,info；可选 free,gift,add_draw,draw,download,task,delay。
兼容 DUOKAN_DELAY、DUOKAN_FREE、DUOKAN_DRAW=1，按旧顺序追加
delay、free、draw；不会自动添加 add_draw 或其他领取动作。
free 会创建零价订单；其他可选动作可能改变书豆或消耗活动机会，请自行选择。
DUOKAN_DRY_RUN=1 完全断网；只验证配置及展示执行计划，不代表业务成功。
本项目规范计划每日 02:23；旧 ck_duokan 的每日 02:05 计划可改为调用此脚本。
依赖仅 Python 3 标准库；通知模块是可选青龙集成，不影响业务退出码。

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
        _ql_notify_identities = ('df7ef61ae68efc75', 'scripts/yuxian158_check_duokan.py', 'yuxian158_check_duokan.py', 'yuxian158_check_duokan', 'c722e904dffeaf49', 'scripts/ck_duokan.py', 'ck_duokan.py', 'ck_duokan')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import contextlib
import fnmatch
import importlib
import importlib.util
import io
import json
import math
import os
import re
import socket
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

GIFT_SIGNS = ['d16ad58199c69518a4afd87b5cf0fe67', '828672d6bc39ccd25e1f6ad34e00b86c', 'f0ccc1bb1cecea673c197b928fb8dbd9', '6b86c490d92a138de9a0ae6847781caa', 'c707047e8b820ba441d29cf87dff341e', '82b2c012a956b18cff2388d24f2574a6', '87d6b5183a361ee1f6ea8cece1ee83c3', '9d42576f7e99c94bb752fde06e6770a5', 'e58d1f67a82a539d9331baaa3785a943', '52c95192ebcb1d0113a748df58a72055', '511f33e481fe4504d2637aaf6cbbbaff', '6e986f36f4a45cadf61d2f246b27cdc6', 'f27797a6a1d7fe495b0f4de05f799327', '4bd335e899fa665f15eea2f215156321', '9355df762183f084473432b5c6900c44', '4fb21fb04cbbae9d65556c3958603674', '2d02ceb4f1bc916510c7407ce4eca5a5', 'ef314bf665af0b51294e624244acd7d6', '1b441a2ab8e9e7dcf11a55b85931132f', '005d2345782ab456e5af167336b70623', '51ac508a4d494654035f17f1d646779b', '0f6579670f1081f1bcba89dd64645b48', '0cd858abe26f0d3db561185fe26bbb75', 'b5f5fd5b47fd587cb003807e97bed783', '6ac9509a5cb799efeb1bb877c505f7e3', 'b5dd986ffc84762429901ffe633d82a0', 'f98a436cc2c85943d23d986a8d84c3bd', '6fc387f2a17b8564ca212e2b16544cc3', '12ead6a62411402378c6311199a0b2ef', '7d8dcf31e2e69fcf6bd8af4f48831e92', '446c3d0303b0dbd6bc2157844f1222ad', '439890227d823ff57bed8ad351fa1b75', '645acf3107722ab26b9d3194ecd156ff', 'afcb41dd9bc54d752c26ace985b49960', '1100ab94ccd2e8373af70326c194d8ea', '373d73c0c0975cf959eb4c40dc82b27c', '2167ac28833149e9ad4ca217bcfa1a62', '80547afccc42f34e4c8c4083e00a41a6', 'b604dda473644bd8157bafdf4ae518dc', '15eaa8f727b595d512b82f55364b53b9', '8fb656937fd613ccbbcacdc384595b03', 'dd8410da0b5144ba4aba5a618723b72e', '204208386b056a2288e541110bfeeec3', 'c5b2e7344efd4128bcab5840fa427103', '0168601e4335095c502e2e550ca53114', 'dfa12fe056a8deee35da18613173560f', 'ed945efdef9c7b2de41249a4fed3945e', 'b9ece5964ab62d51f8b70ffd35191e9d', 'f0e0ca4ca0b8afd766821a4922a2873c', '5c687b8c6bd641f3f2c0d6aaeceafff6', 'c983be6420027231d77b748f9d02c1f2', '7c53358df8156d979cb6cbb74e15877b', 'a58058035f73628a7c0847c66c350e88', '79dd039ca5cf401993801710f9900d6b', '5aff116c2cec01fcc69b389034f456a2', 'd006927cd9bfd620a6af4f76ee3c4100', '410fe62830eeb91ca48be24ffe596364', '9d18226ff144a72812d0104ce59fb34e', 'de439c7f75ca80b1d5b8aba619ee200d', '00d1a0479590793294bfdd5c427643aa', 'd57176b1ce88135243bd501e448b8559', '7c500eff681637b97dd526bb11737abb', '3e197e47aaac926ccd50c37eb2828311', '7db084ea5987f841ad77240bcbb8ce54', 'cce74f0facc50d47c0dd0e3e2f7435fb', 'f8bb53fbeb9b2d45db8aca1401817599', '5baf7f0f355db11eeb0e936b675cdb82', '4478a3354de6bcd7e91b49e28a2b2b3f', '66a0338d93af82e956122288b08d2b4b', '9f598b2b1c9cd0f2b20e335831cce366', '9f4a45fec88b2820653abba179759eb6', '41086649c9a39ec977ba42f9ce81f828', '06ccca6fd73a6e38f65638ab8abbab76', '0cfa0a034a203bb3a22be499e74906f4', 'c0d1da35a8878b7e4dcdf44bf3cd6b96', 'f34921e16f6518c1149cc083bd8e1ad7', 'ed0be3c70075d1d8f1a412f9e59a12e7', 'eb4d6324bae7db952bd220cb4d57a3de', '5ba65d9f8ad735681b594f5092f6ab37', '2fa6e0b612962937edb37ed7043923fd', 'baa8268c7d85d793011c5f5b977f8d4b', 'f4842a465e4583646abf7df67d8e2915', '12c6332c8c9ded3d58d45f2dae7de8da', 'f56609232205692acf6b6a5d337b0965', '3e4eed15387843c668fba53641599d07', 'd1b9d9ede145b5d426130986245cb66e', '2979e43f6ab786f5d68cc262105f3c45', '118a18ed578c78f4855b416f8271b29a', '9122e158d034f094627c70ed6c3d0c33', 'dd5413c17253e86cc4247984f3bb77e5', 'b36bb0124b962efccbb601486665ce9e', '6afb3a719f8b0a0b2f744b3dad8b15ab', 'faf18d64268402ed2975a3f60bc9e651', '9f4081944d4ca3fa7b831d7c3b6c289d', '367d7a3d77a9f96cbd7903b33c30b61f', '605276cf621ff9ba34a99e3675a006f6', 'a50a734c1a3a749918e20205505ef91d', '271ff14ba5edfe89a80a3430227bc11b', '3bae338062b4bb3a5087eb13cbcc6efe', '9b443d60178a9bcb08bae62c41970abf', 'a4f6e97741054f3567ab6a7257c63ab1', 'e06a82cc1f05eda4947e5fa0927d89c5', '4fa3b4fc274c283efb02c0a1ddd133e7', '4aa59e16a3961ed1ebd12b7f15d79547', 'f75fe88eaa24fc28ac57d963d8b90f2d', '42cbe52b6f74761a5a7a79bf370c30ef', '7d4571b5c9710e3b5481330bc7123ecc', 'fcf2f7ec42086809991de5aed5e7ef0d', 'bb7de9aaf68a83ac1ddbe75ba913b8af', 'a9bd964b97e785fffb641edb9b402d3f', '6a815be6f537b2351e947ed66f74e209', '27ae4e4d71395c6255bf7ea57c496507', '2b07f369e90f4fc34ef419d891a2906f', '7a2dc8a5b3fc0c7ecddb97ed1ce2c833', 'e7ad152ef27beb80c5d343f41f885b21', 'ba21758aed15a3a20a27f63bc0d84626', '3820f7b8e1ece2614a11264501b5c93e', 'c3c41c87e6bf752f5237b4fffa33f08b', 'ed21086ff6682ab8495ecbfbb697af4a', '5a2585ff3524f319dfd1f6b735c9a18d', '0e61444507f0a780a1c83b612eb5fb9b', 'b105aa5c696648c0f7aae9e3933f8fe0', 'fec8f729e9e1d02248b949ce17674e0c', 'd3323d5560d15d4bc03575dcd0f53ae9', '15fbf9d24dd05d9d64a18a8fd28f4dcc', 'ac0f3bda53081eee547882b2cdc8b04f', '5dd3fadcd4ea6b922e1462431966c2bf', '4acb71816dad0ce9a53d8fee301d857c', '4c7e173f3a046919587db5b2640896e7', '8407dc0459d0b367eaced7e5dfdef8ed', '17e02409659223ff4e32cabd9ad352d9', 'c49edc07086b27769eddb981359f56b2', '344822f5d8d53fe9aa7a1c7328cd2c59', '92259343c65ac0feab5cb56b2e851783', 'e1e537b0bd37091c0ba4d5f614af9160', 'dff1116c175ddaaa20f3985a3d88abc6', '3b1131a7c7273aa61cbd71b044e9beca', '431aab37ef168c383f078b9244008cee', '96c3bb8355d7e3ed7265095374f1c090', 'c3a7d304cdb307f073bef5003d1b8b78', '627d884fc905cc353d0028076e39846b', '36ce0d88a6bb2d10e0dc0a697f64df4e', 'dc8dbd035d42a5d8170976d5f532dab0', '01c2665e7ea15bc56cca6d955c2e8ae1', 'c54ae7eeedc87ac52249684f012d3805', '2df9b3b8f21a682b20d9d77669087a7a', 'fded473150a783586c12692fd57d0825', '580499e69f42c0ccba0d1f87a83e41e9', '99433cb83f1cd7176b7cdeaa7be49cd8', 'fbd76e8265547376905b3b6004150064', '362768496052ae0dfbe909a9b5c6f54e', '4f33581089c90944e5ad950646b17712', 'bffe93cdfe4b8833190e0a59c779e027', '78e042b792c3af7faf7a6ebfedf6af9e', '51a59c881726c2887efe9752bd9db715', 'a46ecf03d3f4038ba3de4ae4ac28170f', '48d025f7cc34ac29c21d03b2c1f36449', '8c9ceb77d61c20cb96ee652eb7b838c9', '47a5882c89671429ae532339b7f333ce', 'a0b735557416ff3d08d3d8440393061a', '976d3b3a8fbdf33d525075a9288455ab', '636ca4c1db1c4450431ecd7e10a5e671', '8c5cd12180027ee6535a837bd4f0259a', 'b82315333974c76793b3c7f517fe977c', '6143d1f3472cd7cf08e3780918019158', '20d032426fd66d49bec4f99579252cfa', '398ee715d1dfd058a912bc7768d35f82', '1f678678966444fb53d118b8134ceb94', 'd6641f3ed9444eae2b77ba68d3552f6a', 'ab2babaa19539895a5285c1ded6de8c6', '5bc61d3cd53582b859db9cf04fc7e250', '5deb619ed27c2754df4f9c7e3ce16b82', 'b81a322830fee59c75985626f7e0a8b5', 'e2313ad53d58e181c5fbaef29e5772c3', '70d2aa99ef48b6cf1c0e8c107c0e121d', '0633cdb06253a2b11e9a9ca234a3e9c3', 'bd1cbb9764fba94e8f1c0d1c024487af', '301cbdbf26210596f9b22123abff0ca8', '1fc2448ee192a1d0806ae1eb6fcc81fe', '306247030d0b6442c3ded42e9ca99872', '1c8f9a0786a01db1d06989345887967e', '256ec3a54aaae719aae88d8f9c7f9b5f', '45645896cccec48191916fec482979d9', 'c3a19c728d6fd39925bd63abe15aa446', '15f45c4cd8fd4a6c0a3fae14ccafff47', 'a082c46b09772739af41f01676e1d0d1', '14928418f94f5d35b182001ae0160455', 'dfbc5bc946c72650adaaf570f11a1e80', '8a312e3e30d2e8fd1cf8873c3abe1d8c', 'ef425403acaabfb2a5b3f6ab0aafce8c', 'c78d471822dd961a53afe23e6c2dfa61', 'a40f670d8de3784b54784daf63095d88', '49a72ace7fd54d8d0833bb2590db58aa', '38e3808d28de73af3578f6d64020e1fc', 'a8be6ab39263d2edf61acafc60949921', 'd9c16bf0032800916e948ea26624a253', 'dbf3a62ff403c3ba94d5ab1e6219f5bc', '3a6415de684e2978ce17543d66d523f6', '2f69a681ee1ff927df1bdbd5431ced1d', 'e55c0390872735ec285dad8ebdd939e0']
TASK_CODES = ["K7S36GFSZC", "A2AMBFHP6C", "K5HHKUU14D", "J18UK6YYAY", "1BJGW140U5"]
LABELS = {"sign":"每日签到", "info":"书豆查询", "free":"领取今日限免", "gift":"体验奖励", "add_draw":"添加抽奖机会", "draw":"抽奖", "download":"下载奖励", "task":"其他活动奖励", "delay":"书豆延期"}
FALSE = {"0", "false", "no", "off"}
TRUE = {"1", "true", "yes", "on"}
SECRETS = []
CATALOG_ID = "df7ef61ae68efc75"
PUBLISH_PATH = "scripts/yuxian158_check_duokan.py"
NOTIFICATION_IDENTITIES = {
    CATALOG_ID, "c722e904dffeaf49", PUBLISH_PATH,
    "yuxian158_check_duokan.py", "yuxian158_check_duokan",
    "scripts/ck_duokan.py", "ck_duokan.py", "ck_duokan",
    "scripts/duokan_reading.py", "duokan_reading.py", "duokan_reading",
}

class TaskError(Exception):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口重定向，停止发送凭据")

def stamp():
    return time.strftime("%H:%M:%S")

def clean(value):
    text = str(value).replace("\n", " ").replace("\r", " ")
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已隐藏]")
    return re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)

def log(text):
    print(f"[{stamp()}] {clean(text)}", flush=True)

def integer(name, default, maximum):
    try:
        n = int(os.getenv(name, str(default)))
    except ValueError:
        raise TaskError(f"{name} 必须为整数")
    if not 1 <= n <= maximum:
        raise TaskError(f"{name} 超出允许范围 1 至 {maximum}")
    return n

def flag(name):
    value = os.getenv(name, "0").strip().lower()
    if value not in TRUE | FALSE:
        raise TaskError(f"{name} 必须为 1 或 0（也接受 true/false、yes/no、on/off）")
    return value in TRUE

def timeout_seconds():
    try:
        value = float(os.getenv("DUOKAN_TIMEOUT", "15"))
    except ValueError:
        raise TaskError("DUOKAN_TIMEOUT 必须为 1 至 60 的秒数") from None
    if not math.isfinite(value) or not 1 <= value <= 60:
        raise TaskError("DUOKAN_TIMEOUT 必须为 1 至 60 的秒数")
    return value

def account_lines():
    canonical = os.getenv("DUOKAN_COOKIE", "").strip()
    raw = canonical or os.getenv("DUOKAN", "").strip()
    if not raw:
        raise TaskError("缺少必填环境变量 DUOKAN_COOKIE（兼容 DUOKAN）")
    if not canonical and raw.startswith("["):
        try:
            data = json.loads(raw)
            if not isinstance(data, list) or not data:
                raise ValueError()
            return [entry.get("cookie") if isinstance(entry, dict) else None for entry in data]
        except ValueError:
            raise TaskError("DUOKAN 兼容 JSON 格式错误") from None
    return [line.strip() for line in raw.splitlines() if line.strip()]

def parse_cookie(line):
    if not isinstance(line, str) or not line.strip():
        raise TaskError("账号 Cookie 为空或格式错误")
    values = {}
    SECRETS.append(line)
    for field in line.split(";"):
        if not field.strip():
            continue
        key, sep, value = field.strip().partition("=")
        if not sep or not key or not value or any(c in key for c in " \t\r\n"):
            raise TaskError("Cookie 格式错误，应为字段=值，以分号分隔")
        if key in values:
            raise TaskError("Cookie 字段重复")
        values[key] = value
        if key.lower() not in ("uid", "user_id", "userid"):
            SECRETS.append(value)
    if not values.get("device_id") or len(values) < 2:
        raise TaskError("Cookie 必须包含 device_id 和登录会话字段")
    return values

class Client:
    def __init__(self, cookies, dry, timeout):
        self.cookies = cookies
        self.dry = dry
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())
        self.identities = set()

    def signed(self, **extra):
        t = int(time.time())
        c = 0
        for character in f"{self.cookies['device_id']}&{t}":
            c = (c * 131 + ord(character)) % 65536
        return dict(extra, _t=t, _c=c)

    def request(self, path, data=None):
        if self.dry:
            raise TaskError("断网预演禁止 HTTP 请求")
        headers = {"Content-Type":"application/x-www-form-urlencoded; charset=utf-8", "Cookie":"; ".join(f"{k}={v}" for k,v in self.cookies.items())}
        req = Request("https://www.duokan.com" + path, data=None if data is None else urlencode(data).encode(), headers=headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                if response.status != 200:
                    raise TaskError("接口 HTTP 状态异常")
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise TaskError("接口响应过大")
                result = json.loads(raw)
        except TaskError:
            raise
        except Exception:
            raise TaskError("HTTP、网络或 JSON 响应异常（详情已脱敏）") from None
        if not isinstance(result, dict):
            raise TaskError("接口响应结构异常")
        containers = [result]
        if isinstance(result.get("data"), dict):
            containers.append(result["data"])
        for obj in list(containers):
            if isinstance(obj.get("user"), dict):
                containers.append(obj["user"])
        for obj in containers:
            if isinstance(obj, dict):
                for field in ("nickname", "username", "display_name", "uid"):
                    identity = obj.get(field)
                    if not isinstance(identity, (str, int)) or isinstance(identity, bool):
                        continue
                    identity = str(identity)
                    if (not identity or any(ord(c) < 32 for c in identity)
                            or re.fullmatch(r"(?:\+?86)?1[3-9]\d{9}", identity)
                            or any(secret and secret in identity for key, secret in self.cookies.items()
                                   if key.lower() not in ("uid", "user_id", "userid"))):
                        continue
                    if (field, identity) not in self.identities:
                        self.identities.add((field, identity))
                        log(f"官方账号身份 {field}：{identity}")
        return result

    @staticmethod
    def verify(result):
        # 保留源码已明确使用的 result=0、msg=成功；其它响应失败闭合。
        msg = result.get("msg")
        code = result.get("result")
        if isinstance(msg, str) and any(word in msg for word in
                ("失败", "尚未登录", "未登录", "失效", "错误")):
            raise TaskError("接口报告业务失败")
        if (type(code) is int and code == 0) or (code is None and msg in ("成功", "签到成功")):
            return "success"
        if code is None and msg in ("今日已签到", "今天已签到", "已经签到", "已签到"):
            return "already"
        raise TaskError("未获得可验证的业务成功标志，请核对登录状态或活动有效期")

    def awards(self):
        r = self.request("/store/v0/award/coin/list", self.signed(sandbox=0, withid=1))
        if "result" in r:
            self.verify(r)
        msg = r.get("msg")
        if isinstance(msg, str) and any(word in msg for word in ("尚未登录", "未登录", "登录失效")):
            raise TaskError("书豆查询登录状态无效")
        data = r.get("data")
        awards = data.get("award") if isinstance(data, dict) else None
        if not isinstance(awards, list) or any(
                not isinstance(x, dict) or type(x.get("coin")) not in (int, float)
                or not math.isfinite(x["coin"]) or x["coin"] < 0 for x in awards):
            raise TaskError("书豆列表响应结构异常")
        return awards

    def execute(self, action, limit):
        if action == "sign":
            return self.verify(self.request("/checkin/v0/checkin", self.signed()))
        if action in ("info", "delay"):
            awards = self.awards()
            log(f"当前书豆：{sum(x['coin'] for x in awards)}；到期批次：{len(awards)}")
            count = 0
            for x in awards:
                # 日期仅接受日期格式，避免输出未知响应内容。
                date = str(x.get("expire", ""))
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                    log(f"{date} 到期书豆：{x['coin']}")
                if action == "delay" and x.get("delay") == 1:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                        raise TaskError("延期日期格式未知，未发送修改请求")
                    self.verify(self.request("/store/v0/award/coin/delay", self.signed(date=date, withid=1)))
                    count += 1
                    log(f"延期成功：第 {count} 批")
            return "already" if action == "delay" and count == 0 else "success"
        if action == "free":
            r = self.request("/hs/v4/channel/query/2027")
            if "result" in r:
                self.verify(r)
            try:
                bid = r["items"][0]["data"]["book_id"]
                if not isinstance(bid,(str,int)) or isinstance(bid,bool) or not str(bid):
                    raise ValueError()
            except (KeyError, IndexError, TypeError, ValueError):
                raise TaskError("限免书籍响应结构异常") from None
            # price=0 沿用源码；只有显式 free 选项才能创建订单。
            result = self.request("/store/v0/payment/book/create", dict(payment_name="BC", ch="VSZUVB", book_id=bid, price=0, allow_discount=1))
            book = result.get("book")
            title = book.get("title") if isinstance(book, dict) else None
            msg = result.get("msg")
            if isinstance(msg, str) and any(word in msg for word in ("尚未登录", "未登录", "登录失效")):
                raise TaskError("领取限免书籍登录状态无效")
            if not isinstance(title, str) or not title.strip():
                raise TaskError("未获得可验证的限免书籍信息")
            if not ((type(result.get("result")) is int and result["result"] == 0) or
                    ("result" not in result and isinstance(msg, str) and
                     ("成功" in msg or any(word in msg for word in ("已经购买", "已购买", "已拥有"))))):
                raise TaskError("未获得可验证的限免领取成功标志")
            if isinstance(msg, str) and any(word in msg for word in
                    ("失败", "尚未登录", "未登录", "失效", "错误")):
                raise TaskError("限免领取接口报告业务失败")
            log(f"今日限免书籍：{title}")
            return "success"
        if action == "gift":
            r = self.request("/events/common_task_gift_check", self.signed(code="KYKJF7LL0G", withid=1))
            if r.get("result") is not None:
                self.verify(r)
            elif r.get("msg") in ("尚未登录", "未登录", "登录失效"):
                raise TaskError("体验活动登录状态无效")
            chances = r.get("chances")
            if type(chances) is not int or chances < 0:
                raise TaskError("体验奖励机会数无效")
            if chances == 0:
                return "already"
            if chances > limit:
                raise TaskError("体验奖励机会数超过安全上限，未发送领取请求")
            claimed = 0
            # 上游会遍历全部签名；失败签名不代表账号失败，只有最终无法领取才失败。
            for sign in GIFT_SIGNS:
                result = self.request("/events/common_task_gift", self.signed(code="KYKJF7LL0G", chances=1, sign=sign, withid=1))
                msg = result.get("msg")
                if isinstance(msg, str) and any(word in msg for word in ("尚未登录", "未登录", "登录失效")):
                    raise TaskError("体验奖励登录状态无效")
                if (type(result.get("result")) is int and result["result"] == 0) or msg == "成功":
                    claimed += 1
                    log(f"体验奖励第 {claimed}/{chances} 次：成功")
                    if claimed == chances:
                        return "success"
            raise TaskError(f"体验奖励仅验证成功 {claimed}/{chances} 次")
        if action in ("add_draw", "draw"):
            endpoint = "chances/add" if action == "add_draw" else "drawing"
            for i in range(6):
                extra = dict(code="8ulcky4bknbe_f", withid=1)
                if action == "add_draw":
                    extra["count"] = 1
                self.verify(self.request("/store/v0/event/"+endpoint, self.signed(**extra)))
                log(f"{LABELS[action]}第 {i+1}/6 次：成功")
            return "success"
        if action == "download":
            count = 0
            for i in range(limit):
                r = self.request("/events/common_task_gift", self.signed(code="J18UK6YYAY", chances=17, withid=1))
                if type(r.get("result")) is int and r["result"] == 130014:
                    log(f"下载奖励已结束，本轮领取 {count} 次")
                    return "already" if count == 0 else "success"
                self.verify(r)
                count += 1
                log(f"下载奖励第 {count} 次：成功")
            raise TaskError("下载奖励达到安全次数上限，未确认任务结束")
        if action == "task":
            count = 0
            for _ in range(3):
                for code in TASK_CODES:
                    self.verify(self.request("/events/tasks_gift", self.signed(code=code, chances=3, withid=1)))
                    count += 1
                    log(f"其他奖励第 {count}/15 次：成功")
            return "success"
        raise TaskError("未知任务")

def notification_selected():
    if "QINGLONG_NOTIFY" in os.environ:
        return os.environ["QINGLONG_NOTIFY"].strip().lower() not in FALSE
    configured = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if configured is None:
        return True
    selectors = [item.lower() for item in re.split(r"[,;\s]+", configured.strip()) if item]
    if not selectors:
        return False
    identities = NOTIFICATION_IDENTITIES | {Path(__file__).name.lower()}
    return any(selector == "*" or any(fnmatch.fnmatchcase(identity, selector) for identity in identities)
               for selector in selectors)

def notify(summary, dry):
    if os.getenv("QINGLONG_NOTIFY", "auto").strip().lower() in FALSE:
        return "已关闭"
    if not notification_selected():
        return "未列入通知清单"
    body = (f"账号总数：{summary['accounts']}，成功：{summary['success']}，失败：{summary['failure']}；"
            f"状态：{summary['status']}；子任务成功：{summary['steps']['success']}，失败：{summary['steps']['failure']}")
    if dry:
        log("✅ 通知预演：" + body + "（未加载通知模块，未联网）")
        return "预演已模拟通知"
    # 真实运行加载青龙 Python 通知入口；捕获模块输出避免泄漏凭据。
    previous_alarm = signal.getsignal(signal.SIGALRM)
    def notify_timeout(signum, frame):
        raise TimeoutError("通知超时")
    signal.signal(signal.SIGALRM, notify_timeout)
    signal.alarm(20)
    original_socket = socket.socket
    original_connection = socket.create_connection
    original_resolver = socket.getaddrinfo
    def deny(*args, **kwargs):
        raise OSError("断网预演禁止通知联网")
    if dry:
        socket.socket = deny
        socket.create_connection = deny
        socket.getaddrinfo = deny
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            module = None
            try:
                module = importlib.import_module("notify")
            except ImportError:
                paths = []
                if os.getenv("QINGLONG_NOTIFY_DIR"):
                    paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"])/"notify.py")
                paths += [Path("/ql/data/scripts/notify.py"),Path("/ql/scripts/notify.py")]
                for path in paths:
                    if path.is_file():
                        spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        break
            if module and callable(getattr(module,"send",None)):
                module.send("多看阅读", clean(body))
                return "已调用（断网预演）" if dry else "已调用"
            if not dry:
                paths = []
                if os.getenv("QINGLONG_NOTIFY_DIR"):
                    paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"])/"sendNotify.js")
                paths += [Path("/ql/data/scripts/sendNotify.js"),Path("/ql/scripts/sendNotify.js")]
                for path in paths:
                    if path.is_file():
                        js = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
                        p = subprocess.run(["node","-e",js,str(path),"多看阅读",clean(body)], capture_output=True, timeout=20)
                        return "已调用" if p.returncode == 0 else "发送失败"
        return "通知模块不可用（业务退出码保留）"
    except Exception:
        return "通知发送失败（业务退出码保留）"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_alarm)
        socket.socket = original_socket
        socket.create_connection = original_connection
        socket.getaddrinfo = original_resolver

def main():
    started = time.monotonic()
    dry = os.getenv("DUOKAN_DRY_RUN", "0").strip().lower() in TRUE
    lines = []
    log("========== 多看阅读 ==========")
    log("开始时间："+time.strftime("%Y-%m-%d %H:%M:%S"))
    summary = dict(accounts=len(lines),success=0,failure=0,dryRun=dry,steps=dict(total=0,success=0,already=0,skipped=0,failure=0))
    config_error = False
    try:
        dry = flag("DUOKAN_DRY_RUN")
        lines = account_lines()
        summary['accounts'] = len(lines)
        summary['dryRun'] = dry
        log(f"模式：{'断网预演' if dry else '正式运行'}；账号数：{len(lines)}")
        actions = [x.strip() for x in os.getenv("DUOKAN_TASKS", "sign,info").split(",") if x.strip()]
        if not actions or len(set(actions)) != len(actions) or any(x not in LABELS for x in actions):
            raise TaskError("DUOKAN_TASKS 为空、重复或包含未知任务")
        for name, action in (("DUOKAN_DELAY", "delay"), ("DUOKAN_FREE", "free"),
                             ("DUOKAN_DRAW", "draw")):
            if flag(name) and action not in actions:
                actions.append(action)
        timeout = timeout_seconds()
        limit = integer("DUOKAN_MAX_REWARDS",20,200)
    except TaskError as exc:
        log(f"❌ 配置错误：{exc}")
        config_error = True
        summary['failure'] = len(lines)
    if not config_error:
        for number, line in enumerate(lines,1):
            account_start = time.monotonic()
            stats = dict(total=len(actions),success=0,already=0,skipped=0,failure=0)
            log(f"账号 {number} 开始")
            try:
                cookies = parse_cookie(line)
                client = Client(cookies,dry,timeout)
            except TaskError as exc:
                log(f"❌ 账号 {number} 配置错误：{exc}")
                stats['failure'] = len(actions)
            else:
                for stage, action in enumerate(actions,1):
                    stage_start = time.monotonic()
                    log(f"账号 {number} 阶段 {stage}/{len(actions)}：{LABELS[action]}")
                    try:
                        if dry:
                            stats['skipped'] += 1
                            log("⏭️ DRY_RUN_OK：配置有效，计划已验证，未请求接口或变更账号")
                        else:
                            outcome = client.execute(action,limit)
                            stats[outcome] += 1
                            log("✅ 业务成功" if outcome == "success" else "☑️ 已完成")
                    except Exception as exc:
                        stats['failure'] += 1
                        log(f"❌ {exc if isinstance(exc,TaskError) else '处理异常（详情已脱敏）'}")
                    log(f"阶段耗时：{time.monotonic()-stage_start:.2f} 秒")
            summary['failure' if stats['failure'] else 'success'] += 1
            for key in stats:
                summary['steps'][key] += stats[key]
            log(f"账号 {number} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['already']}，跳过 {stats['skipped']}，失败 {stats['failure']}，耗时 {time.monotonic()-account_start:.2f} 秒")
    summary['status'] = 'configuration-error' if config_error else ('partial-failure' if summary['failure'] and summary['success'] else 'failure' if summary['failure'] else 'dry-run' if dry else 'success')
    code = 2 if config_error else 1 if summary['failure'] else 0
    summary['notification'] = notify(summary,dry)
    summary['elapsedSeconds'] = round(time.monotonic()-started,2)
    summary['finishTime'] = time.strftime("%Y-%m-%d %H:%M:%S")
    log("----------------------------------------")
    log(f"账号统计：总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failure']}")
    log(f"子任务统计：{json.dumps(summary['steps'],ensure_ascii=False)}")
    log(f"总耗时：{summary['elapsedSeconds']} 秒；完成时间：{summary['finishTime']}")
    log(f"通知状态：{summary['notification']}；最终状态：{summary['status']}")
    print("TASK_SUMMARY="+json.dumps(summary,ensure_ascii=False,separators=(',',':')))
    return code

if __name__ == "__main__":
    sys.exit(main())
