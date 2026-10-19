// name: 媓钻护肤品
// cron: 40 0 * * *
/**
 * name: 媓钻护肤品
 * cron: 29 11 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_hzhfp.js (2024/08/18)
 * 小程序：#小程序://媓钻/gANSWauVDzi4SPH
 * 在本人已登录的小程序中抓取 api.hzyxhfp.com 请求头 Authorization，
 * 去掉开头 Bearer 后填入 HZHFP_TOKEN；每个非空行一个账号，不支持 & 分隔。
 * HZHFP_DRY_RUN=1：完全断网演练，通知仅本地输出；不会校验凭据或签到。
 * QINGLONG_NOTIFY=0/false/no/off：关闭通知。可用 QINGLONG_NOTIFY_DIR 指定通知模块目录。
 * Node.js >=18；业务 HTTP 仅使用标准库；不下载或安装其他组件。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["400481011873c4b0", "scripts/sudojia_hzhfp.js", "sudojia_hzhfp.js", "sudojia_hzhfp"];
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
const dry = process.env.HZHFP_DRY_RUN === '1';
const tokens = (process.env.HZHFP_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const started = Date.now();
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = s => console.log(`[${stamp()}] ${s}`);
const seconds = ms => `${(ms / 1000).toFixed(2)}秒`;
const stats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const accounts = [];
function request(endpoint, token) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const done = (err, value) => { if (settled) return; settled = true; clearTimeout(timer); err ? reject(err) : resolve(value); };
    const req = https.request({ hostname: 'api.hzyxhfp.com', path: endpoint, method: 'POST', headers: {
      'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json;charset=UTF-8',
      app: 'wx3df7476c42cace5d', Accept: 'application/json',
      Referer: 'https://servicewechat.com/wx3df7476c42cace5d/377/page-frame.html',
      Authorization: `Bearer ${token}`
    } }, res => {
      let bytes = 0; const chunks = [];
      res.on('data', chunk => { bytes += chunk.length; if (bytes > 1048576) { done(new Error('响应超过大小限制')); res.destroy(); req.destroy(); } else chunks.push(chunk); });
      res.on('error', () => done(new Error('响应读取失败')));
      res.on('aborted', () => done(new Error('响应中断')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return done(new Error(`HTTP 状态异常（${res.statusCode}）`));
        let body;
        try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return done(new Error('响应不是有效 JSON')); }
        if (!body || body.code !== 0) return done(new Error('业务未确认成功（要求 code 为数字 0）'));
        if (!body.data || typeof body.data !== 'object' || Array.isArray(body.data)) return done(new Error('响应缺少有效 data'));
        done(null, body.data);
      });
    });
    const timer = setTimeout(() => { done(new Error('请求超过 15 秒')); req.destroy(); }, 15000);
    req.on('error', () => done(new Error('网络请求失败')));
    req.end();
  });
}
function numeric(value, field) {
  if (!['string', 'number'].includes(typeof value) || !/^\d+(\.\d+)?$/.test(String(value))) throw new Error(`${field}字段无效`);
  return String(value);
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  // 演练不载入通知模块：这些模块可能在导入或发送时访问网络。
  if (dry) { log(`⏭️ 演练通知（仅本地）：${body}`); return '演练本地通知'; }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(d => path.resolve(d, 'sendNotify.js')).find(p => fs.existsSync(p));
  if (!file) return '不可用（未找到 sendNotify.js）';
  return new Promise(resolve => {
    // 子进程隔离第三方通知日志，超时不影响业务退出码。
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', file, '媓钻护肤品', body], { stdio: 'ignore' });
    let ended = false;
    const finish = status => { if (ended) return; ended = true; clearTimeout(timer); resolve(status); };
    const timer = setTimeout(() => { child.kill('SIGKILL'); finish('失败（超时）'); }, 15000);
    child.on('error', () => finish('失败（无法启动通知）'));
    child.on('exit', code => finish(code === 0 ? '已发送' : '失败'));
  });
}
async function main() {
  console.log('========== 媓钻护肤品 ==========');
  log(`开始时间：${new Date(started).toISOString()} | 模式：${dry ? '断网演练' : '正式执行'} | 账号数：${tokens.length}`);
  let configError = tokens.length === 0;
  if (configError) log('❌ 配置错误：请设置 HZHFP_TOKEN，每行一个账号');
  for (let i = 0; i < tokens.length; i++) {
    const begin = Date.now();
    const count = { total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    log(`账号 ${i + 1} 开始`);
    const valid = !/[\s&\x00-\x1f\x7f]/.test(tokens[i]);
    if (!valid) { configError = true; log('❌ 账号格式错误：只填写去掉 Bearer 的凭据，每行一个账号'); }
    let authenticated = false;
    const stages = [
      ['用户信息', '/api/users/getUserDetailInfo', data => {
        if (typeof data.wx_nickname !== 'string') throw new Error('响应缺少昵称');
        // JSON 转义控制字符以避免日志注入；不输出手机号或其他字段。
        log(`✅ 昵称：${JSON.stringify(data.wx_nickname)}`); authenticated = true;
      }],
      ['每日签到', '/api/signInLog/addSignIn', data => log(`✅ 签到成功！已连续签到${numeric(data.cont_days, '连续签到天数')}天`)],
      ['积分查询', '/api/userRight/getUserRightDetail', data => log(`✅ 当前积分：${numeric(data.integral, '积分')}`)]
    ];
    for (let n = 0; n < stages.length; n++) {
      const at = Date.now(); const [label, endpoint, show] = stages[n];
      log(`账号 ${i + 1} 阶段 ${n + 1}/3：${label}`);
      if (!valid) { if (n === 0) count.failed++; else count.skipped++; log('⏭️ 配置无效，未请求'); }
      else if (dry) { count.skipped++; log(`⏭️ DRY_RUN：模拟 POST ${endpoint}，未发起请求`); }
      else if (n === 1 && !authenticated) { count.skipped++; log('⏭️ 用户信息未验证，跳过签到'); }
      else {
        try { show(await request(endpoint, tokens[i])); count.success++; }
        catch (e) { count.failed++; log(`❌ ${e.message}`); }
      }
      log(`阶段 ${n + 1} 结束，耗时 ${seconds(Date.now() - at)}`);
    }
    const ok = valid && count.failed === 0 && (dry || count.success === 3);
    accounts.push({ account: i + 1, status: ok ? (dry ? 'dry-run' : 'success') : 'failure', ...count, elapsedMs: Date.now() - begin });
    for (const key of Object.keys(stats)) stats[key] += count[key];
    log(`账号 ${i + 1} 统计：总任务 ${count.total}，成功 ${count.success}，已完成 ${count.alreadyComplete}，跳过 ${count.skipped}，失败 ${count.failed}；耗时 ${seconds(Date.now() - begin)}`);
  }
  const failed = accounts.filter(a => a.status === 'failure').length;
  const success = accounts.filter(a => a.status === 'success').length;
  const status = configError ? 'configuration-error' : failed ? (failed < accounts.length ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const exitCode = configError || failed ? 1 : 0;
  const body = `账号总数 ${tokens.length}，成功 ${success}，失败 ${failed}，演练 ${accounts.filter(a => a.status === 'dry-run').length}；状态 ${status}；子任务成功 ${stats.success}、失败 ${stats.failed}、跳过 ${stats.skipped}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '失败'; }
  console.log('--------------------------------');
  log(body); log(`通知状态：${notification}`);
  log(`完成时间：${new Date().toISOString()} | 总耗时：${seconds(Date.now() - started)} | 最终状态：${status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify({ task: '媓钻护肤品', mode: dry ? 'dry-run' : 'live', status, totalAccounts: tokens.length, success, failed, configurationError: configError, tasks: stats, accounts, notification, elapsedMs: Date.now() - started, exitCode })}`);
  process.exitCode = exitCode;
}
main();
