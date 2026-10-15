// name: 江淮卡友
// cron: 7 0 * * *
/**
 * name: 江淮卡友
 * cron: 55 5 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/client/sudojia_jhcard.js
 * JHCARD_BODY：抓取 APP 登录请求 http://jacwxmp.starnetah.com:18280/v2driver/v2/login
 * 的原始 JSON 请求体，保留 phone/password/sendMessageKey/deviceType/appType/sign 等全部字段。
 * 每个非空行一个账号，可追加 #true 显式开启五次公开评论；#false 或不追加均关闭。
 * 不再自动修改个人资料。服务原接口使用明文 HTTP；凭据仅发送到原服务，不输出响应原文。
 * JHCARD_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方业务依赖。
 */
'use strict';
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const TITLE = '江淮卡友';
const dry = process.env.JHCARD_DRY_RUN === '1';
const started = Date.now();
const lines = (process.env.JHCARD_BODY || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const stats = {accounts: lines.length, success: 0, failed: 0, tasks: {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0}};
const stamp = () => new Date().toTimeString().slice(0, 8);
const log = s => console.log(`[${stamp()}] ${s}`);
const sleep = ms => new Promise(r => setTimeout(r, ms));
function request(url, body, headers = {}, timeout = 15000, limit = 1048576) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (err, data) => { if (settled) return; settled = true; clearTimeout(timer); err ? reject(err) : resolve(data); };
    const req = (url.startsWith('https:') ? https : http).request(url, {method: body === undefined ? 'GET' : 'POST', headers: {'Accept': 'application/json', ...headers}}, res => {
      const chunks = []; let bytes = 0;
      res.on('data', chunk => { bytes += chunk.length; if (bytes > limit) { finish(new Error('响应超出大小限制')); res.destroy(); req.destroy(); } else chunks.push(chunk); });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error('HTTP 请求失败'));
        try { finish(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); } catch { finish(new Error('响应不是有效 JSON')); }
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超时')); req.destroy(); }, timeout);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(body === undefined ? undefined : JSON.stringify(body));
  });
}
function parse(line) {
  // 从 JSON 对象的结束处识别可选后缀，JSON 字符串中的 # 保持原样。
  const end = line.lastIndexOf('}');
  if (end < 0) throw new Error('账号必须是完整的登录 JSON');
  const suffix = line.slice(end + 1).trim();
  if (!['', '#true', '#false'].includes(suffix)) throw new Error('评论后缀只能为 #true 或 #false');
  let body;
  try { body = JSON.parse(line.slice(0, end + 1)); } catch { throw new Error('登录 JSON 格式错误'); }
  for (const key of ['phone', 'password', 'sendMessageKey', 'deviceType', 'appType', 'sign']) {
    if (!body || typeof body !== 'object' || body[key] === undefined || body[key] === null || String(body[key]).trim() === '') throw new Error(`登录 JSON 缺少字段 ${key}`);
  }
  return {body, comment: suffix === '#true'};
}
function numeric(value) {
  if (!['number', 'string'].includes(typeof value) || !/^\d+(\.\d+)?$/.test(String(value))) throw new Error('响应缺少有效统计字段');
  return value;
}
async function textForComment() {
  const fallback = '一路平安，愿每次出行都顺利。';
  try {
    const d = await request('https://v1.hitokoto.cn/?encode=json', undefined, {}, 8000, 16384);
    const clean = v => typeof v === 'string' ? v.replace(/\s+/g, ' ').trim() : '';
    const t = clean(d.hitokoto), a = clean(d.from_who), s = clean(d.from);
    if (!t) throw new Error();
    const result = t + (a && s ? ` —— ${a}《${s}》` : a ? ` —— ${a}` : s ? ` ——《${s}》` : '');
    if (Array.from(result).length > 280) throw new Error();
    return result;
  } catch { log('⚠️ 文案提供方不可用，采用本地文案'); return fallback; }
}
async function account(line, index) {
  const begin = Date.now(); let stage = 0;
  const counts = {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
  async function step(name, fn) {
    const t = Date.now(); counts.total++; log(`账号 ${index} · 阶段 ${++stage} ${name}`);
    try { const result = await fn(); counts[result === 'skipped' ? 'skipped' : 'success']++; log(`${result === 'skipped' ? '⏭️' : '✅'} ${name}（${Date.now() - t}ms）`); return result; }
    catch (e) { counts.failed++; log(`❌ ${name}：${e.message}（${Date.now() - t}ms）`); throw e; }
  }
  try {
    const config = await step('参数校验', async () => parse(line));
    if (dry) {
      await step('断网预演', async () => { log(`计划：登录、账号信息、签到、连续天数、积分；评论${config.comment ? '开启，共五次' : '关闭'}；不修改个人资料`); return 'skipped'; });
    } else {
      const headers = {'Content-Type': 'application/json', appType: '0', 'User-Agent': 'Mozilla/5.0'};
      async function api(route, body, forum = false) {
        const d = await request(`http://jacwxmp.starnetah.com:${forum ? '18180' : '18280'}${route}`, body, headers);
        if (!d || d.resultCode !== 200) throw new Error('业务接口未返回成功状态');
        return d.data;
      }
      const session = await step('登录', async () => {
        const d = await api('/v2driver/v2/login', config.body);
        if (!d || typeof d.token !== 'string' || !d.token || !['string', 'number'].includes(typeof d.userId) || !String(d.userId)) throw new Error('登录响应缺少会话字段');
        return d;
      });
      headers.token = session.token;
      const uid = session.userId;
      const actions = [
        ['账号信息', async () => { const d = await api('/v2driver/getUserInfo', {uc_id: uid}); if (!d || typeof d !== 'object') throw new Error('账号信息缺失'); if (typeof d.name === 'string') log(`账号姓名：${d.name}`); }],
        ['签到', async () => { const d = await api('/v2driver/signIn', {ucId: uid}); log(`签到成功！积分+${numeric(d?.score)}`); }],
        ['连续签到天数', async () => { const now = new Date(); const d = await api('/v2driver/querySignNumber', {year: now.getFullYear(), month: now.getMonth() + 1, ucId: uid}); log(`已连续签到${numeric(d?.continueTime)}天`); }],
        ['积分查询', async () => { const d = await api('/v2driver/queryIntegral', {uc_id: uid}); log(`当前积分：${numeric(d?.integralCounts)}`); }]
      ];
      for (const [name, action] of actions) { await sleep(1100); try { await step(name, action); } catch {} }
      if (!config.comment) await step('公开评论未开启', async () => 'skipped');
      else for (let n = 1; n <= 5; n++) {
        try { await step(`公开评论 ${n}/5`, async () => {
          const d = await api('/jac/bbs/api/invitationInfo/getInvitationList', {bbsType: 'image', forumId: '30', page: 1, size: 30}, true);
          const posts = d?.records;
          if (!Array.isArray(posts) || !posts.length) throw new Error('帖子列表为空或结构变化');
          const id = posts[Math.floor(Math.random() * posts.length)]?.invitationCommentInfo?.invitationId;
          if (!['string', 'number'].includes(typeof id) || !String(id)) throw new Error('帖子标识缺失');
          await sleep(6000);
          const content = await textForComment();
          await api('/jac/bbs/api/invitationComment/newInvitationComment', {commentContent: content, invitationId: id}, true);
          log('评论成功'); await sleep(1500);
        }); } catch {}
      }
    }
  } catch {} finally {
    for (const key of Object.keys(counts)) stats.tasks[key] += counts[key];
    counts.failed ? stats.failed++ : stats.success++;
    log(`账号 ${index} 统计：总任务 ${counts.total}，成功 ${counts.success}，已完成 ${counts.alreadyComplete}，跳过 ${counts.skipped}，失败 ${counts.failed}，耗时 ${Date.now() - begin}ms`);
  }
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  // dry-run 不加载外部通知模块，避免通知通道联网。
  if (dry) { log(`断网通知预演：${body}`); return '断网预演，未投递'; }
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  for (const file of files) {
    if (!fs.existsSync(file)) continue;
    let timer;
    try {
      const mod = require(file);
      await Promise.race([Promise.resolve().then(() => mod.sendNotify(TITLE, body)), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error()), 15000); })]);
      return '已发送';
    } catch { return '通知失败，保留业务退出码'; } finally { clearTimeout(timer); }
  }
  return '通知模块不可用，保留业务退出码';
}
(async () => {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式运行'}；账号数：${lines.length}`);
  if (!lines.length) log('❌ 配置错误：请设置 JHCARD_BODY，每个非空行一个账号');
  for (let i = 0; i < lines.length; i++) await account(lines[i], i + 1);
  const code = !lines.length || stats.failed ? 1 : 0;
  const status = !lines.length ? 'configuration-error' : stats.failed ? (stats.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `账号总数 ${stats.accounts}，成功 ${stats.success}，失败 ${stats.failed}；状态 ${status}；子任务成功 ${stats.tasks.success}，失败 ${stats.tasks.failed}`;
  const notification = await notify(body);
  log('--------------------------------'); log(body);
  log(`子任务总数 ${stats.tasks.total}，已完成 ${stats.tasks.alreadyComplete}，跳过 ${stats.tasks.skipped}；通知：${notification}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now() - started}ms；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({...stats, status, dryRun: dry, notification, elapsedMs: Date.now() - started}));
  process.exit(code);
})();
