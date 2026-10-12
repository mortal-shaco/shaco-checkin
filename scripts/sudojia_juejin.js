// name: 稀土掘金每日签到
// cron: 5 10 * * *
/**
 * name: 稀土掘金每日签到
 * cron: 5 10 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Based on sudojia/AutoTaskScript, src/web/sudojia_juejin.js
 * Author: Telegram@sudojia — https://blog.imzjw.cn
 * 上游提交：4a55327baed0321bdf95802a75cc8363cae118b0
 * JUEJIN_COOKIE：每行 sessionid#签到请求的原始查询串；仅在首个 # 分隔。
 * 登录 https://juejin.cn，在开发者工具 Application/Cookies 取得 sessionid；
 * Network 中手动签到，复制 /growth_api/v1/check_in 的查询串（不含 ?）。
 * 查询串须含 uuid、spider、msToken、a_bogus；签名可能过期，失效须重新抓取。
 * 不自动生成签名，不下载依赖。Node.js >=18，仅使用内置库。
 * JUEJIN_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const started = Date.now();
const dry = process.env.JUEJIN_DRY_RUN === '1';
const title = '稀土掘金每日签到';
const lines = (process.env.JUEJIN_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const results = [];
const time = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = s => console.log(`[${time()}] ${s}`);
function parse(line) {
  const n = line.indexOf('#');
  if (n < 1) throw new Error('参数格式错误：需要 sessionid#原始查询串');
  const session = line.slice(0,n), query = line.slice(n+1);
  if (/[\s;\x00-\x1f\x7f]/.test(session) || !query || /[\s#\x00-\x1f\x7f]/.test(query)) throw new Error('凭据格式不合法');
  const q = new URLSearchParams(query);
  for (const key of ['uuid','spider','msToken','a_bogus']) if (!q.get(key)) throw new Error(`查询串缺少 ${key}`);
  if (q.has('aid') && (q.getAll('aid').length !== 1 || q.get('aid') !== '2608')) throw new Error('查询串 aid 必须为 2608');
  return {session, query:(q.has('aid') ? '' : 'aid=2608&') + query};
}
function request(account, endpoint, method='GET', body) {
  return new Promise((resolve,reject) => {
    const payload = body === undefined ? undefined : JSON.stringify(body);
    const req = https.request('https://api.juejin.cn'+endpoint, {method, headers:{
      Accept:'application/json', 'Accept-Encoding':'identity', 'Content-Type':'application/json',
      Referer:'https://juejin.cn/', Origin:'https://juejin.cn',
      'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
      Cookie:`sid_tt=${account.session}; sessionid=${account.session}; sessionid_ss=${account.session}`,
      ...(payload ? {'Content-Length':Buffer.byteLength(payload)} : {})
    }}, res => {
      let size=0; const chunks=[];
      res.on('data', chunk => {size+=chunk.length; if(size>1048576) req.destroy(new Error('响应超过大小限制')); else chunks.push(chunk);});
      res.on('error', () => reject(new Error('响应传输失败')));
      res.on('end', () => {
        if(res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP 状态 ${res.statusCode}`));
        try {resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));} catch {reject(new Error('响应不是有效 JSON'));}
      });
    });
    const timer=setTimeout(() => req.destroy(new Error('请求超时')),15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    req.end(payload);
  });
}
function checked(r) {
  if (!r || r.err_no !== 0) throw new Error(r && r.err_no === 403 ? '登录失效，请重新获取凭据' : '业务接口未确认成功');
  return r.data;
}
function number(v) {if(typeof v !== 'number' || !Number.isFinite(v) || v<0) throw new Error('响应数值字段不符合预期'); return v;}
async function runAccount(line,index) {
  const begin=Date.now(), stat={index,total:5,success:0,alreadyComplete:0,skipped:0,failed:0};
  let account, status;
  const stages=[
    ['登录与今日签到状态',async()=>{account=parse(line); const d=checked(await request(account,'/growth_api/v1/get_today_status')); if(typeof d !== 'boolean') throw new Error('今日状态字段不符合预期'); status=d; return d?'今日已签到':'今日尚未签到';}],
    ['账号昵称',async()=>{const d=checked(await request(account,'/user_api/v1/user/get_info_pack?aid=2608','POST',{pack_req:{user_counter:true,user_growth_info:true,user:true}})); const name=d?.user_basic?.user_name; if(typeof name!=='string'||!name) throw new Error('未返回账号昵称'); return `账号昵称：${name}`;}],
    ['每日签到',async()=>{if(status) return {already:true,text:'今日已签到'}; const r=await request(account,'/growth_api/v1/check_in?'+account.query,'POST'); if(r?.err_no===15001){if(checked(await request(account,'/growth_api/v1/get_today_status')) !== true) throw new Error('重复签到提示未通过状态复核'); return {already:true,text:'今日已签到（状态复核成功）'};} const d=checked(r); return `签到成功，获得 ${number(d?.incr_point)} 矿石`;}],
    ['矿石余额',async()=>`当前矿石数：${number(checked(await request(account,'/growth_api/v1/get_cur_point?'+account.query)))}`],
    ['签到天数',async()=>{const d=checked(await request(account,'/growth_api/v1/get_counts?aid=2608')); return `已连续签到${number(d?.cont_count)}天、累计签到${number(d?.sum_count)}天`;}]
  ];
  let valid=true;
  for(let i=0;i<stages.length;i++) {
    const t=Date.now(); log(`账号 ${index} 阶段 ${i+1}/5 ${stages[i][0]}`);
    try {
      if(!valid){stat.skipped++; log('⏭️ 登录或配置检查失败，跳过'); continue;}
      if(dry){if(i===0) account=parse(line); stat.skipped++; log('⏭️ DRY_RUN：参数检查通过，不发送请求'); continue;}
      const r=await stages[i][1](); if(r?.already) stat.alreadyComplete++; else stat.success++;
      log(`${r?.already?'☑️':'✅'} ${typeof r==='string'?r:r.text}`);
    } catch(e) {stat.failed++; if(i===0) valid=false; log(`❌ ${e.message}`);}
    finally {log(`账号 ${index} 阶段 ${i+1} 耗时 ${Date.now()-t}ms`);}
  }
  stat.durationMs=Date.now()-begin; stat.status=stat.failed?'failure':dry?'dry-run':'success'; results.push(stat);
  log(`账号 ${index} 统计：总任务 ${stat.total}，成功 ${stat.success}，已完成 ${stat.alreadyComplete}，跳过 ${stat.skipped}，失败 ${stat.failed}，耗时 ${stat.durationMs}ms`);
}
async function notify(body) {
  if(/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY||'1')) return '已关闭';
  if(dry) return '断网预演：通知内容已生成，跳过投递';
  const candidates=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=candidates.find(p=>fs.existsSync(p));
  if(!file) return '不可用：未找到 sendNotify.js';
  return new Promise(resolve=>{
    const child=spawn(process.execPath,['-e','Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))',file,title,body],{stdio:'ignore'});
    const timer=setTimeout(()=>child.kill('SIGKILL'),20000);
    child.on('error',()=>{clearTimeout(timer);resolve('投递失败');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已投递':'投递失败或超时');});
  });
}
(async()=>{
  log(`========== ${title} ==========`); log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${lines.length}`);
  if(!lines.length) log('❌ 配置错误：JUEJIN_COOKIE 未提供账号');
  for(let i=0;i<lines.length;i++) await runAccount(lines[i],i+1);
  const failed=results.filter(r=>r.failed>0).length;
  const exitCode=failed||!lines.length?1:0;
  const summary={task:title,mode:dry?'dry-run':'live',accounts:lines.length,success:results.filter(r=>r.status==='success').length,failed,dryRun:results.filter(r=>r.status==='dry-run').length,status:exitCode?(lines.length?'failure':'configuration-error'):dry?'dry-run':'success',results};
  if(failed>0 && failed<lines.length) summary.status='partial-failure';
  summary.notification=await notify(`账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${failed}，预演 ${summary.dryRun}；状态 ${summary.status}`);
  summary.durationMs=Date.now()-started; summary.finishedAt=new Date().toISOString();
  log('----------------------------------------');
  log(`最终统计：账号 ${summary.accounts}，成功 ${summary.success}，失败 ${failed}，预演 ${summary.dryRun}`);
  const totals=results.reduce((a,r)=>{for(const k of Object.keys(a)) a[k]+=r[k]; return a;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log(`子任务统计：总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`通知：${summary.notification}；总耗时 ${summary.durationMs}ms；完成时间 ${summary.finishedAt}；最终状态 ${summary.status}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary)); process.exitCode=exitCode;
})();
