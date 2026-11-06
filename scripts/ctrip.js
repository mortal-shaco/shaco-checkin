// name: 携程旅行签到
// cron: 11 10 * * *
/*
 * name: 携程旅行签到
 * cron: 0 8 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 携程旅行签到脚本，原作者：@NobyDa，原更新时间：2024/05/09
 * 来源：NobyDa/Script，Ctrip-DailyBonus/Ctrip.js
 * 原通用运行环境署名：https://github.com/chavyleung/scripts/blob/master/Env.min.js
 * 本维护版以 Node.js 内置 HTTPS 实现请求，不再包含代理环境或本地授权存储。
 *
 * CTRIP_AUTH（必填）：每个非空行填写一个账号的 head.auth 授权值。
 * 兼容原格式：{"account":{"账号标识":{"auth":"授权值"}}}。
 * 获取方式：在本人设备登录携程旅行微信小程序或 https://m.ctrip.com/，
 * 在本人授权的网络调试工具中查看携程请求 JSON 的 head.auth；原授权响应的
 * ticket 也是原脚本存入 auth 的值。不得公开抓包记录，多账号不要退出登录。
 * 本脚本不截获、不写入、不删除授权；失效后手动重新登录并更新环境变量。
 * CTRIP_BARK_KEY：可选 Bark APP 推送密钥；不影响签到结果。
 * CTRIP_DRY_RUN=1：断网预演，禁止业务请求、Bark 和通知模块执行。
 * QINGLONG_NOTIFY=auto|1|0：全局通知开关；auto 默认选中本任务。
 * QINGLONG_NOTIFY_SCRIPTS：可按目录相对路径、文件名、通配符或目录 ID 选择；
 * 设置后覆盖默认列表，空值关闭全部。QINGLONG_NOTIFY_DIR 指向 sendNotify.js 所在目录。
 * Node.js >=18；无第三方业务依赖。上游未指定定时表达式，默认每日 08:00。
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
    const identities = ["5e853b28200fc8af", "scripts/ctrip.js", "ctrip.js", "ctrip"];
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
const TITLE = '携程旅行签到';
const CATALOG = '5e853b28200fc8af';
const started = Date.now();
const dryRun = /^(1|true|yes|on)$/i.test(process.env.CTRIP_DRY_RUN || '');
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21E219 MicroMessenger/8.0.49';
const secrets = [process.env.CTRIP_AUTH, process.env.CTRIP_BARK_KEY].filter(Boolean);
function safe(value) {
  let s = String(value);
  for (const secret of secrets) s = s.split(secret).join('[凭据已隐藏]');
  return s.replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, '[手机号已隐藏]').replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
}
function log(message) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${safe(message)}`); }
function seconds(t) { return ((Date.now() - t) / 1000).toFixed(2); }

function parseAccounts(raw) {
  if (!raw || !raw.trim()) throw new Error('缺少必填环境变量 CTRIP_AUTH');
  if (raw.trim().startsWith('{')) {
    let parsed;
    try { parsed = JSON.parse(raw); } catch { throw new Error('CTRIP_AUTH 旧版 JSON 格式无效'); }
    if (!parsed || !parsed.account || typeof parsed.account !== 'object' || Array.isArray(parsed.account)) {
      throw new Error('CTRIP_AUTH 旧版 JSON 必须包含 account 对象');
    }
    const accounts = Object.values(parsed.account).map(v => ({auth: v && typeof v.auth === 'string' ? v.auth.trim() : ''}));
    if (!accounts.length) throw new Error('CTRIP_AUTH 没有账号');
    return accounts;
  }
  return raw.split(/\r?\n/).map(v => v.trim()).filter(Boolean).map(auth => ({auth}));
}

// 不跟随重定向、不自动重试签到；限制总时间和响应大小，不输出原始响应或错误对象。
function postJson(url, data, timeout = 15000) {
  if (dryRun) return Promise.reject(new Error('预演模式禁止网络请求'));
  return new Promise((resolve, reject) => {
    let settled = false;
    let req;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(value);
    };
    const timer = setTimeout(() => {
      finish(new Error('请求超时，服务端状态未知'));
      if (req) req.destroy();
    }, timeout);
    const body = JSON.stringify(data);
    try {
      req = https.request(url, {method: 'POST', headers: {
        'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body),
        'User-Agent': UA, Accept: 'application/json', 'Accept-Encoding': 'identity'
      }}, res => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          finish(new Error(`HTTP 请求失败（${res.statusCode}）`));
          res.destroy();
          return;
        }
        const chunks = [];
        let bytes = 0;
        res.on('data', chunk => {
          bytes += chunk.length;
          if (bytes > 262144) {
            finish(new Error('响应超过大小限制'));
            res.destroy();
          } else chunks.push(chunk);
        });
        res.on('end', () => {
          if (settled) return;
          try {
            const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
            if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error();
            finish(null, value);
          } catch { finish(new Error('响应不是有效 JSON 对象')); }
        });
        res.on('error', () => finish(new Error('响应传输失败')));
        res.on('aborted', () => finish(new Error('响应被中断')));
      });
      req.on('error', () => finish(new Error('网络请求失败')));
      req.end(body);
    } catch { finish(new Error('请求初始化失败')); }
  });
}

function showIdentity(body, index) {
  // 只读取官方身份白名单，不遍历未知字段、不使用本地账号标签或设备字段。
  for (const object of [body, body.userInfo]) {
    if (!object || typeof object !== 'object') continue;
    for (const key of ['nickname', 'nickName', 'username', 'userName', 'displayName', 'uid']) {
      if (['string', 'number'].includes(typeof object[key]) && String(object[key]).trim()) {
        log(`账号 ${index} 官方身份（${key}）：${object[key]}`);
      }
    }
  }
}

async function runAccount(account, index) {
  const t = Date.now();
  const stats = {index, total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
  log(`账号 ${index} 开始`);
  if (!account.auth) {
    stats.failed = 2;
    log(`❌ 账号 ${index} 配置错误：缺少有效 auth；阶段 1 签到、阶段 2 积分查询均失败`);
  } else {
    for (const stage of [1, 2]) {
      const stepStart = Date.now();
      const name = stage === 1 ? '每日签到' : '积分查询';
      log(`账号 ${index} 阶段 ${stage}/2：${name}`);
      if (dryRun) {
        stats.skipped++;
        log(`⏭️ 账号 ${index} ${name}：离线预演，未请求、未验证业务成功；耗时 ${seconds(stepStart)} 秒`);
        continue;
      }
      try {
        const body = await postJson(stage === 1
          ? 'https://m.ctrip.com/restapi/soa2/22769/signToday'
          : 'https://m.ctrip.com/restapi/soa2/15634/json/getPointsOrderUserInfo',
        stage === 1 ? {head: {auth: account.auth}} : {needUserInfo: true, head: {auth: account.auth}});
        showIdentity(body, index);
        if (stage === 1) {
          if (body.code === 0 || body.code === '0') {
            stats.success++;
            log(`✅ 账号 ${index} 签到成功；耗时 ${seconds(stepStart)} 秒`);
          } else if (body.code === 400001 || body.code === '400001') {
            stats.alreadyComplete++;
            log(`☑️ 账号 ${index} 今日已签到；耗时 ${seconds(stepStart)} 秒`);
          } else if (body.code === 404001 || body.code === '404001') {
            throw new Error('登录失效，请重新获取授权；未删除账号');
          } else throw new Error('签到未返回已知成功业务码');
        } else {
          if (body.isLogin !== true && body.isLogin !== 1) throw new Error('积分查询未确认登录状态');
          const credits = body.availableCredits;
          if (!['number', 'string'].includes(typeof credits) || String(credits).trim() === '' ||
              !Number.isFinite(Number(credits)) || Number(credits) < 0) throw new Error('积分查询缺少有效积分字段');
          stats.success++;
          log(`✅ 账号 ${index} 总积分：${Number(credits)}；耗时 ${seconds(stepStart)} 秒`);
        }
      } catch (error) {
        stats.failed++;
        log(`❌ 账号 ${index} ${name}失败：${error.message}；耗时 ${seconds(stepStart)} 秒`);
      }
    }
  }
  stats.durationSeconds = Number(seconds(t));
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationSeconds} 秒`);
  return stats;
}

function notificationSelected() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(mode)) return false;
  if (['1', 'true', 'yes', 'on'].includes(mode)) return true;
  if (mode !== 'auto') return false;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const names = [CATALOG, 'Ctrip.js', 'scripts/Ctrip.js', path.basename(__filename),
    path.relative(process.cwd(), __filename).replace(/\\/g, '/')];
  return process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(selector => {
    const regex = new RegExp('^' + selector.split('*').map(v => v.split('?').map(
      s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.')).join('.*') + '$');
    return names.some(name => regex.test(name));
  });
}

async function notify(summary) {
  if (!notificationSelected()) return '已由全局通知策略关闭';
  if (dryRun) return '离线预演：已生成脱敏通知摘要，未加载通知模块或发送 Bark';
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const moduleFile = dirs.map(dir => path.resolve(dir, 'sendNotify.js')).find(file => fs.existsSync(file));
  let result = '青龙通知模块不可用';
  if (moduleFile) {
    // 隔离通知模块的输出及异常，避免其泄漏推送凭据或改变业务退出码。
    result = await new Promise(resolve => {
      const runner = "Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))";
      const child = spawn(process.execPath, ['-e', runner, moduleFile, TITLE, summary], {stdio: 'ignore'});
      const timer = setTimeout(() => { child.kill('SIGKILL'); }, 15000);
      child.on('error', () => { clearTimeout(timer); resolve('青龙通知启动失败'); });
      child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '青龙通知已发送' : '青龙通知失败或超时'); });
    });
  }
  if (process.env.CTRIP_BARK_KEY) {
    try {
      const body = await postJson('https://api.day.app/push', {title: TITLE, body: summary,
        device_key: process.env.CTRIP_BARK_KEY, ext_params: {group: TITLE}}, 8000);
      result += body.code === 200 || body.code === '200' ? '；Bark 已发送' : '；Bark 未确认成功';
    } catch { result += '；Bark 发送失败'; }
  }
  return result;
}

async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；运行模式：${dryRun ? '离线预演' : '正式执行'}`);
  const results = [];
  let configError = false;
  let count = 0;
  try {
    const accounts = parseAccounts(process.env.CTRIP_AUTH);
    count = accounts.length;
    for (const account of accounts) if (account.auth) secrets.push(account.auth);
    log(`账号数量：${count}`);
    for (let i = 0; i < count; i++) results.push(await runAccount(accounts[i], i + 1));
  } catch (error) {
    configError = true;
    log(`账号数量：${count}；❌ 配置错误：${error.message}`);
  }
  const failed = results.filter(r => r.failed > 0).length;
  const successful = dryRun ? 0 : results.filter(r => r.failed === 0).length;
  const status = configError ? 'configuration-error' : failed
    ? (results.some(r => r.failed === 0) ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
  const exitCode = configError || failed ? 1 : 0;
  const totals = results.reduce((a, r) => {
    for (const k of ['total', 'success', 'alreadyComplete', 'skipped', 'failed']) a[k] += r[k];
    return a;
  }, {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0});
  const summary = `状态：${status}；账号总数 ${count}，成功 ${successful}，失败 ${failed}，配置错误 ${configError ? 1 : 0}；子任务总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`;
  let notification;
  try { notification = await notify(summary); } catch { notification = '通知不可用，保留业务退出码'; }
  console.log('----------------------------------------');
  log(summary);
  log(`通知状态：${notification}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${seconds(started)} 秒；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({task: TITLE, status, mode: dryRun ? 'dry-run' : 'live',
    accountCount: count, successfulAccounts: successful, failedAccounts: failed, configurationError: configError,
    totals, accounts: results, notification, durationSeconds: Number(seconds(started)), exitCode}));
  process.exitCode = exitCode;
}

main();
