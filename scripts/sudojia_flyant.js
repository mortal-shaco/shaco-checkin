// name: 飞蚂蚁旧衣回收
// cron: 50 0 * * *
/**
 * name: 飞蚂蚁旧衣回收
 * cron: 0 6 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 基于 sudojia/AutoTaskScript src/wx_mini/sudojia_flyant.js
 * 原作者 Telegram@sudojia，https://blog.imzjw.cn，2024/10/04
 * FLY_ANT_TOKEN：每个非空行一个账号，格式为 Token 或 Token|真实步数。
 * 在旧衣回收微信小程序抓取 openapp.fmy90.com 请求头 authorization，去掉 bearer。
 * 可选步数为当日真实未兑换步数，仅提交一次，不伪造或重复兑换。
 * FLY_ANT_DRAW / FLY_ANT_EARLY_SIGN / FLY_ANT_BET=1 显式开启抽奖/早起打卡/报名。
 * 抽奖和报名可能消耗环保豆；早起活动时间及资格请在小程序确认。
 * FLY_ANT_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，仅使用内置模块。通知模块是可选集成，不影响业务退出码。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["4fb882fdbc0ba03a", "scripts/sudojia_flyant.js", "sudojia_flyant.js", "sudojia_flyant"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const TITLE = '飞蚂蚁旧衣回收';
const dry = process.env.FLY_ANT_DRY_RUN === '1';
const common = {version:'V2.00.01', platformKey:'F2EE24892FBF66F0AFF8C0EB532A9394', mini_scene:1356, partner_ext_infos:''};
const started = Date.now();
const results = [];
const log = s => console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`);
function request(token, endpoint, method='POST', extra={}) {
  const params = {...common, ...(method==='GET'?{mini_scene:1256}:{}), ...extra};
  const url = new URL(endpoint, 'https://openapp.fmy90.com');
  const body = method==='POST' ? JSON.stringify(params) : undefined;
  if (method==='GET') url.search = new URLSearchParams(params).toString();
  return new Promise((resolve,reject) => {
    let settled=false;
    const finish=(err,val)=>{if(settled)return;settled=true;clearTimeout(timer);err?reject(err):resolve(val);};
    const req=https.request(url,{method,headers:{authorization:`bearer ${token}`,'content-type':'application/json;charset=utf8','User-Agent':'Mozilla/5.0','referer':'https://servicewechat.com/wx501990400906c9ff/426/page-frame.html','accept-language':'zh-CN,zh;q=0.9'}},res=>{
      let text='',bytes=0;
      res.on('data',chunk=>{bytes+=chunk.length;if(bytes>1048576){finish(new Error('响应超出大小限制'));req.destroy();}else text+=chunk;});
      res.on('error',()=>finish(new Error('响应读取失败')));
      res.on('end',()=>{
        if(res.statusCode<200||res.statusCode>=300)return finish(new Error(`HTTP 请求失败（${res.statusCode}）`));
        let data;try{data=JSON.parse(text);}catch{return finish(new Error('响应不是有效 JSON'));}
        if(!data || data.code!==200)return finish(new Error('业务未确认成功（接口 code 非 200）'));
        finish(null,data);
      });
    });
    const timer=setTimeout(()=>{finish(new Error('请求超时'));req.destroy();},15000);
    req.on('error',()=>finish(new Error('网络请求失败')));
    req.end(body);
  });
}
function identity(data, token) {
  const obj=data && data.data;
  if(!obj||typeof obj!=='object')return;
  for(const key of ['nickname','username','displayName','publicUid']) {
    const v=obj[key];
    if((typeof v==='string'||typeof v==='number') && String(v)!==token) log(`官方账号身份 ${key}：${JSON.stringify(v)}`);
  }
}
function number(v) {if(!['string','number'].includes(typeof v)||String(v).trim()===''||!Number.isFinite(Number(v))||Number(v)<0)throw new Error('响应统计字段无效');return Number(v);}
async function account(line,index) {
  const begin=Date.now(), r={account:index,total:7,success:0,alreadyComplete:0,skipped:0,failed:0};
  results.push(r);
  const delimiter=line.indexOf('|');
  const token=(delimiter<0?line:line.slice(0,delimiter)).trim();
  const steps=delimiter<0?'':line.slice(delimiter+1).trim();
  if(!token || /\s|&/.test(token) || (steps!=='' && (!/^\d+$/.test(steps)||!Number.isSafeInteger(Number(steps))||Number(steps)<=0))) {
    r.failed=1;r.skipped=6;r.durationMs=Date.now()-begin;log(`❌ 账号 ${index} 参数无效；统计：总任务 7，成功 0，已完成 0，跳过 6，失败 1，耗时 ${r.durationMs}ms`);return;
  }
  let balance;
  const call=async (...args)=>{const d=await request(token,...args);identity(d,token);return d;};
  const stages=[
    ['早起打卡',process.env.FLY_ANT_EARLY_SIGN==='1',async()=>{await call('/active/pool/sign','POST',{active_id:'1'});return '早起打卡成功';}],
    ['每日签到',true,async()=>{await call('/sign/new/do');return '签到成功';}],
    ['连续签到天数',true,async()=>{const d=await call('/shop/get-sign-bean-task-nav','GET');return `连续签到 ${number(d.data?.sign_data?.continuaDays)} 天`;}],
    ['环保豆查询',true,async()=>{const a=await call('/user/new/beans/info','GET',{type:1});const b=await call('/user/new/beans/info','GET',{type:2});const received=number(a.data?.totalCount),used=number(b.data?.totalCount);balance=received-used;if(balance<0)throw new Error('环保豆统计不一致');return `已获取 ${received}，已使用 ${used}，剩余 ${balance}`;}],
    ['真实步数兑换',steps!=='',async()=>{const d=await call('/step/exchange','POST',{steps:Number(steps)});if(d.message!=='兑换成功')throw new Error('兑换结果未确认成功');return '步数兑换成功';}],
    ['抽奖',process.env.FLY_ANT_DRAW==='1',async()=>{if(balance===undefined)throw new Error('余额未验证，禁止抽奖');if(balance<10)return null;const d=await call('/active/turntable/go','POST',{active_id:'1'});if(typeof d.data?.prizeName!=='string')throw new Error('缺少抽奖结果');return `抽奖成功，奖品：${JSON.stringify(d.data.prizeName.replaceAll(token,'[已隐藏]'))}`;}],
    ['早起报名',process.env.FLY_ANT_BET==='1',async()=>{await call('/active/pool/bet','POST',{active_id:'1'});return '早起报名成功';}]
  ];
  for(let i=0;i<stages.length;i++) {
    const [name,enabled,fn]=stages[i],t=Date.now();log(`账号 ${index} 阶段 ${i+1}/7 ${name}`);
    try {
      if(!enabled){r.skipped++;log('⏭️ 未启用或未提供真实步数');}
      else if(dry){r.skipped++;log('⏭️ DRY_RUN 已校验请求计划，不发送请求');}
      else {const msg=await fn();if(msg===null){r.skipped++;log('⏭️ 环保豆不足 10，跳过抽奖');}else{r.success++;log(`✅ ${msg}`);}}
    }catch(e){r.failed++;log(`❌ ${e.message}`);}
    log(`账号 ${index} 阶段 ${i+1} 耗时 ${Date.now()-t}ms`);
  }
  r.durationMs=Date.now()-begin;
  log(`账号 ${index} 统计：总任务 ${r.total}，成功 ${r.success}，已完成 ${r.alreadyComplete}，跳过 ${r.skipped}，失败 ${r.failed}，耗时 ${r.durationMs}ms`);
}
function notify(body) {
  if(['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY||'1').toLowerCase()))return '已关闭';
  // 断网预演不能调用可能发起网络请求的通知模块。
  if(dry){log(`通知预演：${body}`);return '断网预演（未投递）';}
  const dirs=[process.env.QINGLONG_NOTIFY_DIR,'/ql/data/scripts','/ql/scripts'].filter(Boolean);
  for(const dir of dirs){const file=path.join(dir,'sendNotify.js');if(!fs.existsSync(file))continue;
    const child=spawnSync(process.execPath,['-e','Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exitCode=1)',file,TITLE,body],{stdio:'ignore',timeout:20000});
    if(child.status===0)return '已发送';
  }
  const code='import sys,importlib.util\np=sys.argv[1]\nif p:\n s=importlib.util.spec_from_file_location("notify",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nelse:\n import notify as m\nm.send(sys.argv[2],sys.argv[3])';
  for(const file of [...dirs.map(d=>path.join(d,'notify.py')).filter(f=>fs.existsSync(f)),'']) {
    const child=spawnSync('python3',['-c',code,file,TITLE,body],{stdio:'ignore',timeout:20000});
    if(child.status===0)return '已发送';
  }
  return '不可用或发送失败（保留业务退出码）';
}
(async()=>{
  const accounts=(process.env.FLY_ANT_TOKEN||'').split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  log(`========== ${TITLE} ==========`);log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'DRY_RUN':'正式'}；账号数：${accounts.length}`);
  let configError=!accounts.length;
  for(const key of ['FLY_ANT_DRY_RUN','FLY_ANT_DRAW','FLY_ANT_EARLY_SIGN','FLY_ANT_BET'])if(process.env[key]!==undefined&&!['0','1'].includes(process.env[key]))configError=true;
  if(configError)log('❌ 配置错误：请提供账号，并将任务开关设为 0 或 1');
  else for(let i=0;i<accounts.length;i++)await account(accounts[i],i+1);
  const failed=configError?accounts.length:results.filter(r=>r.failed>0).length;
  const success=results.filter(r=>r.failed===0).length;
  const exitCode=configError||failed?1:0;
  const status=configError?'configuration-error':failed?(success?'partial-failure':'failure'):(dry?'dry-run':'success');
  const body=`账号总数 ${accounts.length}，${dry?'预演通过':'成功'} ${success}，失败 ${failed}；状态 ${status}`;
  const notification=notify(body);
  const tasks=results.reduce((a,r)=>{for(const k of Object.keys(a))a[k]+=r[k];return a;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log('----------------------------------------');log(body);log(`子任务统计：${JSON.stringify(tasks)}`);log(`通知：${notification}`);
  log(`完成时间：${new Date().toISOString()}；总耗时：${Date.now()-started}ms；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:TITLE,mode:dry?'dry-run':'live',accounts:accounts.length,success,failed,configurationError:configError,status,tasks,results,notification,durationMs:Date.now()-started,exitCode}));
  process.exitCode=exitCode;
})().catch(()=>{log('❌ 内部执行异常');process.exitCode=1;});
