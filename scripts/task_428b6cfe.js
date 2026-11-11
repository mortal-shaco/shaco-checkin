// name: 掘金沾喜气与签到
// cron: 43 10 * * *
/*
 * name: 掘金沾喜气与签到
 * cron: 17 9 * * *
 * 来源：ynzy/juejin_auto_game，app.js
 * 上游提交：f42080a828232628098fccdfe82c00954fd74908
 * 许可：MIT。保留上游作者 ynzy 归属；输入文件没有附带其他版权声明。
 *
 * JUEJIN_ACCOUNTS：每行一个 JSON 对象，含 cookie、aid、uuid；签到及抽奖另需 signature。
 * 从已登录掘金网页的开发者工具 Network 中找到 growth_api 请求，复制 Cookie 请求头
 * 及 URL 查询参数 aid、uuid、_signature（写为 signature）；不要分享这些值。
 * JUEJIN_TASKS：逗号分隔 lucky（默认）、signin、draw；draw 必须显式启用且只抽一次免费奖。
 * JUEJIN_DRY_RUN=1：完全断网，仅检查配置和展示计划，绝不执行通知或业务请求。
 * 没有提供 autoGame/collectBugGame 的实现；不猜测游戏协议，不声明支持游戏。
 * 原文件没有 cron；上面的每日时间为维护版建议，可在青龙中调整。
 * 不发帖、评论或分享，不使用随机文案接口。
 *
 * MIT License
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
    const identities = ["428b6cfe6c4ed62e", "scripts/task_428b6cfe.js", "task_428b6cfe.js", "task_428b6cfe"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '掘金沾喜气与签到';
const CATALOG = '428b6cfe6c4ed62e';
const dryRun = process.env.JUEJIN_DRY_RUN === '1';
const started = Date.now();
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
const results = [];
let configFailed = false;
let secrets = [];
function log(text) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${text}`); }
function safeIdentity(data) {
  if (!data || typeof data !== 'object') return;
  const user = data.user_info || data.user || data;
  for (const key of ['nickname', 'user_name', 'username', 'display_name', 'user_id', 'uid']) {
    const value = user[key];
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const text = String(value);
    if (!text || /[\r\n\x00-\x1f]/.test(text) || text.length > 200) continue;
    if (/^(?:\+?86)?1\d{10}$/.test(text)) continue;
    if (secrets.some(secret => secret && text.includes(secret))) continue;
    log(`官方账号身份 ${key}：${text}`);
  }
}
class TaskError extends Error {}
function validate(line, actions) {
  let account;
  try { account = JSON.parse(line); } catch { throw new TaskError('账号格式错误：每行必须是完整 JSON 对象'); }
  if (!account || typeof account !== 'object' || Array.isArray(account)) throw new TaskError('账号格式错误');
  for (const key of ['cookie', 'aid', 'uuid']) {
    if (typeof account[key] !== 'string' || !account[key].trim() || /[\r\n\x00]/.test(account[key])) {
      throw new TaskError(`缺少或无效的账号字段：${key}`);
    }
  }
  if (account.signature === undefined && typeof account._signature === 'string') account.signature = account._signature;
  if (actions.some(action => action === 'signin' || action === 'draw') &&
      (typeof account.signature !== 'string' || !account.signature.trim() || /[\r\n\x00]/.test(account.signature))) {
    throw new TaskError('签到或抽奖需要有效 signature 字段');
  }
  secrets = [account.cookie, account.uuid, account.signature,
    ...account.cookie.split(';').map(pair => pair.slice(pair.indexOf('=') + 1).trim()).filter(v => v.length >= 4)].filter(Boolean);
  return account;
}
function request(account, endpoint, method, body) {
  if (dryRun) throw new TaskError('预演模式禁止联网');
  const url = new URL(`https://api.juejin.cn/growth_api/v1/${endpoint}`);
  url.searchParams.set('aid', account.aid);
  url.searchParams.set('uuid', account.uuid);
  if (['check_in', 'lottery/draw'].includes(endpoint)) url.searchParams.set('_signature', account.signature);
  const payload = body === undefined ? undefined : JSON.stringify(body);
  return new Promise((resolve, reject) => {
    let settled = false;
    let req;
    const finish = (error, data) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(data);
    };
    const timer = setTimeout(() => {
      finish(new TaskError('请求超时，写入结果未知；不自动重试'));
      if (req) req.destroy();
    }, 15000);
    try {
      req = https.request(url, {
        method,
        headers: {
          Cookie: account.cookie,
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36 Edg/92.0.902.67',
          Accept: 'application/json',
          ...(payload === undefined ? {} : { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) })
        }
      }, res => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          finish(new TaskError(`HTTP 状态异常：${res.statusCode}（不跟随重定向）`));
          res.destroy();
          return;
        }
        let bytes = 0;
        const chunks = [];
        res.on('data', chunk => {
          bytes += chunk.length;
          if (bytes > 1048576) {
            finish(new TaskError('响应超出大小限制'));
            res.destroy();
          } else chunks.push(chunk);
        });
        res.on('error', () => finish(new TaskError('响应读取失败')));
        res.on('aborted', () => finish(new TaskError('响应意外中断')));
        res.on('end', () => {
          let data;
          try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
          catch { finish(new TaskError('响应不是有效 JSON')); return; }
          if (!data || data.err_no !== 0) {
            const code = data && Number.isSafeInteger(data.err_no) ? `，业务码 ${data.err_no}` : '';
            finish(new TaskError(`业务未确认成功${code}`));
            return;
          }
          finish(null, data.data);
        });
      });
      req.on('error', () => finish(new TaskError('网络请求失败，结果未确认；不自动重试')));
      req.end(payload);
    } catch { finish(new TaskError('请求参数无效')); }
  });
}
function nonnegative(value) { return typeof value === 'number' && Number.isFinite(value) && value >= 0; }
async function lucky(account) {
  const data = await request(account, 'lottery_history/global_big', 'POST');
  safeIdentity(data);
  if (!data || !Array.isArray(data.lotteries) || !data.lotteries.length) throw new TaskError('中奖记录为空或结构改变，未执行沾喜气');
  const id = data.lotteries[0] && data.lotteries[0].history_id;
  if (!((typeof id === 'string' && id.trim()) || (Number.isSafeInteger(id) && id > 0))) throw new TaskError('中奖记录缺少有效编号');
  log('已确认中奖记录，准备沾喜气');
  const result = await request(account, 'lottery_lucky/dip_lucky', 'POST', { lottery_history_id: id });
  safeIdentity(result);
  if (!result || !nonnegative(result.dip_value)) throw new TaskError('沾喜气响应缺少有效 dip_value，不能确认结果');
  return { status: 'success', detail: `沾喜气成功，本次幸运值 ${result.dip_value}` };
}
async function signin(account) {
  const result = await request(account, 'check_in', 'POST');
  safeIdentity(result);
  if (!result || !nonnegative(result.incr_point) || !nonnegative(result.sum_point)) throw new TaskError('签到响应缺少有效矿石字段，不能确认结果');
  return { status: 'success', detail: `签到成功，获得矿石 ${result.incr_point}，矿石总数 ${result.sum_point}` };
}
async function draw(account) {
  const config = await request(account, 'lottery_config/get', 'GET');
  safeIdentity(config);
  if (!config || !Number.isSafeInteger(config.free_count) || config.free_count < 0) throw new TaskError('免费次数无效，禁止抽奖');
  if (config.free_count === 0) return { status: 'skipped', detail: '免费次数为零，跳过抽奖，禁止付费重试' };
  log(`已确认免费次数 ${config.free_count}，只请求一次抽奖`);
  const result = await request(account, 'lottery/draw', 'POST');
  safeIdentity(result);
  if (!result || typeof result !== 'object' || Array.isArray(result) || !Object.keys(result).length) throw new TaskError('抽奖结果缺失，不能确认结果');
  return { status: 'success', detail: '免费抽奖成功（业务码 0 且返回有效结果）' };
}
const handlers = { signin, lucky, draw };
const names = { signin: '签到', lucky: '沾喜气', draw: '免费抽奖' };
function selectedNotify() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(mode)) return false;
  if (['1', 'true', 'yes', 'on'].includes(mode)) return true;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const selectors = process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean);
  const filename = path.basename(__filename);
  const relative = __filename.replace(/^.*\/scripts\//, '');
  return selectors.some(selector => {
    if (selector === CATALOG || selector === relative || selector === filename) return true;
    const glob = selector.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    return new RegExp(`^${glob}$`).test(filename);
  });
}
async function notify(body) {
  if (!selectedNotify()) return '已关闭';
  if (dryRun) { log(`预演通知摘要（断网，不投递）：${body}`); return '预演未联网'; }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const modulePath = dirs.map(dir => path.join(dir, 'sendNotify.js')).find(file => fs.existsSync(file));
  if (!modulePath) { log('⚠️ 未找到青龙 sendNotify.js，保留业务退出码'); return '不可用'; }
  // 隔离通知模块输出及异常，避免它输出原始推送响应；限定通知进程总时长。
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e',
      'Promise.resolve().then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).then(() => process.exit(0), () => process.exit(1));',
      modulePath, TITLE, body], { stdio: 'ignore' });
    let done = false;
    const finish = state => { if (!done) { done = true; clearTimeout(timer); resolve(state); } };
    const timer = setTimeout(() => { child.kill('SIGKILL'); finish('超时'); }, 15000);
    child.on('error', () => finish('失败'));
    child.on('close', code => finish(code === 0 ? '已发送' : '失败'));
  });
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dryRun ? '断网预演' : '正式执行'}`);
  const lines = (process.env.JUEJIN_ACCOUNTS || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean);
  log(`账号总数：${lines.length}`);
  let actions = [];
  try {
    actions = [...new Set((process.env.JUEJIN_TASKS || 'lucky').split(',').map(v => v.trim()))];
    if (!actions.length || actions.some(v => !Object.hasOwn(handlers, v))) throw new TaskError('JUEJIN_TASKS 仅允许 signin,lucky,draw');
    // 保持原签到组合流程的先签到、再沾喜气、最后免费抽奖顺序。
    actions = ['signin', 'lucky', 'draw'].filter(v => actions.includes(v));
    if (!lines.length) throw new TaskError('缺少 JUEJIN_ACCOUNTS：每行一个账号 JSON');
  } catch (error) {
    configFailed = true;
    log(`❌ 配置错误：${error instanceof TaskError ? error.message : '配置校验失败'}`);
  }
  if (!configFailed) for (let i = 0; i < lines.length; i++) {
    const accountStart = Date.now();
    const stats = { account: i + 1, total: actions.length, success: 0, alreadyComplete: 0, skipped: 0, failure: 0, durationMs: 0 };
    log(`----- 账号 ${i + 1} -----`);
    let account;
    try { account = validate(lines[i], actions); }
    catch (error) {
      configFailed = true;
      stats.failure = actions.length;
      log(`❌ 账号 ${i + 1} 配置错误：${error instanceof TaskError ? error.message : '校验失败'}`);
    }
    if (account) for (let step = 0; step < actions.length; step++) {
      const action = actions[step];
      const stepStart = Date.now();
      log(`阶段 ${step + 1}/${actions.length}：${names[action]} 开始`);
      try {
        const result = dryRun ? { status: 'skipped', detail: `DRY_RUN_OK ${names[action]}：配置有效，未发送请求或改变账号状态` } : await handlers[action](account);
        stats[result.status]++;
        log(`${result.status === 'success' ? '✅' : '⏭️'} ${result.detail}；阶段耗时 ${Date.now() - stepStart}ms`);
      } catch (error) {
        stats.failure++;
        log(`❌ ${names[action]}失败：${error instanceof TaskError ? error.message : '执行异常（细节已脱敏）'}；阶段耗时 ${Date.now() - stepStart}ms`);
      }
    }
    stats.durationMs = Date.now() - accountStart;
    results.push(stats);
    for (const key of Object.keys(totals)) totals[key] += stats[key];
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failure}，耗时 ${stats.durationMs}ms`);
  }
  const failed = configFailed && results.length === 0 ? lines.length : results.filter(v => v.failure > 0).length;
  const succeeded = results.filter(v => v.failure === 0).length;
  const exitCode = configFailed || failed ? 1 : 0;
  const status = configFailed ? 'configuration-error' : failed ? (succeeded ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
  const body = `状态：${status}；账号总数 ${lines.length}，成功 ${succeeded}，失败 ${failed}；子任务成功 ${totals.success}，跳过 ${totals.skipped}，失败 ${totals.failure}。${dryRun ? '预演未执行业务，成功数仅指配置检查通过。' : ''}`;
  let notification;
  try { notification = await notify(body); }
  catch { notification = '失败'; log('⚠️ 通知执行失败，保留业务退出码'); }
  console.log('----------------------------------------');
  log(body);
  log(`子任务总数 ${totals.total}，已完成 ${totals.alreadyComplete}；通知状态：${notification}`);
  log(`结束时间：${new Date().toISOString()}；总耗时 ${Date.now() - started}ms；最终状态：${status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify({ task: TITLE, mode: dryRun ? 'dry-run' : 'live', status, accounts: { total: lines.length, success: succeeded, failure: failed }, tasks: totals, results, notification, durationMs: Date.now() - started, exitCode })}`);
  process.exitCode = exitCode;
}
main().catch(() => {
  // 防止不可预料的异常暴露 URL、Cookie 或运行时堆栈。
  log('❌ 任务发生未处理异常，细节已脱敏');
  process.exitCode = 1;
});
