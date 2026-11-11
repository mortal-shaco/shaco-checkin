#!/usr/bin/env node
// name: 机场账号每日签到
// cron: 42 10 * * *
/*
 * Derived from HardIsStyle/CF-Workers-checkin, worker.js
 * https://gitlab.com/HardIsStyle/CF-Workers-checkin
 * License: Apache-2.0 (effective license supplied by source catalog).
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy at https://www.apache.org/licenses/LICENSE-2.0
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * Node.js >=18. 每个非空行一个 JSON 账号：CF_WORKERS_ACCOUNTS 中填写
 * {"domain":"https://站点域名","email":"注册邮箱","password":"登录密码"}
 * 从本人站点登录页取得域名，使用注册邮箱和密码；密码原样保留。
 * 单账号兼容 JC/DOMAIN、ZH/USER、MM/PASS（优先前者）。
 * CF_WORKERS_DRY_RUN=1 完全断网预演，包括通知；不会验证真实业务。
 * 上游未提供 cron；默认北京时间每日 08:00，可在青龙任务中调整。
 * 手动执行本文件等价于安全的手动签到，不再监听包含密码的 HTTP 路径。
 * QINGLONG_NOTIFY=auto 默认仅通知选中脚本，1 强制开启，0 关闭；
 * QINGLONG_NOTIFY_SCRIPTS 支持目录路径、文件名、通配符及来源编号，
 * 使用逗号、分号、空白分隔；设置为空关闭所有选择，设置后覆盖默认。
 * QINGLONG_NOTIFY_DIR 可指定 sendNotify.js 目录；缺失不改变业务退出码。
 * TGTOKEN+TGID 可选官方 TG 通道，仅发送脱敏汇总，移除第三方代理。
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
    const identities = ["a497ca3639ff7639", "scripts/cf_workers.js", "cf_workers.js", "cf_workers"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '机场账号每日签到';
const dry = process.env.CF_WORKERS_DRY_RUN === '1';
const started = Date.now();
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
const log = text => console.log(`[${stamp()}] ${text}`);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
class SafeError extends Error {}
const fail = msg => { throw new SafeError(msg); };
const message = error => error instanceof SafeError ? error.message : '运行异常（详细信息已抑制，请检查配置及网络）';

function entries() {
  if (process.env.CF_WORKERS_ACCOUNTS !== undefined) {
    return process.env.CF_WORKERS_ACCOUNTS.split(/\r?\n/).filter(x => x.trim()).map(line => () => {
      try { return validate(JSON.parse(line)); } catch (e) {
        if (e instanceof SafeError) throw e;
        fail('账号行必须是有效 JSON 对象');
      }
    });
  }
  const e = process.env;
  if (e.JC || e.DOMAIN || e.MM || e.PASS || e.ZH) {
    return [() => validate({ domain: e.JC || e.DOMAIN, email: e.ZH || e.USER, password: e.MM || e.PASS })];
  }
  return [];
}
function validate(a) {
  if (!a || !['domain', 'email', 'password'].every(k => typeof a[k] === 'string' && a[k].trim())) fail('账号缺少域名、邮箱或密码');
  if (/[\r\n]/.test(a.email + a.password)) fail('凭据不能包含换行');
  let url;
  try { url = new URL(a.domain.includes('://') ? a.domain.trim() : `https://${a.domain.trim()}`); }
  catch { fail('站点域名无效'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') fail('站点必须是无路径、无内嵌凭据的 HTTPS 域名');
  return { domain: url.origin, email: a.email, password: a.password };
}
async function request(url, options = {}, json = true) {
  if (dry) fail('断网保护：预演禁止请求');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(url, { ...options, redirect: 'manual', signal: controller.signal });
    if (!response.ok) fail(`接口 HTTP ${response.status}，未确认成功`);
    const reader = response.body?.getReader();
    const parts = []; let size = 0;
    if (reader) {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > 1048576) { await reader.cancel(); fail('响应超过大小限制'); }
        parts.push(Buffer.from(value));
      }
    }
    const text = Buffer.concat(parts).toString('utf8');
    let data;
    if (json) {
      try { data = JSON.parse(text); } catch { fail('接口未返回有效 JSON'); }
      if (!data || typeof data !== 'object' || Array.isArray(data)) fail('接口响应结构无效');
    }
    return { headers: response.headers, data };
  } catch (e) {
    if (e instanceof SafeError) throw e;
    fail(controller.signal.aborted ? '请求超时' : '网络请求失败');
  } finally { clearTimeout(timer); }
}
function cookies(headers, jar) {
  const values = typeof headers.getSetCookie === 'function' ? headers.getSetCookie() : (headers.get('set-cookie') || '').split(/,\s*(?=[^;,=\s]+\s*=)/);
  for (const value of values) {
    const pair = value.split(';', 1)[0]; const eq = pair.indexOf('=');
    if (eq > 0) jar.set(pair.slice(0, eq).trim(), pair.slice(eq + 1));
  }
}
function identity(data, account) {
  const item = data.user || data.data?.user || data.data || data;
  for (const key of ['nickname', 'username', 'display_name', 'displayName', 'uid']) {
    const value = item?.[key];
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const text = String(value);
    // 不输出被误放入身份字段的凭据、手机号、邮箱或设备信息。
    if (!text || text.includes('@') || /\d{7,}/.test(text) && key !== 'uid' || /[\r\n\x00-\x1f]/.test(text) || text.includes(account.password) || text.includes(account.email)) continue;
    log(`官方账号身份（${key}）：${text}`); break;
  }
}
async function runAccount(load, index) {
  const begin = Date.now();
  const stats = { account: index, total: 4, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, status: 'failure' };
  let stage = 0;
  async function step(title, work) {
    stage++; const t = Date.now(); log(`账号 ${index} 阶段 ${stage}/4 ${title}`);
    let result;
    try { result = await work(); } catch (e) { log(`账号 ${index} 阶段 ${stage} ❌ 失败，耗时 ${Date.now() - t}ms`); throw e; }
    stats.success++;
    log(`账号 ${index} 阶段 ${stage} ✅ 完成，耗时 ${Date.now() - t}ms`); return result;
  }
  try {
    const a = load();
    if (dry) {
      for (const title of ['获取初始会话', '邮箱密码登录', '验证会话', '签到']) {
        stage++; stats.skipped++; log(`账号 ${index} 阶段 ${stage}/4 ${title} ⏭️ 预演跳过请求，耗时 0ms`);
      }
      stats.status = 'dry-run';
    } else {
      const jar = new Map();
      const headers = () => ({ 'User-Agent': 'Mozilla/5.0 Chrome/129.0.0.0 Safari/537.36', Accept: 'application/json, text/plain, */*', Origin: a.domain, Referer: `${a.domain}/auth/login`, Cookie: [...jar].map(([k,v]) => `${k}=${v}`).join('; ') });
      await step('获取初始会话', async () => cookies((await request(`${a.domain}/auth/login`, { headers: headers() }, false)).headers, jar));
      await step('邮箱密码登录', async () => {
        const r = await request(`${a.domain}/auth/login`, { method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ email: a.email, passwd: a.password, remember_me: 'on', code: '' }) });
        if (r.data.ret !== 1) fail('登录业务校验失败，请核对凭据或验证码要求');
        cookies(r.headers, jar); if (!jar.size) fail('登录后无有效会话 Cookie');
        identity(r.data, a);
      });
      await step('验证会话', async () => {
        // 参考同应用版本：等待会话传播并更新 Cookie；不将异常状态视为成功。
        for (let attempt = 1; attempt <= 6; attempt++) {
          await sleep(attempt === 1 ? 1500 : 2000);
          try {
            const r = await request(`${a.domain}/user`, { headers: headers() }, false);
            cookies(r.headers, jar); return;
          } catch (e) { if (attempt === 6) throw e; log(`账号 ${index} 会话检查 ${attempt}/6 未就绪`); }
        }
      });
      await step('签到', async () => {
        await sleep(1000);
        const r = await request(`${a.domain}/user/checkin`, { method: 'POST', headers: { ...headers(), Referer: `${a.domain}/user/panel`, 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' } });
        identity(r.data, a);
        if (r.data.ret === 1) { log(`账号 ${index} ✅ 签到业务成功`); return; }
        // ret=0 不是通用成功码，只接纳明确的当天已签到响应。
        if (r.data.ret === 0 && typeof r.data.msg === 'string' && /^(?:您|你)?(?:今天|今日)(?:已经|已)签到[!！。.]?$/.test(r.data.msg.trim())) {
          stats.alreadyComplete++; log(`账号 ${index} ☑️ 今日已签到`); return;
        }
        fail('签到业务未确认成功（未输出原始响应）');
      });
      stats.status = 'success';
    }
  } catch (e) {
    stats.failed = 1; stats.skipped = Math.max(0, stats.total - stats.success - 1);
    stats.status = stage === 0 ? 'configuration-error' : 'failure';
    log(`账号 ${index} ❌ ${message(e)}，阶段耗时已计入账号统计`);
  }
  stats.success -= stats.alreadyComplete;
  stats.durationMs = Date.now() - begin;
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs}ms`);
  return stats;
}
function selected() {
  const value = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0','false','no','off'].includes(value)) return false;
  const list = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (list !== undefined) {
    const names = ['a497ca3639ff7639', '8fb4a521c8826a35', __filename, path.basename(__filename), path.relative('/ql/data/scripts', __filename), path.relative('/ql/scripts', __filename)];
    return list.split(/[,;\s]+/).filter(Boolean).some(pattern => {
      const re = new RegExp('^' + pattern.split('*').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
      return names.some(n => re.test(n));
    });
  }
  return ['1','true','yes','on'].includes(value);
}
async function notify(body) {
  if (dry) { log('通知：断网预演，仅模拟脱敏通知'); return 'dry-run'; }
  if (!selected()) { log('通知：未选中或全局关闭'); return 'disabled'; }
  let delivered = false;
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(d => path.join(d, 'sendNotify.js')).find(f => fs.existsSync(f));
  if (file) {
    delivered = await new Promise(resolve => {
      const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', file, TITLE, body], { stdio: 'ignore' });
      const timer = setTimeout(() => { child.kill('SIGKILL'); resolve(false); }, 20000);
      child.on('error', () => { clearTimeout(timer); resolve(false); });
      child.on('close', code => { clearTimeout(timer); resolve(code === 0); });
    });
  }
  if (process.env.TGTOKEN && process.env.TGID) {
    try {
      if (!/^\d+:[\w-]+$/.test(process.env.TGTOKEN)) fail('TG 参数格式错误');
      const r = await request(`https://api.telegram.org/bot${process.env.TGTOKEN}/sendMessage`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chat_id: process.env.TGID, text: `${TITLE}\n${body}` }) });
      if (r.data.ok !== true) fail('TG 通知未成功');
      delivered = true;
    } catch { log('通知：官方 TG 发送失败（详情已抑制）'); }
  }
  log(delivered ? '通知：脱敏汇总已发送' : '通知：青龙模块不可用或发送失败，保留业务退出码');
  return delivered ? 'sent' : 'unavailable';
}
async function main() {
  const loads = entries();
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${loads.length}`);
  const results = [];
  for (let i = 0; i < loads.length; i++) results.push(await runAccount(loads[i], i + 1));
  if (!loads.length) log('❌ 配置错误：请设置 CF_WORKERS_ACCOUNTS 或完整旧版单账号参数');
  const failed = results.filter(r => ['failure','configuration-error'].includes(r.status)).length;
  const success = results.filter(r => r.status === 'success').length;
  const status = !loads.length || results.every(r => r.status === 'configuration-error') ? 'configuration-error' : failed ? (failed < loads.length ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const code = failed || !loads.length ? 1 : 0;
  log('----------------------------------------');
  const body = `状态：${status}；账号总数：${loads.length}；成功：${success}；失败：${failed}；预演：${results.filter(r => r.status === 'dry-run').length}；配置错误：${!loads.length || results.some(r => r.status === 'configuration-error') ? '是' : '否'}`;
  log(body);
  let notification;
  try { notification = await notify(body); } catch { notification = 'unavailable'; log('通知：发送异常，保留业务退出码'); }
  const finishedAt = new Date().toISOString();
  log(`子任务统计：${JSON.stringify(results.reduce((s,r) => { for (const k of Object.keys(s)) s[k] += r[k]; return s; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }))}`);
  log(`完成时间：${finishedAt}；总耗时：${Date.now()-started}ms；最终状态：${status}；通知：${notification}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, status, mode: dry ? 'dry-run' : 'live', accounts: loads.length, success, failed, results, notification, finishedAt, durationMs: Date.now()-started }));
  process.exitCode = code;
}
main().catch(() => { process.exitCode = 1; console.error('任务运行异常，详细信息已抑制'); });
