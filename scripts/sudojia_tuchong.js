// name: 图虫每日签到
// cron: 38 5 * * *
/**
 * name: 图虫每日签到
 * cron: 38 5 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/client/sudojia_tuchong.js
 * 基于上游维护，按 GPL-3.0 分发。
 * Node.js >=18，无第三方业务依赖。
 * TUC_ACCOUNTS：图虫 APP 注册并设置或重设密码，每行 手机号#密码。
 * 只在第一个 # 分割；密码中的 #、&、@ 保留，不支持 & 分隔账号。
 * TUC_DRY_RUN=1：完全断网预演；通知仅生成本地摘要，不调用外部发送器。
 * QINGLONG_NOTIFY=0 可关闭通知；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
 * 已移除随机点赞、关注及撤销操作，避免破坏账号原有关系。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const started = Date.now();
const dry = process.env.TUC_DRY_RUN === '1';
const lines = (process.env.TUC_ACCOUNTS || '').split(/\r?\n/).filter(x => x.trim().length > 0);
const summary = {task:'图虫每日签到', mode:dry?'dry-run':'live', accounts:lines.length, success:0, failed:0, tasks:{total:0,success:0,alreadyComplete:0,skipped:0,failed:0}, notification:'pending'};
const stamp = () => new Date().toTimeString().slice(0,8);
const log = text => console.log(`[${stamp()}] ${text}`);
const headers = {'User-Agent':'okhttp/3.12.2 com.ss.android.tuchong (Tuchong: 7391 7.39.1) (Android: 11 30)', 'Content-Type':'application/x-www-form-urlencoded', version:'7576',channel:'oppo',platform:'android','Accept-Encoding':'identity'};
function request(url, method, token, form) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve,reject) => {
    const body = form ? new URLSearchParams(form).toString() : undefined;
    const h = {...headers};
    if(token) h.token=token;
    if(body) h['Content-Length']=Buffer.byteLength(body);
    let settled=false;
    const finish=(err,value)=>{if(settled)return;settled=true;clearTimeout(timer);err?reject(err):resolve(value);};
    const req=https.request(url,{method,headers:h},res=>{
      if(res.statusCode<200||res.statusCode>=300){res.resume();finish(new Error('HTTP 状态异常'));return;}
      let chunks=[],size=0;
      res.on('data',chunk=>{size+=chunk.length;if(size>1048576){req.destroy();finish(new Error('响应过大'));}else chunks.push(chunk);});
      res.on('error',()=>finish(new Error('响应读取失败')));
      res.on('aborted',()=>finish(new Error('响应中断')));
      res.on('end',()=>{try {const value=JSON.parse(Buffer.concat(chunks).toString('utf8'));if(!value||typeof value!=='object')throw 0;finish(null,value);}catch{finish(new Error('响应格式异常'));}});
    });
    const timer=setTimeout(()=>{req.destroy();finish(new Error('请求超时'));},15000);
    req.on('error',()=>finish(new Error('网络请求失败')));
    req.end(body);
  });
}
function encrypt(phone){const c=crypto.createCipheriv('aes-128-ecb',Buffer.from('41343045353832423133303141423545','hex'),null);return c.update(phone,'utf8','base64')+c.final('base64');}
function checked(data){if(data.result!=='SUCCESS')throw new Error('业务未明确成功');return data;}
async function account(line,index){
  const t=Date.now(),stats={total:4,success:0,alreadyComplete:0,skipped:0,failed:0};
  let token,identity,loginOK=false;
  log(`账号 ${index} 开始`);
  const steps=[['登录',async()=>{
    const pos=line.indexOf('#');
    if(pos<1||!line.slice(pos+1)||!/^\+?\d{6,15}$/.test(line.slice(0,pos)))throw new Error('配置错误：需每行手机号#密码');
    if(dry)return;
    const data=await request('https://api.tuchong.com/accounts/login','POST',null,{account:encrypt(line.slice(0,pos)),password:line.slice(pos+1)});
    if(data.account_status!==0||typeof data.token!=='string'||!data.token||!['string','number'].includes(typeof data.identity)||!String(data.identity))throw new Error('登录未明确成功或缺少令牌/身份');
    token=data.token;identity=String(data.identity);
  }],['账号身份查询',async()=>{
    if(dry)return;
    const data=checked(await request(`https://api.tuchong.com/2/sites/${encodeURIComponent(identity)}`,'GET',token));
    if(!data.site||typeof data.site.name!=='string'||!['string','number'].includes(typeof data.site.site_id))throw new Error('缺少账号身份字段');
    // 官方非秘密身份按返回值展示，不输出其他响应字段。
    log(`账号 ${index} 昵称：${data.site.name}；公开 UID：${data.site.site_id}`);
  }],['每日签到',async()=>{
    if(dry)return;
    checked(await request('https://api.tuchong.com/point/check-in','GET',token));
  }],['积分与等级查询',async()=>{
    if(dry)return;
    const data=await request('https://m.tuchong.com/tuchonggapi/misc/point/v2/status?platform=android&version=7.57.6','GET',token);
    if(data.result!==undefined&&data.result!=='SUCCESS')throw new Error('积分查询业务失败');
    // 上游此接口以 status 字段为数据契约，未提供额外成功码。
    const s=data.status;
    if(!s||!Number.isFinite(Number(s.total_point))||s.total_point===null||s.total_point===''||typeof s.influence_level_text!=='string'||!s.influence_level_text)throw new Error('积分或等级字段缺失');
    log(`账号 ${index} 当前积分：${Number(s.total_point)}；当前等级：${s.influence_level_text}`);
  }]];
  for(let n=0;n<steps.length;n++){
    const [name,fn]=steps[n],s=Date.now();
    if(n>0&&!loginOK){stats.skipped++;log(`账号 ${index} 阶段 ${n+1}/4 ${name} ⏭️ 登录失败，跳过；耗时 0ms`);continue;}
    log(`账号 ${index} 阶段 ${n+1}/4 ${name} 开始`);
    try{await fn();if(n===0)loginOK=true;stats.success++;log(`账号 ${index} 阶段 ${n+1}/4 ${name} ✅ ${dry?'预演通过，未发送请求':'成功'}；耗时 ${Date.now()-s}ms`);}
    catch(e){stats.failed++;log(`账号 ${index} 阶段 ${n+1}/4 ${name} ❌ ${e.message}；耗时 ${Date.now()-s}ms`);}
  }
  for(const k of Object.keys(stats))summary.tasks[k]+=stats[k];
  stats.failed?summary.failed++:summary.success++;
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${Date.now()-t}ms`);
}
async function notify(body){
  if(['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY||'1').toLowerCase()))return 'disabled';
  if(dry){log(`通知预演（断网，仅本地）：${body}`);return 'dry-run-local';}
  const dirs=[process.env.QINGLONG_NOTIFY_DIR,'/ql/data/scripts','/ql/scripts'].filter(Boolean);
  const file=dirs.map(d=>path.join(d,'sendNotify.js')).find(f=>fs.existsSync(f));
  if(!file)return 'unavailable';
  return new Promise(resolve=>{
    // 隔离通知模块日志和异常，避免泄漏其配置；限时且不改变业务退出码。
    const child=spawn(process.execPath,['-e',`Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))`,file,'图虫每日签到',body],{stdio:'ignore'});
    const timer=setTimeout(()=>child.kill('SIGKILL'),20000);
    child.on('error',()=>{clearTimeout(timer);resolve('failed');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'sent':'failed');});
  });
}
async function main(){
  log('========== 图虫每日签到 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${summary.mode}；账号数：${lines.length}`);
  if(!lines.length){summary.configurationError=true;log('❌ 配置错误：请设置 TUC_ACCOUNTS，每行手机号#密码');}
  for(let i=0;i<lines.length;i++)await account(lines[i],i+1);
  const failed=!!summary.configurationError||summary.failed>0;
  summary.status=failed?(summary.success?'partial-failure':'failure'):(dry?'dry-run':'success');
  const body=`模式 ${summary.mode}；账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；子任务成功 ${summary.tasks.success}，失败 ${summary.tasks.failed}，跳过 ${summary.tasks.skipped}；状态 ${summary.configurationError?'configuration-error':summary.status}`;
  try{summary.notification=await notify(body);}catch{summary.notification='failed';}
  summary.durationMs=Date.now()-started;summary.finishedAt=new Date().toISOString();
  log('----------------------------------------');log(body);
  log(`子任务总数 ${summary.tasks.total}，已完成 ${summary.tasks.alreadyComplete}；通知状态 ${summary.notification}；总耗时 ${summary.durationMs}ms`);
  log(`完成时间：${summary.finishedAt}；最终状态：${summary.status}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary));process.exitCode=failed?1:0;
}
main();
