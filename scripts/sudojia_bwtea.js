// name: 霸王茶姬每日签到与积分提醒
// cron: 22 11 * * *
/**
 * name: 霸王茶姬
 * cron: 22 11 * * *
 * 来源 sudojia/AutoTaskScript，作者 Telegram@sudojia，https://blog.imzjw.cn
 * 原文件 src/wx_mini/sudojia_bwtea.js；许可证 GPL-3.0，维护修改沿用 GPL-3.0。
 * BW_TEA_TOKEN：在微信小程序登录时抓取本人
 * https://webapi2.qmai.cn/web/seller/oauth/flash-sale-login 的响应，
 * 将 token 与 user.id 按 token#id 合并；每个非空行一个账号，仅按首个 # 分割。
 * BW_TEA_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * 默认执行新版签到；上游已停用的旧版签到不恢复，避免重复修改状态。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const {spawn} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const dry = process.env.BW_TEA_DRY_RUN === '1';
const appid = 'wxafec6f8422cb357b', activityId = '1080523113114726401';
const start = Date.now();
const lines = (process.env.BW_TEA_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const results = [];
const stamp = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = s => console.log(`[${stamp()}] ${s}`);
function request(token, endpoint, method, body) {
  if (dry) throw new Error('预演禁止业务网络请求');
  return new Promise((resolve,reject) => {
    const url = new URL(endpoint, 'https://webapi2.qmai.cn');
    if (method === 'GET') url.searchParams.set('appid', appid);
    const payload = method === 'POST' ? JSON.stringify(body) : undefined;
    const req = https.request(url, {method, headers:{'content-type':'application/json', 'qm-from':'wechat', 'qm-user-token':token,
      'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a1b)XWEB/11097', ...(payload ? {'content-length':Buffer.byteLength(payload)} : {})}}, res => {
      let size=0; const chunks=[];
      res.on('data', chunk => {size+=chunk.length; if(size>262144) req.destroy(new Error('响应超限')); else chunks.push(chunk);});
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if(res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP ${res.statusCode}`));
        try {const data=JSON.parse(Buffer.concat(chunks).toString());
          if(data.status !== true) return reject(new Error('业务未明确成功（可能凭据失效或活动变化），请在小程序核对'));
          resolve(data.data);
        } catch {reject(new Error('响应格式异常'));}
      });
    });
    const timer=setTimeout(() => req.destroy(new Error('请求超时')),15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    req.end(payload);
  });
}
function signature(timestamp,uid) {
  const values={activityId,sellerId:'49006',timestamp,userId:uid};
  return crypto.createHash('md5').update(Object.keys(values).sort().map(k=>`${k}=${values[k]}`).join('&')+'&key='+activityId.split('').reverse().join('')).digest('hex');
}
function numeric(v) {return (typeof v==='number' || typeof v==='string' && v.trim()!=='') && Number.isFinite(Number(v)) && Number(v)>=0;}
async function account(line,index) {
  const r={account:index,total:4,success:0,alreadyComplete:0,skipped:0,failed:0};
  const began=Date.now(); let stage=0;
  results.push(r);
  async function step(label,fn) {
    stage++; const t=Date.now(); log(`账号 ${index} · ${stage}/4 ${label}`);
    if(dry) {r.skipped++;log(`⏭️ ${label}：预演，不发送请求；耗时 ${Date.now()-t}ms`);return;}
    try {const already=await fn(); if(already) r.alreadyComplete++;else r.success++;log(`${already?'☑️':'✅'} ${label}；耗时 ${Date.now()-t}ms`);}
    catch(e) {r.failed++;log(`❌ ${label}：${e.message}；耗时 ${Date.now()-t}ms`);throw e;}
  }
  try {
    const split=line.indexOf('#');
    if(split<=0 || !line.slice(split+1).trim() || /[\r\n\x00-\x1f\x7f]/.test(line)) throw new Error('账号格式错误：需要 token#id');
    const token=line.slice(0,split), uid=line.slice(split+1);
    const call=(p,m='POST',b={appid})=>request(token,p,m,b);
    await step('登录校验',()=>call('/web/catering2-apiserver/crm/customer-center','GET').then(()=>false));
    await step('账号身份',async()=>{
      const d=await call('/web/catering/crm/personal-info','GET');
      if(!d || typeof d.name!=='string') throw new Error('身份响应字段异常');
      // 不输出手机号、原始响应或凭据；官方昵称保持原值。
      if(d.name===token || d.name.includes(token) || /\d{11}/.test(d.name)) log('账号昵称含敏感信息，已抑制');
      else log(`账号 ${index} 昵称：${JSON.stringify(d.name)}`);
    });
    await step('新版每日签到',async()=>{
      const body={activityId,appid};
      const d=await call('/web/cmk-center/sign/userSignStatistics','POST',body);
      if(!d || ![0,1].includes(d.signStatus) || !numeric(d.signDays)) throw new Error('签到状态字段异常');
      log(`连续签到 ${Number(d.signDays)} 天`);
      if(d.signStatus===1) return true;
      const timestamp=Date.now();
      await call('/web/cmk-center/sign/takePartInSign','POST',{...body,storeId:49006,store_id:49006,timestamp,signature:signature(timestamp,uid)});
      const checked=await call('/web/cmk-center/sign/userSignStatistics','POST',body);
      if(!checked || checked.signStatus!==1) throw new Error('签到后状态未确认，不自动重试写入');
      log('新版-签到成功');
    });
    await step('积分及到期提醒',async()=>{
      const d=await call('/web/catering/crm/points-info');
      if(!d || !numeric(d.totalPoints) || !numeric(d.soonExpiredPoints)) throw new Error('积分字段异常');
      log(`当前积分：${Number(d.totalPoints)}`);
      if(Number(d.soonExpiredPoints)>0) {
        if(typeof d.expiredTime!=='string' || !/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?$/.test(d.expiredTime)) throw new Error('积分到期时间字段异常');
        log(`${Number(d.soonExpiredPoints)} 积分将在 ${d.expiredTime} 失效`);
      } else log('暂无过期积分');
    });
  } catch(e) {
    if(!r.failed) {r.failed++;log(`❌ 账号 ${index}：${e.message}`);}
    r.skipped=r.total-r.success-r.alreadyComplete-r.failed;
  }
  r.durationMs=Date.now()-began;
  log(`账号 ${index} 统计：总任务 ${r.total}，成功 ${r.success}，已完成 ${r.alreadyComplete}，跳过 ${r.skipped}，失败 ${r.failed}，耗时 ${r.durationMs}ms`);
}
async function notify(body) {
  if(['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY||'1').toLowerCase())) return '已关闭';
  const candidates=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=candidates.find(f=>fs.existsSync(f));
  if(!file) return '通知不可用：未找到 sendNotify.js';
  // 预演仍尝试调用通知入口，但封锁传输和子进程，保证完全断网。
  const code=`if(process.env.BW_TEA_DRY_RUN==='1'){const deny=()=>{throw Error('dry-run network disabled')};for(const n of ['http','https']){const m=require(n);m.request=deny;m.get=deny;}require('net').Socket.prototype.connect=deny;require('tls').connect=deny;global.fetch=deny;const cp=require('child_process');for(const k of ['spawn','exec','execFile','fork','spawnSync','execSync','execFileSync'])cp[k]=deny;} Promise.resolve().then(()=>require(process.argv[1]).sendNotify('霸王茶姬',process.argv[2])).then(()=>process.exit(0),()=>process.exit(1));`;
  return new Promise(resolve=>{
    const child=spawn(process.execPath,['-e',code,file,body],{stdio:'ignore',env:{...process.env}});
    const timer=setTimeout(()=>{child.kill('SIGKILL');},20000);
    child.on('error',()=>{clearTimeout(timer);resolve('通知失败：入口无法运行');});
    child.on('close',c=>{clearTimeout(timer);resolve(c===0?'通知入口已完成':dry?'预演通知传输已阻止':'通知失败');});
  });
}
async function main() {
  log('========== 霸王茶姬 ==========');log(`开始时间：${new Date(start).toISOString()}；模式：${dry?'断网预演':'正式运行'}；账号数：${lines.length}`);
  if(!lines.length) log('❌ 配置错误：请设置 BW_TEA_TOKEN，每行 token#id');
  for(let i=0;i<lines.length;i++) await account(lines[i],i+1);
  const failed=results.filter(r=>r.failed>0).length;
  const status=!lines.length?'configuration-error':failed?(failed===lines.length?'failure':'partial-failure'):dry?'dry-run':'success';
  process.exitCode=(!lines.length || failed)?1:0;
  const totals=results.reduce((a,r)=>{for(const k of Object.keys(a)) a[k]+=r[k];return a;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  const body=`模式：${dry?'断网预演':'正式运行'}；账号总数 ${lines.length}，成功 ${dry?0:lines.length-failed}，失败 ${failed}；状态 ${status}；子任务 ${JSON.stringify(totals)}`;
  const notification=await notify(body);
  log('--------------------------------');log(body);log(`通知状态：${notification}`);
  const finish=new Date().toISOString();log(`完成时间：${finish}；总耗时 ${Date.now()-start}ms；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:'霸王茶姬',mode:dry?'dry-run':'live',status,accounts:lines.length,success:dry?0:lines.length-failed,failed,totals,results,notification,finish,durationMs:Date.now()-start}));
}
main().catch(()=>{process.exitCode=1;log('❌ 任务内部异常');});
