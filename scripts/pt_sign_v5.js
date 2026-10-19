// name: PT 多站签到（SafeLine 兼容维护版）
// cron: 46 2 * * *
// 上游未声明 cron；本维护版建议每天 08:00 运行。
// 来源：Flyingpen/PT-sign，PT-sign-V5.js，提交 5c6cf9d38020c327f9a30c3977eb7765e4d2c5c2。
// 许可：MIT。上游原说明保留于下方；维护版参数与安全行为以契约为准。
/*
MIT License
Copyright: 原作者 Flyingpen/PT-sign 及其贡献者（保留原作者归属）
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
*/
/**
 * PT 签到 v5（雷池 SafeLine WAF 兼容版）
 * 相比 v4 的关键修复：
 *   1. 修复 getZhReason() 中全角句号「。」导致的语法错误（v4 根本无法运行）
 *   2. 新增 Cookie 罐：保存并回传服务器下发的所有 Set-Cookie（含雷池 sl-session 等）
 *   3. 新增雷池 SafeLine 自动挑战：检测 468/挑战页 → issue → 本地 PoW 计算 → verify → 携带 jwt 重放
 *   4. 移除伪造的 x-forwarded-for / x-real-ip（对 WAF 是自曝 bot 特征）
 *   5. 统一使用完整、自洽的 Chrome 请求头（不再随机换 UA、不再缺 accept 等）
 *   6. POST 的 content-type 固定为 application/x-www-form-urlencoded（v4 有 50% 概率随机成 json 导致必败）
 *   7. axios 关闭自动重定向，改用手动跟随：302 到 login.php/takelogin.php 才判定 Cookie 失效
 *   8. formhash 正则放宽（8~32 位字母数字，兼容不同站点）
 *   9. POST 请求补齐 origin / referer / sec-fetch-* 头
 *
 * 环境变量：
 *   PT_SITE_<SITE>_CK     必须，对应站点 cookie（如 PT_SITE_HDKYL_CK）
 *   PT_SITE_<SITE>_URL    可选，覆盖站点签到页地址
 *   PT_WEBHOOK_URL        必须，推送地址
 *   PT_WEBHOOK_TYPE       feishu | bark | sct | ding | wx | custom，默认 custom
 *   PT_PROXY              可选，如 http://127.0.0.1:7890
 *   PT_RETRY              重试次数，默认 3
 *   PT_TIMEOUT            请求超时毫秒，默认 20000
 *   PT_SAFELINE           是否启用雷池自动挑战，默认 1（设为 0 关闭）
 *   PT_EXTRA_HEADERS      可选，额外 header，格式：key1:value1|key2:value2
 *   PT_DEBUG              可选，开启调试模式，输出 HTML 内容
 */


'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["ff443f9fbbdbade5", "scripts/pt_sign_v5.js", "pt_sign_v5.js", "pt_sign_v5"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
// 每个站点的 Cookie 改为一行一个账号，不按 &、@ 等符号切分。
// PT_SITES 默认 hdkyl,carpt,afun；只运行部分站点时显式设置此变量。
// PT_DRY_RUN=1 时完全断网，通知仅模拟；PT_DEBUG 不再输出 HTML 或凭据。
// Webhook 现在可选；所有实际运行均尝试青龙通知。代理和额外头不写入日志。
const fs = require('node:fs');
const path = require('node:path');
const started = Date.now();
const DRY = /^(1|true|yes|on)$/i.test(process.env.PT_DRY_RUN || '');
const DEBUG = /^(1|true|yes|on)$/i.test(process.env.PT_DEBUG || '');
const SAFELINE = process.env.PT_SAFELINE !== '0';
const BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const sites = {
  hdkyl: { url: 'https://www.hdkyl.in/attendance.php', cookie: process.env.PT_SITE_HDKYL_CK, override: process.env.PT_SITE_HDKYL_URL, currency: '魔力值' },
  carpt: { url: 'https://carpt.net/attendance.php', cookie: process.env.PT_SITE_CARPT_CK, override: process.env.PT_SITE_CARPT_URL, currency: '魔力值' },
  afun: { url: 'https://www.ptlover.cc/attendance.php', cookie: process.env.PT_SITE_AFUN_CK, override: process.env.PT_SITE_AFUN_URL, currency: '喵饼' }
};
const secretValues = [];
for (const site of Object.values(sites)) {
  for (const line of (site.cookie || '').split(/\r?\n/)) {
    if (line.trim()) secretValues.push(line.trim());
    for (const pair of line.split(';')) {
      const i = pair.indexOf('=');
      if (i >= 0 && pair.slice(i + 1).trim()) secretValues.push(pair.slice(i + 1).trim());
    }
  }
}
for (const name of ['PT_WEBHOOK_URL', 'PT_PROXY', 'PT_EXTRA_HEADERS']) {
  if (process.env[name]) secretValues.push(process.env[name]);
}
function clean(value) {
  let text = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const secret of secretValues.sort((a,b) => b.length-a.length)) text = text.split(secret).join('[已脱敏]');
  return text.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function clock() { return new Date().toLocaleTimeString('zh-CN', { hour12: false }); }
