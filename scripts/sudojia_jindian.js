// name: 金典有机生活+
// cron: 18 0 * * *
/**
 * name: 金典有机生活+
 * cron: 56 7 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者 Telegram@sudojia — https://blog.imzjw.cn
 * 来源 sudojia/AutoTaskScript src/wx_mini/sudojia_jindian.js
 * 独立维护版：Node.js >=18，无第三方业务依赖。
 * 微信小程序「金典有机生活+」登录后，在本人授权的抓包环境中读取
 * msmarket.msx.digitalyili.com 请求头 access-token，填入 JINDIAN_TOKEN。
 * 每个非空行一个账号；不使用 & 或 @ 分隔。JINDIAN_DRY_RUN=1 完全断网预演。
 * QINGLONG_NOTIFY=0 关闭通知；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const { spawn } = require('node:child_process');
const BASE = 'https://msmarket.msx.digitalyili.com';
const dry = process.env.JINDIAN_DRY_RUN === '1';
const title = '金典有机生活+';
const now = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = s => console.log(`[${now()}] ${s}`);

// 通知隔离进程：超时或模块异常不会改变业务结果；预演强制禁止网络。
async function notificationWorker() {
  if (dry) {
    const deny = () => { throw new Error('预演禁止网络'); };
    for (const name of ['node:http', 'node:https']) {
      const mod = require(name); mod.request = deny; mod.get = deny;
    }
    const net = require('node:net'); net.connect = deny; net.createConnection = deny;
    net.Socket.prototype.connect = deny;
    require('node:tls').connect = deny;
    require('node:dgram').createSocket = deny;
    globalThis.fetch = deny;
    const cp = require('node:child_process');
    for (const k of ['spawn','exec','execFile','fork','spawnSync','execSync','execFileSync']) cp[k] = deny;
  }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  for (const dir of dirs) {
    let file;
    try { file = require.resolve(path.join(dir, 'sendNotify.js')); } catch { continue; }
    try {
      const mod = require(file);
      if (typeof mod.sendNotify !== 'function') continue;
      await mod.sendNotify(title, process.env.JINDIAN_NOTIFICATION_SUMMARY);
      return;
    } catch { process.exitCode = 1; return; }
  }
  process.exitCode = 1;
}
function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return Promise.resolve('已关闭');
  return new Promise(resolve => {
    const child = spawn(process.execPath, [__filename, '--notification-worker'], {
      env: { ...process.env, JINDIAN_NOTIFICATION_SUMMARY: body }, stdio: 'ignore'
    });
    const timer = setTimeout(() => { child.kill('SIGKILL'); }, 12000);
    child.once('error', () => { clearTimeout(timer); resolve('不可用'); });
    child.once('close', code => { clearTimeout(timer); resolve(code === 0 ? '已调用通知模块' : (dry ? '预演通知不可用或网络发送已阻止' : '通知不可用或失败')); });
  });
}
function request(token, endpoint, method = 'GET') {
  if (dry) throw new Error('预演禁止业务网络');
  return new Promise((resolve, reject) => {
    const body = method === 'POST' ? '{}' : undefined;
    const req = https.request(BASE + endpoint, { method, headers: {
      'access-token': token, 'Content-Type': 'application/json', Accept: '*/*',
      'User-Agent': 'Mozilla/5.0',
      Referer: 'https://servicewechat.com/wxf32616183fb4511e/616/page-frame.html',
      ...(body ? { 'Content-Length': Buffer.byteLength(body) } : {})
    } }, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1048576) { res.destroy(); reject(new Error('响应过大')); }
        else chunks.push(chunk);
      });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP ${res.statusCode}`));
        let data;
        try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch { return reject(new Error('响应不是有效 JSON')); }
        if (!data || data.status !== true) return reject(new Error('业务未明确成功，请检查凭据或接口契约'));
        resolve(data.data);
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('请求失败或超时')));
    req.end(body);
  });
}
const numeric = v => (typeof v === 'number' && Number.isFinite(v) && v >= 0) || (typeof v === 'string' && /^\d+(\.\d+)?$/.test(v));
async function main() {
  const start = Date.now();
  const tokens = (process.env.JINDIAN_TOKEN || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const results = [];
  log(`========== ${title} ==========`);
  log(`开始时间：${new Date().toISOString()}；模式：${dry ? '断网预演' : '正式运行'}；账号数：${tokens.length}`);
  let configurationError = tokens.length === 0;
  if (configurationError) log('❌ 配置错误：请设置 JINDIAN_TOKEN，每行一个账号');
  for (let i = 0; i < tokens.length; i++) {
    const began = Date.now();
    const stat = { account: i + 1, total: 4, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let stage = 0;
    const step = async (name, fn) => {
      stage++; const at = Date.now(); log(`账号 ${i + 1} 阶段 ${stage}/4：${name}`);
      try { const result = await fn(); log(`✅ 账号 ${i + 1} 阶段 ${stage} 完成，耗时 ${Date.now() - at}ms`); return result; }
      catch (e) { log(`❌ 账号 ${i + 1} 阶段 ${stage}：${e.message}；耗时 ${Date.now() - at}ms`); throw e; }
    };
    try {
      if (/[\x00-\x20\x7f-\uffff]/.test(tokens[i])) throw new Error('凭据格式无效：应仅填写 access-token 的值');
      if (dry) {
        for (const name of ['查询账号身份', '检查签到状态', '未签到时执行签到并复查', '查询积分']) {
          await step(name, async () => { log('⏭️ 断网预演：仅验证执行计划，未发出请求或修改账号'); stat.skipped++; });
        }
      } else {
        await step('查询账号身份', async () => {
          const data = await request(tokens[i], '/gateway/api/auth/account/user/info');
          if (!data || typeof data !== 'object') throw new Error('账号信息结构无效');
          for (const key of ['nickName', 'username', 'displayName', 'uid']) {
            const value = data[key];
            if ((typeof value === 'string' || typeof value === 'number') && String(value) !== tokens[i]) log(`账号 ${i + 1} ${key}：${JSON.stringify(value)}`);
          }
          stat.success++;
        });
        const signed = await step('检查签到状态', async () => {
          const data = await request(tokens[i], '/gateway/api/member/sign/status');
          if (!data || typeof data.signed !== 'boolean') throw new Error('签到状态字段无效，停止写入');
          stat.success++; return data.signed;
        });
        await step('每日签到', async () => {
          if (signed) { stat.alreadyComplete++; log('☑️ 今日已签到，请勿重复签到'); return; }
          const data = await request(tokens[i], '/gateway/api/member/daily/sign', 'POST');
          if (!data || !data.dailySign || !numeric(data.dailySign.bonusPoint)) throw new Error('签到奖励字段无效，不自动重试');
          const check = await request(tokens[i], '/gateway/api/member/sign/status');
          if (!check || check.signed !== true) throw new Error('签到后状态未确认，不自动重试');
          log(`签到成功，积分+${data.dailySign.bonusPoint}`); stat.success++;
        });
        await step('查询积分', async () => {
          const points = await request(tokens[i], '/gateway/api/member/point');
          if (!numeric(points)) throw new Error('积分字段无效');
          log(`当前积分：${points}`); stat.success++;
        });
      }
    } catch (e) {
      stat.failed++; stat.skipped = stat.total - stat.success - stat.alreadyComplete - stat.failed;
      if (stage === 0) log(`❌ 账号 ${i + 1}：${e.message}`);
    }
    stat.durationMs = Date.now() - began; results.push(stat);
    log(`账号 ${i + 1} 统计：总任务 ${stat.total}，成功 ${stat.success}，已完成 ${stat.alreadyComplete}，跳过 ${stat.skipped}，失败 ${stat.failed}；耗时 ${stat.durationMs}ms`);
  }
  const failed = results.filter(r => r.failed).length;
  const success = dry ? 0 : results.length - failed;
  const status = configurationError ? 'configuration-error' : failed ? (failed === results.length ? 'failure' : 'partial-failure') : dry ? 'dry-run' : 'success';
  process.exitCode = configurationError || failed ? 1 : 0;
  const body = `模式：${dry ? '断网预演' : '正式运行'}；账号总数：${tokens.length}，成功：${success}，失败：${failed}，预演：${dry ? results.length - failed : 0}；最终状态：${status}`;
  const notification = await notify(body);
  const totals = results.reduce((a, r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  log('----------------------------------------'); log(body);
  log(`子任务统计：总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`通知状态：${notification}；总耗时：${Date.now() - start}ms；完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: title, mode: dry ? 'dry-run' : 'live', status, accounts: tokens.length, success, failed, configurationError, totals, results, notification, durationMs: Date.now() - start }));
}
if (process.argv.includes('--notification-worker')) notificationWorker().catch(() => { process.exitCode = 1; });
else main().catch(() => { console.error('任务发生内部错误'); process.exitCode = 1; });
