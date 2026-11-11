// name: FL 自动登录签到
// cron: 52 10 * * *
/**
 * name: FL 自动登录签到
 * cron: 0 9 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 上游：xpsu/fl-checkin，checkin.ts
 * https://github.com/xpsu/fl-checkin/tree/f2256b8f8c864722831e6bff88f1ee607b2ba7da
 * 原始说明：优雅的自动登录+签到脚本 (TypeScript 版)
 * 原始运行说明：npm start (需要 Node.js 24+)；维护版使用 Node.js 18+ 直接运行。
 * FL_ACCOUNTS：每行 邮箱|密码，仅按第一个 | 分割，密码中的后续 | 原样保留。
 * 在 https://flzt.org 注册或使用现有登录邮箱和密码，无需抓包。
 * 兼容 USER_EMAIL / USER_PASSWORD，同为多行时按行配对；优先 FL_ACCOUNTS。
 * FL_DRY_RUN=1 完全断网预演（包括通知）；QINGLONG_NOTIFY=0 关闭通知。
 * PUSHPLUS_TOKEN：可选，在 PushPlus 官网个人中心获取，仅用于脱敏签到结果推送。
 * 原源码未提供 cron；此处建议每天 09:00，青龙中可调整。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  const raw = process.env.QINGLONG_NOTIFY;
  if (raw !== undefined && String(raw).trim() !== '' && String(raw).trim().toLowerCase() !== 'auto') return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["669a029282a2f49e", "scripts/fl.js", "fl.js", "fl"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const path = require('node:path');
const fs = require('node:fs');
const { execFile } = require('node:child_process');
const TITLE = 'FL 自动登录签到';
const CATALOG = '669a029282a2f49e';
const BASE = 'https://flzt.org';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.7727.117 Safari/537.36';
const dry = process.env.FL_DRY_RUN === '1';
const started = Date.now();
const log = text => console.log(`[${new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}] ${text}`);
const lines = value => (value || '').split(/\r?\n/).filter(x => x.trim() !== '');
const stats = () => ({ total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });

function accounts() {
  if (process.env.FL_ACCOUNTS !== undefined) {
    return lines(process.env.FL_ACCOUNTS).map(line => {
      const pos = line.indexOf('|');
      return pos < 1 ? { invalid: true } : { email: line.slice(0, pos).trim(), password: line.slice(pos + 1) };
    });
  }
  const emails = lines(process.env.USER_EMAIL);
  const passwords = lines(process.env.USER_PASSWORD);
  return Array.from({ length: Math.max(emails.length, passwords.length) }, (_, i) => ({ email: emails[i]?.trim(), password: passwords[i] }));
}

// 独立实现 HTTP；超时涵盖响应体，限制体积，禁止携带凭据跟随重定向。
async function request(url, options, retries = 0) {
  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const res = await fetch(url, { ...options, redirect: 'error', signal: controller.signal });
      if ((res.status === 429 || res.status >= 500) && attempt < retries) {
        await res.body?.cancel();
        log('⚠️ 登录暂时不可用，进行一次重试');
        continue;
      }
      if (res.status >= 500 || res.status === 429) throw new Error(`HTTP ${res.status}`);
      let size = 0;
      const chunks = [];
      for await (const chunk of res.body || []) {
        size += chunk.length;
        if (size > 262144) { controller.abort(); throw new Error('响应体超出限制'); }
        chunks.push(Buffer.from(chunk));
      }
      let json;
      try { json = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
      catch { throw new Error('接口响应不是有效 JSON'); }
      if (!json || typeof json !== 'object' || Array.isArray(json)) throw new Error('接口响应结构无效');
      return { ok: res.ok, status: res.status, json };
    } catch (error) {
      if (attempt < retries) { log('⚠️ 登录请求异常，进行一次重试'); continue; }
      // 不传播网络库异常、响应或请求参数，避免意外回显凭据。
      if (controller.signal.aborted) throw new Error('请求超时或响应体超限');
      if (/^(HTTP \d{3}|响应体超出限制|接口响应不是有效 JSON|接口响应结构无效)$/.test(error.message)) throw error;
      throw new Error('网络请求失败');
    } finally { clearTimeout(timer); }
  }
}

function identity(data, account, token = '') {
  if (!data || typeof data !== 'object') return;
  const item = ['nickname', 'username', 'display_name', 'public_uid', 'uid'].find(key => typeof data[key] === 'string' || typeof data[key] === 'number');
  if (!item) return;
  const value = String(data[item]);
  // 不输出手机号、邮箱、设备标识或凭据；非敏感官方身份按原值展示。
  if (value.includes('@') || /(?:\+?86[- ]?)?1[3-9]\d{9}/.test(value) || /[\r\n\x00-\x1f]/.test(value) ||
      [account.email, account.password, token, data.token].some(secret => secret && value.includes(secret))) return;
  log(`账号身份（${item}）：${value}`);
}

async function runAccount(account, index) {
  const begin = Date.now();
  const result = { account: index + 1, status: 'failure', ...stats() };
  let stage = 1;
  let stageStart = Date.now();
  log(`账号 ${index + 1} / 阶段 1：校验参数并登录`);
  try {
    if (account.invalid || !account.email || !account.password || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(account.email)) throw new Error('账号配置无效，请检查邮箱及密码配对');
    if (dry) {
      result.skipped = 2;
      result.status = 'dry-run';
      log(`⏭️ 阶段 1 校验通过，跳过登录（${Date.now() - stageStart}ms）`);
      log('⏭️ 阶段 2：跳过签到；DRY_RUN_OK，无网络请求');
      return result;
    }
    const login = await request(`${BASE}/api/v1/passport/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'User-Agent': UA },
      body: JSON.stringify({ email: account.email, password: account.password })
    }, 1);
    const auth = login.json.data?.auth_data;
    if (!login.ok || login.json.status !== 'success' || typeof auth !== 'string' || !auth.trim() || /[\r\n]/.test(auth)) throw new Error('登录未获业务成功或有效授权，请检查凭据');
    result.success++;
    log(`✅ 阶段 1 登录成功（${Date.now() - stageStart}ms）`);
    identity(login.json.data, account, auth);
    stage = 2;
    stageStart = Date.now();
    log('阶段 2：执行签到');
    // 签到改变状态，不自动重放请求，避免响应丢失时重复变更。
    const response = await request(`${BASE}/api/v1/user/checkIn`, { headers: { authorization: auth, 'User-Agent': UA } });
    const json = response.json;
    const data = json.data;
    if (response.ok && json.status === 'success' && data &&
        ['string', 'number'].includes(typeof data.reward_mb) && String(data.reward_mb).trim() !== '' && Number.isFinite(Number(data.reward_mb)) && Number(data.reward_mb) >= 0 &&
        typeof data.total_checkin_traffic === 'number' && Number.isFinite(data.total_checkin_traffic) && data.total_checkin_traffic >= 0) {
      result.success++;
      result.status = 'success';
      result.rewardMB = Number(data.reward_mb);
      result.totalGB = (data.total_checkin_traffic / 1024 ** 3).toFixed(2);
      log(`✅ 阶段 2 签到成功：获得 ${result.rewardMB} MB，累计签到流量 ${result.totalGB} GB（${Date.now() - stageStart}ms）`);
      identity(data, account, auth);
    } else if ((response.ok || response.status === 400) && json.status === 'fail' && typeof json.message === 'string' && json.message.toLowerCase().includes('already checked in')) {
      result.alreadyComplete++;
      result.status = 'already-complete';
      log(`☑️ 阶段 2 今日已签到（${Date.now() - stageStart}ms）`);
    } else throw new Error('签到未获明确业务成功，请检查服务状态或凭据');
  } catch (error) {
    result.failed++;
    result.skipped = 2 - result.success - result.alreadyComplete - result.failed;
    result.status = stage === 1 && (account.invalid || !account.email || !account.password || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(account.email)) ? 'configuration-error' : 'failure';
    log(`❌ 阶段 ${stage}：${error.message}（${Date.now() - stageStart}ms）`);
  } finally {
    result.durationMs = Date.now() - begin;
    log(`账号 ${index + 1} 统计：总任务 ${result.total}，成功 ${result.success}，已完成 ${result.alreadyComplete}，跳过 ${result.skipped}，失败 ${result.failed}，耗时 ${result.durationMs}ms`);
  }
  return result;
}

function notifyEnabled() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(mode)) return false;
  if (['1', 'true', 'yes', 'on'].includes(mode)) return true;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (selection === undefined) return false; // listed-only；当前来源没有内置通知名单。
  const filename = path.basename(__filename);
  const relative = __filename.replace(/^.*\/scripts\//, '').replaceAll(path.sep, '/');
  return selection.split(/[,;\s]+/).filter(Boolean).some(selector => {
    const re = new RegExp('^' + selector.split('*').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return [CATALOG, filename, relative].some(value => re.test(value));
  });
}

function child(command, args) {
  return new Promise(resolve => execFile(command, args, { timeout: 15000, maxBuffer: 65536 }, error => resolve(!error)));
}

async function notify(body) {
  if (dry) { log('⏭️ 通知：断网预演，仅本地生成脱敏摘要'); return 'dry-run'; }
  let ql = 'disabled';
  if (notifyEnabled()) {
    ql = 'unavailable';
    const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
    for (const dir of dirs) {
      const js = path.join(dir, 'sendNotify.js');
      const py = path.join(dir, 'notify.py');
      if (fs.existsSync(js)) {
        const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))';
        if (await child(process.execPath, ['-e', code, js, TITLE, body])) { ql = 'sent'; break; }
        ql = 'failed';
      }
      if (fs.existsSync(py)) {
        const code = 'import sys; sys.path.insert(0,sys.argv[1]); import notify; notify.send(sys.argv[2],sys.argv[3])';
        if (await child('python3', ['-c', code, dir, TITLE, body])) { ql = 'sent'; break; }
        ql = 'failed';
      }
    }
    log(`${ql === 'sent' ? '✅' : '⚠️'} 青龙通知：${ql}，不影响业务退出码`);
  } else log('⏭️ 青龙通知：未启用或未在通知名单中');
  let pushplus = 'disabled';
  if (process.env.PUSHPLUS_TOKEN && !['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '').toLowerCase())) {
    try {
      const response = await request('https://www.pushplus.plus/send', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: process.env.PUSHPLUS_TOKEN, title: TITLE, content: body, template: 'txt' })
      });
      pushplus = response.ok && response.json.code === 200 ? 'sent' : 'failed';
    } catch { pushplus = 'failed'; }
    log(`${pushplus === 'sent' ? '✅' : '⚠️'} PushPlus 通知：${pushplus}，不影响业务退出码`);
  }
  return { qinglong: ql, pushplus };
}

async function main() {
  const all = accounts();
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${all.length}`);
  const results = [];
  if (!all.length) log('❌ 配置错误：请设置 FL_ACCOUNTS，或兼容的 USER_EMAIL / USER_PASSWORD');
  for (let i = 0; i < all.length; i++) results.push(await runAccount(all[i], i));
  const failed = results.filter(r => ['failure', 'configuration-error'].includes(r.status)).length;
  const succeeded = results.length - failed;
  const exitCode = failed || !all.length ? 1 : 0;
  process.exitCode = exitCode;
  const status = !all.length ? 'configuration-error' : failed ? (succeeded ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const subtasks = results.reduce((total, row) => {
    for (const key of Object.keys(total)) total[key] += row[key];
    return total;
  }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  const body = `账号总数 ${all.length}，成功 ${succeeded}，失败 ${failed}；状态 ${status}。\n` + results.map(r => `账号 ${r.account}：${r.status}${r.rewardMB !== undefined ? `，奖励 ${r.rewardMB} MB，累计 ${r.totalGB} GB` : ''}`).join('\n');
  let notification;
  try { notification = await notify(body); } catch { notification = 'failed'; log('⚠️ 通知不可用，保留业务退出码'); }
  log('----------------------------------------');
  log(body);
  log(`子任务统计：总数 ${subtasks.total}，成功 ${subtasks.success}，已完成 ${subtasks.alreadyComplete}，跳过 ${subtasks.skipped}，失败 ${subtasks.failed}`);
  log(`完成时间：${new Date().toISOString()}；总耗时：${Date.now() - started}ms；最终状态：${status}；通知状态：${JSON.stringify(notification)}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ applicationKey: 'fl', mode: dry ? 'dry-run' : 'live', status, accounts: all.length, succeeded, failed, subtasks, results, notification, durationMs: Date.now() - started, exitCode }));
}
main().catch(() => {
  process.exitCode = 1;
  log('❌ 任务发生本地执行异常');
});
