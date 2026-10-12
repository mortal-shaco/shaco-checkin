// name: 星妈优选
// cron: 39 2 * * *
/**
 * name: 星妈优选
 * cron: 39 2 * * *
 * 原作者：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_starMom.js
 * SPDX-License-Identifier: GPL-3.0-only
 * STAR_MOM_TOKEN：打开微信小程序「星妈优选」，在本人授权的抓包工具中
 * 查找 https://www.feihevip.com 请求头 token；每行一个账号。令牌时效很短。
 * STAR_MOM_DRY_RUN=1：完全断网预演，通知仅生成摘要，不进行外部投递。
 * QINGLONG_NOTIFY=0 可关闭通知；QINGLONG_NOTIFY_DIR 指定青龙通知模块目录。
 * 移除自动补签、购买、抽奖、开启提醒任务；不自动刷新令牌。
 * Node.js >=18，无第三方业务依赖。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const dry = process.env.STAR_MOM_DRY_RUN === '1';
const tasks = [['浏览主会场','LLZTY',3],['浏览热销爆品1','TZSPXQ2',3],['查看我的优惠券','LLYHJ',3],['浏览视频10s','LLSP',11],['浏览粮油专场10s','XXGG',11]];
const accounts = (process.env.STAR_MOM_TOKEN || '').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
const started = Date.now();
const totals = {total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
function log(s) { console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`); }
function safeIdentity(value) {
  let s = String(value);
  for (const token of accounts) s = s.split(token).join('[凭据已隐藏]');
  return s.replace(/[\r\n\u0000-\u001f\u007f]/g,' ');
}
function signature() {
  const alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
  const nonce=Array.from({length:16},()=>alphabet[crypto.randomInt(alphabet.length)]).join('');
  const timestamp=Math.floor(Date.now()/1000);
  return {fhNonceStr:nonce,fhTimestamp:String(timestamp),fhSign:crypto.createHash('md5').update(`fhAppidxmyxfhNonceStr${nonce}fhTimestamp${timestamp}{}TwUQ01lKS1Km5zlV2f7amsZc5EQYkTbv`).digest('hex').toUpperCase()};
}
function request(token, endpoint, method='GET') {
  if(dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve,reject)=>{
    const req=https.request(new URL(endpoint,'https://www.feihevip.com'), {method,headers:{
      'User-Agent':'Mozilla/5.0 MicroMessenger/8.0.48','Content-Type':'application/json',
      Referer:'https://servicewechat.com/wx4205ec55b793245e/271/page-frame.html',
      fhAppid:'xmyx',source:'1',token,...signature()
    }},res=>{
      let size=0; const chunks=[];
      res.on('data',c=>{size+=c.length;if(size>1048576)req.destroy(new Error('响应超出限制'));else chunks.push(c);});
      res.on('error',()=>reject(new Error('响应读取失败')));
      res.on('end',()=>{
        if(res.statusCode!==200)return reject(new Error('HTTP 状态异常'));
        try {const data=JSON.parse(Buffer.concat(chunks).toString());
          if(String(data.code)!=='200')return reject(new Error('业务未成功（请检查令牌或任务状态）'));
          resolve(data.data);
        } catch {reject(new Error('响应格式异常'));}
      });
    });
    const timer=setTimeout(()=>req.destroy(new Error('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',()=>reject(new Error('网络请求失败或超时')));
    req.end();
  });
}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
function number(x) {return (typeof x==='number'||typeof x==='string') && String(x).trim()!=='' && Number.isFinite(Number(x)) && Number(x)>=0;}
async function notify(body) {
  if(/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY||'1'))return '已关闭';
  if(dry)return '预演已生成通知摘要，断网模式不投递';
  const candidates=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const modulePath=candidates.find(p=>fs.existsSync(p));
  if(!modulePath)return '通知模块不可用（业务退出码保留）';
  return new Promise(resolve=>{
    const child=spawn(process.execPath,['-e',"Promise.resolve().then(()=>require(process.argv[1]).sendNotify('星妈优选',process.argv[2])).then(()=>process.exit(0)).catch(()=>process.exit(1))",modulePath,body],{stdio:'ignore'});
    const timer=setTimeout(()=>{child.kill('SIGKILL');resolve('通知超时');},15000);
    child.on('error',()=>{clearTimeout(timer);resolve('通知失败');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':'通知失败');});
  });
}
async function main() {
  console.log('========== 星妈优选 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${accounts.length}`);
  let passed=0,failed=0;
  const configError=!accounts.length;
  if(configError)log('❌ 配置错误：请设置 STAR_MOM_TOKEN，每行一个账号');
  for(let i=0;i<accounts.length;i++){
    const began=Date.now(); const stats={total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
    let stage=0;
    async function step(name,action){
      const t=Date.now();stats.total++;stage++;
      log(`账号 ${i+1} 阶段 ${stage}：${name}`);
      try {
        if(dry){stats.skipped++;log(`⏭️ 预演：${name}，未发送请求；耗时 ${Date.now()-t}ms`);return;}
        const result=await action();
        if(result.already)stats.alreadyComplete++;else stats.success++;
        log(`${result.already?'☑️':'✅'} ${result.text}；耗时 ${Date.now()-t}ms`);
      }catch(e){stats.failed++;log(`❌ ${name}：${e.message}；耗时 ${Date.now()-t}ms`);}
    }
    const token=accounts[i];
    await step('每日签到',async()=>{
      const d=await request(token,'/api/member/signin/getSignInfo?signType=1');
      if(!d||!Array.isArray(d.signPop)||!d.signPop.length||!number(d.signPop[0].signPoint))throw new Error('签到响应不足以验证成功或已签到');
      const p=Number(d.signPop[0].signPoint);
      return {already:p===0,text:p===0?'今日已签到':'签到成功，积分+'+p};
    });
    for(const [name,type,seconds] of tasks)await step(name,async()=>{
      await request(token,`/api/member/signin/tofinish?taskType=${type}`);
      log(`账号 ${i+1}：任务开始已确认，等待 ${seconds} 秒`);
      await wait(seconds*1000);
      const d=await request(token,`/api/member/signin/completeTask?taskType=${type}`);
      if(!d||!number(d.awardSendPoints))throw new Error('积分奖励字段异常，无法确认完成');
      return {text:`${name}完成，积分+${Number(d.awardSendPoints)}`};
    });
    await step('查询账号和积分',async()=>{
      const d=await request(token,'/api/starMember/getMemberInfo','POST');
      if(!d||!d.baseInfo||typeof d.baseInfo.nickName!=='string'||!number(d.memberPoints?.scoreValue)||!['string','number'].includes(typeof d.memberGrade?.currentGrade))throw new Error('账号资料响应字段异常');
      return {text:`昵称：${safeIdentity(d.baseInfo.nickName)}；等级：${safeIdentity(d.memberGrade.currentGrade)}；积分：${Number(d.memberPoints.scoreValue)}`};
    });
    for(const k of Object.keys(totals))totals[k]+=stats[k];
    if(stats.failed)failed++;else passed++;
    log(`账号 ${i+1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now()-began}ms`);
  }
  const exitCode=configError||failed?1:0;
  const status=configError?'configuration-error':failed?(passed?'partial-failure':'failure'):dry?'dry-run':'success';
  const body=`账号总数 ${accounts.length}，${dry?'预演通过':'成功'} ${passed}，失败 ${failed}；状态 ${status}；子任务成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`;
  const notification=await notify(body);
  console.log('--------------------------------');log(body);log(`通知：${notification}`);
  const finish=new Date().toISOString();
  log(`完成时间：${finish}；总耗时 ${Date.now()-started}ms；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:'星妈优选',mode:dry?'dry-run':'live',status,accounts:accounts.length,success:dry?0:passed,dryRunPassed:dry?passed:0,failed,configurationError:configError,steps:totals,notification,finishTime:finish,elapsedMs:Date.now()-started,exitCode}));
  process.exitCode=exitCode;
}
main();
