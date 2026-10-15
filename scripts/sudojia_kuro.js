// name: 库街区每日签到
// cron: 4 2 * * *
/**
 * name: 库街区每日签到
 * cron: 22 8 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/client/sudojia_kuro.js
 * KURO_TOKEN：每个非空行一个账号。登录 https://www.kurobbs.com/ 后，
 * F12 → Application → Local storage → auth_token；或获取本人 APP
 * api.kurobbs.com 请求头 token。不要填写 Cookie，不使用 & 分隔账号。
 * KURO_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方业务依赖。签到需已绑定游戏角色并开启库街区展示。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const path = require('node:path');
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const dry = process.env.KURO_DRY_RUN === '1';
const tokens = (process.env.KURO_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const start = Date.now();
const totals = {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
const log = s => console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${s}`);
function safe(value) {
  let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const token of tokens) s = s.split(token).join('[凭据已隐藏]');
  return s.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function dateCN(value = new Date()) {
  const d = new Date(value);
  if (!Number.isFinite(d.getTime())) return '';
  const p = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
  return ['year','month','day'].map(k => p.find(x => x.type === k).value).join('-');
}
function request(ctx, endpoint, fields = {}, device = false) {
  if (dry) throw new Error('预演禁止网络请求');
  const body = new URLSearchParams(fields).toString();
  return new Promise((resolve, reject) => {
    const headers = {source:ctx.source, token:ctx.token, 'Content-Type':'application/x-www-form-urlencoded', 'Content-Length':Buffer.byteLength(body)};
    if (device) headers.devcode = crypto.randomBytes(20).toString('hex').toUpperCase();
    const req = https.request({hostname:'api.kurobbs.com',path:endpoint,method:'POST',headers}, res => {
      let chunks = [], size = 0;
      res.on('data', chunk => { size += chunk.length; if(size > 1048576) req.destroy(new Error('响应超过大小限制')); else chunks.push(chunk); });
      res.on('error', () => reject(new Error('响应传输失败')));
      res.on('end', () => {
        if(res.statusCode !== 200) return reject(new Error(`HTTP 状态异常（${res.statusCode}）`));
        try { const data = JSON.parse(Buffer.concat(chunks).toString()); if(!data || typeof data.code !== 'number') throw 0; resolve(data); }
        catch { reject(new Error('响应格式无效')); }
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('请求失败或超时')));
    req.end(body);
  });
}
function check(r) {
  if(r.code !== 200) throw new Error(`业务未成功（代码 ${r.code}）`);
  return r.data;
}
function role(data, requireUser) {
  if(!data || !['serverId','roleId', ...(requireUser ? ['userId'] : [])].every(k => ['string','number'].includes(typeof data[k]) && String(data[k]).length)) throw new Error('角色资料不完整，请检查绑定和展示设置');
  return data;
}
function identity(data) {
  if(!data || typeof data !== 'object') return;
  for(const key of ['nickname','nickName','username','displayName','userId']) {
    if(['string','number'].includes(typeof data[key])) log(`账号身份 ${key}：${safe(data[key])}`);
  }
}
async function account(token, index) {
  const ctx = {token, source:'h5'};
  const stats = {total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  const began = Date.now();
  let stage = 0;
  async function step(name, fn, skip = false) {
    const t = Date.now(); stats.total++; log(`账号 ${index} 阶段 ${++stage}：${name}`);
    try {
      if(skip || dry) {stats.skipped++; log(`⏭️ ${dry ? '预演：已检查流程，未请求或修改远端' : '前置条件不满足，跳过'}`); return;}
      const result = await fn(); stats.success++; log(`✅ ${name}成功`); return result;
    } catch(e) {stats.failed++; log(`❌ ${name}：${safe(e.message)}`);}
    finally {log(`阶段 ${stage} 耗时 ${Date.now()-t} 毫秒`);}
  }
  const mc = await step('检查 Token 和鸣潮角色', async () => {
    let r = await request(ctx, '/gamer/widget/game3/refresh', {type:2,sizeType:1});
    if(r.code === 220) {ctx.source='android'; log('H5 验证失败，尝试 Android 来源'); r=await request(ctx,'/gamer/widget/game3/refresh',{type:2,sizeType:1});}
    const data=role(check(r),true); identity(data); return data;
  });
  await step('社区签到', async () => {
    const d=check(await request(ctx,'/user/signIn',{gameId:2}));
    if(!d || !Array.isArray(d.gainVoList) || !d.gainVoList.length || !Number.isFinite(Number(d.continueDays))) throw new Error('签到结果缺失');
    for(const gain of d.gainVoList) {if(!Number.isFinite(Number(gain.gainValue))) throw new Error('签到奖励无效'); log(`获得库洛币 ${Number(gain.gainValue)}`);}
    log(`连续签到 ${Number(d.continueDays)} 天`);
  });
  await step('库洛币查询', async () => {
    const d=check(await request(ctx,'/encourage/gold/getTotalGold'));
    if(!d || d.goldNum == null || !Number.isFinite(Number(d.goldNum))) throw new Error('余额结果缺失');
    log(`当前账户库洛币：${Number(d.goldNum)}`);
  });
  async function game(name, gameId, r) {
    const params=r ? {gameId,serverId:r.serverId,roleId:r.roleId,userId:r.userId ?? mc?.userId} : {};
    await step(`${name}每日签到`, async () => {
      const d=check(await request(ctx,'/encourage/signIn/v2',{...params,reqMonth:dateCN().slice(5,7)},true));
      if(d == null) throw new Error('签到返回空结果，请检查展示设置');
    }, !r);
    await step(`${name}今日奖励查询`, async () => {
      const d=check(await request(ctx,'/encourage/signIn/queryRecordV2',params));
      if(!Array.isArray(d)) throw new Error('奖励记录格式无效');
      const today=d.filter(x => x && dateCN(x.sigInDate) === dateCN());
      if(!today.length) throw new Error('未找到今日签到记录，无法确认完成');
      for(const x of today) {if(typeof x.goodsName !== 'string' || x.goodsNum == null || !Number.isFinite(Number(x.goodsNum))) throw new Error('奖励字段无效'); log(`${name}今日签到奖励：${safe(x.goodsName)} × ${Number(x.goodsNum)}`);}
    }, !r);
  }
  await game('鸣潮',3,mc);
  const zs=await step('查询战双角色',async () => {
    const d=check(await request(ctx,'/gamer/widget/game2/refresh',{gameId:2,type:1,sizeType:1},true));
    if(d == null) {log('战双未绑定角色，无需签到');return null;}
    const r=role(d,false); identity(r);
    if(r.userId == null && !mc?.userId) throw new Error('缺少同账号用户标识');
    return r;
  });
  await game('战双',2,zs);
  for(const k in totals) totals[k]+=stats[k];
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now()-began} 毫秒`);
  return stats.failed === 0;
}
async function notify(body) {
  if(['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  const candidates=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=candidates.find(x => fs.existsSync(x));
  if(!file) return '不可用：未找到 sendNotify.js（业务退出码不变）';
  // 演练仍调用通知接口，但阻断通知模块的所有网络和子进程出口。
  const runner=`if(process.env.KURO_DRY_RUN==='1'){for(const n of ['node:net','node:tls','node:http','node:https','node:dgram','node:child_process']){const m=require(n);for(const k of ['connect','createConnection','request','get','createSocket','spawn','exec','execFile','fork','spawnSync','execSync','execFileSync'])if(typeof m[k]==='function')m[k]=()=>{throw Error('dry-run network blocked')};}require('node:net').Socket.prototype.connect=()=>{throw Error('dry-run network blocked')};for(const m of [require('node:dns'),require('node:dns').promises])for(const k of Object.keys(m))if(typeof m[k]==='function')m[k]=()=>{throw Error('dry-run network blocked')};global.fetch=()=>Promise.reject(Error('dry-run network blocked'));} Promise.resolve().then(()=>require(process.argv[1]).sendNotify('库街区每日签到',process.argv[2])).catch(()=>{process.exitCode=1});`;
  return new Promise(resolve => {
    const env={...process.env}; delete env.KURO_TOKEN;
    const child=spawn(process.execPath,['-e',runner,file,body],{env,stdio:'ignore'});
    const timer=setTimeout(()=>child.kill('SIGKILL'),15000);
    child.on('error',()=>{clearTimeout(timer);resolve('通知失败（业务退出码不变）');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':dry?'预演通知受断网保护，未送达':'通知失败（业务退出码不变）');});
  });
}
(async()=>{
  log('========== 库街区每日签到 ==========');
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${tokens.length}`);
  let success=0, failed=0;
  if(!tokens.length) log('❌ 配置错误：请设置 KURO_TOKEN，每个非空行一个账号');
  for(let i=0;i<tokens.length;i++) {if(await account(tokens[i],i+1)) success++; else failed++;}
  const status=!tokens.length?'configuration-error':failed?(success?'partial-failure':'failure'):dry?'dry-run':'success';
  process.exitCode=failed || !tokens.length ? 1 : 0;
  const body=`模式：${dry?'断网预演':'正式执行'}；账号总数 ${tokens.length}，成功 ${success}，失败 ${failed}；状态 ${status}；子任务成功 ${totals.success}，跳过 ${totals.skipped}，失败 ${totals.failed}`;
  const notification=await notify(body);
  log('----------------------------------------'); log(body); log(`通知状态：${notification}`);
  log(`子任务统计：${JSON.stringify(totals)}；总耗时：${Date.now()-start} 毫秒；完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:'库街区每日签到',mode:dry?'dry-run':'live',accounts:tokens.length,success,failed,status,tasks:totals,notification,elapsedMs:Date.now()-start}));
})();
