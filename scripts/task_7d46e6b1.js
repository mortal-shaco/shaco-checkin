// name: 云闪付签到
// cron: 59 15 8 * * *
/*
name: 云闪付签到
cron: 59 15 8 * * *
SPDX-License-Identifier: GPL-3.0
来源：NaroisCool/naro-scripts，云闪付签到.js
https://github.com/NaroisCool/naro-scripts
原始版本：c2ffa8af2089bd98e1ed623c7a25d49b60ca0fdd
原始说明：抓包域名https://youhui.95516.com/newsign/api/daily_sign_in
参数Authorization和Cookie分别对应变量名YSF_TOKEN和YSF_COOKIE

Node.js >= 18，无第三方业务依赖。
YSF_ACCOUNTS：每个非空行一个账号，Authorization|Cookie；只在第一个 | 分割。
优先使用 YSF_ACCOUNTS，兼容单账号 YSF_TOKEN + YSF_COOKIE（不可用换行拆分账号）。
在云闪付官方客户端进入签到页，使用本人授权的抓包工具获取上述 POST 请求头，
完整保留 Authorization（含可能的前缀）与 Cookie，不是登录密码，不分享抓包数据。
YSF_DRY_RUN=1：仅检查参数和请求结构，禁止业务及通知联网；输出本地通知预演。
YSF_CITY：可选 x-city 城市编码，默认保留上游 360900。
QINGLONG_NOTIFY=auto|1|0；auto 仅在 QINGLONG_NOTIFY_SCRIPTS 选中本任务时推送。
通知模块：QINGLONG_NOTIFY_DIR/sendNotify.js 或青龙标准 scripts/sendNotify.js。
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
    const identities = ["7d46e6b18960482b", "scripts/task_7d46e6b1.js", "task_7d46e6b1.js", "task_7d46e6b1"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');

const TITLE = '云闪付签到';
const CATALOG = '7d46e6b18960482b';
const URL = 'https://youhui.95516.com/newsign/api/daily_sign_in';
const started = Date.now();
const dry = /^(1|true|yes|on)$/i.test(process.env.YSF_DRY_RUN || '');
const stats = { accounts: 0, success: 0, failed: 0, tasks: 0, completed: 0, alreadyComplete: 0, skipped: 0, taskFailed: 0 };
const identities = [];
const dayResults = [];
const secrets = [];
let stage = 0;
const timestamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${timestamp()}] ${text}`);
function step(text) { log(`阶段 ${++stage}：${text}`); }

function accounts() {
  if (process.env.YSF_ACCOUNTS !== undefined) {
    return process.env.YSF_ACCOUNTS.split(/\r?\n/).map(x => x.trim()).filter(Boolean).map(line => {
      const at = line.indexOf('|');
      return at < 0 ? { invalid: true } : { token: line.slice(0, at).trim(), cookie: line.slice(at + 1).trim() };
    });
  }
  if (process.env.YSF_TOKEN || process.env.YSF_COOKIE) {
    return [{ token: (process.env.YSF_TOKEN || '').trim(), cookie: (process.env.YSF_COOKIE || '').trim() }];
  }
  return [];
}

function validate(account) {
  if (account.invalid || !account.token || !account.cookie) throw new Error('凭据不完整：需同一账号的 Authorization|Cookie');
  if (/[\r\n\x00-\x1f\x7f]/.test(account.token + account.cookie)) throw new Error('凭据含非法控制字符');
  secrets.push(account.token, account.cookie);
  // 同时保护 Cookie 内单个会话字段与 Authorization 的令牌部分。
  for (const field of account.cookie.split(';')) {
    const index = field.indexOf('=');
    if (index >= 0 && field.slice(index + 1).trim()) secrets.push(field.slice(index + 1).trim());
  }
  const token = account.token.split(/\s+/).pop();
  if (token) secrets.push(token);
}

function requestOptions(account, city) {
  return {
    method: 'POST',
    headers: {
      Host: 'youhui.95516.com', Accept: 'application/json, text/plain, /',
      Authorization: account.token, Cookie: account.cookie,
      'Sec-Fetch-Site': 'same-origin', 'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
      'x-city': city, 'Sec-Fetch-Mode': 'cors', 'Accept-Encoding': 'identity',
      Origin: 'https://youhui.95516.com', 'Content-Length': '2',
      'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/sa-sdk-ios (com.unionpay.chsp) (cordova 4.5.4) (updebug 0) (version 938) (UnionPay/1.0 CloudPay) (clientVersion 198) (language zh_CN) (upHtml) (walletMode 00)',
      Referer: 'https://youhui.95516.com/newsign/public/app/index.html',
      Connection: 'close', 'Content-Type': 'application/json', 'Sec-Fetch-Dest': 'empty'
    }
  };
}

function signIn(options) {
  if (dry) throw new Error('预演模式禁止网络请求');
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (error, data) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(data);
    };
    const req = https.request(URL, options, res => {
      let size = 0;
      const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 262144) {
          finish(new Error('响应超出大小限制'));
          res.destroy(); req.destroy();
        } else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应中断')));
      res.on('end', () => {
        if (done) return;
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error(`HTTP 状态 ${res.statusCode}，未验证成功`));
        if (res.headers['content-encoding'] && res.headers['content-encoding'] !== 'identity') return finish(new Error('服务返回不支持的压缩格式'));
        let data;
        try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch { return finish(new Error('响应不是有效 JSON')); }
        if (!data || typeof data !== 'object' || Array.isArray(data)) return finish(new Error('响应结构无效'));
        finish(null, data);
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超过 15 秒')); req.destroy(); }, 15000);
    req.on('error', () => finish(new Error('网络或 TLS 请求失败')));
    req.end('{}');
  });
}

function identity(data) {
  // 只读取明确的公开身份字段，绝不输出任意响应对象或服务端错误消息。
  for (const object of [data, data.userInfo, data.user]) {
    if (!object || typeof object !== 'object') continue;
    for (const key of ['nickname', 'nickName', 'username', 'displayName', 'publicUid', 'uid']) {
      const value = object[key];
      if (typeof value !== 'string' && typeof value !== 'number') continue;
      const text = String(value);
      if (!text || text.length > 128 || /[\r\n\x00-\x1f\x7f]|1[3-9]\d{9}/.test(text)) continue;
      if (secrets.some(secret => secret && text.includes(secret))) continue;
      return text;
    }
  }
  return '';
}
function days(value) { return Number.isSafeInteger(value) && value >= 0 ? String(value) : '未返回有效天数'; }

function selected() {
  const setting = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(setting)) return false;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (selection === undefined) return ['1', 'true', 'yes', 'on'].includes(setting);
  const names = [CATALOG, '云闪付签到.js', 'candidate.js', path.basename(__filename), __filename.replace(/\\/g, '/')];
  const scriptsAt = __filename.replace(/\\/g, '/').lastIndexOf('/scripts/');
  if (scriptsAt >= 0) names.push(__filename.replace(/\\/g, '/').slice(scriptsAt + 9));
  return selection.split(/[,;\s]+/).filter(Boolean).some(pattern => {
    const regex = new RegExp('^' + pattern.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(name => regex.test(name));
  });
}

async function notify(body) {
  if (!selected()) { log('⏭️ 通知未启用或未选中本任务'); return 'disabled'; }
  if (dry) { log(`通知预演（不联网）：${body.replace(/\n/g, '；')}`); return 'dry-run'; }
  const files = [
    process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    path.join(__dirname, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'
  ].filter(Boolean);
  const file = files.find(p => { try { return fs.statSync(p).isFile(); } catch { return false; } });
  if (!file) { log('⚠️ 未找到青龙 sendNotify.js，保留业务退出码'); return 'unavailable'; }
  // 隔离模块的输出与凭据环境，防止通知器打印凭据；通知失败不影响业务结果。
  return new Promise(resolve => {
    const env = { ...process.env };
    for (const key of ['YSF_ACCOUNTS', 'YSF_TOKEN', 'YSF_COOKIE']) delete env[key];
    const worker = spawn(process.execPath, ['-e', `
      let input=''; process.stdin.on('data', c=>input+=c);
      process.stdin.on('end', async()=>{try {
        const p=JSON.parse(input); const n=require(p.file);
        if(typeof n.sendNotify !== 'function') process.exit(1);
        await n.sendNotify(p.title,p.body); process.exit(0);
      } catch {process.exit(1);}});
    `], { env, stdio: ['pipe', 'ignore', 'ignore'] });
    let settled = false;
    const finish = status => { if (!settled) { settled = true; clearTimeout(timer); log(status === 'sent' ? '✅ 汇总通知已发送' : '⚠️ 通知失败，保留业务退出码'); resolve(status); } };
    const timer = setTimeout(() => { worker.kill('SIGKILL'); finish('failed'); }, 15000);
    worker.on('error', () => finish('failed'));
    worker.on('close', code => finish(code === 0 ? 'sent' : 'failed'));
    worker.stdin.on('error', () => finish('failed'));
    worker.stdin.end(JSON.stringify({ file: path.resolve(file), title: TITLE, body }));
  });
}

async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式签到'}`);
  step('读取账号与公共参数');
  const list = accounts();
  stats.accounts = list.length;
  log(`账号总数：${list.length}`);
  const city = process.env.YSF_CITY || '360900';
  let configurationError = false;
  log(`参数读取阶段耗时：${Date.now() - started}ms`);
  if (!list.length || !/^\d{6}$/.test(city)) {
    configurationError = true;
    log('❌ 配置错误：请填写 YSF_ACCOUNTS（或单账号 YSF_TOKEN 与 YSF_COOKIE），YSF_CITY 必须为六位城市编码');
  } else {
    // 先登记全部凭据，避免公开身份恰好包含其他账号凭据时泄漏。
    for (const account of list) { try { validate(account); } catch { /* 在对应账号阶段独立报告 */ } }
    for (let i = 0; i < list.length; i++) {
      const begin = Date.now();
      let ok = false;
      step(`账号 ${i + 1}：验证凭据并执行签到`);
      stats.tasks++;
      try {
        validate(list[i]);
        const options = requestOptions(list[i], city);
        if (dry) {
          log(`⏭️ 账号 ${i + 1}：DRY_RUN_OK，POST、请求头与空 JSON 请求体已构造；未发出请求`);
          stats.skipped++;
        } else {
          const data = await signIn(options);
          const name = identity(data);
          if (name) { log(`账号 ${i + 1} 身份：${name}`); identities.push(`账号 ${i + 1}：${name}`); }
          if (data.signedIn !== true) throw new Error('接口未返回 signedIn=true，签到未验证成功；请在官方客户端核对凭据或活动状态');
          stats.completed++;
          log(`✅ 账号 ${i + 1}：签到成功`);
          log(`目前连续签到天数为：${days(data.signInDays?.days)}`);
          log(`这个月连续签到天数：${days(data.signInDays?.current?.days)}`);
          dayResults.push(`账号 ${i + 1} 连续签到天数：${days(data.signInDays?.days)}；当月连续签到天数：${days(data.signInDays?.current?.days)}`);
        }
        stats.success++; ok = true;
      } catch (error) {
        stats.failed++; stats.taskFailed++;
        // 此处消息全部由本脚本生成，库异常统一处理，不打印请求配置或响应。
        const message = error instanceof Error && /^(凭据|响应|HTTP 状态|服务返回|请求超过|网络或 TLS|接口未返回)/.test(error.message) ? error.message : '执行失败，请检查参数格式';
        log(`❌ 账号 ${i + 1}：${message}`);
      }
      log(`账号 ${i + 1} 统计：总任务 1；成功 ${ok && !dry ? 1 : 0}；已完成 0；跳过 ${ok && dry ? 1 : 0}；失败 ${ok ? 0 : 1}；耗时 ${Date.now() - begin}ms`);
    }
  }
  const exitCode = configurationError || stats.failed ? 1 : 0;
  const status = configurationError ? 'configuration-error' : stats.failed ? (stats.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `状态：${status}\n账号总数：${stats.accounts}；成功：${stats.success}；失败：${stats.failed}\n子任务：${stats.tasks}；签到成功：${stats.completed}；跳过：${stats.skipped}；失败：${stats.taskFailed}${identities.length ? '\n' + identities.join('\n') : ''}${dayResults.length ? '\n' + dayResults.join('\n') : ''}`;
  step('汇总及通知');
  const notificationStarted = Date.now();
  let notification;
  try { notification = await notify(body); } catch { notification = 'failed'; log('⚠️ 通知异常，保留业务退出码'); }
  log(`汇总及通知阶段耗时：${Date.now() - notificationStarted}ms`);
  console.log('----------------------------------------');
  log(body.replace(/\n/g, '；'));
  const finished = new Date().toISOString();
  log(`完成时间：${finished}；总耗时：${Date.now() - started}ms；通知：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, mode: dry ? 'dry-run' : 'live', status, ...stats, notification, startedAt: new Date(started).toISOString(), finishedAt: finished, durationMs: Date.now() - started, exitCode }));
  process.exitCode = exitCode;
}

main().catch(() => { log('❌ 未预期的执行器错误'); process.exitCode = 1; });
