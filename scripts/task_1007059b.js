// name: CordCloud 每日签到
// cron: 57 10 * * *
/*
name: CordCloud 每日签到
cron: 57 10 * * *
上游 hankchn/checkin-cordcloud scripts/checkin.js
来源提交 77749ac19de6413dbd80a9b65ab23eb5e232de8c，许可证 MIT。
原输入没有附带版权声明。保留来源归属，维护版本同样采用 MIT。

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

Node.js >=18。CORDCLOUD_ACCOUNTS 每个非空行一个 JSON 对象。
同一行提供 cookie，或 email 和 password，可同时提供以允许会话失效后登录。
可选 baseUrl 默认 https://cordc.net，loginPath 默认 /auth/login。
Cookie 从本人在官方网页登录并完成 2FA 后的 /user 请求头获取。
遇到 2FA 或页面挑战时需重新获取 Cookie，脚本不会猜测验证接口。
不保存凭据、截图或本地去重锁，以服务器明确结果判断签到。
CORDCLOUD_DRY_RUN=1 完全断网，通知也只模拟。详见 contract.json。
*/
'use strict';

// qinglong-notification-policy: begin
(() => {
  const raw = process.env.QINGLONG_NOTIFY;
  if (raw !== undefined && String(raw).trim() !== '' && String(raw).trim().toLowerCase() !== 'auto') return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["1007059beed08b37", "scripts/task_1007059b.js", "task_1007059b.js", "task_1007059b"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const TITLE = 'CordCloud 每日签到';
const CATALOG = '1007059beed08b37';
const DRY = process.env.CORDCLOUD_DRY_RUN === '1';
const started = Date.now();
const results = [];
let configurationError = false;

function log(message) {
  const time = new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
  console.log(`[${time}] ${message}`);
}

function parseAccount(line) {
  let account;
  try { account = JSON.parse(line); } catch { throw new Error('账号行必须为有效 JSON 对象'); }
  if (!account || typeof account !== 'object' || Array.isArray(account)) {
    throw new Error('账号行必须为 JSON 对象');
  }
  for (const key of ['email', 'password', 'cookie', 'baseUrl', 'loginPath']) {
    if (account[key] !== undefined && typeof account[key] !== 'string') {
      throw new Error('账号字段类型错误');
    }
  }
  if (!account.cookie?.trim() && !(account.email?.trim() && account.password)) {
    throw new Error('需要 cookie 或完整的 email、password');
  }
  if (account.cookie && /[\r\n\x00-\x1f\x7f]/.test(account.cookie)) {
    throw new Error('Cookie 含有非法控制字符');
  }
  let base;
  try { base = new URL(account.baseUrl || 'https://cordc.net'); }
  catch { throw new Error('baseUrl 格式错误'); }
  if (base.protocol !== 'https:' || base.username || base.password ||
      base.search || base.hash || base.pathname !== '/') {
    throw new Error('baseUrl 必须为不带路径、查询和凭据的 HTTPS 站点');
  }
  const loginPath = account.loginPath || '/auth/login';
  let login;
  try { login = new URL(loginPath, base); }
  catch { throw new Error('loginPath 格式错误'); }
  if (!loginPath.startsWith('/') || login.origin !== base.origin || login.search || login.hash) {
    throw new Error('loginPath 必须为同站点绝对路径');
  }
  return { ...account, base: base.origin, loginPath };
}

// 每个账号使用独立内存 Cookie 容器，校验域、路径和安全标记。
class Session {
  constructor(account) {
    this.origin = account.base;
    this.cookies = new Map();
    for (const part of (account.cookie || '').split(';')) {
      const delimiter = part.indexOf('=');
      if (delimiter < 1) continue;
      const name = part.slice(0, delimiter).trim();
      this.store(name, part.slice(delimiter + 1).trim(), '/', Infinity);
    }
    if (account.cookie?.trim() && !this.cookies.size) throw new Error('Cookie 格式错误');
  }

  store(name, value, cookiePath, expires) {
    if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(name) || /[\x00-\x20\x7f;]/.test(value)) {
      throw new Error('Cookie 格式错误');
    }
    this.cookies.set(`${name}|${cookiePath}`, { name, value, path: cookiePath, expires });
  }

  accept(headers, url) {
    for (const header of headers || []) {
      const parts = header.split(';');
      const first = parts.shift();
      const delimiter = first.indexOf('=');
      if (delimiter < 1) continue;
      const attributes = {};
      for (const part of parts) {
        const index = part.indexOf('=');
        attributes[(index < 0 ? part : part.slice(0, index)).trim().toLowerCase()] =
          index < 0 ? true : part.slice(index + 1).trim();
      }
      const domain = String(attributes.domain || url.hostname).replace(/^\./, '').toLowerCase();
      if (url.hostname !== domain && !url.hostname.endsWith(`.${domain}`)) continue;
      let expires = Infinity;
      if (attributes.expires && Number.isFinite(Date.parse(attributes.expires))) expires = Date.parse(attributes.expires);
      if (attributes['max-age'] !== undefined && /^-?\d+$/.test(attributes['max-age'])) {
        expires = Date.now() + Number(attributes['max-age']) * 1000;
      }
      const defaultPath = url.pathname.slice(0, url.pathname.lastIndexOf('/') + 1) || '/';
      const cookiePath = String(attributes.path || defaultPath);
      this.store(first.slice(0, delimiter).trim(), first.slice(delimiter + 1).trim(), cookiePath, expires);
    }
  }

  request(endpoint, method = 'GET', data, redirects = 0) {
    if (DRY) return Promise.reject(new Error('预演禁止网络请求'));
    const url = new URL(endpoint, this.origin);
    if (url.origin !== this.origin || url.username || url.password) {
      return Promise.reject(new Error('拒绝跨站点请求'));
    }
    const cookie = [...this.cookies.values()]
      .filter(item => item.expires > Date.now() && (url.pathname === item.path ||
        url.pathname.startsWith(item.path.endsWith('/') ? item.path : `${item.path}/`)))
      .sort((a, b) => b.path.length - a.path.length)
      .map(item => `${item.name}=${item.value}`).join('; ');
    const body = data === undefined ? undefined : JSON.stringify(data);
    const headers = { Accept: 'application/json, text/html', 'Accept-Encoding': 'identity',
      'User-Agent': 'CordCloud-Qinglong/1.0', 'X-Requested-With': 'XMLHttpRequest',
      Origin: this.origin, Referer: `${this.origin}/user` };
    if (cookie) headers.Cookie = cookie;
    if (body !== undefined || method === 'POST') headers['Content-Type'] = 'application/json';
    if (body !== undefined) headers['Content-Length'] = Buffer.byteLength(body);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => request.destroy(new Error('请求超时')), 15000);
      const request = https.request(url, { method, headers }, response => {
        const chunks = [];
        let size = 0;
        response.on('data', chunk => {
          size += chunk.length;
          if (size > 1024 * 1024) response.destroy(new Error('响应超过大小限制'));
          else chunks.push(chunk);
        });
        response.on('error', () => { clearTimeout(timer); reject(new Error('读取响应失败')); });
        response.on('end', () => {
          clearTimeout(timer);
          try {
            this.accept(response.headers['set-cookie'], url);
            if ([301, 302, 303, 307, 308].includes(response.statusCode)) {
              if (redirects >= 3 || !response.headers.location) throw new Error('重定向异常');
              const next = new URL(response.headers.location, url);
              if (next.origin !== this.origin) throw new Error('拒绝跨站点重定向');
              // 写请求不自动重放，防止重复签到和凭据转发。
              if (method !== 'GET') throw new Error('写请求发生重定向，需检查登录或验证状态');
              resolve(this.request(next.href, 'GET', undefined, redirects + 1));
              return;
            }
            if (response.statusCode < 200 || response.statusCode >= 300) {
              throw new Error(`HTTP 状态异常 ${response.statusCode}`);
            }
            resolve({ text: Buffer.concat(chunks).toString('utf8'), url });
          } catch (error) { reject(error); }
        });
      });
      request.on('error', () => { clearTimeout(timer); reject(new Error('网络请求失败或超时')); });
      if (body !== undefined) request.write(body);
      request.end();
    });
  }
}

