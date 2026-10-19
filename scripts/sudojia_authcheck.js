// name: 多合一账号失效检测
// cron: 32 12,21 * * *
/**
 * name: 多合一账号失效检测
 * cron: 10 12,21 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia；https://blog.imzjw.cn；2024/09/24
 * 上游：sudojia/AutoTaskScript src/other/sudojia_authCheck.js
 * 检测现有脚本仓库凭证（Token、Cookie）等是否失效。
 * 上游默认关闭；上游说明：每天跑两次，仅推送失效账号。
 * 维护版：所有运行状态均生成脱敏通知；未验证检查不视为成功。
 * AUTH_CHECK_ACCOUNTS：每行一个 JSON：{"service":"变量名","credential":"该账号凭据"}。
 * 兼容原有变量，每行一个账号；不再以 & 分隔账号。
 * ENABLE_CHECK_TOKEN=true 才执行；AUTH_CHECK_DRY_RUN=1 完全断网预演。
 * AUTH_CHECK_ALLOW_MUTATIONS=true 显式允许登录、刷新、同步、活动参与探测。
 * MOTO_TOKEN 为 token#uid，SHUI_FEI_COOKIE 为 Cookie#memberId（只在首个 # 分割）。
 * BW_TEA_TOKEN/INSTAX_TOKEN/MAWUW_TOKEN 兼容 token#附加字段；TEBU_JSON 为请求头 JSON。
 * 厚工坊、库街区、南航缺少可证实的正向契约，维护版拒绝在线调用并报未验证。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["505cfecf6964c372", "scripts/sudojia_authcheck.js", "sudojia_authcheck.js", "sudojia_authcheck"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const started = Date.now();
const dry = process.env.AUTH_CHECK_DRY_RUN === '1';
const enabled = process.env.ENABLE_CHECK_TOKEN === 'true';
const allowMutations = process.env.AUTH_CHECK_ALLOW_MUTATIONS === 'true';
const stats = {accounts: 0, success: 0, failed: 0, skipped: 0, tasks: 0};
const results = [];
let currentIdentity = '';
const secrets = [];
const $ = {source: 'h5', wait: ms => new Promise(resolve => setTimeout(resolve, ms))};
const sudojia = {
  getRandomUserAgent: () => 'Mozilla/5.0',
  getRandomWait: () => 1000,
  md5: value => crypto.createHash('md5').update(value).digest('hex'),
  sendRequest: request
};
function stamp() { return new Date().toLocaleTimeString('zh-CN', {hour12: false}); }
function log(message) { console.log(`[${stamp()}] ${message}`); }
function splitPair(value) {
  const i = value.indexOf('#');
  return i < 0 ? [value] : [value.slice(0,i), value.slice(i+1)];
}
function createHeaders(type, ...custom) {
  const headers = {'User-Agent': sudojia.getRandomUserAgent(type)};
  for (const item of custom) {
    const i = item.indexOf('@');
    if (i > 0 && item.slice(i+1)) headers[item.slice(0,i)] = item.slice(i+1);
  }
  return headers;
}
function getLaoBanToken(openid) {
  const timestamp = Date.now();
  return {is_need_sync: 0, timestamp, token: sudojia.md5(`${timestamp}wqewq${openid}`), openid};
}
function captureIdentity(data) {
  if (!data || typeof data !== 'object') return;
  const objects = [data, data.data, data.body, data.resultJson, data.Result];
  for (const item of [...objects]) if (item && typeof item === 'object') {
    for (const key of ['user', 'userinfo', 'member', 'VipInfo']) if (item[key]) objects.push(item[key]);
  }
  for (const item of objects) if (item && typeof item === 'object') {
    for (const key of ['nickname', 'nickName', 'username', 'displayName', 'userId', 'uid']) {
      const value = item[key];
      if ((typeof value === 'string' || typeof value === 'number') && String(value) &&
          !secrets.some(s => s && String(value).includes(s)) && !/1[3-9]\d{9}/.test(String(value)) &&
          !/[\r\n]/.test(String(value))) { currentIdentity = String(value); return; }
    }
  }
}
async function request(url, method, headers, body) {
  if (dry) throw new Error('预演禁止网络');
  if (!url.startsWith('https://')) throw new Error('禁止明文接口');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const options = {method: method.toUpperCase(), headers: {...headers}, signal: controller.signal, redirect: 'error'};
    for (const key of Object.keys(options.headers)) if (key.toLowerCase() === 'accept-encoding') delete options.headers[key];
    if (body !== undefined && !['GET', 'HEAD'].includes(options.method)) {
      options.body = typeof body === 'string' ? body : JSON.stringify(body);
      if (!Object.keys(options.headers).some(k => k.toLowerCase() === 'content-type')) options.headers['Content-Type'] = 'application/x-www-form-urlencoded';
    }
    const res = await fetch(url, options);
    if (!res.ok) throw new Error('HTTP 检查失败');
    const chunks = []; let size = 0;
    for await (const chunk of res.body) {
      size += chunk.length;
      if (size > 1048576) { controller.abort(); throw new Error('响应超限'); }
      chunks.push(chunk);
    }
    const text = Buffer.concat(chunks).toString('utf8');
    if (['club.fnnas.com','www.v2ex.com','www.znds.com'].includes(new URL(url).hostname)) return text;
    let data;
    try { data = JSON.parse(text); } catch { throw new Error('响应格式不符'); }
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('响应结构不符');
    captureIdentity(data);
    return data;
  } finally { clearTimeout(timer); }
}
const accounts = [
    {
        name: '所有女生',
        env: 'ALL_GIRLS_TOKEN',
        list: process.env.ALL_GIRLS_TOKEN ? process.env.ALL_GIRLS_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://7.wawo.cc/api/account/wx/member/base`, 'get', createHeaders('wx_mini', `authorization@bearer ${token}`, 'Content-Type@application/json', 'referer@https://servicewechat.com/wx7d1403fe84339669/1076/page-frame.html'));
            return '000' !== data.code || !data.data;
        },
    },
    {
        name: '安慕希',
        env: 'AMX_TOKEN',
        list: process.env.AMX_TOKEN ? process.env.AMX_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://amxshop.yili.com/api/user/getUser`, 'get', createHeaders('wx_mini', `accesstoken@${token}`, 'Content-Type@application/x-www-form-urlencoded', 'referer@https://servicewechat.com/wxf2a6206f7e2fd712/666/page-frame.html'));
            return '未登陆或登陆超时' === data.msg || !data.data;
        },
    },
    {
        name: '霸王茶姬',
        env: 'BW_TEA_TOKEN',
        list: process.env.BW_TEA_TOKEN ? process.env.BW_TEA_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            token = splitPair(token)[0];
            const data = await sudojia.sendRequest(`https://webapi2.qmai.cn/web/catering2-apiserver/crm/customer-center?appid=wxafec6f8422cb357b`, 'get', createHeaders('wx_mini', `qm-user-token@${token}`, 'Content-Type@application/json', 'qm-from@wechat'));
            return data.status !== true || !data.data;
        },
    },
    {
        name: '飞牛私有云',
        env: 'FN_NAS_COOKIE',
        list: process.env.FN_NAS_COOKIE ? process.env.FN_NAS_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://club.fnnas.com`, 'get', createHeaders('PC', `Cookie@${token}`, 'Accept-Encoding@gzip, deflate, br, zstd'));
            const match = data.match(/class=["'][^"']*icon_msg[^"']*["'][\s\S]{0,2000}?href=["'][^"']*uid=(\d+)/);
            return !match || Number(match[1]) <= 0;
        },
    },
    {
        name: '国乐酱酒',
        env: 'GYJ_TOKEN',
        list: process.env.GYJ_TOKEN ? process.env.GYJ_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://member.guoyuejiu.com/api/user/info`, 'get', createHeaders('wx_mini', `Authorization@${token}`, 'Content-Type@application/json', 'Host@member.guoyuejiu.com', 'referer@https://servicewechat.com/wxeff120e4d11594c0/72/page-frame.html'));
            return 1011 === data.code || !data.data || typeof data.data !== "object";
        },
    },
    {
        name: '厚工坊',
        env: 'HGF_COOKIE',
        list: process.env.HGF_COOKIE ? process.env.HGF_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://api.hgf1862.com/YUN//Game/2021/QianDao/QianDaoAjax_By28.aspx?op=now&vers=`, 'post', createHeaders('wx_mini', `Cookie@user=SessionID=${token}`, 'Accept@application/json, text/javascript, */*; q=0.01'));
            throw new Error("缺少厚工坊成功响应契约，无法验证");
        },
    },
    {
        name: '海澜之家-游戏',
        env: 'HLZJ_UNID',
        list: process.env.HLZJ_UNID ? process.env.HLZJ_UNID.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://gmdevpro.hlzjppgl.cn/server/api/authorized-login`, 'post', createHeaders('wx_mini', `Cookie@user=SessionID=${token}`, 'Content-Type@application/json', 'Host@gmdevpro.hlzjppgl.cn'), {
                "union_id": token,
                "invite_user_id": ""
            });
            return 200 !== data.code || !data.data.token;
        },
    },
    {
        name: '媓钻护肤品',
        env: 'HZHFP_TOKEN',
        list: process.env.HZHFP_TOKEN ? process.env.HZHFP_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const headers = createHeaders(
                'wx_mini',
                `Authorization@Bearer ${token}`,
                'Content-Type@application/json;charset=UTF-8',
                'Host@api.hzyxhfp.com',
                'referer@https://servicewechat.com/wx3df7476c42cace5d/377/page-frame.html',
                'app@wx3df7476c42cace5d',
            );
            const data = await sudojia.sendRequest(`https://api.hzyxhfp.com/api/users/getUserDetailInfo`, 'post', headers);
            return 0 !== data.code || !data.data;
        },
    },
    {
        name: '玩拍由我俱乐部',
        env: 'INSTAX_TOKEN',
        list: process.env.INSTAX_TOKEN ? process.env.INSTAX_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            token = splitPair(token)[0];
            const data = await sudojia.sendRequest(`https://instax.app.xcxd.net.cn/api/me`, 'get', createHeaders('wx_mini', `Authorization@Bearer ${token}`, 'Content-Type@application/json', 'Host@instax.app.xcxd.net.cn', 'referer@https://servicewechat.com/wx3cb572fbf3aa30c8/136/page-frame.html'));
            return Boolean(data.error) || !data.data;
        },
    },
    {
        name: '金典有机生活+',
        env: 'JINDIAN_TOKEN',
        list: process.env.JINDIAN_TOKEN ? process.env.JINDIAN_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://msmarket.msx.digitalyili.com/gateway/api/auth/account/user/info`, 'get', createHeaders('wx_mini', `access-token@${token}`, 'Content-Type@application/json', 'referer@https://servicewechat.com/wxf32616183fb4511e/616/page-frame.html'));
            return !data.status || !data.data.userId;
        },
    },
    {
        name: '嘉立创',
        env: 'JLC_TOKEN',
        list: process.env.JLC_TOKEN ? process.env.JLC_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://m.jlc.com/api/appPlatform/center/setting/selectPersonalInfo`, 'get', createHeaders('PC', `x-jlc-accesstoken@${token}`, 'x-jlc-clienttype@WEB', 'accept@application/json, text/plain, */*', 'referer@https://m.jlc.com/mapp/pages/my/index'), '');
            return 200 !== data.code || !data.data.customerLinkPhone
        },
    },
    {
        name: '植白说官方商城',
        env: 'KOZBS_TOKEN',
        list: process.env.KOZBS_TOKEN ? process.env.KOZBS_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://www.kozbs.com/demo/wx/user/getUserIntegral`, 'get', createHeaders('wx_mini', `x-dts-token@${token}`, 'Content-Type@application/json', 'referer@https://servicewechat.com/wx6b6c5243359fe265/153/page-frame.html'));
            return '无效用户' === data.errmsg || 0 !== data.errno;
        },
    },
    {
        name: '开天工作室',
        env: 'KTGZS_TOKEN',
        list: process.env.KTGZS_TOKEN ? process.env.KTGZS_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://api.box.vipinfinity.com/user`, 'get', createHeaders('wx_mini', `Authorization@${token}`, 'Client-Name@default', 'Content-Type@application/json', 'Client-Type@wechat--miniapp-windows', 'Host@api.box.vipinfinity.com', 'referer@https://servicewechat.com/wxa1ff7cf5ddff1da2/9/page-frame.html'));
            return 0 !== data.code || !data.data.user;
        },
    },
    {
        name: '库街区',
        env: 'KURO_TOKEN',
        list: process.env.KURO_TOKEN ? process.env.KURO_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            $.source = 'h5';
            let data = await sudojia.sendRequest(`https://api.kurobbs.com/gamer/widget/game3/refresh`, 'post', {
                "source": $.source,
                'token': token,
            }, `type=2&sizeType=1`);
            if (220 === data.code) {
                $.source = 'android';
                await $.wait(sudojia.getRandomWait(1000, 1500));
                data = await sudojia.sendRequest(`https://api.kurobbs.com/gamer/widget/game3/refresh`, 'post', {
                    "source": $.source,
                    'token': token,
                }, `type=2&sizeType=1`);
                throw new Error("缺少库街区成功响应契约，无法验证");
            }
            throw new Error("缺少库街区成功响应契约，无法验证");
        },
    },
    {
        name: '老板电器服务微商城',
        env: 'LAOBAN_OPENID',
        list: process.env.LAOBAN_OPENID ? process.env.LAOBAN_OPENID.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://vip.foxech.com/index.php/api/member/get_member_info`, 'post', createHeaders('wx_mini', 'Content-Type@application/json', 'referer@https://servicewechat.com/wxc8c90950cf4546f6/157/page-frame.html'), getLaoBanToken(token));
            return '200' !== data.code || !data.data;
        },
    },
    {
        name: '龙湖天街',
        env: 'LONG_FOR_TOKEN',
        list: process.env.LONG_FOR_TOKEN ? process.env.LONG_FOR_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://gw2c-hw-open.longfor.com/riyuehu-miniapp-prod/service/ryh/user/info`, 'post', createHeaders('wx_mini', 'X-Gaia-Api-Key@646fce29-3a77-462a-aabe-0fe77bc3023f', `token@${token}`, 'Content-Type@application/json'), {
                "data": {
                    "projectId": "B379F9F1-C176-4925-B6F6-92555AC62E61"
                }
            });
            return 10000 !== data.code || !data.data;
        },
    },
    {
        name: '欣都龙城',
        env: 'MALLCOO_TOKEN',
        list: process.env.MALLCOO_TOKEN ? process.env.MALLCOO_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://m.mallcoo.cn/api/user/user/GetUserAndMallCard`, 'post', createHeaders('wx_mini', 'Content-Type@application/json', 'referer@https://servicewechat.com/wx7ef63cf605a639fb/18/page-frame.html'), {
                "MallId": 10144,
                "Header": {
                    "Token": token,
                    "systemInfo": {
                        "model": "microsoft",
                        "SDKVersion": "3.5.0",
                        "system": "Windows 11 x64",
                        "version": "3.9.10",
                        "miniVersion": "2.67.7"
                    }
                }
            });
            return data.m !== 1;
        },
    },
    {
        name: '馬伍旺饮料厂',
        env: 'MAWUW_TOKEN',
        list: process.env.MAWUW_TOKEN ? process.env.MAWUW_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            token = splitPair(token)[0];
            const data = await sudojia.sendRequest(`https://webapi.qmai.cn/web/catering/crm/customer-center?appid=wxc1381dc6f2213b72`, 'get', createHeaders('wx_mini', `qm-user-token@${token}`, 'Content-Type@application/json', 'qm-from@wechat'));
            return !data.status || !data.data;
        },
    },
    {
        name: '美的会员',
        env: 'MIDEA_COOKIE',
        list: process.env.MIDEA_COOKIE ? process.env.MIDEA_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://mvip.midea.cn/next/mucuserinfo/getmucuserinfo`, 'get', createHeaders('wx_mini', `Cookie@${token}`, 'Content-Type@application/json', 'referer@https://servicewechat.com/wx03925a39ca94b161/437/page-frame.html'));
            return 0 !== data.errcode || !data.data.userinfo;
        },
    },
    {
        name: '摩托范',
        env: 'MOTO_TOKEN',
        list: process.env.MOTO_TOKEN ? process.env.MOTO_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const [ck, uid] = splitPair(token)
            const headers = createHeaders(
                'H5',
                `token@${ck}`,
                'Content-Type@application/x-www-form-urlencoded',
                'referer@api.58moto.com',
                `timestamp@${Date.now()}`,
                'version@3.57.63'
            );
            const data = await sudojia.sendRequest(`https://api.58moto.com/user/center/info/v2/principal`, 'post', headers, `uid=${encodeURIComponent(uid)}`);
            return 0 !== data.code || !data.data.mobile
        },
    },
    {
        name: '南方航空',
        env: 'NFHK_COOKIE',
        list: process.env.NFHK_COOKIE ? process.env.NFHK_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://wxapi.csair.com/marketing-tools/activity/join?type=APPTYPE&chanel=ss&lang=zh`, 'post', createHeaders('wx_mini', `Cookie@${[`sign_user_token=${token}`, `TOKEN=${token}`, `cs1246643sso=${token}`,].join('; ')}`, 'User-Agent@okhttp/3.12.1;jdmall;android;version/10.3.4;build/92451;', 'Content-Type@application/json'), {
                "activityType": "sign",
                "channel": "app",
                "entrance": 1,
            });
            throw new Error("缺少南方航空成功响应契约，无法验证");
        },
    },
    {
        name: '胖哥俩肉蟹煲',
        env: 'PANG_GE_TOKEN',
        list: process.env.PANG_GE_TOKEN ? process.env.PANG_GE_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const headers = createHeaders(
                'wx_mini',
                'deviceWidth@400',
                'Host@saash5.namek.com.cn',
                'tenantId@24',
                'Accept@*/*',
                'Content-Type@application/json;charset=UTF-8',
                'Accept-Encoding@gzip, deflate, br',
                'referer@https://servicewechat.com/wxe61905cae01a6c7d/67/page-frame.html',
                'clientVersion@3.2.0',
                `timestamp@${Date.now()}`,
                `token@${token}`
            )
            const data = await sudojia.sendRequest(`https://saash5.namek.com.cn//api/v1/member/personal?shopId=24`, 'get', headers);
            return !data.body || !data.body.member;
        },
    },
    {
        name: '皮皮世界',
        env: 'PPX_COOKIE',
        list: process.env.PPX_COOKIE ? process.env.PPX_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://api.pipix.com/bds/user/user_profile/`, 'get', createHeaders('H5', 'Accept-Encoding@gzip', 'host@api.pipix.com', `Cookie@sessionid=${token}`), {});
            return data.status_code !== 0 || !data.data || !data.data.user;
        },
    },
    {
        name: '水费易签到',
        env: 'SHUI_FEI_COOKIE',
        list: process.env.SHUI_FEI_COOKIE ? process.env.SHUI_FEI_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const [cookie, mId] = splitPair(token);
            const data = await sudojia.sendRequest(`https://m.ipaiyun.cn/PersonalCenter/PersonalCenter/GetShopMemberDetail`, 'post', createHeaders('PC', `Cookie@${cookie}`, 'Accept@*/*', 'referer@https://m.ipaiyun.cn/Ipai/Home/Index?code=031sLtFa11eBTH0d0uFa1NqtY53sLtFQ&state=wxbe5b7a2bc0467240', 'Content-Type@application/x-www-form-urlencoded; charset=UTF-8'), `memberId=${encodeURIComponent(mId)}`);
            return 0 !== data.code || !data.resultJson.meberinfo;
        },
    },
    {
        name: '特步会员中心',
        env: 'TEBU_JSON',
        list: process.env.TEBU_JSON ? process.env.TEBU_JSON.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const headers = createHeaders('wx_mini', 'ezr-source@weapp', 'content-type@application/json', 'referer@https://servicewechat.com/wx12e1cb3b09a0e6f0/121/page-frame.html')
            for (const [key, value] of Object.entries(JSON.parse(token))) {
                headers[key] = value;
            }
            const data = await sudojia.sendRequest(`https://wxa-tp.ezrpro.com/myvip/FamilyCard/GetVipCardInfoByVipId`, 'get', headers);
            return 200 !== data.Status || !data.Result.VipInfo;
        },
    },
    {
        name: '贴吧签到',
        env: 'TIE_BA_COOKIE',
        list: process.env.TIE_BA_COOKIE ? process.env.TIE_BA_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const headers = createHeaders('H5', 'Content-Type@application/x-www-form-urlencoded');
            const matchList = token.match(/BDUSS=([^;]+);?/);
            if (matchList) {
                headers.Cookie = `BDUSS=${matchList[1]}`;
            } else {
                headers.Cookie = `BDUSS=${token}`;
            }
            const data = await sudojia.sendRequest(`https://tieba.baidu.com/dc/common/tbs`, 'get', headers);
            return !data.tbs || 1 !== data.is_login;
        },
    },
    {
        name: '贴吧任务签到',
        env: 'TIE_BA_COOKIE',
        list: process.env.TIE_BA_COOKIE ? process.env.TIE_BA_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest(`https://tieba.baidu.com/mo/q/usergrowth/showUserGrowth?client_type=2&client_version=12.60.1.2`, 'get', createHeaders('H5', `Cookie@${token}`));
            return !data.data.tbs || !data.data.user;
        },
    },
    {
        name: 'V2EX每日签到',
        env: 'V2EX_COOKIE',
        list: process.env.V2EX_COOKIE ? process.env.V2EX_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest('https://www.v2ex.com', 'get', createHeaders('PC', `Cookie@${token}`, 'Accept-Encoding@gzip, deflate, br', 'Accept@text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'));
            return !(data.indexOf('登出') > -1);
        },
    },
    {
        name: '心喜',
        env: 'XINXI_TOKEN',
        list: process.env.XINXI_TOKEN ? process.env.XINXI_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest('https://api.xinc818.com/mini/user', 'get', createHeaders('wx_mini', `sso@${token}`, 'Accept-Encoding@gzip, deflate, br', 'Content-Type@application/json', 'referer@https://servicewechat.com/wx673f827a4c2c94fa/276/page-frame.html'));
            return 40001 === data.code || !data.data || !data.data.nickname;
        },
    },
    {
        name: '兴攀农场',
        env: 'XPFARM_TOKEN',
        list: process.env.XPFARM_TOKEN ? process.env.XPFARM_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest('https://p.xpfarm.cn/treemp/user.PersonalCenter/getInfo', 'post', createHeaders('wx_mini', `authorization@${token}`, 'Accept-Encoding@gzip, deflate, br', 'Content-Type@application/json', 'referer@https://servicewechat.com/wx27e219ff3142b7c8/63/page-frame.html'));
            return 1000 !== data.code || !data.data.id;
        },
    },
    {
        name: '智能电视',
        env: 'ZNDS_COOKIE',
        list: process.env.ZNDS_COOKIE ? process.env.ZNDS_COOKIE.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest('https://www.znds.com/', 'post', createHeaders('PC', `Cookie@${token}`, 'Accept-Encoding@gzip, deflate, br', 'Content-Type@text/html; charset=utf-8', 'Accept@text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'));
            return !(data.indexOf('退出') > -1);
        },
    },
    {
        name: '甄稀冰淇淋',
        env: 'ZX_ICE_TOKEN',
        list: process.env.ZX_ICE_TOKEN ? process.env.ZX_ICE_TOKEN.split(/\r?\n/).map(v => v.trim()).filter(Boolean) : [],
        checkFn: async (token) => {
            const data = await sudojia.sendRequest('https://msmarket.msx.digitalyili.com/gateway/api/auth/account/user/info', 'get', createHeaders('wx_mini', `access-token@${token}`, 'Content-Type@application/json', 'referer@https://servicewechat.com/wx21fd8b5d6d4cf1ca/195/page-frame.html'));
            return !data.status || !data.data.userId;
        },
    },
];

