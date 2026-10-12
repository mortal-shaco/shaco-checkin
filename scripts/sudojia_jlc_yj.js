// name: 嘉立创硬件开源平台
// cron: 44 5 * * *
/**
 * name: 嘉立创硬件开源平台
 * cron: 44 5 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 基于 sudojia/AutoTaskScript src/web/sudojia_jlc_yj.js
 * 原作者 Telegram@sudojia；https://blog.imzjw.cn；2025/01/02
 * 登录 https://oshwhub.com/sign_in，在浏览器开发者工具网络面板中，
 * 从 oshwhub.com 已登录请求复制完整 Cookie 到 JLC_COOKIE，每个非空行一个账号。
 * 不以 & 或 @ 分隔账号。JLC_YJ_DRY_RUN=1 完全离线预演。
 * QINGLONG_NOTIFY 默认开启；0/false/no/off 关闭；QINGLONG_NOTIFY_DIR 可指定通知模块目录。
 * 正式运行仅执行查询身份、每日签到和查询积分，不领取奖励、不更新账号资料。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { fork } = require('node:child_process');

// 通知单独进程运行，防止通知模块输出敏感内容、挂起或改变业务退出码。
if (process.argv[2] === '--notification-worker') {
  process.once('message', async ({ modulePath, title, body }) => {
    try {
      const mod = require(modulePath);
      if (typeof mod.sendNotify !== 'function') throw new Error();
      await mod.sendNotify(title, body);
      process.exit(0);
    } catch { process.exit(1); }
  });
} else {
  main().catch(() => { process.exitCode = 1; });
}

function stamp() { return new Date().toTimeString().slice(0, 8); }
function log(text) { console.log(`[${stamp()}] ${text}`); }
function request(cookie, method, endpoint, body) {
  return new Promise((resolve, reject) => {
    const payload = body === undefined ? undefined : JSON.stringify(body);
    const headers = { Cookie: cookie, Accept: 'application/json', 'User-Agent': 'Qinglong-OSHWHub/1.0' };
    if (payload) { headers['Content-Type'] = 'application/json'; headers['Content-Length'] = Buffer.byteLength(payload); }
    let settled = false;
    let timer;
    const finish = (err, data) => {
      if (settled) return;
      settled = true; clearTimeout(timer);
      err ? reject(new Error(err)) : resolve(data);
    };
    const req = https.request({ hostname: 'oshwhub.com', path: endpoint, method, headers }, res => {
      if (res.statusCode !== 200) { res.resume(); finish(`HTTP 状态异常（${res.statusCode}）`); return; }
      const chunks = []; let bytes = 0;
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 262144) { finish('响应超过大小限制'); res.destroy(); req.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => finish('响应读取失败'));
      res.on('aborted', () => finish('响应中断'));
      res.on('end', () => {
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || data.success !== true) return finish('官方未确认业务成功，请检查登录状态');
          finish(null, data);
        } catch { finish('响应格式无效'); }
      });
    });
    timer = setTimeout(() => { finish('请求超时'); req.destroy(); }, 15000);
    req.on('error', () => finish('网络请求失败'));
    req.end(payload);
  });
}
async function notify(body, dry) {
  if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  if (dry) return '离线模拟通知完成';
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  for (const dir of [...new Set(dirs)]) {
    const modulePath = path.resolve(dir, 'sendNotify.js');
    if (!fs.existsSync(modulePath)) continue;
    const ok = await new Promise(resolve => {
      let child; let timer; let done = false;
      const finish = value => { if (done) return; done = true; clearTimeout(timer); if (child) child.kill(); resolve(value); };
      try {
        const env = { ...process.env }; delete env.JLC_COOKIE;
        child = fork(__filename, ['--notification-worker'], { silent: true, env });
        child.stdout.resume(); child.stderr.resume();
        child.on('error', () => finish(false));
        child.on('exit', code => finish(code === 0));
        timer = setTimeout(() => finish(false), 15000);
        child.send({ modulePath, title: '嘉立创硬件开源平台', body }, err => { if (err) finish(false); });
      } catch { finish(false); }
    });
    if (ok) return '发送成功';
  }
  return '通知不可用或发送失败（保留业务退出码）';
}
async function main() {
  const start = Date.now();
  const dry = process.env.JLC_YJ_DRY_RUN === '1';
  const accounts = (process.env.JLC_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  const results = [];
  log('========== 嘉立创硬件开源平台 ==========');
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry ? '完全离线预演' : '正式执行'}；账号数：${accounts.length}`);
  let configurationError = false;
  if (!accounts.length) { configurationError = true; log('❌ 配置错误：JLC_COOKIE 必须包含至少一个账号的完整 Cookie'); }
  for (let i = 0; i < accounts.length; i++) {
    const cookie = accounts[i]; const accountStart = Date.now();
    const stats = { total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let identified = false;
    log(`----- 账号 ${i + 1} -----`);
    const stages = ['查询账号身份', '每日签到', '查询积分'];
    for (let j = 0; j < stages.length; j++) {
      const stageStart = Date.now();
      let outcome;
      try {
        if (j > 0 && !identified) { stats.skipped++; outcome = '⏭️ 身份查询未成功，跳过'; }
        else if (dry) {
          if (j === 0) identified = true;
          stats.success++; outcome = `✅ 离线预演：${j === 1 ? 'POST /api/users/signIn，正文仅含 _t' : 'GET /api/users'}；未发起请求`;
        } else {
          if (/[\x00-\x1f\x7f]/.test(cookie) || !cookie.includes('=')) throw new Error('Cookie 格式无效');
          const data = await request(cookie, j === 1 ? 'POST' : 'GET', j === 1 ? '/api/users/signIn' : '/api/users', j === 1 ? { _t: Date.now() } : undefined);
          if (j === 0) {
            if (!data.result || typeof data.result.nickname !== 'string' || !data.result.nickname.trim()) throw new Error('身份响应缺少昵称');
            identified = true;
            // 只读取官方指定的公开昵称字段，不输出 UUID、Cookie 或原始响应。
            outcome = `✅ 昵称：${data.result.nickname}`;
          } else if (j === 1) outcome = '✅ 签到成功（官方 success=true）';
          else {
            const points = data.result && data.result.points;
            if (!((typeof points === 'number' && Number.isFinite(points)) || (typeof points === 'string' && /^\d+(\.\d+)?$/.test(points)))) throw new Error('积分响应字段无效');
            outcome = `✅ 当前积分：${points}`;
          }
          stats.success++;
        }
      } catch (err) { stats.failed++; outcome = `❌ ${/^(HTTP 状态异常|官方未确认|响应|请求超时|网络请求失败|Cookie 格式无效|身份响应缺少昵称|积分响应字段无效)/.test(err.message) ? err.message : '请求配置或执行失败'}`; }
      log(`账号 ${i + 1} 阶段 ${j + 1}/3 ${stages[j]}：${outcome}；耗时 ${Date.now() - stageStart}ms`);
    }
    const ok = stats.failed === 0 && stats.skipped === 0;
    results.push({ account: i + 1, ...stats, ok, durationMs: Date.now() - accountStart });
    for (const key of Object.keys(totals)) totals[key] += stats[key];
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}；成功 ${stats.success}；已完成 ${stats.alreadyComplete}；跳过 ${stats.skipped}；失败 ${stats.failed}；耗时 ${Date.now() - accountStart}ms`);
  }
  const successCount = results.filter(r => r.ok).length;
  const failureCount = accounts.length - successCount;
  const exitCode = configurationError || failureCount ? 1 : 0;
  const status = configurationError ? 'configuration-error' : failureCount ? (successCount ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `账号总数 ${accounts.length}，成功 ${successCount}，失败 ${failureCount}；状态 ${status}；子任务成功 ${totals.success}、失败 ${totals.failed}、跳过 ${totals.skipped}`;
  let notification;
  try { notification = await notify(body, dry); } catch { notification = '通知失败（保留业务退出码）'; }
  log('----------------------------------------');
  log(body);
  log(`子任务总数 ${totals.total}；已完成 ${totals.alreadyComplete}；通知状态：${notification}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now() - start}ms；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: '嘉立创硬件开源平台', mode: dry ? 'dry-run' : 'live', status, accounts: accounts.length, success: successCount, failed: failureCount, configurationError, tasks: totals, results, notification, durationMs: Date.now() - start, exitCode }));
  process.exitCode = exitCode;
}
