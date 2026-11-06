// name: 智谱清言每日领分与余额
// cron: 37 9 * * *
// 上游未声明 cron；此处为每日任务建议时间。
// @name         zhipu-switch · 智谱清言多账号积分助手
// @author       apmengzi
// @license      MIT
// 来源：apmengzi/zhipu-switch，edge-ext/content.js，版本 0.3.4。
/*
 * MIT License
 * Copyright (c) apmengzi
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
 * 功能盘点：原版提供每日领分、余额查询、多账号池、过期令牌续期；浏览器
 * 交互包括切号、添加/删除账号、取消添加、当前登录态/账号池导出、双语浮窗
 * 和收起偏好。原版无环境变量、无 cron，页面加载自动领分；账号存于
 * localStorage，切号会写 Cookie/设备标识并重载，添加会清 Cookie，导出含令牌。
 * 本版独立实现每日领分、余额及多账号处理；无已维护候选或相关参考。
 * 浏览器交互不属于定时业务，不迁移登录态改写、请求嗅探或明文导出。
 *
 * Node.js >=18，无第三方依赖。ZHIPU_ACCOUNTS 每行一个 JSON 对象：
 * 字段 access（不含 Bearer 前缀）、device_id、可选 refresh，均为同一账号。
 * 获取：本人登录 https://chatglm.cn，在开发者工具 Network 中查看官方
 * /chatglm/user-api/user/info 请求的 Authorization 和 X-Device-Id；只在
 * 本地复制至青龙私密环境变量。可选 refresh 来自该站 Cookie
 * chatglm_refresh_token，不上传、不导出。设备标识优先使用 access JWT
 * 内绑定的 device_id；JWT 仅作字段提取，不作为身份认证结果。
 * ZHIPU_TASKS=checkin,balance；仅查询可设 balance。
 * ZHIPU_ALLOW_REFRESH=1 才允许 401 后续期（可能轮换 refresh）；新令牌仅用于
 * 本进程，不写文件、不打印，后续运行需从本人登录态重新获取。
 * ZHIPU_DRY_RUN=1 完全断网，包括通知；预演只验证配置，不表示业务成功。
 * 通知使用青龙 sendNotify.js，QINGLONG_NOTIFY 支持 auto/1/0；auto 默认选中
 * 本任务，QINGLONG_NOTIFY_SCRIPTS 设置后替换默认选择（空值禁用）。
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
    const identities = ["293d29f23c4b62a2", "scripts/content.js", "content.js", "content"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { fork } = require('node:child_process');
const TITLE = '智谱清言每日领分与余额';
const CATALOG = '293d29f23c4b62a2';
const enabled = v => /^(1|true|yes|on)$/i.test(v || '');
const disabled = v => /^(0|false|no|off)$/i.test(v || '');
const dry = enabled(process.env.ZHIPU_DRY_RUN);
const started = Date.now();
const results = [];
const secrets = new Set();
const clock = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
function safe(value) {
  let s = String(value);
  for (const secret of secrets) if (secret) s = s.split(secret).join('[已隐藏]');
  return s.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]').replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
}
function log(s) { console.log(`[${clock()}] ${safe(s)}`); }
function jwt(token) {
  try {
    const p = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8'));
    return p && typeof p === 'object' ? p : {};
  } catch { return {}; }
}
function headers(device, token) {
  const a = String(Date.now());
  const sum = [...a].reduce((n, c) => n + Number(c), 0);
  const stamp = a.slice(0, -2) + ((sum - Number(a[a.length - 2])) % 10) + a.slice(-1);
  const nonce = crypto.randomUUID().replace(/-/g, '');
  return {
    'App-Name': 'chatglm', 'X-App-Platform': 'pc', 'X-App-Version': '0.0.1',
    'X-Device-Id': device, 'X-Lang': 'zh', 'X-Request-Id': crypto.randomUUID(),
    'X-Timestamp': stamp, 'X-Nonce': nonce,
    'X-Sign': crypto.createHash('md5').update(`${stamp}-${nonce}-8a1317a7468aa3ad86e997d08f3f31cb`).digest('hex'),
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };
}
function request(acc, endpoint, method = 'GET', authorization) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const h = headers(acc.device_id, acc.access);
    if (authorization !== undefined) h.Authorization = authorization;
    const body = method === 'POST' ? '{}' : undefined;
    if (body) { h['Content-Type'] = 'application/json;charset=utf-8'; h['Content-Length'] = Buffer.byteLength(body); }
    let done = false, req;
    const finish = (err, value) => {
      if (done) return;
      done = true; clearTimeout(timer);
      if (err) reject(err); else resolve(value);
    };
    const timer = setTimeout(() => { finish(new Error('请求超时')); if (req) req.destroy(); }, 12000);
    req = https.request({ hostname: 'chatglm.cn', path: `/chatglm${endpoint}`, method, headers: h }, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 262144) { finish(new Error('响应超过大小限制')); res.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('end', () => {
        if (done) return;
        if (res.statusCode === 401) return finish(null, { status: 401 });
        if (res.statusCode !== 200) return finish(new Error(`HTTP 请求失败（${res.statusCode}）`));
        try {
          const j = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!j || typeof j !== 'object' || Array.isArray(j) || !Number.isInteger(j.status)) throw new Error();
          finish(null, j);
        } catch { finish(new Error('响应不是有效业务对象')); }
      });
    });
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(body);
  });
}
async function refresh(acc) {
  if (!enabled(process.env.ZHIPU_ALLOW_REFRESH) || !acc.refresh) throw new Error('凭据过期；需重新获取登录态或显式启用续期');
  // 保留上游 refresh 原值、Bearer 两种认证兼容链，只在明确拒绝认证时回退。
  for (const auth of [acc.refresh, `Bearer ${acc.refresh}`]) {
    const j = await request(acc, '/user-api/user/refresh', 'POST', auth);
    if (j.status === 401 || j.status === 403) continue;
    const r = j.result;
    const access = r && (r.access_token || r.token);
    if (j.status !== 0 || typeof access !== 'string' || !access || /\s/.test(access)) throw new Error('续期未返回有效成功结果');
    secrets.add(access);
    if (r.refresh_token) secrets.add(r.refresh_token);
    const bound = jwt(access).device_id;
    if (bound && (typeof bound !== 'string' || !/^[a-f0-9]{32}$/i.test(bound))) throw new Error('续期设备字段无效');
    acc.access = access;
    acc.refresh = r.refresh_token || acc.refresh;
    if (bound) { secrets.add(bound); acc.device_id = bound; }
    log('令牌续期成功，仅本轮内存生效；后续运行需重新获取登录态');
    return;
  }
  throw new Error('续期认证失败');
}
async function call(acc, endpoint, method) {
  let j = await request(acc, endpoint, method);
  if (j.status === 401) { await refresh(acc); j = await request(acc, endpoint, method); }
  return j;
}
function infoResult(j) {
  if (j.status !== 0 || !j.result || typeof j.result !== 'object') throw new Error(`账号查询未成功（业务码 ${j.status}）`);
  const r = j.result, balance = r.member_info && r.member_info.left_score;
  if (typeof balance !== 'number' || !Number.isFinite(balance) || balance < 0) throw new Error('余额字段缺失或无效');
  const identity = r.nickname || r.username || r.display_name || r._id;
  if (typeof identity === 'string' || typeof identity === 'number') log(`官方账号身份：${identity}`);
  log(`余额：${balance} 分`);
}
async function runAccount(line, index, tasks) {
  const time = Date.now();
  const stat = { account: index, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let stage = 0;
  async function step(label, action) {
    const t = Date.now(); stat.total++; stage++;
    log(`账号 ${index} / 阶段 ${stage}：${label}`);
    try {
      const state = await action();
      if (state === 'already') stat.alreadyComplete++;
      else if (state === 'skipped') stat.skipped++;
      else stat.success++;
      log(`${state === 'skipped' ? '⏭️' : '✅'} ${label}完成，耗时 ${Date.now() - t}ms`);
    } catch (e) { stat.failed++; log(`❌ ${label}失败：${e.message}，耗时 ${Date.now() - t}ms`); throw e; }
  }
  try {
    let acc;
    await step('校验同账号凭据', async () => {
      try { acc = JSON.parse(line); } catch { throw new Error('账号行必须是 JSON 对象'); }
      if (!acc || Array.isArray(acc) || typeof acc !== 'object') throw new Error('账号行必须是 JSON 对象');
      for (const key of ['access', 'device_id', 'refresh']) if (typeof acc[key] === 'string') secrets.add(acc[key]);
      if (typeof acc.access !== 'string' || !acc.access || /\s/.test(acc.access)) throw new Error('access 必填且不能包含 Bearer 前缀或空白');
      if (acc.refresh !== undefined && (typeof acc.refresh !== 'string' || !acc.refresh || /\s/.test(acc.refresh))) throw new Error('refresh 格式无效');
      const p = jwt(acc.access);
      if (p.is_guest) throw new Error('不能使用访客账号');
      acc.device_id = p.device_id || acc.device_id;
      if (typeof acc.device_id !== 'string' || !/^[a-f0-9]{32}$/i.test(acc.device_id)) throw new Error('device_id 必须为同账号的 32 位十六进制设备标识');
      secrets.add(acc.device_id);
    });
    if (dry) {
      for (const task of tasks) await step(`预演 ${task}`, async () => { log('配置有效；未发送请求、未变更账号、未投递通知'); return 'skipped'; });
    } else {
      await step('查询账号身份与余额', async () => infoResult(await call(acc, '/user-api/user/info')));
      if (tasks.includes('checkin')) {
        await step('领取每日积分', async () => {
          const j = await call(acc, '/member-api/member/daily_login_score', 'POST');
          if (j.status === 10001) { log('今日已领取'); return 'already'; }
          if (j.status !== 0 || !j.result || typeof j.result.score !== 'number' || !Number.isFinite(j.result.score) || j.result.score < 0) throw new Error(`领分未返回有效成功结果（业务码 ${j.status}）`);
          log(`每日领分成功：+${j.result.score} 分`);
        });
        await step('核对领取后余额', async () => infoResult(await call(acc, '/user-api/user/info')));
      }
    }
  } catch { /* 已在对应阶段脱敏记录，继续下个账号。 */ }
  stat.durationMs = Date.now() - time;
  stat.status = stat.failed ? 'failure' : dry ? 'dry-run' : 'success';
  results.push(stat);
  log(`账号 ${index} 统计：总任务 ${stat.total}，成功 ${stat.success}，已完成 ${stat.alreadyComplete}，跳过 ${stat.skipped}，失败 ${stat.failed}，耗时 ${stat.durationMs}ms`);
}
function selected() {
  const setting = process.env.QINGLONG_NOTIFY || 'auto';
  if (disabled(setting)) return false;
  if (enabled(setting)) return true;
  if (setting !== 'auto') return false;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const names = [CATALOG, path.basename(__filename), 'candidate.js', 'edge-ext/content.js', 'scripts/candidate.js'];
  return process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(pattern => {
    const re = new RegExp('^' + pattern.split('*').map(x => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(n => re.test(n));
  });
}
async function notify(summary) {
  if (!selected()) return 'disabled';
  if (dry) { log('预演通知摘要已生成，断网模式不投递'); return 'dry-run-skipped'; }
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const modulePath = locations.find(p => fs.existsSync(p));
  if (!modulePath) { log('⚠️ 未找到青龙 sendNotify.js，保留业务退出码'); return 'unavailable'; }
  const body = safe(`状态：${summary.status}；账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；${summary.error ? '配置错误；' : ''}耗时 ${summary.durationMs}ms`);
  // 子进程隔离通知日志，防止第三方通知模块打印环境变量或原始响应。
  return new Promise(resolve => {
    let settled = false;
    const child = fork(__filename, ['--notify-worker', modulePath], { silent: true });
    const finish = state => { if (settled) return; settled = true; clearTimeout(timer); child.kill(); resolve(state); };
    const timer = setTimeout(() => finish('timeout'), 15000);
    child.on('error', () => finish('failed'));
    child.on('exit', code => finish(code === 0 ? 'sent' : 'failed'));
    child.send({ title: TITLE, body });
  });
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}`);
  const lines = (process.env.ZHIPU_ACCOUNTS || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  // 在任何身份输出之前收集所有账号的敏感字段，包括格式不合法的行。
  for (const line of lines) {
    secrets.add(line);
    try { const a = JSON.parse(line); for (const k of ['access', 'refresh', 'device_id']) if (a && typeof a[k] === 'string') secrets.add(a[k]); } catch {}
  }
  log(`账号数：${lines.length}`);
  let error;
  const tasks = [...new Set((process.env.ZHIPU_TASKS || 'checkin,balance').split(',').map(s => s.trim()))];
  if (!lines.length) error = '缺少必填环境变量 ZHIPU_ACCOUNTS';
  else if (tasks.some(t => !['checkin', 'balance'].includes(t))) error = 'ZHIPU_TASKS 仅支持 checkin、balance';
  else if (process.env.ZHIPU_DRY_RUN && !enabled(process.env.ZHIPU_DRY_RUN) && !disabled(process.env.ZHIPU_DRY_RUN)) error = 'ZHIPU_DRY_RUN 开关无效';
  else if (process.env.ZHIPU_ALLOW_REFRESH && !enabled(process.env.ZHIPU_ALLOW_REFRESH) && !disabled(process.env.ZHIPU_ALLOW_REFRESH)) error = 'ZHIPU_ALLOW_REFRESH 开关无效';
  if (error) log(`❌ 配置错误：${error}`);
  else for (let i = 0; i < lines.length; i++) await runAccount(lines[i], i + 1, tasks);
  const failed = error ? lines.length : results.filter(r => r.failed).length;
  const success = error ? 0 : results.length - failed;
  const status = error ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const summary = { task: CATALOG, status, mode: dry ? 'dry-run' : 'live', accounts: lines.length, success, failed, error, results, durationMs: Date.now() - started };
  process.exitCode = error || failed ? 1 : 0;
  try { summary.notification = await notify(summary); } catch { summary.notification = 'failed'; }
  log(`通知状态：${summary.notification}（不改变业务退出码）`);
  console.log('----------------------------------------');
  const total = key => results.reduce((n, r) => n + r[key], 0);
  log(`账号统计：总数 ${lines.length}，成功 ${success}，失败 ${failed}`);
  log(`子任务统计：总数 ${total('total')}，成功 ${total('success')}，已完成 ${total('alreadyComplete')}，跳过 ${total('skipped')}，失败 ${total('failed')}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now() - started}ms；最终状态：${status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
}
if (process.argv[2] === '--notify-worker' && process.send) {
  process.once('message', async ({ title, body }) => {
    try { const n = require(process.argv[3]); if (typeof n.sendNotify !== 'function') throw new Error(); await n.sendNotify(title, body); process.exit(0); }
    catch { process.exit(1); }
  });
} else {
  main().catch(() => { process.exitCode = 1; log('❌ 任务执行异常'); });
}