function jsonResponse(response) {
  let data;
  try { data = JSON.parse(response.text); } catch { throw new Error('接口未返回有效 JSON，可能需要网页验证'); }
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('接口响应结构异常');
  return data;
}

function showIdentity(data, account) {
  // 仅使用官方明确命名的非凭据身份字段，拒绝控制字符及敏感字段回显。
  const identity = data.nickname ?? data.username ?? data.displayName ?? data.uid;
  if (typeof identity !== 'string' && typeof identity !== 'number') return;
  const text = String(identity);
  if (text.length > 160 || /[\x00-\x1f\x7f]|\b1[3-9]\d{9}\b|@/.test(text)) return;
  const secrets = [account.email, account.password, account.cookie,
    ...(account.cookie || '').split(';').map(part => part.slice(part.indexOf('=') + 1).trim())];
  if (secrets.some(secret => secret && text.includes(secret))) return;
  log(`官方账号身份 ${text}`);
}

async function stage(result, number, title, action) {
  const time = Date.now();
  log(`账号 ${result.account} · 阶段 ${number} ${title}`);
  result.tasks++;
  try {
    const status = await action();
    result[status || 'success']++;
    log(`账号 ${result.account} · 阶段 ${number} ${status === 'alreadyComplete' ? '☑️ 已完成' : status === 'skipped' ? '⏭️ 跳过' : '✅ 成功'} · 耗时 ${Date.now() - time} 毫秒`);
  } catch (error) {
    result.failed++;
    log(`账号 ${result.account} · 阶段 ${number} ❌ ${error.message} · 耗时 ${Date.now() - time} 毫秒`);
    throw error;
  }
}

