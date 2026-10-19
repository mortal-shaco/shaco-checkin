// name: 开天工作室
// cron: 35 0 * * *
/**
 * name: 开天工作室
 * cron: 33 9 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_ktgzs.js
 * KTGZS_TOKEN：打开微信小程序「开天工作室」，在自己的授权抓包环境中
 * 获取 api.box.vipinfinity.com 请求头 Authorization 完整值；每个非空行一个账号。
 * KTGZS_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方业务依赖。通知可使用青龙 sendNotify.js。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["3c1b078ac7332577", "scripts/sudojia_ktgzs.js", "sudojia_ktgzs.js", "sudojia_ktgzs"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const {execFile} = require('node:child_process');
const started = Date.now();
const dry = process.env.KTGZS_DRY_RUN === '1';
const accounts = (process.env.KTGZS_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const stamp = () => new Date().toTimeString().slice(0, 8);
const log = text => console.log(`[${stamp()}] ${text}`);
const number = x => (typeof x === 'number' && Number.isFinite(x) && x >= 0) || (typeof x === 'string' && /^\d+(\.\d+)?$/.test(x));
function request(route, method, token) {
  return new Promise((resolve, reject) => {
    let timer;
    const req = https.request({hostname: 'api.box.vipinfinity.com', path: route, method,
      headers: {'Authorization': token, 'User-Agent': 'Mozilla/5.0', 'Client-Name': 'default',
        'Client-Type': 'wechat--miniapp-windows', 'Content-Type': 'application/json',
        'Referer': 'https://servicewechat.com/wxa1ff7cf5ddff1da2/9/page-frame.html', 'Accept': '*/*', 'Accept-Encoding': 'identity'}}, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => { size += chunk.length; if (size > 1048576) req.destroy(new Error('响应过大')); else chunks.push(chunk); });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        clearTimeout(timer);
        if (res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP 状态异常 ${res.statusCode}`));
        let body; try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return reject(new Error('响应不是有效 JSON')); }
        if (!body || body.code !== 0) return reject(new Error('业务未确认成功，请检查凭据或服务状态'));
        resolve(body.data);
      });
    });
    timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('error', () => { clearTimeout(timer); reject(new Error('网络请求失败或超时')); });
    req.end();
  });
}
async function notify(summary) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  const paths = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = paths.find(x => fs.existsSync(x));
  if (!file) return '不可用：未找到青龙 sendNotify.js';
  // 子进程隔离通知的异常、日志和退出码；预演仍尝试通知接口，但禁止网络传输。
  const code = `if(process.env.KTGZS_DRY_RUN==='1') { const deny=()=>{throw Error('dry-run network disabled')}; require('node:net').Socket.prototype.connect=deny; require('node:tls').connect=deny; require('node:http').request=deny; require('node:https').request=deny; global.fetch=deny; require('node:dgram').createSocket=deny; for(const k of ['exec','execFile','spawn','fork','execSync','execFileSync','spawnSync'])require('node:child_process')[k]=deny; } Promise.resolve().then(()=>require(process.argv[1]).sendNotify('开天工作室',process.argv[2])).catch(()=>process.exitCode=1);`;
  return await new Promise(resolve => execFile(process.execPath, ['-e', code, file, summary], {timeout: 20000, maxBuffer: 65536, env: {...process.env, KTGZS_TOKEN: ''}}, error => resolve(error ? (dry ? '预演通知已尝试，网络传输被禁用' : '通知失败（不影响业务退出码）') : '通知已调用')));
}
async function main() {
  log('========== 开天工作室 ==========');
  log(`开始时间：${new Date(started).toISOString()} | 模式：${dry ? '断网预演' : '正式'} | 账号数：${accounts.length}`);
  const results = []; let configError = false;
  if (!accounts.length) { configError = true; log('❌ 配置错误：请设置 KTGZS_TOKEN，每行一个 Authorization 完整值'); }
  for (const [i, token] of accounts.entries()) {
    const begin = Date.now(); const stats = {account: i + 1, total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
    let authenticated = false;
    const stages = [
      ['账号信息', async () => { const d = await request('/user', 'GET', token); if (!d || !d.user || typeof d.user.name !== 'string' || !d.user.name.trim()) throw Error('账号信息字段缺失'); authenticated = true; log(`账号名称：${d.user.name}`); }],
      ['每日签到', async () => { const d = await request('/sign-in', 'POST', token); if (!d || !number(d.continuous_days) || !number(d.award_score)) throw Error('签到结果字段缺失'); log(`签到成功，积分+${d.award_score}；已连续签到${d.continuous_days}天`); }],
      ['积分查询', async () => { const d = await request('/asset-records/score?page=1&per_page=20', 'GET', token); if (!d || !Array.isArray(d.list) || !d.list[0] || !number(d.list[0].after)) throw Error('积分记录为空或字段缺失'); log(`当前积分：${d.list[0].after}`); }]
    ];
    for (const [j, [name, action]] of stages.entries()) {
      const s = Date.now(); log(`账号 ${i + 1} | 阶段 ${j + 1}/3 ${name}`);
      if (dry) { stats.skipped++; log(`⏭️ 预演：${name}，未发送请求 | 耗时 ${Date.now() - s}ms`); continue; }
      if (j > 0 && !authenticated) { stats.skipped++; log(`⏭️ 身份校验失败，跳过${name} | 耗时 ${Date.now() - s}ms`); continue; }
      try { await action(); stats.success++; log(`✅ ${name}完成 | 耗时 ${Date.now() - s}ms`); }
      catch (e) { stats.failed++; log(`❌ ${name}失败：${e.message} | 耗时 ${Date.now() - s}ms`); }
    }
    stats.durationMs = Date.now() - begin; results.push(stats);
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs}ms`);
  }
  const failed = results.filter(x => x.failed > 0).length;
  const success = dry ? 0 : results.filter(x => x.success === 3).length;
  const exitCode = configError || failed ? 1 : 0;
  const status = configError ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const summary = {task: '开天工作室', mode: dry ? 'dry-run' : 'live', status, accounts: accounts.length, success, failed, dryRunAccounts: dry ? accounts.length : 0, results, exitCode};
  const body = `状态：${status}；账号总数 ${accounts.length}，成功 ${success}，失败 ${failed}，预演 ${summary.dryRunAccounts}`;
  try { summary.notification = await notify(body); } catch { summary.notification = '通知不可用'; }
  log('--------------------------------'); log(body);
  const totals = results.reduce((a, r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0});
  summary.taskStatistics = totals; summary.durationMs = Date.now() - started; summary.finishedAt = new Date().toISOString();
  log(`子任务统计：总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`通知：${summary.notification} | 总耗时 ${summary.durationMs}ms | 完成时间 ${summary.finishedAt} | 最终状态 ${status}`);
  if (dry && !exitCode) log('DRY_RUN_OK');
  console.log('TASK_SUMMARY=' + JSON.stringify(summary)); process.exitCode = exitCode;
}
main();