function log(message) { console.log(`[${clock()}] ${clean(message)}`); }
function debug(message) { if (DEBUG) log(`调试：${message}`); }
function fail(message, noRetry = false) { const e = new Error(message); e.safe = true; e.noRetry = noRetry; throw e; }
function reason(e) { return e.safe ? e.message : '请求或依赖异常（详细内容已隐藏），请检查网络、依赖和配置'; }
function number(name, fallback, min, max) {
  const value = process.env[name];
  if (value === undefined || value === '') return fallback;
  if (!/^\d+$/.test(value) || Number(value) < min || Number(value) > max) fail(`${name} 配置不合法`, true);
  return Number(value);
}
function secureUrl(value, label) {
  let u; try { u = new URL(value); } catch { fail(`${label} 地址格式不合法`, true); }
  if (u.protocol !== 'https:' || u.username || u.password) fail(`${label} 必须是无内嵌凭据的 HTTPS 地址`, true);
  return u.href;
}
function getExtraHeaders() {
  const headers = {};
  for (const pair of (process.env.PT_EXTRA_HEADERS || '').split('|').filter(Boolean)) {
    const idx = pair.indexOf(':');
    if (idx <= 0) fail('PT_EXTRA_HEADERS 格式不合法', true);
    const name = pair.slice(0, idx).trim().toLowerCase();
    const value = pair.slice(idx + 1).trim();
    if (!/^[a-z0-9-]+$/.test(name) || /[\r\n]/.test(value)) fail('额外请求头格式不合法', true);
    if (/^(cookie|authorization|proxy-authorization|host|content-length|origin|referer|content-type|x-forwarded-for|x-real-ip)$/.test(name)) fail('额外请求头包含受保护字段', true);
    headers[name] = value;
  }
  return headers;
}
function navHeaders(referer) {
  const headers = {
    'user-agent': BROWSER_UA,
    accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document', 'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin', 'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1', ...getExtraHeaders()
  };
  if (referer) headers.referer = referer;
  return headers;
}
let http, Jar, TIMEOUT, RETRY;
function initializeHttp() {
  const axios = require('axios');
  Jar = require('tough-cookie').CookieJar;
  const config = { timeout: TIMEOUT, maxRedirects: 0, validateStatus: () => true,
    maxContentLength: 2 * 1024 * 1024, maxBodyLength: 2 * 1024 * 1024,
    responseType: 'text', proxy: false };
  if (process.env.PT_PROXY) {
    const proxy = new URL(process.env.PT_PROXY);
    if (!['http:', 'https:'].includes(proxy.protocol)) fail('PT_PROXY 仅支持 HTTP 或 HTTPS 代理', true);
    const { HttpsProxyAgent } = require('https-proxy-agent');
    config.httpsAgent = new HttpsProxyAgent(proxy);
  }
  http = axios.create(config);
}
class CookieJar {
  constructor(url, cookie) {
    this.url = url; this.jar = new Jar();
    for (const pair of cookie.split(';')) {
      const i = pair.indexOf('=');
      if (i > 0) this.jar.setCookieSync(`${pair.trim()}; Path=/; Secure`, url);
    }
  }
  absorb(resp, url) {
    for (const value of resp.headers['set-cookie'] || []) {
      try { this.jar.setCookieSync(value, url); } catch { debug('忽略不合法的服务器 Cookie'); }
    }
  }
  set(name, value) { this.jar.setCookieSync(`${name}=${value}; Path=/; Secure`, this.url); }
  header(url) { return this.jar.getCookieStringSync(url); }
}
const redirects = [301, 302, 303, 307, 308];
function redirectTarget(resp, url, jar) {
  const loc = resp.headers.location;
  if (!loc) fail('重定向缺少目标地址');
  const next = secureUrl(new URL(loc, url).href, '重定向');
  if (/\/(login|takelogin|takeconfirm)\.php/i.test(new URL(next).pathname)) fail('Cookie 失效：重定向至登录页', true);
  if (new URL(next).origin !== new URL(jar.url).origin) fail('拒绝跨域重定向以保护凭据', true);
  return next;
}
async function siteRequest(url, jar, method = 'GET', body, depth = 0) {
  if (depth > 5) fail('重定向次数过多');
  if (new URL(url).origin !== new URL(jar.url).origin) fail('拒绝向其他站点发送凭据', true);
  const headers = { ...navHeaders(jar.url), cookie: jar.header(url) };
  if (method === 'POST') Object.assign(headers, { 'content-type': 'application/x-www-form-urlencoded', origin: new URL(url).origin });
  let resp;
  try { resp = await http.request({ url, method, headers, data: body }); }
  catch { fail(method === 'POST' ? '签到提交未收到有效响应，状态未知；请下次运行先查询签到状态' : '获取页面失败或超时', method === 'POST'); }
  jar.absorb(resp, url);
  debug(`${method} HTTP ${resp.status}，响应长度 ${String(resp.data).length}`);
  if (redirects.includes(resp.status)) {
    const next = redirectTarget(resp, url, jar);
    // 307/308 必须保留方法，不能擅自转成 GET 或重复签到。
    if (method === 'POST' && [307, 308].includes(resp.status)) fail('签到提交要求重放 POST，已停止以避免重复副作用', true);
    return siteRequest(next, jar, 'GET', undefined, depth + 1);
  }
  return resp;
}
function safeJson(s) { try { return typeof s === 'string' ? JSON.parse(s) : s; } catch { return null; } }
function safelineCalc(e) {
  let t = 1;
  const n = e.reduce((a, b) => a + b, 0);
  let r = (6 + e.length + n) % 6 + 6;
  for (let o = r; o--;) t *= 6;
  if (t < 6666) t *= e.length;
  if (t > 0x3f940aa) t = Math.floor(t / e.length);
  for (let o = 0; o < e.length; o++) {
    t += Math.pow(e[o], 3);
    t ^= o;
    t ^= e[o] + o;
  }
  const out = [];
  for (; t > 0;) { out.unshift(63 & t); t >>= 6; }
  return out;
}

