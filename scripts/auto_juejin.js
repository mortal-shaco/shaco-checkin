// name: 掘金每日签到
// cron: 36 10 * * *
/**
 * name: 掘金每日签到
 * cron: 36 10 * * *
 * 来源 suojian0313/juejin_helper，auto_juejin.js
 * 上游提交 790a83033e4979e0a66399678be46337f09e218b，维护许可 MIT。
 *
 * JUEJIN_COOKIE 必填，每个非空行一个账号的完整 Cookie，Cookie 内分号原样保留。
 * 获取方式：登录掘金网页版，在浏览器开发者工具 Network 中找到本人
 * api.juejin.cn 的已登录请求，复制请求头 Cookie。勿复制请求或响应到日志。
 * JUEJIN_DRY_RUN=1 完全断网预演。默认执行签到和只读统计。
 * JUEJIN_DIP_LUCKY=1 开启沾喜气，另需 JUEJIN_LOTTERY_HISTORY_ID
 * （本人在掘金沾喜气请求中取得的有效 lottery_history_id）。移除上游固定 ID。
 * JUEJIN_FREE_LOTTERY=1 开启抽奖，仅 free_count 为正时提交一次。
 * 抽奖接口未提供强制免费参数，并发运行可能消耗矿石，请勿并发执行。
 * 可选功能默认关闭以移除不安全默认副作用。所有账号共享可选开关。
 * QINGLONG_NOTIFY=auto|1|0 控制通知。auto 仅匹配 QINGLONG_NOTIFY_SCRIPTS
 * 中的目录标识、脚本相对路径、文件名或通配符时通知，未设置名单默认不通知。
 * QINGLONG_NOTIFY_DIR 可指向青龙 sendNotify.js 所在目录。
 * 预演仅记录通知摘要和投递计划，避免通知组件联网。
 * 保留已发布维护任务的每日 10:36 计划；来源云函数未声明 cron。
 * 合并来源：CocoSilent/auto-sign，cloudfunctions/juejin/index.js 与 utils.js (MIT)。
 * 兼容 JUEJIN_ACCOUNTS：每个非空行 aid|sessionid，仅按第一个 | 拆分。
 * 从本人 api.juejin.cn 请求查询参数取得 aid，从 Cookie 取得 sessionid 的值。
 * 兼容 juejin_aid + juejin_sessionid 单账号变量；输入优先级：
 * JUEJIN_COOKIE > JUEJIN_ACCOUNTS > 旧变量对，显式空值不回退。
 * 默认查询免费抽奖次数；仍仅显式开启 JUEJIN_FREE_LOTTERY 后抽奖。
 * 云函数兼容入口 exports.main 返回 {result,msg}；导入不会自动执行。
 * Node.js >=18；仅使用标准库，无业务外部依赖。
 *
 * MIT License
 * Original source attribution: suojian0313/juejin_helper
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
    const identities = ["9e33a705da89cfd6", "scripts/auto_juejin.js", "auto_juejin.js", "auto_juejin"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const TITLE = '掘金每日签到';
const CATALOG = '9e33a705da89cfd6';
const enabledValues = ['1', 'true', 'yes', 'on'];
const disabledValues = ['0', 'false', 'no', 'off'];
const isEnabled = value => enabledValues.includes((value || '').toLowerCase());
function accountsFrom(env) {
  if (env.JUEJIN_COOKIE !== undefined) {
    return env.JUEJIN_COOKIE.split(/\r?\n/).map(line => line.trim()).filter(Boolean)
      .map(cookie => ({ cookie, aid: '', valid: cookie.includes('=') && !/[\x00-\x1f\x7f]/.test(cookie) }));
  }
  const lines = env.JUEJIN_ACCOUNTS !== undefined ? env.JUEJIN_ACCOUNTS.split(/\r?\n/) :
    (env.juejin_aid || env.juejin_sessionid ? [`${env.juejin_aid || ''}|${env.juejin_sessionid || ''}`] : []);
  return lines.map(line => line.trim()).filter(Boolean).map(line => {
    const at = line.indexOf('|');
    const aid = at < 0 ? '' : line.slice(0, at).trim();
    const session = at < 0 ? '' : line.slice(at + 1).trim();
    return { cookie: `sessionid=${session}`, aid,
      valid: /^\d+$/.test(aid) && !!session && !/[;\s\x00-\x1f\x7f]/.test(session) };
  });
}
const endpoint = {
  status: ['GET', 'get_today_status'],
  checkIn: ['POST', 'check_in'],
  counts: ['GET', 'get_counts'],
  points: ['GET', 'get_cur_point'],
  lucky: ['POST', 'lottery_lucky/my_lucky'],
  free: ['GET', 'lottery_config/get'],
  dip: ['POST', 'lottery_lucky/dip_lucky'],
  lottery: ['POST', 'lottery/draw']
};
function log(text) {
  console.log(`[${new Date().toTimeString().slice(0, 8)}] ${text}`);
}
function safeText(value, cookie) {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  let text = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  const sensitive = [cookie, ...cookie.split(';').map(part => part.slice(part.indexOf('=') + 1).trim())];
  for (const secret of sensitive.filter(item => item)) {
    if (secret.length >= 4) text = text.split(secret).join('[凭据已隐藏]');
    else if (text === secret) text = '[凭据已隐藏]';
  }
  return text.replace(/(?:cookie|token|session|authorization)\s*[:=]\s*\S+/gi, '[凭据已隐藏]')
    .replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function request(account, key, config) {
  const { cookie, aid } = account;
  const { dryRun, historyId } = config;
  if (dryRun) throw new Error('预演模式禁止网络请求');
  const [method, route] = endpoint[key];
  const url = new URL(`https://api.juejin.cn/growth_api/v1/${route}`);
  if (aid) url.searchParams.set('aid', aid);
  // 保留上游 dip_lucky 参数所在的查询串，不推测未提供证据的接口变更。
  if (key === 'dip') url.searchParams.set('lottery_history_id', historyId);
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolve(value);
    };
    const req = https.request(url, {
      method,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', Cookie: cookie },
      timeout: 15000
    }, res => {
      if (res.statusCode !== 200) {
        res.resume();
        finish(new Error(`HTTP 状态异常 ${res.statusCode}`));
        return;
      }
      let size = 0;
      const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 262144) {
          finish(new Error('响应超过大小限制'));
          res.destroy();
          return;
        }
        chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应提前中断')));
      res.on('end', () => {
        if (settled) return;
        let body;
        try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch { finish(new Error('响应不是有效 JSON')); return; }
        if (!body || body.err_no !== 0) {
          finish(new Error('业务未成功，请检查凭据有效性和接口状态'));
          return;
        }
        finish(null, body.data);
      });
    });
    timer = setTimeout(() => {
      finish(new Error('请求超过 15 秒总时限'));
      req.destroy();
    }, 15000);
    req.on('timeout', () => {
      finish(new Error('请求超时'));
      req.destroy();
    });
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end();
  });
}
function number(value) { return typeof value === 'number' && Number.isFinite(value) && value >= 0; }
function identify(data, cookie) {
  if (!data || typeof data !== 'object') return;
  for (const name of ['nickname', 'user_name', 'username', 'display_name', 'user_id', 'uid']) {
    if (data[name] !== undefined) log(`账号身份 ${name}=${safeText(data[name], cookie)}`);
  }
  for (const key of ['user_info', 'user']) {
    if (data[key] && typeof data[key] === 'object') identify(data[key], cookie);
  }
}
async function runAccount(account, index, config) {
  const { cookie } = account;
  const { dryRun, dip, lottery } = config;
  let freeCount = null;
  const begin = Date.now();
  const stats = { account: index, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  const result = { checkInStatus: false, continuousDay: null, totalDay: null, oreCount: null, prize: null, LuckyValue: null };
  async function stage(name, action) {
    const stepStart = Date.now();
    stats.total++;
    log(`账号 ${index} 阶段 ${stats.total} ${name} 开始`);
    try {
      const outcome = await action();
      stats[outcome.kind || 'success']++;
      log(`账号 ${index} ${name} ${outcome.message}，耗时 ${Date.now() - stepStart}ms`);
      console.log(JSON.stringify({ result: true, msg: outcome.message }));
    } catch (error) {
      stats.failed++;
      const message = safeText(error.message, cookie);
      log(`账号 ${index} ${name} ❌ ${message}，耗时 ${Date.now() - stepStart}ms`);
      console.log(JSON.stringify({ result: false, msg: message }));
    }
  }
  async function read(key) {
    const data = await request(account, key, config);
    identify(data, cookie);
    return data;
  }
  if (!account.valid) {
    await stage('凭据格式检查', async () => { throw new Error('凭据格式异常，请检查完整 Cookie 或 aid|sessionid'); });
    stats.durationMs = Date.now() - begin;
    stats.status = 'failure';
    log(`账号 ${index} 统计 总任务 1，成功 0，已完成 0，跳过 0，失败 1，耗时 ${stats.durationMs}ms`);
    return stats;
  }
  await stage('每日签到', async () => {
    if (dryRun) return { kind: 'skipped', message: '⏭️ 预演，计划查询签到状态并仅在未签到时签到' };
    const status = await read('status');
    if (typeof status !== 'boolean') throw new Error('签到状态字段异常');
    if (status) {
      result.checkInStatus = true;
      return { kind: 'alreadyComplete', message: '☑️ 今日已签到' };
    }
    await read('checkIn');
    if (await read('status') !== true) throw new Error('签到后状态核验失败');
    result.checkInStatus = true;
    return { message: '✅ 今日签到成功，已核验状态' };
  });
  await stage('沾喜气', async () => {
    if (!dip) return { kind: 'skipped', message: '⏭️ 开关未开启' };
    if (dryRun) return { kind: 'skipped', message: '⏭️ 预演，计划使用配置的历史记录沾喜气' };
    await read('dip');
    return { message: '✅ 沾喜气业务成功' };
  });
  await stage('查询免费抽奖次数', async () => {
    if (dryRun) return { kind: 'skipped', message: '⏭️ 预演，计划查询免费抽奖次数，不模拟业务成功' };
    const data = await read('free');
    if (!data || !Number.isSafeInteger(data.free_count) || data.free_count < 0) throw new Error('免费次数字段异常');
    freeCount = data.free_count;
    return { message: `✅ 免费抽奖次数 ${freeCount}` };
  });
  await stage('免费抽奖', async () => {
    if (!lottery) return { kind: 'skipped', message: '⏭️ 开关未开启' };
    if (dryRun) return { kind: 'skipped', message: '⏭️ 预演，计划核验免费次数，最多抽奖一次' };
    if (freeCount === null) return { kind: 'skipped', message: '⏭️ 免费次数查询失败，禁止抽奖' };
    if (freeCount === 0) return { kind: 'skipped', message: '⏭️ 无免费次数，未提交抽奖' };
    const draw = await read('lottery');
    if (!draw || typeof draw.lottery_name !== 'string' || !draw.lottery_name.trim()) throw new Error('抽奖结果字段异常');
    result.prize = safeText(draw.lottery_name, cookie);
    return { message: `✅ 免费次数核验通过，抽奖成功，奖品 ${result.prize}` };
  });
  await stage('签到天数', async () => {
    if (dryRun) return { kind: 'skipped', message: '⏭️ 预演，计划读取连续和累计签到天数' };
    const counts = await read('counts');
    if (!counts || !number(counts.cont_count) || !number(counts.sum_count)) throw new Error('签到天数字段异常');
    result.continuousDay = counts.cont_count;
    result.totalDay = counts.sum_count;
    return { message: `✅ 连续 ${result.continuousDay} 天，累计 ${result.totalDay} 天` };
  });
  await stage('当前矿石', async () => {
    if (dryRun) return { kind: 'skipped', message: '⏭️ 预演，计划读取矿石余额' };
    const points = await read('points');
    if (!number(points)) throw new Error('矿石余额字段异常');
    result.oreCount = points;
    return { message: `✅ 当前矿石 ${points}` };
  });
  await stage('幸运值', async () => {
    if (dryRun) return { kind: 'skipped', message: '⏭️ 预演，计划读取幸运值' };
    const lucky = await read('lucky');
    if (!lucky || !number(lucky.total_value)) throw new Error('幸运值字段异常');
    result.LuckyValue = lucky.total_value;
    return { message: `✅ 累计幸运值 ${result.LuckyValue}/6000` };
  });
  stats.durationMs = Date.now() - begin;
  stats.status = stats.failed ? 'failure' : dryRun ? 'dry-run' : 'success';
  log(`账号 ${index} 统计 总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs}ms`);
  return stats;
}
function notifySelected() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (disabledValues.includes(mode)) return false;
  if (enabledValues.includes(mode) && process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const selectors = (process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const current = __filename.replace(/\\/g, '/');
  const names = [CATALOG, '012f027cd2f3c11b', 'juejin.js', 'scripts/juejin.js', path.basename(__filename), 'auto_juejin.js', 'scripts/auto_juejin.js', current];
  return selectors.some(selector => {
    const escaped = selector.split(/([*?])/).map(part => {
      if (part === '*') return '.*';
      if (part === '?') return '.';
      return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }).join('');
    const pattern = new RegExp(`^${escaped}$`);
    return names.some(name => pattern.test(name) || (selector.includes('/') && current.endsWith(`/${selector}`)));
  });
}
async function notify(summary, dryRun) {
  const body = `账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}，预演 ${summary.dryRunAccounts}，状态 ${summary.status}`;
  log(`通知摘要 ${body}`);
  if (!notifySelected()) return 'disabled';
  if (dryRun) return 'dry-run-suppressed';
  const candidates = [
    process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'
  ].filter(Boolean);
  const file = candidates.find(item => fs.existsSync(item));
  if (!file) { log('⚠️ 通知组件不可用，保留业务退出码'); return 'unavailable'; }
  // 隔离组件异常和挂起，子进程输出不进入日志，摘要通过标准输入传入。
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', `
      let input = '';
      process.stdin.on('data', chunk => input += chunk);
      process.stdin.on('end', async () => {
        try {
          const [file, title, body] = JSON.parse(input);
          const notifier = require(file);
          if (typeof notifier.sendNotify !== 'function') process.exit(1);
          await notifier.sendNotify(title, body);
          process.exit(0);
        } catch { process.exit(1); }
      });
    `], { stdio: ['pipe', 'ignore', 'ignore'] });
    const timer = setTimeout(() => child.kill('SIGKILL'), 20000);
    let settled = false;
    function finish(status) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(status);
    }
    child.on('error', () => finish('failed'));
    child.on('close', code => finish(code === 0 ? 'sent' : 'failed'));
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify([file, TITLE, body]));
  });
}
async function main() {
  const started = Date.now();
  const dryRun = isEnabled(process.env.JUEJIN_DRY_RUN);
  const dip = isEnabled(process.env.JUEJIN_DIP_LUCKY);
  const lottery = isEnabled(process.env.JUEJIN_FREE_LOTTERY);
  const historyId = (process.env.JUEJIN_LOTTERY_HISTORY_ID || '').trim();
  const accounts = accountsFrom(process.env);
  const config = { dryRun, dip, lottery, historyId };
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间 ${new Date(started).toISOString()}，模式 ${dryRun ? '断网预演' : '正式执行'}，账号数 ${accounts.length}`);
  log('阶段 0 参数检查');
  const invalidSwitch = ['JUEJIN_DRY_RUN', 'JUEJIN_DIP_LUCKY', 'JUEJIN_FREE_LOTTERY'].some(name =>
    process.env[name] !== undefined && ![...enabledValues, ...disabledValues].includes(process.env[name].toLowerCase()));
  const invalidNotify = process.env.QINGLONG_NOTIFY !== undefined && !['auto', ...enabledValues, ...disabledValues].includes(process.env.QINGLONG_NOTIFY.toLowerCase());
  const invalid = accounts.length === 0 || invalidSwitch || invalidNotify || (dip && !/^\d+$/.test(historyId));
  const results = [];
  if (invalid) log('❌ 配置错误，请检查 账号变量、布尔开关、通知开关及沾喜气所需的历史记录 ID');
  else for (let index = 0; index < accounts.length; index++) results.push(await runAccount(accounts[index], index + 1, config));
  const failed = invalid ? accounts.length : results.filter(item => item.failed > 0).length;
  const success = results.filter(item => item.status === 'success').length;
  const status = invalid ? 'configuration-error' : failed ? (results.some(item => !item.failed) ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
  process.exitCode = invalid || failed ? 1 : 0;
  const summary = {
    name: TITLE, status, mode: dryRun ? 'dry-run' : 'live', accounts: accounts.length,
    success, failed, dryRunAccounts: results.filter(item => item.status === 'dry-run').length,
    configurationError: Boolean(invalid), results
  };
  try { summary.notification = await notify(summary, dryRun); }
  catch { summary.notification = 'failed'; }
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  console.log('----------------------------------------');
  log(`任务统计 账号 ${summary.accounts}，成功 ${success}，失败 ${failed}，预演 ${summary.dryRunAccounts}`);
  for (const key of ['total', 'success', 'alreadyComplete', 'skipped', 'failed']) {
    log(`子任务 ${key} ${results.reduce((sum, item) => sum + item[key], 0)}`);
  }
  log(`通知状态 ${summary.notification}，总耗时 ${summary.durationMs}ms，完成时间 ${summary.finishedAt}`);
  log(`最终状态 ${status}${status === 'success' ? ' 掘金任务全部完成' : status === 'dry-run' ? ' DRY_RUN_OK' : ''}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  return { result: !invalid && failed === 0, msg: invalid || failed ? '任务存在失败或配置错误' : dryRun ? '断网演练成功' : '任务成功' };
}
exports.main = main;
if (require.main === module) main().catch(async () => {
  process.exitCode = 1;
  log('❌ 执行器发生未预期异常');
  const summary = { name: TITLE, status: 'failure', mode: isEnabled(process.env.JUEJIN_DRY_RUN) ? 'dry-run' : 'live',
    accounts: accountsFrom(process.env).length, success: 0, failed: accountsFrom(process.env).length, dryRunAccounts: 0 };
  try { summary.notification = await notify(summary, isEnabled(process.env.JUEJIN_DRY_RUN)); }
  catch { summary.notification = 'failed'; }
  summary.finishedAt = new Date().toISOString();
  log(`任务统计 账号 ${summary.accounts}，成功 0，失败 ${summary.failed}，完成时间 ${summary.finishedAt}，最终状态 failure，通知状态 ${summary.notification}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
});
