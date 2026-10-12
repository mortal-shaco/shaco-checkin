// name: 爷爷不泡茶
// cron: 30 9 * * *
/**
 * name: 爷爷不泡茶
 * cron: 30 9 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_paotea.js
 * 每行一个 PAO_TEA_TOKEN：Token#活动ID；仅在第一个 # 分隔。
 * 微信小程序「爷爷不泡茶」登录后，在自己的授权抓包中查看 webapi.qmai.cn：
 * qm-user-token 请求头及 sign/userSignStatistics 请求体 activityId。
 * PAO_TEA_DRY_RUN=1 完全断网预演；Node.js >=18，无第三方业务依赖。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const dry = process.env.PAO_TEA_DRY_RUN === '1';
const appid = 'wx3423ef0c7b7f19af';
const started = Date.now();
const rows = (process.env.PAO_TEA_TOKEN || '').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
const secrets = rows.flatMap(x=>[x,x.split('#')[0]]).filter(Boolean);
const results = [];
function safe(v) {
  let s = String(v).replace(/[\r\n\x00-\x1f]/g,' ');
  for (const secret of secrets) s = s.split(secret).join('[凭据已隐藏]');
  return s.replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g,'[手机号已隐藏]');
}
function log(s) { console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`); }
function request(token, endpoint, body) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve,reject)=>{
    const payload = body ? JSON.stringify(body) : null;
    const req = https.request(new URL(endpoint,'https://webapi.qmai.cn'), {
      method: payload ? 'POST':'GET', headers: {
        'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a1b)XWEB/11097',
        'Content-Type':'application/json','store-id':'216652','qm-from':'wechat','scene':'1145',
        referer:`https://servicewechat.com/${appid}/49/page-frame.html`, 'qm-user-token':token,
        ...(payload ? {'Content-Length':Buffer.byteLength(payload)} : {})
      }
    },res=>{
      let chunks=[], size=0;
      res.on('data',c=>{ size+=c.length; if(size>1048576) req.destroy(new Error('响应超过大小限制')); else chunks.push(c); });
      res.on('error',()=>reject(new Error('响应读取失败')));
      res.on('end',()=>{
        if(res.statusCode<200 || res.statusCode>=300) return reject(new Error(`HTTP ${res.statusCode}`));
        try { const d=JSON.parse(Buffer.concat(chunks).toString());
          if(d.status!==true) return reject(new Error('业务未明确成功，请核对凭据和活动ID'));
          resolve(d.data);
        } catch { reject(new Error('响应格式无效')); }
      });
    });
    const timer=setTimeout(()=>req.destroy(new Error('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',()=>reject(new Error('网络请求失败或超时')));
    req.end(payload);
  });
}
function numeric(x) { return (typeof x==='number'||typeof x==='string') && String(x).trim()!=='' && Number.isFinite(Number(x)) && Number(x)>=0; }
async function account(row,index) {
  const r={account:index,total:4,success:0,alreadyComplete:0,skipped:0,failed:0};
  const begin=Date.now(); const split=row.indexOf('#');
  const token=row.slice(0,split), activityId=row.slice(split+1);
  const valid=split>0 && /^\d+$/.test(activityId) && !/[\s&]/.test(token);
  let login=false;
  const steps=[
    ['登录校验',async()=>{ const d=await request(token,`/web/catering2-apiserver/crm/customer-center?appid=${appid}`);
      login=true;
      for(const k of ['nickname','nickName','username','displayName','uid']) if(d && (typeof d[k]==='string' || typeof d[k]==='number')) log(`账号 ${index} ${k}：${safe(d[k])}`);
      return '登录校验成功'; }],
    ['每日签到',async()=>{const body={activityId,appid};
      const d=await request(token,'/web/cmk-center/sign/userSignStatistics',body);
      if(d?.signStatus===1) {r.alreadyComplete++;return '今天已经签到过了';}
      if(d?.signStatus!==0) throw new Error('签到状态未知，停止写入');
      await request(token,'/web/cmk-center/sign/takePartInSign',{activityId,storeId:216652,timestamp:Date.now(),appid});
      const verified=await request(token,'/web/cmk-center/sign/userSignStatistics',body);
      if(verified?.signStatus!==1) throw new Error('签到后状态未确认');
      return '签到成功（已复核）';}],
    ['连续签到及阶段奖励',async()=>{const d=await request(token,'/web/cmk-center/sign/userSignStatistics',{activityId,appid});
      if(!d || !numeric(d.signDays) || !Array.isArray(d.rewardList)) throw new Error('签到统计字段无效');
      log(`已连续签到[${d.signDays}]天`);
      if(d.rewardList.some(x=>!x || !numeric(x.signNum))) throw new Error('奖励阶段字段无效');
      const next=d.rewardList.find(x=>Number(x.signNum)>Number(d.signDays));
      if(next) { const name=next.rewardList?.[0]?.rewardName; if(typeof name!=='string') throw new Error('奖励名称缺失');
        return `下一阶段奖励[${safe(name)}]还需签到[${Number(next.signNum)-Number(d.signDays)}]天`; }
      return '已达到所有签到奖励阶段！';}],
    ['积分及到期提醒',async()=>{const d=await request(token,'/web/catering/crm/points-info',{appid});
      if(!d || !numeric(d.totalPoints) || !numeric(d.soonExpiredPoints)) throw new Error('积分字段无效');
      log(`当前积分：${d.totalPoints}`);
      if(Number(d.soonExpiredPoints)>0) {if(typeof d.expiredTime!=='string' && typeof d.expiredTime!=='number') throw new Error('积分到期时间缺失');
        return `${d.soonExpiredPoints}积分将在${safe(d.expiredTime)}失效`;}
      return '暂无过期积分';}]
  ];
  for(let i=0;i<steps.length;i++) {
    const start=Date.now(); log(`账号 ${index} 阶段 ${i+1}/4：${steps[i][0]}`);
    if(i>0 && !login && !dry) {r.skipped++;log(`⏭️ 登录未通过，跳过；阶段耗时 ${Date.now()-start}ms`);continue;}
    try {
      if(!valid) throw new Error('配置错误：每行必须为 Token#数字活动ID，不支持 & 分隔账号');
      if(dry) {r.skipped++;log('⏭️ 预演：参数有效，不发送请求、不执行签到');}
      else {const before=r.alreadyComplete; const message=await steps[i][1]();if(before===r.alreadyComplete)r.success++;log(`✅ ${message}`);}
    } catch(e) {r.failed++;log(`❌ ${e.message}`);}
    log(`阶段耗时 ${Date.now()-start}ms`);
  }
  r.ok=r.failed===0; r.durationMs=Date.now()-begin; results.push(r);
  log(`账号 ${index} 统计：总任务 ${r.total}，成功 ${r.success}，已完成 ${r.alreadyComplete}，跳过 ${r.skipped}，失败 ${r.failed}，耗时 ${r.durationMs}ms`);
}
async function notify(body) {
  if(['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY||'1').toLowerCase())) return '已关闭';
  const locations=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=locations.find(x=>fs.existsSync(x));
  if(!file) return '通知不可用：未找到 sendNotify.js';
  // 在独立进程中调用青龙通知；预演关闭所有网络能力，仍尝试通知接口。
  const code=`if(process.env.PAO_TEA_DRY_RUN==='1'){for(const m of ['node:http','node:https','node:net','node:tls','node:dgram','node:child_process']){const o=require(m);for(const k of Object.keys(o))if(typeof o[k]==='function')o[k]=()=>{throw Error('dry-run')}}global.fetch=()=>Promise.reject(Error('dry-run'));} Promise.resolve().then(()=>require(process.argv[1]).sendNotify('爷爷不泡茶',process.argv[2])).then(()=>process.exit(0),()=>process.exit(1));`;
  return new Promise(resolve=>{const child=spawn(process.execPath,['-e',code,file,body],{stdio:'ignore',env:{...process.env,PAO_TEA_TOKEN:''}});
    const timer=setTimeout(()=>{child.kill('SIGKILL');},10000);
    child.on('error',()=>{clearTimeout(timer);resolve('通知不可用');});
    child.on('close',c=>{clearTimeout(timer);resolve(c===0?'通知已发送':dry?'预演通知已尝试（网络禁用）':'通知失败');});});
}
(async()=>{
  log('========== 爷爷不泡茶 ==========');log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式运行'}；账号数：${rows.length}`);
  if(!rows.length) log('❌ 配置错误：缺少 PAO_TEA_TOKEN');
  for(let i=0;i<rows.length;i++) await account(rows[i],i+1);
  const success=results.filter(r=>r.ok).length, failed=results.length-success;
  const ok=rows.length>0 && failed===0;
  const status=!rows.length?'configuration-error':dry&&ok?'dry-run':ok?'success':success?'partial-failure':'failure';
  const summary={task:'爷爷不泡茶',mode:dry?'dry-run':'live',status,accounts:rows.length,success,failed,subtasks:results,durationMs:Date.now()-started};
  summary.notification=await notify(`模式：${summary.mode}；状态：${status}；账号总数：${rows.length}，成功：${success}，失败：${failed}${!rows.length?'；缺少账号配置':''}`);
  log('--------------------------------');log(`账号统计：总数 ${rows.length}，成功 ${success}，失败 ${failed}`);
  log(`子任务统计：成功 ${results.reduce((s,r)=>s+r.success,0)}，已完成 ${results.reduce((s,r)=>s+r.alreadyComplete,0)}，跳过 ${results.reduce((s,r)=>s+r.skipped,0)}，失败 ${results.reduce((s,r)=>s+r.failed,0)}`);
  log(`通知状态：${summary.notification}；总耗时：${Date.now()-started}ms；完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary));process.exitCode=ok?0:1;
})();
