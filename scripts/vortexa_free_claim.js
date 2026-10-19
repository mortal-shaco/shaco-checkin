// name: Vortexa 免费主机检查与领取
// cron: 1,11,21,31,41,51 * * * *
/*
name: Vortexa 免费主机检查与领取
cron: 1,11,21,31,41,51 * * * *
Vortexa Free Hosting 领取脚本
原作者及来源：lizhixu/ql-script-hub，vortexa_free_claim.js
来源提交：ac591a320092dcaeaf236b7c2b6acfd28981e589
SPDX-License-Identifier: MIT

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

参数：VORTEXA_ACCOUNTS 每个非空行一个 JSON 对象；账号配套字段在同一对象内。
支持 account/password、token、cookie 或 refresh，以及 fingerprint/userAgent。
在官网注册账号；登录后通过浏览器开发者工具查看 /auth/login 请求体及响应、
受保护请求 Authorization、Cookie、x-fingerprint；不得把这些值公开。
旧 VORTEXA_LOGIN/ACCOUNT_PASSWORD 支持每行 账号@密码（用户名在第一个 @ 分割，邮箱在完整邮箱后的 @ 分割；
推荐 JSON 避免歧义）；旧 TOKEN/ACCESS_TOKEN、COOKIE、REFRESH、
ACCOUNT/EMAIL/USERNAME + PASSWORD 仍支持，每行一个账号，配套变量按行对齐。
默认只检查；VORTEXA_CLAIM=1 才领取。VORTEXA_LIST_PRODUCTS=1 只列产品。
显式 VORTEXA_LOOP=1 启用有限扫描，VORTEXA_MAX_SCANS 默认 3。
VORTEXA_DRY_RUN=1 完全断网；通知辅助脚本也在断网子进程中尝试。
更多可选参数、获取说明和安全边界见同目录 contract.json。
*/
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["7f027fefd96fedf2", "scripts/vortexa_free_claim.js", "vortexa_free_claim.js", "vortexa_free_claim"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const zlib = require('zlib');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const env = process.env;
const trueValue = value => /^(1|true|yes|on)$/i.test(String(value || '').trim());
const DRY = trueValue(env.VORTEXA_DRY_RUN);
const LIST = trueValue(env.VORTEXA_LIST_PRODUCTS);
const CLAIM = trueValue(env.VORTEXA_CLAIM);
const LOOP = trueValue(env.VORTEXA_LOOP);
const TITLE = 'Vortexa 免费主机检查与领取';
const stamp = () => new Date().toTimeString().slice(0, 8);
const log = message => console.log(`[${stamp()}] ${message}`);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function integer(name, fallback, min, max) {
  if (env[name] === undefined || env[name] === '') return fallback;
  if (!/^\d+$/.test(env[name])) throw new Error(`配置错误：${name} 必须是整数`);
  const n = Number(env[name]);
  if (!Number.isSafeInteger(n) || n < min || n > max) throw new Error(`配置错误：${name} 超出允许范围`);
  return n;
}
function secureUrl(value, label) {
  let u;
  try { u = new URL(value); } catch (_) { throw new Error(`配置错误：${label} URL 无效`); }
  if (u.protocol !== 'https:' || u.username || u.password || u.search || u.hash) {
    throw new Error(`配置错误：${label} 仅允许无凭据、查询串及片段的 HTTPS URL`);
  }
  return u.href.replace(/\/+$/, '');
}
function config() {
  const min = integer('VORTEXA_INTERVAL_MIN_SECONDS', integer('VORTEXA_INTERVAL_SECONDS', 30, 1, 300), 1, 300);
  const max = integer('VORTEXA_INTERVAL_MAX_SECONDS', Math.max(min, 60), min, 300);
  const field = env.VORTEXA_LOGIN_FIELD || '';
  if (field && !/^[a-zA-Z][a-zA-Z0-9_]*$/.test(field)) throw new Error('配置错误：VORTEXA_LOGIN_FIELD 无效');
  if (field === 'password') throw new Error('配置错误：登录字段不能覆盖 password');
  return {
    base: secureUrl(env.VORTEXA_API_BASE || 'https://api.vortexa.cloud/api', 'VORTEXA_API_BASE'),
    origin: secureUrl(env.VORTEXA_ORIGIN || 'https://www.vortexa.cloud', 'VORTEXA_ORIGIN'),
    referer: secureUrl(env.VORTEXA_REFERER || 'https://www.vortexa.cloud/free-hosting', 'VORTEXA_REFERER'),
    timeout: integer('VORTEXA_TIMEOUT_MS', 30000, 1000, 120000),
    delay: integer('VORTEXA_CONFIRM_DELAY_SECONDS', 5, 0, 120),
    scans: LOOP ? integer('VORTEXA_MAX_SCANS', 3, 1, 30) : 1, min, max, field
  };
}
const lines = value => String(value || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean);
function accounts() {
  if (env.VORTEXA_ACCOUNTS !== undefined) {
    return lines(env.VORTEXA_ACCOUNTS).map(line => {
      try {
        const a = JSON.parse(line);
        if (!a || Array.isArray(a) || typeof a !== 'object') throw new Error();
        return a;
      } catch (_) { return { invalid: true }; }
    });
  }
  const fields = {
    pair: lines(env.VORTEXA_LOGIN || env.VORTEXA_ACCOUNT_PASSWORD),
    account: lines(env.VORTEXA_ACCOUNT || env.VORTEXA_EMAIL || env.VORTEXA_USERNAME),
    password: lines(env.VORTEXA_PASSWORD), token: lines(env.VORTEXA_TOKEN || env.VORTEXA_ACCESS_TOKEN),
    cookie: lines(env.VORTEXA_COOKIE), refresh: lines(env.VORTEXA_REFRESH)
  };
  const count = Math.max(0, ...Object.values(fields).map(v => v.length));
  if (Object.values(fields).some(v => v.length && v.length !== count)) {
    throw new Error('配置错误：旧凭据变量非空行数必须一致；建议改用 VORTEXA_ACCOUNTS');
  }
  return Array.from({length: count}, (_, i) => {
    const a = Object.fromEntries(Object.entries(fields).map(([key, values]) => [key, values[i] || '']));
    if (a.pair) {
      const emailPrefix = a.pair.match(/^[^@\s]+@[^@\s]+\.[^@\s]+@/);
      const split = emailPrefix ? emailPrefix[0].length - 1 : a.pair.indexOf('@');
      if (split <= 0 || split === a.pair.length - 1) a.invalid = true;
      else { a.account = a.pair.slice(0, split); a.password = a.pair.slice(split + 1); }
    }
    delete a.pair;
    return a;
  });
}
function checkedAccount(a) {
  if (a.invalid) throw new Error('账号配置错误：JSON 或旧登录格式无效');
  for (const key of ['account', 'password', 'token', 'refresh', 'cookie', 'fingerprint', 'userAgent']) {
    if (a[key] !== undefined && (typeof a[key] !== 'string' || /[\r\n]/.test(a[key]))) {
      throw new Error('账号配置错误：凭据字段必须是单行文本');
    }
  }
  if (!(a.token || a.refresh || a.cookie || (a.account && a.password))) {
    throw new Error('账号配置错误：需要 Token、刷新 Cookie 或完整账号密码');
  }
  return {...a, token: a.token || '', cookie: a.cookie || (a.refresh ? `openbot_refresh=${a.refresh}` : ''),
    fingerprint: a.fingerprint || env.VORTEXA_FINGERPRINT || crypto.randomBytes(16).toString('hex'),
    userAgent: a.userAgent || env.VORTEXA_USER_AGENT || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'};
}
function business(data) {
  if (data === null || typeof data !== 'object') throw new Error('接口业务失败：响应结构无效');
  if (data.error || data.success === false || data.message === 'Request failed') throw new Error('接口业务失败：服务拒绝请求');
  // 源码未提供业务 code 契约：不猜测任意 code 是成功；最终由所需字段核验。
  return data;
}
function owned(data) {
  return data.has_free_server === true || Boolean(data.service && typeof data.service === 'object' &&
    (data.service.id || data.service.name));
}
function validStatus(data) {
  if (!owned(data) && typeof data.has_free_server !== 'boolean' && typeof data.can_get_free_server !== 'boolean') {
    throw new Error('状态核验失败：缺少已知免费主机状态字段');
  }
}
function numeric(value) {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : null;
}
function stockInfo(data) {
  const s = data.free_stock || data;
  const left = numeric(s.available ?? s.remain ?? s.left);
  const used = numeric(s.used), limit = numeric(s.global_limit ?? s.limit);
  if (left === null && !(used !== null && limit !== null && limit > 0) && typeof s.is_full !== 'boolean') {
    throw new Error('库存核验失败：缺少已知库存字段');
  }
  const full = s.is_full === true || (left !== null && left <= 0) || (limit > 0 && used !== null && used >= limit);
  // 领取前须有明确可用库存证据。
  const available = !full && (left > 0 || (limit > 0 && used !== null && used < limit) || s.is_full === false);
  return {full, available, text: `已使用 ${used ?? '未知'} / 限制 ${limit ?? '未知'} / 剩余 ${left ?? '未知'}`};
}
const freePlan = p => Array.isArray(p.plans) ? p.plans.find(plan => plan && (plan.type === 'free' || numeric(plan.price) === 0)) : undefined;
function productList(payload) {
  const items = [payload, payload.data, payload.products, payload.items].find(Array.isArray);
  if (!items) throw new Error('产品核验失败：缺少产品数组');
  return items.filter(p => p && typeof p === 'object' && (String(p.slug || '').startsWith('free-') || freePlan(p)));
}
// 只显示显式公开字段；移除控制字符、已知凭据及手机号，绝不打印原始响应。
function display(value, a) {
  let text = String(value ?? '').replace(/[\x00-\x1f\x7f]/g, ' ');
  const secretValues = [a.password, a.token, a.refresh, a.cookie, a.fingerprint, env.VORTEXA_PASSWORD,
    env.VORTEXA_TOKEN, env.VORTEXA_ACCESS_TOKEN, env.VORTEXA_REFRESH, env.VORTEXA_COOKIE];
  for (const secret of secretValues.filter(Boolean).sort((x, y) => y.length - x.length)) text = text.split(secret).join('[已脱敏]');
  for (const item of String(a.cookie || '').split(';')) {
    const at = item.indexOf('=');
    if (at >= 0 && item.slice(at + 1).trim()) text = text.split(item.slice(at + 1).trim()).join('[已脱敏]');
  }
  return text.replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, '[手机号已脱敏]');
}
function identity(data, a, i) {
  const user = data.user || data;
  const value = user.nickname ?? user.username ?? user.displayName ?? user.display_name ?? user.public_uid ?? user.uid;
  if (value !== undefined && value !== null && ['string','number'].includes(typeof value)) log(`账号 ${i} 官方身份：${display(value, a)}`);
}
async function request(a, c, method, endpoint, options = {}) {
  if (DRY) throw new Error('断网保护：禁止调用 HTTP');
  const u = new URL(c.base + endpoint);
  const headers = {accept: 'application/json, text/plain, */*', 'accept-language': 'en,zh-CN;q=0.9,zh;q=0.8',
    'cache-control': 'no-cache', pragma: 'no-cache', 'content-type': 'application/json', origin: c.origin,
    referer: c.referer, 'user-agent': a.userAgent, 'x-fingerprint': a.fingerprint,
    'sec-ch-ua': `"Chromium";v="${a.userAgent.match(/Chrome\/(\d+)/)?.[1] || 148}", "Google Chrome";v="${a.userAgent.match(/Chrome\/(\d+)/)?.[1] || 148}", "Not/A)Brand";v="99"`,
    'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-site'};
  if (options.cookie && a.cookie) headers.cookie = a.cookie;
  if (options.auth) {
    if (!a.token) throw new Error('登录状态失败：没有可用访问 Token');
    headers.authorization = `Bearer ${a.token}`;
    if (a.cookie) headers.cookie = a.cookie;
  }
  if (endpoint === '/auth/refresh') headers['x-requested-with'] = 'XMLHttpRequest';
  const body = options.body === undefined ? null : JSON.stringify(options.body);
  if (body) headers['content-length'] = Buffer.byteLength(body);
  return new Promise((resolve, reject) => {
    let req, timer;
    const fail = message => { if (req) req.destroy(); clearTimeout(timer); reject(new Error(message)); };
    try {
      req = https.request(u, {method, headers}, res => {
        const chunks = []; let size = 0;
        res.on('error', () => fail('网络失败：响应中断'));
        res.on('aborted', () => fail('网络失败：响应中断'));
        res.on('data', chunk => {
          size += chunk.length;
          if (size > 1024 * 1024) { res.destroy(); fail('响应核验失败：数据超出限制'); }
          else chunks.push(chunk);
        });
        res.on('end', () => {
          clearTimeout(timer);
          const status = res.statusCode || 0;
          if (status === 401 || status === 403) return resolve({status});
          if (status < 200 || status >= 300) return reject(new Error(`HTTP 请求失败：${status}`));
          try {
            let buffer = Buffer.concat(chunks);
            const limits = {maxOutputLength: 1024 * 1024};
            if (res.headers['content-encoding'] === 'gzip') buffer = zlib.gunzipSync(buffer, limits);
            else if (res.headers['content-encoding'] === 'deflate') buffer = zlib.inflateSync(buffer, limits);
            else if (res.headers['content-encoding'] === 'br') buffer = zlib.brotliDecompressSync(buffer, limits);
            const data = business(JSON.parse(buffer.toString('utf8')));
            resolve({status, data, cookies: res.headers['set-cookie']});
          } catch (_) { reject(new Error('响应核验失败：压缩、JSON 或业务状态无效')); }
        });
      });
      timer = setTimeout(() => fail('网络失败：请求超时'), c.timeout);
      req.on('error', () => fail('网络失败：连接或 TLS 错误'));
      if (body) req.write(body);
      req.end();
    } catch (_) { fail('请求失败：请求参数或请求头无效'); }
  });
}
function mergeCookies(a, cookies) {
  const jar = new Map();
  for (const item of [...String(a.cookie || '').split(';'), ...(cookies || []).map(v => v.split(';')[0])]) {
    const at = item.indexOf('=');
    if (at > 0) jar.set(item.slice(0, at).trim(), item.slice(at + 1).trim());
  }
  a.cookie = [...jar].map(([k,v]) => `${k}=${v}`).join('; ');
}
async function login(a, c, i) {
  let endpoint, body;
  if (a.account && a.password) {
    endpoint = '/auth/login';
    const field = c.field || (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(a.account) ? 'email' : 'username');
    body = {[field]: a.account, password: a.password};
    if (field !== 'email' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(a.account)) body.email = a.account;
  } else if (a.cookie) endpoint = '/auth/refresh';
  else throw new Error('登录状态失败：缺少重新登录凭据');
  const r = await request(a, c, 'POST', endpoint, {body, cookie: true});
  if (!r.data || typeof r.data.accessToken !== 'string' || !r.data.accessToken) throw new Error('登录失败：未返回访问 Token');
  a.token = r.data.accessToken;
  mergeCookies(a, r.cookies);
  identity(r.data, a, i);
  log(`账号 ${i} 登录成功（凭据不输出）`);
}
async function api(a, c, i, method, endpoint, options = {}) {
  let r = await request(a, c, method, endpoint, options);
  if ([401,403].includes(r.status) && options.auth) {
    log(`账号 ${i} 授权失效，尝试重新登录一次`);
    await login(a, c, i);
    r = await request(a, c, method, endpoint, options);
  }
  if (!r.data) throw new Error(`授权失败：HTTP ${r.status}；请在浏览器检查登录或人机验证`);
  if (options.auth) identity(r.data, a, i);
  return r.data;
}
async function select(a, c, i, stage) {
  const products = await stage('读取免费产品', async () => productList(await api(a,c,i,'GET','/hosting/products/free')));
  if (!products.length) throw new Error('产品核验失败：没有免费产品');
  if (LIST) {
    for (const p of products) {
      log(`账号 ${i} 产品：${display(p.name || '',a)}；slug=${display(p.slug || '',a)}；product_id=${display(p.id || '',a)}`);
      for (const plan of (Array.isArray(p.plans) ? p.plans : []).filter(v => v && (v.type === 'free' || numeric(v.price) === 0))) {
        log(`账号 ${i} 免费套餐：plan_id=${display(plan.id || '',a)}；名称=${display(plan.name || '',a)}；类型=${display(plan.type || '',a)}；价格=${display(plan.price ?? '',a)}`);
      }
    }
    return;
  }
  let p;
  if (env.VORTEXA_PRODUCT_ID) p = products.find(v => String(v.id) === env.VORTEXA_PRODUCT_ID);
  else if (env.VORTEXA_PRODUCT_SLUG) p = products.find(v => String(v.slug || '').toLowerCase() === env.VORTEXA_PRODUCT_SLUG.toLowerCase());
  else if (env.VORTEXA_PRODUCT_NAME) p = products.find(v => String(v.name || '').toLowerCase().includes(env.VORTEXA_PRODUCT_NAME.toLowerCase()));
  else p = products[0];
  if (!p) throw new Error('产品核验失败：指定产品不存在，不改领其他产品');
  const plan = env.VORTEXA_PLAN_ID ? (Array.isArray(p.plans) ? p.plans.find(v => String(v.id) === env.VORTEXA_PLAN_ID) : null) : freePlan(p);
  if (!plan || !(plan.type === 'free' || numeric(plan.price) === 0) || !p.id || !plan.id) throw new Error('套餐核验失败：必须是明确免费且具有 ID 的套餐');
  log(`账号 ${i} 选择免费产品：${display(p.name || p.slug || p.id,a)}；product_id=${display(p.id,a)}；plan_id=${display(plan.id,a)}`);
  return {product_id: p.id, plan_id: plan.id};
}
async function runAccount(raw, c, i) {
  const started = Date.now(), stats = {total:0, success:0, alreadyComplete:0, skipped:0, failed:0};
  let result = 'failure';
  async function stage(name, action) {
    const n = ++stats.total, t = Date.now();
    log(`账号 ${i} 阶段 ${n}：${name}`);
    try {
      const data = await action(); stats.success++;
      log(`账号 ${i} 阶段 ${n} ✅ ${name}；耗时 ${Date.now()-t} 毫秒`);
      return data;
    } catch (e) {
      stats.failed++;
      log(`账号 ${i} 阶段 ${n} ❌ ${e.message}；耗时 ${Date.now()-t} 毫秒`);
      throw e;
    }
  }
  try {
    const a = await stage('检查账号配置', async () => checkedAccount(raw));
    if (DRY) {
      await stage('断网预演', async () => {
        log(`账号 ${i} 预演通过：凭据格式有效；${LIST ? '列出产品' : CLAIM ? '库存检查、免费套餐校验、领取及状态确认' : '已有主机、库存及免费套餐检查'}；所有 HTTP、登录和领取均未执行`);
      });
      stats.success--; stats.skipped++; result = 'dry-run';
    } else if (LIST) {
      await select(a,c,i,stage); result = 'success';
    } else {
      if (!a.token) await stage('登录或刷新访问凭据', () => login(a,c,i));
      for (let scan=1; scan<=c.scans; scan++) {
        const status = await stage(`第 ${scan} 次检查已有主机`, async () => {
          const data = await api(a,c,i,'GET','/hosting/free/status',{auth:true}); validStatus(data); return data;
        });
        if (owned(status)) {
          log(`账号 ${i} ☑️ 已有免费服务：${display(status.service?.name || status.service?.id || '已开通',a)}`);
          stats.success--; stats.alreadyComplete++; result = 'success'; break;
        }
        const stock = await stage('检查库存', async () => stockInfo(await api(a,c,i,'GET','/platform/free/stock-status')));
        log(`账号 ${i} 库存：${stock.text}`);
        if (!CLAIM) {
          await select(a,c,i,stage);
          log(`账号 ${i} ✅ 只读检查完成；领取资格：${status.can_get_free_server === true ? '允许' : status.can_get_free_server === false ? '暂不满足' : '未知'}；领取开关关闭`);
          stats.total++; stats.skipped++; log(`账号 ${i} 阶段 ${stats.total} ⏭️ 跳过领取；耗时 0 毫秒`); result = 'success'; break;
        }
        if (status.can_get_free_server === false) await stage('领取资格核验', async () => { throw new Error('领取失败：当前账号不满足条件'); });
        if (stock.available) {
          const body = await select(a,c,i,stage);
          await stage('提交免费领取', () => api(a,c,i,'POST','/hosting/free/purchase',{auth:true,body}));
          await stage('核验领取结果', async () => {
            if (c.delay) await sleep(c.delay*1000);
            const confirm = await api(a,c,i,'GET','/hosting/free/status',{auth:true}); validStatus(confirm);
            if (!owned(confirm)) throw new Error('领取未确认：官方状态未显示免费主机，不自动重复提交');
            log(`账号 ${i} 免费服务：${display(confirm.service?.name || confirm.service?.id || '已开通',a)}`);
          });
          log(`账号 ${i} [完成] 免费主机领取已核验`); result = 'success'; break;
        }
        if (scan === c.scans) await stage('库存扫描结果', async () => { throw new Error('领取未完成：库存不足或可用状态未知，扫描次数已耗尽'); });
        const delay = c.min + Math.floor(Math.random()*(c.max-c.min+1));
        await stage(`等待 ${delay} 秒再扫描`, () => sleep(delay*1000));
      }
    }
  } catch (e) {
    if (!stats.failed) {stats.total++; stats.failed++; log(`账号 ${i} 阶段 ${stats.total} ❌ ${e.message}；耗时 ${Date.now()-started} 毫秒`);}
  }
  log(`账号 ${i} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now()-started} 毫秒；状态 ${result}`);
  return {account:i,status:result,...stats,durationMs:Date.now()-started};
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(String(env.QINGLONG_NOTIFY ?? '1').trim())) return 'disabled';
  const candidates = [env.QINGLONG_NOTIFY_DIR && path.join(env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = candidates.find(v => fs.existsSync(v));
  if (!file) { log('⚠️ 通知不可用：未找到青龙 sendNotify.js；业务退出码保持不变'); return 'unavailable'; }
  // 外部通知在有限时长、无凭据环境子进程运行；预演时禁止该子进程网络。
  const code = `
    if (process.env.VORTEXA_DRY_RUN === '1') {
      const deny = () => { throw new Error('dry-run network disabled'); };
      require('net').Socket.prototype.connect = deny;
      require('tls').connect = deny;
      require('http').request = require('http').get = deny;
      require('https').request = require('https').get = deny;
      require('dgram').createSocket = deny;
      require('dns').lookup = require('dns').resolve = deny;
      global.fetch = deny;
      for (const key of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork']) require('child_process')[key] = deny;
      for (const key of Object.keys(require('dns').promises)) if (typeof require('dns').promises[key] === 'function') require('dns').promises[key] = deny;
    }
    Promise.resolve().then(() => require(process.argv[1]).sendNotify(process.argv[2],process.argv[3]))
      .then(() => {process.exit(0);}, () => {process.exit(1);});`;
  const childEnv = Object.fromEntries(Object.entries(env).filter(([key]) => !/^VORTEXA_/i.test(key)));
  if (DRY) childEnv.VORTEXA_DRY_RUN = '1';
  return new Promise(resolve => {
    let child, timer, finished=false;
    const finish = status => { if (!finished) {finished=true; clearTimeout(timer); resolve(status);} };
    try {
      child = spawn(process.execPath,['-e',code,file,TITLE,body],{env:childEnv,stdio:'ignore'});
      timer=setTimeout(() => {child.kill('SIGKILL'); finish('failed');},10000);
      child.on('error',() => finish('failed'));
      child.on('close', code => finish(code===0 ? (DRY ? 'dry-run-delivered' : 'sent') : 'failed'));
    } catch (_) {finish('failed');}
  });
}
async function main() {
  const start = Date.now(); let rows=[], count=0, configurationError=false;
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(start).toISOString()}；运行模式：${DRY ? '断网预演' : LIST ? '列出产品' : CLAIM ? '免费领取' : '只读检查'}`);
  try {
    const list=accounts(); count=list.length; const c=config();
    log(`账号总数：${count}`);
    if (!count) throw new Error('配置错误：缺少 VORTEXA_ACCOUNTS 或兼容凭据');
    for (let i=0;i<count;i++) rows.push(await runAccount(list[i],c,i+1));
  } catch (e) {
    configurationError=true;
    log(`账号总数：${count}；阶段 1 ❌ ${e.message}`);
  }
  const success=rows.filter(r => r.status !== 'failure').length;
  const failed=configurationError ? Math.max(1,count-success) : count-success;
  const status=configurationError ? 'configuration-error' : failed ? success ? 'partial-failure' : 'failure' : DRY ? 'dry-run' : 'success';
  const exitCode=failed ? 1 : 0;
  const tasks=rows.reduce((sum,r) => {for (const k of ['total','success','alreadyComplete','skipped','failed']) sum[k]+=r[k]; return sum;}, {total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  const body=`${TITLE}\n模式：${DRY ? '断网预演' : LIST ? '列出产品' : CLAIM ? '免费领取' : '只读检查'}\n状态：${status}\n账号总数：${count}；成功数：${success}；失败数：${failed}\n子任务总数：${tasks.total}；成功：${tasks.success}；失败：${tasks.failed}${DRY ? '\n预演不代表真实业务成功。' : ''}`;
  const notification=await notify(body);
  log('----------------------------------------');
  log(`任务统计：账号总数 ${count}，成功 ${success}，失败 ${failed}；子任务 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now()-start} 毫秒；通知状态 ${notification}；最终状态 ${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:TITLE,mode:DRY?'dry-run':LIST?'list':CLAIM?'claim':'check',status,accountCount:count,success,failed,configurationError,tasks,accounts:rows,notification,durationMs:Date.now()-start,exitCode}));
  process.exitCode=exitCode;
}
if (require.main === module) main().catch(() => {process.exitCode=1;});
