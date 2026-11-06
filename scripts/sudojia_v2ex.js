// name: V2EX每日签到
// cron: 57 9 * * *
/**
 * name: V2EX每日签到
 * cron: 0 9 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 基于 sudojia/AutoTaskScript src/web/sudojia_v2ex.js
 * 原作者 Telegram@sudojia https://blog.imzjw.cn，2024/5/22
 * V2EX_COOKIE：登录 https://www.v2ex.com 后，在开发者工具网络面板复制
 * 发往该站点的请求 Cookie 请求头值；每个非空行一个账号，不使用 & 分隔。
 * V2EX_DRY_RUN=1：完全断网预演（通知也仅模拟）；QINGLONG_NOTIFY=0 关闭通知。
 * V2EX_COOKIE 兼容原有完整 Cookie 行；也可每行填写 JSON 对象：
 * {"cookie":"完整 Cookie","proxy":"代理 URL"}，同一行组合一个账号的配置。
 * V2EX_PROXY：可选公共 HTTP/HTTPS 代理 URL；账号 proxy 优先，空值直连。
 * 代理由公开 npm 包 https-proxy-agent（7.x）提供；脚本不会下载或安装依赖。
 * Node.js >=18；签到默认开启，V2EX_CHECKIN=0 可关闭领奖。
 * V2EX_BROWSE=1 显式启用主题浏览，默认关闭以避免自动产生访问记录。
 * V2EX_TOPIC_COUNT=8 每轮主题数，V2EX_MAX_VISIT_COUNT=80 每日访问上限。
 * 兼容来源 evcli/v2ex-daily-bonus background.js（MIT，原标注 V2EX Daily Bonus Background Script）。
 * 浏览使用独立 HTTP 请求，访问后等待 5–10 秒，按 UTC 日期重置计数。
 * 活跃度达到 half/almost/done 时停止，限额和活跃度写入本地状态文件。
 * V2EX_STATE_DIR 默认脚本目录下 .v2ex-state，应放在持久目录，不可每日清理。
 * 同账号并发浏览会失败闭合。异常遗留锁需确认无运行任务后人工删除 lock 目录。
 * 保留维护版 cron 0 9 * * *。来源每三小时签到可设 0 0,3,6,9,12,15,18,21 * * *，
 * 来源每小时浏览可另设 0 * * * * 并配置 V2EX_CHECKIN=0、V2EX_BROWSE=1。
 * 浏览器的启动签到、标签页和设置变更闹钟由青龙定时任务替代。
 * 不发布文本、不更新脚本。
 * 合并参考 Jckling 签到脚本 checkin/v2ex.py，2021/04/08 09:43（MIT）。
 * 合并参考 Sitoi/dailycheckin dailycheckin/v2ex/main.py（MIT）。
 * 原有维护版本 GPL-3.0-only，合并版本继续按 GPL-3.0-only 发布。
 * MIT 许可声明（适用于上述 MIT 来源）：
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
    const identities = ["705cf315f5da6907", "scripts/sudojia_v2ex.js", "sudojia_v2ex.js", "sudojia_v2ex"];
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
const crypto = require('node:crypto');
const dry = process.env.V2EX_DRY_RUN === '1';
const started = Date.now();
const accounts = (process.env.V2EX_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const results = [];
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const stamp = () => new Date().toTimeString().slice(0, 8);
const log = text => console.log(`[${stamp()}] ${text}`);
function decode(s) {
  return s.replace(/&#(x[0-9a-f]+|\d+);/gi, (_, n) => {
    const c = n[0].toLowerCase() === 'x' ? parseInt(n.slice(1), 16) : Number(n);
    return c <= 0x10ffff ? String.fromCodePoint(c) : '';
  }).replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&');
}
const plain = s => decode(s.replace(/<[^>]*>/g, '')).replace(/[\r\n\t]/g, ' ').trim();
function accountConfig(line) {
  let cookie = line, proxy = process.env.V2EX_PROXY || '';
  if (line.startsWith('{')) {
    let data;
    try { data = JSON.parse(line); } catch { throw Error('账号 JSON 格式错误'); }
    if (!data || typeof data.cookie !== 'string') throw Error('账号 JSON 缺少 cookie 字符串');
    cookie = data.cookie;
    if (data.proxy !== undefined) proxy = data.proxy;
  }
  // 不分割 Cookie 内的等号、分号或其他凭据文本。
  if (!cookie.includes('=') || /[\x00-\x1f\x7f]/.test(cookie)) throw Error('Cookie 格式错误');
  if (typeof proxy !== 'string') throw Error('代理必须是 URL 字符串');
  let agent;
  if (proxy) {
    try {
      const url = new URL(proxy);
      if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.hash) throw Error();
    } catch { throw Error('代理格式错误：仅支持 HTTP/HTTPS URL'); }
    if (!dry) {
      let ProxyAgent;
      try { ProxyAgent = require('https-proxy-agent').HttpsProxyAgent; }
      catch { throw Error('代理依赖不可用：请在青龙依赖管理安装 https-proxy-agent 7.x'); }
      try { agent = new ProxyAgent(proxy); } catch { throw Error('代理初始化失败'); }
    }
  }
  return { cookie, agent, settings: taskSettings() };
}
function request(route, config, depth = 0) {
  if (dry) throw Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const url = new URL(route, 'https://www.v2ex.com');
    if (url.origin !== 'https://www.v2ex.com' || url.username || url.password) return reject(Error('拒绝跨站跳转'));
    const req = https.get(url, { agent: config.agent, headers: { Cookie: config.cookie, Referer: 'https://www.v2ex.com/mission/daily', Accept: 'text/html', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8', 'Accept-Encoding': 'identity', 'User-Agent': 'Mozilla/5.0 V2EXDaily/1.0' } }, res => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode)) {
        res.resume();
        if (depth >= 3 || !res.headers.location) return reject(Error('跳转异常'));
        let next;
        try { next = new URL(res.headers.location, url); } catch { return reject(Error('跳转异常')); }
        return resolve(request(next.href, config, depth + 1));
      }
      if (res.statusCode !== 200) { res.resume(); return reject(Error(`HTTP ${res.statusCode}`)); }
      let size = 0; const chunks = [];
      res.on('data', b => { size += b.length; if (size > 2 * 1024 * 1024) req.destroy(Error('响应超限')); else chunks.push(b); });
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
      res.on('error', () => reject(Error('响应读取失败')));
    });
    const timer = setTimeout(() => req.destroy(Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(Error('网络请求失败或超时')));
  });
}
function taskSettings() {
  function switchValue(name, fallback) {
    const value = process.env[name] ?? fallback;
    if (!['0', '1'].includes(value)) throw Error('任务开关仅接受 0 或 1');
    return value === '1';
  }
  function positiveInteger(name, fallback, maximum) {
    const value = process.env[name] ?? String(fallback);
    if (!/^\d+$/.test(value) || Number(value) < 1 || Number(value) > maximum) throw Error('浏览数量参数超出允许范围');
    return Number(value);
  }
  const settings = {
    checkin: switchValue('V2EX_CHECKIN', '1'),
    browse: switchValue('V2EX_BROWSE', '0'),
    topicCount: positiveInteger('V2EX_TOPIC_COUNT', 8, 80),
    maxVisits: positiveInteger('V2EX_MAX_VISIT_COUNT', 80, 80)
  };
  if (!settings.checkin && !settings.browse) throw Error('签到和浏览不能同时关闭');
  return settings;
}
function activity(html) {
  const bar = html.match(/class=["'][^"']*\bmember-activity-bar\b[^"']*["'][^>]*>\s*<div\b([^>]*)>/i);
  if (!bar) throw Error('活跃度区域缺失，停止浏览以避免超出限制');
  const cls = bar[1].match(/class=["']([^"']+)["']/i);
  if (!cls || !/\bmember-activity-[a-z-]+\b/i.test(cls[1])) throw Error('活跃度格式变化，停止浏览');
  return { stopped: /\bmember-activity-(?:half|almost|done)\b/.test(cls[1]) };
}
async function browse(config, username) {
  // 仅保存账号摘要与计数，不保存 Cookie、代理或页面。
  if (!username) throw Error('未返回稳定的官方用户名，无法安全维护每日浏览计数');
  const key = crypto.createHash('sha256').update(username).digest('hex');
  const directory = path.resolve(process.env.V2EX_STATE_DIR || path.join(__dirname, '.v2ex-state'));
  const file = path.join(directory, key + '.json');
  const lock = path.join(directory, key + '.lock');
  try { fs.mkdirSync(directory, { recursive: true, mode: 0o700 }); fs.mkdirSync(lock, { mode: 0o700 }); }
  catch { throw Error('浏览状态不可写或同账号已有运行任务，请检查状态目录及锁'); }
  try {
    const date = new Date().toISOString().slice(0, 10);
    let state = { date, visits: 0, stopped: false };
    if (fs.existsSync(file)) {
      let stored;
      try { stored = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { throw Error('浏览状态文件无法读取，停止浏览'); }
      if (!stored || typeof stored.date !== 'string' || !Number.isSafeInteger(stored.visits) || stored.visits < 0 || typeof stored.stopped !== 'boolean') throw Error('浏览状态格式错误，停止浏览');
      if (stored.date === date) state = stored;
    }
    function save() {
      const temporary = file + '.tmp';
      try { fs.writeFileSync(temporary, JSON.stringify(state), { mode: 0o600 }); fs.renameSync(temporary, file); }
      catch { throw Error('浏览计数保存失败，停止浏览'); }
    }
    if (state.visits >= config.settings.maxVisits || state.stopped) {
      log(`☑️ 今日浏览已达上限或活跃度停止条件，访问计数 ${state.visits}`);
      return 'alreadyComplete';
    }
    const recent = await request('/recent', config); loggedIn(recent);
    state.stopped = activity(recent).stopped; save();
    if (state.stopped) { log('☑️ 官方活跃度已达到停止条件'); return 'alreadyComplete'; }
    const ids = [...new Set([...recent.matchAll(/href=["']\/t\/(\d+)(?:#[^"']*)?["']/g)].map(m => m[1]))];
    if (!ids.length) throw Error('最新主题页面没有可识别主题');
    let visited = 0;
    for (const id of ids.slice(0, config.settings.topicCount)) {
      if (state.visits >= config.settings.maxVisits || state.stopped) break;
      if (new Date().toISOString().slice(0, 10) !== date) throw Error('UTC 日期已变化，请下一轮继续浏览');
      // 先预留次数，网络失败或进程中断也不会导致重试超出每日上限。
      state.visits++; save();
      const page = await request(`/t/${id}`, config); loggedIn(page);
      state.stopped = activity(page).stopped; save();
      await new Promise(resolve => setTimeout(resolve, 5000 + Math.random() * 5000));
      visited++;
      log(`✅ 浏览主题 ${id} 已验证登录和活跃度，本轮 ${visited}，今日预留访问 ${state.visits}/${config.settings.maxVisits}`);
    }
    log(`✅ 浏览完成，本轮 ${visited}，活跃度${state.stopped ? '已达到停止条件' : '未达到停止条件'}`);
    return 'success';
  } finally {
    try { fs.rmdirSync(lock); } catch { log('⚠️ 浏览锁清理失败，请检查状态目录'); }
  }
}
function loggedIn(html) { if (!html.includes('登出')) throw Error('登录状态未验证，请重新获取 Cookie'); }
function identity(html) {
  for (const m of html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)) {
    if (/class\s*=\s*["'][^"']*\btop\b/.test(m[1]) && /href\s*=\s*["']\/member\//.test(m[1])) return plain(m[2]);
  }
  return '';
}
function balance(html) {
  const m = html.match(/<(?:a|div|span)\b[^>]*class=["'][^"']*\bbalance_area\b[^"']*["'][^>]*>([\s\S]*?)<\/(?:a|div|span)>/i);
  if (!m) throw Error('余额区域缺失');
  const nums = plain(m[1]).match(/\d+/g);
  if (!nums || nums.length > 3) throw Error('余额格式无法确认');
  const values = nums.map(Number); while (values.length < 3) values.unshift(0);
  return `${values[0]}金币 ${values[1]}银币 ${values[2]}铜币`;
}
function rewardDetails(html) {
  // 只读取签到有关的账目，避免记录其他交易或账号数据。
  for (const row of html.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)) {
    const cells = [...row[1].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/gi)].map(m => plain(m[1]));
    const description = cells.find(x => /每日登录奖励|每日签到|登录奖励/.test(x));
    if (!description) continue;
    const amount = cells.find(x => /^[+−-]?\d+(?:\.\d+)?$/.test(x));
    log('今日签到账目：' + description + (amount ? '；金额：' + amount : ''));
    return;
  }
  log('今日签到账目：页面未提供可识别的奖励记录');
}
async function notify(body) {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (/^(0|false|no|off)$/.test(mode)) return '已关闭';
  if (!/^(1|true|yes|on)$/.test(mode) && process.env.QINGLONG_NOTIFY_SCRIPTS !== undefined) {
    const selectors = process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean);
    const names = ['705cf315f5da6907', '42ec6f79fddb0214', 'scripts/sudojia_v2ex.js', 'sudojia_v2ex.js', path.basename(__filename)];
    const selected = selectors.some(selector => {
      const escaped = selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
      return names.some(name => new RegExp('^' + escaped + '$').test(name));
    });
    if (!selected) return '未选中';
  }
  if (dry) { log('通知预演：' + body); return '预演模拟，未发送'; }
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = files.find(x => fs.existsSync(x));
  if (!file) return '不可用：未找到 sendNotify.js';
  return new Promise(resolve => {
    const env = { ...process.env }; delete env.V2EX_COOKIE; delete env.V2EX_PROXY;
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', file, 'V2EX每日签到', body], { env, stdio: 'ignore' });
    const timer = setTimeout(() => child.kill('SIGKILL'), 20000);
    child.on('error', () => { clearTimeout(timer); resolve('发送失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '发送失败'); });
  });
}
async function main() {
  console.log('========== V2EX每日签到 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式'}；账号数：${accounts.length}`);
  if (!accounts.length) log('❌ 配置错误：V2EX_COOKIE 未提供非空账号行');
  for (let i = 0; i < accounts.length; i++) {
    const begin = Date.now(); const stats = { total: 4, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let html = ''; let failed = false; let config; let username = ''; let authenticated = false;
    const stages = ['登录校验及用户名', '每日奖励及连续天数', '账户余额', '可选主题浏览'];
    for (let n = 0; n < stages.length; n++) {
      const tick = Date.now(); log(`账号[${i + 1}] 阶段 ${n + 1}/${stages.length} ${stages[n]} 开始`);
      let outcome = 'success';
      try {
        if (dry) {
          outcome = 'skipped';
          if (failed) log('⏭️ 前置参数校验失败');
          else {
            if (n === 0) {
              config = accountConfig(accounts[i]);
              log('✅ Cookie、代理及任务参数格式校验通过');
              log(`预演计划：领奖${config.settings.checkin ? '开启' : '关闭'}，浏览${config.settings.browse ? '开启' : '关闭'}，每轮主题 ${config.settings.topicCount}，每日上限 ${config.settings.maxVisits}`);
            }
            log('⏭️ 仅验证流程，不请求站点、不领取奖励、不浏览、不写状态文件');
          }
        }
        else if ((!authenticated && n > 0) || (failed && n < 2)) { outcome = 'skipped'; log('⏭️ 前置阶段失败'); }
        else if (n === 0) {
          config = accountConfig(accounts[i]);
          html = await request('/mission/daily', config); loggedIn(html);
          authenticated = true; username = identity(html); log(username ? `✅ 用户名称：${username}` : '✅ 登录有效；未返回用户名');
        } else if (n === 1) {
          if (!config.settings.checkin) { outcome = 'skipped'; log('⏭️ 领奖开关已关闭'); }
          else if (html.includes('每日登录奖励已领取')) { outcome = 'alreadyComplete'; log('☑️ 已经签到过了'); }
          else {
            const once = html.match(/\/mission\/daily\/redeem\?once=(\d+)/);
            if (!once) throw Error('领取入口缺失或响应已变化');
            await new Promise(r => setTimeout(r, 2000));
            html = await request(`/mission/daily/redeem?once=${once[1]}`, config);
            loggedIn(html);
            if (!html.includes('每日登录奖励已领取') && !/已成功领取每日登录奖励\s*\d+\s*铜币/.test(html)) {
              html = await request('/mission/daily', config); loggedIn(html);
              if (!html.includes('每日登录奖励已领取')) throw Error('未验证到奖励领取成功');
            }
            log('✅ 签到成功');
          }
          const days = plain(html).match(/已连续登录\s*(\d+)\s*天/);
          log(days ? `连续签到：${days[1]}天` : '连续签到天数：页面未提供');
        } else if (n === 3) {
          if (!config.settings.browse) { outcome = 'skipped'; log('⏭️ 主题浏览默认关闭，V2EX_BROWSE=1 可启用'); }
          else outcome = await browse(config, username);
        } else {
          if (!config) { outcome = 'skipped'; log('⏭️ 账号参数不可用'); }
          else { const data = await request('/balance', config); loggedIn(data); log('✅ 账户余额：' + balance(data)); rewardDetails(data); }
        }
      } catch (e) { outcome = 'failed'; failed = true; log('❌ ' + e.message); }
      stats[outcome]++; log(`账号[${i + 1}] 阶段 ${n + 1}/${stages.length} 耗时 ${Date.now() - tick}ms`);
    }
    for (const k of Object.keys(totals)) totals[k] += stats[k];
    results.push({ account: i + 1, status: failed ? 'failure' : dry ? 'dry-run' : 'success', ...stats });
    log(`账号[${i + 1}] 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${Date.now() - begin}ms`);
  }
  const failures = results.filter(x => x.status === 'failure').length;
  const validAccounts = results.length - failures;
  const successes = dry ? 0 : validAccounts;
  const dryRuns = dry ? validAccounts : 0;
  const code = !accounts.length || failures ? 1 : 0;
  const status = !accounts.length ? 'configuration-error' : failures ? validAccounts ? 'partial-failure' : 'failure' : dry ? 'dry-run' : 'success';
  const body = `状态：${status}；账号总数：${accounts.length}；成功：${successes}；失败：${failures}；预演：${dryRuns}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '发送失败'; }
  console.log('----------------------------------------');
  log(body); log(`子任务统计：${JSON.stringify(totals)}`);
  log(`通知：${notification}；总耗时：${Date.now() - started}ms；完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ status, accounts: accounts.length, success: successes, failed: failures, dryRun: dry, tasks: totals, results, notification }));
  process.exitCode = code;
}
main();
