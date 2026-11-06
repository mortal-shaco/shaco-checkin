// name: 百果园小程序签到
// cron: 34 1 * * *
// SPDX-License-Identifier: GPL-3.0-only
// 来源：chavyleung/scripts，pagoda/pagoda.js、pagoda/pagoda.cookie.js。
// 原始作者归属与许可证保留；本维护版按 GPL-3.0-only 发布。
/**
 * 功能：重放百果园小程序签到 GET；0 为成功，35702 为已签到。
 * 原关联脚本只采集请求，不是额外账号任务；原计划为每日 00:10。
 * PAGODA_ACCOUNTS：每个非空行是一个 JSON 对象，包含 url、headers。
 * 获取：在自己设备受信任的抓包工具中，打开百果园小程序签到页，
 * 找到 https://wx-mini.pagoda.com.cn/api/v1/wxmini/signIn/customer
 * 请求，完整复制 URL（保留查询参数）和请求头，组成单行 JSON。
 * 不预设或猜测鉴权字段；保留实际请求中的 Cookie、Token 等鉴权头。
 * 也接受原 chavy_sign_pagoda 的相同 JSON；主变量设置时优先使用主变量。
 * 不读取 box.dat、不采集他人凭据、不保存会话；会话失效时重新采集。
 * PAGODA_DRY_RUN=1：只校验配置，不发出任何网络请求（包括通知）。
 * Node.js >=18，无第三方依赖。正式运行只产生签到副作用，不自动重试。
 * QINGLONG_NOTIFY=auto 默认仅通知选中脚本；1 强制开启，0 关闭。
 * QINGLONG_NOTIFY_SCRIPTS 可用目录路径、文件名、目录编号或文件名通配符，
 * 以逗号、分号或空白分隔；设置为空表示全部关闭，* 表示全部选中。
 * 通知模块为可选的青龙 sendNotify.js；缺失或失败不改变业务退出码。
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
    const identities = ["93a6cb1dedb6401b", "scripts/pagoda.js", "pagoda.js", "pagoda"];
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
const TITLE = '百果园小程序签到';
const ENDPOINT = '/api/v1/wxmini/signIn/customer';
const START = Date.now();
const dryRun = process.env.PAGODA_DRY_RUN === '1';
const sensitiveValues = new Set();
const clock = () => new Date().toTimeString().slice(0, 8);
const log = s => console.log(`[${clock()}] ${s}`);
const duration = start => `${((Date.now() - start) / 1000).toFixed(2)}秒`;
class TaskError extends Error {}

function parseAccount(line) {
  let account;
  try { account = JSON.parse(line); } catch { throw new TaskError('账号 JSON 格式错误'); }
  if (!account || typeof account !== 'object' || Array.isArray(account) || typeof account.url !== 'string') {
    throw new TaskError('账号必须包含完整 url 和 headers');
  }
  let url;
  try { url = new URL(account.url); } catch { throw new TaskError('签到 URL 格式错误'); }
  if (url.protocol !== 'https:' || url.hostname !== 'wx-mini.pagoda.com.cn' ||
      (url.port && url.port !== '443') || url.pathname !== ENDPOINT || url.username || url.password || url.hash) {
    throw new TaskError('签到 URL 必须是原百果园 HTTPS 签到接口');
  }
  if (account.method && String(account.method).toUpperCase() !== 'GET') {
    throw new TaskError('参考源码仅支持签到 GET 请求');
  }
  if (!account.headers || typeof account.headers !== 'object' || Array.isArray(account.headers) || !Object.keys(account.headers).length) {
    throw new TaskError('缺少实际采集的签到请求头');
  }
  const headers = {};
  for (const [key, value] of Object.entries(account.headers)) {
    if (typeof value !== 'string' || !/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(key) || /[^\t\x20-\xff]/.test(value)) {
      throw new TaskError('请求头格式错误');
    }
    sensitiveValues.add(value);
    // Host 由固定 URL 生成，禁止用户控制代理或请求分帧。
    if (/^(host|content-length|content-type|connection|transfer-encoding|accept-encoding|proxy-.*)$/i.test(key)) continue;
    headers[key.toLowerCase()] = value;
  }
  for (const value of url.searchParams.values()) if (value) sensitiveValues.add(value);
  headers['accept-encoding'] = 'identity';
  return { url, headers };
}

function requestSign(account) {
  if (dryRun) throw new TaskError('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    let finished = false;
    let timer;
    const finish = (error, value) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(value);
    };
    const req = https.request(account.url, { method: 'GET', headers: account.headers }, res => {
      if (res.statusCode < 200 || res.statusCode >= 300) {
        finish(new TaskError(`签到 HTTP 状态异常（${res.statusCode}），未跟随重定向`));
        res.destroy();
        return;
      }
      let size = 0;
      const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) {
          finish(new TaskError('签到响应超出大小限制'));
          res.destroy();
        } else chunks.push(chunk);
      });
      res.on('error', () => finish(new TaskError('签到响应读取失败')));
      res.on('aborted', () => finish(new TaskError('签到响应中断')));
      res.on('end', () => {
        if (finished) return;
        let value;
        try { value = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch { finish(new TaskError('签到响应不是有效 JSON')); return; }
        if (!value || typeof value !== 'object' || Array.isArray(value)) {
          finish(new TaskError('签到响应结构不符合约定')); return;
        }
        finish(null, value);
      });
    });
    timer = setTimeout(() => { finish(new TaskError('签到请求超时（15秒）')); req.destroy(); }, 15000);
    req.on('error', () => finish(new TaskError('签到网络或 TLS 请求失败')));
    req.end();
  });
}

function showIdentity(response) {
  const containers = [response, response.data, response.data?.customer, response.data?.user];
  for (const obj of containers) {
    if (!obj || typeof obj !== 'object') continue;
    for (const key of ['nickname', 'nickName', 'username', 'userName', 'displayName', 'publicUid']) {
      const value = obj[key];
      if (typeof value !== 'string' && typeof value !== 'number') continue;
      const identity = String(value);
      // 只展示明确的非凭据身份字段，不推测 token、手机号或设备 ID 为身份。
      if (!identity || /[\r\n\x00-\x1f\x7f]/.test(identity) || /(?:\+?86)?1[3-9]\d{9}/.test(identity) ||
          [...sensitiveValues].some(secret => secret && identity.includes(secret))) continue;
      log(`账号身份：${identity}`);
      return;
    }
  }
}

function notificationSelected() {
  const setting = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(setting)) return false;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (selection !== undefined) {
    const candidates = ['93a6cb1dedb6401b', 'pagoda.js', 'pagoda/pagoda.js', 'candidate.js', path.basename(__filename)];
    return selection.split(/[,;\s]+/).filter(Boolean).some(pattern => {
      const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
      return candidates.some(name => new RegExp(`^${escaped}$`).test(name));
    });
  }
  return ['1', 'true', 'yes', 'on'].includes(setting);
}

async function notify(summary) {
  if (dryRun) return '预演跳过，未调用通知模块';
  if (!notificationSelected()) return '未选中或已关闭';
  const files = [
    process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'
  ].filter(Boolean);
  const file = files.find(f => fs.existsSync(f));
  if (!file) return '通知模块不可用，保留业务退出码';
  const body = `状态：${summary.status}\n账号总数：${summary.accounts}，成功：${summary.success}，失败：${summary.failed}\n已签到：${summary.alreadyComplete}，跳过：${summary.skipped}`;
  return new Promise(resolve => {
    let settled = false;
    let timer;
    const finish = message => { if (!settled) { settled = true; clearTimeout(timer); resolve(message); } };
    const code = 'Promise.resolve().then(()=>{const m=require(process.argv[1]);if(typeof m.sendNotify!=="function")throw Error();return m.sendNotify(process.argv[2],process.argv[3]);}).then(()=>process.exit(0),()=>process.exit(1));';
    const child = spawn(process.execPath, ['-e', code, file, TITLE, body], { stdio: 'ignore', shell: false });
    timer = setTimeout(() => { child.kill('SIGKILL'); finish('通知超时，保留业务退出码'); }, 15000);
    child.on('error', () => finish('通知启动失败，保留业务退出码'));
    child.on('close', code => finish(code === 0 ? '通知已发送' : '通知失败，保留业务退出码'));
  });
}

async function main() {
  const raw = process.env.PAGODA_ACCOUNTS !== undefined ? process.env.PAGODA_ACCOUNTS : (process.env.chavy_sign_pagoda || '');
  const lines = raw.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const summary = { task: TITLE, mode: dryRun ? 'dry-run' : 'live', accounts: lines.length,
    success: 0, failed: 0, alreadyComplete: 0, skipped: 0, configurationErrors: 0, results: [] };
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(START).toISOString()}；模式：${dryRun ? '断网预演' : '正式签到'}；账号数：${lines.length}`);
  log('阶段 1 配置检查：每个非空行独立处理，不输出请求或凭据');
  if (!lines.length) {
    summary.configurationErrors++;
    log('❌ 配置错误：请设置 PAGODA_ACCOUNTS（兼容 chavy_sign_pagoda）');
  }
  for (let i = 0; i < lines.length; i++) {
    const start = Date.now();
    const result = { account: i + 1, total: 1, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    log(`账号 ${i + 1} / 阶段 1 参数校验开始`);
    let account;
    try {
      account = parseAccount(lines[i]);
      log(`账号 ${i + 1} / 阶段 1 ✅ 参数校验通过；耗时 ${duration(start)}`);
    } catch (e) {
      summary.configurationErrors++;
      result.failed++;
      log(`账号 ${i + 1} / 阶段 1 ❌ ${e instanceof TaskError ? e.message : '参数校验失败'}；耗时 ${duration(start)}`);
    }
    if (account) {
      const stageStart = Date.now();
      log(`账号 ${i + 1} / 阶段 2 小程序签到开始`);
      try {
        if (dryRun) {
          result.skipped++;
          log(`账号 ${i + 1} / 阶段 2 ⏭️ DRY_RUN_OK：配置有效，未发送签到请求；耗时 ${duration(stageStart)}`);
        } else {
          const response = await requestSign(account);
          showIdentity(response);
          if (response.errorCode === 0) {
            result.success++;
            log(`账号 ${i + 1} / 阶段 2 ✅ 签到成功（errorCode=0）；耗时 ${duration(stageStart)}`);
          } else if (response.errorCode === 35702) {
            result.alreadyComplete++;
            log(`账号 ${i + 1} / 阶段 2 ☑️ 已签到（errorCode=35702）；耗时 ${duration(stageStart)}`);
          } else throw new TaskError('签到未通过业务成功检查，请更新会话或人工核对');
        }
      } catch (e) {
        result.failed++;
        log(`账号 ${i + 1} / 阶段 2 ❌ ${e instanceof TaskError ? e.message : '签到处理失败'}；耗时 ${duration(stageStart)}`);
      }
    }
    if (result.failed) summary.failed++;
    else if (dryRun) summary.skipped++;
    else summary.success++;
    summary.alreadyComplete += result.alreadyComplete;
    result.durationMs = Date.now() - start;
    summary.results.push(result);
    log(`账号 ${i + 1} 统计：总任务 ${result.total}，成功 ${result.success}，已完成 ${result.alreadyComplete}，跳过 ${result.skipped}，失败 ${result.failed}；耗时 ${duration(start)}`);
  }
  const exitCode = summary.configurationErrors || summary.failed ? 1 : 0;
  summary.status = summary.configurationErrors ? 'configuration-error' : summary.failed ? (summary.success || summary.skipped ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
  process.exitCode = exitCode;
  const notifyStart = Date.now();
  log('阶段 3 脱敏总结通知开始');
  try { summary.notification = await notify(summary); }
  catch { summary.notification = '通知失败，保留业务退出码'; }
  log(`阶段 3 ${summary.notification}；耗时 ${duration(notifyStart)}`);
  summary.durationMs = Date.now() - START;
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`账号统计：总数 ${summary.accounts}，成功 ${summary.success}（含已签到 ${summary.alreadyComplete}），失败 ${summary.failed}，预演跳过 ${summary.skipped}；配置错误 ${summary.configurationErrors}`);
  log(`子任务统计：总数 ${summary.results.length}，成功 ${summary.results.reduce((n, r) => n + r.success, 0)}，已完成 ${summary.alreadyComplete}，跳过 ${summary.skipped}，失败 ${summary.failed}`);
  log(`完成时间：${summary.finishedAt}；总耗时：${duration(START)}；最终状态：${summary.status}；退出码：${exitCode}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
}

main().catch(() => {
  process.exitCode = 1;
  // 正常业务和配置错误均在 main 中收敛；此处只处理意外运行时故障。
  log('❌ 运行时异常，未输出原始错误或凭据');
});
