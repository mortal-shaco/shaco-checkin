// name: OPPO商城每日签到与任务领奖
// cron: 25 12 * * *
/**
 * name: OPPO商城
 * cron: 25 12 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 基于 sudojia/AutoTaskScript src/client/sudojia_opposhop.js
 * 作者 Telegram@sudojia；https://blog.imzjw.cn；上游日期 2024/08/23。
 * OPPOSHOP_ACCOUNTS：每行 User-Agent|Cookie，仅在第一个 | 处分割。
 * 打开 OPPO商城 APP 抓包，进入「我的 - 签到任务」，获取
 * https://hd.opposhop.cn/api/cn/oapi/users/web/member/check?unpaid=0
 * 请求中的 User-Agent 和 Cookie；两者必须属于同一账号，不要分享抓包文件。
 * OPPOSHOP_TASK_IDS：手动核实安全的任务 ID，逗号分隔；默认不执行任务上报。
 * OPPOSHOP_CUMULATIVE_REWARDS=1：核实当月奖励 ID 1327/1328/1329/1330
 * 分别对应 3/5/10/15 天后启用；默认关闭，禁止猜测新活动的奖励 ID。
 * OPPOSHOP_DRY_RUN=1 完全断网预演。QINGLONG_NOTIFY=0 关闭通知。
 * 预演只准备通知内容，不加载可能联网的通知模块。Node.js >=18，无第三方依赖。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const BASE = 'https://hd.opposhop.cn';
const API = '/api/cn/oapi/marketing/';
const dry = process.env.OPPOSHOP_DRY_RUN === '1';
const start = Date.now();
const results = [];
const totals = {success:0, alreadyComplete:0, skipped:0, failed:0};
const log = s => console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`);
const wait = ms => new Promise(r => setTimeout(r, ms));
function request(route, account, body, html=false) {
  if (dry) throw Error('预演禁止网络访问');
  return new Promise((resolve,reject) => {
    const payload = body === undefined ? null : JSON.stringify(body);
    const req = https.request(BASE + route, {method:payload === null?'GET':'POST', headers:{
      'User-Agent':account.ua, Cookie:account.cookie, Accept:html?'text/html':'application/json',
      ...(payload === null?{}:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(payload)})
    }}, res => {
      let bytes=0; const chunks=[];
      res.on('data', c => { bytes+=c.length; if(bytes>2*1024*1024) req.destroy(Error('响应过大')); else chunks.push(c); });
      res.on('error', () => reject(Error('响应读取失败')));
      res.on('end', () => {
        if(res.statusCode<200 || res.statusCode>=300) return reject(Error('HTTP 请求失败'));
        const raw=Buffer.concat(chunks).toString('utf8');
        if(html) return resolve(raw);
        try { resolve(JSON.parse(raw)); } catch { reject(Error('响应不是有效 JSON')); }
      });
    });
    const timer=setTimeout(()=>req.destroy(Error('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',()=>reject(Error('网络请求失败或超时')));
    if(payload!==null) req.write(payload);
    req.end();
  });
}
function dataOf(r) {
  // 上游仅证明 data 是业务成功字段；不猜测未记录的成功业务码。
  if(!r || !r.data || r.code===403 || r.code==='403' || r.success===false) throw Error('业务结果未确认');
  return r.data;
}
function parseDSL(html) {
  const pos=html.indexOf('window.__DSL__');
  const begin=html.indexOf('{',pos);
  if(pos<0 || begin<0) throw Error('活动页面缺少 DSL');
  let depth=0, quote=false, escape=false;
  for(let i=begin;i<html.length;i++) {
    const c=html[i];
    if(quote) { if(escape) escape=false; else if(c==='\\') escape=true; else if(c==='"') quote=false; continue; }
    if(c==='"') quote=true;
    else if(c==='{') depth++;
    else if(c==='}' && --depth===0) { try{return JSON.parse(html.slice(begin,i+1));}catch{throw Error('活动 DSL 格式错误');} }
  }
  throw Error('活动 DSL 不完整');
}
function id(v) { const s=String(v??''); if(!/^\d+$/.test(s)) throw Error('活动或任务 ID 无效'); return s; }
async function runAccount(line,index,allowed) {
  const begun=Date.now(), stats={success:0,alreadyComplete:0,skipped:0,failed:0}; let stage=0;
  const step=async(name,fn)=>{
    const at=Date.now(); log(`账号 ${index} 阶段 ${++stage}：${name}`);
    try { const state=await fn() || 'success'; stats[state]++; log(`账号 ${index} ${name}：${state}，耗时 ${Date.now()-at}ms`); return true; }
    catch { stats.failed++; log(`❌ 账号 ${index} ${name}失败：配置、网络或业务结果未确认（已隐藏响应）`); return false; }
  };
  let a, signId, taskId, days;
  const valid=await step('解析账号参数',async()=>{
    const split=line.indexOf('|');
    if(split<1 || split===line.length-1) throw Error();
    a={ua:line.slice(0,split).trim(),cookie:line.slice(split+1).trim()};
    if(!a.ua || !a.cookie || /[\r\n\x00-\x1f\x7f]/.test(a.ua+a.cookie)) throw Error();
  });
  if(valid && dry) {
    await step('无网络预演',async()=>{log('DRY_RUN_OK：已校验账号格式；模拟活动发现、身份核验、签到、天数查询、任务与奖励安全开关；未发送请求');return 'skipped';});
  } else if(valid) {
    const ready=await step('发现当月活动',async()=>{
      const dsl=parseDSL(await request('/bp/b371ce270f7509f0?nightModelEnable=true&us=wode&um=qiandaobanner',a,undefined,true));
      const components=Object.values(dsl.byId||{});
      signId=id(components.find(c=>c?.type==='SignIn')?.attr?.activityInfo?.activityId);
      taskId=id(components.find(c=>c?.type==='Task')?.attr?.taskActivityInfo?.activityId);
      log(`活动：签到 ${signId}，任务 ${taskId}`);
    });
    const auth=ready && await step('核验会员身份',async()=>{
      const login=await request(API+'task/isLogin',a);
      if(!login || login.code===403 || login.code==='403' || login.data===false || login.success===false) throw Error();
      const member=dataOf(await request('/api/cn/oapi/users/web/member/check?unpaid=0',a));
      if(typeof member.name!=='string' || !member.name.trim()) throw Error();
      // 只显示官方明确的会员名称；手机号或包含凭据的异常名称不输出。
      if(!/\d{11}/.test(member.name) && !/[\r\n\x00-\x1f]/.test(member.name) && !member.name.includes(a.cookie) && !/cookie|token|session/i.test(member.name)) log(`OPPO会员：${member.name}`);
    });
    if(auth) {
      const detail=async()=>dataOf(await request(API+`cumulativeSignIn/getSignInDetail?activityId=${signId}`,a));
      await step('每日签到',async()=>{
        const before=await detail();
        if(before.todaySignIn===true) return 'alreadyComplete';
        if(before.todaySignIn!==false) throw Error();
        await wait(1200);
        dataOf(await request(API+'cumulativeSignIn/signIn',a,{activityId:signId}));
        if((await detail()).todaySignIn!==true) throw Error();
        log('✅ 签到成功（状态复核通过）');
      });
      await step('查询连续签到天数',async()=>{
        const d=await detail(); days=Number(d.signInDayNum);
        if(!Number.isInteger(days)||days<0) {days=undefined;throw Error();}
        log(`已连续签到 ${days} 天`);
      });
      let tasks;
      await step('读取任务列表',async()=>{
        tasks=dataOf(await request(API+`task/queryTaskList?activityId=${taskId}&source=c`,a)).taskDTOList;
        if(!Array.isArray(tasks)) {tasks=undefined;throw Error();}
        log(`返回 ${tasks.length} 个任务，仅执行已核实的白名单 ID`);
      });
      const seen=new Set();
      for(const t of tasks||[]) {
        await step('任务检查与领奖',async()=>{
          const tid=id(t.taskId); seen.add(tid);
          if(Number(t.taskType)===6 || !allowed.has(tid)) {log(`任务 ${tid}：安全策略跳过`);return 'skipped';}
          const aid=id(t.activityId); if(aid!==taskId) throw Error();
          await wait(1200);
          dataOf(await request(API+`taskReport/signInOrShareTask?taskId=${tid}&activityId=${aid}&taskType=1`,a));
          await wait(2500);
          const award=dataOf(await request(API+`task/receiveAward?taskId=${tid}&activityId=${aid}`,a));
          if(award.awardValue===undefined) throw Error();
          log(`任务 ${tid}：上报成功，奖励已确认`);
        });
      }
      for(const tid of allowed) if(tasks && !seen.has(tid)) await step('核对已配置任务',async()=>{throw Error();});
      for(const [awardId,threshold] of [[1327,3],[1328,5],[1329,10],[1330,15]]) {
        await step(`${threshold} 天累计奖励`,async()=>{
          if(process.env.OPPOSHOP_CUMULATIVE_REWARDS!=='1') return 'skipped';
          if(days===undefined) throw Error();
          if(days<threshold) return 'skipped';
          await wait(1200);
          const award=dataOf(await request(API+'cumulativeSignIn/drawCumulativeAward',a,{activityId:signId,awardId}));
          if(award.awardValue===undefined) throw Error();
          log('累计奖励领取成功');
        });
      }
    }
  }
  for(const k of Object.keys(totals)) totals[k]+=stats[k];
  const result={account:index,status:stats.failed?'failure':dry?'dry-run':'success',...stats,total:Object.values(stats).reduce((a,b)=>a+b,0),durationMs:Date.now()-begun};
  results.push(result);log(`账号统计 ${JSON.stringify(result)}`);
}
async function notify(summary) {
  if(/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY||'1')) return '已关闭';
  if(dry) {log('通知预演：已生成脱敏总结；为保证断网未加载通知模块');return '断网预演';}
  const locations=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  for(const file of locations) {
    if(!fs.existsSync(file)) continue;
    try {
      const sender=require(file);
      await Promise.race([Promise.resolve().then(()=>sender.sendNotify('OPPO商城',summary)),new Promise((_,reject)=>{const timer=setTimeout(()=>reject(Error()),10000);timer.unref();})]);
      return '已发送';
    } catch {return '通知失败（业务退出码不变）';}
  }
  return '通知模块不可用（业务退出码不变）';
}
async function main() {
  const lines=(process.env.OPPOSHOP_ACCOUNTS||'').split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  log('========== OPPO商城 =========='); log(`开始时间：${new Date(start).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${lines.length}`);
  let configError=false;
  const configured=(process.env.OPPOSHOP_TASK_IDS||'').trim();
  const allowed=new Set(configured?configured.split(',').map(s=>s.trim()):[]);
  if(!lines.length || [...allowed].some(s=>!/^\d+$/.test(s)) || !['0','1'].includes(process.env.OPPOSHOP_CUMULATIVE_REWARDS||'0') || !['0','1'].includes(process.env.OPPOSHOP_DRY_RUN||'0')) {
    configError=true;log('❌ 配置错误：请检查账号变量、任务 ID 和开关格式');
  } else for(let i=0;i<lines.length;i++) await runAccount(lines[i],i+1,allowed);
  const failed=results.filter(r=>r.status==='failure').length;
  const success=results.length-failed;
  const status=configError?'configuration-error':failed?(success?'partial-failure':'failure'):dry?'dry-run':'success';
  const notification=await notify(`账号总数 ${lines.length}，成功数 ${dry?0:success}，失败数 ${failed}，预演数 ${dry?success:0}；最终状态 ${status}；子任务成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  const summary={status,mode:dry?'dry-run':'live',accounts:lines.length,success:dry?0:success,failed,dryRun:dry?success:0,configurationError:configError,tasks:totals,notification,durationMs:Date.now()-start,finishedAt:new Date().toISOString()};
  log('--------------------------------');log(`最终任务统计：${JSON.stringify(summary)}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
  process.exitCode=configError||failed?1:0;
}
main().catch(()=>{log('❌ 未预期的内部错误（已隐藏详情）');process.exitCode=1;});
