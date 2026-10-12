// name: 新湖南每日签到
// cron: 51 4 * * *
/**
 * name: 新湖南每日签到
 * cron: 51 4 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/client/sudojia_xhn.js
 * 独立维护版本，保留原登录签名、签到和积分查询协议。
 * Node.js >= 18，无第三方依赖。
 * 真机注册并在本人登录前开启抓包，复制
 * https://xhnapi2.voc.com.cn/v5/user/login 的完整表单请求体至 XHN_ACCOUNTS。
 * 每个非空行一个账号；保留 URL 编码及全部字段，不能用 & 或 @ 分隔账号。
 * XHN_DRY_RUN=1 完全断网预演（通知仅输出脱敏预演摘要）。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const path = require('node:path');
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const dry = process.env.XHN_DRY_RUN === '1';
const start = Date.now();
const lines = (process.env.XHN_ACCOUNTS || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const stats = {total:0, success:0, alreadyComplete:0, skipped:0, failed:0};
const summary = {task:'新湖南每日签到', mode:dry?'dry-run':'live', accounts:lines.length, success:0, failed:0, tasks:stats};
function log(s) {console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`);}
function request(url, method, headers, body) {
  if (dry) throw new Error('预演禁止网络');
  return new Promise((resolve,reject) => {
    let done=false;
    const finish=(err,value)=>{if(done)return;done=true;clearTimeout(timer);err?reject(err):resolve(value);};
    const req=https.request(url,{method,headers:{...headers,'Accept-Encoding':'identity',...(body?{'Content-Type':'application/x-www-form-urlencoded','Content-Length':Buffer.byteLength(body)}:{})}},res=>{
      const chunks=[];let size=0;
      res.on('data',chunk=>{size+=chunk.length;if(size>1048576){finish(new Error('响应过大'));res.destroy();req.destroy();}else chunks.push(chunk);});
      res.on('error',()=>finish(new Error('响应读取失败')));
      res.on('end',()=>{if(res.statusCode<200||res.statusCode>=300)return finish(new Error('HTTP 请求失败'));try{const value=JSON.parse(Buffer.concat(chunks).toString());if(!value||typeof value!=='object')throw Error();finish(null,value);}catch{finish(new Error('响应格式错误'));}});
    });
    const timer=setTimeout(()=>{finish(new Error('请求超时'));req.destroy();},15000);
    req.on('error',()=>finish(new Error('网络请求失败')));
    req.end(body);
  });
}
function signed(nonce) {
  const time=String(Date.now());
  return {'User-Agent':'xhn-11.0.3-Mozilla/5.0 (Linux; Android 9; V1916A Build/PQ3B.190801.06131105; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36',referer:'https://usergrow-xhncloud.voc.com.cn/points/web/',time,nonce,signature:crypto.createHash('sha1').update(`${time}${nonce}hHacFKN5DxR5sPwyc1ns52M168rdoe3AGrWaseN3zYd2XoKaxYhYQTqDXvCtMkwz`).digest('hex')};
}
function identity(data, secrets) {
  if(!data||typeof data!=='object')return;
  for(const key of ['nickname','nickName','displayName','username','uid']) {
    const v=data[key]; if(typeof v!=='string'&&typeof v!=='number')continue;
    const s=String(v);
    if(!s||/[\r\n\x00-\x1f]/.test(s)||/\+?\d[\d -]{9,}\d/.test(s)||secrets.some(x=>x&&s.includes(x)))continue;
    log(`账号身份 ${key}：${s}`);
  }
}
async function account(body,index) {
  const began=Date.now(), local={total:3,success:0,alreadyComplete:0,skipped:0,failed:0};
  let token, valid=true;
  const form=new URLSearchParams(body);
  const secrets=['password','RegistrationID'].map(k=>form.get(k));
  for(const [n,title,action] of [
    [1,'登录',async()=>{
      if(!['password','username','logintype','RegistrationID','appid','type'].every(k=>form.get(k)))throw new Error('登录表单缺少必需字段，请重新抓取完整请求体');
      if(dry)return;
      const device=crypto.randomBytes(20).toString('hex').toUpperCase(),timestamp=String(Date.now());
      const data=await request('https://xhnapi2.voc.com.cn/v5/user/login','POST',{'User-Agent':'xhn/11.0.3 (vivo/V1916A; android/28; okhttp/4.12.0)',os:'android','rmt-device-id':device,appversion:'11.0.3','rmt-device-type':'android','rmt-build':'1100302','rmt-app-version':'11.0.3','rmt-app-id':'9','rmt-hash':crypto.createHash('md5').update(`C50GIK6GDhQNjtMRVRoQbwxVovXCX8DUv5android${device}${timestamp}`).digest('hex'),'rmt-request-time':timestamp},body);
      if(data.state_code!==1||typeof data.data?.auth!=='string'||!data.data.auth.trim())throw new Error('登录业务失败或缺少授权令牌');
      token=data.data.auth;secrets.push(token);identity(data.data,secrets);
    }],
    [2,'每日签到',async()=>{
      if(dry)return;
      const data=await request('https://usergrow-xhncloud.voc.com.cn/usergrow/api/v2/points/','POST',signed('300000'),new URLSearchParams({points_rule_id:'8',appid:'9',oauth_token:token}).toString());
      if(data.statecode!==1)throw new Error('签到业务失败');
    }],
    [3,'查询积分',async()=>{
      if(dry)return;
      const query=new URLSearchParams({refreshUserInfo:'0',appid:'9',oauth_token:token});
      const data=await request(`https://usergrow-xhncloud.voc.com.cn/usergrow/api/v2/points/pointsUser?${query}`,'GET',signed('700000'));
      if(data.statecode!==1||!['string','number'].includes(typeof data.data?.validPoints)||!/^\d+(\.\d+)?$/.test(String(data.data.validPoints)))throw new Error('积分业务失败或缺少有效积分');
      identity(data.data,secrets);log(`当前积分：${data.data.validPoints}`);
    }]
  ]) {
    const t=Date.now(); log(`账号 ${index} · 阶段 ${n}/3 ${title}`);
    if(!valid){local.skipped++;log(`⏭️ 登录失败，跳过后续步骤；阶段耗时 ${Date.now()-t} 毫秒`);continue;}
    try {await action();if(dry){local.skipped++;log(`⏭️ 预演检查通过，不发送${title}请求`);}else{local.success++;log(`✅ ${title}成功`);}}
    catch(e){local.failed++;log(`❌ ${e.message}`);if(n===1)valid=false;}
    log(`阶段耗时 ${Date.now()-t} 毫秒`);
    if(!dry&&n===2)await new Promise(r=>setTimeout(r,2000+crypto.randomInt(501)));
  }
  for(const k of Object.keys(stats))stats[k]+=local[k];
  summary[local.failed?'failed':'success']++;
  log(`账号 ${index} 统计：总任务 ${local.total}，成功 ${local.success}，已完成 ${local.alreadyComplete}，跳过 ${local.skipped}，失败 ${local.failed}；耗时 ${Date.now()-began} 毫秒`);
}
async function notify(text) {
  if(/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY||'1'))return '已关闭';
  if(dry){log(`通知预演（不联网）：${text}`);return '断网预演';}
  const dirs=[process.env.QINGLONG_NOTIFY_DIR,'/ql/data/scripts','/ql/scripts'].filter(Boolean);
  const file=dirs.map(d=>path.join(d,'sendNotify.js')).find(f=>fs.existsSync(f));
  if(!file)return '不可用：未找到 sendNotify.js';
  return new Promise(resolve=>{
    const child=spawn(process.execPath,['-e','Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))',file,'新湖南每日签到',text],{stdio:'ignore'});
    const timer=setTimeout(()=>{child.kill('SIGKILL');resolve('通知超时');},15000);
    child.on('error',()=>{clearTimeout(timer);resolve('通知失败');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':'通知失败');});
  });
}
(async()=>{
  log('========== 新湖南每日签到 ==========');
  log(`开始时间：${new Date(start).toISOString()}；模式：${summary.mode}；账号数：${lines.length}`);
  let configError=!lines.length;
  if(configError)log('❌ 配置错误：XHN_ACCOUNTS 未设置有效账号');
  for(let i=0;i<lines.length;i++)await account(lines[i],i+1);
  summary.status=configError?'configuration-error':summary.failed?(summary.success?'partial-failure':'failure'):(dry?'dry-run':'success');
  process.exitCode=configError||summary.failed?1:0;
  const body=`状态：${summary.status}；账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；子任务成功 ${stats.success}，跳过 ${stats.skipped}，失败 ${stats.failed}`;
  try{summary.notification=await notify(body);}catch{summary.notification='通知失败';}
  summary.durationMs=Date.now()-start;summary.finishTime=new Date().toISOString();
  log('----------------------------------------');log(body);
  log(`总耗时 ${summary.durationMs} 毫秒；完成时间 ${summary.finishTime}；通知状态：${summary.notification}；最终状态：${summary.status}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
})().catch(()=>{process.exitCode=1;log('❌ 未预期的本地运行错误');});
