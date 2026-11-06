// name: 巴哈姆特每日签到
// cron: 15 10 * * *
/*
 * name: 巴哈姆特每日签到
 * cron: 0 8 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 上游 NobyDa/Script — Bahamut/BahamutDailyBonus.js，更新时间 8/13/2026。
 * 来源 https://github.com/NobyDa/Script （GPL-3.0-only）。
 * 上游兼容函数注明：修改自 https://github.com/chavyleung/scripts/blob/master/Env.js
 * 上游 TOTP 注明：从 https://jsfiddle.net/russau/rbyjk774 魔改。
 * 本版独立实现 Node.js HTTPS、日志、通知及原生 crypto TOTP，不读取 box.dat。
 *
 * 参数：BAHAMUT_ACCOUNTS，每个非空行一个 JSON 对象：
 * {"uid":"账号占位符","pwd":"密码占位符","totp":""}
 * uid/pwd 为官网注册的账号密码；totp 为账号安全设置启用两步验证时保存的
 * Base32 密钥（不是六位验证码），未启用留空。JSON 可无损保存密码中的分隔符。
 * 兼容 ND_BAHA 环境变量 JSON 对象的 ID/PW/TOTP/ADS/GUILD/ANSWER 字段。
 * BAHAMUT_GUILD 默认 1；BAHAMUT_ADS 默认 0；BAHAMUT_ANSWER 默认 0。
 * 答题每天只有一次机会，上游文章可能出错，须显式开启；不会猜测答案。
 * BAHAMUT_DRY_RUN=1 完全断网预演；依赖 tough-cookie@4.1.4（青龙 Node 依赖）。
 * 每日北京时间 08:00，单账号隔离 Cookie，无自动安装、下载或私有仓库依赖。
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
    const identities = ["62449b894277f9fb", "scripts/bahamutdailybonus.js", "bahamutdailybonus.js", "bahamutdailybonus"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '巴哈姆特每日签到';
const ID = '62449b894277f9fb';
const started = Date.now();
const results = [];
let dry = false;
const log = text => console.log(`[${new Date().toLocaleTimeString('zh-CN', { hour12: false })}] ${text}`);
const ok = detail => ({ status: 'success', detail });
const already = detail => ({ status: 'alreadyComplete', detail });
const skip = detail => ({ status: 'skipped', detail });
function flag(value, fallback) {
  if (value === undefined || value === '') return fallback;
  if (/^(1|true|yes|on)$/i.test(String(value))) return true;
  if (/^(0|false|no|off)$/i.test(String(value))) return false;
  throw new Error('布尔开关格式错误，仅接受 1/0、true/false、yes/no、on/off');
}
function parseAccount(line) {
  let a;
  try { a = JSON.parse(line); } catch { throw new Error('账号必须是单行 JSON 对象'); }
  if (!a || typeof a.uid !== 'string' || !a.uid.trim() || typeof a.pwd !== 'string' || !a.pwd) {
    throw new Error('账号缺少非空 uid 或 pwd');
  }
  if (a.totp !== undefined && (typeof a.totp !== 'string' || (a.totp && !/^[A-Z2-7]{16,}=*$/i.test(a.totp)))) {
    throw new Error('totp 必须是 Base32 两步验证密钥');
  }
  return a;
}
function totp(secret, now = Date.now()) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of secret.toUpperCase().replace(/=+$/, '')) bits += alphabet.indexOf(ch).toString(2).padStart(5, '0');
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(now / 30000)));
  const mac = crypto.createHmac('sha1', Buffer.from(bytes)).update(counter).digest();
  return String((mac.readUInt32BE(mac[19] & 15) & 0x7fffffff) % 1000000).padStart(6, '0');
}
function createClient() {
  let CookieJar;
  try { ({ CookieJar } = require('tough-cookie')); } catch { fail('缺少公共 Node 依赖 tough-cookie@4.1.4，请在青龙依赖管理中安装'); }
  const jar = new CookieJar();
  async function request(url, form, extra = {}) {
    if (dry) throw new Error('预演禁止网络请求');
    const u = new URL(url);
    if (u.protocol !== 'https:' || !['api.gamer.com.tw', 'www.gamer.com.tw', 'ani.gamer.com.tw', 'guild.gamer.com.tw'].includes(u.hostname)) throw new Error('请求地址不在官方域名白名单');
    const requestStarted = Date.now();
    log(`HTTP ${form === undefined ? 'GET' : 'POST'} ${u.hostname}${u.pathname} 开始`);
    const body = form === undefined ? undefined : new URLSearchParams(form).toString();
    const headers = { 'User-Agent': 'Anime/2.13.9 (tw.com.gamer.anime;build:437;iOS 14.5.0) Alamofire/5.4.1', Cookie: jar.getCookieStringSync(url), ...extra };
    if (body !== undefined) headers['Content-Type'] = 'application/x-www-form-urlencoded';
    return new Promise((resolve, reject) => {
      const req = https.request(u, { method: body === undefined ? 'GET' : 'POST', headers }, res => {
        let chunks = [], length = 0;
        res.on('error', () => reject(new Error('响应读取失败')));
        res.on('data', chunk => { length += chunk.length; if (length > 2 * 1024 * 1024) req.destroy(new Error('响应超过大小限制')); else chunks.push(chunk); });
        res.on('end', () => {
          clearTimeout(timer);
          log(`HTTP ${res.statusCode} ${u.pathname}，耗时 ${Date.now() - requestStarted}ms`);
          if (res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP ${res.statusCode}，拒绝重定向或异常响应`));
          try {
            for (const c of res.headers['set-cookie'] || []) jar.setCookieSync(c, url);
            resolve(Buffer.concat(chunks).toString('utf8'));
          } catch { reject(new Error('服务端 Cookie 格式异常')); }
        });
      });
      const timer = setTimeout(() => req.destroy(new Error('请求超时（20秒）')), 20000);
      req.on('error', e => { clearTimeout(timer); reject(new Error(e.message === '请求超时（20秒）' ? e.message : 'HTTPS 请求失败（详情已脱敏）')); });
      req.end(body);
    });
  }
  return {
    jar, request,
    json: async (url, form, extra) => {
      const text = await request(url, form, extra);
      try { const j = JSON.parse(text); if (!j || typeof j !== 'object' || Array.isArray(j)) throw 0; return j; }
      catch { throw new Error('接口未返回预期 JSON 对象'); }
    }
  };
}
function signedBefore(j) {
  return /今天.*已經簽到過|今日.*已經簽到過/.test(String(j.error?.message || j.msg || '')) && !j.nologin && j.error?.code !== 401;
}
function answeredBefore(j) {
  return !j.nologin && /今日已經答過題目/.test(String(j.msg || ''));
}
function counts(rows) {
  const c = { total: rows.length, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
  for (const r of rows) c[r.status]++;
  return c;
}
async function stage(account, name, action) {
  const begin = Date.now(), n = account.steps.length + 1;
  log(`账号 ${account.index} 阶段 ${n}：${name} 开始`);
  let r;
  try { r = await action(); } catch (e) { r = { status: 'failure', detail: e.safe ? e.message : '任务失败，接口返回或运行环境未满足预期（原始详情不输出）' }; }
  r = { name, ...r, durationMs: Date.now() - begin };
  account.steps.push(r);
  log(`账号 ${account.index} 阶段 ${n}：${name} ${r.status}；${r.detail}；耗时 ${r.durationMs}ms`);
  return r.status !== 'failure';
}
function fail(message) { const e = new Error(message); e.safe = true; throw e; }
async function guilds(c) {
  const text = await c.request('https://api.gamer.com.tw/ajax/common/topBar.php?type=forum');
  const ids = [...new Set([...text.matchAll(/guild\.php\?g?sn=(\d+)/g)].map(m => m[1]))];
  if (!ids.length) fail('未识别到公会列表；可能没有加入公会或页面结构变化，可关闭公会任务');
  let success = 0, complete = 0, failure = 0;
  for (const sn of ids) {
    try {
      const j = await c.json('https://guild.gamer.com.tw/ajax/guildSign.php', { sn });
      if (j.ok === 1) { success++; log(`公会 ${sn}：签到成功`); }
      else if (signedBefore(j)) { complete++; log(`公会 ${sn}：今日已签到`); }
      else { failure++; log(`公会 ${sn}：未确认签到成功`); }
    } catch { failure++; log(`公会 ${sn}：请求失败`); }
  }
  const detail = `公会总数 ${ids.length}，成功 ${success}，已完成 ${complete}，失败 ${failure}`;
  if (failure) fail(detail);
  return success ? ok(detail) : already(detail);
}
async function quiz(c) {
  const q = await c.json('https://ani.gamer.com.tw/ajax/animeGetQuestion.php?t=' + Date.now());
  if (answeredBefore(q)) return already('今日已答题');
  if (!q.token || !q.question || ![q.a1, q.a2, q.a3, q.a4].every(x => typeof x === 'string' && x)) fail('题目或选项不完整，不提交答案');
  const home = await c.json('https://api.gamer.com.tw/mobile_app/bahamut/v1/home.php?owner=blackXblue&page=1');
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Taipei', month: '2-digit', day: '2-digit' }).format(new Date());
  const articles = (Array.isArray(home.creation) ? home.creation : []).filter(a => typeof a.title === 'string' && a.title.includes(parts) && /^\d+$/.test(String(a.sn)));
  if (articles.length !== 1) fail('当日答案文章缺失或不唯一，不猜测答案');
  const article = await c.json('https://api.gamer.com.tw/mobile_app/bahamut/v1/home_creation_detail.php?sn=' + articles[0].sn);
  const matches = [...String(article.content || '').matchAll(/A:\s*([1-4])(?!\d)/g)];
  if (matches.length !== 1) fail('文章答案缺失或有歧义，不提交答案');
  const answer = await c.json('https://ani.gamer.com.tw/ajax/animeAnsQuestion.php', { token: q.token, ans: matches[0][1], t: Date.now() });
  if (answeredBefore(answer)) return already('今日已答题');
  if (answer.ok !== 1 || typeof answer.gift !== 'string' || !answer.gift) fail('未确认答题正确，今日机会可能已使用');
  return ok('官方已确认答题成功并返回奖励');
}
async function runAccount(line, index, config) {
  const a = { index, steps: [], durationMs: 0 }, begin = Date.now();
  results.push(a);
  let credential, client, token;
  const valid = await stage(a, '参数校验', async () => { try { credential = parseAccount(line); } catch (e) { fail(e.message); } return ok('账号和两步验证参数格式有效'); });
  if (valid) {
    const login = await stage(a, '登录与身份核对', async () => {
      if (dry) return skip('DRY_RUN：计划登录，不连接服务、不生成会话');
      client = createClient();
      const url = 'https://api.gamer.com.tw/mobile_app/user/v3/do_login.php';
      const form = { uid: credential.uid, passwd: credential.pwd, vcode: '6666' };
      if (credential.totp) form.twoStepAuth = totp(credential.totp);
      const j = await client.json(url, form, { Cookie: 'ckAPP_VCODE=6666' });
      if (j.success !== true || typeof j.userid !== 'string' || !j.userid) fail('登录未通过业务校验，请核对账号密码、两步验证密钥或验证码要求');
      // 官方非凭据身份按返回值显示；不输出用户提供的登录参数或服务端消息。
      log(`账号 ${index} 官方身份：${j.userid}${typeof j.nickname === 'string' ? `，昵称：${j.nickname}` : ''}`);
      if (!client.jar.getCookiesSync('https://www.gamer.com.tw/').length) fail('登录成功但未取得主站会话 Cookie');
      return ok('登录与会话校验通过');
    });
    for (const [name, enabled, action] of [
      ['公会签到', config.guild, () => guilds(client)],
      ['主站签到', true, async () => {
        token = (await client.request('https://www.gamer.com.tw/ajax/get_csrf_token.php')).trim();
        if (!/^[A-Za-z0-9_-]{16,512}$/.test(token)) fail('签到令牌格式异常');
        const j = await client.json('https://www.gamer.com.tw/ajax/signin.php', { action: 1, token });
        if (signedBefore(j)) return already('主站今日已签到');
        if (j.error || !Number.isInteger(j.data?.days) || j.data.days < 1) fail('主站签到未通过业务校验');
        return ok(`主站签到成功，连续 ${j.data.days} 天`);
      }],
      ['双倍广告奖励', config.ads, async () => {
        if (!token) fail('没有可用签到令牌，无法领取广告奖励');
        const csrf = token.slice(0, 16);
        const rune = client.jar.getCookiesSync('https://api.gamer.com.tw/').find(v => v.key === 'BAHARUNE');
        if (!rune) fail('缺少广告奖励所需登录 Cookie');
        const headers = { 'X-Bahamut-Csrf-Token': csrf, Cookie: `ckBahamutCsrfToken=${csrf};BAHARUNE=${rune.value}` };
        const prefix = 'https://api.gamer.com.tw/mobile_app/bahamut/v1/sign_in_ad_';
        let j = await client.json(prefix + 'start.php', {}, headers);
        if (j.error || ![0, 1].includes(j.data?.finished)) fail('广告奖励启动未通过业务校验');
        if (j.data.finished === 1) return already('广告奖励已完成');
        log('广告奖励：等待上游要求的 30 秒后领取');
        await new Promise(resolve => setTimeout(resolve, 30000));
        j = await client.json(prefix + 'finished.php', {}, headers);
        if (j.error || j.data?.finished !== 1) fail('未确认广告奖励到账');
        return ok('双倍签到广告奖励领取成功');
      }],
      ['动画疯答题', config.answer, () => quiz(client)]
    ]) {
      await stage(a, name, async () => {
        if (!enabled) return skip('开关关闭');
        if (!login) fail('登录失败，本动作未执行');
        if (dry) return skip('DRY_RUN：计划执行，不请求、不提交、不领取');
        return action();
      });
    }
  }
  a.durationMs = Date.now() - begin;
  a.statistics = counts(a.steps);
  a.status = a.statistics.failure ? 'failure' : dry ? 'dry-run' : 'success';
  log(`账号 ${index} 统计：总任务 ${a.statistics.total}，成功 ${a.statistics.success}，已完成 ${a.statistics.alreadyComplete}，跳过 ${a.statistics.skipped}，失败 ${a.statistics.failure}；耗时 ${a.durationMs}ms；${a.status}`);
}
function selected() {
  const value = process.env.QINGLONG_NOTIFY || 'auto';
  if (/^(0|false|no|off)$/i.test(value)) return false;
  const explicit = /^(1|true|yes|on)$/i.test(value);
  if (!explicit && value !== 'auto') return false;
  const list = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (list === undefined) return explicit; // listed-only，无默认选择名单
  const names = [ID, 'candidate.js', 'BahamutDailyBonus.js', path.basename(__filename), __filename.replace(/^.*\/scripts\//, '')];
  return list.split(/[,;\s]+/).filter(Boolean).some(s => {
    const regex = new RegExp('^' + s.split('*').map(x => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(n => regex.test(n));
  });
}
async function notify(summary) {
  if (!selected()) return '未选择或全局关闭';
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'];
  const file = candidates.find(p => p && fs.existsSync(p));
  if (!file) { log('通知：未找到青龙 sendNotify.js，保留业务退出码'); return '通知不可用'; }
  // 子进程隔离第三方输出及退出码；预演连通知网络也禁止。
  const code = `
    if(process.env.QL_NOTIFICATION_DRY === '1') {
      const deny=()=>{throw Error('dry-run network disabled')};
      for(const m of ['http','https']) { const x=require(m); x.request=deny; x.get=deny; }
      const net=require('net'); net.Socket.prototype.connect=deny; net.connect=deny; net.createConnection=deny;
      global.fetch=deny;
      require('child_process').spawn=deny; require('child_process').exec=deny;
    }
    Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1));`;
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', code, file, TITLE, summary], { stdio: 'ignore', env: { ...process.env, QL_NOTIFICATION_DRY: dry ? '1' : '0' } });
    const timer = setTimeout(() => { child.kill('SIGKILL'); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve('通知不可用'); });
    child.on('close', code => { clearTimeout(timer); resolve(dry ? '预演通知已尝试（禁止联网）' : code === 0 ? '已发送' : '通知失败或超时'); });
  });
}
async function main() {
  let configurationError = false;
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}`);
  try {
    dry = flag(process.env.BAHAMUT_DRY_RUN, false);
    log(`运行模式：${dry ? 'DRY_RUN（完全断网）' : '正式执行'}`);
    let legacy = {};
    if (process.env.ND_BAHA) { try { legacy = JSON.parse(process.env.ND_BAHA); if (!legacy || typeof legacy !== 'object' || Array.isArray(legacy)) throw 0; } catch { fail('ND_BAHA 必须是 JSON 对象'); } }
    const config = {
      guild: flag(process.env.BAHAMUT_GUILD ?? legacy.GUILD, true),
      ads: flag(process.env.BAHAMUT_ADS ?? legacy.ADS, false),
      answer: flag(process.env.BAHAMUT_ANSWER ?? legacy.ANSWER, false)
    };
    const raw = process.env.BAHAMUT_ACCOUNTS !== undefined ? process.env.BAHAMUT_ACCOUNTS : legacy.ID || legacy.PW ? JSON.stringify({ uid: legacy.ID, pwd: legacy.PW, totp: legacy.TOTP || '' }) : '';
    const lines = raw.split(/\r?\n/).filter(line => line.trim());
    log(`账号数量：${lines.length}`);
    if (!lines.length) fail('缺少 BAHAMUT_ACCOUNTS，请按每行一个账号 JSON 配置');
    for (let i = 0; i < lines.length; i++) await runAccount(lines[i], i + 1, config);
  } catch (e) {
    configurationError = true;
    log(`配置或运行错误：${e.safe ? e.message : '运行环境异常（详情已脱敏）'}`);
  }
  const failed = results.filter(r => r.status === 'failure').length;
  const success = results.length - failed;
  const exitCode = configurationError || failed ? 1 : 0;
  const status = configurationError ? 'configuration-error' : failed ? success ? 'partial-failure' : 'failure' : dry ? 'dry-run' : 'success';
  const stats = counts(results.flatMap(a => a.steps));
  const body = `状态 ${status}；账号总数 ${results.length}，${dry ? '预演通过' : '成功'} ${success}，失败 ${failed}；子任务成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failure}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '通知失败'; }
  log('----------------------------------------');
  log(body);
  log(`通知状态：${notification}`);
  log(`总耗时 ${Date.now() - started}ms；完成时间 ${new Date().toISOString()}；最终状态 ${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, status, mode: dry ? 'dry-run' : 'live', accountCount: results.length, successCount: dry ? 0 : success, dryRunCount: dry ? success : 0, failureCount: failed, configurationError, statistics: stats, accounts: results, notification, startedAt: new Date(started).toISOString(), finishedAt: new Date().toISOString(), durationMs: Date.now() - started, exitCode }));
  process.exitCode = exitCode;
}
main().catch(() => { process.exitCode = 1; });
