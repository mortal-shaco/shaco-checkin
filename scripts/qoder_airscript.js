// name: Qoder每日签到
// cron: 17 8 * * *
// Qoder 每日自动签到 · 金山文档 AirScript 版（修复版）
// 独立 Node.js 维护版本；上游：wallechfox/qoder-checkin
// 合并来源：L0NE-6/Qoder-Daily/qoder_daily.py，MIT 授权。
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
QODER_ACTION=checkin（默认）或 refresh；也支持 --refresh-only。
QODER_ONLY 或 --only 指定从 1 开始的账号序号；--no-notify 关闭全部通知。
账号 region 可为 cn/global，未填沿用 QODER_REGION；不改变默认 cron。
国际区活动窗口北京时间 10:00 开启，可自行调整任务时间，不自动改动计划。
不查找本机组件、不下载软件、不自动生成设备身份；device 必须由本人取得。
功能清单与覆盖核对：原维护能力全部保留；强制刷新列表、仅刷新令牌、
指定账号、混合区域、通知链及幂等识别不变，仍逐项领取全部 CLAIM_BENEFIT。
本次来源核对：AirScript/core 使用同一活动及领取接口、设备头和刷新接口；
当前 qoder_daily.py 新增 403/业务码 105、10019901001 续期，中国区成功空表
用四个最小鉴权头复取一次，Pro /reward 只读查面值及 /api/v2/quota/usage
额度前后回读。本脚本保留既有 forceRefresh=true，合并这些兼容改进；
奖励面值和额度差额仅辅助核验，不能代替明确 CLAIMED 领取结果。
QODER_PRO_VERIFY=1 默认启用只读核验，可设 0 关闭；不减少既有领取能力。
QODER_PRO_UPGRADE=1 才额外领取列表中非 CLAIM_BENEFIT 的明确 Pro 活动，
默认 0 不扩大原候选的领取边界。不猜活动 ID，不打印兑换券或服务端原文。
QODER_WINDOW_RETRY=1 可启用北京时间 10:00-10:30 暂无活动时刷新列表，
默认 0 保持原候选单轮查询；QODER_WINDOW_RETRY_MAX 默认16、范围1至16，
QODER_WINDOW_RETRY_GAP 默认90秒、范围1至300秒，不重试领取请求。
兼容 QODER_TOKENS（中国区）和 QODER_GLOBAL_TOKENS（国际区），仅在未设
QODER_ACCOUNTS/私有文件时使用，每行 access 或 access|refresh 或
备注|access|refresh 或 备注|access|refresh|uid，绝不用 & 分账号。
拆分首个字段分隔符后保留剩余字段；含 | 的令牌请用规范 JSON 行避免歧义。
旧变量需 QODER_ENABLED=1 显式启用；device 从 QODER_COSY_CLIENT_TYPE、
QODER_COSY_MACHINE_OS/HOSTNAME/ID/TOKEN/CODE/TYPE、QODER_COSY_VERSION
取得，三项风控头还兼容 QODER_MACHINE_TOKEN/CODE/TYPE；不生成设备参数。
可选 PUSHPLUS_TOKEN、BARK_URL、WECOM_WEBHOOK、DINGTALK_WEBHOOK/SECRET
用于全局汇总通知，保留逐账号原有三种通知，全部服从总开关。
不将任意 409 当作成功，仅接受可核验 ALREADY_CLAIMED/replayed 业务结果。
取号脚本是 Windows 参数获取工具，02_checkin 是依赖入口，不另行发布。
前次失败为 includedSources 引用了未知或过期来源；本轮仅引用 task.json
当前允许的 catalogId/sha256，逐个核对文件哈希，不沿用旧来源表。
QINGLONG_NOTIFY 默认 auto，本维护任务默认在通知名单内；1/true/yes/on
强制开启，0/false/no/off 关闭所有通知。auto 下 QINGLONG_NOTIFY_SCRIPTS
设置后替换默认名单，支持目录相对路径、文件名、catalogId、文件名通配符，
逗号、分号或空白分隔，* 全选，空值全关；dry-run 只模拟通知以保证断网。
QINGLONG_NOTIFY_DIR 可指定含 sendNotify.js 的青龙通知目录。
保留候选实际 cron 17 8 * * *；覆盖表中的 23 2 * * * 与提供的文件不同，
本次不自动迁移已有计划，主来源 10:00 开窗仅作运行说明。
*/
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["e034e75509550071", "scripts/qoder_airscript.js", "qoder_airscript.js", "qoder_airscript"];
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
const https = require('node:https');
const crypto = require('node:crypto');
const {spawn} = require('node:child_process');
const dry = /^(1|true|yes|on)$/i.test(process.env.QODER_DRY_RUN || '');
const enabled = x => /^(1|true|yes|on)$/i.test(x || '');
const disabled = x => /^(0|false|no|off)$/i.test(x || '');
function notificationSelected() {
  if (process.argv.includes('--no-notify') || disabled(process.env.QINGLONG_NOTIFY)) return false;
  if (enabled(process.env.QINGLONG_NOTIFY)) return true;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const names=['e034e75509550071','7dae37fb02629e65','scripts/qoder_airscript.js','qoder_airscript.js',path.basename(__filename)];
  return process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(s=>{
    const pattern='^'+s.split('*').map(p=>p.split('?').map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('.')).join('.*')+'$';
    return names.some(n=>new RegExp(pattern).test(n));
  });
}
const notifyEnabled = notificationSelected();
let action='checkin', only=0;
const started = Date.now();
const fields = ['clientType','machineOS','machineHostname','machineId','machineToken','machineCode','machineType','version'];
const results = [];
let accounts = [], lines = [], file = '', base, configFailure = false;
let retryMax=16, retryGap=90;
const accountBase = a => a.region==='global' ? 'https://openapi.qoder.sh' : a.region==='cn' ? 'https://openapi.qoder.com.cn' : base;
const payload = d => d && typeof d.data==='object' && d.data && !Array.isArray(d.data) ? d.data : d;
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
          if ([401,403].includes(res.statusCode)) { resolve({status:res.statusCode,data:null}); return; }
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
    ['code','Code'].every(k=>!Object.hasOwn(d,k) || [0,200,'0','200'].includes(d[k])) && d.success !== false;
}
function identity(d, a) {
  const objects = [d, d && d.user, d && d.account];
  const secrets = [a,...accounts].filter(x=>x && typeof x==='object').flatMap(x=>
    [x.accessToken,x.access_token,x.refreshToken,x.refresh_token,x.device?.machineToken,x.device?.machineCode,x.device?.machineId,x.device?.machineHostname,x.serverchan,x.pushplus,x.qywx]);
  secrets.push(...['PUSHPLUS_TOKEN','BARK_URL','WECOM_WEBHOOK','DINGTALK_WEBHOOK','DINGTALK_SECRET'].map(k=>process.env[k]));
  const protectedValues=secrets.filter(nonempty);
  for (const obj of objects) {
    if (!obj || typeof obj !== 'object') continue;
    for (const key of ['nickname','username','displayName','uid']) {
      if (obj[key] == null || typeof obj[key] === 'object') continue;
      const v=String(obj[key]);
      // 官方非敏感身份原样显示；疑似手机号或凭据、控制字符不进入日志。
      if (v && !/[\x00-\x1f\x7f]/.test(v) && (key==='uid' || !/\+?\d{11,}/.test(v)) && !protectedValues.some(s=>v.includes(s))) log(`官方${key}：${v}`);
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
  const ep=rt.startsWith('jrt-') ? '/api/v1/jobToken/refresh' : '/api/v1/deviceToken/refresh';
  const q=await request(accountBase(a)+ep,'POST',headers(a,''),{refresh_token:rt});
  if (q.status!==200 || !businessOK(q.data)) throw new Error(`刷新失败：HTTP ${q.status} 或业务拒绝`);
  const d=payload(q.data);
  if (!businessOK(d)) throw new Error('刷新业务拒绝');
  const token=d.token || d.accessToken || d.access_token || d.device_token || d.deviceToken;
  if (!nonempty(token)) throw new Error('刷新响应缺少有效访问令牌');
  const rtNew=d.refreshToken || d.refresh_token || rt;
  if (!nonempty(rtNew)) throw new Error('刷新响应令牌格式无效');
  a.accessToken=token; a.refreshToken=rtNew; delete a.access_token; delete a.refresh_token;
  identity(q.data,a); if (d!==q.data) identity(d,a);
  persist(index,a); return token;
}
const campaignId = c => c.campaignId || c.id || c.campaignKey;
function campaignBody(q) {
  if (q.status!==200 || !businessOK(q.data) || !businessOK(payload(q.data))) return null;
  // 已有标准及 data 包装均兼容；不把未知响应形状当作成功空表。
  for (const d of [payload(q.data),q.data]) {
    if (Array.isArray(d?.campaigns)) return {...d,campaigns:d.campaigns};
    if (d?.showCampaign===false && d.campaigns==null) return {...d,campaigns:[]};
  }
  return null;
}
function authDead(q) {
  return [401,403].includes(q.status) || [q.data,payload(q.data)].some(d=>
    d && [d.code,d.Code].some(code=>['105','10019901001'].includes(String(code))));
}
function minimalHeaders(a,token) {
  return {'Authorization':`Bearer ${token}`,'Cosy-ClientType':a.device.clientType,'User-Agent':'Qoder','Content-Type':'application/json'};
}
async function queryCampaigns(a,index,r) {
  let token=a.accessToken || a.access_token;
  const once=async()=>{
    const q=await request(accountBase(a)+'/sash/api/v1/me/campaigns?forceRefresh=true','GET',headers(a,token));
    log(`账号${r.account} 活动查询 HTTP ${q.status}`);
    const d=campaignBody(q);
    if (accountBase(a)==='https://openapi.qoder.com.cn' && d && !d.campaigns.length) {
      log(`账号${r.account} 中国区明确空列表，按上游四头协议只读重查一次`);
      // 原强制刷新请求保留，补取沿用当前主来源不带 forceRefresh 的四头请求。
      const retry=await request(accountBase(a)+'/sash/api/v1/me/campaigns','GET',minimalHeaders(a,token));
      log(`账号${r.account} 中国区补取 HTTP ${retry.status}`);
      if (campaignBody(retry)?.campaigns.length===0) return q;
      return retry;
    }
    return q;
  };
  let q=await once();
  if (authDead(q) && (a.refreshToken || a.refresh_token)) {
    log(`账号${r.account} HTTP 或已知业务码表示鉴权失效，续期后仅重试一次`);
    token=await refresh(a,index); q=await once();
  }
  const d=campaignBody(q);
  if (!d) throw new Error(`活动查询失败或响应契约不符（HTTP ${q.status}）`);
  identity(q.data,a); if(d!==q.data) identity(d,a);
  log(`账号${r.account} 返回活动${d.campaigns.length}项`);
  return {...q,data:d};
}
function windowActive() {
  const d=new Date(Date.now()+8*3600000);
  return d.getUTCHours()===10 && d.getUTCMinutes()<30;
}
const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));
function looksPro(c) {
  return ['campaignKey','actionType','title','name','campaignName'].some(k=>/pro|upgrade/i.test(String(c[k] || ''))) ||
    (String(c.benefit?.kind).toUpperCase()==='CREDITS' && Number(c.benefit.amount)>=1000);
}
async function diagnostic(r,title,fn) {
  const t=Date.now(); r.total++;
  log(`账号${r.account} 阶段${r.total} ${title} 开始`);
  try {const value=await fn(); r.success++; log(`✅ 账号${r.account} ${title} 完成，耗时${Date.now()-t}毫秒`); return value;}
  catch {r.skipped++; log(`⚠️ 账号${r.account} ${title} 不可用，不改变领取判定，耗时${Date.now()-t}毫秒`); return null;}
}
async function rewardOf(a,c,token) {
  const id=campaignId(c);
  if (!['string','number'].includes(typeof id) || !String(id)) throw new Error('缺少活动标识');
  // 奖励页只读接口按来源仅用鉴权及客户端头，不发送设备身份。
  const q=await request(accountBase(a)+'/sash/api/v1/me/campaigns/'+encodeURIComponent(String(id))+'/reward','GET',
    {...minimalHeaders(a,token),Accept:'application/json','Accept-Language':'zh-CN',Origin:accountBase(a)});
  const d=payload(q.data);
  if (q.status!==200 || !businessOK(q.data) || !businessOK(d)) throw new Error('奖励查询失败');
  identity(q.data,a); if(d!==q.data) identity(d,a);
  const b=d.benefit && typeof d.benefit==='object' ? d.benefit : d;
  const amount=Number(b.amount);
  if (b.amount==null || !Number.isFinite(amount) || amount<0) throw new Error('奖励面值未知');
  return {kind:String(d.kind || b.kind || '').toUpperCase(),amount};
}
async function quotaRemaining(a,token) {
  const q=await request(accountBase(a)+'/api/v2/quota/usage','GET',headers(a,token));
  const d=payload(q.data);
  if (q.status!==200 || !businessOK(q.data) || !businessOK(d)) throw new Error('额度查询失败');
  identity(q.data,a); if(d!==q.data) identity(d,a);
  const pools=[d.userQuota,d.addOnQuota,d.orgResourcePackage,...(Array.isArray(d.dedicatedResourcePackages)?d.dedicatedResourcePackages:[])];
  const values=pools.filter(p=>p && p.remaining!=null).map(p=>Number(p.remaining));
  if (!values.length || values.some(n=>!Number.isFinite(n))) throw new Error('额度响应契约不符');
  return values.reduce((n,v)=>n+v,0);
}
const claimFailures={
  REDEMPTION_CODE_OUT_OF_STOCK:'今日名额已发完', SAME_PERSON_ALREADY_CLAIMED:'同一设备身份下其他账号已领取',
  CAMPAIGN_NOT_ACTIVE:'活动尚未开放或已结束', ACHIEVEMENT_NOT_COMPLETED:'活动条件尚未完成',
  RISK_BLOCKED:'设备风控未通过，请更新本人设备头', RISK_DEPENDENCY_UNAVAILABLE:'设备风控依赖暂不可用'
};
function claimVerdict(q) {
  const d=payload(q.data);
  const bodies=[d,q.data].filter(x=>x && typeof x==='object');
  const replay=bodies.some(b=>b.replayed===true || ['ALREADY_CLAIMED','REPLAYED'].includes(b.result) ||
    ['ALREADY_CLAIMED','REPLAYED'].includes(b.failureCode) || ['ALREADY_CLAIMED','REPLAYED'].includes(b.errorCode));
  if ([200,201,409].includes(q.status) && replay && (q.status===409 || businessOK(q.data) && businessOK(d))) return 'already';
  const failure=bodies.some(b=>b.failureCode || b.errorCode);
  const reason=bodies.map(b=>claimFailures[b.failureCode] || claimFailures[b.errorCode]).find(Boolean);
  if (failure) throw new Error(reason || `领取业务拒绝：HTTP ${q.status}`);
  if ([200,201].includes(q.status) && businessOK(q.data) && businessOK(d) && d.status==='CLAIMED') return 'claimed';
  throw new Error(reason || `领取未确认：HTTP ${q.status}`);
}
function legacyDevice() {
  const suffix={clientType:'CLIENT_TYPE',machineOS:'MACHINE_OS',machineHostname:'MACHINE_HOSTNAME',machineId:'MACHINE_ID',machineToken:'MACHINE_TOKEN',machineCode:'MACHINE_CODE',machineType:'MACHINE_TYPE',version:'VERSION'};
  return Object.fromEntries(fields.map(f=>[f,process.env['QODER_COSY_'+suffix[f]] ||
    (['machineToken','machineCode','machineType'].includes(f) ? process.env['QODER_'+suffix[f]] : '') || (f==='clientType'?'10':'')]));
}
function legacyAccounts(raw,region) {
  const first=s=>{const i=s.indexOf('|'); return i<0?[s,'',false]:[s.slice(0,i),s.slice(i+1),true];};
  const isToken=s=>/^(dt-|drt-|jt-|jrt-|eyJ)/.test(s) || s.length>80 || s.split('.').length>=3;
  return (raw || '').split(/\r?\n/).map(s=>s.trim()).filter(s=>s && !s.startsWith('#')).map(line=>{
    let [head,tail,has]=first(line), name='', accessToken=head, refreshToken='', uid='';
    if (has) {
      if (isToken(head) || !tail.includes('|') && !isToken(tail)) refreshToken=tail;
      else {name=head; const parts=first(tail); accessToken=parts[0]; refreshToken=parts[1];
        // 旧四字段格式明确规定最后一项为公开 UID；含分隔符凭据请改用 JSON。
        if (parts[2] && refreshToken.includes('|')) [refreshToken,uid]=first(refreshToken);
      }
    }
    return {name,accessToken,refreshToken,uid,region,device:legacyDevice(),enabled:enabled(process.env.QODER_ENABLED)};
  });
}
async function one(a,index) {
  const t=Date.now(); const r={account:index+1,total:0,success:0,alreadyComplete:0,skipped:0,failed:0,status:'failure',credits:0}; results.push(r);
  try {
    await stage(r,'参数校验',async()=>{
      if (!a || typeof a!=='object' || Array.isArray(a)) throw new Error('账号行必须是 JSON 对象');
      if (a.region!==undefined && !['cn','global'].includes(a.region)) throw new Error('账号区域必须为 cn 或 global');
      if (!a.device || fields.some(f=>!nonempty(a.device[f]))) throw new Error('device 八项参数必须为非空单行字符串');
      if (!nonempty(a.accessToken || a.access_token) && !nonempty(a.refreshToken || a.refresh_token)) throw new Error('至少提供一项有效访问或刷新令牌');
      for (const k of ['accessToken','access_token','refreshToken','refresh_token','serverchan','pushplus','qywx']) if (a[k]!==undefined && a[k]!=='' && !nonempty(a[k])) throw new Error('凭据必须为单行字符串');
    });
    if (only && index+1!==only) {r.skipped++; r.status='skipped'; log(`⏭️ 账号${index+1} 不在指定执行范围`); return;}
    if (a.enabled!==true && a.qiandao!=='是') {r.skipped++; r.status='skipped'; log(`⏭️ 账号${index+1} 签到未启用`); return;}
    if (action==='refresh' && !nonempty(a.refreshToken || a.refresh_token)) {await stage(r,'刷新参数校验',async()=>{throw new Error('仅刷新模式必须提供刷新令牌');});}
    if (dry) {await stage(r,'断网流程预演',async()=>log(action==='refresh' ? '将仅刷新令牌；本次未发请求、未写回' : '将优先使用访问令牌，必要时刷新，强制刷新活动；中国区空表补取，逐项领取，Pro 只读核验；本次未发请求、未写回')); r.status='dry-run'; return;}
    if (action==='refresh') {await stage(r,'仅刷新令牌',()=>refresh(a,index)); r.status='success'; return;}
    let token=a.accessToken || a.access_token;
    if (!token) token=await stage(r,'获取访问令牌',()=>refresh(a,index));
    let q=await stage(r,'查询活动',()=>queryCampaigns(a,index,r));
    const eligible=c=>c && (c.actionType==='CLAIM_BENEFIT' || accountBase(a)==='https://openapi.qoder.com.cn' && enabled(process.env.QODER_PRO_UPGRADE) && looksPro(c));
    for (let attempt=0; enabled(process.env.QODER_WINDOW_RETRY) && attempt<retryMax && windowActive() &&
      !q.data.campaigns.some(c=>eligible(c) && ['CLAIMABLE','CLAIMED'].includes(c.claimStatus)); attempt++) {
      await stage(r,'等待活动开窗',async()=>{
        // 不跨越北京时间 10:30 继续派发重试。
        const bj=new Date(Date.now()+8*3600000);
        const remaining=(30-bj.getUTCMinutes())*60000-bj.getUTCSeconds()*1000-bj.getUTCMilliseconds();
        const delay=Math.min(retryGap*1000,Math.max(0,remaining));
        log(`账号${r.account} 暂未下发，等待${Math.ceil(delay/1000)}秒`); await sleep(delay);
      });
      if (!windowActive()) break;
      q=await stage(r,'开窗重新查询',()=>queryCampaigns(a,index,r));
    }
    token=a.accessToken || a.access_token;
    const benefits=q.data.campaigns.filter(eligible);
    const claimable=benefits.filter(c=>c.claimStatus==='CLAIMABLE');
    const verify=!disabled(process.env.QODER_PRO_VERIFY) && accountBase(a)==='https://openapi.qoder.com.cn';
    let probes=0;
    for (const c of claimable) {
      try {await stage(r,'领取活动',async()=>{
        const cid=campaignId(c);
        if (!['string','number'].includes(typeof cid) || !String(cid)) throw new Error('活动缺少标识');
        let pro=looksPro(c);
        if (verify && (pro || probes<5)) {
          probes++;
          const reward=await diagnostic(r,'只读核验奖励面值',()=>rewardOf(a,c,token));
          if (reward) {pro=pro || reward.kind==='CREDITS' && reward.amount>=1000; log(`账号${r.account} 奖励面值${reward.amount}，${pro?'识别为 Pro 升级候选':'普通活动'}`);}
        }
        const before=verify && pro ? await diagnostic(r,'领取前回读总剩余额度',()=>quotaRemaining(a,token)) : null;
        const cr=await request(accountBase(a)+'/sash/api/v1/me/campaigns/'+encodeURIComponent(String(cid))+'/claim','POST',{...headers(a,token),Origin:accountBase(a)},{});
        log(`账号${r.account} 领取 HTTP ${cr.status}`);
        const verdict=claimVerdict(cr);
        const d=payload(cr.data);
        identity(cr.data,a); if(d!==cr.data) identity(d,a);
        if (verdict==='already') {r.alreadyComplete++; log('☑️ 服务端确认活动已领取，未重复计入 Credits'); return;}
        if (verify && pro) {
          const after=await diagnostic(r,'领取后回读总剩余额度',async()=>{await sleep(2000); return quotaRemaining(a,token);});
          if (before!==null && after!==null) {const delta=after-before; log(delta>0 ? `账号${r.account} Pro 额度回读增加 ${delta}` : `账号${r.account} Pro 领取已确认，额度暂未增加，待到账核验`);}
          else log(`账号${r.account} Pro 领取已确认，额度回读不可用，到账待核验`);
        }
        const amount=Number(d.benefit?.amount ?? c.benefit?.amount ?? 0);
        if (Number.isFinite(amount)) r.credits+=amount;
        log(`领取已确认，累计 ${r.credits.toLocaleString('en-US')} Credits`);
        const days=Number(d.benefit?.validity?.days);
        if(Number.isFinite(days) && days>0) log(`奖励有效期 ${days} 天`);
      });} catch {} // 各活动独立执行，保留失败计数。
    }
    if (r.failed) r.status='failure';
    else if (claimable.length) r.status='success';
    else {
      const seconds=Date.now()/1000;
      if (benefits.some(b=>b.claimStatus==='CLAIMED' && Number(b.startAt || 0)<=seconds && seconds<Number(b.endAt || 0))) {r.alreadyComplete++; r.status='already-complete'; log('☑️ 今日已领取');}
      else {r.skipped++; r.status='unavailable'; if ((a.region || process.env.QODER_REGION)==='global') log('国际区活动窗口北京时间 10:00 开启，暂未下发不视为领取成功'); log(benefits.length ? '⏭️ 活动待下发，等下轮' : '⏭️ 活动未开放');}
    }
  } catch {r.status='failure';}
  finally {r.elapsedMs=Date.now()-t; log(`账号${r.account} 统计：总任务${r.total} 成功${r.success} 已完成${r.alreadyComplete} 跳过${r.skipped} 失败${r.failed} 耗时${r.elapsedMs}毫秒 状态${r.status}`);}
}
function sendQinglong(modulePath,title,body) {
  if (dry) throw new Error('预演禁止调用通知模块');
  // 使用同一 Node.js 运行时隔离可选青龙模块的输出，防止它打印配置或响应。
  const program=`let raw='';process.stdin.setEncoding('utf8');process.stdin.on('data',c=>raw+=c);process.stdin.on('end',async()=>{try{const p=JSON.parse(raw),m=require(process.argv[1]);if(typeof m.sendNotify!=='function')throw Error();const r=await m.sendNotify(p.title,p.body);process.exit(r===false?1:0);}catch{process.exit(1);}});`;
  return new Promise((resolve,reject)=>{
    const child=spawn(process.execPath,['-e',program,path.resolve(modulePath)],{stdio:['pipe','ignore','ignore']});
    const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('通知超时'));},30000);
    child.on('error',()=>{clearTimeout(timer);reject(new Error('通知执行失败'));});
    child.on('close',code=>{clearTimeout(timer);if(code===0) resolve();else reject(new Error('通知发送失败'));});
    child.stdin.on('error',()=>{});
    child.stdin.end(JSON.stringify({title,body}));
  });
}
async function notifications(summary) {
  if (!notifyEnabled) {log('⏭️ 通知已关闭'); return 'disabled';}
  if (dry) {log('⏭️ 断网预演：青龙及账号通知仅模拟'); return 'dry-run';}
  const title='Qoder每日签到';
  const body=`账号总数 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${summary.failed}，跳过 ${summary.skipped}，未确认领取 ${summary.unverified}；状态 ${summary.status}`;
  let delivered=false, failure=false;
  for (let i=0;i<accounts.length;i++) {
    const a=accounts[i]; if (!a || typeof a!=='object' || (a.enabled!==true && a.qiandao!=='是') || (only && i+1!==only)) continue;
    const text=`${body}\n账号${i+1}：${results[i]?.status || 'failure'}；Credits ${results[i]?.credits || 0}`;
    const channels=[];
    if (nonempty(a.serverchan)) channels.push(['Server酱',`https://sctapi.ftqq.com/${encodeURIComponent(a.serverchan)}.send`,{title,desp:text},d=>d.code===0]);
    if (nonempty(a.pushplus)) channels.push(['PushPlus','https://www.pushplus.plus/send',{token:a.pushplus,title,content:text,channel:'wechat',template:'txt'},d=>d.code===200]);
    if (nonempty(a.qywx)) {const key=a.qywx.includes('key=') ? a.qywx.split('key=').pop() : a.qywx; channels.push(['企业微信',`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=${encodeURIComponent(key)}`,{msgtype:'text',text:{content:text}},d=>d.errcode===0]);}
    for (const [name,url,payload,ok] of channels) {
      try {const q=await request(url,'POST',{'Content-Type':'application/json'},payload); if(q.status!==200 || !ok(q.data)) throw new Error(); log(`账号${i+1} ${name}通知成功`);}
      catch {failure=true; log(`⚠️ 账号${i+1} ${name}通知失败`);}
    }
  }
  const globalChannels=[];
  if (nonempty(process.env.PUSHPLUS_TOKEN)) globalChannels.push(['全局 PushPlus','https://www.pushplus.plus/send',
    {token:process.env.PUSHPLUS_TOKEN,title,content:body,template:'txt'},d=>d.code===200]);
  if (nonempty(process.env.BARK_URL)) globalChannels.push(['Bark',process.env.BARK_URL.replace(/\/+$/,''),{title,body,group:'Qoder'},d=>d.code===200]);
  if (nonempty(process.env.WECOM_WEBHOOK)) {
    const value=process.env.WECOM_WEBHOOK;
    const url=value.startsWith('https://') ? value : 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key='+encodeURIComponent(value);
    globalChannels.push(['全局企业微信',url,{msgtype:'text',text:{content:`${title}\n${body}`}},d=>d.errcode===0]);
  }
  if (nonempty(process.env.DINGTALK_WEBHOOK)) {
    try {
      const url=new URL(process.env.DINGTALK_WEBHOOK), secret=process.env.DINGTALK_SECRET;
      if (secret) {const timestamp=String(Date.now()); url.searchParams.set('timestamp',timestamp);
        url.searchParams.set('sign',crypto.createHmac('sha256',secret).update(`${timestamp}\n${secret}`).digest('base64'));}
      globalChannels.push(['钉钉',url.toString(),{msgtype:'text',text:{content:`${title}\n${body}`}},d=>d.errcode===0]);
    } catch {failure=true; log('⚠️ 钉钉通知地址配置无效');}
  }
  for (const [name,url,data,ok] of globalChannels) {
    try {const target=new URL(url); if (target.protocol!=='https:' || target.username || target.password) throw new Error();
      const q=await request(target,'POST',{'Content-Type':'application/json'},data);
      if (q.status!==200 || !ok(q.data)) throw new Error(); log(`✅ ${name}汇总通知成功`);
    } catch {failure=true; log(`⚠️ ${name}汇总通知失败`);}
  }
  const paths=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  for (const found of [...new Set(paths)].filter(p=>fs.existsSync(p))) {
    try {await sendQinglong(found,title,body); delivered=true;} catch {}
    if (delivered) break;
  }
  if (!delivered) failure=true;
  log(delivered ? '✅ 青龙通知已发送' : '⚠️ 青龙通知不可用或发送失败，保留业务退出码');
  return failure ? 'unavailable-or-failed' : 'sent';
}
async function main() {
  log('========== Qoder每日签到 =========='); log(`开始时间 ${stamp()}；模式 ${dry?'断网预演':'正式运行'}`);
  try {
    const args=process.argv.slice(2);
    for(let j=0;j<args.length;j++) {
      if(args[j]==='--only') {if(!args[j+1] || !/^[1-9]\d*$/.test(args[j+1])) throw new Error(); only=Number(args[++j]);}
      else if(!['--refresh-only','--no-notify'].includes(args[j])) throw new Error();
    }
    if(!only && process.env.QODER_ONLY) {if(!/^[1-9]\d*$/.test(process.env.QODER_ONLY)) throw new Error(); only=Number(process.env.QODER_ONLY);}
    action=args.includes('--refresh-only') ? 'refresh' : process.env.QODER_ACTION || 'checkin';
    if(!['checkin','refresh'].includes(action)) throw new Error();
    for (const [key,min,max] of [['QODER_WINDOW_RETRY_MAX',1,16],['QODER_WINDOW_RETRY_GAP',1,300]]) {
      if (process.env[key]!==undefined && (!/^\d+$/.test(process.env[key]) || Number(process.env[key])<min || Number(process.env[key])>max)) throw new Error();
    }
    retryMax=Number(process.env.QODER_WINDOW_RETRY_MAX || 16); retryGap=Number(process.env.QODER_WINDOW_RETRY_GAP || 90);
    const region=process.env.QODER_REGION || 'cn';
    if (!['cn','global'].includes(region)) throw new Error();
    base=region==='global' ? 'https://openapi.qoder.sh' : 'https://openapi.qoder.com.cn';
    file=process.env.QODER_ACCOUNTS_FILE || '';
    if (file || process.env.QODER_ACCOUNTS!==undefined) {
      const raw=file ? fs.readFileSync(file,'utf8') : process.env.QODER_ACCOUNTS;
      lines=raw.split(/\r?\n/).filter(x=>x.trim());
      accounts=lines.map(line=>{try{return JSON.parse(line);} catch{return null;}});
    } else {
      accounts=[...legacyAccounts(process.env.QODER_TOKENS,'cn'),...legacyAccounts(process.env.QODER_GLOBAL_TOKENS,'global')];
    }
    if (!accounts.length) throw new Error();
    if(only>accounts.length || !Number.isSafeInteger(only)) throw new Error();
  } catch {configFailure=true; log('❌ 阶段1 配置错误：请检查账号变量、私有文件及区域设置');}
  log(`账号数量 ${accounts.length}`);
  log(`任务动作 ${action==='refresh'?'仅刷新令牌':'签到'}；范围 ${only ? '账号'+only : '全部账号'}`);
  if(!configFailure) for(let i=0;i<accounts.length;i++) await one(accounts[i],i);
  const failed=results.filter(r=>r.status==='failure').length;
  const skipped=results.filter(r=>['skipped','unavailable'].includes(r.status)).length;
  const succeeded=results.filter(r=>['success','already-complete','dry-run'].includes(r.status)).length;
  // 活动未开放/关闭账号不是签到成功，不将它们当成成功退出。
  const unverified=results.filter(r=>r.status==='unavailable').length;
  const exitCode=configFailure || failed || unverified || !succeeded ? 1 : 0;
  const summary={task:'Qoder每日签到',mode:dry?'dry-run':'live',action,accounts:accounts.length,succeeded,failed,skipped,unverified,status:configFailure?'configuration-error':failed || unverified?(succeeded?'partial-failure':'failure'):exitCode?'no-verified-success':dry?'dry-run':'success',exitCode,results};
  try {summary.notification=await notifications(summary);} catch {summary.notification='unavailable-or-failed'; log('⚠️ 通知处理失败，保留业务退出码');}
  summary.elapsedMs=Date.now()-started; summary.finishedAt=stamp();
  log('--------------------------------');
  log(`任务统计：账号${summary.accounts} 成功${succeeded} 失败${failed} 跳过${skipped}；子任务成功${results.reduce((n,r)=>n+r.success,0)} 失败${results.reduce((n,r)=>n+r.failed,0)}；总耗时${summary.elapsedMs}毫秒`);
  log(`完成时间 ${summary.finishedAt}；最终状态 ${summary.status}；通知 ${summary.notification}`);
  console.log('全部处理完成');
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
  process.exitCode=exitCode;
}
main().then(()=>{process.exit(process.exitCode || 0);}).catch(()=>{log('❌ 任务内部错误');process.exit(1);});
