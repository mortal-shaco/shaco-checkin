// name: Follow 每日签到
// cron: 17 10 * * *
// SPDX-License-Identifier: GPL-3.0-only
// 上游：chavyleung/scripts，follow/follow.js
// 来源提交：bfab3c906f3d5d126e9094f15730e025f7f32128
// 保留上游作者归属；本维护版本沿用 GPL-3.0-only。
/*
 * Node.js >= 18，无第三方业务依赖。上游未指定 cron；建议每天 08:00。
 * FOLLOW_ACCOUNTS：每个非空行 csrfToken|Cookie，仅按第一个 | 切分。
 * 登录 Follow 网页，开发者工具 Network 中手动签到，查看
 * https://api.follow.is/wallets/transactions/claim_daily 的请求：
 * JSON 正文 csrfToken 和请求头 Cookie 必须属于同一账号；仅保存在私有环境变量。
 * 兼容单账号 follow_csrfToken + follow_cookie，不读取 box.dat。
 * FOLLOW_DRY_RUN=1 完全离线，只校验配置和模拟流程，不领取、不加载通知模块。
 * QINGLONG_NOTIFY=auto 默认未选择；配置 QINGLONG_NOTIFY_SCRIPTS 选择本任务，
 * 或 QINGLONG_NOTIFY=1 强制通知，=0 禁用。预演仅展示通知摘要。
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
    const identities = ["76f759b6f1d6f730", "scripts/follow.js", "follow.js", "follow"];
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
const TITLE = 'Follow 每日签到';
const CATALOG = '76f759b6f1d6f730';
const ENDPOINT = 'https://api.follow.is/wallets/transactions/claim_daily';
const TRUE = ['1', 'true', 'yes', 'on'];
const FALSE = ['0', 'false', 'no', 'off'];
const now = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${now()}] ${text}`);
const fault = code => Object.assign(new Error(code), { safeCode: code });

function parseAccounts(env) {
  if (Object.hasOwn(env, 'FOLLOW_ACCOUNTS')) {
    return env.FOLLOW_ACCOUNTS.split(/\r?\n/).map(s => s.trim()).filter(Boolean).map(line => {
      const pos = line.indexOf('|');
      return pos > 0 ? { csrfToken: line.slice(0, pos).trim(), cookie: line.slice(pos + 1).trim() } : { invalid: true };
    });
  }
  if (env.follow_csrfToken || env.follow_cookie) {
    return [{ csrfToken: env.follow_csrfToken || '', cookie: env.follow_cookie || '' }];
  }
  return [];
}
function validAccount(a) {
  return !a.invalid && typeof a.csrfToken === 'string' && !!a.csrfToken.trim() &&
    typeof a.cookie === 'string' && !!a.cookie.trim() &&
    !/[\r\n\x00-\x1f\x7f]/.test(a.csrfToken + a.cookie);
}
function claim(account) {
  return new Promise((resolve, reject) => {
    let done = false;
    let timer;
    const finish = (err, value) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      err ? reject(err) : resolve(value);
    };
    const payload = JSON.stringify({ csrfToken: account.csrfToken });
    const req = https.request(ENDPOINT, {
      method: 'POST',
      headers: {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.38(0x1800262c) NetType/4G Language/zh_CN',
        'Content-Type': 'application/json', Accept: '*/*', Cookie: account.cookie,
        'Content-Length': Buffer.byteLength(payload)
      }
    }, res => {
      const chunks = [];
      let bytes = 0;
      res.on('error', () => finish(fault('响应读取失败')));
      res.on('aborted', () => finish(fault('响应中断')));
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 1024 * 1024) {
          finish(fault('响应超过大小限制'));
          res.destroy(); req.destroy();
        } else chunks.push(chunk);
      });
      res.on('end', () => {
        if (done) return;
        if (!(res.statusCode >= 200 && res.statusCode < 300)) return finish(fault('HTTP 状态异常'));
        let body;
        try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch { return finish(fault('响应不是有效 JSON')); }
        if (!body || typeof body !== 'object' || Array.isArray(body) || body.code !== 0) {
          return finish(fault('签到未获业务成功确认（要求 code 为数字 0）'));
        }
        finish(null, body);
      });
    });
    timer = setTimeout(() => { finish(fault('请求超时')); req.destroy(); }, 15000);
    req.on('error', () => finish(fault('网络请求失败')));
    req.end(payload);
  });
}
function identities(body, account) {
  const values = [];
  const objects = [body, body.user, body.data, body.data && body.data.user];
  for (const obj of objects) {
    if (!obj || typeof obj !== 'object') continue;
    for (const key of ['nickname', 'username', 'displayName', 'publicUid', 'uid']) {
      const value = obj[key];
      if (!['string', 'number'].includes(typeof value)) continue;
      const text = String(value);
      if (!text || /^\+?\d[\d -]{6,}\d$/.test(text) && key !== 'uid' && key !== 'publicUid') continue;
      if ([account.csrfToken, account.cookie, ...account.cookie.split(';').map(s => s.slice(s.indexOf('=') + 1).trim())]
        .some(secret => secret && text.includes(secret))) continue;
      values.push(`${key}=${JSON.stringify(value)}`);
    }
  }
  return [...new Set(values)].join('，');
}
function selectedForNotification(env) {
  const mode = (env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (FALSE.includes(mode)) return false;
  if (TRUE.includes(mode)) return true;
  const selectors = (env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const names = [CATALOG, 'follow.js', 'follow/follow.js', path.basename(__filename)];
  return selectors.some(selector => {
    const re = new RegExp('^' + selector.split('*').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(name => re.test(name));
  });
}
async function notify(env, summary, dryRun) {
  if (dryRun) { log('⏭️ 离线预演：已生成脱敏通知摘要，不加载通知渠道'); return '预演'; }
  if (!selectedForNotification(env)) { log('⏭️ 通知未启用或本任务未被清单选中'); return '未启用'; }
  const dirs = [...new Set([env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean))];
  const notifier = dirs.map(dir => path.join(dir, 'sendNotify.js')).find(file => fs.existsSync(file));
  if (!notifier) { log('⚠️ 未发现 sendNotify.js，保留业务退出码'); return '不可用'; }
  // 通知置于独立进程：限制耗时、丢弃模块输出，仅传递脱敏摘要。
  const body = `账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}，预演 ${summary.skipped}；状态：${summary.status}`;
  return new Promise(resolve => {
    let settled = false;
    let timer;
    const finish = status => {
      if (settled) return;
      settled = true; clearTimeout(timer);
      log(status === '已发送' ? '✅ 脱敏汇总通知已发送' : '⚠️ 通知失败或超时，保留业务退出码');
      resolve(status);
    };
    const childEnv = { ...env };
    delete childEnv.FOLLOW_ACCOUNTS; delete childEnv.follow_csrfToken; delete childEnv.follow_cookie;
    const child = spawn(process.execPath, ['-e',
      'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))',
      notifier, TITLE, body], { env: childEnv, stdio: 'ignore' });
    timer = setTimeout(() => { child.kill('SIGKILL'); finish('失败'); }, 15000);
    child.on('error', () => finish('失败'));
    child.on('exit', code => finish(code === 0 ? '已发送' : '失败'));
  });
}
async function main(env = process.env) {
  const start = Date.now();
  const dryRun = TRUE.includes((env.FOLLOW_DRY_RUN || '').toLowerCase());
  const accounts = parseAccounts(env);
  const summary = { task: TITLE, mode: dryRun ? 'dry-run' : 'live', accounts: accounts.length,
    success: 0, failed: 0, skipped: 0, alreadyComplete: 0, status: '', results: [] };
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(start).toISOString()}；模式：${dryRun ? '离线预演' : '实际签到'}；账号数：${accounts.length}`);
  if (!accounts.length) { log('❌ 阶段 1 配置校验：缺少 FOLLOW_ACCOUNTS（兼容 follow_csrfToken 与 follow_cookie）'); summary.status = 'configuration-error'; }
  for (let i = 0; i < accounts.length; i++) {
    const account = accounts[i];
    const at = Date.now();
    const result = { account: i + 1, total: 1, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    log(`账号 ${i + 1} / ${accounts.length}：阶段 1 配置校验`);
    if (!validAccount(account)) {
      result.failed = 1; summary.failed++;
      log('❌ 阶段 1 失败：需要同一账号的非空 csrfToken|Cookie，且不得包含控制字符；耗时 0ms');
    } else {
      log('✅ 阶段 1 完成：配套参数校验通过；耗时 0ms');
      const step = Date.now();
      log(`阶段 2 每日签到：${dryRun ? '离线检查固定 POST 请求配置' : '提交领取请求（不自动重试）'}`);
      if (dryRun) { result.skipped = 1; summary.skipped++; log('⏭️ DRY_RUN_OK：配置有效，未发起网络请求，未验证真实签到'); }
      else {
        try {
          const body = await claim(account);
          const identity = identities(body, account);
          if (identity) log(`账号 ${i + 1} 官方身份：${identity}`);
          result.success = 1; summary.success++;
          log('✅ 签到成功：HTTP 成功且业务 code=0');
        } catch (error) {
          result.failed = 1; summary.failed++;
          log(`❌ ${error.safeCode || '签到执行失败（详情已脱敏）'}`);
        }
      }
      log(`阶段 2 结束；耗时 ${Date.now() - step}ms`);
    }
    result.durationMs = Date.now() - at;
    summary.results.push(result);
    log(`账号 ${i + 1} 统计：总任务 1，成功 ${result.success}，已完成 0，跳过 ${result.skipped}，失败 ${result.failed}；耗时 ${result.durationMs}ms`);
  }
  summary.status ||= summary.failed ? (summary.success || summary.skipped ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
  const exitCode = summary.failed || !accounts.length ? 1 : 0;
  log('阶段 3 汇总通知');
  const notificationStart = Date.now();
  try { summary.notification = await notify(env, summary, dryRun); }
  catch { summary.notification = '失败'; log('⚠️ 通知异常，保留业务退出码'); }
  log(`阶段 3 结束；耗时 ${Date.now() - notificationStart}ms`);
  summary.durationMs = Date.now() - start;
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`账号统计：总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}，预演 ${summary.skipped}`);
  log(`子任务统计：总数 ${summary.accounts}，成功 ${summary.success}，已完成 0，跳过 ${summary.skipped}，失败 ${summary.failed}`);
  log(`总耗时 ${summary.durationMs}ms；完成时间 ${summary.finishedAt}；通知 ${summary.notification}；最终状态 ${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  return exitCode;
}
module.exports = { main, parseAccounts, claim, identities, selectedForNotification };
if (require.main === module) main().then(code => { process.exitCode = code; }).catch(() => {
  // 正常业务、配置与通知错误均在 main 内收敛；此处仅覆盖意外运行时故障。
  log('❌ 运行时故障，详情已脱敏'); process.exitCode = 1;
});
