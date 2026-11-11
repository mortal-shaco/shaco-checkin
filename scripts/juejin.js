// name: 掘金每日签到与可选免费抽奖
// cron: 42 10 * * *
/*
name: 掘金每日签到与可选免费抽奖
cron: 42 10 * * *
来源：CocoSilent/auto-sign，cloudfunctions/juejin/index.js 与 utils.js
https://github.com/CocoSilent/auto-sign (MIT)
上游输入未附独立版权文字；保留来源与 MIT 许可。原云函数未声明 cron，以上为建议每日计划。

MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Node.js >=18；无业务依赖。JUEJIN_ACCOUNTS：每行 aid|sessionid，仅按第一个 | 拆分。
登录掘金网页版，在开发者工具 Network 中查 api.juejin.cn 的请求，
从查询参数取得 aid，从请求 Cookie 取得 sessionid 的值（不要粘贴整条 Cookie）。
兼容单账号 juejin_aid + juejin_sessionid；设置规范变量后不再读取旧变量。
JUEJIN_DRY_RUN=1：完全断网，仅验证配置与演练流程，不调用通知模块。
JUEJIN_FREE_LOTTERY=1：显式授权抽奖；默认关闭。仅免费次数为正时抽一次，
不循环、不充值、不重试写请求。查询与抽奖不是原子操作，请勿同时运行其他抽奖任务。
QINGLONG_NOTIFY=auto 默认按名单；QINGLONG_NOTIFY_SCRIPTS 可用逗号、分号、空白
分隔 catalogId、路径或文件名 glob；空名单关闭。1 强制开启（仍遵守显式名单），0 关闭。
可用 QINGLONG_NOTIFY_DIR 指定青龙 sendNotify.js 目录。通知失败不改变业务退出码。
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
    const identities = ["012f027cd2f3c11b", "scripts/juejin.js", "juejin.js", "juejin"];
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
const { pathToFileURL } = require('node:url');
const TITLE = '掘金每日签到与可选免费抽奖';
const CATALOG = '012f027cd2f3c11b';
const enabled = value => /^(1|true|yes|on)$/i.test(value || '');
const disabled = value => /^(0|false|no|off)$/i.test(value || '');
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = message => console.log(`[${stamp()}] ${message}`);
const seconds = start => Number(((Date.now() - start) / 1000).toFixed(3));

function accountsFrom(env) {
  let lines;
  if (env.JUEJIN_ACCOUNTS !== undefined) {
    lines = env.JUEJIN_ACCOUNTS.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  } else if (env.juejin_aid || env.juejin_sessionid) {
    lines = [`${env.juejin_aid || ''}|${env.juejin_sessionid || ''}`];
  } else lines = [];
  return lines.map(line => {
    const at = line.indexOf('|');
    const aid = at >= 0 ? line.slice(0, at).trim() : '';
    const session = at >= 0 ? line.slice(at + 1).trim() : '';
    const valid = /^\d+$/.test(aid) && session.length > 0 && !/[;\s\x00-\x1f\x7f]/.test(session);
    return { aid, session, valid };
  });
}

// 直接实现业务 HTTP，不依赖上游云函数、私有工具或外部可执行程序。
function request(account, endpoint, method) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let req;
    const timer = setTimeout(() => finish(new Error('请求超时')), 15000);
    function finish(error, value) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) { if (req) req.destroy(); reject(error); }
      else resolve(value);
    }
    try {
      const url = new URL(`https://api.juejin.cn/growth_api/v1/${endpoint}`);
      url.searchParams.set('aid', account.aid);
      req = https.request(url, {
        method, headers: { 'Content-Type': 'application/json', Cookie: `sessionid=${account.session}` }
      }, res => {
        if (res.statusCode !== 200) {
          res.resume();
          finish(new Error(`HTTP 状态异常（${Number(res.statusCode) || 0}）`));
          return;
        }
        const chunks = [];
        let length = 0;
        res.on('data', chunk => {
          length += Buffer.byteLength(chunk);
          if (length > 1024 * 1024) return finish(new Error('响应超出大小限制'));
          chunks.push(Buffer.from(chunk));
        });
        res.on('aborted', () => finish(new Error('响应中断')));
        res.on('error', () => finish(new Error('响应读取失败')));
        res.on('end', () => {
          if (settled) return;
          let body;
          try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
          catch { return finish(new Error('响应不是有效 JSON')); }
          if (!body || typeof body !== 'object' || !Number.isInteger(body.err_no)) {
            return finish(new Error('响应缺少有效业务码'));
          }
          if (body.err_no !== 0) return finish(new Error(`业务失败（代码 ${body.err_no}）`));
          finish(null, body);
        });
      });
      req.on('error', () => finish(new Error('网络请求失败')));
      req.end();
    } catch { finish(new Error('请求初始化失败')); }
  });
}

function showIdentity(body, account) {
  const data = body && body.data;
  if (!data || typeof data !== 'object') return;
  const objects = [data, data.user_info, data.user];
  for (const obj of objects) {
    if (!obj || typeof obj !== 'object') continue;
    for (const key of ['nickname', 'user_name', 'username', 'display_name', 'user_id', 'uid']) {
      if (typeof obj[key] !== 'string' && typeof obj[key] !== 'number') continue;
      const value = String(obj[key]);
      // 官方非秘密身份原样输出；遇到凭据、手机号或控制字符则不输出。
      if (!value || value.includes(account.session) || /[\r\n\x00-\x1f\x7f]/.test(value) || /(?:\+?86[- ]?)?1[3-9]\d{9}/.test(value)) continue;
      log(`官方账号身份 ${key}：${value}`);
    }
  }
}

function notificationSelected(env) {
  if (disabled(env.QINGLONG_NOTIFY)) return false;
  const names = [CATALOG, path.basename(__filename), __filename, path.relative(process.cwd(), __filename).replace(/\\/g, '/')];
  if (env.QINGLONG_NOTIFY_SCRIPTS !== undefined) {
    return env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(selector => {
      const pattern = '^' + selector.split('*').map(part => part.split('?').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.')).join('.*') + '$';
      return names.some(name => new RegExp(pattern).test(name));
    });
  }
  return enabled(env.QINGLONG_NOTIFY); // 未提供默认名单，auto 不自动全选。
}
async function notify(env, summary, dry) {
  if (!notificationSelected(env)) return '未选中或已关闭';
  if (dry) { log('通知演练：已生成脱敏总结，断网模式不调用通知模块'); return '断网演练'; }
  const paths = [env.QINGLONG_NOTIFY_DIR && path.join(env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const target = paths.find(p => fs.existsSync(p));
  if (!target) { log('⚠️ 未找到青龙 sendNotify.js，保留业务结果'); return '不可用'; }
  let timer;
  try {
    const mod = await import(pathToFileURL(target).href);
    const send = mod.sendNotify || (mod.default && mod.default.sendNotify);
    if (typeof send !== 'function') throw new Error('通知契约不兼容');
    const body = `状态：${summary.status}\n账号总数：${summary.accounts}，成功：${summary.success}，失败：${summary.failed}\n子任务成功：${summary.steps.success}，已完成：${summary.steps.alreadyComplete}，跳过：${summary.steps.skipped}，失败：${summary.steps.failed}`;
    await Promise.race([Promise.resolve().then(() => send(TITLE, body)), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('通知超时')), 10000); })]);
    return '已发送';
  } catch { log('⚠️ 通知发送失败，保留业务结果'); return '失败'; }
  finally { clearTimeout(timer); }
}

async function main() {
  const env = process.env;
  const started = Date.now();
  const dry = enabled(env.JUEJIN_DRY_RUN);
  const lottery = enabled(env.JUEJIN_FREE_LOTTERY);
  const accounts = accountsFrom(env);
  const summary = { task: TITLE, mode: dry ? 'dry-run' : 'live', accounts: accounts.length, success: 0, failed: 0, configurationErrors: 0, steps: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, results: [] };
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${summary.mode}；账号数：${accounts.length}`);
  if (!accounts.length) {
    log('❌ 配置错误：请设置 JUEJIN_ACCOUNTS，每行 aid|sessionid，或兼容的旧变量对');
    summary.configurationErrors++;
  }
  for (let i = 0; i < accounts.length; i++) {
    const account = accounts[i];
    const begin = Date.now();
    const stats = { account: i + 1, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let free = null;
    log(`---------- 账号 ${i + 1} ----------`);
    async function stage(number, name, work) {
      const time = Date.now();
      stats.total++;
      log(`账号 ${i + 1} 阶段 ${number}/3：${name}`);
      try {
        const outcome = await work();
        stats[outcome.skipped ? 'skipped' : 'success']++;
        log(`${outcome.skipped ? '⏭️' : '✅'} ${outcome.msg}；耗时 ${seconds(time)} 秒`);
        console.log(JSON.stringify({ result: true, msg: outcome.msg }));
      } catch (error) {
        stats.failed++;
        log(`❌ ${name}：${error.message}；耗时 ${seconds(time)} 秒`);
        console.log(JSON.stringify({ result: false, msg: error.message }));
      }
    }
    if (!account.valid) {
      summary.configurationErrors++;
      stats.total = 1; stats.failed = 1;
      log('❌ 阶段 1/1：配置错误，需填写数字 aid 和不含分号、空白或控制字符的 sessionid');
    } else {
      await stage(1, '每日签到', async () => {
        if (dry) return { msg: 'DRY_RUN：签到请求已演练，未发送请求' };
        const body = await request(account, 'check_in', 'POST');
        showIdentity(body, account);
        return { msg: '签到成功' };
      });
      await stage(2, '查询免费抽奖次数', async () => {
        if (dry) { free = 1; return { msg: 'DRY_RUN：免费次数查询已演练，模拟一次免费机会' }; }
        const body = await request(account, 'lottery_config/get', 'GET');
        showIdentity(body, account);
        if (!body.data || !Number.isSafeInteger(body.data.free_count) || body.data.free_count < 0) throw new Error('响应缺少有效免费次数');
        free = body.data.free_count;
        return { msg: `免费抽奖次数：${free}` };
      });
      await stage(3, '可选免费抽奖', async () => {
        if (!lottery) return { skipped: true, msg: '抽奖未开启；JUEJIN_FREE_LOTTERY=1 可显式授权' };
        if (free === null) return { skipped: true, msg: '查询失败，禁止抽奖' };
        if (free === 0) return { skipped: true, msg: '没有免费次数，正常跳过抽奖' };
        if (dry) return { msg: 'DRY_RUN：免费抽奖已演练，未发送请求' };
        const body = await request(account, 'lottery/draw', 'POST');
        showIdentity(body, account);
        return { msg: '抽奖成功' };
      });
    }
    stats.durationSeconds = seconds(begin);
    stats.status = stats.failed ? 'failure' : (dry ? 'dry-run' : 'success');
    summary[stats.failed ? 'failed' : 'success']++;
    for (const key of Object.keys(summary.steps)) summary.steps[key] += stats[key];
    summary.results.push(stats);
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${stats.durationSeconds} 秒`);
  }
  const failed = summary.failed > 0 || summary.configurationErrors > 0;
  summary.status = summary.configurationErrors ? 'configuration-error' : failed ? (summary.success ? 'partial-failure' : 'failure') : (dry ? 'dry-run' : 'success');
  summary.notification = await notify(env, summary, dry);
  summary.durationSeconds = seconds(started);
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`账号统计：总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}，配置错误 ${summary.configurationErrors}`);
  log(`子任务统计：总数 ${summary.steps.total}，成功 ${summary.steps.success}，已完成 ${summary.steps.alreadyComplete}，跳过 ${summary.steps.skipped}，失败 ${summary.steps.failed}`);
  log(`完成时间：${summary.finishedAt}；总耗时 ${summary.durationSeconds} 秒；通知：${summary.notification}；最终状态：${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = failed ? 1 : 0;
  return { result: !failed, msg: failed ? '任务存在失败或配置错误' : dry ? '断网演练成功' : '任务成功' };
}
exports.main = main;
if (require.main === module) main().catch(() => {
  // 不打印异常对象，避免意外包含凭据；正常业务失败均在账号阶段内汇总。
  log('❌ 执行器异常');
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, status: 'failure', reason: '执行器异常' }));
  process.exitCode = 1;
});
