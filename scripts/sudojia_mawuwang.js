// name: 馬伍旺饮料厂
// cron: 13 0 * * *
/**
 * name: 馬伍旺饮料厂
 * cron: 48 6 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Derived from sudojia/AutoTaskScript, Telegram@sudojia, https://blog.imzjw.cn
 * 原作日期：2024/09/01；维护版保留 GPL-3.0 许可。
 * Node.js >=18，无第三方业务依赖。
 * 微信登录馬伍旺饮料厂小程序，抓取本人请求
 * https://webapi.qmai.cn/web/seller/oauth/flash-sale-login
 * 响应中的 token 和 user.id，设置 MAWUW_TOKEN，每个非空行 token#id。
 * 只按第一个 # 分割，不使用 & 或 @ 分隔账号。请勿分享抓包内容。
 * MAWUW_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 * 签名沿用上游固定 userId=10086；凭据 id 保留，不擅改未经验证的接口。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '馬伍旺饮料厂';
const APP = 'wxc1381dc6f2213b72';
const ACTIVITY = '1103263769176125440';
const dry = process.env.MAWUW_DRY_RUN === '1';
const start = Date.now();
const lines = (process.env.MAWUW_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const secrets = lines.flatMap(x => { const i = x.indexOf('#'); return [x, i < 0 ? x : x.slice(0, i), i < 0 ? '' : x.slice(i + 1)]; }).filter(Boolean);
const results = [];
const details = [];
const log = text => { details.push(text); console.log(`[${new Date().toTimeString().slice(0, 8)}] ${text}`); };
function safe(value) {
  let s = String(value).replace(/[\r\n\u0000-\u001f\u007f]/g, ' ');
  for (const secret of secrets) s = s.split(secret).join('[凭据已隐藏]');
  return s.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function request(endpoint, method, token, body) {
  return new Promise((resolve, reject) => {
    if (dry) return reject(new Error('预演禁止网络请求'));
    const payload = body ? JSON.stringify(body) : undefined;
    let settled = false;
    const finish = (err, data) => { if (settled) return; settled = true; clearTimeout(timer); err ? reject(err) : resolve(data); };
    const req = https.request(new URL(endpoint, 'https://webapi.qmai.cn'), {
      method, headers: {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a1b)XWEB/11097',
        'content-type': 'application/json', 'qm-from': 'wechat',
        referer: `https://servicewechat.com/${APP}/26/page-frame.html`,
        'qm-user-token': token, ...(payload ? { 'content-length': Buffer.byteLength(payload) } : {})
      }
    }, res => {
      const chunks = []; let size = 0;
      res.on('data', chunk => { size += chunk.length; if (size > 1048576) { finish(new Error('响应超过大小限制')); res.destroy(); } else chunks.push(chunk); });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error(`HTTP 状态异常 ${res.statusCode}`));
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || data.status !== true) return finish(new Error('业务未确认成功，检查凭据及活动有效性'));
          finish(null, data.data);
        } catch { finish(new Error('响应不是有效 JSON')); }
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超时')); req.destroy(); }, 15000);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(payload);
  });
}
function signature(timestamp) {
  const source = `activityId=${ACTIVITY}&sellerId=215357&timestamp=${timestamp}&userId=10086&key=${[...ACTIVITY].reverse().join('')}`;
  return crypto.createHash('md5').update(source).digest('hex').toUpperCase();
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
function number(value) { return (typeof value === 'number' || typeof value === 'string' && value.trim() !== '') && Number.isFinite(Number(value)) && Number(value) >= 0; }
async function account(line, index) {
  const began = Date.now();
  const r = { account: index, total: 5, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  results.push(r);
  let step = 0;
  async function stage(label, fn) {
    const t = Date.now(); log(`账号 ${index} 阶段 ${++step}/5 ${label}`);
    try { const state = await fn(); r[state || 'success']++; log(`账号 ${index} ${label}：${state === 'skipped' ? '⏭️ 预演跳过' : state === 'alreadyComplete' ? '☑️ 已完成' : '✅ 成功'}，耗时 ${Date.now() - t}ms`); return true; }
    catch (e) { r.failed++; log(`账号 ${index} ${label}：❌ ${safe(e.message)}，耗时 ${Date.now() - t}ms`); return false; }
  }
  const pos = line.indexOf('#');
  const token = line.slice(0, pos); const uid = line.slice(pos + 1);
  let valid = await stage('参数检查', async () => {
    if (pos < 1 || !uid.trim() || /[\s\u0000-\u001f\u007f]/.test(token)) throw new Error('MAWUW_TOKEN 应每行填写 token#id');
  });
  if (valid && dry) {
    for (const label of ['登录校验', '用户信息', '签到', '积分及过期提醒']) await stage(label, async () => 'skipped');
  } else if (valid) {
    valid = await stage('登录校验', () => request(`/web/catering/crm/customer-center?appid=${APP}`, 'GET', token).then(() => undefined));
    if (valid) {
      await pause(1000);
      await stage('用户信息', async () => {
        const d = await request(`/web/catering/crm/personal-info?appid=${APP}`, 'GET', token);
        if (!d || typeof d !== 'object') throw new Error('用户信息字段缺失');
        for (const key of ['nickName', 'nickname', 'username', 'displayName']) {
          if (typeof d[key] === 'string' && d[key]) { log(`账号 ${index} 身份：${safe(d[key])}`); break; }
        }
      });
      await pause(1200);
      await stage('签到', async () => {
        const body = { activityId: ACTIVITY, appid: APP };
        const d = await request('/web/cmk-center/sign/userSignStatistics', 'POST', token, body);
        if (!d || ![0, 1].includes(d.signStatus) || !number(d.signDays)) throw new Error('签到状态字段异常，停止写操作');
        log(`账号 ${index} 连续签到 ${Number(d.signDays)} 天`);
        if (d.signStatus === 1) return 'alreadyComplete';
        await pause(3500);
        const timestamp = Date.now();
        await request('/web/cmk-center/sign/takePartInSign', 'POST', token, { ...body, storeId: 215357, timestamp, signature: signature(timestamp) });
        log(`账号 ${index} 签到成功`);
      });
      await pause(1200);
      await stage('积分及过期提醒', async () => {
        const d = await request('/web/catering/crm/points-info', 'POST', token, { appid: APP });
        if (!d || !number(d.totalPoints) || !number(d.soonExpiredPoints)) throw new Error('积分字段缺失或异常');
        log(`账号 ${index} 当前积分：${Number(d.totalPoints)}`);
        if (Number(d.soonExpiredPoints) > 0) {
          if (typeof d.expiredTime !== 'string' && typeof d.expiredTime !== 'number') throw new Error('积分过期时间缺失');
          log(`账号 ${index} ${Number(d.soonExpiredPoints)} 积分将在 ${safe(d.expiredTime)} 失效`);
        } else log(`账号 ${index} 暂无过期积分`);
      });
    }
  }
  while (step < r.total) { log(`账号 ${index} 阶段 ${++step}/5 ⏭️ 前置条件失败，跳过`); r.skipped++; }
  r.durationMs = Date.now() - began;
  log(`账号 ${index} 统计：总任务 ${r.total}，成功 ${r.success}，已完成 ${r.alreadyComplete}，跳过 ${r.skipped}，失败 ${r.failed}，耗时 ${r.durationMs}ms`);
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) { log('通知预演：已生成脱敏摘要，断网模式不加载通知模块'); return '预演跳过发送'; }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(d => path.join(d, 'sendNotify.js')).find(f => fs.existsSync(f));
  if (!file) return '不可用：未找到 sendNotify.js';
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', file, TITLE, body], { stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('失败：通知超时'); }, 20000);
    child.on('error', () => { clearTimeout(timer); resolve('失败：通知无法启动'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '失败：通知发送异常'); });
  });
}
(async () => {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry ? '断网预演' : '正式'}；账号数：${lines.length}`);
  let fatal = false;
  if (!lines.length) { fatal = true; log('❌ 配置错误：MAWUW_TOKEN 未提供非空账号'); }
  for (let i = 0; i < lines.length; i++) {
    try { await account(lines[i], i + 1); } catch { fatal = true; log(`账号 ${i + 1} ❌ 执行异常（详情已隐藏）`); }
  }
  const failed = results.filter(r => r.failed > 0 || r.success + r.alreadyComplete + r.skipped + r.failed !== r.total).length;
  const passed = results.length - failed;
  const exitCode = fatal || failed ? 1 : 0;
  const status = exitCode ? (!lines.length ? 'configuration-error' : passed ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const stats = results.reduce((a, r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  const body = `账号总数：${lines.length}，成功：${passed}，失败：${failed}；状态：${status}；子任务成功：${stats.success}，已完成：${stats.alreadyComplete}，跳过：${stats.skipped}，失败：${stats.failed}`;
  let notification; try { notification = await notify(body + '\n\n' + details.join('\n')); } catch { notification = '失败：通知不可用'; }
  log('----------------------------------------'); log(body);
  log(`通知状态：${notification}；总耗时：${Date.now() - start}ms；完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, mode: dry ? 'dry-run' : 'live', status, accounts: lines.length, success: passed, failed, steps: stats, results, notification, durationMs: Date.now() - start, exitCode }));
  process.exitCode = exitCode;
})();
