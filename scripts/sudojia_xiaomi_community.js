// name: 小米社区-小程序
// cron: 48 9 * * *
/**
 * name: 小米社区-小程序
 * cron: 48 9 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 基于 sudojia/AutoTaskScript，作者 Telegram@sudojia
 * https://blog.imzjw.cn ，原版日期 2025/04/27
 * 完整 Cookie：在微信小程序「小米社区」登录后，使用自己设备的抓包工具，
 * 从 api.vip.miui.com 请求头复制 Cookie（须含 serviceToken、miui_vip_ph）。
 * XIAOMI_COMM_COOKIE 每个非空行一个账号，不按 & 或 @ 分割。
 * XIAOMI_COMM_DRY_RUN=1 完全离线预演；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方业务依赖。仅执行每日签到，不更新或下载程序。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const title = '小米社区-小程序';
const started = Date.now();
const dry = process.env.XIAOMI_COMM_DRY_RUN === '1';
const accounts = (process.env.XIAOMI_COMM_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const results = [];
const time = () => new Date().toLocaleTimeString('zh-CN', {hour12: false});
const log = s => console.log(`[${time()}] ${s}`);
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
function credentials(cookie) {
  if (/[\x00-\x1f\x7f]/.test(cookie)) throw new Error('Cookie 含非法控制字符');
  const fields = new Map();
  for (const field of cookie.split(';')) {
    const at = field.indexOf('=');
    if (at > 0) fields.set(field.slice(0, at).trim(), field.slice(at + 1).trim());
  }
  if (!fields.get('serviceToken') || !fields.get('miui_vip_ph')) throw new Error('Cookie 缺少 serviceToken 或 miui_vip_ph，请重新获取完整请求头');
  return fields.get('miui_vip_ph');
}
// 仅输出有限数字业务码和固定分类，绝不输出服务端 message 或原始响应。
function businessFailure(data) {
  const status = data && typeof data === 'object' ? data.status : undefined;
  const code = typeof status === 'number' && Number.isSafeInteger(status) && Math.abs(status) <= 999999
    ? String(status) : typeof status === 'string' && /^-?\d{1,6}$/.test(status) ? status : '不可识别';
  const message = typeof data?.message === 'string' ? data.message.slice(0, 4096) : '';
  let category = '未知业务错误';
  if (/未登录|登录失效|登录过期|重新登录|token.*(?:invalid|expired)|unauthorized/i.test(message)) category = '登录凭据可能失效';
  else if (/参数|parameter|argument/i.test(message)) category = '请求参数可能无效';
  else if (/已经签到|已签到|重复|already|加分失败/i.test(message)) category = '疑似重复操作，未经确认不计为成功';
  else if (/频繁|限流|too many|rate limit/i.test(message)) category = '请求频率受限';
  else if (/维护|系统繁忙|稍后再试/i.test(message)) category = '服务暂时不可用';
  const shape = data === null ? '空值' : Array.isArray(data) ? '数组' : typeof data;
  const statusType = status === undefined ? '缺失' : typeof status;
  return new Error(`业务状态未确认成功：status=${code}；分类=${category}；响应类型=${shape}；状态类型=${statusType}（不推断为已签到）`);
}
function request(route, cookie, body) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (err, value) => { if (settled) return; settled = true; clearTimeout(timer); err ? reject(err) : resolve(value); };
    const req = https.request(new URL(route, 'https://api.vip.miui.com'), {
      method: body === undefined ? 'GET' : 'POST',
      headers: {
        'User-Agent': 'Mozilla/5.0 MicroMessenger/8.0',
        Accept: 'application/json, text/plain, */*', xweb_xhr: '1',
        Origin: 'https://servicewechat.com',
        'Content-Type': 'application/x-www-form-urlencoded',
        Referer: 'https://servicewechat.com/wx240a4a764023c444/3/page-frame.html',
        'Accept-Language': 'zh-CN,zh;q=0.9', Cookie: cookie,
        ...(body === undefined ? {} : {'Content-Length': Buffer.byteLength(body)})
      }
    }, res => {
      if (res.statusCode !== 200) { res.resume(); finish(new Error(`HTTP 状态异常：${res.statusCode}`)); return; }
      const chunks = []; let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 262144) { finish(new Error('响应超过大小限制')); res.destroy(); return; }
        chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应被提前中断')));
      res.on('end', () => {
        if (settled) return;
        let data;
        try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch { finish(new Error('响应不是有效 JSON')); return; }
        if (!data || data.status !== 200) { finish(businessFailure(data)); return; }
        finish(null, data.entity);
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超时')); req.destroy(); }, 15000);
    req.on('error', err => {
      const known = new Set(['ENOTFOUND', 'EAI_AGAIN', 'ECONNRESET', 'ECONNREFUSED', 'ETIMEDOUT', 'CERT_HAS_EXPIRED', 'UNABLE_TO_VERIFY_LEAF_SIGNATURE']);
      finish(new Error(`网络请求失败：${known.has(err.code) ? err.code : '未分类传输错误'}`));
    });
    req.end(body);
  });
}
// 仅展示明确的公开身份字段；过滤凭据、手机号和控制字符。
function identity(entity, cookie) {
  if (!entity || typeof entity !== 'object' || Array.isArray(entity)) throw new Error('用户信息结构异常');
  const secretValues = cookie.split(';').map(x => x.slice(x.indexOf('=') + 1).trim()).filter(Boolean);
  const values = ['username', 'nickname', 'displayName', 'userId'].flatMap(key => {
    const v = entity[key];
    if (typeof v !== 'string' && typeof v !== 'number') return [];
    const text = String(v);
    if (!text || /[\x00-\x1f\x7f]|serviceToken|miui_vip_ph|cookie|session|token/i.test(text) || (key !== 'userId' && /(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text)) || secretValues.some(s => text.includes(s))) return [];
    return [`${key}=${text}`];
  });
  return values.length ? values.join('，') : '未返回可展示的公开身份';
}
async function runAccount(cookie, index) {
  const begin = Date.now();
  const r = {account: index, total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
  let ph;
  try { ph = credentials(cookie); }
  catch (e) { log(`账号 ${index} 配置错误：${e.message}`); r.failed = 1; r.skipped = 3; r.total = 4; r.configurationError = true; }
  if (ph) {
    let authenticated = false;
    const stages = [
      ['查询用户身份', async () => { const entity = await request('/mtop/planet/lite/userinfo', cookie); const label = identity(entity, cookie); authenticated = true; return label; }],
      ['每日签到', async () => {
        const entity = await request(`/mtop/planet/vip/member/addCommunityGrowUpPointByActionV2?miui_vip_ph=${encodeURIComponent(ph)}`, cookie, 'action=WECHAT_CHECKIN_TASK');
        const score = entity?.score;
        if ((typeof score !== 'number' && typeof score !== 'string') || !/^\d+(?:\.\d+)?$/.test(String(score)) || !Number.isFinite(Number(score))) throw new Error('签到响应缺少有效积分，结果待核实，不自动重试');
        return `签到成功，积分+${score}`;
      }],
      ['查询成长值', async () => {
        const entity = await request('/mtop/planet/wechat/growup/points/detail', cookie);
        if (!Array.isArray(entity) || entity.some(item => !item || typeof item.jumpText !== 'string')) throw new Error('成长值响应结构异常');
        const total = entity.reduce((sum, item) => sum + (Number.parseInt(item.jumpText.replace(/\D/g, ''), 10) || 0), 0);
        if (!Number.isSafeInteger(total)) throw new Error('成长值数值异常');
        return `当前成长值: ${total}`;
      }]
    ];
    for (let i = 0; i < stages.length; i++) {
      const stepStart = Date.now();
      log(`账号 ${index} 阶段 ${i + 1}/3：${stages[i][0]}`);
      if (dry) { r.skipped++; log(`⏭️ 离线预演：请求已跳过，耗时 ${Date.now() - stepStart}ms`); continue; }
      if (i === 1 && !authenticated) { r.skipped++; log('⏭️ 未确认登录，跳过签到；耗时 0ms'); continue; }
      try { log(`✅ ${await stages[i][1]()}；耗时 ${Date.now() - stepStart}ms`); r.success++; }
      catch (e) { r.failed++; log(`❌ ${e.message}；耗时 ${Date.now() - stepStart}ms`); }
      if (i < stages.length - 1) await wait(1200);
    }
  }
  r.durationMs = Date.now() - begin;
  r.status = r.failed ? 'failure' : dry ? 'dry-run' : 'success';
  log(`账号 ${index} 统计：总任务 ${r.total}，成功 ${r.success}，已完成 ${r.alreadyComplete}，跳过 ${r.skipped}，失败 ${r.failed}，耗时 ${r.durationMs}ms`);
  results.push(r);
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) { log('离线通知预演：' + body); return '离线模拟发送（未联网）'; }
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = candidates.find(p => fs.existsSync(p));
  if (!file) return '不可用：未找到 sendNotify.js';
  // 在独立进程内发送，超时与通知模块日志不会影响业务退出码或泄漏敏感信息。
  return new Promise(resolve => {
    const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))';
    const child = spawn(process.execPath, ['-e', code, file, title, body], {stdio: 'ignore'});
    const timer = setTimeout(() => { child.kill('SIGKILL'); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve('发送失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '发送失败或超时'); });
  });
}
(async () => {
  console.log(`========== ${title} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '离线预演' : '正式执行'}；账号数：${accounts.length}`);
  let configurationError = !accounts.length;
  if (configurationError) log('❌ 配置错误：请设置 XIAOMI_COMM_COOKIE，每个非空行一个完整 Cookie');
  for (let i = 0; i < accounts.length; i++) {
    await runAccount(accounts[i], i + 1);
    if (!dry && i < accounts.length - 1) await wait(2200);
  }
  configurationError ||= results.some(r => r.configurationError);
  const failed = results.filter(r => r.failed).length;
  const success = results.filter(r => r.status === 'success').length;
  const status = configurationError ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const exitCode = configurationError || failed ? 1 : 0;
  const body = `账号总数 ${accounts.length}，成功 ${success}，失败 ${failed}，预演 ${results.filter(r => r.status === 'dry-run').length}；最终状态 ${status}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '发送失败'; }
  const summary = {task: title, mode: dry ? 'dry-run' : 'live', accounts: accounts.length, success, failed, status, exitCode, notification, results, durationMs: Date.now() - started, finishedAt: new Date().toISOString()};
  console.log('----------------------------------------');
  log(body);
  const counts = results.reduce((a,r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, {total:0, success:0, alreadyComplete:0, skipped:0, failed:0});
  log(`子任务统计：${JSON.stringify(counts)}；总耗时 ${summary.durationMs}ms`);
  log(`完成时间：${summary.finishedAt}；通知状态：${notification}；最终状态：${status}`);
  if (dry && !exitCode) log('DRY_RUN_OK：离线预演通过，无业务或通知网络请求');
  if (!dry && !exitCode) log('TASK_SUCCESS：全部账号业务成功');
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
})().catch(() => { console.error('任务发生未预期内部错误'); process.exitCode = 1; });
