// name: 欣都龙城每日签到
// cron: 48 10 * * *
/**
 * name: 欣都龙城每日签到
 * cron: 48 10 * * *
 * 原作者：Telegram@sudojia https://blog.imzjw.cn，2024/07/22
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_mallcoo.js
 * SPDX-License-Identifier: GPL-3.0-only
 * 维护版：独立 Node.js 运行，仅使用内置模块。
 * MALLCOO_TOKEN：登录欣都龙城微信小程序，抓取 https://m.mallcoo.cn
 * 请求 Body 中 Header.Token 的值；每个非空行一个账号，不使用 & 或 @ 分隔。
 * MALLCOO_DRY_RUN=1：完全断网预演，包括通知仅预演。
 * QINGLONG_NOTIFY 默认开启；0/false/no/off 关闭，可用 QINGLONG_NOTIFY_DIR 指定通知模块目录。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { fork } = require('node:child_process');
const title = '欣都龙城每日签到';
const tokens = (process.env.MALLCOO_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const dry = process.env.MALLCOO_DRY_RUN === '1';
const started = Date.now();
const lines = [];
function clean(value) {
  let s = String(value);
  for (const token of tokens) s = s.split(token).join('[凭据已隐藏]');
  return s.replace(/1[3-9]\d{9}/g, '[手机号已隐藏]').replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
}
function log(value) {
  const s = clean(value);
  console.log(`[${new Date().toTimeString().slice(0, 8)}] ${s}`);
  lines.push(s);
}
function body(token, upper = false) {
  return { [upper ? 'MallID' : 'MallId']: 10144, Header: { Token: token, systemInfo: {
    model: 'microsoft', SDKVersion: '3.5.0', system: 'Windows 11 x64', version: '3.9.10', miniVersion: '2.67.7'
  } } };
}
function request(endpoint, data) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(data);
    const req = https.request({ hostname: 'm.mallcoo.cn', path: endpoint, method: 'POST', headers: {
      'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json', Accept: '*/*',
      Referer: 'https://servicewechat.com/wx7ef63cf605a639fb/18/page-frame.html',
      'Content-Length': Buffer.byteLength(payload)
    } }, res => {
      let length = 0; const chunks = [];
      res.on('data', chunk => { length += chunk.length; if (length > 1048576) req.destroy(new Error('响应过大')); else chunks.push(chunk); });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error(`HTTP 请求失败（${res.statusCode}）`));
        try {
          const result = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!result || result.m !== 1) return finish(new Error(result && result.m === 320 ? '凭据无效或过期' : '业务接口未确认成功'));
          if (!result.d || typeof result.d !== 'object') return finish(new Error('业务响应结构异常'));
          finish(null, result.d);
        } catch { finish(new Error('响应不是有效 JSON')); }
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    function finish(err, result) { clearTimeout(timer); err ? reject(err) : resolve(result); }
    req.on('error', () => finish(new Error('网络请求失败或超时')));
    req.end(payload);
  });
}
function field(data, key, numeric = false) {
  const v = data[key];
  if (numeric ? !((typeof v === 'number' || typeof v === 'string') && /^\d+(\.\d+)?$/.test(String(v))) : typeof v !== 'string') throw new Error('业务字段缺失或格式异常');
  return v;
}
async function notify(summary) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) return '断网预演，通知未发送';
  const choices = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const modulePath = choices.find(p => fs.existsSync(p));
  if (!modulePath) return '不可用：未找到 sendNotify.js';
  return new Promise(resolve => {
    // 子进程隔离通知模块的输出和异常，超时不改变业务退出码。
    const child = fork(__filename, ['--notify-worker'], { stdio: ['ignore', 'ignore', 'ignore', 'ipc'] });
    let done = false;
    const finish = state => { if (done) return; done = true; clearTimeout(timer); child.kill(); resolve(state); };
    const timer = setTimeout(() => finish('失败：通知超时'), 15000);
    child.on('message', ok => finish(ok ? '已发送' : '失败'));
    child.on('error', () => finish('失败'));
    child.on('exit', () => finish('失败'));
    child.send({ modulePath, title, summary });
  });
}
async function main() {
  log(`===== ${title} =====`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式运行'}；账号数：${tokens.length}`);
  const accounts = [];
  if (!tokens.length) log('❌ 配置错误：MALLCOO_TOKEN 必须包含至少一个账号');
  for (let i = 0; i < tokens.length; i++) {
    const begin = Date.now(); const stats = { account: i + 1, total: 5, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    const token = tokens[i]; let authenticated = false;
    const stages = [
      ['账号信息', async () => { const d = await request('/api/user/user/GetUserAndMallCard', body(token)); const name = field(d, 'NickName'); log(`昵称：${name}`); authenticated = true; }],
      ['每日签到', async () => {
        const d = await request('/api/user/user/CheckinBefore', { ...body(token), IsCheckMemberCard: true });
        if (typeof d.IsCheckIn !== 'boolean') throw new Error('签到状态字段异常');
        if (d.IsCheckIn) { log('☑️ 今日已签到'); return 'already'; }
        await request('/api/user/User/CheckinV2', body(token, true));
        const verified = await request('/api/user/user/CheckinBefore', { ...body(token), IsCheckMemberCard: true });
        if (verified.IsCheckIn !== true) throw new Error('签到后状态未确认');
        log('✅ 签到成功，已复核签到状态');
      }],
      ['积分余额', async () => { const d = await request('/api/user/Bonus/GetBonusHistoryList', { ...body(token, true), PageIndex: 1, PageSize: 10 }); log(`当前积分：${field(d, 'TotalBonus', true)}`); }],
      ['连续签到天数', async () => { const d = await request('/api/user/User/GetCheckinDetail', body(token, true)); log(`已连续签到${field(d, 'ContinueDay', true)}天`); }],
      ['过期积分提示', async () => { const d = await request('/api/user/Bonus/GetUserExpiredBonus', body(token, true)); log(`过期积分提示：${field(d, 'ExpiredBounsTips')}`); }]
    ];
    for (let j = 0; j < stages.length; j++) {
      const t = Date.now(); const [name, run] = stages[j];
      log(`账号 ${i + 1} 阶段 ${j + 1}/5：${name}`);
      try {
        if (dry || (j > 0 && !authenticated)) { stats.skipped++; log(`⏭️ ${dry ? 'DRY_RUN：已检查请求计划，不发送请求' : '账号认证失败，跳过'}；耗时 ${Date.now() - t}ms`); }
        else { const state = await run(); state === 'already' ? stats.alreadyComplete++ : stats.success++; log(`✅ ${name}完成；耗时 ${Date.now() - t}ms`); }
      } catch (error) { stats.failed++; log(`❌ ${name}失败：${error.message}；耗时 ${Date.now() - t}ms`); }
    }
    stats.ok = stats.failed === 0; stats.elapsedMs = Date.now() - begin; accounts.push(stats);
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${stats.elapsedMs}ms`);
  }
  const success = accounts.filter(a => a.ok).length;
  const failed = accounts.length - success;
  const ok = tokens.length > 0 && failed === 0;
  const status = !tokens.length ? 'configuration-error' : dry ? 'dry-run' : ok ? 'success' : success ? 'partial-failure' : 'failure';
  const totals = accounts.reduce((a, s) => { for (const k of Object.keys(a)) a[k] += s[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  log('--------------------------------');
  log(`账号总数 ${tokens.length}，成功 ${success}，失败 ${failed}；子任务：${JSON.stringify(totals)}`);
  let notification;
  try { notification = await notify(lines.join('\n')); } catch { notification = '失败：通知不可用'; }
  log(`通知状态：${notification}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now() - started}ms；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: title, mode: dry ? 'dry-run' : 'live', status, accountCount: tokens.length, success, failed, totals, accounts, notification }));
  process.exitCode = ok ? 0 : 1;
}
if (process.argv[2] === '--notify-worker') {
  process.once('message', async ({ modulePath, title, summary }) => {
    try { await require(modulePath).sendNotify(title, summary); process.send(true); } catch { process.send(false); }
  });
} else main().catch(() => { console.error('内部执行错误'); process.exitCode = 1; });
