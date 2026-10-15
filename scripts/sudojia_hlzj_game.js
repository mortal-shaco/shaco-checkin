// name: 海澜之家-游戏
// cron: 20 8,15,20 * * *
/**
 * name: 海澜之家-游戏
 * cron: 39 8,15,20 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Derived from sudojia/AutoTaskScript, Telegram@sudojia, https://blog.imzjw.cn
 * 原作者日期：2024/08/16。维护版：独立请求、失败闭合、无默认邀请绑定。
 * HLZJ_UNID：海澜之家小程序底部「游戏」，抓取自己账号
 * https://gmdevpro.hlzjppgl.cn/server/api/authorized-login 请求体 union_id。
 * 每个非空行一个账号，不支持 & 或 @ 分隔。不要提供整段请求体。
 * HLZJ_DRY_RUN=1 完全断网预演（通知仅预览）；HLZJ_USE_POWER=1 开启消耗电力及宝箱。
 * HLZJ_POWER_LIMIT 默认 20，每账号每次最多 1–100 次消耗请求；达到上限仍有任务则失败。
 * QINGLONG_NOTIFY 默认 1；可选 QINGLONG_NOTIFY_DIR 指定青龙通知模块目录。
 * 原源码未启用的浏览、三餐礼包、答题、投资不属于默认任务，本版不执行。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const BASE = 'https://gmdevpro.hlzjppgl.cn';
const TITLE = '海澜之家-游戏';
const dry = process.env.HLZJ_DRY_RUN === '1';
const power = process.env.HLZJ_USE_POWER === '1';
const accounts = (process.env.HLZJ_UNID || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const limit = Number(process.env.HLZJ_POWER_LIMIT || '20');
const started = Date.now();
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const results = [];
function log(s) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${s}`); }
function safeIdentity(value) {
  let s = String(value);
  for (const credential of accounts) s = s.split(credential).join('[凭据已隐藏]');
  return s.replace(/[\r\n\x00-\x1f\x7f]/g, ' ').replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function fail(message) { const e = new Error(message); e.safe = true; throw e; }
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function request(ctx, endpoint, payload = {}) {
  if (dry) fail('预演禁止网络请求');
  const nonce = crypto.randomBytes(15).toString('hex');
  const timestamp = String(Date.now());
  const sign = crypto.createHash('md5').update(`ff${nonce}nn${timestamp}${ctx.userId || ''}mm`).digest('hex');
  const body = JSON.stringify({ ...payload, nonce, timestamp, sign });
  const headers = { 'Content-Type': 'application/json', Accept: 'application/json', Origin: BASE,
    'User-Agent': 'Mozilla/5.0', Referer: `${BASE}/?token=${encodeURIComponent(ctx.union)}&timestamp=${timestamp}`,
    'Content-Length': Buffer.byteLength(body) };
  if (ctx.token) headers.Authorization = `Bearer ${ctx.token}`;
  return new Promise((resolve, reject) => {
    const error = message => { const e = new Error(message); e.safe = true; return e; };
    const req = https.request(BASE + '/server/api/' + endpoint, { method: 'POST', headers }, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => { size += chunk.length; if (size > 1048576) req.destroy(error('响应超过大小限制')); else chunks.push(chunk); });
      res.on('error', () => reject(error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(error(`HTTP 请求失败（${res.statusCode}）`));
        try { const obj = JSON.parse(Buffer.concat(chunks).toString('utf8')); if (!obj || typeof obj !== 'object') throw new Error(); resolve(obj); }
        catch { reject(error('响应不是有效 JSON 对象')); }
      });
    });
    const timer = setTimeout(() => req.destroy(error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', e => reject(e.safe ? e : error('网络请求失败')));
    req.end(body);
  });
}
function verified(r) {
  if (r.code !== 200) fail('业务接口未确认成功');
  if (!r.data || typeof r.data !== 'object') fail('业务响应缺少数据');
  return r.data;
}
function number(n) { if (typeof n !== 'number' || !Number.isFinite(n) || n < 0) fail('业务数值字段无效'); return n; }
async function login(ctx) {
  const d = verified(await request(ctx, 'authorized-login', { union_id: ctx.union, invite_user_id: '' }));
  if (typeof d.token !== 'string' || !d.token || !d.user_info || !d.user_info.id) fail('登录响应缺少必要身份字段');
  ctx.token = d.token; ctx.userId = d.user_info.id; ctx.treeId = d.user_info.tree_id;
  for (const key of ['nick_name', 'user_no']) if (d.user_info[key] != null) log(`账号身份 ${key}：${safeIdentity(d.user_info[key])}`);
}
async function consume(ctx) {
  if (!ctx.treeId) fail('缺少游戏轮次标识');
  let refreshes = 0;
  for (let i = 0; i < limit; i++) {
    const r = await request(ctx, 'game/use-power', { num: 1, user_tree_id: ctx.treeId });
    if (r.code === 309) {
      if (++refreshes > 2) fail('轮次切换超过安全上限');
      await login(ctx); if (!ctx.treeId) fail('刷新轮次失败');
      log('当前轮次已结束，重新获取轮次');
    } else {
      const d = verified(r);
      const energy = number(d.info?.sy_water), remaining = number(d.user_tree?.send_water);
      log(`加入电力成功；当前电力 ${energy}，剩余次数 ${remaining}`);
      if (remaining === 0) return;
    }
    await sleep(1500);
  }
  fail('已达电力请求上限，未确认全部完成');
}
async function runAccount(union, index) {
  const begin = Date.now(); const stats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  const ctx = { union }; let authenticated = false, consumed = false;
  async function stage(n, title, action, enabled = true) {
    const t = Date.now(); stats.total++; log(`账号 ${index} · 阶段 ${n} ${title} 开始`);
    try {
      if (!enabled || dry) { stats.skipped++; log(`⏭️ ${dry ? '断网预演：检查阶段（不执行）' : '跳过'} ${title}`); return false; }
      const state = await action(); stats[state === 'already' ? 'alreadyComplete' : 'success']++;
      log(`${state === 'already' ? '☑️ 已完成' : '✅ 成功'} ${title}`); return true;
    } catch (e) { stats.failed++; log(`❌ ${title}：${e.safe ? e.message : '响应处理失败（详情已隐藏）'}`); return false; }
    finally { log(`阶段 ${n} 耗时 ${Date.now() - t}ms`); }
  }
  authenticated = await stage(1, '登录', () => login(ctx));
  await stage(2, '领取每日电力', async () => {
    const d = verified(await request(ctx, 'user/get-today-water'));
    log(`今日领取 ${number(d.get_water)}，明日可领 ${number(d.tomorrow_get_water_num)} 电力`);
  }, authenticated);
  await stage(3, '每日签到', async () => {
    const d = verified(await request(ctx, 'day-list'));
    if ([true, 1].includes(d.day_sign_status)) return 'already';
    if (![false, 0].includes(d.day_sign_status)) fail('签到状态字段无效');
    const s = verified(await request(ctx, 'day-sign'));
    log(`签到奖励 ${number(s.water_num)} 电力，连续 ${number(s.day_sign_list?.day_num)} 天`);
  }, authenticated);
  consumed = await stage(4, '加入电力', () => consume(ctx), authenticated && power);
  await stage(5, '领取宝箱', async () => {
    const d = verified(await request(ctx, 'game/receive-box')); log(`宝箱奖励 ${number(d.add_water)} 电力`);
  }, consumed && power);
  for (const k of Object.keys(totals)) totals[k] += stats[k];
  const result = { account: index, status: dry ? 'dry-run' : stats.failed ? 'failed' : 'success', ...stats, durationMs: Date.now() - begin };
  results.push(result);
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${result.durationMs}ms`);
}
async function notify(summary) {
  if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  if (dry) { log('通知预览：' + summary); return '断网预演仅预览'; }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(d => path.join(d, 'sendNotify.js')).find(p => fs.existsSync(p));
  if (!file) return '通知模块不可用';
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', file, TITLE, summary], { stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('通知超时'); }, 20000);
    child.on('error', () => { clearTimeout(timer); resolve('通知失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '通知失败'); });
  });
}
async function main() {
  log(`===== ${TITLE} =====`); log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式运行'}；账号数：${accounts.length}`);
  let configurationError = false;
  if (!accounts.length || accounts.some(x => /[&@\s]/.test(x)) || !Number.isInteger(limit) || limit < 1 || limit > 100 ||
      !['0', '1'].includes(process.env.HLZJ_DRY_RUN || '0') || !['0', '1'].includes(process.env.HLZJ_USE_POWER || '0')) {
    configurationError = true; log('❌ 配置错误：请检查 HLZJ_UNID 每行一个凭据、模式开关及电力次数上限');
  } else { for (let i = 0; i < accounts.length; i++) await runAccount(accounts[i], i + 1); }
  const failed = results.filter(x => x.status === 'failed').length;
  const success = results.filter(x => x.status === 'success').length;
  const status = configurationError ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  process.exitCode = configurationError || failed ? 1 : 0;
  const summary = `账号总数 ${accounts.length}，成功 ${success}，失败 ${configurationError ? accounts.length : failed}，预演 ${dry && !configurationError ? accounts.length : 0}；最终状态 ${status}`;
  let notification; try { notification = await notify(summary); } catch { notification = '通知失败'; }
  log('--------------------------------'); log(summary);
  log(`子任务统计：总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`总耗时 ${Date.now() - started}ms；完成时间 ${new Date().toISOString()}；通知状态 ${notification}`);
  if (status === 'dry-run') log('DRY_RUN_OK');
  if (status === 'success') log('HLZJ_SUCCESS');
  console.log('TASK_SUMMARY=' + JSON.stringify({ status, accounts: accounts.length, success, failed, configurationError, tasks: totals, results, notification, durationMs: Date.now() - started }));
}
main().catch(() => { process.exitCode = 1; console.error('任务异常终止（详情已隐藏）'); });
