// name: 安慕希每日签到
// cron: 33 14 * * *
/**
 * name: 安慕希每日签到
 * cron: 33 14 * * *
 * 安慕希小程序 — 独立维护版，Node.js >= 18，无第三方业务依赖。
 * 原作者 Telegram@sudojia · https://blog.imzjw.cn
 * 来源 sudojia/AutoTaskScript src/wx_mini/sudojia_amx.js
 * SPDX-License-Identifier: GPL-3.0-only
 * 使用与分发遵循 GNU GPL v3：https://www.gnu.org/licenses/gpl-3.0.html
 * 登录安慕希小程序，在自己授权的抓包环境中读取
 * msmarket.msx.digitalyili.com 请求头 access-token；填入 AMX_TOKEN。
 * 每个非空行一个完整 Token，不使用 & 或 @ 分隔账号。
 * AMX_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 禁用通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 */
'use strict';
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '安慕希每日签到';
const BASE = 'https://msmarket.msx.digitalyili.com/gateway';
const dry = process.env.AMX_DRY_RUN === '1';
const accounts = (process.env.AMX_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const started = Date.now();
const results = [];
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = s => console.log(`[${stamp()}] ${s}`);
const pause = () => new Promise(r => setTimeout(r, 1500));
function request(token, endpoint, method = 'GET') {
  if (dry) throw new Error('预演禁止网络请求');
  if (/[\x00-\x1f\x7f-\uffff]/.test(token)) throw new Error('Token 请求头格式无效');
  return new Promise((resolve, reject) => {
    const body = method === 'POST' ? '{}' : undefined;
    const req = https.request(BASE + endpoint, {
      method,
      headers: {
        'user-agent': 'Mozilla/5.0', 'referer': 'https://servicewechat.com/wxf2a6206f7e2fd712/780/page-frame.html',
        'content-type': 'application/json', 'xweb_xhr': '1', scene: '1145', oms: 'old',
        accept: '*/*', 'access-token': token,
        ...(body ? { 'content-length': Buffer.byteLength(body) } : {})
      }
    }, res => {
      let bytes = 0; const chunks = [];
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 262144) req.destroy(new Error('响应超过大小限制'));
        else chunks.push(chunk);
      });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error(res.statusCode === 403 ? 'HTTP 403：网关拒绝请求，未确认业务成功' : `HTTP ${res.statusCode}`));
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || data.status !== true) return reject(new Error('业务状态未明确成功，请检查凭据或接口'));
          resolve(data.data);
        } catch { reject(new Error('响应不是有效 JSON')); }
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', err => reject(new Error(err.message === '请求超时' ? '请求超时' : '网络请求失败')));
    req.end(body);
  });
}
function numeric(value) { return (typeof value === 'number' && Number.isFinite(value)) || (typeof value === 'string' && /^\d+(\.\d+)?$/.test(value)); }
async function runAccount(token, index) {
  const at = Date.now();
  const stats = { account: index, total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, durationMs: 0 };
  const stages = [
    ['账号信息', async () => {
      const data = await request(token, '/api/auth/account/user/info');
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('账号信息字段异常');
      if (typeof data.nickName === 'string' && data.nickName) log(`账号 ${index} 昵称：${data.nickName}`);
      return '账号信息查询成功';
    }],
    ['今日签到', async () => {
      const state = await request(token, '/api/member/sign/status');
      if (!state || typeof state.signed !== 'boolean') throw new Error('签到状态字段异常，停止签到');
      if (state.signed) return 'already';
      await pause();
      const signed = await request(token, '/api/member/daily/sign', 'POST');
      await pause();
      const verified = await request(token, '/api/member/sign/status');
      if (!verified || verified.signed !== true) throw new Error('签到后未确认已签到状态');
      const bonus = signed?.dailySign?.bonusPoint;
      return `签到成功${numeric(bonus) ? `，积分+${bonus}` : '，状态已核验'}`;
    }],
    ['积分查询', async () => {
      const points = await request(token, '/api/member/point');
      if (!numeric(points)) throw new Error('积分字段异常');
      return `当前积分：${points}`;
    }]
  ];
  log(`账号 ${index} 开始`);
  for (let n = 0; n < stages.length; n++) {
    const [name, action] = stages[n]; const time = Date.now();
    log(`账号 ${index} · 阶段 ${n + 1}/3 ${name}`);
    try {
      if (/[\x00-\x1f\x7f-\uffff]/.test(token)) throw new Error('Token 请求头格式无效');
      if (dry) { stats.skipped++; log(`⏭️ 预演：已检查阶段配置，不发送请求`); }
      else if (n === 1 && stats.failed) { stats.skipped++; log('⏭️ 账号信息失败，停止签到副作用'); }
      else {
        const result = await action();
        if (result === 'already') { stats.alreadyComplete++; log('☑️ 今日已签到'); }
        else { stats.success++; log(`✅ ${result}`); }
      }
    } catch (err) { stats.failed++; log(`❌ ${err.message}`); }
    log(`账号 ${index} · 阶段 ${n + 1} 耗时 ${Date.now() - time}ms`);
    if (!dry && n < stages.length - 1) await pause();
  }
  stats.durationMs = Date.now() - at;
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs}ms`);
  results.push(stats);
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已禁用';
  // 预演优先保证绝对断网，不执行可能联网的通知模块。
  if (dry) return '预演跳过发送（禁止网络）';
  const paths = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = paths.find(p => fs.existsSync(p));
  if (!file) return '不可用：未找到 sendNotify.js';
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))', file, TITLE, body], { stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('发送超时'); }, 20000);
    child.on('error', () => { clearTimeout(timer); resolve('发送失败'); });
    child.on('exit', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '发送失败'); });
  });
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()} · 模式：${dry ? '断网预演' : '正式运行'} · 账号数：${accounts.length}`);
  const configurationError = !accounts.length;
  if (configurationError) log('❌ 配置错误：AMX_TOKEN 必须每个非空行填写一个有效请求头 Token');
  else for (let i = 0; i < accounts.length; i++) await runAccount(accounts[i], i + 1);
  const failed = configurationError ? accounts.length : results.filter(x => x.failed > 0).length;
  const succeeded = dry ? 0 : results.filter(x => x.failed === 0).length;
  const status = configurationError ? 'configuration-error' : failed ? (succeeded ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const exitCode = configurationError || failed ? 1 : 0;
  const tasks = results.reduce((a, x) => { for (const k of Object.keys(a)) a[k] += x[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  const body = `账号总数 ${accounts.length}，成功 ${succeeded}，失败 ${failed}，预演 ${dry ? results.length : 0}；状态 ${status}；子任务成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '发送失败'; }
  console.log('----------------------------------------');
  log(body);
  log(`总耗时 ${Date.now() - started}ms · 完成时间 ${new Date().toISOString()} · 通知：${notification} · 最终状态：${status}`);
  if (dry && !exitCode) log('DRY_RUN_OK：无网络预演完成');
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, status, mode: dry ? 'dry-run' : 'live', accounts: accounts.length, succeeded, failed, configurationError, tasks, results, notification, durationMs: Date.now() - started, exitCode }));
  process.exitCode = exitCode;
}
main();
