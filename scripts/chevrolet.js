// name: 雪佛兰APP签到
// cron: 0 8 * * *
/*
 * name: 雪佛兰APP签到
 * cron: 0 8 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者及来源：NaroisCool/naro-scripts，chevrolet.js
 * 原始说明：雪佛兰app签到；将抓包里的cpctoken放到xflCookie。
 * 本维护版本按 GPL-3.0 发布，保留上游署名。
 * Node.js >= 18，无第三方业务依赖。
 * CHEVROLET_ACCOUNTS：每行一个 cpctoken；兼容旧变量 xflCookie。
 * 在本人授权设备上抓取雪佛兰 APP 签到请求的 cpctoken 请求头值。
 * 不包含请求头名称，不使用 & 或 @ 分隔账号。签到会改变签到状态。
 * CHEVROLET_DRY_RUN=1：完全断网预演；通知调用也禁止网络。
 * 上游未提供定时配置，本版本建议每天 08:00 执行。
 */
'use strict';

const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '雪佛兰APP签到';
const dryRun = process.env.CHEVROLET_DRY_RUN === '1';
const started = Date.now();
const stats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const accountsResult = [];
let credentials = [];
let configurationError = false;

function safe(value) {
  let result = String(value).replace(/[\r\n\u0000-\u001f\u007f]/g, ' ');
  for (const token of credentials) result = result.split(token).join('[凭据已隐藏]');
  return result.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function log(message) {
  console.log(`[${new Date().toTimeString().slice(0, 8)}] ${safe(message)}`);
}

function checkIn(token) {
  if (dryRun) throw new Error('预演禁止业务请求');
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (error, data) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(data);
    };
    const req = https.request('https://ctwx.sgmlink.com/api/check/submit', {
      method: 'POST',
      headers: {
        Accept: 'application/json, text/plain, */*',
        cpctoken: token,
        userType: '1',
        source: '0',
        'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
        'Content-Type': 'application/json;charset=utf-8',
        Origin: 'https://ctwx.sgmlink.com',
        'User-Agent': 'Optional(Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MyChevy/7.20.0) MyChevy/7.20.0',
        Referer: 'https://ctwx.sgmlink.com/portal/',
        'Content-Length': '2'
      }
    }, res => {
      if (res.statusCode !== 200) {
        finish(new Error(`HTTP 状态 ${res.statusCode}，未确认签到成功`));
        res.destroy();
        return;
      }
      const chunks = [];
      let bytes = 0;
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 65536) {
          finish(new Error('响应超过大小限制'));
          res.destroy();
        } else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应中断')));
      res.on('end', () => {
        if (done) return;
        try { finish(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch { finish(new Error('响应不是有效 JSON')); }
      });
    });
    const timer = setTimeout(() => {
      finish(new Error('请求超过 15 秒时限'));
      req.destroy();
    }, 15000);
    req.on('error', () => finish(new Error('网络请求失败，未确认签到成功')));
    req.end('{}');
  });
}

function verified(response) {
  // 没有可核对的业务码资料，不猜测 0、200 或消息字符串的含义。
  return !!response && typeof response === 'object' && !Array.isArray(response)
    && response.success === true;
}

function identity(response) {
  const candidates = [response, response && response.data,
    response && response.data && response.data.user];
  for (const item of candidates) {
    if (!item || typeof item !== 'object') continue;
    for (const field of ['nickname', 'nickName', 'username', 'displayName', 'publicUid']) {
      if (typeof item[field] === 'string' || typeof item[field] === 'number') {
        if (String(item[field]).trim()) return safe(item[field]);
      }
    }
  }
  return '';
}

async function notify(summary) {
  if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) {
    log('⏭️ 通知已按 QINGLONG_NOTIFY 关闭');
    return 'disabled';
  }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(dir => path.resolve(dir, 'sendNotify.js')).find(p => fs.existsSync(p));
  if (!file) { log('⚠️ 未找到青龙 sendNotify.js，业务退出码保持不变'); return 'unavailable'; }
  // 通知在独立进程运行，屏蔽其原始日志；不把业务凭据传给通知器。
  const code = `
    if (process.env.NOTIFY_DRY_RUN === '1') {
      const denied = () => { throw new Error('dry-run 禁止网络'); };
      for (const name of ['http', 'https', 'http2', 'net', 'tls', 'dgram', 'dns']) {
        const mod = require('node:' + name);
        for (const key of Object.keys(mod)) if (typeof mod[key] === 'function') mod[key] = denied;
      }
      global.fetch = denied;
      const cp = require('node:child_process');
      for (const key of Object.keys(cp)) if (typeof cp[key] === 'function') cp[key] = denied;
    }
    Promise.resolve().then(() => require(process.env.NOTIFY_MODULE).sendNotify(
      process.env.NOTIFY_TITLE, process.env.NOTIFY_BODY
    )).then(() => { process.exit(0); }, () => { process.exit(1); });
  `;
  const env = { PATH: process.env.PATH || '', NOTIFY_MODULE: file,
    NOTIFY_TITLE: TITLE, NOTIFY_BODY: summary, NOTIFY_DRY_RUN: dryRun ? '1' : '0' };
  // 保留青龙通知渠道配置，但移除当前任务凭据及其别名。
  for (const [key, value] of Object.entries(process.env)) {
    if (key === 'CHEVROLET_ACCOUNTS' || key === 'xflCookie') continue;
    if (credentials.some(token => value.includes(token))) continue;
    env[key] = value;
  }
  const sent = await new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', code], { env, stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve(false); }, 10000);
    child.on('error', () => { clearTimeout(timer); resolve(false); });
    child.on('close', status => { clearTimeout(timer); resolve(status === 0); });
  });
  log(sent ? '✅ 通知调用完成' : '⚠️ 通知未送达，业务退出码保持不变');
  return sent ? 'sent' : (dryRun ? 'dry-run-network-blocked' : 'failed');
}

