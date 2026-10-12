// name: 贝因美每日签到
// cron: 19 11 * * *
/**
 * name: 贝因美每日签到
 * cron: 19 11 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Derived from sudojia/AutoTaskScript, src/wx_mini/sudojia_beiyinmei.js
 * Author: Telegram@sudojia — https://blog.imzjw.cn (2024/07/21)
 * BYM_ACCOUNT：每个非空行填写 SID|access_token，仅按首个 | 分隔。
 * 在贝因美微信小程序登录后，通过自己的授权抓包获取 h5.youzan.com 请求：
 * extra-data 请求头中的 sid，以及 checkinV2.json URL 中的 access_token。
 * 凭据须属于同一账号，时效较短，失效后重新获取。不要分享抓包记录。
 * BYM_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方业务依赖。通知可使用青龙 sendNotify.js。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const dry = process.env.BYM_DRY_RUN === '1';
const started = Date.now();
const results = [];
function log(text) { console.log(`[${new Date().toTimeString().slice(0,8)}] ${text}`); }
function request(route, sid) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const req = https.get(new URL(route, 'https://h5.youzan.com'), {headers: {
      'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json', Accept: '*/*',
      Referer: 'https://servicewechat.com/wx8b625f82fd29eda7/46/page-frame.html',
      'extra-data': JSON.stringify({sid, version:'2.175.7.201', clientType:'weapp-miniprogram', client:'weapp', bizEnv:'', ftime:Date.now()})
    }}, res => {
      let size=0; const chunks=[];
      res.on('data', chunk => { size += chunk.length; if(size>1048576) req.destroy(new Error('响应过大')); else chunks.push(chunk); });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if(res.statusCode!==200) return reject(new Error(`HTTP 状态异常（${res.statusCode}）`));
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch { reject(new Error('响应不是有效 JSON')); }
      });
    });
    const timer=setTimeout(()=>req.destroy(new Error('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',()=>reject(new Error('请求失败或超时（详情已脱敏）')));
  });
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) { log('通知预演：'+body); return '断网预演，未发送'; }
  const files=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=files.find(f=>fs.existsSync(f));
  if(!file) return '不可用：未找到 sendNotify.js';
  return new Promise(resolve=>{
    // 隔离通知模块的日志和异常，避免打印其配置或影响业务退出码。
    const child=spawn(process.execPath,['-e',"Promise.resolve().then(()=>require(process.argv[1]).sendNotify('贝因美每日签到',process.argv[2])).then(()=>process.exit(0)).catch(()=>process.exit(1))",file,body],{stdio:'ignore'});
    const timer=setTimeout(()=>{child.kill('SIGKILL');resolve('失败：通知超时');},15000);
    child.on('error',()=>{clearTimeout(timer);resolve('失败：通知无法启动');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':'失败：通知模块异常');});
  });
}
async function main() {
  const lines=(process.env.BYM_ACCOUNT || '').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  log('========== 贝因美每日签到 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'实际执行'}；账号数：${lines.length}`);
  let configError=lines.length===0;
  if(configError) log('❌ 配置错误：请设置 BYM_ACCOUNT，每行 SID|access_token');
  for(let i=0;i<lines.length;i++) {
    const begin=Date.now(); const stat={account:i+1,total:2,success:0,alreadyComplete:0,skipped:0,failed:0};
    let stage=1; let stageStart=Date.now();
    try {
      log(`账号 ${i+1} [1/2] 凭据检查与登录身份查询`);
      const split=lines[i].indexOf('|');
      const sid=lines[i].slice(0,split).trim(), token=lines[i].slice(split+1).trim();
      if(split<1 || !sid || !token || /[\r\n\x00-\x1f]/.test(sid+token)) {configError=true;throw new Error('账号配置错误：需要 SID|access_token');}
      if(dry) { log('✅ 账号格式有效；模拟登录成功（未验证真实凭据）'); }
      else {
        const data=await request('/wscaccount/api/authorize/data.json?kdt_id=43704621',sid);
        if(data.code !== undefined && data.code !== 0) throw new Error('登录接口业务状态异常');
        const user=data.data && data.data.userInfo;
        if(!user || user.hasLogin !== true) throw new Error('未验证登录成功，请重新获取凭据');
        if(typeof user.nickname==='string' && user.nickname) log(`账号昵称：${user.nickname.replace(/[\r\n\x00-\x1f]/g,' ')}`);
        log('✅ 登录状态已验证');
      }
      stat.success++; log(`阶段 1 耗时 ${Date.now()-stageStart}ms`);
      stage=2; stageStart=Date.now(); log(`账号 ${i+1} [2/2] 每日签到`);
      if(dry) log('✅ 模拟签到成功：未请求业务接口、未改变账户状态');
      else {
        const query=new URLSearchParams({checkinId:'2845584',app_id:'wx8b625f82fd29eda7',kdt_id:'43704621',access_token:token});
        const data=await request('/wscump/checkin/checkinV2.json?'+query,sid);
        if(data.code!==0) throw new Error('签到未返回成功业务码，不能判定为已签到');
        log('✅ 签到成功（业务码 0）');
      }
      stat.success++; log(`阶段 2 耗时 ${Date.now()-stageStart}ms`);
    } catch(e) {stat.failed++;stat.skipped=2-stage;log(`❌ 阶段 ${stage}：${e.message}；耗时 ${Date.now()-stageStart}ms`);}
    stat.durationMs=Date.now()-begin;stat.status=stat.failed?'failure':dry?'dry-run':'success';results.push(stat);
    log(`账号 ${i+1} 统计：总任务 ${stat.total}，成功 ${stat.success}，已完成 ${stat.alreadyComplete}，跳过 ${stat.skipped}，失败 ${stat.failed}，耗时 ${stat.durationMs}ms`);
  }
  const failed=results.filter(x=>x.failed).length, success=results.length-failed;
  const exitCode=configError||failed?1:0;
  const status=configError?'configuration-error':failed?(success?'partial-failure':'failure'):dry?'dry-run':'success';
  const body=`模式：${dry?'断网预演':'实际执行'}；状态：${status}；账号总数 ${lines.length}，成功 ${success}，失败 ${failed}；配置错误 ${configError?'是':'否'}`;
  const notification=await notify(body);
  log('----------------------------------------');log(body);
  const tasks=results.reduce((a,r)=>{for(const k of Object.keys(a))a[k]+=r[k];return a;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log(`子任务统计：${JSON.stringify(tasks)}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now()-started}ms；通知：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({status,mode:dry?'dry-run':'live',accounts:lines.length,success,failed,configError,tasks,results,notification,exitCode}));
  process.exitCode=exitCode;
}
main();