async function runAccount(line, index) {
  const time = Date.now();
  const result = { account: index + 1, tasks: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  results.push(result);
  try {
    let account;
    let session;
    await stage(result, 1, '参数检查', async () => {
      account = parseAccount(line);
      session = new Session(account);
    });
    await stage(result, 2, '检查会话并按需登录', async () => {
      if (DRY) { log('预演已通过 · 会话与登录请求已模拟'); return 'skipped'; }
      const response = await session.request('/user');
      if (response.text.trim().startsWith('{')) {
        const data = jsonResponse(response);
        showIdentity(data, account);
      }
      const valid = response.url.pathname === '/user' || response.url.pathname.startsWith('/user/');
      const loginForm = /<input\b[^>]*type\s*=\s*["']password["']/i.test(response.text);
      if (valid && !loginForm) return;
      if (!(account.email && account.password)) throw new Error('会话失效，请完成网页验证并更新 Cookie');
      const data = jsonResponse(await session.request(account.loginPath, 'POST', {
        email: account.email, passwd: account.password, remember_me: 'on'
      }));
      if (data.ret !== 1) throw new Error('登录未确认成功，请检查凭据或在网页完成 2FA');
      showIdentity(data, account);
      const verified = await session.request('/user');
      if (!/^\/user(?:\/|$)/.test(verified.url.pathname) || /type\s*=\s*["']password["']/i.test(verified.text)) {
        throw new Error('登录后会话验证失败，请完成网页验证');
      }
    });
    await stage(result, 3, '每日签到', async () => {
      if (DRY) { log('预演已通过 · POST /user/checkin 已模拟，未执行签到'); return 'skipped'; }
      const data = jsonResponse(await session.request('/user/checkin', 'POST'));
      showIdentity(data, account);
      const message = typeof data.msg === 'string' ? data.msg.trim() : '';
      // ret=0 本身不代表已签到。仅接受明确的今日重复签到消息。
      if ((data.ret === 0 || data.ret === 1) &&
          /^(?:(?:您|你)?今天已经签到(?:了)?[！!。.]?|(?:今日|今天)?已签到[！!。.]?|already\s+(?:checked\s*in|signed\s*in)(?:\s+today)?[!.]?)$/i.test(message)) {
        return 'alreadyComplete';
      }
      if (data.ret !== 1) throw new Error('签到未确认成功，请检查账号或服务状态');
      log('签到成功 · 已验证接口 ret=1');
    });
  } catch {
    if (result.tasks === 1) configurationError = true;
  } finally {
    result.durationMs = Date.now() - time;
    result.status = result.failed ? 'failure' : DRY ? 'dry-run' : 'success';
    log(`账号 ${result.account} 统计 · 总任务 ${result.tasks} · 成功 ${result.success} · 已完成 ${result.alreadyComplete} · 跳过 ${result.skipped} · 失败 ${result.failed} · 耗时 ${result.durationMs} 毫秒`);
  }
}

function notificationSelected() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(mode)) return false;
  if (['1', 'true', 'yes', 'on'].includes(mode)) return true;
  if (mode !== 'auto') return false;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const selectors = process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean);
  const names = [CATALOG, 'checkin.js', 'scripts/checkin.js', path.basename(__filename)];
  return selectors.some(selector => {
    const pattern = selector.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    return names.some(name => new RegExp(`^${pattern}$`).test(name));
  });
}