async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dryRun ? '断网预演' : '实际签到'}`);
  const input = process.env.CHEVROLET_ACCOUNTS !== undefined
    ? process.env.CHEVROLET_ACCOUNTS : (process.env.xflCookie || '');
  credentials = input.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  log(`账号总数：${credentials.length}`);
  if (!credentials.length) {
    configurationError = true;
    log('❌ 阶段 1 参数检查：缺少 CHEVROLET_ACCOUNTS（兼容 xflCookie）');
  }
  for (let i = 0; i < credentials.length; i++) {
    const begin = Date.now();
    const result = { account: i + 1, total: 1, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    stats.total++;
    log(`账号 ${i + 1} / 阶段 1：凭据格式检查`);
    try {
      // 不限制 token 中的分隔字符，仅拒绝 HTTP 请求头不允许的字符。
      if (/[^\x20-\x7e\x80-\xff]/.test(credentials[i])) throw new Error('凭据包含非法请求头字符');
      log(`✅ 参数检查通过；阶段耗时 ${Date.now() - begin} 毫秒`);
      const stageStart = Date.now();
      log(`账号 ${i + 1} / 阶段 2：${dryRun ? '模拟签到' : '提交签到'}`);
      if (dryRun) {
        result.skipped = 1;
        stats.skipped++;
        log(`✅ DRY_RUN_OK 账号 ${i + 1}：参数有效，未发送业务请求；阶段耗时 ${Date.now() - stageStart} 毫秒`);
      } else {
        const response = await checkIn(credentials[i]);
        const name = identity(response);
        if (name) log(`账号 ${i + 1} 官方身份：${name}`);
        if (!verified(response)) throw new Error('业务响应未含 success=true，未确认签到成功');
        result.success = 1;
        stats.success++;
        log(`✅ CHECKIN_SUCCESS 账号 ${i + 1}：签到成功；阶段耗时 ${Date.now() - stageStart} 毫秒`);
      }
    } catch (error) {
      result.failed = 1;
      stats.failed++;
      log(`❌ 账号 ${i + 1} 阶段失败：${error.message}；账号耗时 ${Date.now() - begin} 毫秒`);
    }
    result.elapsedMs = Date.now() - begin;
    accountsResult.push(result);
    log(`账号 ${i + 1} 统计：总任务 ${result.total}，成功 ${result.success}，已完成 ${result.alreadyComplete}，跳过 ${result.skipped}，失败 ${result.failed}；耗时 ${result.elapsedMs} 毫秒`);
  }
  const failed = accountsResult.filter(a => a.failed).length;
  const successful = accountsResult.length - failed;
  const status = configurationError ? 'configuration-error' : failed
    ? (successful ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
  process.exitCode = configurationError || failed ? 1 : 0;
  log('----------------------------------------');
  const body = `状态：${status}；模式：${dryRun ? '断网预演（未验证业务成功）' : '实际签到'}；账号总数 ${credentials.length}，成功数 ${dryRun ? 0 : successful}，失败数 ${failed}；预演通过数 ${dryRun ? successful : 0}；子任务成功 ${stats.success}，跳过 ${stats.skipped}，失败 ${stats.failed}`;
  log(body);
  let notification;
  try { notification = await notify(body); }
  catch { notification = 'failed'; log('⚠️ 通知异常，业务退出码保持不变'); }
  const finishTime = new Date().toISOString();
  log(`完成时间：${finishTime}；总耗时 ${Date.now() - started} 毫秒；最终状态 ${status}；通知 ${notification}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, mode: dryRun ? 'dry-run' : 'live',
    status, accountCount: credentials.length, successfulAccounts: dryRun ? 0 : successful,
    dryRunPassedAccounts: dryRun ? successful : 0, failedAccounts: failed,
    configurationError, tasks: stats, accounts: accountsResult, notification,
    elapsedMs: Date.now() - started, finishTime, exitCode: process.exitCode }));
}

main().catch(() => { process.exitCode = 1; console.error('❌ 任务执行器异常，未确认业务成功'); });