const unsafe = new Set(['HLZJ_UNID', 'KURO_TOKEN', 'LAOBAN_OPENID', 'NFHK_COOKIE']);
const unverified = new Set(['HGF_COOKIE', 'KURO_TOKEN', 'NFHK_COOKIE']);
function validate(service, credential) {
  if (typeof credential !== 'string' || !credential.trim() || /[\r\n]/.test(credential)) throw new Error('凭据格式错误');
  if (['MOTO_TOKEN','SHUI_FEI_COOKIE'].includes(service)) {
    const pair = splitPair(credential);
    if (!pair[0] || !pair[1]) throw new Error('配套凭据不完整');
  }
  if (service === 'TEBU_JSON') {
    const value = JSON.parse(credential);
    if (!value || typeof value !== 'object' || Array.isArray(value) || !Object.keys(value).length ||
        !Object.entries(value).every(([k,v]) => /^[a-zA-Z0-9-]+$/.test(k) && typeof v === 'string' && !/[\r\n]/.test(v))) throw new Error('请求头格式错误');
  }
}
async function notify(summary) {
  if (['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  if (dry) { log('阶段 3 通知：断网预演已生成脱敏通知内容'); return '预演生成，未发送'; }
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  for (const file of files) {
    if (!fs.existsSync(file)) continue;
    let timer;
    try {
      const module = require(file);
      await Promise.race([Promise.resolve().then(() => module.sendNotify('多合一账号失效检测', summary)),
        new Promise((_,reject) => {timer = setTimeout(() => reject(new Error('timeout')),10000);})]);
      return '已发送';
    } catch { log('⚠️ 通知不可用，保留业务退出码'); return '发送失败'; }
    finally { clearTimeout(timer); }
  }
  log('⚠️ 未找到青龙通知模块，保留业务退出码');
  return '模块不可用';
}
async function main() {
  log('========== 多合一账号失效检测 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '在线检查'}`);
  let configurationError = false;
  log('阶段 1 参数清点');
  try {
    if (process.env.AUTH_CHECK_ACCOUNTS) {
      for (const account of accounts) account.list = [];
      for (const line of process.env.AUTH_CHECK_ACCOUNTS.split(/\r?\n/).filter(v => v.trim())) {
        try {
          const record = JSON.parse(line);
          if (!record || !accounts.some(a => a.env === record.service)) throw new Error('未知服务');
          for (const account of accounts.filter(a => a.env === record.service)) account.list.push(record.credential);
        } catch { configurationError = true; log('❌ 一行账号配置无效，其他有效行继续处理'); }
      }
    }
    for (const a of accounts) for (const value of a.list) if (typeof value === "string") secrets.push(value, ...splitPair(value));
    stats.accounts = accounts.reduce((n,a) => n+a.list.length,0);
    if (!stats.accounts || (!dry && !enabled)) throw new Error('配置未启用或没有账号');
  } catch { configurationError = true; log('❌ 配置错误：检查账号 JSON、服务名和 ENABLE_CHECK_TOKEN=true；至少配置一项凭据'); }
  log(`账号检查数：${stats.accounts}（贴吧同一凭据有两项检查）`);
  if (dry || enabled) for (const account of accounts) {
    for (let i=0; i<account.list.length; i++) {
      const t = Date.now(); const credential = account.list[i]; currentIdentity = '';
      let status = 'failed'; let detail = '凭据无效或响应不能证实有效';
      log(`阶段 2.${results.length+1} ${account.name} 账号[${i+1}]：开始凭据检查`);
      try {
        validate(account.env, credential);
        if (dry) { status = 'dry-run'; detail = 'DRY_RUN_OK：参数校验通过；未调用业务或通知网络'; }
        else if (unverified.has(account.env)) { status='skipped'; detail='缺少正向成功响应证据，未执行且未验证'; }
        else if (unsafe.has(account.env) && !allowMutations) { status='skipped'; detail='未允许有副作用的探测，未执行且未验证'; }
        else if (account.name === '贴吧任务签到' && !credential.includes('CUID=')) { status='skipped'; detail='缺少 CUID，未执行且未验证'; }
        else if (!await account.checkFn(credential)) {status='success'; detail='有效！✅ 已验证响应契约';}
      } catch { detail='请求、配置或响应检查失败；未输出敏感异常'; }
      stats.tasks++;
      if (status==='success' || status==='dry-run') stats.success++; else { stats.failed++; if(status==='skipped') stats.skipped++; }
      const result = {service:account.env, task:account.name, account:i+1, status, durationMs:Date.now()-t};
      results.push(result);
      log(`${currentIdentity ? '账号身份：'+currentIdentity+'；' : ''}${detail}；耗时 ${result.durationMs}ms`);
      log(`账号统计：总任务 1，成功 ${['success','dry-run'].includes(status)?1:0}，已完成 0，跳过 ${status==='skipped'?1:0}，失败 ${status==='failed'?1:0}`);
    }
  }
  const failed = configurationError || stats.failed > 0;
  process.exitCode = failed ? 1 : 0;
  const status = configurationError ? 'configuration-error' : dry ? (failed?'failure':'dry-run') : failed ? (stats.success?'partial-failure':'failure') : 'success';
  const summary = `账号检查总数 ${stats.accounts}，成功 ${stats.success}，失败或未验证 ${stats.failed}，跳过 ${stats.skipped}；状态 ${status}。`;
  const notification = await notify(summary);
  log('----------------------------------------');
  log(`最终任务统计：${summary} 子任务 ${stats.tasks}；耗时 ${Date.now()-started}ms；通知 ${notification}`);
  log(`完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({status, mode:dry?'dry-run':'live', ...stats, configurationError, notification, durationMs:Date.now()-started, results}));
}
main().catch(() => { process.exitCode=1; log('❌ 内部执行失败'); });
