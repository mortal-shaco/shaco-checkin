#!/usr/bin/env node
// name: 飞客茶馆签到
// cron: 18 10 * * *
// SPDX-License-Identifier: GPL-3.0-only
// Derived from chavyleung/scripts, flyertea/flyertea.js and flyertea/flyertea.cookie.js.
// Upstream: https://github.com/chavyleung/scripts (GPL-3.0-only).
// 保留原作者署名；原文件未附额外版权声明。依 GPL-3.0-only 分发和修改。
// Node.js >=18；无第三方业务依赖。仅执行每日签到，不采集或打印凭据。
// FLYERTEA_ACCOUNTS：每个非空行一个 JSON 对象，格式见 contract.json。
// 登录飞客 App，在本人授权的 HTTPS 抓包中手动签到，取得 www.flyert.com
// plugin.php?id=k_misign:sign&operation=qiandao 的 Cookie 及查询参数
// version、appkey、appversion、formhash、token；将解码后的查询值放入 params 对象。
// 同一行：{"cookie":"本人请求的 Cookie","params":{"version":"原值",...}}。
// 不要分享抓包；过期后重新登录采集。不读取 box.dat，不需要代理脚本或其他仓库。
'use strict';

// qinglong-notification-policy: begin
(() => {
  const raw = process.env.QINGLONG_NOTIFY;
  if (raw !== undefined && String(raw).trim() !== '' && String(raw).trim().toLowerCase() !== 'auto') return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["c48b00b2cb36fe09", "scripts/flyertea.js", "flyertea.js", "flyertea"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const zlib = require('node:zlib');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const TITLE = '飞客茶馆签到';
const REQUIRED = ['version', 'appkey', 'appversion', 'formhash', 'token'];
const started = Date.now();
const enabled = v => /^(1|true|yes|on)$/i.test(v || '');
const disabled = v => /^(0|false|no|off)$/i.test(v || '');
const dry = enabled(process.env.FLYERTEA_DRY_RUN);
const secrets = [];
function log(message) {
  console.log(`[${new Date().toTimeString().slice(0, 8)}] ${message}`);
}
function identity(value) {
  let s = String(value).replace(/[\x00-\x1f\x7f\u2028\u2029]/g, ' ');
  for (const secret of secrets) if (secret) s = s.split(secret).join('[已隐藏]');
  return s.replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, '[手机号已隐藏]');
}
function accountLines() {
  if (process.env.FLYERTEA_ACCOUNTS !== undefined) {
    return process.env.FLYERTEA_ACCOUNTS.split(/\r?\n/).filter(s => s.trim()).map(raw => ({raw}));
  }
  // 旧 BoxJS 环境变量仅兼容单账号；不再访问私有文件。
  if (process.env.chavy_cookie_flyertea || process.env.chavy_token_flyertea) {
    return [{legacy: true, raw: process.env.chavy_token_flyertea || ''}];
  }
  return [];
}
function parseAccount(line) {
  let data;
  try { data = JSON.parse(line.raw); } catch { throw new Error('账号 JSON 格式错误'); }
  if (line.legacy) data = {cookie: process.env.chavy_cookie_flyertea, params: data};
  if (!data || typeof data !== 'object' || Array.isArray(data) ||
      typeof data.cookie !== 'string' || !data.cookie.trim() || /[\r\n\x00]/.test(data.cookie)) {
    throw new Error('缺少有效 Cookie');
  }
  const p = data.params;
  if (!p || typeof p !== 'object' || Array.isArray(p)) throw new Error('缺少 params 参数对象');
  for (const key of REQUIRED) {
    if (!['string', 'number'].includes(typeof p[key]) || !String(p[key]).trim() || /[\r\n\x00]/.test(String(p[key]))) {
      throw new Error(`缺少有效参数 ${key}`);
    }
  }
  secrets.push(data.cookie, ...data.cookie.split(';').map(s => s.slice(s.indexOf('=') + 1).trim()).filter(Boolean),
    ...REQUIRED.filter(k => k !== 'version' && k !== 'appversion').map(k => String(p[k])));
  return data;
}
function buildURL(p) {
  const url = new URL('https://www.flyert.com/plugin.php');
  const values = {id: 'k_misign:sign', operation: 'qiandao', from: 'insign', version: p.version,
    appcan: 'appcan', appkey: p.appkey, appversion: p.appversion, formhash: p.formhash, token: p.token};
  for (const [key, value] of Object.entries(values)) url.searchParams.set(key, String(value));
  return url;
}
function requestAccount(data) {
  return new Promise((resolve, reject) => {
    let req, stream, settled = false;
    const timer = setTimeout(() => finish(new Error('请求超时（15 秒）')), 15000);
    function finish(error, result) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) { if (stream) stream.destroy(); if (req) req.destroy(); reject(error); }
      else resolve(result);
    }
    try {
      req = https.get(buildURL(data.params), {headers: {
        Cookie: data.cookie, Accept: '*/*', 'Accept-Language': 'zh-Hans-CN;q=1',
        'User-Agent': 'FKForum/7.28.3 (iPhone 12; iOS 14.5; Scale/3.00)',
        'Accept-Encoding': 'gzip, deflate, br', Connection: 'close'
      }}, res => {
        // 不跟随重定向，避免将 Cookie 发往其他站点。
        res.on('error', () => finish(new Error('响应传输失败')));
        res.on('aborted', () => finish(new Error('响应中断')));
        if (res.statusCode !== 200) { res.resume(); finish(new Error(`HTTP 状态异常 ${res.statusCode}`)); return; }
        const enc = (res.headers['content-encoding'] || 'identity').toLowerCase();
        if (!['identity', 'gzip', 'deflate', 'br'].includes(enc)) {
          res.resume(); finish(new Error('响应编码不支持')); return;
        }
        stream = enc === 'identity' ? res : res.pipe(enc === 'br' ? zlib.createBrotliDecompress() : zlib.createUnzip());
        let size = 0, wireSize = 0;
        res.on('data', b => { wireSize += b.length; if (wireSize > 1048576) finish(new Error('响应过大')); });
        const chunks = [];
        stream.on('error', () => finish(new Error('响应解码失败')));
        stream.on('data', b => {
          size += b.length;
          if (size > 1048576) finish(new Error('响应过大'));
          else chunks.push(b);
        });
        stream.on('end', () => {
          if (settled) return;
          try { finish(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
          catch { finish(new Error('响应不是有效 JSON')); }
        });
      });
      req.on('error', () => finish(new Error('网络请求失败')));
    } catch { finish(new Error('无法建立请求（请检查参数格式）')); }
  });
}
function businessResult(result) {
  if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('业务响应结构异常');
  const messages = [result.Variables && result.Variables.Message, result.Message].filter(Boolean);
  // 仅接受上游明确约定的状态，绝不把 HTTP 200 或任意提示当成成功。
  if (messages.some(m => m.messageval === 'success')) return 'success';
  if (messages.some(m => m.messageval === 'error' && typeof m.messagestr === 'string' && m.messagestr.includes('只能签到一次'))) return 'alreadyComplete';
  throw new Error('签到未获业务成功确认（请检查登录凭据或接口变化）');
}
function reportIdentity(result) {
  const v = result && result.Variables;
  if (!v || typeof v !== 'object') return;
  const fields = [['member_username', '用户名'], ['nickname', '昵称'], ['username', '用户名'], ['displayname', '显示名称'], ['member_uid', '公开 UID'], ['uid', '公开 UID']];
  for (const [key, label] of fields) {
    if (['string', 'number'].includes(typeof v[key]) && String(v[key])) log(`账号身份 ${label}：${identity(v[key])}`);
  }
}
function selectionMatches(pattern, value) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
  return new RegExp(`^${escaped}$`).test(value);
}
function notify(summary) {
  const sw = process.env.QINGLONG_NOTIFY || 'auto';
  const list = process.env.QINGLONG_NOTIFY_SCRIPTS;
  const names = ['c48b00b2cb36fe09', 'flyertea/flyertea.js', 'checkin/flyertea.js', 'flyertea.js', path.basename(__filename)];
  const selected = list !== undefined && list.split(/[,;\s]+/).filter(Boolean).some(p => names.some(n => selectionMatches(p, n)));
  if (disabled(sw) || (!enabled(sw) && !selected)) return '已关闭（全局开关或未选中）';
  if (dry) return '预演已模拟（不调用通知网络）';
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(d => path.join(d, 'sendNotify.js')).find(f => fs.existsSync(f));
  if (!file) return '不可用（未找到 sendNotify.js，保留业务退出码）';
  const body = `状态：${summary.status}；账号总数 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${summary.failed}；签到成功 ${summary.tasks.success}，已完成 ${summary.tasks.alreadyComplete}，跳过 ${summary.tasks.skipped}。`;
  const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))';
  const child = spawnSync(process.execPath, ['-e', code, file, TITLE, body], {stdio: 'ignore', timeout: 12000});
  return child.status === 0 ? '已发送' : '发送失败或超时（保留业务退出码）';
}
async function main() {
  const lines = accountLines();
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '无网络预演' : '正式签到'}；账号数：${lines.length}`);
  const summary = {status: '', mode: dry ? 'dry-run' : 'live', accounts: lines.length, succeeded: 0, failed: 0,
    tasks: {total: lines.length, success: 0, alreadyComplete: 0, skipped: 0, failed: 0}, results: []};
  if (!lines.length) log('❌ 配置错误：请设置 FLYERTEA_ACCOUNTS，每个非空行一个账号 JSON');
  let configError = !lines.length;
  for (let i = 0; i < lines.length; i++) {
    const begin = Date.now();
    let stage = Date.now(), outcome = 'failed';
    log(`账号 ${i + 1} / 阶段 1：检查账号配置`);
    try {
      let data;
      try { data = parseAccount(lines[i]); } catch (e) { configError = true; throw e; }
      log(`✅ 阶段 1：必需参数齐全；耗时 ${Date.now() - stage}ms`);
      stage = Date.now();
      log(`账号 ${i + 1} / 阶段 2：${dry ? '模拟签到请求（不联网）' : '提交签到请求'}`);
      if (dry) {
        buildURL(data.params);
        outcome = 'skipped';
        log('⏭️ DRY_RUN_OK：配置与请求构造通过；未执行真实签到');
      } else {
        const result = await requestAccount(data);
        reportIdentity(result);
        outcome = businessResult(result);
        log(outcome === 'success' ? '✅ 签到结果: 成功' : '☑️ 签到结果: 成功 (重复签到)');
      }
      log(`阶段 2 结束；耗时 ${Date.now() - stage}ms`);
      summary.succeeded++;
    } catch (e) {
      // 只打印本脚本构造的固定错误，不输出网络异常、响应体或 URL。
      log(`❌ 账号 ${i + 1}：${e.message}；阶段耗时 ${Date.now() - stage}ms`);
      summary.failed++;
    }
    summary.tasks[outcome]++;
    const result = {account: i + 1, total: 1, success: outcome === 'success' ? 1 : 0,
      alreadyComplete: outcome === 'alreadyComplete' ? 1 : 0, skipped: outcome === 'skipped' ? 1 : 0,
      failed: outcome === 'failed' ? 1 : 0, durationMs: Date.now() - begin};
    summary.results.push(result);
    log(`账号 ${i + 1} 统计：总任务 1，成功 ${result.success}，已完成 ${result.alreadyComplete}，跳过 ${result.skipped}，失败 ${result.failed}，耗时 ${result.durationMs}ms`);
  }
  summary.status = !lines.length ? 'configuration-error' : summary.failed ? (summary.succeeded ? 'partial-failure' : configError ? 'configuration-error' : 'failure') : dry ? 'dry-run' : 'success';
  process.exitCode = !lines.length || summary.failed ? 1 : 0;
  log('阶段 3：发送脱敏汇总通知');
  const notifyStart = Date.now();
  try { summary.notification = notify(summary); } catch { summary.notification = '通知异常（保留业务退出码）'; }
  log(`阶段 3：${summary.notification}；耗时 ${Date.now() - notifyStart}ms`);
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`账号统计：总数 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${summary.failed}`);
  log(`子任务统计：总数 ${summary.tasks.total}，成功 ${summary.tasks.success}，已完成 ${summary.tasks.alreadyComplete}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}`);
  log(`总耗时 ${summary.durationMs}ms；完成时间 ${summary.finishedAt}；最终状态 ${summary.status}；通知 ${summary.notification}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
}
main();
