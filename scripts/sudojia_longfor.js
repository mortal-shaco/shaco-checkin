// name: 龙湖天街
// cron: 39 1 * * *
/**
 * name: 龙湖天街
 * cron: 39 8 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Derived from sudojia/AutoTaskScript, src/wx_mini/sudojia_longfor.js
 * Author: Telegram@sudojia https://blog.imzjw.cn (2024/09/18)
 * LONG_FOR_TOKEN: 登录龙湖天街微信小程序，使用自己的抓包工具查看
 * gw2c-hw-open.longfor.com 请求头 token/lmToken；每行一个账号，不使用 & 分隔。
 * 本脚本将同一凭据用于 lmToken 和 X-LF-UserToken，不输出凭据或手机号。
 * LONG_FOR_ENABLE_LOTTERY=1 明确开启抽奖签到及一次抽奖（消耗机会）。
 * LONG_FOR_SIGN_ACTIVITY / LONG_FOR_LOTTERY_ACTIVITY 可使用自己请求中的 activity_no。
 * 历史活动可能已失效；无接口更新证据，保留上游接口及活动标识，失败闭合。
 * LONG_FOR_DRY_RUN=1 完全离线预演，包括通知仅预演；QINGLONG_NOTIFY=0 关闭通知。
 * 通知通过青龙 sendNotify.js；QINGLONG_NOTIFY_DIR 可指定其所在目录。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["a4edb286cd8742e3", "scripts/sudojia_longfor.js", "sudojia_longfor.js", "sudojia_longfor"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const env = process.env;
const dry = env.LONG_FOR_DRY_RUN === '1';
const lotteryEnabled = env.LONG_FOR_ENABLE_LOTTERY === '1';
const tokens = (env.LONG_FOR_TOKEN || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const start = Date.now();
const results = [];
const signActivity = env.LONG_FOR_SIGN_ACTIVITY || '11111111111686241863606037740000';
const lotteryActivity = env.LONG_FOR_LOTTERY_ACTIVITY || '11111111111725156856102879310000';
function log(s) { console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`); }
function identity(value) {
  if (typeof value !== 'string') return '';
  // Never echo a credential or a phone number even if returned in a display field.
  if (tokens.some(t => value.includes(t)) || /\b1[3-9]\d{9}\b/.test(value)) return '[身份字段含敏感内容，已隐藏]';
  return value.replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
}
function request(token, endpoint, data, userInfo = false) {
  const body = JSON.stringify(data);
  const headers = {'Content-Type':'application/json', 'Accept-Language':'zh-CN,zh;q=0.9',
    'User-Agent':'Mozilla/5.0', lmToken:token,
    'X-Gaia-Api-Key':userInfo ? '646fce29-3a77-462a-aabe-0fe77bc3023f' : 'c06753f1-3e68-437d-b592-b94656ea5517'};
  if (!userInfo) Object.assign(headers, {'X-LF-UserToken':token,'X-LF-Bu-Code':'C20400',
    'X-LF-DXRisk-Source':'5','X-LF-DXRisk-Captcha-Token':'undefined','X-LF-Channel':'C2'});
  return new Promise((resolve,reject) => {
    const req = https.request({hostname:'gw2c-hw-open.longfor.com',path:endpoint,method:'POST',headers}, res => {
      let size=0; const chunks=[];
      res.on('data', c => {size+=c.length; if(size>262144) req.destroy(new Error('响应超过限制')); else chunks.push(c);});
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if(res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP ${res.statusCode}`));
        try { const obj=JSON.parse(Buffer.concat(chunks).toString());
          if(!obj || typeof obj !== 'object') throw Error(); resolve(obj);
        } catch {reject(new Error('响应不是有效 JSON 对象'));}
      });
    });
    const timer=setTimeout(() => req.destroy(new Error('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',()=>reject(new Error('网络请求失败或超时')));
    req.end(body);
  });
}
function business(r) {
  if(r.code !== '0000' || !r.data || typeof r.data !== 'object') throw new Error('业务未确认成功（凭据、活动或接口可能失效）');
  return r.data;
}
async function account(token, i) {
  const begun=Date.now(); const stat={account:i,total:4,success:0,alreadyComplete:0,skipped:0,failed:0};
  let authenticated=false, lotteryReady=false;
  const base='/lmarketing-task-api-mvc-prod/openapi/task/v1/';
  const steps=[['账号信息',async()=>{
    const r=await request(token,'/riyuehu-miniapp-prod/service/ryh/user/info',{data:{projectId:'B379F9F1-C176-4925-B6F6-92555AC62E61'}},true);
    if ((r.code !== undefined && r.code !== '0000') || !r.data || typeof r.data.nickName !== 'string' || !r.data.nickName.trim()) throw new Error('账号身份未确认，停止该账号后续操作');
    log(`账号 ${i} 昵称：${identity(r.data.nickName)}`); authenticated=true; return 'success';
  }],['每日签到',async()=>{
    const d=business(await request(token,base+'signature/clock',{activity_no:signActivity}));
    if(d.is_popup!==0 && d.is_popup!==1) throw new Error('签到结果字段不符合已知契约');
    return d.is_popup===1?'success':'alreadyComplete';
  }],['抽奖签到',async()=>{
    const d=business(await request(token,base+'lottery/sign',{activity_no:lotteryActivity,task_id:''}));
    if(!Number.isFinite(Number(d.ticket_times)) || d.ticket_times===null || Number(d.ticket_times)<0) throw new Error('抽奖机会未确认');
    log(`账号 ${i} 获得抽奖机会：${Number(d.ticket_times)}`); lotteryReady=true; return 'success';
  }],['一次抽奖',async()=>{
    const d=business(await request(token,base+'lottery/luck',{activity_no:lotteryActivity,task_id:''}));
    if(typeof d.desc!=='string' || !d.desc.trim()) throw new Error('抽奖结果未确认');
    log(`账号 ${i} 抽奖结果：${identity(d.desc)}`); return 'success';
  }]];
  for(let n=0;n<steps.length;n++) {
    const t=Date.now(); let state;
    log(`账号 ${i} 阶段 ${n+1}/4 ${steps[n][0]} 开始`);
    try {
      if(n>=2 && !lotteryEnabled) {state='skipped'; log('⏭️ 抽奖流程未启用');}
      else if(dry) {state='skipped'; log('⏭️ DRY_RUN：请求与副作用均未执行');}
      else if(n>0 && !authenticated || n===3 && !lotteryReady) {state='skipped'; log('⏭️ 前置操作未确认成功');}
      else {state=await steps[n][1](); log(state==='alreadyComplete'?'☑️ 今日已签到':'✅ 已验证成功');}
    } catch(e) {state='failed';log(`❌ ${e.message}`);}
    stat[state]++; log(`账号 ${i} 阶段 ${n+1} 耗时 ${Date.now()-t}ms`);
  }
  stat.durationMs=Date.now()-begun; results.push(stat);
  log(`账号 ${i} 统计：总任务 ${stat.total}，成功 ${stat.success}，已完成 ${stat.alreadyComplete}，跳过 ${stat.skipped}，失败 ${stat.failed}，耗时 ${stat.durationMs}ms`);
}
async function notify(body) {
  if(/^(0|false|no|off)$/i.test(env.QINGLONG_NOTIFY||'1')) return '已关闭';
  if(dry) return '离线预演（未发送）';
  const dirs=[env.QINGLONG_NOTIFY_DIR,'/ql/data/scripts','/ql/scripts'].filter(Boolean);
  const file=dirs.map(d=>path.join(d,'sendNotify.js')).find(f=>fs.existsSync(f));
  if(!file) return '不可用（未找到 sendNotify.js）';
  return new Promise(resolve=>{
    const child=spawn(process.execPath,['-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))',file,'龙湖天街',body],{stdio:'ignore'});
    const timer=setTimeout(()=>{child.kill('SIGKILL');resolve('失败（超时）');},15000);
    child.on('error',()=>{clearTimeout(timer);resolve('失败');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':'失败');});
  });
}
(async()=>{
  log('========== 龙湖天街 ==========');
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry?'离线预演':'正式运行'}；账号数：${tokens.length}`);
  let configError = !tokens.length || tokens.some(t=>/[\x00-\x20\x7f&]/.test(t)) ||
    !/^\d+$/.test(signActivity) || !/^\d+$/.test(lotteryActivity) ||
    ['LONG_FOR_DRY_RUN','LONG_FOR_ENABLE_LOTTERY'].some(k=>env[k]!==undefined && !['0','1'].includes(env[k]));
  if(configError) log('❌ 配置错误：凭据须每行一个、不含空白或 &；活动 ID 须为数字；模式开关须为 0 或 1');
  else for(let i=0;i<tokens.length;i++) await account(tokens[i],i+1);
  const failed=configError?tokens.length:results.filter(r=>r.failed).length;
  const succeeded=dry||configError?0:results.length-failed;
  const status=configError?'configuration-error':failed?(succeeded?'partial-failure':'failure'):dry?'dry-run':'success';
  const summary={status,accounts:tokens.length,success:succeeded,failed,dryRun:dry,results};
  const body=`状态：${status}；账号总数：${tokens.length}；成功：${succeeded}；失败：${failed}；预演：${dry?'是':'否'}`;
  summary.notification=await notify(body);
  summary.durationMs=Date.now()-start;
  log('--------------------------------');log(body);
  const total=results.reduce((s,r)=>{for(const k of Object.keys(s))s[k]+=r[k];return s;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log(`子任务统计：${JSON.stringify(total)}`);
  log(`完成时间：${new Date().toISOString()}；总耗时：${summary.durationMs}ms；通知：${summary.notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
  process.exitCode=configError||failed?1:0;
})().catch(()=>{log('❌ 未预期的本地运行错误');process.exitCode=1;});
