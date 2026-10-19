// name: 看雪论坛签到
// cron: 0 35 11 * * *
/*
name: 看雪论坛签到
cron: 0 35 11 * * *
上游：unitaryhighs/ql_sign_script，sign/kanxue.js
ql_sign_script : https://github.com/unitaryhighs/ql_sign_script
许可证：MIT（沿用上游许可）

KANXUE_COOKIE_LIST（必填）：登录 https://bbs.kanxue.com 后，在浏览器开发者
工具的网络面板查看本站请求，将请求头 Cookie 的完整值填入青龙环境变量。
每个非空行一个账号，不使用 & 或 @ 分隔，Cookie 中的分号和等号原样保留。
KANXUE_DRY_RUN=1：完全断网预演，不验证登录、不发送签到请求。
QINGLONG_NOTIFY 未设置时按上架状态；0/false/no/off 关闭通知。
QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
只执行签到，不发帖、评论、分享或修改账号资料。

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
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
*/
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["ada2bb484eeceac4", "scripts/kanxue.js", "kanxue.js", "kanxue"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');

const TITLE = '看雪论坛签到';
const ENDPOINT = 'https://bbs.kanxue.com/user-signin.htm';
const USER_AGENT = 'HD1910(Android/7.1.2) (pediy.UNICFBC0DD/1.0.5) Weex/0.26.0 720x1280';
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${stamp()}] ${text}`);
const disabled = value => /^(0|false|no|off)$/i.test(value || '');
const enabled = value => /^(1|true|yes|on)$/i.test(value || '');

function signIn(cookie) {
  return new Promise((resolve, reject) => {
    // 上游 HTTP.post 传入对象；独立版本显式使用 JSON 编码，避免重复编码。
    const body = JSON.stringify({ csrf_token: '' });
    const req = https.request(ENDPOINT, {
      method: 'POST', headers: {
        'User-Agent': USER_AGENT, Cookie: cookie,
        'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body)
      }
    }, res => {
      let size = 0;
      const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 65536) req.destroy(new Error('response-too-large'));
        else chunks.push(chunk);
      });
      res.on('error', () => reject(new Error('response-error')));
      res.on('aborted', () => reject(new Error('response-aborted')));
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error('http-error'));
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch { reject(new Error('invalid-json')); }
      });
    });
    // 总时限覆盖 DNS、连接、响应读取；不跟随重定向，不重试有副作用的 POST。
    const timer = setTimeout(() => req.destroy(new Error('timeout')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', err => {
      clearTimeout(timer);
      reject(new Error(['timeout', 'response-too-large'].includes(err.message) ? err.message : 'network-error'));
    });
    req.end(body);
  });
}

function resultOf(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return 'failure';
  if (response.code === 0 || response.code === '0') return 'success';
  const completed = ['今日已签到', '今天已经签到', '您今天已经签到', '已经签到', '已签到'];
  if ((typeof response.code === 'number' || typeof response.code === 'string') &&
      completed.includes(response.message)) return 'alreadyComplete';
  return 'failure';
}

function identityOf(response, cookie) {
  const objects = [response, response && response.data];
  for (const obj of objects) {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) continue;
    for (const field of ['nickname', 'username', 'display_name', 'displayName', 'uid']) {
      const value = obj[field];
      if (typeof value !== 'string' && typeof value !== 'number') continue;
      const text = String(value);
      // 公共身份按官方原值显示；拒绝控制字符、手机号及任何与凭据重合的值。
      const secrets = cookie.split(';').map(part => part.slice(part.indexOf('=') + 1).trim()).filter(Boolean);
      if (text && text.length <= 100 && !/[\r\n\x00-\x1f\x7f]/.test(text) &&
          !/(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text) &&
          !/cookie|token|session|authorization/i.test(text) &&
          !secrets.some(secret => text.includes(secret))) return text;
    }
  }
  return null;
}

async function notify(body, dryRun) {
  if (disabled(process.env.QINGLONG_NOTIFY)) return '已关闭';
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = files.find(file => fs.existsSync(file));
  if (!file) return '通知不可用（未找到青龙 sendNotify.js）';
  // 隔离通知异常和输出，且不向通知进程传递账号环境变量。
  const code = `
    if (process.env.NOTIFY_OFFLINE === '1') {
      const deny = () => { throw new Error('dry-run-network-disabled'); };
      for (const moduleName of ['http', 'https']) {
        const m = require(moduleName); m.request = deny; m.get = deny;
      }
      const net = require('net'); net.connect = deny; net.createConnection = deny;
      net.Socket.prototype.connect = deny; require('tls').connect = deny;
      const dns = require('dns'); dns.lookup = deny; dns.resolve = deny;
      if (dns.promises) { dns.promises.lookup = deny; dns.promises.resolve = deny; }
      global.fetch = deny;
      require('http2').connect = deny;
      require('dgram').createSocket = deny;
      require('worker_threads').Worker = deny;
      const cp = require('child_process');
      for (const key of ['exec', 'execSync', 'execFile', 'execFileSync', 'spawn', 'spawnSync', 'fork']) cp[key] = deny;
    }
    Promise.resolve().then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3]))
      .catch(() => { process.exitCode = 1; });
  `;
  const env = { ...process.env, NOTIFY_OFFLINE: dryRun ? '1' : '0' };
  delete env.KANXUE_COOKIE_LIST;
  return new Promise(resolve => execFile(process.execPath, ['-e', code, file, TITLE, body],
    { env, timeout: 10000, maxBuffer: 65536 }, err => resolve(err ?
      (dryRun ? '通知预演已尝试（断网限制或通知失败）' : '通知失败（保留业务退出码）') : '通知已发送')));
}

async function main() {
  const started = Date.now();
  const dryRun = enabled(process.env.KANXUE_DRY_RUN);
  const accounts = (process.env.KANXUE_COOKIE_LIST || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const summary = { task: TITLE, mode: dryRun ? 'dry-run' : 'live', accounts: accounts.length,
    successfulAccounts: 0, failedAccounts: 0, tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 },
    status: '', notification: '' };
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()} | 模式：${dryRun ? '断网预演' : '正式执行'} | 账号数：${accounts.length}`);
  log('阶段 1：配置检查');
  const configStarted = Date.now();
  let configurationError = accounts.length === 0;
  if (configurationError) log('❌ 配置错误：缺少 KANXUE_COOKIE_LIST 的非空账号行');
  log(`阶段 1 完成：${configurationError ? '❌ 缺少账号' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`);
  for (let i = 0; i < accounts.length; i++) {
    const began = Date.now();
    const cookie = accounts[i];
    summary.tasks.total++;
    let outcome = 'failure';
    log(`账号 ${i + 1} | 阶段 2：签到请求`);
    try {
      if (!/^[^=;\s]+=[^;]*(?:;.*)?$/.test(cookie) || /[\x00-\x1f\x7f]/.test(cookie)) {
        configurationError = true;
        log('❌ 配置错误：该行不是有效的 Cookie 请求头值');
      } else if (dryRun) {
        outcome = 'skipped';
        log('⏭️ DRY_RUN_OK：Cookie 格式通过；未请求网络，未验证真实业务');
      } else {
        const response = await signIn(cookie);
        const identity = identityOf(response, cookie);
        if (identity) log(`账号 ${i + 1} | 官方身份：${identity}`);
        outcome = resultOf(response);
        log(outcome === 'success' ? '✅ 签到成功（业务码 0）' : outcome === 'alreadyComplete' ?
          '☑️ 今日已签到（已核验）' : '❌ 签到未确认成功：登录失效或业务拒绝，请核对 Cookie');
      }
    } catch (err) {
      const reasons = { timeout: '请求超时', 'response-too-large': '响应过大', 'http-error': 'HTTP 状态异常',
        'invalid-json': '响应不是有效 JSON', 'network-error': '网络请求失败', 'response-error': '响应读取失败',
        'response-aborted': '响应中断' };
      log(`❌ ${reasons[err.message] || '请求失败'}；未确认签到成功`);
    }
    summary.tasks[outcome]++;
    if (outcome === 'failure') summary.failedAccounts++;
    else summary.successfulAccounts++;
    log(`账号 ${i + 1} | 阶段 2 完成 | 耗时 ${Date.now() - began}ms`);
    log(`账号 ${i + 1} 统计：总任务 1 | 成功 ${+(outcome === 'success')} | 已完成 ${+(outcome === 'alreadyComplete')} | 跳过 ${+(outcome === 'skipped')} | 失败 ${+(outcome === 'failure')} | 耗时 ${Date.now() - began}ms`);
  }
  const exitCode = configurationError || summary.failedAccounts ? 1 : 0;
  summary.status = configurationError ? 'configuration-error' : summary.failedAccounts ?
    (summary.successfulAccounts ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
  const body = `状态：${summary.status}；账号总数：${summary.accounts}；成功数：${summary.successfulAccounts}；失败数：${summary.failedAccounts}；签到成功：${summary.tasks.success}；已完成：${summary.tasks.alreadyComplete}；预演跳过：${summary.tasks.skipped}`;
  log('阶段 3：脱敏总结通知');
  const notifyStarted = Date.now();
  summary.notification = await notify(body, dryRun);
  log(`阶段 3 完成：${summary.notification} | 耗时 ${Date.now() - notifyStarted}ms`);
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(body);
  log(`子任务统计：总数 ${summary.tasks.total} | 成功 ${summary.tasks.success} | 已完成 ${summary.tasks.alreadyComplete} | 跳过 ${summary.tasks.skipped} | 失败 ${summary.tasks.failure}`);
  log(`总耗时：${summary.durationMs}ms | 完成时间：${summary.finishedAt} | 通知状态：${summary.notification} | 最终状态：${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
}

if (require.main === module) main().catch(() => { process.exitCode = 1; console.error('任务执行异常（已脱敏）'); });
