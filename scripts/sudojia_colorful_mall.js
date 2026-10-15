// name: 七彩虹商城
// cron: 22 0 * * *
/**
 * name: 七彩虹商城
 * cron: 14 12 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 基于 sudojia/AutoTaskScript，作者 Telegram@sudojia，https://blog.imzjw.cn
 * 上游提交 4a55327baed0321bdf95802a75cc8363cae118b0
 * Node.js >= 18；仅使用标准库。使用说明见 contract.json。
 * COLORFUL_TOKEN：每行一个完整 JSON，含 OpenId、Iv、EncryptedData。
 * 退出小程序登录，开启本地抓包后重新登录，复制 DecryptPhoneNumber 请求体。
 * 请在本地压缩 JSON，勿将凭据粘贴到在线工具。公开评论默认关闭。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const dry = process.env.COLORFUL_DRY_RUN === '1';
const comments = process.env.COLORFUL_COMMENT === '1';
const start = Date.now();
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
const results = [];
let configError = false;
function log(s) { console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`); }
function fail(s) { throw new Error(s); }
function number(v) { if (typeof v !== 'number' || !Number.isFinite(v) || v < 0) fail('响应数值字段无效'); return v; }
const delay = ms => new Promise(r => setTimeout(r, ms));
// 所有 HTTP 在本脚本实现；禁止重定向、限制体积与总耗时，不记录请求或原始响应。
function request(url, method = 'GET', headers = {}, body, timeout = 15000, limit = 1048576) {
  if (dry) return Promise.reject(new Error('预演禁止网络请求'));
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (err, value) => { if (done) return; done = true; clearTimeout(timer); err ? reject(err) : resolve(value); };
    const req = https.request(url, { method, headers }, res => {
      let size = 0; const chunks = [];
      res.on('data', c => { size += c.length; if (size > limit) { finish(new Error('响应超出大小限制')); res.destroy(); req.destroy(); } else chunks.push(c); });
      res.on('error', () => finish(new Error('读取响应失败')));
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
function client() {
  let auth = {};
  return {
    setAuth(data) {
      if (!data || typeof data.Token !== 'string' || !data.Token || typeof data.RefreshToken !== 'string' || !data.RefreshToken) fail('登录响应缺少凭据');
      auth = { Authorization: `Bearer ${data.Token}`, 'X-Authorization': `Bearer ${data.RefreshToken}` };
    },
    async call(endpoint, method = 'GET', body) {
      const appId = '815d8026-9a52-4445-a42c-a5443134232e';
      const secret = '2b5c01fb-7640-401a-8188-43a13190a626';
      const ticks = Date.now(), requestId = crypto.randomUUID();
      const sign = crypto.createHash('md5').update([JSON.stringify({AppId: appId}), JSON.stringify({Ticks: ticks}), JSON.stringify({requestId}), JSON.stringify({AppSecret: secret})].join('')).digest('hex');
      const response = await request(`https://shop.skycolorful.com${endpoint}`, method, {
        'User-Agent': 'Mozilla/5.0', Accept: '*/*', source: 'Wx', 'Content-Type': 'application/json',
        referer: 'https://servicewechat.com/wx49018277e65fc3e1/61/page-frame.html',
        Ticks: String(ticks), requestId, AppId: appId, AppSecret: Buffer.from(secret).toString('base64'), Sign: sign, ...auth
      }, body);
      if (!response || response.Code !== 0) fail('业务接口未确认成功，请检查凭据或服务状态');
      return response.Data;
    }
  };
}
function normalize(s) { return typeof s === 'string' ? s.replace(/\s+/gu, ' ').trim() : ''; }
async function content() {
  try {
    const data = await request('https://v1.hitokoto.cn/?encode=json', 'GET', {}, undefined, 8000, 16384);
    const text = normalize(data.hitokoto), author = normalize(data.from_who), source = normalize(data.from);
    if (!text) fail('缺少文本');
    const value = text + (author && source ? ` —— ${author}《${source}》` : source ? ` ——《${source}》` : author ? ` —— ${author}` : '');
    if (Array.from(value).length > 280) fail('文本过长');
    log('评论文本：已获取一言及署名（不输出正文）');
    return value;
  } catch {
    log('⚠️ 随机文本不可用，采用本地备用文本');
    const local = normalize(process.env.COLORFUL_COMMENT_TEXT);
    return local && Array.from(local).length <= 280 ? local : '感谢分享，祝大家生活愉快。';
  }
}
async function account(line, index) {
  const began = Date.now();
  const stat = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
  let sequence = 0;
  async function stage(name, fn) {
    const time = Date.now(); stat.total++;
    log(`账号 ${index} · 阶段 ${++sequence} ${name} 开始`);
    try {
      const status = await fn() || 'success'; stat[status]++;
      log(`账号 ${index} · 阶段 ${sequence} ${name} ${status === 'skipped' ? '⏭️ 跳过' : status === 'alreadyComplete' ? '☑️ 已完成' : '✅ 成功'} · ${Date.now()-time}ms`);
    } catch (e) { stat.failure++; log(`账号 ${index} · 阶段 ${sequence} ${name} ❌ ${e.message} · ${Date.now()-time}ms`); throw e; }
  }
  try {
    let credentials;
    await stage('参数校验', async () => {
      try { credentials = JSON.parse(line); } catch { fail('账号必须是单行 JSON'); }
      if (!credentials || Array.isArray(credentials) || ['OpenId','Iv','EncryptedData'].some(k => typeof credentials[k] !== 'string' || !credentials[k].trim())) fail('账号缺少 OpenId、Iv 或 EncryptedData');
    });
    if (dry) {
      for (const name of ['换取登录凭据','校验登录','读取用户信息','旧版签到状态及签到','新版签到','连续签到天数','评论积分任务','积分查询']) {
        await stage(name, async () => { log('断网预演：仅验证执行计划，不确认业务成功'); return 'skipped'; });
      }
    } else {
      const api = client(); let mobile;
      await stage('换取登录凭据', async () => api.setAuth(await api.call('/api/User/DecryptPhoneNumber', 'POST', credentials)));
      await stage('校验登录', async () => { await api.call('/api/User/RefreshLoginTime', 'POST', {phone: ''}); });
      await stage('读取用户信息', async () => {
        const d = await api.call('/api/User/GetUserInfo'); if (!d || typeof d !== 'object') fail('用户信息结构无效');
        if (typeof d.NickName === 'string' && d.NickName) log(`账号 ${index} 昵称：${d.NickName}`);
        mobile = d.Mobile;
      });
      // 各业务动作独立记录失败；凭据失败则不继续该账号。
      async function action(name, fn) { try { await stage(name, fn); } catch {} }
      await action('旧版签到状态及签到', async () => {
        const d = await api.call('/api/User/IsSign');
        if (!d || typeof d.IsSign !== 'boolean') fail('签到状态字段无效');
        if (d.IsSign) return 'alreadyComplete';
        await api.call('/api/User/Sign', 'POST'); log('旧版签到成功');
      });
      await action('新版签到', async () => { await api.call('/api/User/SignV2', 'POST'); log('新版签到成功'); });
      await action('连续签到天数', async () => { log(`已连续签到 ${number(await api.call('/api/User/SignDays'))} 天`); });
      await action('评论积分任务', async () => {
        if (!comments) { log('公开评论未开启；COLORFUL_COMMENT=1 可授权发布'); return 'skipped'; }
        if (typeof mobile !== 'string' || !mobile) fail('评论所需账号字段缺失');
        let count = 0;
        for (let i = 0; i < 3; i++) {
          const config = await api.call('/api/Sys/GetPointConfig');
          if (!config || !Array.isArray(config.DataList)) fail('积分任务结构无效');
          const task = config.DataList.find(t => t.Name === '社区内容评论');
          if (!task) fail('未找到评论积分任务');
          if (number(task.DayGetPointTotal) >= 9) { log('今日评论积分已达上限'); return count ? 'success' : 'alreadyComplete'; }
          const list = await api.call(`/api/Bbs/GetHotList?page=1&size=30&phone=${encodeURIComponent(mobile)}`);
          if (!Array.isArray(list) || !list.length) fail('没有可评论文章');
          const article = list[Math.floor(Math.random()*list.length)];
          if (!article || !['string','number'].includes(typeof article.Id) || !article.Id) fail('文章标识无效');
          await api.call('/api/Bbs/PostReply', 'POST', {PostId: article.Id, ReplyId:'', ParentReplyId:'', Phone: mobile, Content: await content(), Pictures: []});
          count++; log(`第 ${count} 次评论：业务确认成功`); await delay(6000);
        }
      });
      await action('积分查询', async () => { const d = await api.call('/api/User/GetUserPoint'); log(`当前积分：${number(d && d.Num)}`); });
    }
  } catch { /* 错误已由阶段脱敏记录；继续下一个账号。 */ }
  Object.keys(totals).forEach(k => { totals[k] += stat[k]; });
  results.push({index, status: stat.failure ? 'failure' : dry ? 'dry-run' : 'success', ...stat, durationMs: Date.now()-began});
  log(`账号 ${index} 统计：总任务 ${stat.total}，成功 ${stat.success}，已完成 ${stat.alreadyComplete}，跳过 ${stat.skipped}，失败 ${stat.failure}，耗时 ${Date.now()-began}ms`);
}
async function notify(summary) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return 'disabled';
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = files.find(f => fs.existsSync(f));
  if (!file) { log('⚠️ 未找到青龙 sendNotify.js，保留业务退出码'); return 'unavailable'; }
  // 隔离通知输出和异常；预演仍调用通知模块，但禁止网络与子进程。
  const code = `if(process.env.COLORFUL_DRY_RUN==='1'){const deny=()=>{throw Error('dry-run')};require('net').Socket.prototype.connect=deny;require('tls').connect=deny;require('dgram').createSocket=deny;global.fetch=deny;for(const k of ['spawn','exec','execFile','fork','spawnSync','execSync','execFileSync'])require('child_process')[k]=deny;} Promise.resolve().then(()=>require(process.argv[1]).sendNotify('七彩虹商城',process.argv[2])).then(()=>process.exit(0),()=>process.exit(1));`;
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e',code,file,summary], {stdio:'ignore', env: {...process.env, COLORFUL_TOKEN:''}});
    const timer = setTimeout(() => { child.kill('SIGKILL'); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve('failed'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? 'sent' : dry ? 'dry-run-network-blocked' : 'failed'); });
  });
}
async function main() {
  const lines = (process.env.COLORFUL_TOKEN || '').split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  log('========== 七彩虹商城 =========='); log(`开始时间：${new Date(start).toISOString()} · 模式：${dry?'断网预演':'正式执行'} · 账号数：${lines.length}`);
  if (!lines.length) { configError = true; log('❌ 配置错误：缺少 COLORFUL_TOKEN'); }
  for (let i=0;i<lines.length;i++) await account(lines[i],i+1);
  const failed = results.filter(r=>r.status==='failure').length;
  const success = results.length - failed;
  const status = configError ? 'configuration-error' : failed ? (success ? 'partial-failure':'failure') : dry ? 'dry-run':'success';
  const body = `状态：${status}；账号总数：${lines.length}；成功数：${dry?0:success}；失败数：${failed}；预演通过：${dry?success:0}；子任务成功：${totals.success}；已完成：${totals.alreadyComplete}；跳过：${totals.skipped}；失败：${totals.failure}`;
  const notification = await notify(body);
  const summary = {task:'七彩虹商城',mode:dry?'dry-run':'live',status,accounts:lines.length,success:dry?0:success,failed,dryRunPassed:dry?success:0,configurationError:configError,steps:totals,notification,durationMs:Date.now()-start,finishedAt:new Date().toISOString()};
  log('--------------------------------'); log(body); log(`通知状态：${notification} · 总耗时：${summary.durationMs}ms · 完成时间：${summary.finishedAt} · 最终状态：${status}`);
  if (dry && !configError && !failed) log('DRY_RUN_OK');
  if (!dry && status==='success') log('COLORFUL_SUCCESS');
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
  process.exitCode = configError || failed ? 1 : 0;
}
main();
