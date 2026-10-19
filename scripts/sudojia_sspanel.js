// name: SSPANEL面板签到
// cron: 34 0 * * *
/**
 * name: SSPANEL面板签到
 * cron: 35 9 * * *
 * 原作者：Telegram@sudojia — https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript，src/web/sudojia_sspanel.js
 * SPDX-License-Identifier: GPL-3.0-only
 * 维护版本保留上游 GPL-3.0 许可，按 GPL 第三版分发，不提供担保。
 * Node.js >= 18，无第三方业务依赖。
 * SITE_ACCOUNTS：每个非空行一个账号，格式为 HTTPS站点地址,邮箱:密码。
 * 在使用的机场网页底部确认 Powered by SSPANEL；从浏览器地址栏获取站点地址，
 * 使用本人注册邮箱和登录密码。先按第一个逗号、再按第一个冒号分割，密码可含冒号、逗号、&、@。
 * SSPANEL_DRY_RUN=1：仅校验配置并模拟流程；通知也禁止联网。
 * QINGLONG_NOTIFY 未设置时按上架状态；0/false/no/off 关闭通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["3ab685f53b0a5cc0", "scripts/sudojia_sspanel.js", "sudojia_sspanel.js", "sudojia_sspanel"];
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
const { spawn } = require('node:child_process');
const TITLE = 'SSPANEL面板签到';
const dry = process.env.SSPANEL_DRY_RUN === '1';
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${stamp()}] ${text}`);
function parse(line) {
  const comma = line.indexOf(',');
  const rest = line.slice(comma + 1);
  const colon = rest.indexOf(':');
  if (comma < 1 || colon < 1 || !rest.slice(colon + 1)) throw Error('配置格式错误');
  let url;
  try { url = new URL(line.slice(0, comma)); } catch { throw Error('站点地址无效'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) throw Error('站点必须是无凭据及查询参数的 HTTPS 地址');
  return { base: url.href.replace(/\/$/, ''), email: rest.slice(0, colon), password: rest.slice(colon + 1) };
}
function request(url, body, cookie) {
  return new Promise((resolve, reject) => {
    if (dry) return reject(Error('演练禁止网络请求'));
    const payload = new URLSearchParams(body).toString();
    const headers = { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0 SSPANEL-Checkin/1.0', 'Content-Length': Buffer.byteLength(payload) };
    if (cookie) headers.Cookie = cookie;
    const req = https.request(url, { method: 'POST', headers }, res => {
      let bytes = 0; const chunks = [];
      res.on('data', chunk => { bytes += chunk.length; if (bytes > 1048576) req.destroy(Error('响应超过大小限制')); else chunks.push(chunk); });
      res.on('error', () => reject(Error('读取响应失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return reject(Error(`HTTP 状态异常（${res.statusCode}）`));
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || typeof data !== 'object' || Array.isArray(data)) throw Error();
          resolve({ data, cookies: res.headers['set-cookie'] || [] });
        } catch { reject(Error('响应不是有效 JSON 对象')); }
      });
    });
    const timer = setTimeout(() => req.destroy(Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(Error('网络请求失败或超时')));
    req.end(payload);
  });
}
function showIdentity(data, account) {
  for (const obj of [data, data.user, data.data, data.data && data.data.user]) {
    if (!obj || typeof obj !== 'object') continue;
    for (const key of ['nickname', 'username', 'display_name', 'displayName', 'public_uid']) {
      const v = obj[key];
      if (typeof v !== 'string' && typeof v !== 'number') continue;
      const s = String(v);
      // 身份字段直接显示；拒绝混入手机号、凭据或日志控制字符的字段。
      if (!s || /[\r\n\x00-\x1f\x7f]|\+?\d[\d -]{9,}\d/.test(s) || s.includes(account.email) || s.includes(account.password)) continue;
      log(`账号身份 ${key}：${s}`); return;
    }
  }
}
function trafficValue(v) {
  // 只展示流量数值和单位，不输出服务端任意文本。
  return (typeof v === 'number' && Number.isFinite(v)) || (typeof v === 'string' && /^\s*\d+(?:\.\d+)?\s*(?:[KMGTPE]?i?B|Bytes?|字节|兆|吉)?\s*$/i.test(v)) ? String(v) : '接口未提供有效流量值';
}
async function notifyWorker() {
  // 子进程隔离通知日志及错误，防止第三方通知模块打印敏感配置。
  console.log = console.error = console.warn = () => {};
  if (dry) {
    const deny = () => { throw Error('演练禁止联网'); };
    require('node:net').Socket.prototype.connect = deny;
    require('node:http').request = require('node:http').get = deny;
    https.request = https.get = deny;
    global.fetch = async () => { throw Error('演练禁止联网'); };
    const cp = require('node:child_process');
    for (const k of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork']) cp[k] = deny;
  }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  for (const dir of dirs) {
    const file = path.join(dir, 'sendNotify.js');
    if (!fs.existsSync(file)) continue;
    const helper = require(file);
    if (typeof helper.sendNotify !== 'function') continue;
    await helper.sendNotify(TITLE, process.env.SSPANEL_NOTIFICATION_BODY);
    return;
  }
  throw Error('未找到通知模块');
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  return new Promise(resolve => {
    const env = { ...process.env, SSPANEL_NOTIFICATION_BODY: body };
    delete env.SITE_ACCOUNTS;
    const child = spawn(process.execPath, [__filename, '--notify-worker'], { env, stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); }, 12000);
    child.on('error', () => { clearTimeout(timer); resolve('不可用，保留业务退出码'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? (dry ? '演练通知处理完成（禁止联网）' : '通知模块已完成') : (dry ? '演练通知未发送（禁止联网或模块不可用）' : '通知失败或不可用，保留业务退出码')); });
  });
}
async function main() {
  const start = Date.now();
  const notificationDetails = [];
  const lines = (process.env.SITE_ACCOUNTS || '').split(/\r?\n/).filter(x => x.trim());
  const summary = { task: TITLE, mode: dry ? 'dry-run' : 'live', accounts: lines.length, success: 0, failed: 0, tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, results: [] };
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(start).toISOString()}；模式：${summary.mode}；账号数：${lines.length}`);
  if (!lines.length) log('❌ 配置错误：请设置 SITE_ACCOUNTS');
  for (let i = 0; i < lines.length; i++) {
    const begun = Date.now(); const stats = { total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }; let stage = 0;
    const step = async (name, action) => {
      stage++; const t = Date.now(); log(`账号 ${i + 1} 阶段 ${stage}/3：${name}`);
      try { const value = await action(); stats.success++; log(`✅ 账号 ${i + 1} 阶段 ${stage} ${name}完成；耗时 ${Date.now() - t}ms`); return value; }
      catch (err) { log(`❌ 账号 ${i + 1} 阶段 ${stage}：${err.message}；耗时 ${Date.now() - t}ms`); throw err; }
    };
    try {
      const account = await step('配置校验', () => parse(lines[i]));
      const cookie = await step('登录', async () => {
        if (dry) { log('⏭️ 演练：模拟登录，不发送请求'); return ''; }
        const r = await request(`${account.base}/auth/login`, { email: account.email, passwd: account.password, code: '' });
        if (r.data.ret !== 1) throw Error('登录业务未确认成功，请检查账号或站点兼容性');
        showIdentity(r.data, account);
        const cookies = r.cookies.map(c => c.split(';', 1)[0]).filter(c => /^[^=\s;]+=[^\r\n;]+$/.test(c));
        if (!cookies.length) throw Error('登录未返回有效会话');
        return cookies.join('; ');
      });
      await step('每日签到与流量展示', async () => {
        if (dry) { log('⏭️ 演练：模拟签到及流量展示，不变更账户'); return; }
        const { data } = await request(`${account.base}/user/checkin`, {}, cookie);
        if (data.ret !== 1) throw Error('签到业务未确认成功（不将未知业务码或提示文本当作成功）');
        showIdentity(data, account);
        log('✅ 签到成功');
        const traffic = `总套餐：${trafficValue(data.traffic)}；已使用：${trafficValue(data.trafficInfo?.lastUsedTraffic)}；剩余流量：${trafficValue(data.trafficInfo?.unUsedTraffic)}`;
        log(traffic);
        notificationDetails.push(`账号 ${i + 1}：签到成功；${traffic}`);
      });
      summary.success++;
    } catch { stats.failed++; stats.skipped = 3 - stage; summary.failed++; }
    for (const k of Object.keys(stats)) summary.tasks[k] += stats[k];
    summary.results.push({ account: i + 1, ...stats, durationMs: Date.now() - begun });
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now() - begun}ms${dry ? '（仅演练）' : ''}`);
  }
  const code = !lines.length || summary.failed ? 1 : 0;
  summary.status = !lines.length ? 'configuration-error' : summary.failed ? (summary.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  summary.notification = await notify(`模式：${summary.mode}；状态：${summary.status}；账号总数：${summary.accounts}；成功：${summary.success}；失败：${summary.failed}；子任务成功：${summary.tasks.success}；子任务失败：${summary.tasks.failed}${dry ? '；仅演练，未执行真实签到' : ''}\n${notificationDetails.join('\n')}`);
  summary.durationMs = Date.now() - start;
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`账号总数 ${summary.accounts}；成功 ${summary.success}；失败 ${summary.failed}；子任务：${JSON.stringify(summary.tasks)}`);
  log(`通知：${summary.notification}；总耗时 ${summary.durationMs}ms；完成时间：${summary.finishedAt}；最终状态：${summary.status}`);
  if (dry && code === 0) log('DRY_RUN_OK');
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = code;
}
if (process.argv.includes('--notify-worker')) notifyWorker().then(() => process.exit(0), () => process.exit(1));
else main().catch(() => { console.error('任务内部错误（详细内容已抑制）'); process.exitCode = 1; });
