// name: 嘉立创每日签到
// cron: 30 6 * * *
/**
 * name: 嘉立创每日签到
 * cron: 30 6 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia，https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/web/sudojia_jlc.js
 * 在嘉立创下单助手或 https://m.jlc.com/mapp/ 登录，
 * 抓取 m.jlc.com 请求头 x-jlc-accesstoken 和 secretkey。
 * JLC_TOKEN：每行一个账号，格式为 x-jlc-accesstoken#secretkey；仅按首个 # 分割。
 * JLC_CLAIM_REWARD=1 才允许领取默认奖励；默认不替用户作出奖励选择。
 * JLC_DRY_RUN=1：完全断网预演（通知仅本地模拟）。Node.js >=18，无外部依赖。
 */
'use strict';
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const dry = process.env.JLC_DRY_RUN === '1';
const title = '嘉立创每日签到';
const start = Date.now();
const lines = (process.env.JLC_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const log = text => console.log(`[${new Date().toTimeString().slice(0, 8)}] ${text}`);
const results = [];
function fail(message) { throw new Error(message); }
function request(route, credentials) {
  if (dry) return Promise.reject(new Error('预演禁止网络请求'));
  return new Promise((resolve, reject) => {
    const req = https.get({ hostname: 'm.jlc.com', path: route, headers: {
      'User-Agent': 'Mozilla/5.0', 'x-jlc-clienttype': 'WEB',
      Accept: 'application/json, text/plain, */*',
      Referer: 'https://m.jlc.com/mapp/pages/my/index',
      'x-jlc-accesstoken': credentials.token, secretkey: credentials.key
    } }, res => {
      let body = ''; let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) req.destroy(new Error('响应过大'));
        else body += chunk;
      });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP 状态 ${res.statusCode}`));
        try {
          const parsed = JSON.parse(body);
          if (parsed.success !== true) return reject(new Error('业务未确认成功，请检查凭据或官方页面'));
          resolve(parsed.data);
        } catch { reject(new Error('响应不是有效 JSON')); }
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('请求失败或超时（详情已脱敏）')));
  });
}
const routes = {
  user: '/api/appPlatform/center/setting/selectPersonalInfo',
  config: '/api/activity/sign/getCurrentUserSignInConfig',
  sign: '/api/activity/sign/signIn?source=4',
  reward: '/api/activity/sign/receiveVoucher',
  points: '/api/activity/front/getCustomerIntegral'
};
function signState(data) {
  if (!data || typeof data.haveSignIn !== 'boolean') fail('签到状态字段异常');
  return data.haveSignIn;
}
async function account(line, index) {
  const began = Date.now();
  const stat = { account: index, total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  const split = line.indexOf('#');
  const credentials = { token: line.slice(0, split), key: line.slice(split + 1) };
  const valid = split > 0 && credentials.key.length > 0 && !/[\x00-\x20\x7f]/.test(credentials.token + credentials.key);
  let authenticated = false;
  async function stage(n, name, fn) {
    const beganStage = Date.now();
    log(`账号 ${index} 阶段 ${n}/3 ${name}`);
    try {
      const state = await fn();
      stat[state || 'success']++;
      log(`账号 ${index} ${name}：${state === 'alreadyComplete' ? '☑️ 已完成' : state === 'skipped' ? '⏭️ 跳过' : '✅ 成功'}，耗时 ${Date.now() - beganStage}ms`);
    } catch (e) { stat.failed++; log(`账号 ${index} ${name}：❌ ${e.message}，耗时 ${Date.now() - beganStage}ms`); }
  }
  await stage(1, '凭据与账号身份', async () => {
    if (!valid) fail('JLC_TOKEN 格式错误，应为每行一组令牌#密钥');
    if (dry) { log('凭据结构有效；模拟身份查询，不请求接口'); authenticated = true; return 'skipped'; }
    const data = await request(routes.user, credentials);
    if (!data || !['string', 'number'].includes(typeof data.customerCode)) fail('账号身份字段缺失');
    // customerCode 是上游公开账号身份字段；JSON 编码防止控制字符破坏日志。
    const identity = String(data.customerCode);
    if (identity.includes(credentials.token) || identity.includes(credentials.key)) {
      log(`账号 ${index}：身份字段疑似敏感值，已省略`);
    } else log(`账号身份：${JSON.stringify(identity)}`);
    authenticated = true;
  });
  await stage(2, '签到与奖励', async () => {
    if (!authenticated) return 'skipped';
    if (dry) { log(`模拟检查签到、签到及复查；奖励领取${process.env.JLC_CLAIM_REWARD === '1' ? '已授权' : '未授权'}，不执行变更`); return 'skipped'; }
    if (signState(await request(routes.config, credentials))) return 'alreadyComplete';
    const data = await request(routes.sign, credentials);
    if (!data || typeof data !== 'object') fail('签到响应字段异常');
    if (!data.gainNum) {
      if (process.env.JLC_CLAIM_REWARD !== '1') fail('有奖励待选择，请在官方页面领取，或明确设置 JLC_CLAIM_REWARD=1；未自动选择');
      await request(routes.reward, credentials);
      log('✅ 奖励接口确认领取成功');
      // 至多重试一次，避免上游递归领取与签到。
      await request(routes.sign, credentials);
    } else if (!Number.isFinite(Number(data.gainNum)) || Number(data.gainNum) < 0) fail('签到奖励字段异常');
    if (!signState(await request(routes.config, credentials))) fail('复查未确认今日签到完成');
    log('✅ 签到成功，已复查官方签到状态');
  });
  await stage(3, '金豆余额', async () => {
    if (!authenticated) return 'skipped';
    if (dry) { log('模拟金豆查询，不请求接口'); return 'skipped'; }
    const data = await request(routes.points, credentials);
    if (!data || !['number', 'string'].includes(typeof data.integralVoucher) || !/^\d+(\.\d+)?$/.test(String(data.integralVoucher))) fail('金豆余额字段异常');
    log(`当前金豆：${data.integralVoucher}`);
  });
  stat.status = stat.failed ? 'failure' : dry ? 'dry-run' : 'success';
  stat.durationMs = Date.now() - began;
  log(`账号 ${index} 统计：总任务 ${stat.total}，成功 ${stat.success}，已完成 ${stat.alreadyComplete}，跳过 ${stat.skipped}，失败 ${stat.failed}，耗时 ${stat.durationMs}ms`);
  results.push(stat);
}
async function notify(body) {
  if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return 'disabled';
  if (dry) { log(`预演通知（本地模拟，禁止联网）：${body}`); return 'dry-run'; }
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const modulePath = candidates.find(p => fs.existsSync(p));
  if (!modulePath) return 'unavailable';
  return new Promise(resolve => {
    // 隔离通知异常及其输出，避免泄漏推送配置；超时不改变业务退出码。
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', modulePath, title, body], { stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('timeout'); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve('failed'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? 'sent' : 'failed'); });
  });
}
async function main() {
  log(`========== ${title} ==========`);
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${lines.length}`);
  let configError = !lines.length;
  if (!lines.length) log('❌ 配置错误：请设置 JLC_TOKEN，每行一个账号');
  if (process.env.JLC_CLAIM_REWARD && !['0', '1'].includes(process.env.JLC_CLAIM_REWARD)) { configError = true; log('❌ 配置错误：JLC_CLAIM_REWARD 仅允许 0 或 1'); }
  if (!configError) for (let i = 0; i < lines.length; i++) await account(lines[i], i + 1);
  const failed = results.filter(x => x.failed).length;
  const success = results.filter(x => x.status === 'success').length;
  const status = configError ? 'configuration-error' : failed ? (failed === lines.length ? 'failure' : 'partial-failure') : dry ? 'dry-run' : 'success';
  const exitCode = configError || failed ? 1 : 0;
  const summary = { status, mode: dry ? 'dry-run' : 'live', accounts: lines.length, success, failed, dryRun: results.filter(x => x.status === 'dry-run').length, configurationError: configError, results, exitCode };
  const body = `状态：${status}；账号总数：${lines.length}，成功：${success}，失败：${failed}，预演：${summary.dryRun}，配置错误：${configError ? '是' : '否'}`;
  summary.notification = await notify(body);
  log('----------------------------------------');
  log(body);
  const totals = results.reduce((a, r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  log(`子任务统计：${JSON.stringify(totals)}`);
  summary.durationMs = Date.now() - start;
  log(`完成时间：${new Date().toISOString()}；总耗时：${summary.durationMs}ms；通知：${summary.notification}；最终状态：${status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = exitCode;
}
main();