function isSafeLineChallenge(html, status) {
  if (status === 468) return true;
  if (typeof html !== 'string') return false;
  return html.includes('SafeLineChallenge(') || html.includes('/.safeline/challenge') || html.includes('id="sl-box"');
}

function parseAttendanceDetails(html, currencyName = '魔力值') {
  debug('==================== 开始解析签到详情 ====================');
  let continuousDays = null;
  let reward = null;
  let todayReward = null;

  const navMatch = html.match(/\[签到已得(\d+(?:\.\d+)?)[,，]\s*补签卡[：:]\s*(\d+)\]/i);
  if (navMatch) {
    reward = `累计${navMatch[1]}${currencyName}`;
    debug(`✅ 从导航栏匹配到签到信息: 累计${navMatch[1]}${currencyName} (补签卡: ${navMatch[2]})`);
  }

  const patterns = {
    continuous: [
      /连续签到[：:\s]*(\d+)\s*天/i,
      /已连续签到[：:\s]*(\d+)\s*天/i,
      /连续\s*(\d+)\s*天签到/i,
      /(\d+)\s*天连续签到/i,
      /continuous[:\s]*(\d+)\s*day/i,
      /<td[^>]*>连续签到天数<\/td>\s*<td[^>]*>(\d+)/i,
      /<td[^>]*>连续[：:]*<\/td>\s*<td[^>]*>(\d+)/i,
      /连续签到.*?(\d+).*?天/is,
    ],
    todayReward: [
      /今[日天].*?获得[：:\s]*(\d+\.?\d*)\s*(魔力值|积分|喵饼|GB|MB)/i,
      /本次签到.*?[：:\s]*(\d+\.?\d*)\s*(魔力值|积分|喵饼|GB|MB)/i,
      /签到成功.*?[+]\s*(\d+\.?\d*)\s*(魔力值|积分|喵饼)/i,
      /<td[^>]*>今日[签奖].*?<\/td>\s*<td[^>]*>(\d+\.?\d*)\s*(魔力值|积分|喵饼)/i,
    ]
  };

  for (const pattern of patterns.continuous) {
    const match = html.match(pattern);
    if (match && match[1] && parseInt(match[1]) > 0) {
      continuousDays = match[1];
      debug(`✅ 匹配到连续签到天数: ${continuousDays}天`);
      break;
    }
  }

  for (const pattern of patterns.todayReward) {
    const match = html.match(pattern);
    if (match && match[1]) {
      todayReward = `${match[1]}${match[2] || currencyName}`;
      debug(`✅ 匹配到今日奖励: ${todayReward}`);
      break;
    }
  }

  if (!continuousDays) {
    const tableRows = html.match(/<tr[^>]*>[\s\S]*?<\/tr>/gi) || [];
    for (const row of tableRows) {
      const text = row.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
      if (/连续/i.test(text)) {
        const numMatch = text.match(/(\d+)/);
        if (numMatch && parseInt(numMatch[1]) > 0 && parseInt(numMatch[1]) < 10000) {
          continuousDays = numMatch[1];
          debug(`✅ 从表格行提取到连续天数: ${continuousDays}天`);
          break;
        }
      }
    }
  }

  if (!continuousDays) debug('⚠️ 未匹配到连续签到天数');
  if (!todayReward && !reward) debug('⚠️ 未匹配到奖励信息');

  debug('==================== 签到详情解析结束 ====================');
  return { continuousDays, reward: todayReward || reward };
}


