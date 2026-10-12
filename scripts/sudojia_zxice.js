// name: 甄稀冰淇淋每日签到
// cron: 22 15 * * *
/**
 * name: 甄稀冰淇淋
 * cron: 22 15 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia；https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_zxice.js
 * 独立维护版本，Node.js >= 18，无第三方业务依赖。
 * ZX_ICE_TOKEN：登录甄稀冰淇淋微信小程序，抓取本人发往
 * msmarket.msx.digitalyili.com 的请求头 access-token；每个非空行一个账号。
 * ZX_ICE_DRY_RUN=1：完全断网，仅校验配置、展示执行计划和生成本地通知摘要。
 * QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const BASE = 'https://msmarket.msx.digitalyili.com';
const dry = process.env.ZX_ICE_DRY_RUN === '1';
const tokens = (process.env.ZX_ICE_TOKEN || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const started = Date.now();
const results = [];
let stageNumber = 0;
const stamp = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = s => console.log(`[${stamp()}] ${s}`);
const safeIdentity = value => {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  const s = String(value);
  if (tokens.some(t => s.includes(t)) || /(?:\+?86[- ]?)?1[3-9]\d{9}/.test(s) || /[\r\n\x00-\x1f]/.test(s)) return '';
  return s;
};
function request(token, endpoint, method = 'GET') {
  if (dry) throw new Error('预演模式禁止请求');
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (err, data) => { if(done) return; done = true; clearTimeout(timer); err ? reject(err) : resolve(data); };
    const req = https.request(BASE + endpoint, {method, headers: {
      'access-token':token, 'user-agent':'Mozilla/5.0',
      referer:'https://servicewechat.com/wx21fd8b5d6d4cf1ca/195/page-frame.html',
      'content-type':'application/json', accept:'application/json', 'accept-encoding':'identity'
    }}, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => {size += chunk.length; if(size > 1024*1024) {finish(new Error('响应超过大小限制')); res.destroy();} else chunks.push(chunk);});
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error(`HTTP 请求失败（${res.statusCode}）`));
        try {
          const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!body || body.status !== true) return finish(new Error('接口未明确确认业务成功，请检查登录状态或接口契约'));
          finish(null, body.data);
        } catch {finish(new Error('响应不是有效 JSON'));}
      });
    });
    const timer = setTimeout(() => {finish(new Error('请求超时')); req.destroy();}, 15000);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(method === 'POST' ? '{}' : undefined);
  });
}
async function stage(account, name, fn) {
  const n = ++stageNumber, start = Date.now();
  log(`账号 ${account.index} 阶段 ${n}：${name}`);
  try { const detail = await fn(); account.success++; log(`✅ ${detail}；耗时 ${Date.now()-start}ms`); }
  catch(e) {account.failed++; log(`❌ ${name}：${e.message}；耗时 ${Date.now()-start}ms`); throw e;}
}
async function runAccount(token, index) {
  const a = {index, success:0, alreadyComplete:0, skipped:0, failed:0, total:4};
  const start = Date.now(); stageNumber = 0;
  try {
    if (/\s/.test(token)) throw new Error('凭据不能含空白字符');
    if(dry) {
      for(const name of ['登录校验','签到状态查询','仅未签到时执行签到','奶滴值查询']) log(`账号 ${index} 阶段 ${++stageNumber}：⏭️ ${name}，预演不请求；耗时 0ms`);
      a.skipped = 4;
    } else {
      await stage(a,'登录校验',async () => {const data = await request(token,'/gateway/api/auth/account/user/info'); if(!data || typeof data !== 'object') throw new Error('用户信息结构无效'); const identity = safeIdentity(data.nickName); return identity ? `登录成功，昵称：${identity}` : '登录成功';});
      let signed;
      await stage(a,'签到状态查询',async () => {const data = await request(token,'/gateway/api/member/sign/status'); if(typeof data?.signed !== 'boolean') throw new Error('签到状态字段无效，停止后续操作'); signed = data.signed; return signed ? '已确认今日已签到' : '已确认今日未签到';});
      if(signed) {a.alreadyComplete++; log(`账号 ${index} 阶段 ${++stageNumber}：☑️ 今日已签到；耗时 0ms`);}
      else await stage(a,'每日签到',async () => {const data = await request(token,'/gateway/api/member/daily/sign','POST'); const bonus = data?.dailySign?.bonusPoint; if(!isNumber(bonus)) throw new Error('签到奖励字段无效，结果未确认；不自动重试'); return `签到成功，奶滴值+${bonus}`;});
      await stage(a,'奶滴值查询',async () => {const data = await request(token,'/gateway/api/member/point'); if(!isNumber(data)) throw new Error('奶滴值字段无效'); return `当前奶滴值：${data}`;});
    }
  } catch(e) {if(!a.failed) {a.failed++; log(`❌ 账号 ${index}：${e.message}`);} a.skipped = a.total-a.success-a.failed-a.alreadyComplete;}
  a.elapsedMs = Date.now()-start;
  a.ok = a.failed === 0;
  log(`账号 ${index} 统计：总任务 ${a.total}，成功 ${a.success}，已完成 ${a.alreadyComplete}，跳过 ${a.skipped}，失败 ${a.failed}，耗时 ${a.elapsedMs}ms`);
  results.push(a);
}
function isNumber(v) {return (typeof v === 'number' && Number.isFinite(v) && v >= 0) || (typeof v === 'string' && /^\d+(?:\.\d+)?$/.test(v));}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  // 青龙通知模块可访问网络，完全断网预演只生成通知摘要，不调用模块。
  if(dry) {log(`预演通知摘要：${body}`); return '预演本地摘要（禁止网络投递）';}
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  for(const file of files) {
    if(!fs.existsSync(file)) continue;
    let timer;
    try {
      const mod = require(file);
      if(typeof mod.sendNotify !== 'function') continue;
      await Promise.race([Promise.resolve().then(() => mod.sendNotify('甄稀冰淇淋',body)), new Promise((_,reject) => {timer = setTimeout(() => reject(new Error('timeout')),15000);})]);
      return '已发送';
    } catch {log('⚠️ 通知模块发送失败，不改变业务退出码');}
    finally {clearTimeout(timer);}
  }
  return '通知不可用或发送失败';
}
async function main() {
  console.log('========== 甄稀冰淇淋 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${tokens.length}`);
  if(!tokens.length) log('❌ 配置错误：缺少 ZX_ICE_TOKEN，请按说明设置每行一个账号');
  for(let i=0;i<tokens.length;i++) await runAccount(tokens[i],i+1);
  const failed = results.filter(a => !a.ok).length;
  const exitCode = !tokens.length || failed ? 1 : 0;
  const status = !tokens.length ? 'configuration-error' : failed ? (failed===tokens.length?'failure':'partial-failure') : dry?'dry-run':'success';
  const body = `账号总数 ${tokens.length}，成功 ${results.length-failed}，失败 ${failed}；最终状态 ${status}${!tokens.length?'；缺少账号配置':''}`;
  const notification = await notify(body);
  console.log('--------------------------------');
  log(body);
  const tasks = {total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  for(const a of results) for(const k of Object.keys(tasks)) tasks[k] += a[k];
  log(`子任务统计：${JSON.stringify(tasks)}；总耗时 ${Date.now()-started}ms`);
  log(`完成时间：${new Date().toISOString()}；通知状态：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:'zxice',mode:dry?'dry-run':'live',accounts:tokens.length,success:results.length-failed,failed,status,tasks,results,notification,exitCode}));
  process.exitCode = exitCode;
  // 外部通知模块可能遗留连接，汇总写出后仍须保证业务退出码。
  setTimeout(() => process.exit(exitCode),100).unref();
}
main().catch(() => {console.error('❌ 任务发生内部错误（详细信息已隐藏）'); process.exitCode=1;});
