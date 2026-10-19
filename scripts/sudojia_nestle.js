// name: 雀巢会员
// cron: 30 2 * * *
/**
 * name: 雀巢会员
 * cron: 28 8 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * Derived from sudojia/AutoTaskScript src/wx_mini/sudojia_nestle.js
 * Original author: Telegram@sudojia; https://blog.imzjw.cn; 2024/11/27
 * Upstream commit: 4a55327baed0321bdf95802a75cc8363cae118b0
 * 本衍生版本遵循 GPL-3.0，保留原作者署名，不提供任何担保。
 * Node.js >= 18，无第三方依赖。
 * NESTLE_TOKEN：登录微信“雀巢会员”小程序，在自己的授权抓包环境中查找
 * crm.nestlechinese.com 请求头 authorization，去掉 Bearer 前缀。
 * 每个非空行一个账号；不支持 & 或 @ 分隔账号。不要分享凭据。
 * NESTLE_TASK_GUIDS：可选，每行一个明确授权执行的 task_guid。
 * 先不设置此变量，查看任务编号，再在小程序确认任务内容及风险后配置。
 * 默认仅查询，不提交任何任务；白名单对所有账号生效，缺失任务视为失败。
 * NESTLE_DRY_RUN=1：内置模拟，不请求业务接口或通知服务。
 * QINGLONG_NOTIFY 未设置时按上架状态；0/false/no/off 关闭。
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
    const identities = ["e68269710bb6fed2", "scripts/sudojia_nestle.js", "sudojia_nestle.js", "sudojia_nestle"];
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
const started = Date.now();
const dry = process.env.NESTLE_DRY_RUN === '1';
const lines = value => (value || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const accounts = lines(process.env.NESTLE_TOKEN);
const selected = [...new Set(lines(process.env.NESTLE_TASK_GUIDS))];
const secretValues = accounts.flatMap(x => [x, x.replace(/^Bearer\s+/i, '')]);
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const results = [];
const summary = { mode: dry ? 'dry-run' : 'live', accounts: accounts.length, success: 0, failed: 0, configurationErrors: 0 };
const stamp = () => new Date().toTimeString().slice(0, 8);
function safe(value) {
  let text = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const secret of secretValues) if (secret) text = text.split(secret).join('[凭据已隐藏]');
  return text;
}
function log(text) { console.log(`[${stamp()}] ${text}`); }
function fail(message) { const e = new Error(message); e.safe = true; return e; }
const guidOK = x => typeof x === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(x);
function request(endpoint, method, token, body) {
  if (dry) {
    if (endpoint.endsWith('/GetUserInfo')) return Promise.resolve({ nickname: '预演账号' });
    if (endpoint.endsWith('/getlist')) return Promise.resolve((selected.length ? selected : ['dry-task']).map(task_guid => ({ task_guid })));
    if (endpoint.endsWith('/getuserbalance')) return Promise.resolve(0);
    return Promise.resolve(null);
  }
  return new Promise((resolve, reject) => {
    const payload = body === undefined ? undefined : JSON.stringify(body);
    const headers = {
      'User-Agent': 'Mozilla/5.0',
      'content-type': 'application/json',
      referer: 'https://servicewechat.com/wxc5db704249c9bb31/353/page-frame.html',
      authorization: `Bearer ${token}`
    };
    if (payload !== undefined) headers['content-length'] = Buffer.byteLength(payload);
    let settled = false;
    const done = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(value);
    };
    const req = https.request({ hostname: 'crm.nestlechinese.com', path: endpoint, method, headers }, res => {
      const buffers = []; let bytes = 0;
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 1024 * 1024) { done(fail('响应超过大小限制')); res.destroy(); req.destroy(); }
        else buffers.push(chunk);
      });
      res.on('error', () => done(fail('响应读取失败')));
      res.on('aborted', () => done(fail('响应中断')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return done(fail(`HTTP 状态异常：${res.statusCode}`));
        let data;
        try { data = JSON.parse(Buffer.concat(buffers).toString('utf8')); }
        catch { return done(fail('接口返回非 JSON 数据')); }
        if (!data || data.errcode !== 200) return done(fail('接口未确认业务成功（要求 errcode=200）'));
        done(null, data.data);
      });
    });
    const timer = setTimeout(() => { done(fail('请求超时（15秒）')); req.destroy(); }, 15000);
    req.on('error', () => done(fail('网络或 TLS 请求失败')));
    req.end(payload);
  });
}
const endpoints = {
  user: '/openapi/member/api/User/GetUserInfo',
  list: '/openapi/activityservice/api/task/getlist',
  add: '/openapi/activityservice/api/task/add',
  balance: '/openapi/pointsservice/api/Points/getuserbalance'
};
const pause = () => dry ? Promise.resolve() : new Promise(resolve => setTimeout(resolve, 2200));
async function runAccount(raw, index) {
  const t = Date.now();
  const stats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let stage = 0;
  async function step(name, action) {
    const n = ++stage; const begin = Date.now(); stats.total++;
    log(`账号 ${index} 阶段 ${n}：${name}`);
    try {
      const value = await action(); stats.success++;
      log(`✅ 账号 ${index} 阶段 ${n} 成功，耗时 ${Date.now() - begin}ms`);
      return { ok: true, value };
    } catch (e) {
      stats.failed++;
      log(`❌ 账号 ${index} 阶段 ${n} 失败：${e.safe ? e.message : '处理异常，详情已隐藏'}，耗时 ${Date.now() - begin}ms`);
      return { ok: false };
    }
  }
  function skip(name) {
    stage++; stats.total++; stats.skipped++;
    log(`⏭️ 账号 ${index} 阶段 ${stage}：${name}，耗时 0ms`);
  }
  const token = raw.replace(/^Bearer\s+/i, '');
  const user = await step('校验凭据并查询用户信息', async () => {
    if (!token || /[\s&@\x00-\x1f\x7f]/.test(token)) throw fail('凭据格式错误；每行一个 Token，不使用 & 或 @ 分隔');
    const data = await request(endpoints.user, 'GET', token);
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw fail('用户信息结构异常');
    for (const key of ['nickname', 'username', 'displayName', 'public_uid']) {
      if (typeof data[key] === 'string' || typeof data[key] === 'number') log(`账号 ${index} ${key}：${safe(data[key])}`);
    }
    return data;
  });
  if (user.ok) {
    await pause();
    const tasks = await step('查询任务列表', async () => {
      const data = await request(endpoints.list, 'POST', token);
      if (!Array.isArray(data) || data.some(x => !x || !guidOK(x.task_guid))) throw fail('任务列表结构异常，停止提交');
      log(`账号 ${index} 可用任务 ${data.length} 项`);
      data.forEach((task, i) => log(`账号 ${index} 任务 ${i + 1} 编号：${safe(task.task_guid)}`));
      return data;
    });
    if (tasks.ok) {
      const available = new Set(tasks.value.map(x => x.task_guid));
      for (const guid of selected) {
        await pause();
        await step(`提交授权任务 ${safe(guid)}`, async () => {
          if (!available.has(guid)) throw fail('白名单任务不在当前任务列表中');
          await request(endpoints.add, 'POST', token, { task_guid: guid });
          log(dry ? '预演：模拟业务成功，未提交任务' : '任务接口已确认 errcode=200');
        });
      }
      for (const guid of available) if (!selected.includes(guid)) skip(`任务 ${safe(guid)} 未获显式授权，不提交`);
    } else skip('任务列表不可用，停止任务提交');
    await pause();
    await step('查询巢币余额', async () => {
      const balance = await request(endpoints.balance, 'POST', token);
      if (!((typeof balance === 'number' && Number.isFinite(balance)) || (typeof balance === 'string' && /^\d+(\.\d+)?$/.test(balance)))) throw fail('余额结构异常');
      log(`账号 ${index} 当前巢币：${balance}`);
    });
  } else {
    skip('身份查询失败，停止任务查询和提交'); skip('身份查询失败，停止余额查询');
  }
  for (const key of Object.keys(totals)) totals[key] += stats[key];
  const ok = stats.failed === 0;
  summary[ok ? 'success' : 'failed']++;
  results.push({ account: index, status: ok ? 'success' : 'failure', ...stats });
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now() - t}ms`);
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  // 完全断网预演不得加载第三方通知模块：通知模块可能在加载时发起请求。
  if (dry) { log(`通知预演：${body}`); return '预演完成，未联网发送'; }
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = locations.find(p => fs.existsSync(p));
  if (!file) return '通知不可用：未找到 sendNotify.js（保留业务退出码）';
  return new Promise(resolve => {
    const script = `const fs=require('node:fs'); const p=JSON.parse(fs.readFileSync(0,'utf8')); Promise.resolve().then(()=>require(p.file).sendNotify(p.title,p.body)).then(()=>process.exit(0),()=>process.exit(1));`;
    // 不把凭据传递给通知子进程；通知模块自身日志也不透传。
    const env = { ...process.env }; delete env.NESTLE_TOKEN;
    const child = spawn(process.execPath, ['-e', script], { env, stdio: ['pipe', 'ignore', 'ignore'] });
    let done = false;
    const finish = result => { if (done) return; done = true; clearTimeout(timer); resolve(result); };
    const timer = setTimeout(() => { child.kill('SIGKILL'); finish('通知超时（保留业务退出码）'); }, 15000);
    child.on('error', () => finish('通知启动失败（保留业务退出码）'));
    child.on('close', code => finish(code === 0 ? '已发送' : '通知失败（保留业务退出码）'));
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify({ file, title: '雀巢会员', body }));
  });
}
async function main() {
  console.log('========== 雀巢会员 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式运行'}；账号数：${accounts.length}`);
  try {
    if (!accounts.length || selected.some(x => !guidOK(x))) {
      summary.configurationErrors++;
      summary.failed = accounts.length;
      log('❌ 阶段 1：配置校验失败，耗时 0ms；请配置 NESTLE_TOKEN，并检查 NESTLE_TASK_GUIDS 格式');
    } else {
      for (let i = 0; i < accounts.length; i++) {
        await runAccount(accounts[i], i + 1);
        if (i + 1 < accounts.length) await pause();
      }
    }
  } catch {
    summary.configurationErrors++;
    log('❌ 运行异常，详情已隐藏');
  }
  const code = summary.failed || summary.configurationErrors ? 1 : 0;
  summary.status = code ? (summary.configurationErrors ? 'configuration-error' : summary.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `状态：${summary.status}；账号总数：${summary.accounts}；成功数：${summary.success}；失败数：${summary.failed}；配置错误：${summary.configurationErrors}；子任务成功：${totals.success}；跳过：${totals.skipped}；失败：${totals.failed}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '通知异常（保留业务退出码）'; }
  console.log('--------------------------------');
  log(body);
  log(`子任务总数：${totals.total}，已完成：${totals.alreadyComplete}；通知状态：${notification}`);
  log(`总耗时：${Date.now() - started}ms；完成时间：${new Date().toISOString()}；最终状态：${summary.status}`);
  if (dry && !code) console.log('NESTLE_DRY_RUN_OK');
  if (!dry && !code) console.log('NESTLE_SUCCESS');
  console.log('TASK_SUMMARY=' + JSON.stringify({ ...summary, tasks: totals, results, notification, durationMs: Date.now() - started }));
  process.exitCode = code;
}
main();
