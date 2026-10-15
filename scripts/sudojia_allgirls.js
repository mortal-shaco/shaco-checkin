// name: 所有女生会员签到
// cron: 33 2 * * *
/**
 * name: 所有女生会员签到
 * cron: 19 16 * * *
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_allGirls.js
 * 作者：Telegram@sudojia https://blog.imzjw.cn （2024/07/09）
 * SPDX-License-Identifier: GPL-3.0-only
 * ALL_GIRLS_TOKEN：在所有女生会员服务中心小程序登录，抓取 7.wawo.cc
 * 请求头 AccessToken 的完整值；每个非空行一个账号，不使用 & 或 @ 分隔。
 * ALL_GIRLS_DRY_RUN=1：完全断网预演，不证明凭据有效。
 * QINGLONG_NOTIFY 默认开启；0/false/no/off 关闭。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 * 仅签到会改变账号状态，不执行更新、安装或公开内容发布。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const dry = process.env.ALL_GIRLS_DRY_RUN === '1';
const tokens = (process.env.ALL_GIRLS_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const start = Date.now();
const results = [];
const log = s => console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`);
const delay = () => new Promise(r => setTimeout(r, 900));
function request(token, endpoint, method='GET', body) {
  if (dry) throw new Error('预演禁止业务网络请求');
  return new Promise((resolve, reject) => {
    const payload = body === undefined ? undefined : JSON.stringify(body);
    const req = https.request({hostname:'7.wawo.cc', path:endpoint, method,
      headers:{AccessToken:token, 'user-agent':'Mozilla/5.0',
        referer:'https://servicewechat.com/wx7d1403fe84339669/1076/page-frame.html',
        'content-type':'application/json', accept:'*/*',
        ...(payload ? {'content-length':Buffer.byteLength(payload)} : {})}}, res => {
      let size=0; const chunks=[];
      res.on('data', b => {size += b.length; if(size>262144) req.destroy(new Error('响应过大')); else chunks.push(b);});
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if(res.statusCode < 200 || res.statusCode >= 300) return reject(new Error('HTTP 状态异常'));
        try {
          const data=JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if(!data || data.code !== '000') throw new Error();
          resolve(data.data);
        } catch {reject(new Error('业务未确认成功或响应格式异常'));}
      });
    });
    const timer=setTimeout(() => req.destroy(new Error('请求超时')),15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    req.end(payload);
  });
}
async function account(token, index) {
  const began=Date.now(); const r={account:index,total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  let stage=0;
  async function step(label, fn) {
    const t=Date.now(); r.total++; log(`账号 ${index} 阶段 ${++stage}：${label}`);
    try {const value=await fn(); r.success++; log(`✅ ${label}完成，耗时 ${Date.now()-t} 毫秒`); return value;}
    catch(e) {r.failed++; log(`❌ ${label}失败：${e.message}，耗时 ${Date.now()-t} 毫秒`); throw e;}
  }
  try {
    await step('参数检查',async()=>{if(/[\x00-\x20\x7f-\uffff]/.test(token)) throw new Error('令牌必须为有效请求头文本');});
    if(dry) {
      await step('断网预演',async()=>log('⏭️ 已验证账号解析；将依次获取身份、检查签到、按需签到并复查、查询积分。未发送请求。'));
      r.skipped+=4; r.total+=4;
    } else {
      const member=await step('获取会员身份',async()=>{
        const m=await request(token,'/api/account/wx/member/base');
        if(!m || !['string','number'].includes(typeof m.cardNo) || !String(m.cardNo).trim()) throw new Error('会员卡字段缺失');
        if(typeof m.nickName==='string') {
          // 昵称按官方值输出；凭据或手机号形式的值不作为可公开身份。
          if(!tokens.some(t=>m.nickName.includes(t)) && !/\d{11}/.test(m.nickName)) log(`昵称：${m.nickName}`);
        }
        return m;
      });
      const status=()=>request(token,'/api/activity/wx/task/sign/signMsg','POST',{cardNo:member.cardNo});
      await delay();
      const signed=await step('查询签到状态',async()=>{
        const s=await status(); if(!s || ![0,1].includes(s.signed)) throw new Error('签到状态字段异常'); return s.signed;
      });
      if(signed===1) {r.alreadyComplete++; r.total++; log('☑️ 已签到，无需重复签到');}
      else {
        await delay();
        await step('签到并确认结果',async()=>{
          await request(token,'/api/activity/wx/task/sign/signIn','POST');
          await delay(); const s=await status(); if(!s || s.signed!==1) throw new Error('签到后未确认已签到');
        });
      }
      await delay();
      await step('查询积分',async()=>{
        const amount=await request(token,'/api/score/wx/score/queryAmount');
        if(!((typeof amount==='number' && Number.isFinite(amount)) || (typeof amount==='string' && /^\d+(\.\d+)?$/.test(amount)))) throw new Error('积分字段格式异常');
        log(`当前积分：${amount}`);
      });
    }
  } catch { /* 已记录安全错误，继续下一个账号 */ }
  r.durationMs=Date.now()-began; results.push(r);
  log(`账号 ${index} 统计：总任务 ${r.total}，成功 ${r.success}，已完成 ${r.alreadyComplete}，跳过 ${r.skipped}，失败 ${r.failed}，耗时 ${r.durationMs} 毫秒`);
}
async function notify(body) {
  if(['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY||'1').toLowerCase())) return '已关闭';
  const files=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=files.find(f=>fs.existsSync(f));
  if(!file) return '不可用：未发现 sendNotify.js';
  // 子进程隔离通知输出和异常；预演限制网络，仍调用青龙通知入口。
  const code=`if(process.env.ALL_GIRLS_DRY_RUN==='1'){const deny=()=>{throw Error('offline')};for(const n of ['http','https']){const m=require(n);m.request=deny;m.get=deny;}require('net').Socket.prototype.connect=deny;require('tls').connect=deny;global.fetch=deny;require('child_process').spawn=deny;require('child_process').exec=deny;}Promise.resolve().then(()=>require(process.argv[1]).sendNotify('所有女生会员签到',process.argv[2])).then(()=>process.exit(0),()=>process.exit(1));`;
  return new Promise(resolve=>{
    const env={...process.env}; delete env.ALL_GIRLS_TOKEN;
    const p=spawn(process.execPath,['-e',code,file,body],{env,stdio:'ignore'});
    const t=setTimeout(()=>{p.kill('SIGKILL');},20000);
    p.on('error',()=>{clearTimeout(t);resolve('通知启动失败');});
    p.on('close',c=>{clearTimeout(t);resolve(c===0?'已调用通知':'通知失败（预演禁止网络）或投递不可用');});
  });
}
(async()=>{
  log('========== 所有女生会员签到 ==========');
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${tokens.length}`);
  if(!tokens.length) log('❌ 配置错误：请设置 ALL_GIRLS_TOKEN，每行一个账号');
  for(let i=0;i<tokens.length;i++) await account(tokens[i],i+1);
  const failed=results.filter(r=>r.failed).length;
  const status=!tokens.length?'configuration-error':failed?(failed===tokens.length?'failure':'partial-failure'):dry?'dry-run':'success';
  const summary={status,mode:dry?'dry-run':'live',accounts:tokens.length,success:results.length-failed,failed,configurationErrors:tokens.length?0:1,results};
  process.exitCode=failed || !tokens.length ? 1 : 0;
  const body=`账号总数：${summary.accounts}，成功：${summary.success}，失败：${failed}，状态：${status}${dry?'；仅预演，未验证业务成功':''}`;
  summary.notification=await notify(body);
  summary.durationMs=Date.now()-start; summary.finishedAt=new Date().toISOString();
  log('----------------------------------------'); log(body);
  const totals=results.reduce((a,r)=>{for(const k of Object.keys(a))a[k]+=r[k];return a;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log(`子任务统计：总计 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`通知：${summary.notification}；总耗时：${summary.durationMs} 毫秒；完成时间：${summary.finishedAt}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
})().catch(()=>{process.exitCode=1; console.error('任务内部错误');});
