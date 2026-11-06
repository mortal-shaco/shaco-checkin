// name: 威锋网签到
// cron: 16 10 * * *
// SPDX-License-Identifier: GPL-3.0-only
// 来源：chavyleung/scripts，feng/feng.js、feng/feng.cookie.js
// 上游版本：bfab3c906f3d5d126e9094f15730e025f7f32128。保留原作者署名及 GPL-3.0-only 许可。
/*
 * Node.js >= 18，无第三方业务依赖。定时表达式为每日 08:00（上游未提供）。
 * FENG_ACCOUNTS：每个非空行一个 JSON 对象：{"body":"原始登录请求体","headers":{"X-Running-Env":"原值"}}
 * 在本人威锋 App 登录时，通过本人授权的抓包工具获取
 * POST https://api.wfdata.club/v1/auth/signin 的原始请求体及 X-Running-Env。
 * body 必须原样保留为字符串，不拆分其中的 &、@ 或其他字符。
 * 不需要复制 Cookie、X-Request-Id、X-Access-Token；签名及临时令牌由脚本处理。
 * 兼容环境变量 chavy_login_feng 中原会话 JSON，不读取 box.dat 或私有文件。
 * FENG_DRY_RUN=1：只校验参数、生成本地签名，不调用业务接口。
 * 通知遵循 QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS；预演通知在禁止联网的子进程尝试。
 * 默认仅执行登录与签到，不发布内容、不修改其他资料、不缓存凭据。
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
    const identities = ["a4a2af6a3c46bf58", "scripts/feng.js", "feng.js", "feng"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '威锋网签到';
const CATALOG = 'a4a2af6a3c46bf58';
const dryRun = process.env.FENG_DRY_RUN === '1';
const started = Date.now();
const rows = (process.env.FENG_ACCOUNTS || process.env.chavy_login_feng || '').split(/\r?\n/).filter(s => s.trim());
const secrets = [];
const results = [];
const now = () => new Date().toTimeString().slice(0, 8);
const log = text => console.log(`[${now()}] ${text}`);
const elapsed = start => `${((Date.now() - start) / 1000).toFixed(2)}秒`;
function fail(message) { const e = new Error(message); e.safe = true; throw e; }
function parseAccount(line) {
  let data;
  try { data = JSON.parse(line); } catch { fail('账号行必须是完整 JSON 对象'); }
  if (!data || Array.isArray(data) || typeof data !== 'object') fail('账号行必须是 JSON 对象');
  if (typeof data.body !== 'string' || !data.body.trim()) fail('缺少原始登录请求体 body');
  const headers = data.headers;
  if (!headers || typeof headers !== 'object' || Array.isArray(headers)) fail('缺少请求头 headers');
  const entry = Object.entries(headers).find(([k]) => k.toLowerCase() === 'x-running-env');
  const env = entry && entry[1];
  if (typeof env !== 'string' || !env.trim() || /[\r\n\x00-\x1f\x7f]/.test(env) || env.length > 8192) fail('X-Running-Env 缺失或格式无效');
  // 不采用捕获的 URL、签名、Cookie 或其他任意请求头。
  secrets.push(data.body, env);
  try {
    for (const [key, value] of new URLSearchParams(data.body)) if (value && /password|passwd|token|session|cookie|secret|device|phone|mobile/i.test(key)) secrets.push(value);
    const body = JSON.parse(data.body);
    if (body && typeof body === 'object') for (const [key, value] of Object.entries(body)) if (typeof value === 'string' && /password|passwd|token|session|cookie|secret|device|phone|mobile/i.test(key)) secrets.push(value);
  } catch { /* 原始请求体无需是 JSON。 */ }
  return { body: data.body, env };
}
function signature(endpoint, time = Date.now()) {
  // 与上游 CryptoJS AES-CBC / PKCS7 的原始密钥模式一致，非口令派生模式。
  const key = Buffer.from('aaf82c19ea3b090b', 'utf8');
  const cipher = crypto.createCipheriv('aes-128-cbc', key, key);
  return Buffer.concat([cipher.update(`url=${endpoint}$time=${time}`, 'utf8'), cipher.final()]).toString('base64');
}
function request(endpoint, account, token) {
  if (dryRun) fail('预演模式禁止业务网络请求');
  const body = token ? '' : account.body;
  const headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Request-Id': signature(endpoint),
    'X-Running-Env': account.env,
    'Content-Length': Buffer.byteLength(body)
  };
  if (token) {
    headers['X-Access-Token'] = token;
    headers['User-Agent'] = 'fengapp/6.4 (com.feng.New.WPForumClient; build:21.03.14; iOS 14.4.1) Alamofire/4.9.1';
  }
  return new Promise((resolve, reject) => {
    let timer;
    const error = text => { const e = new Error(text); e.safe = true; return e; };
    const req = https.request({ hostname: 'api.wfdata.club', path: endpoint, method: 'POST', headers }, res => {
      const chunks = []; let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) req.destroy(error('响应超过大小限制'));
        else chunks.push(chunk);
      });
      res.on('error', () => req.destroy(error('响应读取失败')));
      res.on('aborted', () => req.destroy(error('响应中断')));
      res.on('end', () => {
        clearTimeout(timer);
        if (res.statusCode < 200 || res.statusCode >= 300) return reject(error(`HTTP 状态异常（${res.statusCode}），未跟随重定向`));
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch { reject(error('响应不是有效 JSON')); }
      });
    });
    timer = setTimeout(() => req.destroy(error('请求超时（15秒）')), 15000);
    req.on('error', e => { clearTimeout(timer); reject(e.safe ? e : error('网络请求失败（详情已脱敏）')); });
    req.end(body);
  });
}
function businessCode(response) {
  const code = response && response.status && response.status.code;
  if (typeof code !== 'number' || !Number.isInteger(code)) fail('响应缺少明确的业务状态码');
  return code;
}
function identity(data) {
  for (const obj of [data, data && data.user, data && data.userInfo]) {
    if (!obj || typeof obj !== 'object') continue;
    for (const key of ['nickname', 'nickName', 'username', 'displayName', 'uid']) {
      const value = obj[key];
      if (typeof value !== 'string' && typeof value !== 'number') continue;
      const text = String(value);
      if (!text || /(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text) || secrets.some(secret => secret && text.includes(secret))) continue;
      log(`官方账号身份 ${key}: ${JSON.stringify(value)}`);
    }
  }
}
async function runAccount(line, index) {
  const start = Date.now();
  const stats = { account: index, total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, status: 'failure' };
  let completed = 0;
  async function stage(number, title, action) {
    const begin = Date.now(); log(`账号${index} 阶段${number}/3 ${title}：开始`);
    try {
      const result = await action(); completed++;
      const state = result && result.state || 'success';
      stats[state]++;
      log(`账号${index} 阶段${number}/3 ${title}：${state === 'skipped' ? '⏭️ 预演跳过网络操作' : state === 'alreadyComplete' ? '☑️ 已签到' : '✅ 成功'}，耗时${elapsed(begin)}`);
      return result;
    } catch (e) {
      stats.failed++; completed++;
      log(`账号${index} 阶段${number}/3 ${title}：❌ ${e.safe ? e.message : '执行异常（详情已脱敏）'}，耗时${elapsed(begin)}`);
      throw e;
    }
  }
  try {
    const account = await stage(1, '校验会话参数', () => parseAccount(line));
    let token;
    await stage(2, '登录', async () => {
      if (dryRun) { signature('/v1/auth/signin'); return { state: 'skipped' }; }
      const response = await request('/v1/auth/signin', account);
      const code = businessCode(response);
      if (code !== 0) fail(`登录业务失败（代码${code}）`);
      token = response.data && response.data.accessToken;
      if (typeof token !== 'string' || !token.trim() || /[\r\n\x00-\x1f\x7f]/.test(token)) fail('登录成功响应缺少有效 accessToken');
      secrets.push(token); identity(response.data);
    });
    await stage(3, '每日签到', async () => {
      if (dryRun) { signature('/v1/attendance/userSignIn'); return { state: 'skipped' }; }
      const response = await request('/v1/attendance/userSignIn', account, token);
      const code = businessCode(response);
      if (code === 1021) return { state: 'alreadyComplete' };
      if (code !== 0) fail(`签到业务失败（代码${code}）`);
    });
    stats.status = dryRun ? 'dry-run' : 'success';
  } catch { stats.skipped += stats.total - completed; }
  stats.durationMs = Date.now() - start;
  log(`账号${index}统计：总任务${stats.total}，成功${stats.success}，已完成${stats.alreadyComplete}，跳过${stats.skipped}，失败${stats.failed}，耗时${elapsed(start)}，状态${stats.status}`);
  return stats;
}
function globMatch(pattern, value) {
  const regex = pattern.split('*').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
  return new RegExp(`^${regex}$`).test(value);
}
async function notify(summary) {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').trim().toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(mode)) return '已关闭';
  const enabled = ['1', 'true', 'yes', 'on'].includes(mode);
  const selectors = process.env.QINGLONG_NOTIFY_SCRIPTS;
  const names = [CATALOG, 'feng/feng.js', 'feng.js', 'candidate.js', path.basename(__filename), __filename.replace(/\\/g, '/')];
  if (selectors !== undefined) {
    if (!selectors.split(/[,;\s]+/).filter(Boolean).some(s => names.some(n => globMatch(s, n)))) return '未选中';
  } else if (!enabled) return '未选中（默认仅通知清单内脚本）';
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'];
  const file = candidates.find(p => p && fs.existsSync(p));
  if (!file) return '不可用（未找到 sendNotify.js，业务退出码保持不变）';
  const body = `模式：${dryRun ? '断网预演' : '正式'}；状态：${summary.status}；账号总数${summary.accounts}，成功${summary.succeeded}，失败${summary.failed}；子任务成功${summary.steps.success}，已完成${summary.steps.alreadyComplete}，跳过${summary.steps.skipped}，失败${summary.steps.failed}`;
  // 通知库在独立进程运行，禁止其输出泄露环境变量；超时或失败不覆盖业务状态。
  // 预演仍调用本地通知入口，但封锁网络和启动外部程序的能力。
  const code = `
    if (process.env.FENG_DRY_RUN === '1') {
      const deny = () => { throw new Error('预演禁止网络和外部程序'); };
      for (const mod of ['http','https']) for (const key of ['request','get']) require(mod)[key] = deny;
      const net = require('net'); net.Socket.prototype.connect = deny; net.connect = deny; net.createConnection = deny;
      require('tls').connect = deny; require('dgram').createSocket = deny; require('http2').connect = deny;
      for (const obj of [require('dns'), require('dns').promises])
        for (const key of Object.keys(obj)) if (/^(lookup|resolve|reverse)/.test(key)) obj[key] = deny;
      const cp = require('child_process');
      for (const key of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork']) cp[key] = deny;
      global.fetch = deny; global.WebSocket = deny;
    }
    Promise.resolve().then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3]))
      .then(() => process.exit(0), () => process.exit(1));
  `;
  return new Promise(resolve => {
    let done = false;
    const child = spawn(process.execPath, ['-e', code, file, TITLE, body], { stdio: 'ignore', env: process.env });
    const timer = setTimeout(() => { child.kill('SIGKILL'); finish('失败（通知超时，业务退出码保持不变）'); }, 10000);
    function finish(value) { if (!done) { done = true; clearTimeout(timer); resolve(value); } }
    child.on('error', () => finish('失败（通知不可用，业务退出码保持不变）'));
    child.on('close', code => finish(code === 0 ? (dryRun ? '已调用本地通知（网络已禁止）' : '已发送') : '失败（业务退出码保持不变）'));
  });
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dryRun ? '断网预演' : '正式'}；账号数量：${rows.length}`);
  if (!rows.length) log('❌ 配置错误：请设置 FENG_ACCOUNTS（兼容 chavy_login_feng），每个非空行一个会话 JSON');
  for (let i = 0; i < rows.length; i++) results.push(await runAccount(rows[i], i + 1));
  const failed = results.filter(r => r.status === 'failure').length;
  const status = !rows.length ? 'configuration-error' : failed ? (failed === rows.length ? 'failure' : 'partial-failure') : dryRun ? 'dry-run' : 'success';
  const summary = {
    task: TITLE, mode: dryRun ? 'dry-run' : 'live', status, accounts: rows.length,
    succeeded: results.length - failed, failed,
    steps: results.reduce((a, r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }),
    results
  };
  const exitCode = !rows.length || failed ? 1 : 0;
  try { summary.notification = await notify(summary); }
  catch { summary.notification = '失败（业务退出码保持不变）'; }
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`任务统计：账号总数${summary.accounts}，成功${summary.succeeded}，失败${failed}；子任务总数${summary.steps.total}，成功${summary.steps.success}，已完成${summary.steps.alreadyComplete}，跳过${summary.steps.skipped}，失败${summary.steps.failed}`);
  log(`通知状态：${summary.notification}；总耗时：${elapsed(started)}；完成时间：${summary.finishedAt}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
}
main();
