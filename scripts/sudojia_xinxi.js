// name: 心喜签到
// cron: 20 1 * * *
/**
 * name: 心喜签到
 * cron: 43 12 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 基于 sudojia/AutoTaskScript src/wx_mini/sudojia_xinxi.js
 * 作者 Telegram@sudojia · https://blog.imzjw.cn · 2024/07/21
 * 上游提交 4a55327baed0321bdf95802a75cc8363cae118b0；维护版保留 GPL-3.0。
 * 合并参考 Rookie-wb-WH/ql_scripts xinxi.py，作者 清风（MIT）。
 * 原来源 cron: 15 5 * * *；兼容每日运行，保留维护目标 cron: 43 12 * * *。
 * 原来源更新记录：20224-09-03 修复抽奖问题；2024-09-18 修复问题,增加BUG。
 * Node.js >=18，无第三方业务依赖。
 * XINXI_TOKEN 未设置时兼容 xx_sso，仍为每行一个账号，禁止旧 # 分隔。
 * XINXI_DAILY_TASKS=1 查询每日任务；XINXI_MEMBER_BENEFITS=1 查看会员权益领取奖励。
 * xx_del_topic=1 不再执行批量删帖，报配置错误，避免删除既有内容。
 * 在心喜微信小程序登录，使用自己的抓包工具查看 api.xinc818.com
 * 请求头 sso，将完整值填入 XINXI_TOKEN，每个非空行一个账号。
 * XINXI_DRY_RUN=1 完全断网预演；XINXI_FREE_DRAW=1 启用一次免费抽奖；
 * XINXI_REWARD_TASKS=1 启用分享任务记账及商城浏览奖励（各最多两次）。
 * 随机想要商品、点赞帖子、关注和取关已移除，避免改变个人偏好和社交关系。
 * QINGLONG_NOTIFY 默认开启；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const started = Date.now();
const dry = process.env.XINXI_DRY_RUN === '1';
const credentialInput = process.env.XINXI_TOKEN !== undefined ? process.env.XINXI_TOKEN : (process.env.xx_sso || '');
const accounts = credentialInput.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
const results = [];
let configError = false;
const stamp = () => new Date().toTimeString().slice(0, 8);
const log = text => console.log(`[${stamp()}] ${text}`);
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
function validNumber(n) { return typeof n === 'number' && Number.isFinite(n) && n >= 0; }
function expect(ok) { if (!ok) throw new Error('响应字段不符合已知接口，未确认成功'); }
function request(token, route, method = 'GET', body) {
  if (dry) throw new Error('预演模式禁止业务网络请求');
  return new Promise((resolve, reject) => {
    let settled = false;
    const payload = body === undefined ? undefined : JSON.stringify(body);
    const finish = (error, value) => { if (settled) return; settled = true; clearTimeout(timer); error ? reject(error) : resolve(value); };
    const req = https.request(new URL(route, 'https://api.xinc818.com'), {
      method, headers: { sso: token, 'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json', Accept: 'application/json', Referer: 'https://servicewechat.com/wx673f827a4c2c94fa/276/page-frame.html', ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}) }
    }, res => {
      const chunks = []; let size = 0;
      res.on('data', chunk => { size += chunk.length; if (size > 1048576) { finish(new Error('响应超过大小限制')); res.destroy(); req.destroy(); } else chunks.push(chunk); });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode !== 200) return finish(new Error(`HTTP 状态异常：${res.statusCode}`));
        try {
          const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!value || value.code !== 0) return finish(new Error(value && value.code === 40001 ? '登录凭据已失效' : '业务接口拒绝请求，未确认成功'));
          finish(null, value.data);
        } catch { finish(new Error('响应不是有效 JSON')); }
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超时')); req.destroy(); }, 15000);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(payload);
  });
}
async function runAccount(token, index) {
  const begin = Date.now();
  const stats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
  let stage = 0; let user;
  async function step(name, action, disabled = false, local = false) {
    const t = Date.now(); ++stage; ++stats.total;
    log(`账号 ${index} · 阶段 ${stage} ${name} 开始`);
    let state = 'success';
    try {
      if (disabled) { state = 'skipped'; log('⏭️ 未启用或前置步骤失败'); }
      else if (dry && !local) { state = 'skipped'; log('⏭️ DRY_RUN_OK：已校验执行计划，不请求、不修改账号'); }
      else { const outcome = await action(); if (outcome) state = outcome; }
    } catch (e) { state = 'failure'; log(`❌ ${e.message}`); }
    ++stats[state];
    log(`账号 ${index} · 阶段 ${stage} ${name} ${state}，耗时 ${Date.now() - t}ms`);
    if (!dry && !disabled) await wait(1500);
    return state;
  }
  await step('凭据格式校验', async () => { expect(!/[#\s\x00-\x1f\x7f]/.test(token)); log('✅ 凭据格式通过'); }, false, true);
  await step('查询账号身份', async () => {
    user = await request(token, '/mini/user');
    expect(user && validNumber(user.integral));
    if (typeof user.nickname === 'string' && user.nickname) console.log(`[${stamp()}] 账号 ${index} 昵称：${JSON.stringify(user.nickname)}`);
    log(`✅ 当前喜点：${user.integral}`);
    if (validNumber(user.historyIntegral)) log(`✅ 历史喜点：${user.historyIntegral}`);
  }, stats.failure > 0);
  const unavailable = stats.failure > 0 || (!dry && !user);
  await step('查询每日任务', async () => {
    const d = await request(token, '/mini/dailyTask/daily');
    expect(d !== null && typeof d === 'object');
    log(Array.isArray(d) ? `✅ 每日任务查询成功，返回 ${d.length} 项任务` : '✅ 每日任务查询成功');
  }, unavailable || process.env.XINXI_DAILY_TASKS !== '1');
  await step('查看会员权益奖励', async () => {
    const d = await request(token, '/mini/dailyTask/benefits/2');
    if (d === null || d === false) { log('☑️ 会员权益任务已完成'); return 'alreadyComplete'; }
    expect(d && validNumber(d.singleReward));
    log(`✅ 查看会员权益成功，奖励 ${d.singleReward} 喜点`);
  }, unavailable || process.env.XINXI_MEMBER_BENEFITS !== '1');
  await step('每日签到', async () => {
    const d = await request(token, '/mini/sign/in?dailyTaskId=');
    expect(d && validNumber(d.integral));
    if (d.integral === 0) { log('☑️ 今日已签到'); return 'alreadyComplete'; }
    expect(validNumber(d.continuousDay));
    log(`✅ 签到成功！喜点+${d.integral}，连续签到 ${d.continuousDay} 天`);
  }, unavailable);
  await step('免费抽奖', async () => {
    const count = await request(token, '/mini/lottery/71/freeNum');
    expect(Number.isSafeInteger(count) && count >= 0);
    log(`免费抽奖次数：${count}`);
    if (count === 0) { log('☑️ 免费次数已用完'); return 'alreadyComplete'; }
    expect(user.id !== null && user.id !== undefined && String(user.id).trim() !== '' && Number.isSafeInteger(Number(user.id)) && Number(user.id) > 0);
    await wait(1500);
    const d = await request(token, '/mini/lottery/draw', 'POST', { activityId: 71, batch: false, isIntegral: false, userId: Number(user.id), dailyTaskId: 9 });
    expect(d && d.taskResult && validNumber(d.taskResult.singleReward) && Array.isArray(d.lotteryResult) && d.lotteryResult.length > 0);
    log(`✅ 免费抽奖成功，任务奖励 ${d.taskResult.singleReward} 喜点`);
  }, unavailable || process.env.XINXI_FREE_DRAW !== '1');
  for (const [name, route] of [['分享任务', '/mini/dailyTask/share'], ['商城浏览任务', '/mini/dailyTask/browseGoods/22']]) {
    await step(name, async () => {
      for (let i = 0; i < 2; i++) {
        if (name === '商城浏览任务') { log('等待 30 秒后提交浏览任务'); await wait(30000); }
        const d = await request(token, route);
        if (d === null || d === false) { log('☑️ 本周任务已完成'); return i === 0 ? 'alreadyComplete' : 'success'; }
        expect(d && validNumber(d.singleReward) && typeof d.taskName === 'string');
        log(`✅ ${name}第 ${i + 1} 次成功，奖励 ${d.singleReward} 喜点`);
        await wait(2000);
      }
    }, unavailable || process.env.XINXI_REWARD_TASKS !== '1');
  }
  await step('查询最终喜点', async () => { const d = await request(token, '/mini/user'); expect(d && validNumber(d.integral)); log(`✅ 当前喜点：${d.integral}`); }, unavailable);
  Object.keys(totals).forEach(k => { totals[k] += stats[k]; });
  const result = { account: index, status: stats.failure ? 'failure' : dry ? 'dry-run' : 'success', ...stats, durationMs: Date.now() - begin };
  results.push(result);
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failure}，耗时 ${result.durationMs}ms`);
}
async function notify(summary) {
  if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return 'disabled';
  // 通知插件可能联网，完全断网预演只生成通知预览，不加载或执行插件。
  if (dry) { log(`通知预演：${summary}`); return 'dry-run'; }
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = files.find(p => fs.existsSync(p));
  if (!file) { log('⚠️ 青龙通知模块不可用，保留业务退出码'); return 'unavailable'; }
  return new Promise(resolve => {
    const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))';
    const child = spawn(process.execPath, ['-e', code, file, '心喜签到', summary], { stdio: 'ignore' });
    const timer = setTimeout(() => child.kill('SIGKILL'), 20000);
    child.on('error', () => { clearTimeout(timer); resolve('failed'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? 'sent' : 'failed'); });
  });
}
async function main() {
  log('========== 心喜签到 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${accounts.length}`);
  for (const key of ['XINXI_DRY_RUN', 'XINXI_FREE_DRAW', 'XINXI_REWARD_TASKS', 'XINXI_DAILY_TASKS', 'XINXI_MEMBER_BENEFITS']) {
    if (process.env[key] !== undefined && !['0', '1'].includes(process.env[key])) { configError = true; log(`❌ ${key} 仅支持 0 或 1`); }
  }
  if (process.env.xx_del_topic === '1') { configError = true; log('❌ 不支持旧批量删帖设置 xx_del_topic=1，请移除该设置'); }
  if (credentialInput.includes('#')) { configError = true; log('❌ 不支持旧 # 账号分隔，请改为每行一个账号'); }
  if (!accounts.length) { configError = true; log('❌ 未配置 XINXI_TOKEN，请每行填写一个账号的 sso'); }
  if (!configError) for (let i = 0; i < accounts.length; i++) await runAccount(accounts[i], i + 1);
  const failed = configError ? accounts.length : results.filter(r => r.status === 'failure').length;
  const success = results.filter(r => r.status === 'success').length;
  const status = configError ? 'configuration-error' : failed ? (failed === accounts.length ? 'failure' : 'partial-failure') : dry ? 'dry-run' : 'success';
  const summary = `状态：${status}；账号总数 ${accounts.length}，成功 ${success}，失败 ${failed}，预演 ${results.filter(r => r.status === 'dry-run').length}；子任务成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failure}`;
  let notification;
  try { notification = await notify(summary); } catch { notification = 'failed'; }
  if (notification === 'failed') log('⚠️ 青龙通知发送失败，保留业务退出码');
  log('--------------------------------'); log(summary);
  log(`完成时间：${new Date().toISOString()}；总耗时：${Date.now() - started}ms；通知状态：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ status, accounts: accounts.length, success, failed, tasks: totals, results, notification, durationMs: Date.now() - started }));
  process.exitCode = configError || failed ? 1 : 0;
}
main().catch(() => { log('❌ 未预期的内部错误'); process.exitCode = 1; });
