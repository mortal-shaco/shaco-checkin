// name: 美的会员
// cron: 33 11 * * *
/**
 * name: 美的会员
 * cron: 33 11 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia，https://blog.imzjw.cn，2024/07/21
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_midea.js
 * 维护版：独立 HTTP、逐账号失败隔离、脱敏日志与离线预演。
 * MIDEA_COOKIE：在本人登录的美的会员微信小程序中，抓取 mvip.midea.cn
 * 请求头 Cookie 的完整值，每个非空行一个账号；不使用 & 分隔。
 * MIDEA_DRY_RUN=1：完全离线模拟，不验证凭据，不实际发送通知。
 * QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭；QINGLONG_NOTIFY_DIR 可指定通知模块目录。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const dry = process.env.MIDEA_DRY_RUN === '1';
const started = Date.now();
const accounts = (process.env.MIDEA_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const summary = { task: '美的会员', mode: dry ? 'dry-run' : 'live', accounts: accounts.length, success: 0, failed: 0, configurationError: false };
function log(s) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${s}`); }
function request(cookie, endpoint) {
  return new Promise((resolve, reject) => {
    let timer;
    const fail = () => reject(new Error('网络、超时或响应格式异常'));
    const req = https.get({ hostname: 'mvip.midea.cn', path: endpoint, method: 'GET', headers: {
      Cookie: cookie, 'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json',
      Accept: '*/*', 'Accept-Encoding': 'identity',
      Referer: 'https://servicewechat.com/wx03925a39ca94b161/437/page-frame.html'
    } }, res => {
      const chunks = []; let size = 0;
      res.on('data', chunk => { size += chunk.length; if (size > 1048576) res.destroy(new Error('oversized')); else chunks.push(chunk); });
      res.on('error', fail);
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error('HTTP 状态异常'));
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || data.errcode !== 0) return reject(new Error('业务未确认成功（凭据失效或接口拒绝）'));
          resolve(data.data);
        } catch { fail(); }
      });
    });
    timer = setTimeout(() => req.destroy(new Error('timeout')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', fail);
  });
}
function identity(info, cookie) {
  for (const key of ['nickname', 'Nickname', 'NickName', 'username', 'UserName', 'displayName', 'DisplayName', 'publicUid']) {
    const value = info[key];
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const text = String(value);
    // 防止凭据回显、手机号及控制字符注入日志；正常公开身份原样显示。
    if (text && !/[\r\n\x00-\x1f]/.test(text) && !/\d{11}/.test(text) && !cookie.includes(text)) log(`账号身份：${text}`);
  }
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) { log(`通知离线预演：${body}`); return '离线预演（未发送）'; }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(d => path.resolve(d, 'sendNotify.js')).find(f => fs.existsSync(f));
  if (!file) return '不可用（未找到 sendNotify.js）';
  // 隔离通知模块输出及退出行为，超时不影响业务退出码。
  return new Promise(resolve => {
    const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1));';
    const child = spawn(process.execPath, ['-e', code, file, '美的会员', body], { stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('失败（超时）'); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve('失败（无法启动）'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '发送失败'); });
  });
}
async function run() {
  log('========== 美的会员 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${summary.mode}；账号数：${accounts.length}`);
  if (!accounts.length) { summary.configurationError = true; log('❌ 配置错误：请设置 MIDEA_COOKIE，每行一个账号'); }
  for (let i = 0; i < accounts.length; i++) {
    const start = Date.now(); const stats = { total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }; let authenticated = false;
    log(`----- 账号 ${i + 1} -----`);
    const stages = [
      ['查询账号信息', '/next/mucuserinfo/getmucuserinfo', data => {
        if (!data || !data.userinfo || typeof data.userinfo !== 'object') throw new Error('账号信息字段缺失');
        identity(data.userinfo, accounts[i]);
        const level = data.userinfo.LevelName;
        if (typeof level === 'string' && /^[\p{L}\p{N} _-]{1,60}$/u.test(level) && !/\d{11}/.test(level) && !accounts[i].includes(level)) log(`会员等级：${level}`);
        authenticated = true;
      }],
      ['每日签到', '/my/score/create_daily_score', () => {}],
      ['查询积分与成长值', '/my/muc/get_growth_status', data => {
        for (const key of ['vipPoint', 'vipGrow']) if (!data || !/^[0-9]+(?:\.[0-9]+)?$/.test(String(data[key]))) throw new Error('积分或成长值字段异常');
        log(`当前积分：${data.vipPoint}；成长值：${data.vipGrow}`);
      }]
    ];
    for (let j = 0; j < stages.length; j++) {
      const t = Date.now(); const [name, endpoint, validate] = stages[j];
      log(`阶段 ${j + 1}/3：${name}`);
      try {
        if (j > 0 && !authenticated) { stats.skipped++; log('⏭️ 账号验证失败，跳过后续操作'); }
        else if (dry) { authenticated = true; stats.skipped++; log(`⏭️ DRY_RUN 阶段模拟：${name}，未发起请求`); }
        else { validate(await request(accounts[i], endpoint)); stats.success++; log(`✅ ${name}成功（errcode=0）`); }
      } catch (error) { stats.failed++; log(`❌ ${name}失败：${['网络、超时或响应格式异常', 'HTTP 状态异常', '业务未确认成功（凭据失效或接口拒绝）', '账号信息字段缺失', '积分或成长值字段异常'].includes(error.message) ? error.message : '请求或处理异常（详情已脱敏）'}`); }
      log(`阶段 ${j + 1} 耗时：${Date.now() - t}ms`);
    }
    for (const key of Object.keys(totals)) totals[key] += stats[key];
    if (stats.failed) summary.failed++; else summary.success++;
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${Date.now() - start}ms`);
  }
  const exitCode = summary.failed || summary.configurationError ? 1 : 0;
  summary.status = exitCode ? (summary.success ? 'partial-failure' : summary.configurationError ? 'configuration-error' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `模式：${summary.mode}；账号总数：${summary.accounts}；成功数：${summary.success}；失败数：${summary.failed}；状态：${summary.status}${dry ? '；成功数仅表示离线流程通过，未验证业务' : ''}`;
  summary.notification = await notify(body).catch(() => '发送失败');
  summary.tasks = totals; summary.durationMs = Date.now() - started;
  log('--------------------------------'); log(body);
  log(`子任务：总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`通知：${summary.notification}；总耗时：${summary.durationMs}ms`);
  log(`完成时间：${new Date().toISOString()}；最终状态：${summary.status}`);
  if (dry && !exitCode) log('DRY_RUN_OK');
  if (!dry && !exitCode) log('MIDEA_SUCCESS');
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
}
run();
