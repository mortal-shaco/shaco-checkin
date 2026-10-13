// name: Qoder每日签到
// cron: 17 8 * * *
// Qoder 每日自动签到 · 金山文档 AirScript 版（修复版）
// 独立 Node.js 维护版本；上游：wallechfox/qoder-checkin
// 与 Python 版 qoder_core.py 对齐：优先用 accessToken，查活动 401 时才用
// refreshToken 续期，不再一上来就强制刷新。
// 上游授权：MIT。原文件没有单独的版权声明。
// MIT License
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.
/*
Node.js >=18，无第三方业务依赖。每天一次，沿用上游建议避开整点。
QODER_ACCOUNTS：每个非空行一个 JSON 对象，不用 & 或 @ 分隔账号。
字段：accessToken/access_token、refreshToken/refresh_token（至少一项），
device 的 clientType、machineOS、machineHostname、machineId、machineToken、
machineCode、machineType、version 八项均必填。原账号 name、uid 保留。
取得参数：在本人已登录的 Qoder 客户端查看本人授权请求的 Authorization
及 Cosy-* 头；按上述八项与对应头名称复制。刷新令牌从本人客户端登录凭据
中取得；不要上传给第三方。原 qoder_gettoken.py 导出的整行 JSON 也兼容，
本脚本不依赖该工具。中国区默认，国际区 QODER_REGION=global。
签到开关：账号 enabled=true 或 qiandao="是" 才领取，默认跳过（对应原 B 列）。
每账号可选 serverchan、pushplus、qywx 对应原 C/D/E 列；填本人通道令牌。
QODER_ACCOUNTS_FILE：可选显式指定的私有 JSONL 文件，优先于环境变量；
令牌刷新后原子写回此文件（权限 0600），相当于原 A 列写回。
仅使用环境变量时不写凭据，刷新令牌轮换后可能需要重新取得账号参数。
结果以日志及 TASK_SUMMARY 输出，代替原 F 列；不依赖金山文档应用。
QODER_DRY_RUN=1 完全断网且不写回：校验参数并模拟流程及通知。
QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭所有通知。
QINGLONG_NOTIFY_DIR 可指定含 sendNotify.js 的青龙通知目录。
*/
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');
const dry = /^(1|true|yes|on)$/i.test(process.env.QODER_DRY_RUN || '');
const notifyEnabled = !/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1');
const started = Date.now();
const fields = ['clientType','machineOS','machineHostname','machineId','machineToken','machineCode','machineType','version'];
const results = [];
let accounts = [], lines = [], file = '', base, configFailure = false;
const now = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = s => console.log(`[${now()}] ${s}`);
const stamp = () => new Date().toISOString();
const nonempty = x => typeof x === 'string' && x.trim() && !/[\x00-\x1f\x7f]/.test(x);
function request(url, method, headers, body) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const bytes = body === undefined ? null : Buffer.from(JSON.stringify(body));
    const req = https.request(url, {method, headers: {...headers, ...(bytes ? {'Content-Length':bytes.length} : {})}}, res => {
      let size=0, chunks=[];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1048576) { req.destroy(); reject(new Error('响应超出大小限制')); }
        else chunks.push(chunk);
      });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        let data;
        try { data=JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch {
          if (res.statusCode===401) { resolve({status:401,data:null}); return; }
          reject(new Error(`HTTP ${res.statusCode}：响应不是有效 JSON`)); return;
        }
        resolve({status:res.statusCode, data});
      });
    });
    const timer = setTimeout(() => {req.destroy(); reject(new Error('请求超时'));},30000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败')));
    if (bytes) req.write(bytes);
    req.end();
  });
}
function headers(a, token) {
  const h = {'Accept':'application/json','Content-Type':'application/json','User-Agent':'Qoder/claim'};
  for (const f of fields) h[`Cosy-${f[0].toUpperCase()}${f.slice(1)}`] = a.device[f];
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}
function businessOK(d) {
  return d && typeof d === 'object' && !Array.isArray(d) &&
    (!Object.hasOwn(d,'code') || [0,200,'0','200'].includes(d.code)) && d.success !== false;
}
function identity(d, a) {
  const objects = [d, d && d.user, d && d.account];
  const secrets = [a.accessToken,a.access_token,a.refreshToken,a.refresh_token,...Object.values(a.device || {}),a.serverchan,a.pushplus,a.qywx].filter(nonempty);
  for (const obj of objects) {
    if (!obj || typeof obj !== 'object') continue;
    for (const key of ['nickname','username','displayName','uid']) {
      if (obj[key] == null || typeof obj[key] === 'object') continue;
      const v=String(obj[key]);
      // 官方非敏感身份原样显示；疑似手机号或凭据、控制字符不进入日志。
      if (v && !/[\x00-\x1f\x7f]/.test(v) && !/\+?\d{11,}/.test(v) && !secrets.some(s=>v.includes(s))) log(`官方${key}：${v}`);
    }
  }
}
async function stage(r, title, action) {
  const t=Date.now(); r.total++;
  log(`账号${r.account} 阶段${r.total} ${title} 开始`);
  try { const value=await action(); r.success++; log(`✅ 账号${r.account} ${title} 完成，耗时${Date.now()-t}毫秒`); return value; }
  catch (e) {r.failed++; log(`❌ 账号${r.account} ${title}：${e.message}，耗时${Date.now()-t}毫秒`); throw e;}
}
function persist(index,a) {
  if (!file) {log('⚠️ 刷新令牌仅在本次内存中使用；未配置账号文件写回'); return;}
  const updated=lines.slice(); updated[index]=JSON.stringify(a);
  const temp=`${file}.${process.pid}.tmp`;
  try {fs.writeFileSync(temp,updated.join('\n')+'\n',{mode:0o600,flag:'wx'}); fs.renameSync(temp,file); lines=updated;}
  catch {try {fs.unlinkSync(temp);} catch {} throw new Error('私有账号文件写回失败');}
  log('刷新令牌已写回指定私有账号文件');
}
async function refresh(a,index) {
  const rt=a.refreshToken || a.refresh_token;
  if (!rt) throw new Error('缺少刷新令牌，请重新登录取得参数');
  const q=await request(base+'/api/v1/deviceToken/refresh','POST',headers(a,''),{refresh_token:rt});
  if (q.status!==200 || !businessOK(q.data)) throw new Error(`刷新失败：HTTP ${q.status} 或业务拒绝`);
  const token=q.data.token || q.data.accessToken || q.data.access_token;
  if (!nonempty(token)) throw new Error('刷新响应缺少有效访问令牌');
  const rtNew=q.data.refreshToken || q.data.refresh_token || rt;
  if (!nonempty(rtNew)) throw new Error('刷新响应令牌格式无效');
  a.accessToken=token; a.refreshToken=rtNew; delete a.access_token; delete a.refresh_token;
  persist(index,a); return token;
}
async function one(a,index) {
  const t=Date.now(); const r={account:index+1,total:0,success:0,alreadyComplete:0,skipped:0,failed:0,status:'failure',credits:0}; results.push(r);
  try {
    await stage(r,'参数校验',async()=>{
      if (!a || typeof a!=='object' || Array.isArray(a)) throw new Error('账号行必须是 JSON 对象');
      if (!a.device || fields.some(f=>!nonempty(a.device[f]))) throw new Error('device 八项参数必须为非空单行字符串');
      if (!nonempty(a.accessToken || a.access_token) && !nonempty(a.refreshToken || a.refresh_token)) throw new Error('至少提供一项有效访问或刷新令牌');
      for (const k of ['accessToken','access_token','refreshToken','refresh_token','serverchan','pushplus','qywx']) if (a[k]!==undefined && a[k]!=='' && !nonempty(a[k])) throw new Error('凭据必须为单行字符串');
    });
    if (a.enabled!==true && a.qiandao!=='是') {r.skipped++; r.status='skipped'; log(`⏭️ 账号${index+1} 签到未启用`); return;}
    if (dry) {await stage(r,'断网流程预演',async()=>log('将优先使用访问令牌，必要时刷新，查询并领取可领活动；本次未发请求、未写回')); r.status='dry-run'; return;}
    let token=a.accessToken || a.access_token;
    if (!token) token=await stage(r,'获取访问令牌',()=>refresh(a,index));
    let q=await stage(r,'查询活动',async()=>{
      let value=await request(base+'/sash/api/v1/me/campaigns','GET',headers(a,token));
      log(`活动查询 HTTP ${value.status}`);
      if (value.status===401 && (a.refreshToken || a.refresh_token)) {
        log('访问令牌被拒绝，刷新并重试一次'); token=await refresh(a,index);
        value=await request(base+'/sash/api/v1/me/campaigns','GET',headers(a,token)); log(`重试查询 HTTP ${value.status}`);
      }
      if (value.status!==200 || !businessOK(value.data) || !Array.isArray(value.data.campaigns)) throw new Error('活动查询失败或响应契约不符');
      identity(value.data,a); return value;
    });
    const benefits=q.data.campaigns.filter(c=>c && c.actionType==='CLAIM_BENEFIT');
    const claimable=benefits.filter(c=>c.claimStatus==='CLAIMABLE');
    for (const c of claimable) {
      try {await stage(r,'领取活动',async()=>{
        const cid=c.campaignId || c.id;
        if (!['string','number'].includes(typeof cid) || !String(cid)) throw new Error('活动缺少标识');
        const cr=await request(base+'/sash/api/v1/me/campaigns/'+encodeURIComponent(String(cid))+'/claim','POST',headers(a,token),{});
        if (cr.status!==200 || !businessOK(cr.data) || cr.data.status!=='CLAIMED') throw new Error(`领取未确认：HTTP ${cr.status}`);
        identity(cr.data,a);
        const amount=Number(cr.data.benefit?.amount ?? c.benefit?.amount ?? 0);
        if (Number.isFinite(amount)) r.credits+=amount;
        log(`领取已确认，累计 ${r.credits.toLocaleString('en-US')} Credits`);
      });} catch {} // 各活动独立执行，保留失败计数。
    }
    if (r.failed) r.status='failure';
    else if (claimable.length) r.status='success';
    else {
      const seconds=Date.now()/1000;
      if (benefits.some(b=>b.claimStatus==='CLAIMED' && Number(b.startAt || 0)<=seconds && seconds<Number(b.endAt || 0))) {r.alreadyComplete++; r.status='already-complete'; log('☑️ 今日已领取');}
      else {r.skipped++; r.status='unavailable'; log(benefits.length ? '⏭️ 活动待下发，等下轮' : '⏭️ 活动未开放');}
    }
  } catch {r.status='failure';}
  finally {r.elapsedMs=Date.now()-t; log(`账号${r.account} 统计：总任务${r.total} 成功${r.success} 已完成${r.alreadyComplete} 跳过${r.skipped} 失败${r.failed} 耗时${r.elapsedMs}毫秒 状态${r.status}`);}
}
async function notifications(summary) {
  if (!notifyEnabled) {log('⏭️ 通知已关闭'); return 'disabled';}
  if (dry) {log('⏭️ 断网预演：青龙及账号通知仅模拟'); return 'dry-run';}
  const title='Qoder每日签到';
  const body=`账号总数 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${summary.failed}，跳过 ${summary.skipped}；状态 ${summary.status}`;
  let delivered=false, failure=false;
  for (let i=0;i<accounts.length;i++) {
    const a=accounts[i]; if (!a || typeof a!=='object' || (a.enabled!==true && a.qiandao!=='是')) continue;
    const text=`${body}\n账号${i+1}：${results[i]?.status || 'failure'}；Credits ${results[i]?.credits || 0}`;
    const channels=[];
    if (a.serverchan) channels.push(['Server酱',`https://sctapi.ftqq.com/${encodeURIComponent(a.serverchan)}.send`,{title,desp:text},d=>d.code===0]);
    if (a.pushplus) channels.push(['PushPlus','https://www.pushplus.plus/send',{token:a.pushplus,title,content:text,channel:'wechat',template:'txt'},d=>d.code===200]);
    if (a.qywx) {const key=a.qywx.includes('key=') ? a.qywx.split('key=').pop() : a.qywx; channels.push(['企业微信',`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=${encodeURIComponent(key)}`,{msgtype:'text',text:{content:text}},d=>d.errcode===0]);}
    for (const [name,url,payload,ok] of channels) {
      try {const q=await request(url,'POST',{'Content-Type':'application/json'},payload); if(q.status!==200 || !ok(q.data)) throw new Error(); log(`账号${i+1} ${name}通知成功`);}
      catch {failure=true; log(`⚠️ 账号${i+1} ${name}通知失败`);}
    }
  }
  const paths=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const found=paths.find(p=>fs.existsSync(p));
  if (found) {
    // 通知模块不得向日志写出配置中的凭据或原始响应。
    const oldLog=console.log, oldError=console.error, oldWarn=console.warn;
    console.log=console.error=console.warn=()=>{};
    try {
      const mod=require(found); if(typeof mod.sendNotify!=='function') throw new Error();
      let timer; try {await Promise.race([mod.sendNotify(title,body),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error()),30000);})]); delivered=true;} finally {clearTimeout(timer);}
    } catch {failure=true;} finally {console.log=oldLog;console.error=oldError;console.warn=oldWarn;}
  } else failure=true;
  log(delivered ? '✅ 青龙通知已发送' : '⚠️ 青龙通知不可用或发送失败，保留业务退出码');
  return failure ? 'unavailable-or-failed' : 'sent';
}
async function main() {
  log('========== Qoder每日签到 =========='); log(`开始时间 ${stamp()}；模式 ${dry?'断网预演':'正式运行'}`);
  try {
    const region=process.env.QODER_REGION || 'cn';
    if (!['cn','global'].includes(region)) throw new Error();
    base=region==='global' ? 'https://openapi.qoder.sh' : 'https://openapi.qoder.com.cn';
    file=process.env.QODER_ACCOUNTS_FILE || '';
    const raw=file ? fs.readFileSync(file,'utf8') : process.env.QODER_ACCOUNTS || '';
    lines=raw.split(/\r?\n/).filter(x=>x.trim());
    if (!lines.length) throw new Error();
    accounts=lines.map(line=>{try{return JSON.parse(line);} catch{return null;}});
  } catch {configFailure=true; log('❌ 阶段1 配置错误：请检查账号变量、私有文件及区域设置');}
  log(`账号数量 ${accounts.length}`);
  for(let i=0;i<accounts.length;i++) await one(accounts[i],i);
  const failed=results.filter(r=>r.status==='failure').length;
  const skipped=results.filter(r=>['skipped','unavailable'].includes(r.status)).length;
  const succeeded=results.filter(r=>['success','already-complete','dry-run'].includes(r.status)).length;
  // 活动未开放/关闭账号不是签到成功，不将它们当成成功退出。
  const exitCode=configFailure || failed || !succeeded ? 1 : 0;
  const summary={task:'Qoder每日签到',mode:dry?'dry-run':'live',accounts:accounts.length,succeeded,failed,skipped,status:configFailure?'configuration-error':failed?(succeeded?'partial-failure':'failure'):exitCode?'no-verified-success':dry?'dry-run':'success',exitCode,results};
  summary.notification=await notifications(summary);
  summary.elapsedMs=Date.now()-started; summary.finishedAt=stamp();
  log('--------------------------------');
  log(`任务统计：账号${summary.accounts} 成功${succeeded} 失败${failed} 跳过${skipped}；子任务成功${results.reduce((n,r)=>n+r.success,0)} 失败${results.reduce((n,r)=>n+r.failed,0)}；总耗时${summary.elapsedMs}毫秒`);
  log(`完成时间 ${summary.finishedAt}；最终状态 ${summary.status}；通知 ${summary.notification}`);
  console.log('全部处理完成');
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
  process.exitCode=exitCode;
}
main().then(()=>{process.exit(process.exitCode || 0);}).catch(()=>{log('❌ 任务内部错误');process.exit(1);});
