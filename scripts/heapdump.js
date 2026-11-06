#!/usr/bin/env node
// name: heapdump 每日签到
// cron: 23 10 * * *
/*
 * 来源：MartinDai/daily-sign-in，src/main/site/heapdump.ts
 * 版本：6e631d1a15a4a7e58bd999e9995f5eeb0ac10a92；上游许可：MIT。
 * 输入源码没有附加版权声明。保留原作者归属，独立实现请求和青龙入口。
 *
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
 * Node.js >=18；无第三方业务依赖。HEAPDUMP_ACCOUNTS：每行 账号|密码，
 * 只在第一个 | 分割，密码余下部分原样保留。账号密码来自本人 heapdump 网站账户。
 * 未设置新变量时兼容单账号 HEAPDUMP_ACCOUNT + HEAPDUMP_PASSWD。
 * HEAPDUMP_DRY_RUN=1 完全离线，仅验证配置和模拟阶段；不调用通知程序。
 * 原脚本未提供 cron；此处建议每天 09:10，由青龙任务设置调整。
 * 无发帖、评论、分享、积分消费或账户资料修改。
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
    const identities = ["a74ebfb1941959d9", "scripts/heapdump.js", "heapdump.js", "heapdump"];
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
const TITLE = 'heapdump 每日签到';
const CATALOG = 'a74ebfb1941959d9';
const DOMAIN = 'https://heapdump.cn';
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
const dry = /^(1|true|yes|on)$/i.test(process.env.HEAPDUMP_DRY_RUN || '');
const started = Date.now();
const summary = { task: TITLE, mode: dry ? 'dry-run' : 'live', accounts: 0, success: 0, failed: 0, simulated: 0, configurationErrors: 0, steps: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, results: [] };
function log(s) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${s}`); }
function failure(message) { return new Error(message); }
function accountsFromEnv() {
  if (process.env.HEAPDUMP_ACCOUNTS !== undefined) {
    return process.env.HEAPDUMP_ACCOUNTS.replace(/\r\n/g, '\n').split('\n').filter(line => line.trim()).map(line => {
      const at = line.indexOf('|');
      return at <= 0 ? { invalid: true } : { account: line.slice(0, at).trim(), passwd: line.slice(at + 1) };
    });
  }
  if (process.env.HEAPDUMP_ACCOUNT !== undefined || process.env.HEAPDUMP_PASSWD !== undefined) {
    return [{ account: process.env.HEAPDUMP_ACCOUNT, passwd: process.env.HEAPDUMP_PASSWD }];
  }
  return [];
}
function validAccount(a) {
  return !a.invalid && typeof a.account === 'string' && a.account.trim().length > 0 &&
    typeof a.passwd === 'string' && a.passwd.length > 0 && !/[\r\n\x00]/.test(a.account + a.passwd);
}
// 仅输出官方返回的身份字段，过滤控制字符以避免伪造日志；不输出登录账号或响应正文。
function showIdentity(result, credentials) {
  const objects = [result, result?.data, result?.data?.user, result?.data?.userInfo, result?.user, result?.userInfo];
  for (const object of objects) {
    if (!object || typeof object !== 'object') continue;
    for (const key of ['nickname', 'nickName', 'username', 'displayName', 'publicUid', 'uid']) {
      const val = object[key];
      if (typeof val !== 'string' && typeof val !== 'number') continue;
      const identity = String(val);
      if (!identity || /[\x00-\x1f\x7f]/.test(identity) || /\+?\d[\d -]{9,}\d/.test(identity) ||
          identity.includes(credentials.passwd) || (identity === credentials.account && /@/.test(identity))) continue;
      log(`官方账号身份（${key}）：${identity}`);
      return;
    }
  }
}
async function request(endpoint, options) {
  if (dry) throw failure('离线预演禁止网络请求');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(DOMAIN + endpoint, { ...options, signal: controller.signal, redirect: 'error' });
    if (response.status !== 200) {
      await response.body?.cancel();
      throw failure(response.status === 401 ? '认证失效（HTTP 401）' : `HTTP 状态异常（${response.status}）`);
    }
    const chunks = [];
    let bytes = 0;
    if (!response.body) throw failure('接口未返回响应内容');
    for await (const chunk of response.body) {
      bytes += chunk.length;
      if (bytes > 262144) { controller.abort(); throw failure('接口响应超过安全大小'); }
      chunks.push(chunk);
    }
    let json;
    try { json = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { throw failure('接口未返回有效 JSON'); }
    if (!json || typeof json !== 'object' || Array.isArray(json)) throw failure('接口响应结构异常');
    return { json, headers: response.headers };
  } catch (err) {
    // 只重抛自定义的固定诊断，禁止打印 fetch 的 URL、请求、响应或服务端 message。
    const allowed = /^(认证失效|HTTP 状态异常|接口未返回|接口响应)/;
    if (allowed.test(err.message)) throw err;
    throw failure(controller.signal.aborted ? '请求超时或响应过大' : '网络请求失败（未输出敏感详情）');
  } finally { clearTimeout(timer); }
}
function cookieHeader(headers) {
  const lines = typeof headers.getSetCookie === 'function' ? headers.getSetCookie() :
    (headers.get('set-cookie') || '').split(/,(?=\s*[^\s;,=]+\s*=)/);
  const cookies = new Map();
  for (const line of lines) {
    const pair = line.split(';', 1)[0].trim();
    const at = pair.indexOf('=');
    if (at < 1 || /[\r\n]/.test(pair)) continue;
    const name = pair.slice(0, at);
    if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(name)) continue;
    if (pair.slice(at + 1)) cookies.set(name, pair);
  }
  if (!cookies.size) throw failure('登录未返回有效会话 Cookie');
  return [...cookies.values()].join('; ');
}
async function runAccount(a, index) {
  const start = Date.now();
  const stats = { total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let stage = 1;
  let stageStart = Date.now();
  let badConfiguration = false;
  log(`账号 ${index} 开始`);
  try {
    log('阶段 1/2：检查配置并登录');
    if (!validAccount(a)) { badConfiguration = true; throw failure('账号配置无效；请使用每行 账号|密码 或完整旧变量'); }
    if (dry) {
      stats.skipped = 2;
      log(`⏭️ 阶段 1/2：配置有效，跳过登录（${Date.now() - stageStart}ms）`);
      log('⏭️ 阶段 2/2：跳过签到（0ms）');
      summary.simulated++;
    } else {
      const login = await request('/api/login/authentication/v1/login', {
        method: 'POST', headers: { 'User-Agent': UA, 'Content-Type': 'application/json' },
        body: JSON.stringify({ account: a.account, passwd: a.passwd })
      });
      if (login.json.code !== 0 && login.json.code !== '0') throw failure('登录业务校验失败（服务端详情已隐藏）');
      const cookie = cookieHeader(login.headers);
      showIdentity(login.json, a);
      stats.success++;
      log(`✅ 阶段 1/2：登录成功且取得会话（${Date.now() - stageStart}ms）`);
      stage = 2;
      stageStart = Date.now();
      log('阶段 2/2：提交签到');
      const signin = await request('/api/community/signin/addSignin', {
        method: 'POST', headers: { 'User-Agent': UA, Cookie: cookie }
      });
      if (signin.json.status !== true && signin.json.status !== 1) throw failure('签到业务校验失败；未确认成功（服务端详情已隐藏）');
      showIdentity(signin.json, a);
      stats.success++;
      summary.success++;
      log(`✅ 阶段 2/2：签到结果：成功（${Date.now() - stageStart}ms）`);
    }
  } catch (err) {
    stats.failed++;
    stats.skipped += 2 - stats.success - stats.failed;
    summary.failed++;
    if (badConfiguration) summary.configurationErrors++;
    log(`❌ 阶段 ${stage}/2：${err.message}（${Date.now() - stageStart}ms）`);
    if (stage === 1) log('⏭️ 阶段 2/2：前置步骤失败，跳过签到（0ms）');
  }
  for (const key of Object.keys(stats)) summary.steps[key] += stats[key];
  const elapsedMs = Date.now() - start;
  summary.results.push({ account: index, status: stats.failed ? 'failure' : dry ? 'dry-run' : 'success', ...stats, elapsedMs });
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${elapsedMs}ms`);
}
function selectedNotification() {
  const setting = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(setting)) return false;
  if (['1', 'true', 'yes', 'on'].includes(setting)) return true;
  const list = process.env.QINGLONG_NOTIFY_SCRIPTS;
  // 本维护任务属于默认通知名单；设置名单时完全替换默认名单。
  if (list === undefined) return true;
  const filename = path.basename(__filename);
  const names = [CATALOG, filename, `scripts/${filename}`, `checkin/${filename}`, __filename.replace(/\\/g, '/')];
  return list.split(/[,;\s]+/).filter(Boolean).some(selector => {
    const pattern = selector.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    return names.some(name => new RegExp(`^${pattern}$`).test(name));
  });
}
async function notify(body) {
  if (!selectedNotification()) return '已关闭';
  // 预演不能调用可能联网的青龙通知模块。
  if (dry) { log('⏭️ 离线通知预演：' + body); return '离线预演，未发送'; }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(dir => path.join(dir, 'sendNotify.js')).find(name => fs.existsSync(name));
  if (!file) return '通知模块不可用，业务退出码保持不变';
  return new Promise(resolve => {
    const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))';
    const child = spawn(process.execPath, ['-e', code, file, TITLE, body], { stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('通知超时，业务退出码保持不变'); }, 20000);
    child.once('error', () => { clearTimeout(timer); resolve('通知启动失败，业务退出码保持不变'); });
    child.once('close', status => { clearTimeout(timer); resolve(status === 0 ? '已发送' : '通知失败，业务退出码保持不变'); });
  });
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '离线预演' : '正式执行'}`);
  const accounts = accountsFromEnv();
  summary.accounts = accounts.length;
  log(`账号数量：${accounts.length}`);
  if (!accounts.length) {
    summary.configurationErrors++;
    log('❌ 配置错误：请设置 HEAPDUMP_ACCOUNTS（每行 账号|密码），或完整旧变量');
  }
  for (let i = 0; i < accounts.length; i++) await runAccount(accounts[i], i + 1);
}
(async () => {
  try { await main(); } catch { summary.configurationErrors++; log('❌ 任务异常终止（详情已隐藏）'); }
  const failed = summary.failed > 0 || summary.configurationErrors > 0;
  summary.status = failed ? (summary.success > 0 ? 'partial-failure' : summary.configurationErrors ? 'configuration-error' : 'failure') : dry ? 'dry-run' : 'success';
  const exitCode = failed ? 1 : 0;
  log('----------------------------------------');
  const body = `账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}，预演 ${summary.simulated}，配置错误 ${summary.configurationErrors}；最终状态 ${summary.status}`;
  log('任务统计：' + body);
  log(`子任务：总数 ${summary.steps.total}，成功 ${summary.steps.success}，已完成 ${summary.steps.alreadyComplete}，跳过 ${summary.steps.skipped}，失败 ${summary.steps.failed}`);
  try { summary.notification = await notify(body); } catch { summary.notification = '通知异常，业务退出码保持不变'; }
  summary.elapsedMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  log(`通知状态：${summary.notification}`);
  log(`完成时间：${summary.finishedAt}；耗时 ${summary.elapsedMs}ms；最终状态：${summary.status}`);
  if (!failed && dry) log('DRY_RUN_OK：配置校验完成，无网络及签到副作用');
  if (!failed && !dry) log('HEAPDUMP_SUCCESS：全部账号签到成功');
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
})();
