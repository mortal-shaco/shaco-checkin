// name: Rousi 签到
// cron: 37 0 * * *
/*
 * name: Rousi 签到
 * cron: 0 9 * * *
 * 来源：373065025/rousi-checkin，rousi_checkin.js
 * 上游提交：627ec698dc9d35f69f44e479366a7c31dd46489c
 * 上游未声明定时；以上为每日北京时间 09:00 的建议定时。
 * 原始源码未含版权声明；保留上游归属，适用 MIT 许可。
 * MIT License
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 * Node.js >= 16，无需第三方依赖。ROUSI_TOKEN 每个非空行一个账号，支持
 * 纯 Token 或 Bearer 前缀；ROUSI_COOKIE 每行一个完整 Cookie。
 * 登录 https://rousi.pro/，开发者工具→网络→站内 API 请求头，复制
 * Authorization 的 Bearer 后内容或 Cookie。请勿复制响应内容或公开凭据。
 * 兼容小写变量及 ROUSI_TOKEN_1..20、ROUSI_COOKIE_1..20（每项也按行读取）。
 * 不再使用 & 分隔账号，Cookie 中的 & 保留为凭据内容。
 * ROUSI_DRY_RUN=1 完全断网预演，通知仅模拟；QINGLONG_NOTIFY=0 关闭通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录，缺失不影响业务退出码。
 * 可选 PUSHPLUS_TOKEN（兼容 pushplus_token）、PUSHPLUS_TYPE，通过 HTTPS 推送。
 * 本脚本只执行普通签到，不发布内容、不消耗积分或修改账号配置。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["3c5c6df4d8a81a7f", "scripts/rousi_checkin.js", "rousi_checkin.js", "rousi_checkin"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const TITLE = 'Rousi 签到';
const BASE = 'https://rousi.pro';
const START = Date.now();
const DRY = /^(1|true|yes|on)$/i.test(process.env.ROUSI_DRY_RUN || '');
const NOTIFY = !/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1');
const stamp = () => new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
const log = text => console.log(`[${stamp()}] ${text}`);
const elapsed = start => ((Date.now() - start) / 1000).toFixed(2);
const lines = value => (value || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean);
const accounts = [];
function addAuth(type, value) {
  for (let credential of lines(value)) {
    if (type === 'token') credential = credential.replace(/^Bearer\s+/i, '').trim();
    if (!credential) continue;
    if (!accounts.some(a => a.type === type && a.value === credential)) accounts.push({ type, value: credential });
  }
}
function readAuths() {
  addAuth('token', process.env.ROUSI_TOKEN || process.env.rousi_token);
  // 显式引用此前失败契约中的编号变量；其余编号遵循同一解析规则。
  addAuth('token', process.env.ROUSI_TOKEN_1 || process.env.rousi_token_1);
  for (const [canonical, legacy] of [
    ['ROUSI_TOKEN_2', 'rousi_token_2'],
    ['ROUSI_TOKEN_3', 'rousi_token_3'],
    ['ROUSI_TOKEN_4', 'rousi_token_4'],
    ['ROUSI_TOKEN_5', 'rousi_token_5'],
    ['ROUSI_TOKEN_6', 'rousi_token_6'],
    ['ROUSI_TOKEN_7', 'rousi_token_7'],
    ['ROUSI_TOKEN_8', 'rousi_token_8'],
    ['ROUSI_TOKEN_9', 'rousi_token_9'],
    ['ROUSI_TOKEN_10', 'rousi_token_10'],
    ['ROUSI_TOKEN_11', 'rousi_token_11'],
    ['ROUSI_TOKEN_12', 'rousi_token_12'],
    ['ROUSI_TOKEN_13', 'rousi_token_13'],
    ['ROUSI_TOKEN_14', 'rousi_token_14'],
    ['ROUSI_TOKEN_15', 'rousi_token_15'],
    ['ROUSI_TOKEN_16', 'rousi_token_16'],
    ['ROUSI_TOKEN_17', 'rousi_token_17'],
    ['ROUSI_TOKEN_18', 'rousi_token_18'],
    ['ROUSI_TOKEN_19', 'rousi_token_19'],
    ['ROUSI_TOKEN_20', 'rousi_token_20']
  ]) addAuth('token', process.env[canonical] || process.env[legacy]);
  addAuth('cookie', process.env.ROUSI_COOKIE || process.env.rousi_cookie);
  for (const [canonical, legacy] of [
    ['ROUSI_COOKIE_1', 'rousi_cookie_1'],
    ['ROUSI_COOKIE_2', 'rousi_cookie_2'],
    ['ROUSI_COOKIE_3', 'rousi_cookie_3'],
    ['ROUSI_COOKIE_4', 'rousi_cookie_4'],
    ['ROUSI_COOKIE_5', 'rousi_cookie_5'],
    ['ROUSI_COOKIE_6', 'rousi_cookie_6'],
    ['ROUSI_COOKIE_7', 'rousi_cookie_7'],
    ['ROUSI_COOKIE_8', 'rousi_cookie_8'],
    ['ROUSI_COOKIE_9', 'rousi_cookie_9'],
    ['ROUSI_COOKIE_10', 'rousi_cookie_10'],
    ['ROUSI_COOKIE_11', 'rousi_cookie_11'],
    ['ROUSI_COOKIE_12', 'rousi_cookie_12'],
    ['ROUSI_COOKIE_13', 'rousi_cookie_13'],
    ['ROUSI_COOKIE_14', 'rousi_cookie_14'],
    ['ROUSI_COOKIE_15', 'rousi_cookie_15'],
    ['ROUSI_COOKIE_16', 'rousi_cookie_16'],
    ['ROUSI_COOKIE_17', 'rousi_cookie_17'],
    ['ROUSI_COOKIE_18', 'rousi_cookie_18'],
    ['ROUSI_COOKIE_19', 'rousi_cookie_19'],
    ['ROUSI_COOKIE_20', 'rousi_cookie_20']
  ]) addAuth('cookie', process.env[canonical] || process.env[legacy]);
}
// 只输出白名单数字与公开身份；不记录服务器消息、原始响应或底层异常。
function number(value) {
  if ((typeof value !== 'number' && typeof value !== 'string') || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
function metric(value, decimals = 2) { const n = number(value); return n === null ? '未提供' : n.toFixed(decimals); }
function size(value) {
  let n = number(value);
  if (n === null || n < 0) return '未提供';
  const units = ['B', 'KB', 'MB', 'GB', 'TB']; let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(2)} ${units[i]}`;
}
function publicIdentity(data) {
  for (const field of ['nickname', 'username', 'display_name', 'displayName', 'uid']) {
    const value = data && data[field];
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const text = String(value);
    if (!text || /[\r\n\x00-\x1f]/.test(text) || /(?:\+?86)?1[3-9]\d{9}/.test(text)) continue;
    if (accounts.some(a => text.includes(a.value))) continue;
    return `${field}: ${text}`;
  }
  return '';
}
function request(url, method = 'GET', headers = {}, data) {
  if (DRY) return Promise.reject(new Error('预演禁止网络请求'));
  return new Promise((resolve, reject) => {
    const body = data === undefined ? undefined : JSON.stringify(data);
    let timer;
    const req = https.request(url, {
      method, headers: { 'Accept': 'application/json', 'Content-Type': 'application/json',
        ...(body ? { 'Content-Length': Buffer.byteLength(body) } : {}), ...headers }
    }, res => {
      let bytes = 0; const chunks = [];
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 262144) req.destroy(new Error('响应超过大小限制'));
        else chunks.push(chunk);
      });
      res.on('error', () => { clearTimeout(timer); reject(new Error('响应读取失败')); });
      res.on('aborted', () => { clearTimeout(timer); reject(new Error('响应中断')); });
      res.on('end', () => {
        clearTimeout(timer);
        if (res.statusCode < 200 || res.statusCode >= 300) { reject(new Error(`HTTP ${res.statusCode}`)); return; }
        try {
          const json = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!json || typeof json !== 'object' || Array.isArray(json)) throw new Error();
          resolve(json);
        } catch (_) { reject(new Error('响应格式无效')); }
      });
    });
    timer = setTimeout(() => req.destroy(new Error('请求超时')), 30000);
    req.on('error', () => { clearTimeout(timer); reject(new Error('网络请求失败或超时')); });
    req.end(body);
  });
}
async function api(auth, endpoint, method = 'GET', body) {
  const headers = { 'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Origin': BASE, 'Referer': BASE + '/',
    ...(auth.type === 'token' ? { Authorization: `Bearer ${auth.value}` } : { Cookie: auth.value }) };
  return request(BASE + endpoint, method, headers, body);
}
function checkedData(response) {
  if (response.code !== 0 || !response.data || typeof response.data !== 'object' || Array.isArray(response.data)) {
    throw new Error('接口未确认业务成功或数据格式已变化');
  }
  return response.data;
}
async function runAccount(auth, index) {
  const began = Date.now(); const details = []; const stats = { total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let stage = 0; let stageStart;
  function begin(title) { stage++; stageStart = Date.now(); log(`账号 ${index} · 阶段 ${stage}/3 ${title}`); }
  function report(text) { log(text); details.push(text); }
  function finish(text, kind = 'success') { stats[kind]++; log(`${text}（阶段耗时 ${elapsed(stageStart)} 秒）`); }
  log(`---------- 账号 ${index} ----------`);
  try {
    if (/[\r\n\x00-\x1f\x7f]/.test(auth.value) || (auth.type === 'token' && /[&\s]/.test(auth.value))) {
      throw new Error('凭据格式无效；Token 请按行分隔且不要使用 &');
    }
    begin('读取积分与签到状态');
    const init = DRY ? { balance: { karma: 0, credits: 0 }, attendance: { server_today: '2026-01-01', attended_dates: [], current_streak: 0 } }
      : checkedData(await api(auth, '/api/points/init'));
    if (!init.balance || typeof init.balance !== 'object' || Array.isArray(init.balance) ||
        !['karma', 'credits'].some(key => number(init.balance[key]) !== null)) throw new Error('积分数据格式已变化');
    const identity = publicIdentity(init) || publicIdentity(init.user) || publicIdentity(init.account);
    if (identity) log(`官方账号身份：${identity}`);
    const label = (value, fallback) => typeof value === 'string' && value.length <= 40 && !/[\r\n\x00-\x1f]/.test(value) && !accounts.some(a => value.includes(a.value)) && !/1[3-9]\d{9}/.test(value) ? value : fallback;
    const karmaName = label(init.config?.karma_name, '魔力值');
    const creditsName = label(init.config?.credits_name, 'PT币');
    report(`${karmaName}：${metric(init.balance.karma)}；${creditsName}：${metric(init.balance.credits)}`);
    const attendance = init.attendance || {};
    report(`连续签到：${metric(attendance.current_streak, 0)} 天；累计签到：${Array.isArray(attendance.attended_dates) ? attendance.attended_dates.length : '未提供'} 天`);
    finish(DRY ? '✅ 预演积分读取通过（模拟数据）' : '✅ 积分读取成功');
    begin('读取分享率与上传下载统计');
    try {
    const response = DRY ? { ratio: 0, bonus: 0, uploaded: 0, downloaded: 0 } : await api(auth, '/api/account/stats');
    // 上游此接口为无 code 的直接对象；若返回 code 则严格要求为 0。
    if (response.code !== undefined && response.code !== 0) throw new Error('账户统计接口未确认业务成功');
    const accountStats = response.code === 0 && response.data ? response.data : response;
    if (!['ratio', 'bonus', 'uploaded', 'downloaded', 'upload', 'download', 'seeding', 'leeching', 'invites'].some(key => number(accountStats[key]) !== null)) {
      throw new Error('账户统计响应字段已变化');
    }
    const statsIdentity = publicIdentity(accountStats);
    if (statsIdentity && statsIdentity !== identity) log(`官方账号身份：${statsIdentity}`);
    report(`分享率：${metric(accountStats.ratio, 3)}；${karmaName}：${metric(accountStats.bonus ?? init.balance.karma)}；累计上传：${size(accountStats.uploaded)}；累计下载：${size(accountStats.downloaded)}`);
    finish(DRY ? '✅ 预演统计读取通过（模拟数据）' : '✅ 账户统计读取成功');
    } catch (_) {
      finish('❌ 账户统计读取失败；继续尝试签到，整体仍按失败退出', 'failed');
    }
    begin('普通签到');
    const today = attendance.server_today;
    if (!DRY && typeof today === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(today) &&
        Array.isArray(attendance.attended_dates) && attendance.attended_dates.includes(today)) {
      finish('☑️ 今日已签到，跳过重复签到', 'alreadyComplete');
    } else if (DRY) {
      finish('✅ DRY_RUN_OK：已预演普通签到 POST /api/points/attendance，未发送请求');
    } else {
      const result = await api(auth, '/api/points/attendance', 'POST', { mode: 'normal' });
      if (result.code !== 0) throw new Error('签到接口未确认业务成功');
      const data = result.data || {};
      report(`本次奖励：${metric(data.bonus)} ${karmaName}；连续签到奖励：${metric(data.streak_bonus)} ${karmaName}；当前连续：${metric(data.current_streak, 0)} 天`);
      finish('✅ 签到成功');
    }
  } catch (error) {
    stats.failed++;
    stats.skipped = Math.max(0, stats.total - stats.success - stats.alreadyComplete - stats.failed);
    log(`❌ 账号 ${index} 失败：${error.message}（阶段耗时 ${elapsed(stageStart || began)} 秒）；其余阶段跳过`);
  }
  const ok = stats.failed === 0;
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${elapsed(began)} 秒`);
  return { account: index, ok, ...stats, details };
}
function helperNotify(file, body) {
  // 隔离通知输出，避免第三方通知模块打印配置或请求；超时不改变业务退出码。
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e',
      'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))',
      file, TITLE, body], { stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve(false); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve(false); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0); });
  });
}
async function notify(body) {
  if (!NOTIFY) { log('⏭️ 通知已由 QINGLONG_NOTIFY 关闭'); return 'disabled'; }
  if (DRY) { log('⏭️ 预演通知：已生成脱敏总结，禁止调用通知模块或网络'); return 'dry-run'; }
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.resolve(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  let state = 'unavailable';
  for (const file of [...new Set(files)]) {
    if (!fs.existsSync(file)) continue;
    if (await helperNotify(file, body)) { state = 'sent'; break; }
    state = 'failed';
  }
  log(state === 'sent' ? '✅ 青龙通知已发送' : '⚠️ 青龙通知不可用或发送失败，保留业务退出码');
  const token = process.env.PUSHPLUS_TOKEN || process.env.pushplus_token;
  if (token) {
    try {
      const type = process.env.PUSHPLUS_TYPE || 'wechat';
      const result = await request('https://www.pushplus.plus/send', 'POST', {}, {
        token, title: TITLE, content: body, timestamp: Date.now(),
        type: ['pushplusvip', 'wxgo', 'qywxgo', 'email', 'feishu', 'dingtalk', 'bark'].includes(type) ? type : 'send'
      });
      log(result.code === 0 || result.code === 200 ? '✅ PushPlus 通知发送成功' : '⚠️ PushPlus 通知业务失败');
    } catch (_) { log('⚠️ PushPlus 通知发送失败，保留业务退出码'); }
  }
  return state;
}
async function main() {
  readAuths();
  log(`============ ${TITLE} ============`);
  log(`开始时间：${new Date(START).toISOString()}；模式：${DRY ? '断网预演' : '正式执行'}；账号数：${accounts.length}`);
  const results = [];
  if (!accounts.length) log('❌ 配置错误：请设置 ROUSI_TOKEN（兼容 ROUSI_TOKEN_1 或 ROUSI_COOKIE）');
  for (let i = 0; i < accounts.length; i++) results.push(await runAccount(accounts[i], i + 1));
  const succeeded = results.filter(r => r.ok).length;
  const failed = results.length - succeeded;
  const status = !accounts.length ? 'configuration-error' : failed ? (succeeded ? 'partial-failure' : 'failure') : (DRY ? 'dry-run' : 'success');
  const exitCode = !accounts.length || failed ? 1 : 0;
  const tasks = results.reduce((a, r) => {
    for (const key of ['total', 'success', 'alreadyComplete', 'skipped', 'failed']) a[key] += r[key];
    return a;
  }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  const body = `模式：${DRY ? '断网预演' : '正式执行'}；状态：${status}；账号总数：${accounts.length}；成功：${succeeded}；失败：${failed}；子任务成功：${tasks.success}；已完成：${tasks.alreadyComplete}；失败：${tasks.failed}。${!accounts.length ? '缺少账号凭据。' : ''}\n` + results.map(r => `账号 ${r.account}：${r.ok ? '通过' : '失败'}\n${r.details.join('\n')}`).join('\n');
  let notification;
  try { notification = await notify(body); } catch (_) { notification = 'failed'; log('⚠️ 通知异常，保留业务退出码'); }
  console.log('----------------------------------------');
  log(`任务统计：账号 ${accounts.length}，成功 ${succeeded}，失败 ${failed}；子任务 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  const finishedAt = new Date().toISOString();
  log(`结束时间：${finishedAt}；总耗时：${elapsed(START)} 秒；通知状态：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, mode: DRY ? 'dry-run' : 'live', status,
    accounts: accounts.length, succeeded, failed, tasks, results, notification, startedAt: new Date(START).toISOString(), finishedAt, exitCode }));
  process.exitCode = exitCode;
}
main();
