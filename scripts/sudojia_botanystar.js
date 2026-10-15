// name: 植物星球
// cron: 33 0 * * *
/**
 * name: 植物星球
 * cron: 32 13 * * *
 * 源码：sudojia/AutoTaskScript src/wx_mini/sudojia_botanyStar.js
 * 原作者 Telegram@sudojia；https://blog.imzjw.cn；2024/07/09
 * SPDX-License-Identifier: GPL-3.0-only
 * 延续上游 GPL-3.0 许可证发布。
 * BOTANY_ACCOUNT：每行 手机号#密码，只按第一个 # 切分。
 * 在小程序注册登录后，进入 我的 → 账号管理 → 修改密码 设置密码。
 * BOTANY_DRY_RUN=1：完全断网预演，不登录、不签到、不提交任务。
 * Node.js >=18；无需安装依赖。通知可使用青龙 sendNotify.js。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const dry = process.env.BOTANY_DRY_RUN === '1';
const started = Date.now();
const rows = (process.env.BOTANY_ACCOUNT || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const log = text => console.log(`[${new Date().toTimeString().slice(0, 8)}] ${text}`);
const wait = ms => dry ? Promise.resolve() : new Promise(r => setTimeout(r, ms));
const count = () => ({ total: 5, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const results = [];
const numeric = v => (typeof v === 'number' || typeof v === 'string' && v.trim() !== '') && Number.isFinite(Number(v)) && Number(v) >= 0;
function request(endpoint, method, token, fields) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const body = fields ? new URLSearchParams(fields).toString() : '';
    const headers = { 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://servicewechat.com/wxd7296b6421fc974e/1/page-frame.html', 'Content-Type': 'application/x-www-form-urlencoded', Accept: '*/*', 'Accept-Encoding': 'identity' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (method === 'POST') headers['Content-Length'] = Buffer.byteLength(body);
    const req = https.request(`https://api.pftp2012.com/api/Member/${endpoint}`, { method, headers }, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => { size += chunk.length; if (size > 1048576) req.destroy(new Error('响应超过大小限制')); else chunks.push(chunk); });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error(`HTTP 状态异常 ${res.statusCode}`));
        let data; try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return reject(new Error('响应不是有效 JSON')); }
        if (!data || data.Status !== 100) return reject(new Error('业务状态未确认成功（要求 Status=100）'));
        resolve(data.Data);
      });
    });
    const deadline = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(deadline));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    req.end(body);
  });
}
function identity(info, secrets) {
  for (const key of ['NickName', 'Nickname', 'DisplayName', 'UserName', 'PublicUID']) {
    const value = info?.[key];
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const s = String(value);
    if (!s || /[\r\n\x00-\x1f]/.test(s) || /\d{11}/.test(s) || secrets.some(x => x && s.includes(x))) continue;
    log(`账号身份 ${key}：${s}`);
  }
}
async function account(row, index) {
  const stats = count(); const begin = Date.now(); let token = ''; let credentials;
  log(`账号 ${index} 开始`);
  async function stage(n, name, fn) {
    const t = Date.now(); log(`账号 ${index} 阶段 ${n}/5 ${name}`);
    try { await fn(); if (dry) { stats.skipped++; log(`⏭️ ${name}：预演通过，未执行远程操作`); } else { stats.success++; log(`✅ ${name}成功`); } return true; }
    catch (e) { stats.failed++; log(`❌ ${name}：${e.message}`); return false; }
    finally { log(`阶段 ${n} 耗时 ${Date.now() - t}ms`); }
  }
  const logged = await stage(1, '登录', async () => {
    const pos = row.indexOf('#');
    if (pos < 1 || !/^\d{11}$/.test(row.slice(0, pos)) || !row.slice(pos + 1)) throw new Error('账号格式错误，需要手机号#密码，每行一个账号');
    credentials = [row.slice(0, pos), row.slice(pos + 1)];
    if (dry) return;
    const hash = crypto.createHash('md5').update(credentials[1]).digest('hex');
    const data = await request('Login', 'POST', '', { userName: credentials[0], userPwd: hash });
    token = data?.MemberInfo?.Token;
    if (typeof token !== 'string' || !token || /[\r\n]/.test(token)) throw new Error('登录响应缺少有效会话');
    identity(data.MemberInfo, [...credentials, hash, token]);
  });
  if (logged) {
    await wait(1800);
    await stage(2, '每日签到', async () => {
      if (dry) return;
      const d = await request('SignIn', 'POST', token);
      if (!numeric(d?.PollenNum) || !numeric(d?.ContinuouNum)) throw new Error('签到结果字段缺失或格式异常');
      log(`绿星币 +${Number(d.PollenNum)}，连续签到 ${Number(d.ContinuouNum)} 天`);
    });
    await wait(1000);
    for (const [n, type] of [[3, '10'], [4, '60']]) {
      if (n === 4) await wait(11000);
      await stage(n, `浏览任务 ${type}`, async () => {
        if (dry) return;
        const d = await request('CompleteMemberMission', 'POST', token, { type, channel: '40' });
        if (!numeric(d)) throw new Error('浏览奖励字段格式异常');
        log(`浏览奖励绿星币 +${Number(d)}${Number(d) === 0 ? '（接口成功，未增加奖励）' : ''}`);
      });
    }
    await wait(1000);
    await stage(5, '查询绿星币', async () => {
      if (dry) return;
      const d = await request('GetMemberInfo', 'GET', token);
      if (!numeric(d?.MemberInfo?.MemberPollen)) throw new Error('余额字段缺失或格式异常');
      identity(d.MemberInfo, [...credentials, token, crypto.createHash('md5').update(credentials[1]).digest('hex')]);
      log(`当前绿星币：${Number(d.MemberInfo.MemberPollen)}`);
    });
  } else { stats.skipped += 4; log('⏭️ 阶段 2–5 跳过：登录或配置失败'); }
  for (const key of Object.keys(totals)) totals[key] += stats[key];
  results.push({ account: index, ...stats, elapsedMs: Date.now() - begin });
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now() - begin}ms`);
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = candidates.find(p => fs.existsSync(p));
  if (!file) return '不可用：未找到青龙 sendNotify.js';
  // 子进程隔离通知错误和输出，预演时拦截所有网络传输，避免通知泄密或联网。
  const program = `if(process.env.BOTANY_DRY_RUN==='1'){const deny=()=>{throw Error('dry-run network disabled')};for(const m of ['http','https']){const x=require(m);x.request=deny;x.get=deny;}const net=require('net');net.connect=deny;net.createConnection=deny;net.Socket.prototype.connect=deny;require('tls').connect=deny;require('dgram').createSocket=deny;for(const k of Object.keys(require('dns'))){if(typeof require('dns')[k]==='function')require('dns')[k]=deny;}global.fetch=deny;const cp=require('child_process');for(const k of ['spawn','exec','execFile','fork','spawnSync','execSync','execFileSync'])cp[k]=deny;}Promise.resolve().then(()=>require(process.argv[1]).sendNotify('植物星球',process.argv[2])).then(()=>process.exit(0),()=>process.exit(1));`;
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', program, file, body], { env: { ...process.env, BOTANY_ACCOUNT: '' }, stdio: 'ignore' });
    const timer = setTimeout(() => child.kill('SIGKILL'), 20000);
    child.on('error', () => { clearTimeout(timer); resolve('通知启动失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '通知已完成' : dry ? '预演通知已尝试，网络发送已阻止' : '通知失败或超时'); });
  });
}
(async () => {
  log('========== 植物星球 ==========');
  log(`开始时间 ${new Date(started).toISOString()}；模式 ${dry ? '断网预演' : '正式执行'}；账号数 ${rows.length}`);
  if (!rows.length) log('❌ 配置错误：BOTANY_ACCOUNT 不能为空');
  for (let i = 0; i < rows.length; i++) { await account(rows[i], i + 1); if (i + 1 < rows.length) await wait(2200); }
  const failed = results.filter(r => r.failed > 0).length;
  const ok = rows.length - failed;
  const exitCode = !rows.length || failed ? 1 : 0;
  const status = !rows.length ? 'configuration-error' : failed ? (ok ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `模式：${dry ? '断网预演' : '正式执行'}；账号总数 ${rows.length}，${dry ? '预演通过' : '成功'} ${ok}，失败 ${failed}；状态 ${status}；子任务成功 ${totals.success}，跳过 ${totals.skipped}，失败 ${totals.failed}`;
  let notification; try { notification = await notify(body); } catch { notification = '通知失败'; }
  log('----------------------------------------'); log(body);
  log(`子任务总数 ${totals.total}，已完成 ${totals.alreadyComplete}；总耗时 ${Date.now() - started}ms`);
  log(`完成时间 ${new Date().toISOString()}；最终状态 ${status}；通知状态 ${notification}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: '植物星球', mode: dry ? 'dry-run' : 'live', status, accounts: rows.length, success: dry ? 0 : ok, dryRunPassed: dry ? ok : 0, failed, tasks: totals, results, notification, elapsedMs: Date.now() - started, exitCode }));
  process.exitCode = exitCode;
})();
