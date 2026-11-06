#!/usr/bin/env node
// name: Discuz 每日签到
// cron: 46 9 * * *
// 来源：guoxpeng/daily-checkin-panel，src/sites/misign.js（MIT）
// 原始说明：Discuz k_misign 签到插件 · 通用模块
// 适用于安装了 k_misign 每日签到插件的 Discuz 论坛（如阅次元 abooky.com）：
// ① GET {base}/plugin.php?id=k_misign:sign → 含「您的签到排名」= 今日已签到
// ② 提取 JD_sign 签到链接并 GET（登录页表示 Cookie 失效）
// ③ 再 GET 签到页确认排名，奖励从 lxreward 提取。
// 凭据：浏览器登录目标论坛后复制的 Cookie。
/*
 * MIT License
 * Upstream attribution: guoxpeng/daily-checkin-panel contributors.
 * Input source contains no separate copyright notice; original attribution retained above.
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
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
/*
 * Node.js >=18，无业务依赖。推荐每天 08:15（青龙时区），上游未提供固定 cron。
 * MISIGN_ACCOUNTS：每个非空行一个账号，JSON 对象包含原字段 base_url、cookie，
 * 可选 user_agent；也支持 论坛地址|Cookie，仅在首个 | 分隔，后续内容保持完整。
 * 论坛地址可包含子目录，无协议时补 https://；仅支持 HTTPS，拒绝明文传输凭据。
 * 获取：浏览器登录论坛（必要时先完成人机验证），F12→网络→签到页请求，
 * 复制 Cookie 请求头；确认签到页为 plugin.php?id=k_misign:sign。
 * MISIGN_USER_AGENT 可选，建议与获取 Cookie 的浏览器一致，账号 user_agent 优先。
 * MISIGN_TIMEOUT_MS：单次请求含读取响应的超时，默认 15000，范围 1000～60000。
 * MISIGN_DRY_RUN=1：仅验证参数和离线流程，不请求网站，不调用通知发送器。
 * QINGLONG_NOTIFY=auto|1|0（也接受 true/yes/on、false/no/off）。auto 仅命中
 * QINGLONG_NOTIFY_SCRIPTS 列表时通知；列表支持目录相对路径、文件名、通配符和目录编号。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录；否则探测标准目录。
 * 只进行每日签到，不发帖、不点赞、不修改账号信息、不自动更新存储凭据。
 * 浏览器扩展执行机制由独立 HTTP 实现替代；遇站点人机验证时需人工重新获取 Cookie。
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
    const identities = ["08bb0c214d8ab765", "scripts/guoxpeng_daily_checkin_panel_sites.js", "guoxpeng_daily_checkin_panel_sites.js", "guoxpeng_daily_checkin_panel_sites"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const fs = require('node:fs');
const path = require('node:path');
const { fork } = require('node:child_process');
const TITLE = 'Discuz 每日签到';
const CATALOG = '08bb0c214d8ab765';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
const env = process.env;
const dry = env.MISIGN_DRY_RUN === '1';
const started = Date.now();
const secrets = [];
const summary = { task: TITLE, mode: dry ? 'dry-run' : 'live', accounts: 0, success: 0, failed: 0, alreadyComplete: 0, skipped: 0, tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, results: [] };
function redact(value) {
  let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const secret of secrets) if (secret) s = s.split(secret).join('[凭据已隐藏]');
  return s.replace(/(?:Cookie|Token|session|formhash)\s*[:=]\s*\S+/gi, '[敏感字段已隐藏]').replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, '[手机号已隐藏]');
}
function log(s) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${redact(s)}`); }
function fail(message) { throw new Error(message); }
function unesc(s) {
  return String(s || '').replace(/&#(x[0-9a-f]+|\d+);/gi, (_, n) => {
    const c = n[0].toLowerCase() === 'x' ? parseInt(n.slice(1), 16) : Number(n);
    return c > 0 && c <= 0x10ffff ? String.fromCodePoint(c) : '';
  }).replace(/&amp;/gi, '&').replace(/&quot;/gi, '"').replace(/&apos;|&#039;/gi, "'").replace(/&lt;/gi, '<').replace(/&gt;/gi, '>').replace(/&nbsp;/gi, ' ');
}
function text(s) { return unesc(String(s).replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '').replace(/<[^>]*>/g, '')).trim(); }
function attrs(tag) {
  const out = {};
  for (const m of tag.matchAll(/([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)) out[m[1].toLowerCase()] = unesc(m[2] ?? m[3] ?? m[4]);
  return out;
}
function parseAccount(line) {
  let a;
  if (line.startsWith('{')) {
    try { a = JSON.parse(line); } catch { fail('账号 JSON 无效，请检查字段与引号'); }
    if (!a || Array.isArray(a)) fail('账号必须是 JSON 对象');
  } else {
    const i = line.indexOf('|');
    if (i < 1) fail('账号格式应为 JSON 对象或论坛地址|Cookie');
    a = { base_url: line.slice(0, i), cookie: line.slice(i + 1) };
  }
  if (typeof a.cookie !== 'string' || !a.cookie.trim()) fail('Cookie 未配置');
  secrets.push(a.cookie, ...a.cookie.split(';').map(s => s.slice(s.indexOf('=') + 1).trim()).filter(v => v.length >= 4));
  const cookie = a.cookie.trim();
  if (/[\r\n\x00-\x1f\x7f]/.test(cookie) || !cookie.includes('=')) fail('Cookie 格式无效，应复制请求头值，不含字段名');
  if (typeof a.base_url !== 'string' || !a.base_url.trim()) fail('论坛地址未配置');
  let raw = a.base_url.trim().replace(/\/+$/, '');
  if (!/^\w+:\/\//.test(raw)) raw = 'https://' + raw;
  let base;
  try { base = new URL(raw); } catch { fail('论坛地址格式无效'); }
  if (base.protocol !== 'https:' || base.username || base.password || base.search || base.hash) fail('论坛地址必须为不含凭据、查询和片段的 HTTPS 首页地址');
  base.pathname = base.pathname.replace(/\/+$/, '') + '/';
  const ua = a.user_agent || env.MISIGN_USER_AGENT || UA;
  if (typeof ua !== 'string' || /[^\x20-\x7e]/.test(ua)) fail('User-Agent 必须为单行可打印英文请求头');
  return { base, cookie, ua, sign: new URL('plugin.php?id=k_misign:sign', base) };
}
function safeUrl(raw, a) {
  let u;
  try { u = new URL(raw, a.base); } catch { fail('签到地址无效'); }
  if (u.origin !== a.base.origin || u.username || u.password || u.hash || u.pathname !== a.sign.pathname || u.searchParams.get('id') !== 'k_misign:sign') fail('拒绝非同源或非 k_misign 的签到地址');
  if (new Set(u.searchParams.keys()).size !== [...u.searchParams.keys()].length) fail('拒绝含重复参数的签到地址');
  const operation = u.searchParams.get('operation');
  if ((operation && operation !== 'qiandao') || u.searchParams.has('action')) fail('拒绝非签到操作');
  return u;
}
function findLink(html, a) {
  html = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '');
  const links = [...html.matchAll(/<a\b[^>]*>/gi)].map(m => attrs(m[0]));
  let link = links.find(x => x.id === 'JD_sign');
  if (!link) link = links.find(x => {
    if (!x.href) return false;
    try { const u = safeUrl(x.href, a); return u.searchParams.get('operation') === 'qiandao'; } catch { return false; }
  });
  if (!link || !link.href) fail('未找到有效签到按钮，请确认插件类型或页面是否改版');
  if (/mod=logging|action=login/i.test(link.href)) fail('登录已失效，请重新获取 Cookie');
  return safeUrl(link.href, a);
}
function pageState(html) {
  const visible = text(html);
  const loginForm = /<form\b[^>]*(?:id=["']loginform|action=["'][^"']*mod=logging)/i.test(html) || (/name=["']password["']/i.test(html) && /name=["']username["']/i.test(html));
  if (loginForm && !/action=logout|退出登录/i.test(html)) fail('登录已失效，请在浏览器登录后重新获取 Cookie');
  if (/cf-chl-|challenge-platform|cf-turnstile|Please enable JavaScript and refresh the page/i.test(html)) fail('站点要求人机验证，请在浏览器完成后重新获取 Cookie');
  return visible.includes('您的签到排名');
}
function showIdentity(html, label) {
  // Discuz 登录用户区内的个人空间链接；不把签到排行榜里其他用户当成当前账号。
  const um = html.match(/<div\b[^>]*id=["']um["'][^>]*>([\s\S]*?)<\/div>/i);
  if (!um) return;
  const strong = um[1].match(/<strong\b[^>]*>([\s\S]*?)<\/strong>/i);
  if (!strong) return;
  const anchor = strong[1].match(/<a\b([^>]*)>([\s\S]*?)<\/a>/i);
  if (!anchor) return;
  const href = attrs('<a ' + anchor[1] + '>').href || '';
  if (!/mod=space/i.test(href)) return;
  const nick = text(anchor[2]);
  const uid = href.match(/[?&]uid=(\d+)/);
  if (nick) log(`${label} 官方昵称：${nick}`);
  if (uid) log(`${label} 公开 UID：${uid[1]}`);
}
async function getPage(url, a, timeout) {
  if (dry) fail('断网预演禁止请求');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    let current = url;
    for (let hop = 0; hop <= 3; hop++) {
      const r = await fetch(current, { method: 'GET', redirect: 'manual', signal: controller.signal, headers: { 'User-Agent': a.ua, Accept: 'text/html', Cookie: a.cookie, Referer: a.base.href } });
      if ([301, 302, 303, 307, 308].includes(r.status)) {
        await r.body?.cancel();
        const loc = r.headers.get('location');
        if (!loc) fail('站点重定向缺少目标地址');
        let next;
        try { next = new URL(loc, current); } catch { fail('重定向地址无效'); }
        if (/mod=logging|action=login/i.test(next.search)) fail('登录已失效，请重新获取 Cookie');
        if (next.origin !== a.base.origin || next.username || next.password) fail('拒绝跨源重定向，未向新站点发送凭据');
        safeUrl(next.href, a);
        current = next;
        continue;
      }
      if (!r.ok) { await r.body?.cancel(); fail([401, 403].includes(r.status) ? `站点拒绝访问（HTTP ${r.status}），请检查登录和人机验证` : `HTTP ${r.status}，未确认业务成功`); }
      const chunks = []; let size = 0;
      for await (const chunk of r.body) {
        size += chunk.length;
        if (size > 2 * 1024 * 1024) { controller.abort(); fail('响应超过安全大小限制'); }
        chunks.push(chunk);
      }
      const data = Buffer.concat(chunks);
      let charset = (r.headers.get('content-type') || '').match(/charset\s*=\s*["']?([\w-]+)/i)?.[1];
      if (!charset) charset = data.toString('ascii').match(/charset\s*=\s*["']?([\w-]+)/i)?.[1] || 'utf-8';
      let html;
      try { html = new TextDecoder(charset).decode(data); } catch { fail('响应字符编码不受支持'); }
      if (!html.trim()) fail('站点返回空页面，未确认业务成功');
      return html;
    }
    fail('重定向次数超过限制');
  } catch (e) {
    if (controller.signal.aborted) fail('请求超时或响应超限，结果未知，请稍后复核');
    if (e instanceof TypeError) fail('网络请求失败，结果未知，请检查网络后复核');
    throw e;
  } finally { clearTimeout(timer); }
}
function selectedNotification() {
  const mode = (env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(mode)) return false;
  if (['1', 'true', 'yes', 'on'].includes(mode)) return true;
  const list = (env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const names = [CATALOG, 'candidate.js', 'misign.js', 'src/sites/misign.js', 'scripts/misign.js', path.basename(__filename), path.relative(process.cwd(), __filename).split(path.sep).join('/')];
  return list.some(pattern => {
    const regex = new RegExp('^' + pattern.split('*').map(x => x.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(n => regex.test(n));
  });
}
async function notify(body) {
  if (!selectedNotification()) return 'disabled';
  if (dry) { log('通知：断网预演，仅展示脱敏通知摘要：' + body); return 'dry-run-preview'; }
  const paths = [env.QINGLONG_NOTIFY_DIR && path.join(env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = paths.map(p => path.resolve(p)).find(p => fs.existsSync(p));
  if (!file) { log('⚠️ 未找到青龙通知模块，保留业务退出码'); return 'unavailable'; }
  // 隔离通知模块的输出与执行时限，不让其输出凭据或改变业务进程退出码。
  return new Promise(resolve => {
    let child;
    const safeEnv = Object.fromEntries(Object.entries(env).filter(([k]) => !/^MISIGN_/.test(k)));
    try { child = fork(__filename, ['--notify-child', file], { env: safeEnv, stdio: ['ignore', 'ignore', 'ignore', 'ipc'] }); }
    catch { log('⚠️ 通知启动失败'); resolve('failed'); return; }
    const timer = setTimeout(() => { child.kill('SIGKILL'); }, 20000);
    child.once('error', () => { clearTimeout(timer); resolve('failed'); });
    child.once('exit', code => { clearTimeout(timer); if (code !== 0) log('⚠️ 通知失败，保留业务退出码'); resolve(code === 0 ? 'sent' : 'failed'); });
    child.send({ title: TITLE, body: redact(body) });
  });
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}`);
  const lines = (env.MISIGN_ACCOUNTS || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  summary.accounts = lines.length;
  log(`账号总数：${lines.length}`);
  let configError = '';
  const timeout = env.MISIGN_TIMEOUT_MS === undefined ? 15000 : Number(env.MISIGN_TIMEOUT_MS);
  if (!Number.isInteger(timeout) || timeout < 1000 || timeout > 60000) configError = 'MISIGN_TIMEOUT_MS 必须为 1000～60000 的整数';
  if (!lines.length) configError = '未配置 MISIGN_ACCOUNTS：每个非空行填写一个账号';
  if (configError) log('❌ 配置错误：' + configError);
  for (let i = 0; i < lines.length; i++) {
    const label = `账号 ${i + 1}`; const begin = Date.now();
    const stats = { total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    async function stage(number, name, action) {
      const t = Date.now(); log(`${label} 阶段 ${number}/3 ${name} 开始`);
      try { const v = await action(); log(`${label} 阶段 ${number}/3 ${name} 完成，耗时 ${Date.now() - t}ms`); return v; }
      catch (e) { log(`${label} 阶段 ${number}/3 ${name} 失败，耗时 ${Date.now() - t}ms`); throw e; }
    }
    try {
      if (configError) fail(configError);
      const a = parseAccount(lines[i]);
      if (dry) {
        await stage(1, '参数检查', async () => { safeUrl(a.sign.href, a); log(`${label} 参数有效，凭据未输出`); });
        for (const [n, title] of [[2, '签到请求'], [3, '结果复核']]) await stage(n, title, async () => log(`${label} ⏭️ 断网预演跳过，不声明业务成功`));
        stats.skipped = 3; summary.skipped++;
      } else {
        const html = await stage(1, '读取签到页', () => getPage(a.sign, a, timeout)); stats.success++;
        const already = pageState(html); showIdentity(html, label);
        if (already) {
          log(`${label} ☑️ 今日已签到，无需重复`); stats.alreadyComplete = 1; stats.skipped = 1;
          log(`${label} 阶段 2/3 签到请求跳过；阶段 3/3 已由当前排名核验，耗时 0ms`);
          summary.alreadyComplete++;
        } else {
          const link = findLink(html, a);
          const response = await stage(2, '执行签到', () => getPage(link, a, timeout)); pageState(response); stats.success++;
          const check = await stage(3, '确认签到排名', async () => { const p = await getPage(a.sign, a, timeout); if (!pageState(p)) fail('确认页未显示您的签到排名，不能确认签到成功'); return p; }); stats.success++;
          const reward = [...check.matchAll(/<input\b[^>]*>/gi)].map(m => attrs(m[0])).find(x => x.id === 'lxreward')?.value;
          log(`${label} ✅ 签到成功${reward ? '，奖励：' + redact(text(reward)) : ''}`);
        }
        summary.success++;
      }
      summary.results.push({ account: i + 1, status: dry ? 'dry-run' : 'success' });
    } catch (e) {
      stats.failed = 1; stats.skipped = Math.max(0, stats.total - stats.success - stats.failed);
      summary.failed++; summary.results.push({ account: i + 1, status: 'failure' });
      log(`${label} ❌ ${e.message}`);
    }
    for (const k of Object.keys(stats)) summary.tasks[k] += stats[k];
    log(`${label} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now() - begin}ms`);
  }
  const code = configError || summary.failed ? 1 : 0;
  summary.status = configError ? 'configuration-error' : summary.failed ? (summary.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `模式：${dry ? '断网预演' : '正式执行'}；账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}，已完成 ${summary.alreadyComplete}，预演跳过 ${summary.skipped}；状态 ${summary.status}`;
  try { summary.notification = await notify(body); } catch { summary.notification = 'failed'; log('⚠️ 通知失败，保留业务退出码'); }
  summary.elapsedMs = Date.now() - started; summary.finishedAt = new Date().toISOString();
  log('----------------------------------------'); log(body);
  log(`子任务统计：总数 ${summary.tasks.total}，成功 ${summary.tasks.success}，已完成 ${summary.tasks.alreadyComplete}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}`);
  log(`完成时间：${summary.finishedAt}；总耗时 ${summary.elapsedMs}ms；通知 ${summary.notification}；最终状态 ${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = code;
}
if (process.argv[2] === '--notify-child') {
  process.once('message', async m => {
    try { const helper = require(process.argv[3]); await helper.sendNotify(m.title, m.body); process.exit(0); }
    catch { process.exit(1); }
  });
} else {
  main().catch(() => { log('❌ 执行器异常，未确认业务成功'); summary.status = 'failure'; console.log('TASK_SUMMARY=' + JSON.stringify(summary)); process.exitCode = 1; });
}
