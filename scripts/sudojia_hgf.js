// name: 厚工坊签到与任务
// cron: 44 1 * * *
/**
 * name: 厚工坊签到与任务
 * cron: 33 5 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 基于 sudojia/AutoTaskScript src/wx_mini/sudojia_hgf.js
 * 原作者 Telegram@sudojia；https://blog.imzjw.cn；2024/09/15
 * HGF_COOKIE：厚工坊商城微信小程序中抓取 api.hgf1862.com 请求头 sessionid，
 * 只填该值，每个非空行一个账号。不支持 & 或 @ 分隔账号。
 * HGF_DRY_RUN=1：完全断网预演；QINGLONG_NOTIFY=0：关闭通知。
 * Node.js >=18；仅使用标准库；不自动更新、下载或安装任何文件。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const dry = process.env.HGF_DRY_RUN === '1';
const accounts = (process.env.HGF_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const start = Date.now();
const stats = { total: accounts.length, success: 0, failed: 0, tasks: {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0} };
function log(s) { console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12: false})}] ${s}`); }
function dateVersion() {
  return new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date()).replace(/-/g, '');
}
function request(route, credential) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const req = https.request(new URL(route, 'https://api.hgf1862.com'), {method: 'POST', headers: {
      'User-Agent': 'Mozilla/5.0', Accept: 'application/json, text/javascript, */*; q=0.01',
      'x-requested-with': 'XMLHttpRequest', 'accept-language': 'zh-CN,zh;q=0.9',
      'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty',
      Cookie: `user=SessionID=${credential}`
    }}, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => { size += chunk.length; if (size > 262144) req.destroy(new Error('响应超过大小限制')); else chunks.push(chunk); });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP 状态异常 ${res.statusCode}`));
        try { const data = JSON.parse(Buffer.concat(chunks).toString('utf8')); if (!data || typeof data !== 'object' || Array.isArray(data)) throw 0; resolve(data); }
        catch { reject(new Error('响应格式无效')); }
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    req.end();
  });
}
function identity(data, credential) {
  for (const key of ['nickname', 'username', 'displayName', 'publicUid']) {
    const value = data[key];
    if (typeof value === 'string' && value && !value.includes(credential) && !/1[3-9]\d{9}/.test(value) && !/[\r\n\x00-\x1f]/.test(value)) log(`官方账号身份（${key}）：${value}`);
  }
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = files.find(p => fs.existsSync(p));
  if (!file) return '不可用：未找到 sendNotify.js，业务退出码保持不变';
  // 通知进程不接收账号凭据，输出不透传；预演阻止通知模块发出网络请求。
  const code = `if(process.env.NOTIFY_DRY==='1'){const deny=()=>{throw Error('dry-run network disabled')};for(const n of ['node:net','node:tls','node:http','node:https','node:http2','node:dgram','node:child_process']){const m=require(n);for(const k of ['connect','createConnection','request','get','createSocket','spawn','exec','execFile','fork','execSync','execFileSync','spawnSync'])if(k in m)m[k]=deny;}global.fetch=deny;}Promise.resolve(require(process.argv[1]).sendNotify('厚工坊签到与任务',process.argv[2])).then(()=>process.exit(0)).catch(()=>process.exit(1));`;
  return new Promise(resolve => {
    const env = {...process.env, NOTIFY_DRY: dry ? '1' : '0'}; delete env.HGF_COOKIE; delete env.NODE_OPTIONS;
    const child = spawn(process.execPath, ['-e', code, file, body], {env, stdio: 'ignore'});
    const timer = setTimeout(() => { child.kill('SIGKILL'); }, 20000);
    child.on('error', () => {clearTimeout(timer); resolve('发送失败，业务退出码保持不变');});
    child.on('close', c => {clearTimeout(timer); resolve(c === 0 ? '已发送' : (dry ? '预演通知已尝试，网络投递被禁止' : '发送失败，业务退出码保持不变'));});
  });
}
async function main() {
  log('========== 厚工坊签到与任务 ==========');
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry ? '断网预演' : '正式运行'}；账号数：${accounts.length}`);
  if (!accounts.length) { log('❌ 配置错误：请设置 HGF_COOKIE，每行一个 sessionid'); process.exitCode = 1; }
  for (let i = 0; i < accounts.length; i++) {
    const began = Date.now(); const credential = accounts[i]; const local = {total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
    const valid = !/[\s;&@]/.test(credential);
    const stages = [ ['每日签到', `/YUN//Game/2021/QianDao/QianDaoAjax_By28.aspx?op=now&vers=${dateVersion()}`], ['浏览小阿头条并领取任务奖励', '/YUN//Game/2024/RenWuJB/AjaxGo.aspx?cid=9'] ];
    for (let j = 0; j < stages.length; j++) {
      const tick = Date.now(); log(`账号 ${i + 1} · 阶段 ${j + 1}/2 ${stages[j][0]}`);
      try {
        if (!valid) throw new Error('凭据格式无效：只填 sessionid，每行一个账号');
        if (dry) { local.skipped++; log('⏭️ DRY_RUN_OK：已校验账号和请求计划，未发送请求、未改变账户状态'); }
        else {
          const data = await request(stages[j][1], credential); identity(data, credential);
          if (data.status !== 1) throw new Error('业务未确认成功（要求 status 为数字 1），请在小程序核实登录与任务状态');
          local.success++; log(`✅ ${stages[j][0]}成功`);
          if (j === 0 && Number.isFinite(data.jiubi)) log(`获得酒币：${data.jiubi}`);
          if (j === 0) await new Promise(r => setTimeout(r, 1200));
        }
      } catch (err) { local.failed++; log(`❌ ${err.message}`); }
      log(`阶段 ${j + 1} 耗时：${Date.now() - tick} 毫秒`);
    }
    for (const k of Object.keys(local)) stats.tasks[k] += local[k];
    if (local.failed) {stats.failed++; process.exitCode = 1;} else stats.success++;
    log(`账号 ${i + 1} 统计：总任务 ${local.total}，成功 ${local.success}，已完成 ${local.alreadyComplete}，跳过 ${local.skipped}，失败 ${local.failed}；耗时 ${Date.now() - began} 毫秒`);
  }
  const status = !accounts.length ? 'configuration-error' : stats.failed ? (stats.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `模式：${dry ? '断网预演' : '正式运行'}；账号总数 ${stats.total}，成功 ${stats.success}，失败 ${stats.failed}；子任务成功 ${stats.tasks.success}，跳过 ${stats.tasks.skipped}，失败 ${stats.tasks.failed}；最终状态 ${status}`;
  const notification = await notify(body);
  log('----------------------------------------'); log(body); log(`通知状态：${notification}`);
  log(`完成时间：${new Date().toISOString()}；总耗时：${Date.now() - start} 毫秒；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ ...stats, mode: dry ? 'dry-run' : 'live', status, notification, elapsedMs: Date.now() - start }));
}
main().catch(() => { process.exitCode = 1; log('❌ 任务发生未预期错误，未输出敏感详情'); });
