// name: 南方航空
// cron: 49 11 * * *
/**
 * name: 南方航空
 * cron: 49 11 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_nfhk.js
 * NFHK_COOKIE：已实名认证账号，在南方航空小程序抓取
 * https://wxapi.csair.com/marketing-tools/ 请求 Cookie 中 sign_user_token 的值。
 * 不含字段名；每个非空行一个账号。NFHK_DRY_RUN=1 完全断网预演。
 * Node.js >=18；无需第三方依赖。通知使用青龙 sendNotify.js。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const dry = process.env.NFHK_DRY_RUN === '1';
const accounts = (process.env.NFHK_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const started = Date.now();
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const results = [];
const log = s => console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${s}`);
function safe(value) {
  let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const credential of accounts) s = s.split(credential).join('[凭据已隐藏]');
  return s.replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, '[手机号已隐藏]');
}
function request(token, method, endpoint, body) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (err, data) => { if(done) return; done=true; clearTimeout(timer); err ? reject(err) : resolve(data); };
    const req = https.request('https://wxapi.csair.com' + endpoint, {method, headers: {
      'User-Agent':'okhttp/3.12.1;jdmall;android;version/10.3.4;build/92451;',
      'Content-Type':'application/json',
      Cookie:`sign_user_token=${token}; TOKEN=${token}; cs1246643sso=${token}`
    }}, res => {
      let size=0; const chunks=[];
      res.on('data', chunk => {size+=chunk.length; if(size>1048576) {finish(new Error('响应超过大小限制')); res.destroy(); req.destroy();} else chunks.push(chunk);});
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('end', () => {
        if(res.statusCode<200 || res.statusCode>=300) return finish(new Error(`HTTP 请求失败（${res.statusCode}）`));
        try { const data=JSON.parse(Buffer.concat(chunks).toString('utf8')); if(!data || typeof data!=='object') throw new Error(); finish(null,data); }
        catch {finish(new Error('响应不是有效 JSON 对象'));}
      });
    });
    const timer=setTimeout(() => {finish(new Error('请求超时')); req.destroy();},15000);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(body);
  });
}
function identify(data) {
  for (const obj of [data, data.data]) {
    if(!obj || typeof obj!=='object') continue;
    for(const key of ['nickname','nickName','username','userName','displayName','publicUid']) {
      if(typeof obj[key]==='string' || typeof obj[key]==='number') log(`账号身份 ${key}：${safe(obj[key])}`);
    }
  }
}
function monthRange() {
  const parts = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit'}).formatToParts(new Date());
  const y=Number(parts.find(p=>p.type==='year').value), m=Number(parts.find(p=>p.type==='month').value);
  const prefix=`${y}-${String(m).padStart(2,'0')}`;
  return [prefix+'-01',prefix+'-'+new Date(Date.UTC(y,m,0)).getUTCDate()];
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  const files=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=files.find(f=>fs.existsSync(f));
  if(!file) return '不可用：未发现 sendNotify.js（业务退出码保留）';
  // 通知隔离执行；预演禁止通知模块建立网络连接或启动外部进程。
  const code=`if(process.env.NFHK_DRY_RUN==='1') { const deny=()=>{throw Error('dry-run network disabled')}; for(const name of ['http','https']) {const m=require(name);m.request=deny;m.get=deny;} const net=require('net');net.connect=deny;net.createConnection=deny;net.Socket.prototype.connect=deny;require('tls').connect=deny;global.fetch=deny;const cp=require('child_process');for(const k of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork'])cp[k]=deny; } Promise.resolve().then(()=>require(process.argv[1]).sendNotify('南方航空',process.argv[2])).then(()=>process.exit(0),()=>process.exit(1));`;
  return new Promise(resolve=>{
    const env={...process.env}; delete env.NFHK_COOKIE;
    const child=spawn(process.execPath,['-e',code,file,body],{env,stdio:'ignore'});
    const timer=setTimeout(()=>{child.kill('SIGKILL');},10000);
    child.on('error',()=>{clearTimeout(timer);resolve('投递失败（业务退出码保留）');});
    child.on('close',c=>{clearTimeout(timer);resolve(c===0?'已发送':dry?'预演通知已尝试，网络投递已阻止':'投递失败（业务退出码保留）');});
  });
}
async function main() {
  log('========== 南方航空 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式运行'}；账号数：${accounts.length}`);
  let configError=false;
  if(!accounts.length) {configError=true;log('❌ 配置错误：NFHK_COOKIE 未配置');}
  for(let i=0;i<accounts.length;i++) {
    const began=Date.now(), stats={total:3,success:0,alreadyComplete:0,skipped:0,failed:0};
    const token=accounts[i]; log(`账号 ${i+1} 开始`);
    if((token.startsWith('sign_user_token=') || /[\s;&@\x00-\x1f\x7f]/.test(token)) || /[^\x21-\x7e]/.test(token)) {
      configError=true;stats.failed=3;log('❌ 配置错误：仅填写 token 值，每行一个账号，不支持旧账号分隔符');
    } else {
      const [first,last]=monthRange();
      const stages=[
        ['签到','POST','/marketing-tools/activity/join?type=APPTYPE&chanel=ss&lang=zh',JSON.stringify({activityType:'sign',channel:'app',entrance:1})],
        ['当月签到进度','GET',`/marketing-tools/sign/getSignCalendar?type=APPTYPE&chanel=ss&lang=zh&startQueryDate=${first}&endQueryDate=${last}`],
        ['可用里程','POST','/marketing-tools/sign/minPriceMileage','type=APPTYPE&chanel=ss&lang=zh']
      ];
      for(let n=0;n<stages.length;n++) {
        const [label,method,url,body]=stages[n], t=Date.now(); log(`账号 ${i+1} 阶段 ${n+1}/3：${label}`);
        try {
          if(dry) {stats.skipped++;log(`⏭️ ${label}：预演校验通过，未发请求`);continue;}
          const data=await request(token,method,url,body); identify(data);
          if(n===0 && data.respCode==='S2001') {stats.alreadyComplete++;log('☑️ 今日已签到');continue;}
          if(data.respCode !== (n===0?'000':'0000')) throw new Error('业务成功码未通过，检查登录状态或接口契约');
          if(n===1) {
            if(!Array.isArray(data.data?.signProgressMsg) || !data.data.signProgressMsg.every(x=>typeof x==='string')) throw new Error('签到进度字段无效');
            log(`签到进度：${safe(data.data.signProgressMsg.join(''))}`);
          }
          if(n===2) {
            const mileage=data.data?.availableMileage;
            if(!['string','number'].includes(typeof mileage) || !/^\d+(?:\.\d+)?$/.test(String(mileage))) throw new Error('可用里程字段无效');
            log(`当前里程：${mileage}`);
          }
          stats.success++;log(`✅ ${label}成功`);
        } catch(e) {stats.failed++;log(`❌ ${label}失败：${e.message}`);}
        finally {log(`阶段 ${n+1} 耗时：${Date.now()-t} 毫秒`);}
      }
    }
    for(const k of Object.keys(totals)) totals[k]+=stats[k];
    results.push({account:i+1,...stats,elapsedMs:Date.now()-began});
    log(`账号 ${i+1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now()-began} 毫秒`);
  }
  const failed=results.filter(x=>x.failed>0).length, success=results.length-failed;
  const status=configError?'configuration-error':failed?(success?'partial-failure':'failure'):dry?'dry-run':'success';
  process.exitCode=configError || failed ? 1 : 0;
  const body=`模式：${dry?'断网预演':'正式运行'}；账号总数 ${accounts.length}，${dry?'预演通过':'成功'} ${success}，失败 ${failed}；任务成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}；状态 ${status}`;
  const notification=await notify(body).catch(()=>'投递失败（业务退出码保留）');
  log('--------------------------------');log(body);log(`通知：${notification}`);
  const finishedAt=new Date().toISOString();log(`完成时间：${finishedAt}；总耗时 ${Date.now()-started} 毫秒；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:'南方航空',mode:dry?'dry-run':'live',status,accounts:accounts.length,success,failed,stages:totals,results,notification,finishedAt,elapsedMs:Date.now()-started}));
}
main().catch(()=>{log('❌ 未预期的内部错误');process.exitCode=1;});
