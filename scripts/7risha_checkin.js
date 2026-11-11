// name: 七日杀中文网每日签到
// cron: * * * * *
// 来源 Crack22/loon-plugins，loon-7risha/7risha_checkin.js、7risha_cookie.js
// 上游许可 MIT。保留原始署名，原始文件未附其他版权声明。
/*
MIT License
Copyright (c) Crack22
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
*/
// RISHA_COOKIE 每个非空行填写一个完整 Cookie，兼容 risha_cookie。
// 浏览器登录 https://www.7risha.com 后打开 /sign，在开发者工具的网络面板
// 找到该站请求，复制请求头 Cookie（包含 wordpress_logged_in_ 登录字段）。
// 默认每天本地时间 08:30 起一小时内执行，成功后当天不重复执行。
// RISHA_TIME_ENABLED=true，RISHA_TIME_MODE=fixed/random，搭配 RISHA_TIME=09:30
// 或 RISHA_TIME_RANGE=08:00-10:00。兼容同名小写 risha_time_* 变量。
// RISHA_MANUAL_RUN=true 忽略时间窗口和当日完成记录，仍由服务端判断已签到。
// RISHA_DRY_RUN=1 完全断网且不写状态，通知摘要仅本地展示。
'use strict';
// qinglong-notification-policy: begin
(() => {
  const raw = process.env.QINGLONG_NOTIFY;
  if (raw !== undefined && String(raw).trim() !== '' && String(raw).trim().toLowerCase() !== 'auto') return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["33127dbe2f8bdda2", "scripts/7risha_checkin.js", "7risha_checkin.js", "7risha_checkin"];
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
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const TITLE = '七日杀中文网每日签到';
const env = process.env;
const enabled = value => /^(1|true|yes|on)$/i.test(value || '');
const setting = (name, fallback = '') => env[name] ?? env[name.toLowerCase()] ?? fallback;
const dryRun = enabled(env.RISHA_DRY_RUN);
const start = Date.now();
const stats = { accounts: 0, success: 0, failed: 0, skipped: 0, tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, mode: dryRun ? 'dry-run' : 'live' };
const timestamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = message => console.log(`[${timestamp()}] ${message}`);
const elapsed = since => `${((Date.now() - since) / 1000).toFixed(2)}秒`;
function localDay() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}
function parseTime(value) {
  const match = /^(\d{1,2}):(\d{1,2})$/.exec(value.trim());
  if (!match || +match[1] > 23 || +match[2] > 59) return null;
  return +match[1] * 60 + +match[2];
}
function targetMinute(day) {
  if (!enabled(setting('RISHA_TIME_ENABLED'))) return 510;
  const mode = setting('RISHA_TIME_MODE').trim();
  if (mode === 'fixed') return parseTime(setting('RISHA_TIME')) ?? 510;
  if (mode === 'random') {
    const range = setting('RISHA_TIME_RANGE').trim();
    const parts = range.split('-');
    if (parts.length === 2) {
      const first = parseTime(parts[0]);
      const last = parseTime(parts[1]);
      if (first !== null && last !== null && last > first) {
        // 当日稳定的伪随机时间，所有账号共用同一时间，重启不会重新选时。
        const hash = crypto.createHash('sha256').update(`${day}|${range}|7risha`).digest();
        return first + hash.readUInt32BE(0) % (last - first + 1);
      }
    }
  }
  log('时间配置无效，使用默认 08:30');
  return 510;
}
function requestSign(cookie) {
  return new Promise((resolve, reject) => {
    const request = https.request('https://www.7risha.com/wp-content/themes/LightSNS/module/action/sign.php', {
      method: 'POST',
      headers: {
        Cookie: cookie,
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        Referer: 'https://www.7risha.com/sign',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength('sign=1')
      }
    }, response => {
      let size = 0;
      const chunks = [];
      response.on('data', chunk => {
        size += chunk.length;
        if (size > 65536) request.destroy(new Error('响应超过大小限制'));
        else chunks.push(chunk);
      });
      response.on('error', () => reject(new Error('响应传输失败')));
      response.on('end', () => {
        if (response.statusCode !== 200) return reject(new Error('HTTP 状态异常，请检查登录态或稍后重试'));
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch { reject(new Error('响应格式异常，请检查登录态')); }
      });
    });
    const timer = setTimeout(() => request.destroy(new Error('请求超时')), 15000);
    request.on('close', () => clearTimeout(timer));
    request.on('error', () => reject(new Error('网络请求失败或超时')));
    request.end('sign=1');
  });
}
function identity(result, cookie) {
  for (const field of ['nickname', 'username', 'display_name', 'public_uid', 'uid']) {
    const value = result[field] ?? result.data?.[field];
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const text = String(value);
    const secretValues = cookie.split(';').map(part => part.slice(part.indexOf('=') + 1).trim()).filter(Boolean);
    if (!text || text.length > 200 || /[\r\n\x00-\x1f]|\b\d{11,}\b|@|wordpress_logged_in_|token|session|cookie/i.test(text)) continue;
    if (secretValues.some(secret => text.includes(secret))) continue;
    log(`官方账号身份 ${text}`);
    break;
  }
}
function notificationSelected() {
  const mode = (env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (/^(0|false|no|off)$/.test(mode)) return false;
  if (/^(1|true|yes|on)$/.test(mode)) return true;
  if (env.QINGLONG_NOTIFY_SCRIPTS === undefined) return false;
  const names = ['33127dbe2f8bdda2', 'candidate.js', '7risha_checkin.js', 'checkin/7risha_checkin.js'];
  return env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(selector => {
    const pattern = selector.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    return names.some(name => new RegExp(`^${pattern}$`).test(name));
  });
}
async function notify(body) {
  if (dryRun) {
    log(`通知预演（断网） ${body}`);
    return 'dry-run';
  }
  if (!notificationSelected()) return 'disabled';
  const directories = [env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const modulePath = directories.map(dir => path.join(dir, 'sendNotify.js')).find(file => fs.existsSync(file));
  if (!modulePath) { log('⚠️ 未发现 sendNotify.js，保留业务退出码'); return 'unavailable'; }
  return new Promise(resolve => {
    // 通过参数传递摘要，不输出通知模块日志或异常，限制通知耗时。
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).catch(() => process.exitCode = 1)', modulePath, TITLE, body], { stdio: 'ignore' });
    const timer = setTimeout(() => child.kill('SIGKILL'), 15000);
    child.on('error', () => { clearTimeout(timer); resolve('failed'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? 'sent' : 'failed'); });
  });
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间 ${new Date(start).toLocaleString('zh-CN')} | 模式 ${stats.mode}`);
  const cookies = (env.RISHA_COOKIE || env.risha_cookie || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  stats.accounts = cookies.length;
  log(`账号数量 ${cookies.length}`);
  let lockPath;
  let locked = false;
  try {
    const configurationStart = Date.now();
    log('阶段 1 参数与调度检查');
    if (!cookies.length) throw new Error('配置错误，请设置 RISHA_COOKIE，每个非空行一个账号');
    const stateFile = env.RISHA_STATE_FILE || path.join(__dirname, '.7risha-state.json');
    const state = {};
    if (!dryRun) {
      lockPath = `${stateFile}.lock`;
      try { fs.mkdirSync(lockPath, { mode: 0o700 }); locked = true; }
      catch { throw new Error('无法获取状态锁，请检查并发任务或异常退出遗留锁'); }
      try {
        const stored = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
        if (!stored || typeof stored !== 'object' || Array.isArray(stored)) throw new Error();
        Object.assign(state, stored);
      } catch (error) {
        if (error.code !== 'ENOENT') throw new Error('无法读取签到状态，请检查状态文件');
      }
    }
    const day = localDay();
    const target = targetMinute(day);
    const now = new Date();
    const minute = now.getHours() * 60 + now.getMinutes();
    const manual = enabled(setting('RISHA_MANUAL_RUN')) || enabled(env.manualRun);
    log(`调度目标 ${String(Math.floor(target / 60)).padStart(2, '0')}:${String(target % 60).padStart(2, '0')}，窗口60分钟，手动模式${manual ? '开启' : '关闭'}`);
    log(`阶段 1 参数与调度检查完成，耗时${elapsed(configurationStart)}`);
    for (const [index, cookie] of cookies.entries()) {
      const accountStart = Date.now();
      const key = crypto.createHash('sha256').update(cookie).digest('hex');
      let outcome = 'failed';
      stats.tasks.total++;
      log(`阶段 2.${index + 1} 账号 ${index + 1} 签到开始`);
      try {
        if (/[\x00-\x1f\x7f]/.test(cookie) || !/(?:^|;\s*)wordpress_logged_in_[^=;\s]+=\S+/.test(cookie)) throw new Error('Cookie 格式无效，缺少 WordPress 登录字段');
        if (dryRun) {
          outcome = 'success';
          log('✅ DRY_RUN_OK 凭据格式、签到请求和结果分支预演通过，未发起请求或写入状态');
        } else if (!manual && (state[key] === day || minute < target || minute >= target + 60)) {
          outcome = 'skipped';
          log('⏭️ 当天已成功运行或当前处于时间窗口外');
        } else {
          const result = await requestSign(cookie);
          if (!result || typeof result !== 'object') throw new Error('签到响应无效');
          identity(result, cookie);
          if (result.code === 8) throw new Error('需先在官网绑定手机号');
          if (result.code === 9) throw new Error('需先在官网绑定邮箱');
          if (result.code !== 1 && result.code !== 2) throw new Error('签到业务失败，请检查登录态并重新获取 Cookie');
          const days = Number.isSafeInteger(Number(result.sign_c)) && Number(result.sign_c) >= 0 ? `，累计签到 ${Number(result.sign_c)} 天` : '';
          log(`${result.code === 1 ? '✅ SIGN_SUCCESS 签到成功' : '☑️ ALREADY_COMPLETE 今日已签到'}${days}`);
          state[key] = day;
          const temporary = `${stateFile}.${process.pid}.tmp`;
          try {
            fs.writeFileSync(temporary, JSON.stringify(state), { mode: 0o600 });
            fs.renameSync(temporary, stateFile);
          } catch { throw new Error('签到已由服务端确认，但本地完成状态保存失败'); }
          finally { try { fs.unlinkSync(temporary); } catch {} }
          outcome = result.code === 1 ? 'success' : 'alreadyComplete';
        }
      } catch (error) {
        // 仅允许本脚本定义的固定错误文本进入日志。
        const message = /^(Cookie 格式无效|需先在官网|签到业务失败|签到响应无效|HTTP 状态异常|响应格式异常|响应传输失败|网络请求失败|签到已由服务端确认)/.test(error.message) ? error.message : '账号执行失败，请检查配置或稍后重试';
        log(`❌ ${message}`);
      }
      stats.tasks[outcome]++;
      if (outcome === 'failed') stats.failed++;
      else if (outcome === 'skipped') stats.skipped++;
      else stats.success++;
      log(`账号 ${index + 1} 统计 总任务1 成功${outcome === 'success' ? 1 : 0} 已完成${outcome === 'alreadyComplete' ? 1 : 0} 跳过${outcome === 'skipped' ? 1 : 0} 失败${outcome === 'failed' ? 1 : 0} 耗时${elapsed(accountStart)}`);
    }
  } catch (error) {
    stats.configurationError = true;
    log(error.message.startsWith('配置错误') || /^(无法获取状态锁|无法读取签到状态)/.test(error.message) ? `❌ ${error.message}` : '❌ 任务配置或本地状态异常');
  } finally {
    if (locked) { try { fs.rmdirSync(lockPath); } catch { log('⚠️ 状态锁清理失败'); } }
  }
  const failed = stats.failed > 0 || !!stats.configurationError;
  stats.status = stats.configurationError ? 'configuration-error' : failed ? (stats.success ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : stats.skipped === stats.accounts ? 'skipped' : 'success';
  const body = `账号总数${stats.accounts}，成功${stats.success}，失败${stats.failed}，跳过${stats.skipped}，状态${stats.status}`;
  log('阶段 3 汇总与通知');
  const notificationStart = Date.now();
  stats.notification = await notify(body);
  if (stats.notification === 'failed') log('⚠️ 通知发送失败，保留业务退出码');
  log(`阶段 3 汇总与通知完成，耗时${elapsed(notificationStart)}`);
  console.log('----------------------------------------');
  log(body);
  log(`子任务统计 总数${stats.tasks.total} 成功${stats.tasks.success} 已完成${stats.tasks.alreadyComplete} 跳过${stats.tasks.skipped} 失败${stats.tasks.failed}`);
  log(`完成时间 ${new Date().toLocaleString('zh-CN')} | 总耗时 ${elapsed(start)} | 通知 ${stats.notification} | 最终状态 ${stats.status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(stats)}`);
  process.exitCode = failed ? 1 : 0;
}
main().catch(() => { log('❌ 未预期的运行错误'); process.exitCode = 1; });