async function solveSafeLine(siteUrl, jar, tag, html) {
  const token = typeof html === 'string' && html.match(/SafeLineChallenge\(\s*["']([^"']+)["']/);
  if (!token) return false;
  const headers = { 'user-agent': BROWSER_UA, accept: '*/*', 'content-type': 'application/json', origin: new URL(siteUrl).origin, referer: siteUrl };
  // 专用头，无账号 Cookie、额外头或认证字段；不跟随重定向。
  const issue = await http.post('https://challenge.rivers.chaitin.cn/challenge/v2/api/issue', { client_id: token[1], level: 1 }, { headers });
  const data = safeJson(issue.data);
  if (issue.status !== 200 || data?.code !== 200 || !data.data?.issue_id) return false;
  const puzzle = data.data.data;
  if (!Array.isArray(puzzle) || !puzzle.length || puzzle.length > 1024 || puzzle.some(n => !Number.isSafeInteger(n) || n < 0 || n > 1000000)) return false;
  const client = { userAgent: BROWSER_UA, platform: 'Win32', language: 'zh-CN,zh', vendor: 'Google Inc.', screen: [1920,1080], visitorId: '', score: 0, target: [] };
  const verify = await http.post('https://challenge.rivers.chaitin.cn/challenge/v2/api/verify', { issue_id: data.data.issue_id, result: safelineCalc(puzzle), serials: [], client }, { headers });
  const checked = safeJson(verify.data);
  if (verify.status !== 200 || checked?.code !== 200 || checked.data?.verified !== true || typeof checked.data.jwt !== 'string' || !checked.data.jwt) return false;
  jar.set('sl-challenge-jwt', checked.data.jwt); jar.set('sl-challenge-server', 'cloud');
  return true;
}
function checkedHtml(resp) {
  if (isSafeLineChallenge(resp.data, resp.status)) fail('SafeLine 挑战未通过，请在浏览器访问站点并更新完整 Cookie', true);
  if (resp.status < 200 || resp.status >= 300) fail(`站点 HTTP ${resp.status}`);
  if (typeof resp.data !== 'string') fail('站点响应不是有效页面');
  if (/name=["']loginform["']|请先登录|您尚未登录/i.test(resp.data) && !/formhash/i.test(resp.data)) fail('Cookie 失效：页面显示未登录', true);
  return resp.data;
}
function already(html) { return /今日已签到|您今天已经签到|今天已经签到|already signed(?: in)?/i.test(html); }
function signed(html) { return /签到成功|打卡成功|att成功|attendance (?:successful|success)/i.test(html); }
function rejected(html) { return /非法提交|formhash.{0,20}错误|签到失败|密码错误|不要重复提交/i.test(html); }
function identity(html) {
  const m = html.match(/<a\b[^>]*href=["'][^"']*userdetails\.php\?id=(\d+)[^"']*["'][^>]*>([\s\S]*?)<\/a>/i);
  if (!m) return '';
  const text = m[2].replace(/<[^>]+>/g, '').replace(/&#(\d+);/g, (_,n) => { const c = Number(n); return c <= 0x10ffff ? String.fromCodePoint(c) : ''; }).replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ').trim();
  return text ? `用户名：${clean(text)}，公开 UID：${m[1]}` : `公开 UID：${m[1]}`;
}
async function stage(stats, n, title, action) {
  const began = Date.now(); log(`阶段 ${n}：${title}`);
  try {
    const result = await action(); stats.success++;
    log(`✅ 阶段 ${n} 完成，耗时 ${Date.now()-began} 毫秒`); return result;
  } catch (e) {
    stats.failed++; log(`❌ 阶段 ${n}：${reason(e)}，耗时 ${Date.now()-began} 毫秒`); throw e;
  }
}
async function sign(account) {
  const begin = Date.now(), stats = { success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  log(`--- 账号 ${account.index}（${account.site}）开始 ---`);
  let result;
  try {
    const url = await stage(stats, 1, '检查账号和参数', async () => {
      if (!account.cookie || !account.cookie.split(';').some(p => /^[^=;\s]+\s*=.+$/.test(p.trim()))) fail('未配置有效的站点 Cookie', true);
      if (/[\r\n\x00-\x1f\x7f]/.test(account.cookie)) fail('Cookie 含非法控制字符', true);
      return secureUrl(sites[account.site].override || sites[account.site].url, '签到页');
    });
    if (DRY) {
      await stage(stats, 2, '断网预演请求、挑战及奖励解析', async () => {
        const fixture = '<input name="formhash" value="fixture123">签到成功 连续签到：3天 今日获得：10魔力值';
        if (!signed(fixture) || parseAttendanceDetails(fixture).continuousDays !== '3' || already('[签到已得10, 补签卡:0]') || signed('generic success')) fail('本地业务判定自检失败');
        if (!Array.isArray(safelineCalc([1,2,3]))) fail('本地挑战计算自检失败');
        log('DRY_RUN_OK：不请求站点、不提交签到、不调用推送或通知网络');
      });
      for (const [n,title] of [[3,'SafeLine 网络挑战'],[4,'签到提交'],[5,'奖励网络查询']]) log(`⏭️ 阶段 ${n}：${title}，断网预演跳过，耗时 0 毫秒`);
      stats.skipped += 3; result = { ok: true, reason: '断网预演通过', dryRun: true };
    } else {
      for (let attempt = 1; attempt <= RETRY; attempt++) {
        try {
          const jar = new CookieJar(url, account.cookie);
          let resp = await stage(stats, 2, `获取签到页（第 ${attempt} 次）`, () => siteRequest(url, jar));
          if (isSafeLineChallenge(resp.data, resp.status)) {
            await stage(stats, 3, '处理 SafeLine 挑战', async () => {
              if (!SAFELINE || !await solveSafeLine(url, jar, account.site, resp.data)) fail('SafeLine 挑战未通过，请更新浏览器完整 Cookie', true);
              resp = await siteRequest(url, jar);
            });
          } else { stats.skipped++; log('⏭️ 阶段 3：未检测到 SafeLine 挑战'); }
          let html = checkedHtml(resp);
          const who = identity(html); if (who) log(who);
          if (already(html)) {
            stats.alreadyComplete++; stats.skipped++; log('☑️ 阶段 4：今日已签到，跳过提交');
            result = { ok: true, reason: '今日已签到', ...parseAttendanceDetails(html, sites[account.site].currency) }; break;
          }
          html = await stage(stats, 4, '提交签到并核实业务状态', async () => {
            const m = html.match(/name=["']formhash["'][^>]*value=["']([a-zA-Z0-9]{6,32})["']/i)
              || html.match(/value=["']([a-zA-Z0-9]{6,32})["'][^>]*name=["']formhash["']/i)
              || html.match(/formhash=([a-zA-Z0-9]{6,32})/i);
            if (!m) fail('页面未找到 formhash，需检查页面结构');
            const post = checkedHtml(await siteRequest(url, jar, 'POST', new URLSearchParams({ action: 'attendance', formhash: m[1] }).toString()));
            if (rejected(post)) fail('签到接口明确拒绝提交', true);
            if (signed(post) || already(post)) return post;
            const refresh = checkedHtml(await siteRequest(url, jar));
            if (rejected(refresh) || !already(refresh)) fail('未得到明确签到成功证据，已停止重复提交', true);
            return refresh;
          });
          let detail = parseAttendanceDetails(html, sites[account.site].currency);
          if (!detail.continuousDays && !detail.reward) {
            try {
              detail = await stage(stats, 5, '查询连续签到和奖励', async () => parseAttendanceDetails(checkedHtml(await siteRequest(url, jar)), sites[account.site].currency));
            } catch { log('⚠️ 奖励详情获取失败；已确认的签到结果保留'); }
          } else { stats.skipped++; log('⏭️ 阶段 5：签到响应已包含奖励信息'); }
          result = { ok: true, reason: '签到成功', ...detail }; break;
        } catch (e) {
          log(`⚠️ 第 ${attempt} 次尝试：${reason(e)}`);
          if (e.noRetry || attempt === RETRY) throw e;
          await new Promise(r => setTimeout(r, 3000));
        }
      }
    }
  } catch (e) { result = { ok: false, reason: reason(e) }; }
  result = { site: account.site, account: account.index, ...result, statistics: { total: stats.success+stats.alreadyComplete+stats.skipped+stats.failed, ...stats, durationMs: Date.now()-begin } };
  log(`${result.ok ? '✅' : '❌'} 账号 ${account.index}：${result.reason}；连续 ${result.continuousDays || '未获取'} 天；奖励 ${result.reward || '未获取'}`);
  log(`账号统计：总任务 ${result.statistics.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${result.statistics.durationMs} 毫秒`);
  return result;
}
async function webhook(title, body) {
  if (!process.env.PT_WEBHOOK_URL) return '未配置';
  const url = secureUrl(process.env.PT_WEBHOOK_URL, 'Webhook');
  const type = (process.env.PT_WEBHOOK_TYPE || 'custom').toLowerCase();
  let payload;
  switch (type) {
    case 'feishu': payload = { msg_type: 'text', content: { text: `${title}\n${body}` } }; break;
    case 'bark': payload = { title, body }; break;
    case 'sct': payload = { title, desp: body }; break;
    case 'ding': case 'wx': payload = { msgtype: 'text', text: { content: `${title}\n${body}` } }; break;
    case 'custom': payload = { title, content: body }; break;
    default: fail('PT_WEBHOOK_TYPE 不支持', true);
  }
  const resp = await http.post(url, payload, { timeout: 8000, headers: { 'content-type': 'application/json' } });
  if (resp.status < 200 || resp.status >= 300) fail('Webhook HTTP 失败', true);
  const data = safeJson(resp.data);
  if (data && ((data.code != null && ![0,200].includes(data.code)) || (data.errcode != null && data.errcode !== 0))) fail('Webhook 返回业务失败', true);
  return '已发送';
}
async function notification(title, body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (DRY) return '断网预演，仅模拟通知';
  const paths = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js', path.join(__dirname, 'sendNotify.js')].filter(Boolean);
  for (const file of [...new Set(paths)]) {
    if (!fs.existsSync(file)) continue;
    try {
      // 通知器第三方输出也不得泄漏响应或配置，隔离子进程并限制耗时。
      const { spawn } = require('node:child_process');
      return await new Promise(resolve => {
        const child = spawn(process.execPath, ['-e', 'const m=require(process.argv[1]); Promise.resolve(m.sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1));', file, title, body], { stdio: 'ignore' });
        const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('失败或超时'); }, 15000);
        child.once('error', () => { clearTimeout(timer); resolve('失败'); });
        child.once('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '失败'); });
      });
    } catch { return '失败'; }
  }
  return '未发现青龙 sendNotify.js';
}
async function main() {
  log('========== PT 多站签到 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${DRY ? '断网预演' : '实际签到'}`);
  let accounts = [], results = [], configError = '';
  try {
    RETRY = number('PT_RETRY', 3, 1, 10); TIMEOUT = number('PT_TIMEOUT', 20000, 1000, 120000);
    getExtraHeaders();
    const selected = [...new Set((process.env.PT_SITES || 'hdkyl,carpt,afun').split(',').map(s => s.trim().toLowerCase()))];
    if (!selected.length || selected.some(s => !Object.hasOwn(sites,s))) fail('PT_SITES 只能选择 hdkyl、carpt、afun', true);
    for (const key of selected) {
      const lines = (sites[key].cookie || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
      if (!lines.length) {
        configError += `${configError ? '；' : ''}请配置 PT_SITE_${key.toUpperCase()}_CK；不运行该站请调整 PT_SITES`;
        continue;
      }
      for (const cookie of lines) accounts.push({ site: key, cookie, index: accounts.length+1 });
    }
    log(`账号总数：${accounts.length}；代理：${process.env.PT_PROXY ? '已配置' : '未配置'}；SafeLine：${SAFELINE ? '启用' : '关闭'}`);
    if (configError) log(`❌ 站点配置错误：${configError}；其余已配置账号继续执行`);
    if (!DRY && accounts.length) initializeHttp();
    for (const account of accounts) results.push(await sign(account));
  } catch (e) { configError = reason(e); log(`❌ 配置或运行初始化错误：${configError}`); }
  const success = results.filter(r => r.ok).length;
  const failed = accounts.length-success;
  const status = configError ? 'configuration-error' : failed ? success ? 'partial-failure' : 'failure' : DRY ? 'dry-run' : 'success';
  const exitCode = configError || failed ? 1 : 0;
  const body = clean(`账号总数：${accounts.length}，成功：${success}，失败：${failed}；状态：${status}\n${configError}\n` + results.map(r => `${r.site} 账号${r.account}：${r.reason}${r.continuousDays ? `，连续${r.continuousDays}天` : ''}${r.reward ? `，奖励${r.reward}` : ''}`).join('\n'));
  let hook = DRY ? '断网预演，仅模拟推送' : '未配置';
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) hook = '已关闭';
  else if (!DRY && http) { try { hook = await webhook('PT 多站签到', body); } catch { hook = '失败（不影响业务退出码）'; } }
  const notify = await notification('PT 多站签到', body);
  const totals = results.reduce((a,r) => { for (const k of ['total','success','alreadyComplete','skipped','failed']) a[k] += r.statistics[k]; return a; }, { total:0,success:0,alreadyComplete:0,skipped:0,failed:0 });
  log('----------------------------------------');
  log(`账号统计：总数 ${accounts.length}，成功 ${success}，失败 ${failed}；子任务统计：${JSON.stringify(totals)}`);
  log(`Webhook：${hook}；青龙通知：${notify}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now()-started} 毫秒；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task:'PT 多站签到', status, mode:DRY ? 'dry-run':'live', accounts:accounts.length, success, failed, configurationError:!!configError, statistics:totals, results, notification:notify, webhook:hook, durationMs:Date.now()-started, exitCode }));
  process.exitCode = exitCode;
}
main().catch(() => { process.exitCode = 1; });
