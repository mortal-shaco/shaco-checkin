// name: 香蕉视频每日任务
// cron: 10 1 * * *
/**
 * name: 香蕉视频每日任务
 * cron: 10 1 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 原作者 Telegram@sudojia；https://blog.imzjw.cn
 * 来源 sudojia/AutoTaskScript src/client/sudojia_bananaVideo.js
 * BANANA_ACCOUNT：在香蕉视频 APP 注册并设置密码，每行 手机号#密码，仅按首个 # 分割。
 * Node.js >=18；无第三方业务依赖。通知使用青龙 sendNotify.js。
 * BANANA_DRY_RUN=1 完全断网预演；BANANA_FAVORITE=1 开启随机收藏（不删除收藏）；
 * BANANA_COMMENT=1 开启公开评论（一言署名，失败使用本地文本）。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const DRY = process.env.BANANA_DRY_RUN === '1';
const BASE = 'https://mgcrjh.ipajx0.cc';
const disabled = /^(0|false|no|off)$/i;
const stamp = () => new Date().toTimeString().slice(0,8);
const log = text => console.log(`[${stamp()}] ${text}`);
const delay = () => new Promise(r => setTimeout(r, 1700));
const randomId = () => 1 + Math.floor(Math.random()*66000);
// 通知在有时间上限的独立进程中执行；预演也尝试通知接口，但禁止网络连接。
async function notifyChild() {
  if (DRY) {
    const deny = () => {throw new Error('预演禁止联网');};
    require('node:net').Socket.prototype.connect = deny;
    require('node:tls').connect = deny;
    require('node:http').request = deny;
    https.request = deny;
    global.fetch = deny;
    for (const k of ['spawn','exec','execFile','fork','spawnSync','execSync','execFileSync']) require('node:child_process')[k] = deny;
  }
  let body = ''; for await (const c of process.stdin) body += c;
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = locations.find(f => fs.existsSync(f));
  if (!file) throw new Error('通知模块不可用');
  await require(file).sendNotify('香蕉视频每日任务', body);
}
function notify(body) {
  if (disabled.test(process.env.QINGLONG_NOTIFY || '1')) return Promise.resolve('已关闭');
  return new Promise(resolve => {
    const child = spawn(process.execPath,[__filename,'--notify'],{stdio:['pipe','ignore','ignore'],env:process.env});
    const timer = setTimeout(() => {child.kill('SIGKILL');},15000);
    child.on('error',()=>{clearTimeout(timer);resolve('不可用');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':DRY?'预演通知不可用或联网已阻止':'发送失败或不可用');});
    child.stdin.on('error',()=>{}); child.stdin.end(body);
  });
}
function request(url, method='GET', headers={}, fields, limit=262144, timeout=12000) {
  if (DRY) throw new Error('预演禁止联网');
  return new Promise((resolve,reject)=>{
    const body = fields ? new URLSearchParams(fields).toString() : undefined;
    const h = {...headers};
    if(body!==undefined) {h['Content-Type']='application/x-www-form-urlencoded';h['Content-Length']=Buffer.byteLength(body);}
    let timer;
    const req=https.request(url,{method,headers:h},res=>{
      const chunks=[]; let size=0;
      res.on('data',c=>{size+=c.length;if(size>limit) req.destroy(new Error('响应过大'));else chunks.push(c);});
      res.on('error',()=>reject(new Error('响应中断')));
      res.on('end',()=>{
        if(res.statusCode<200||res.statusCode>=300) return reject(new Error('HTTP 请求失败'));
        try {resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));}catch {reject(new Error('响应格式错误'));}
      });
    });
    timer=setTimeout(()=>req.destroy(new Error('请求超时')),timeout);
    req.on('error',()=>reject(new Error('请求失败或超时')));
    req.on('close',()=>clearTimeout(timer));
    req.end(body);
  });
}
async function publicText() {
  const clean = x => typeof x==='string'?x.replace(/\s+/g,' ').trim():'';
  try {
    const d=await request('https://v1.hitokoto.cn/?encode=json','GET',{},undefined,16384,8000);
    const text=clean(d.hitokoto), author=clean(d.from_who), source=clean(d.from);
    if(!text) throw Error();
    const result=text+(author&&source?` —— ${author}《${source}》`:source?` ——《${source}》`:author?` —— ${author}`:'');
    if([...result].length>280) throw Error();
    return result;
  } catch {log('评论文本：一言不可用，采用本地文本');return '愿每一天都有值得珍惜的小美好。';}
}
async function run() {
  const start=Date.now();
  const lines=(process.env.BANANA_ACCOUNT||'').split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  const results=[]; let configError=!lines.length;
  log('========== 香蕉视频每日任务 ==========');
  log(`开始时间：${new Date().toISOString()}；模式：${DRY?'断网预演':'正式'}；账号数：${lines.length}`);
  for (const key of ['BANANA_DRY_RUN','BANANA_FAVORITE','BANANA_COMMENT']) if(process.env[key]!==undefined&&!['0','1'].includes(process.env[key])) configError=true;
  if(configError) log('❌ 配置错误：账号不能为空，行为开关只能为 0 或 1');
  for(let i=0;i<lines.length;i++) {
    const t=Date.now(), stats={account:i+1,total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
    const split=lines[i].indexOf('#'); const phone=lines[i].slice(0,split), password=lines[i].slice(split+1);
    const valid=split>0&&/^\d{11}$/.test(phone)&&password.length>0;
    const headers={'x-system':'Android','x-channel':'xj1','x-version':'5.0.5','User-Agent':'Mozilla/5.0 (Linux; Android 10)','Accept-Language':'zh-CN,zh;q=0.9'};
    let loggedIn=false;
    const api=async (route,method='GET',fields) => {
      const d=await request(BASE+route,method,headers,fields);
      if(!d||d.retcode!==0) throw new Error('业务未确认成功');
      return d.data;
    };
    async function step(name,fn,enabled=true) {
      stats.total++;const st=Date.now();log(`账号 ${i+1} 阶段 ${stats.total}：${name}`);
      if(!enabled){stats.skipped++;log(`⏭️ 未启用或前置条件未满足；耗时 ${Date.now()-st}ms`);return;}
      try {if(DRY) log('预演：参数与执行计划通过，无网络请求');else await fn();stats.success++;log(`✅ ${name}${DRY?'预演通过':'成功'}；耗时 ${Date.now()-st}ms`);}
      catch {stats.failed++;log(`❌ ${name}失败：请求、业务码或响应字段未通过验证；耗时 ${Date.now()-st}ms`);}
      if(!DRY) await delay();
    }
    if(!valid||configError) {stats.total=1;stats.failed=1;log(`❌ 账号 ${i+1} 配置无效，格式为每行 手机号#密码`);}
    else {
      await step('登录',async()=>{const d=await api('/login','POST',{logintype:'0',mobiprefix:'86',mobi:phone,password});if(typeof d?.xxx_api_auth!=='string'||!d.xxx_api_auth) throw Error();headers['X-Cookie-Auth']=d.xxx_api_auth;loggedIn=true;});
      if(DRY) loggedIn=true;
      await step('账号信息',async()=>{const d=await api('/ucp/index');if(typeof d?.user?.username!=='string') throw Error();const identity=d.user.username;if(identity.includes(phone)||identity.includes(password)||identity.includes(headers['X-Cookie-Auth'])||/\d{11}/.test(identity)) log('身份字段含敏感信息，已抑制');else log(`昵称：${identity.replace(/[\r\n\x00-\x1f\x7f]/g,' ')}`);},loggedIn);
      await step('每日签到',()=>api('/ucp/task/sign','POST'),loggedIn);
      await step('随机收藏五个视频（保留已有收藏）',async()=>{for(let n=0;n<5;n++){await api('/favorite/add','POST',{vodid:String(randomId())});log(`收藏 ${n+1}/5 已确认`);await delay();}},loggedIn&&process.env.BANANA_FAVORITE==='1');
      await step('广告任务',()=>api('/ucp/task/adviewClick'),loggedIn);
      await step('长视频下载任务登记',async()=>{for(let n=0;n<5;n++){const d=await request(BASE+'/vod/reqdown/'+randomId(),'GET',headers);if(d?.retcode===0)return;if(d?.retcode!==3)throw Error();await delay();}throw Error();},loggedIn);
      await step('观看十个视频',async()=>{let count=0;for(let n=0;n<30&&count<10;n++){const d=await request(BASE+'/v2/vod/reqplay/'+randomId(),'GET',headers);if(d?.retcode===0){count++;log(`观看 ${count}/10 已确认`);}else log('观看业务未成功，有限重试');await delay();}if(count!==10)throw Error();},loggedIn);
      await step('二维码任务登记',()=>api('/ucp/task/qrcodeSave'),loggedIn);
      await step('公开评论',async()=>{const content=await publicText();for(let n=0;n<5;n++){const d=await request(BASE+'/comment/post','POST',headers,{vodid:String(randomId()),content});if(d?.retcode===0)return;if(d?.retcode!==3)throw Error();await delay();}throw Error();},loggedIn&&process.env.BANANA_COMMENT==='1');
      await step('金币查询',async()=>{const d=await api('/ucp/index');const coins=d?.user?.goldcoin;if(!['number','string'].includes(typeof coins)||!/^\d+(\.\d+)?$/.test(String(coins)))throw Error();log(`当前金币：${coins}`);},loggedIn);
    }
    stats.durationMs=Date.now()-t;results.push(stats);
    log(`账号 ${i+1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${stats.durationMs}ms`);
  }
  const failed=results.filter(r=>r.failed>0).length, success=results.length-failed;
  const status=configError?'configuration-error':failed?(success?'partial-failure':'failure'):DRY?'dry-run':'success';
  const body=`模式：${DRY?'断网预演':'正式'}；账号总数 ${lines.length}，成功 ${success}，失败 ${failed}；状态 ${status}`;
  const notification=await notify(body);
  log('--------------------------------');log(body);
  const tasks=results.reduce((a,r)=>{for(const k of Object.keys(a))a[k]+=r[k];return a;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log(`子任务统计：总数 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now()-start}ms；通知：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({status,mode:DRY?'dry-run':'live',accounts:lines.length,success,failed,tasks,results,notification,durationMs:Date.now()-start}));
  process.exitCode=configError||failed?1:0;
}
if(process.argv.includes('--notify')) notifyChild().catch(()=>{process.exitCode=1;});else run().catch(()=>{console.error('任务内部错误');process.exitCode=1;});
