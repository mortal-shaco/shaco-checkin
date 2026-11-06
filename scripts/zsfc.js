// name: 掌上飞车签到与商城
// cron: 51 0,21 * * *
/**
 * name: 掌上飞车签到与商城
 * cron: 10 0,21 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 来源：chavyleung/scripts，zsfc/zsfc.js；原文署名及订阅作者 chiupam。
 * 参考：同仓库 zsfc/zsfc.treasure.js（仅会员页面格式；不合并寻宝任务）。
 * 原始使用说明：打开掌上飞车 APP，点击资讯栏签到（每日福利），再进入游戏栏的掌飞商城。
 * 原始注意事项：每月重新抓取签到活动及流水 ID；商城 Token 失效时重新进入商城获取。
 * 原始 BoxJS 订阅归属：https://raw.githubusercontent.com/chiupam/surge/main/boxjs/chiupam.boxjs.json
 * 本版不执行抓包、青龙配置上传或远程代码。依赖 json5（公开 npm 包），解析页面数据而不执行代码。
 * ZSFC_CONFIG 每行一个 JSON 对象；字段可使用原 zsfc_ 前缀或不带前缀。
 * 必需：accessToken, openid, iActivityId, iFlowId, uin, areaId, userId, token, roleId。
 * iFlowId 是查询累计签到天数的流水；奖励流水可通过 ZSFC_FLOWS 覆盖（JSON）。
 * ZSFC_SHOP 默认关闭；开启需 ZSFC_SHOP_MAX_SPEND 正整数预算，默认仅消费券。
 * ZSFC_SHOP_ALLOW_MONEY=1 才允许使用点券。永久商品购买后本地记录，阻止重复购买。
 * QINGLONG_NOTIFY 默认 auto，仅选择器明确列出本任务时推送；dry-run 只模拟通知，不联网。
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
    const identities = ["d0e6679f8cb579d7", "scripts/zsfc.js", "zsfc.js", "zsfc"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const TITLE = '掌上飞车签到与商城';
const DRY = /^(1|true|yes|on)$/i.test(process.env.ZSFC_DRY_RUN || '');
const started = Date.now();
const stats = { accounts: 0, success: 0, failed: 0, tasks: { success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, mode: DRY ? 'dry-run' : 'live' };
const defaults = {
  daily: ['1028286','1028292','1028291','1028290','1028289','1028288','1028287'],
  accumulative: {5:'1028380',10:'1028379',15:'1028378',20:'1028377',25:'1028376'},
  dailyTask: {'查看动态':'1028557','浏览背包':'1028556','游戏活跃':'1028555'},
  weeklyTask: {'进行游戏':'1028554','花费点券':'1028553'}
};
let flows, shopEnabled, budget, allowMoney;
const stamp = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = s => console.log(`[${stamp()}] ${s}`);
const on = v => /^(1|true|yes|on)$/i.test(String(v || ''));
function fail(s) { throw new Error(s); }
function json(s) { try { return JSON.parse(s); } catch { fail('响应不是有效 JSON'); } }
function assert(condition, message) { if (!condition) fail(message); }
function identity(a, body) {
  for (const key of ['nickname','nickName','username','displayName','uid','roleName','sRoleName']) {
    if (typeof body?.[key] === 'string' || typeof body?.[key] === 'number') {
      let value = String(body[key]);
      // 不输出任何与凭据相同的值或电话号码；身份字段按官方原值显示。
      if ([a.accessToken,a.openid,a.token].some(v => typeof v === 'string' && v && value.includes(v)) || /1[3-9]\d{9}/.test(value) || /[\r\n\x00-\x1f]/.test(value)) continue;
      log(`官方身份 ${key}：${value}`);
    }
  }
}
function request(url, {method='GET', body, cookie, referer} = {}) {
  assert(!DRY, 'dry-run 禁止网络请求');
  return new Promise((resolve, reject) => {
    let settled = false;
    const done = (err, value) => { if (settled) return; settled = true; clearTimeout(timer); err ? reject(err) : resolve(value); };
    const data = body ? new URLSearchParams(body).toString() : '';
    const headers = {'User-Agent':'Mozilla/5.0', ...(cookie ? {Cookie:cookie} : {}), ...(referer ? {Referer:referer} : {})};
    if (method === 'POST') Object.assign(headers, {'Content-Type':'application/x-www-form-urlencoded', 'Content-Length':Buffer.byteLength(data)});
    const req = https.request(url, {method, headers}, res => {
      if (res.statusCode < 200 || res.statusCode >= 300) { res.resume(); return done(new Error(`HTTP 状态异常（${res.statusCode}）`)); }
      let size = 0; const chunks = [];
      res.on('data', chunk => { size += chunk.length; if (size > 2*1024*1024) { done(new Error('响应超过大小限制')); req.destroy(); } else chunks.push(chunk); });
      res.on('end', () => done(null, Buffer.concat(chunks).toString('utf8')));
      res.on('error', () => done(new Error('响应读取失败')));
      res.on('aborted', () => done(new Error('响应意外中断')));
    });
    const timer = setTimeout(() => { done(new Error('请求超时')); req.destroy(); }, 15000);
    req.on('error', () => done(new Error('网络请求失败')));
    req.end(data);
  });
}
const url = (base, query) => `${base}?${new URLSearchParams(query)}`;
const cookie = a => `access_token=${a.accessToken}; acctype=qc; appid=1105330667; openid=${a.openid}`;
async function ams(a, id, extra={}) {
  const body = json(await request(url('https://comm.ams.game.qq.com/ams/ame/amesvr', {sServiceType:'speed',iActivityId:a.iActivityId}), {
    method:'POST', cookie:cookie(a), body:{iActivityId:a.iActivityId,iFlowId:id,g_tk:'1842395457',...extra}
  }));
  identity(a, body); identity(a, body.modRet);
  return body;
}
function codeOK(b) {
  // AMS 仅接受明确的零业务码；拒绝缺码、未知码及子流程失败。
  const c = b.ret ?? b.iRet;
  return c !== undefined && String(c) === '0' && (b.flowRet?.iRet === undefined || String(b.flowRet.iRet) === '0');
}
async function gift(a, id, optional=false) {
  const b = await ams(a, id);
  const msg = String(b.msg || '') + String(b.flowRet?.sMsg || '');
  if (/已经领取|已经签到|已领取|已签到/.test(msg)) return {status:'alreadyComplete', detail:'官方确认已完成'};
  if (optional && /不满足/.test(msg)) return {status:'skipped', detail:'官方提示条件不满足，未领取'};
  assert(codeOK(b) && typeof b.modRet?.sPackageName === 'string' && b.modRet.sPackageName.trim(), '奖励领取未获明确成功确认');
  return {status:'success', detail:'业务码成功且返回奖励名称，领取成功'};
}
function normalize(raw) {
  assert(raw && typeof raw === 'object' && !Array.isArray(raw), '账号必须是 JSON 对象');
  const a = {};
  for (const k of ['accessToken','openid','iActivityId','iFlowId','uin','areaId','userId','token','roleId']) a[k] = String(raw[k] ?? raw[`zsfc_${k}`] ?? '');
  // 兼容上游另行保存的 flow/activity 配置，拆分只针对这两个字段。
  if ((!a.iFlowId || !a.iActivityId) && process.env.ZSFC_iFlowdId) {
    const p = process.env.ZSFC_iFlowdId.indexOf('/');
    if (p > 0) { a.iFlowId ||= process.env.ZSFC_iFlowdId.slice(0,p); a.iActivityId ||= process.env.ZSFC_iFlowdId.slice(p+1); }
  }
  for (const k of Object.keys(a)) assert(a[k] && !/[\r\n\x00-\x1f]/.test(a[k]), `缺少或无效字段：${k}`);
  assert(!/[;\s]/.test(a.accessToken+a.openid), '登录凭据含非法字符');
  for (const k of ['iActivityId','iFlowId','areaId']) assert(/^\d+$/.test(a[k]), `字段格式错误：${k}`);
  return a;
}
function validateSettings() {
  flows = JSON.parse(JSON.stringify(defaults));
  if (process.env.ZSFC_FLOWS) {
    let v; try { v=JSON.parse(process.env.ZSFC_FLOWS); } catch { fail('ZSFC_FLOWS 必须是 JSON 对象'); }
    assert(v && typeof v==='object' && !Array.isArray(v), '流水设置格式错误');
    for (const k of Object.keys(v)) {
      assert(Object.hasOwn(defaults,k), '未知流水分组');
      if (k==='daily') { assert(Array.isArray(v[k]) && v[k].length===7, 'daily 需周日至周六七个流水'); flows[k]=v[k]; }
      else { assert(v[k] && typeof v[k]==='object' && !Array.isArray(v[k]), '流水分组需为对象'); flows[k]={...flows[k],...v[k]}; }
    }
  }
  for (const group of Object.values(flows)) for (const id of Object.values(group)) assert(/^\d+$/.test(String(id)), '流水编号必须为数字');
  shopEnabled = on(process.env.ZSFC_SHOP ?? process.env.zsfc_shop);
  allowMoney = on(process.env.ZSFC_SHOP_ALLOW_MONEY);
  budget = Number(process.env.ZSFC_SHOP_MAX_SPEND);
  if (shopEnabled) assert(Number.isSafeInteger(budget) && budget>0, '开启购物必须设置 ZSFC_SHOP_MAX_SPEND 正整数预算');
}
function pageObject(html, name) {
  const match = html.match(new RegExp(`window\\.${name}\\s*=\\s*eval\\('((?:\\\\.|[^'\\\\])*)'\\)\\s*;`));
  assert(match, '会员页面结构变化');
  // JSON5 解码外层 JS 字符串，再解析内部对象；从不运行响应代码。
  let parse; try { parse = require('json5').parse; } catch { fail('缺少公开依赖 json5，请通过青龙依赖管理安装'); }
  try { let text = parse(`'${match[1]}'`).trim(); if (text.startsWith('(') && text.endsWith(')')) text=text.slice(1,-1); return parse(text); }
  catch { fail('会员数据无法安全解析'); }
}
async function pack(a) {
  const html = await request(url('https://bang.qq.com/app/speed/mall/main2', {areaId:a.areaId,accessToken:a.accessToken,token:a.token,uin:a.uin,userId:a.userId}));
  const money = html.match(/<b\s+id=["']super_money["']\s*>\s*(\d+)\s*<\/b>/);
  const coupons = html.match(/<b\s+id=["']coupons["']\s*>\s*(\d+)\s*<\/b>/);
  assert(money && coupons, '商城余额不可读，请重新抓取商城参数');
  const result = {money:Number(money[1]),coupons:Number(coupons[1])};
  assert(Object.values(result).every(Number.isSafeInteger),'商城余额格式异常'); return result;
}
function plan(item, balance, vip) {
  const counted = item.szItems?.[0]?.ItemNum !== '';
  const raw = counted ? item.szItems?.[0]?.ItemNum : item.szItems?.[0]?.ItemAvailPeriod;
  assert(typeof raw==='string' && Array.isArray(item.szPrices) && item.szPrices.length, '商品规格缺失');
  const values=raw.split(',').filter(Boolean).map(x=> x==='-1'?999: Number(x)/(counted?1:24));
  const rebate=vip ? Number(item.iMemeberRebate)/100 : 1;
  assert(rebate>0 && rebate<=1 && values.length===item.szPrices.length, '商品价格结构异常');
  const specs=item.szPrices.map((p,idx)=>({idx,count:values[idx],cost:Number(p.SuperMoneyPrice)*rebate})).sort((a,b)=>b.count-a.count);
  assert(specs.every(s=>Number.isFinite(s.cost)&&s.cost>0&&Number.isFinite(s.count)&&s.count>0), '商品价格或数量无效');
  const now=new Date(); const monthEnd = new Date(now.getFullYear(), now.getMonth()+1,0).getDate()-now.getDate()<2;
  let remaining=Math.min(budget,balance.coupons+(allowMoney&&monthEnd?balance.money:0));
  const actions=[];
  for (const s of specs) {
    if (s.count===999) { if (remaining>=s.cost) return [{...s,id:item.iId}]; continue; }
    const n=Math.floor(remaining/s.cost);
    assert(actions.length+n<=1000,'购买请求过多，请降低预算');
    for(let i=0;i<n;i++) actions.push({...s,id:item.iId});
    remaining-=n*s.cost;
  }
  // 上游允许少量消费券搭配点券凑最低档；必须显式允许点券并受预算限制。
  const cheapest=[...specs].sort((a,b)=>a.cost-b.cost)[0];
  const spent=actions.reduce((n,s)=>n+s.cost,0);
  if (!monthEnd && counted && allowMoney && remaining>0 && remaining<cheapest.cost && balance.coupons+balance.money-spent>=cheapest.cost && spent+cheapest.cost<=budget && cheapest.count!==999) actions.push({...cheapest,id:item.iId});
  return actions;
}
async function shop(a, stage, vip) {
  const before = await stage('查询商城余额', async()=> { const b=await pack(a); log(`余额：点券 ${b.money}，消费券 ${b.coupons}`); return {status:'success',value:b}; });
  if (!before) return;
  if (new Date().getHours()<16) { await stage('购物时段检查', async()=>({status:'skipped',detail:'每天16点后购买'})); return; }
  if (vip===undefined) return;
  const name=process.env.ZSFC_SHOP_NAME || process.env.zsfc_bang_shopname || ['进气系统+1','点火装置+1','引擎装置+1'][new Date().getMonth()%3];
  const actions = await stage('搜索商品并核算预算', async()=> {
    const b=json(await request(url('https://bang.qq.com/app/speed/mall/search',{uin:a.uin,userId:a.userId,token:a.token,start:'0',paytype:'1',order:'2',text:name}),{method:'POST',referer:'https://bang.qq.com/app/speed/mall/main2'}));
    assert(Array.isArray(b.data), '商品搜索响应异常');
    const item=b.data.find(x=>x.szName===name); assert(item && /^\d+$/.test(String(item.iId)), '未找到完整名称匹配的商品');
    const p=plan(item,before,vip); return {status:'success',detail:`计划购买 ${p.length} 笔，预算上限 ${budget}`,value:p};
  });
  if (!actions) return;
  if (!actions.length) { await stage('余额检查',async()=>({status:'skipped',detail:'授权预算不足，未购买'})); return; }
  const statePath=process.env.ZSFC_SHOP_STATE_FILE || path.join(__dirname,'.zsfc-shop-state.json');
  const key=crypto.createHash('sha256').update(`${a.openid}:${a.roleId}`).digest('hex');
  let state={};
  const ready=await stage('检查永久商品防重记录',async()=>{
    if(fs.existsSync(statePath)) { try {state=JSON.parse(fs.readFileSync(statePath,'utf8'));} catch {fail('购买状态文件损坏，停止购物');} }
    assert(state && typeof state==='object' && !Array.isArray(state),'购买状态文件格式错误');
    return {status:'success',value:true};
  });
  if(!ready) return;
  let spent=0;
  for (const s of actions) {
    if(state[`${key}:${s.id}`]) { await stage('永久商品防重复购买',async()=>({status:'skipped',detail:'已有永久购买记录，停止购物'})); break; }
    const ok=await stage('购买商品',async()=> {
      assert(spent+s.cost<=budget, '购买超出预算');
      const current=await pack(a);
      assert(current.coupons+(allowMoney?current.money:0)>=s.cost, '授权余额不足，停止购买');
      if(s.count===999) { state[`${key}:${s.id}`]='pending'; fs.writeFileSync(statePath,JSON.stringify(state),{mode:0o600}); }
      const b=json(await request('https://bang.qq.com/app/speed/mall/getPurchase',{method:'POST',referer:'https://bang.qq.com/app/speed/mall/detail2',body:{areaId:a.areaId,token:a.token,userId:a.userId,uin:a.uin,pay_type:'1',commodity_id:s.id,price_idx:s.idx}}));
      assert(b.res!==undefined && String(b.res)==='0','购买未获明确成功确认，不自动重试');
      spent+=s.cost;
      if(s.count===999) { state[`${key}:${s.id}`]='purchased'; fs.writeFileSync(statePath,JSON.stringify(state),{mode:0o600}); }
      return {status:'success',detail:`购买确认成功，数量或天数 ${s.count===999?'永久':s.count}`,value:true};
    });
    if(!ok) break;
  }
  await stage('复查剩余余额',async()=>{const b=await pack(a);log(`剩余：点券 ${b.money}，消费券 ${b.coupons}`);return {status:'success'};});
}
async function account(line, index) {
  const begin=Date.now(); const counts={success:0,alreadyComplete:0,skipped:0,failed:0}; let number=0;
  async function stage(name, action) {
    const t=Date.now(); const n=++number; log(`账号 ${index} · 阶段 ${n} ${name} 开始`);
    try { const r=await action(); counts[r.status]++; stats.tasks[r.status]++; log(`账号 ${index} · 阶段 ${n} ${name}：${r.status} ${r.detail||''}（${Date.now()-t}ms）`);return r.value; }
    catch(e) { counts.failed++;stats.tasks.failed++;log(`账号 ${index} · 阶段 ${n} ${name}：❌ ${safeError(e)}（${Date.now()-t}ms）`); }
  }
  const a=await stage('校验账号参数', async()=>{let raw;try{raw=JSON.parse(line);}catch{fail('账号行必须是有效 JSON 对象');}return {status:'success',value:normalize(raw)};});
  if (a) {
    if(DRY) {
      for(const name of ['查询会员状态','每日签到','查询累计签到与奖励','浏览背包与领取日常奖励','周末奖励','可选商城与预算检查']) await stage(name,async()=>({status:'skipped',detail:'DRY_RUN_OK：仅检查配置，不请求业务或通知网络'}));
    } else {
  const vip = await stage('查询会员状态', async()=> {
    const html=await request(url('https://bang.qq.com/app/speed/treasure/index',{roleId:a.roleId,uin:a.uin,areaId:a.areaId}));
    const b=pageObject(html,'userInfo'); identity(a,b);
    assert(b.vip_flag!==undefined && /^\d+$/.test(String(b.vip_flag)), '会员标记缺失');
    return {status:'success',detail:Number(b.vip_flag)?'紫钻会员':'普通会员',value:Number(b.vip_flag)!==0};
  });

      const day=new Date().getDay();
      await stage('每日签到',()=>gift(a,flows.daily[day]));
      const days=await stage('查询累计签到',async()=> {const b=await ams(a,a.iFlowId,{witchDay:'1'});assert(codeOK(b) && /^\d+$/.test(String(b.modRet?.sOutValue5)), '累计签到查询未获成功确认');log(`累计签到 ${b.modRet.sOutValue5} 天`);return {status:'success',value:Number(b.modRet.sOutValue5)};});
      if(days!==undefined) for(const [n,id] of Object.entries(flows.accumulative)) if(Number(n)<=days) await stage(`累计 ${n} 天奖励`,()=>gift(a,id,true));
      await stage('浏览背包',async()=> {
        const b=json(await request('https://mwegame.qq.com/yoyo/dnf/phpgameproxypass',{method:'POST',body:{uin:a.uin,areaId:a.areaId,userId:a.userId,token:a.token,service:'dnf_getspeedknapsack',cGameId:'1003'}}));
        const c=b.ret ?? b.code ?? b.result ?? b.res;
        assert(c!==undefined && String(c)==='0','背包接口未获明确成功确认');identity(a,b.data);return {status:'success',detail:'背包浏览业务码成功'};
      });
      for(const [name,id] of Object.entries(flows.dailyTask)) await stage(`每日奖励：${name}`,()=>gift(a,id,true));
      if(day===0||day===6) for(const [name,id] of Object.entries(flows.weeklyTask)) await stage(`周末奖励：${name}`,()=>gift(a,id,true));
      else await stage('周末奖励',async()=>({status:'skipped',detail:'非周末'}));
      if(shopEnabled) await shop(a,stage,vip); else await stage('商城购买',async()=>({status:'skipped',detail:'购买未开启'}));
    }
  }
  const ok=counts.failed===0; stats[ok?'success':'failed']++;
  log(`账号 ${index} 统计：总任务 ${number}，成功 ${counts.success}，已完成 ${counts.alreadyComplete}，跳过 ${counts.skipped}，失败 ${counts.failed}，耗时 ${Date.now()-begin}ms`);
}
// 错误均使用本地固定信息；不输出异常对象、路径、URL 或服务端原始响应。
function safeError(e) { return e && e.message && /^(响应不是|HTTP 状态|响应超过|响应读取|响应意外|请求超时|网络请求|奖励领取|缺少或|登录凭据|字段格式|ZSFC_|开启购物|未知流水|流水|daily |会员|缺少公开依赖|商城|商品|购买|授权|未找到|累计签到|背包接口|账号行|账号必须)/.test(e.message) ? e.message : '操作失败，请检查配置、依赖与接口契约'; }
function notifySelected() {
  const flag=(process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if(['0','false','no','off'].includes(flag))return false;
  if(on(flag))return true;
  const selectors=(process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const names=['d0e6679f8cb579d7','zsfc/zsfc.js','zsfc.js','candidate.js',path.basename(__filename)];
  return selectors.some(s=> { const re=new RegExp('^'+s.split('*').map(x=>x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('.*')+'$'); return names.some(n=>re.test(n)); });
}
async function notify(status) {
  if(!notifySelected()) return '未选中推送';
  if(DRY) return 'dry-run 模拟通知，未联网';
  const body=`状态：${status}\n账号总数：${stats.accounts}，成功：${stats.success}，失败：${stats.failed}\n子任务：成功 ${stats.tasks.success}，已完成 ${stats.tasks.alreadyComplete}，跳过 ${stats.tasks.skipped}，失败 ${stats.tasks.failed}`;
  for(const file of [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean)) {
    if(!fs.existsSync(file))continue;
    // 独立子进程限制通知耗时；清除业务凭据环境，保留青龙通知通道配置。
    const {spawn}=require('node:child_process');
    const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>!/^zsfc_/i.test(k)));
    return await new Promise(resolve=>{
      const p=spawn(process.execPath,['-e',"Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))",file,TITLE,body],{env,stdio:'ignore'});
      const timer=setTimeout(()=>{p.kill('SIGKILL');resolve('通知超时，保留业务退出码');},20000);
      p.on('error',()=>{clearTimeout(timer);resolve('通知启动失败，保留业务退出码');});
      p.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':'通知失败，保留业务退出码');});
    });
  }
  return '通知模块不可用，保留业务退出码';
}
async function main() {
  log(`🏎️ ${TITLE} | 开始时间 ${new Date(started).toISOString()} | 模式 ${stats.mode}`);
  let configError=false;
  try {
    const lines=(process.env.ZSFC_CONFIG || '').split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
    stats.accounts=lines.length; log(`账号数量：${lines.length}`);
    assert(lines.length,'ZSFC_CONFIG 未配置，每行一个账号 JSON');
    validateSettings();
    for(let i=0;i<lines.length;i++) await account(lines[i],i+1);
  } catch(e) { configError=true;stats.tasks.failed++;log(`❌ 配置错误：${safeError(e)}`); }
  const code=configError||stats.failed||stats.tasks.failed?1:0;
  const status=configError?'configuration-error':stats.failed?(stats.success?'partial-failure':'failure'):DRY?'dry-run':'success';
  let notification; try {notification=await notify(status);} catch {notification='通知失败，保留业务退出码';}
  log('----------------------------------------');
  log(`最终状态：${status}；账号总数 ${stats.accounts}，成功 ${stats.success}，失败 ${stats.failed}`);
  log(`子任务统计：成功 ${stats.tasks.success}，已完成 ${stats.tasks.alreadyComplete}，跳过 ${stats.tasks.skipped}，失败 ${stats.tasks.failed}`);
  log(`通知：${notification}；完成时间 ${new Date().toISOString()}；总耗时 ${Date.now()-started}ms`);
  console.log('TASK_SUMMARY='+JSON.stringify({...stats,status,notification,exitCode:code,elapsedMs:Date.now()-started}));
  process.exitCode=code;
}
main();