async function notify(body) {
  if (!notificationSelected()) return 'disabled';
  if (DRY) { log('通知预演 · 脱敏汇总已生成，未调用通知网络'); return 'dry-run'; }
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  for (const filename of candidates) {
    if (!fs.existsSync(filename)) continue;
    let timer;
    try {
      const notifier = require(filename);
      if (typeof notifier.sendNotify !== 'function') continue;
      await Promise.race([
        Promise.resolve().then(() => notifier.sendNotify(TITLE, body)),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('通知超时')), 15000); })
      ]);
      return 'sent';
    } catch { log('⚠️ 通知发送失败，保留业务退出码'); return 'failed'; }
    finally { clearTimeout(timer); }
  }
  log('⚠️ 未发现青龙 sendNotify.js，保留业务退出码');
  return 'unavailable';
}

async function main() {
  const lines = (process.env.CORDCLOUD_ACCOUNTS || '').split(/\r?\n/).filter(line => line.trim());
  log(`========== ${TITLE} ==========`);
  log(`开始时间 ${new Date(started).toISOString()} · 模式 ${DRY ? '断网预演' : '正式签到'} · 账号数 ${lines.length}`);
  if (process.argv.length > 2) {
    configurationError = true;
    log('❌ 不支持命令行初始化，请在网页完成登录并设置账号变量');
  } else if (!lines.length) {
    configurationError = true;
    log('❌ 未设置 CORDCLOUD_ACCOUNTS');
  } else {
    for (let index = 0; index < lines.length; index++) await runAccount(lines[index], index);
  }
  const failed = results.filter(result => result.failed).length;
  const success = results.length - failed;
  const exitCode = configurationError || failed ? 1 : 0;
  const status = configurationError ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : DRY ? 'dry-run' : 'success';
  const body = `状态 ${status}，账号总数 ${lines.length}，成功 ${success}，失败 ${failed}，配置错误 ${configurationError ? 1 : 0}`;
  const notification = await notify(body);
  const taskCounts = {};
  for (const key of ['tasks', 'success', 'alreadyComplete', 'skipped', 'failed']) {
    taskCounts[key] = results.reduce((sum, result) => sum + result[key], 0);
  }
  log('----------------------------------------');
  log(`任务统计 · ${body}`);
  log(`子任务统计 · 总数 ${taskCounts.tasks} · 成功 ${taskCounts.success} · 已完成 ${taskCounts.alreadyComplete} · 跳过 ${taskCounts.skipped} · 失败 ${taskCounts.failed}`);
  log(`完成时间 ${new Date().toISOString()} · 总耗时 ${Date.now() - started} 毫秒 · 通知 ${notification} · 最终状态 ${status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify({ status, mode: DRY ? 'dry-run' : 'live', accounts: lines.length,
    success, failed, configurationError, taskCounts, results, notification, durationMs: Date.now() - started })}`);
  // 通知模块可能留下连接，业务退出码始终由任务结果决定。
  process.exit(exitCode);
}

main().catch(() => {
  log('❌ 任务内部错误');
  process.exitCode = 1;
});
