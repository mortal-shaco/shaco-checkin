#!/usr/bin/env node
// name: Qoder CN 每日 Credits 领取
// cron: 53 10 * * *
/*
 * Derived from 875778261/qoder-daily-claim, claim.js
 * https://github.com/875778261/qoder-daily-claim (MIT)
 * Supplied source files contain no additional copyright notices.
 * MIT License
 * Copyright holders: original upstream contributors.
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 *
 * Node.js >=18，无第三方业务依赖。北京时间每日10:00切换活动日，建议10:05运行。
 * QODER_ACCOUNTS：每行一个账号的 Bearer Token（不带 Bearer 前缀），或一个
 * JSON对象 {"token":...,"expiresAt":...}；后者有效期为可解析日期，可省略。
 * 获取：在本人已登录的 Qoder CN 官方客户端开发者工具网络请求中，找到
 * openapi.qoder.com.cn 的 /sash/api/v1/me/campaigns 请求，复制 Authorization
 * 中 Bearer 后的值。不能查看该请求时请勿猜测凭据；本脚本不解密本地登录文件。
 * QODER_DRY_RUN=1：完全离线，仅检查配置与任务计划，绝不查询或领取。
 * QODER_FORCE=1 / --force：显式重放领取请求，可能额外调用接口，默认关闭。
 * --dry-run / --verbose / --help 保留。--data-dir 不再支持桌面凭据读取。
 * QODER_CHECKIN_DIR / --checkin-dir、QODER_CHECKIN_LOG_DIR：可选记录目录；
 * 默认不写文件，记录不参与跳过接口核验。无自动更新或下载、无公开文本发布。
 * QINGLONG_NOTIFY=auto：仅 QINGLONG_NOTIFY_SCRIPTS 选中时通知；1强制、0关闭。
 * 选择器支持目录相对路径、文件名、通配符、目录ID；逗号/分号/空白分隔。
 * QINGLONG_NOTIFY_DIR：可选青龙 sendNotify.js 目录；通知故障不改变业务退出码。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  const raw = process.env.QINGLONG_NOTIFY;
  if (raw !== undefined && String(raw).trim() !== '' && String(raw).trim().toLowerCase() !== 'auto') return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["914f52282cf5f911", "scripts/claim.js", "claim.js", "claim"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const BASE = 'https://openapi.qoder.com.cn';
const TITLE = 'Qoder CN 每日 Credits 领取';
const started = Date.now();
const yes = v => /^(1|true|yes|on)$/i.test(v || '');
const no = v => /^(0|false|no|off)$/i.test(v || '');
const time = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = message => console.log(`[${time()}] ${message}`);
const summary = {ok:false, dryRun:yes(process.env.QODER_DRY_RUN), ranAt:new Date().toISOString(), accounts:[], accountCount:0, success:0, failed:0, notification:'pending'};
let secrets = [];
function redact(value) {
  let text = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const secret of secrets) if (secret) text = text.split(secret).join('[凭据已隐藏]');
  return text.replace(/\b(?:Bearer\s+\S+|1[3-9]\d{9})\b/gi, '[敏感信息已隐藏]');
}
function options() {
  const opts = {dryRun:summary.dryRun, force:yes(process.env.QODER_FORCE), dir:process.env.QODER_CHECKIN_DIR};
  for(let i=2;i<process.argv.length;i++) {
    const a=process.argv[i];
    if(a==='--dry-run') opts.dryRun=true;
    else if(a==='--force') opts.force=true;
    else if(a==='--verbose') opts.verbose=true;
    else if(a==='--help'||a==='-h') opts.help=true;
    else if(a==='--checkin-dir') {opts.dir=process.argv[++i];if(!opts.dir) throw Error('领取记录目录不能为空');}
    else if(a==='--data-dir') throw Error('已移除桌面登录文件依赖，请配置 QODER_ACCOUNTS');
    else throw Error('存在不支持的命令行参数');
  }
  return opts;
}
function account(line) {
  let a;
  if(line.startsWith('{')) {try {a=JSON.parse(line);}catch {throw Error('账号JSON格式错误');}}
  else a={token:line};
  if(!a || typeof a.token!=='string' || !a.token.trim() || /\s/.test(a.token)) throw Error('Token格式错误，请填写不带Bearer前缀的值');
  if(a.expiresAt!==undefined && (!Number.isFinite(Date.parse(a.expiresAt)) || Date.parse(a.expiresAt)<=Date.now())) throw Error('登录有效期无效或已过期，请重新获取Token');
  return a;
}
async function api(route, token, method='GET') {
  if(summary.dryRun) throw Error('离线演练禁止HTTP');
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),15000);
  try {
    const response=await fetch(BASE+route,{method,redirect:'error',signal:controller.signal,headers:{Authorization:`Bearer ${token}`,'Cosy-ClientType':'10',Accept:'application/json'}});
    if(!response.ok) throw Error([401,403].includes(response.status)?'登录失效，请重新获取Token':`接口HTTP状态异常：${response.status}`);
    const chunks=[];let length=0;
    for await(const chunk of response.body) {length+=chunk.length;if(length>1048576) {controller.abort();throw Error('接口响应超过大小上限');}chunks.push(chunk);}
    let body;try {body=JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch {throw Error('接口未返回有效JSON');}
    if(!body || typeof body!=='object') throw Error('接口响应结构异常');
    if(body.success===false || body.ok===false || (body.code!==undefined && ![0,200,'0','200','SUCCESS','OK'].includes(body.code))) throw Error('接口业务状态异常，未确认成功');
    return body;
  } catch(e) {
    if(e.name==='AbortError') throw Error('接口请求超时');
    if(e instanceof TypeError) throw Error('网络请求失败');
    throw e;
  } finally {clearTimeout(timer);}
}
function campaignsOf(body) {
  const list = Array.isArray(body.campaigns)?body.campaigns:Array.isArray(body.data?.campaigns)?body.data.campaigns:Array.isArray(body.data)?body.data:null;
  if(!list || list.some(c=>!c || typeof c!=='object' || Array.isArray(c))) throw Error('活动列表结构异常，不能当作无活动成功');
  return list;
}
function activityDayKey() {return new Date(Date.now()-2*3600000).toISOString().slice(0,10);}
async function stage(result, name, fn) {
  const n=++result.total, begin=Date.now();log(`账号${result.index} 阶段${n}：${name}`);
  try {const state=await fn();result[state||'success']++;log(`账号${result.index} 阶段${n}：${name} ${state==='alreadyComplete'?'☑️ 已完成':state==='skipped'?'⏭️ 跳过':'✅ 成功'}，耗时${Date.now()-begin}ms`);}
  catch(e) {result.failed++;result.errors.push(redact(e.message));log(`账号${result.index} 阶段${n}：❌ ${redact(e.message)}，耗时${Date.now()-begin}ms`);}
}
function identity(body, result) {
  const user=body.user || body.data?.user;
  if(!user || typeof user!=='object') return;
  for(const key of ['nickname','name','username','displayName','uid']) {
    if(['string','number'].includes(typeof user[key]) && String(user[key])) {result.account=redact(user[key]);log(`账号${result.index} 官方身份：${result.account}`);return;}
  }
}
async function runAccount(line,index,opts) {
  const begin=Date.now();
  const r={index,ok:false,total:0,success:0,alreadyComplete:0,skipped:0,failed:0,campaigns:[],errors:[]};
  let auth, campaigns;
  await stage(r,'检查账号配置',async()=>{auth=account(line);});
  if(auth && opts.dryRun) await stage(r,'离线演练',async()=>{log('DRY_RUN_OK：配置可解析；计划查询活动、检查北京时间窗口、领取并复核奖励；未发送请求或写入记录');return 'skipped';});
  if(auth && !opts.dryRun) {
    await stage(r,'查询活动',async()=>{const body=await api('/sash/api/v1/me/campaigns',auth.token);identity(body,r);campaigns=campaignsOf(body);log(`活动数：${campaigns.length}`);});
    if(campaigns) {
      const credits=campaigns.filter(c=>c.actionType==='CLAIM_BENEFIT' && c.benefit?.kind==='CREDITS');
      if(!credits.length) {r.campaigns.push({outcome:'no-credits-campaign'});log('当前没有Credits领取活动（已核验活动列表）');}
      for(const c of credits) {
        await stage(r,'检查并领取Credits活动',async()=>{
          if(c.claimStatus==='CLAIMED' && !opts.force) {r.campaigns.push({outcome:'already-claimed'});return 'alreadyComplete';}
          if(c.claimStatus!=='CLAIMABLE' && !opts.force) {r.campaigns.push({outcome:'not-claimable'});return 'skipped';}
          const now=Date.now();
          if(!opts.force && ((typeof c.startAt==='number' && c.startAt*1000>now)||(typeof c.endAt==='number' && c.endAt*1000<=now))) {r.campaigns.push({outcome:'outside-window'});return 'skipped';}
          if(!['string','number'].includes(typeof c.campaignId) || !String(c.campaignId).trim()) throw Error('缺少活动ID，已阻止领取');
          const route=`/sash/api/v1/me/campaigns/${encodeURIComponent(c.campaignId)}`;
          const claimed=await api(route+'/claim',auth.token,'POST');identity(claimed,r);
          if(claimed.status!=='CLAIMED') throw Error('领取接口未明确返回CLAIMED');
          const amount=Number(claimed.benefit?.amount ?? c.benefit?.amount);
          r.campaigns.push({outcome:claimed.replayed?'replayed':'claimed',amount:Number.isFinite(amount)?amount:null});
          log(`领取已确认${Number.isFinite(amount)?`：${amount} Credits`:''}${claimed.replayed?'（幂等重放）':''}`);
          // 领取成功以官方CLAIMED为准；独立显示奖励复核结果，不能伪称到账。
          try {
            const reward=await api(route+'/reward',auth.token);
            if(reward.status==='CLAIMED') log('奖励复核：官方返回CLAIMED');
            else log('⚠️ 奖励复核未返回CLAIMED；领取接口已确认成功，到账状态待核实');
          } catch {log('⚠️ 奖励复核失败；领取接口已确认成功，到账状态待核实');}
          return claimed.replayed?'alreadyComplete':'success';
        });
      }
    }
  }
  r.ok=r.failed===0;r.durationMs=Date.now()-begin;
  log(`账号${index}统计：总任务${r.total} 成功${r.success} 已完成${r.alreadyComplete} 跳过${r.skipped} 失败${r.failed} 耗时${r.durationMs}ms`);
  if(!opts.dryRun) {
    try {
      const key=crypto.createHash('sha256').update(auth?.token || line).digest('hex').slice(0,24);
      if(opts.dir) {fs.mkdirSync(opts.dir,{recursive:true,mode:0o700});fs.writeFileSync(path.join(opts.dir,`${activityDayKey()}-${key}.json`),JSON.stringify(r,null,2),{mode:0o600});}
      if(process.env.QODER_CHECKIN_LOG_DIR) {fs.mkdirSync(process.env.QODER_CHECKIN_LOG_DIR,{recursive:true,mode:0o700});fs.appendFileSync(path.join(process.env.QODER_CHECKIN_LOG_DIR,`claim-${activityDayKey()}.log`),JSON.stringify(r)+'\n',{mode:0o600});}
    } catch {log('⚠️ 可选记录写入失败，不改变业务结果');}
  }
  return r;
}
function selected() {
  const mode=process.env.QINGLONG_NOTIFY || 'auto';
  if(no(mode)) return false;if(yes(mode)) return true;
  const selectors=(process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const names=['914f52282cf5f911',path.basename(__filename),__filename.replace(/^.*\/scripts\//,''),'claim.js'];
  return selectors.some(s=>{const re=new RegExp('^'+s.split('*').map(p=>p.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('.*')+'$');return names.some(n=>re.test(n));});
}
async function notify() {
  if(summary.dryRun) {summary.notification='dry-run-skipped';log('通知：离线演练仅生成脱敏总结，不调用可能联网的通知模块');return;}
  if(!selected()) {summary.notification='disabled';return;}
  const files=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=files.find(f=>fs.existsSync(f));
  if(!file) {summary.notification='unavailable';log('⚠️ 未找到青龙sendNotify.js，保留业务退出码');return;}
  // 隔离通知进程，不向通知模块继承账号凭据，限制执行时间。
  const {spawn}=require('node:child_process');
  const body=`状态：${summary.status}；账号总数：${summary.accountCount}，成功：${summary.success}，失败：${summary.failed}`;
  const env={...process.env};delete env.QODER_ACCOUNTS;
  await new Promise(resolve=>{
    let settled=false;const finish=state=>{if(settled)return;settled=true;clearTimeout(timer);summary.notification=state;resolve();};
    const child=spawn(process.execPath,['-e','Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))',file,TITLE,body],{env,stdio:'ignore'});
    const timer=setTimeout(()=>{child.kill('SIGKILL');finish('failed');},15000);
    child.on('error',()=>finish('failed'));child.on('exit',code=>finish(code===0?'sent':'failed'));
  });
}
(async()=>{
  log(`========== ${TITLE} ==========`);log(`开始时间：${summary.ranAt}`);
  let opts;
  try {
    opts=options();summary.dryRun=opts.dryRun;
    const lines=(process.env.QODER_ACCOUNTS || '').split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
    secrets=lines.flatMap(line=>{try{return [line,JSON.parse(line).token].filter(Boolean);}catch{return [line];}});
    summary.accountCount=lines.length;
    log(`运行模式：${opts.dryRun?'离线演练':'实际领取'}；账号数：${lines.length}；强制重放：${opts.force?'开启':'关闭'}`);
    if(opts.help) {log('参数获取、使用说明和副作用见文件顶部注释');summary.help=true;}
    else {
      if(!lines.length) throw Error('请配置必填环境变量QODER_ACCOUNTS，每行一个Token或账号JSON');
      for(let i=0;i<lines.length;i++) summary.accounts.push(await runAccount(lines[i],i+1,opts));
    }
    summary.success=summary.accounts.filter(r=>r.ok).length;summary.failed=summary.accounts.filter(r=>!r.ok).length;summary.ok=summary.failed===0;
  } catch(e) {summary.error=redact(e.message);summary.ok=false;log(`❌ 配置或执行失败：${summary.error}`);}
  summary.status=summary.ok?(summary.dryRun?'dry-run':'success'):(summary.error?'configuration-error':summary.success?'partial-failure':'failure');
  const exitCode=summary.ok?0:1;
  try {await notify();} catch {summary.notification='failed';}
  summary.durationMs=Date.now()-started;summary.finishedAt=new Date().toISOString();
  summary.tasks=summary.accounts.reduce((t,r)=>{for(const k of Object.keys(t))t[k]+=r[k];return t;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log('----------------------------------------------------');
  log(`任务统计：账号总数${summary.accountCount} 成功${summary.success} 失败${summary.failed}；子任务${summary.tasks.total} 成功${summary.tasks.success} 已完成${summary.tasks.alreadyComplete} 跳过${summary.tasks.skipped} 失败${summary.tasks.failed}`);
  log(`总耗时：${summary.durationMs}ms；完成时间：${summary.finishedAt}；通知：${summary.notification}；最终状态：${summary.status}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary));process.exitCode=exitCode;
})();
