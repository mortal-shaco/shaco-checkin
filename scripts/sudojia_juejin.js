// name: 稀土掘金每日签到
// cron: 43 2 * * *
/**
 * name: 稀土掘金每日签到
 * cron: 5 10 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Based on sudojia/AutoTaskScript, src/web/sudojia_juejin.js
 * Author: Telegram@sudojia — https://blog.imzjw.cn
 * 上游提交：4a55327baed0321bdf95802a75cc8363cae118b0
 * JUEJIN_COOKIE：每行 sessionid#签到请求的原始查询串；仅在首个 # 分隔。
 * 登录 https://juejin.cn，在开发者工具 Application/Cookies 取得 sessionid；
 * Network 中手动签到，复制 /growth_api/v1/check_in 的查询串（不含 ?）。
 * 查询串须含 uuid、spider、msToken、a_bogus；签名可能过期，失效须重新抓取。
 * 不自动生成签名，不下载依赖。Node.js >=18，仅使用内置库。
 * JUEJIN_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * 合并来源：huwangkeji/juejin_checkin，juejin_checkin.js，作者 CodeBuddy，原版本 1.0.0。
 * 原描述：掘金社区每日签到 + 免费抽奖 + 沾喜气 + Bug消除，支持Cookie自动签到。
 * 原 namespace：https://juejin.cn；原定时 30 6 * * *，本维护任务保留 5 10 * * *。
 * 合并参考：同仓库 juejin-extension/background.js、content.js、popup.js（参数获取）。
 * 所有合并内容按 GPL-3.0 维护；保留上述原作者及来源署名。
 * 也支持完整 Cookie#原始查询串，仍只在第一个 # 分隔；查询串不可混用账号。
 * 兼容旧配置 JUEJIN_COOKIE_2 至 JUEJIN_COOKIE_5（各变量内仍每行一账号）。
 * 旧完整 Cookie 配置可搭配 JUEJIN_AID、JUEJIN_UUID、JUEJIN_MSTOKEN、
 * JUEJIN_A_BOGUS；附加账号使用同名 _2 至 _5 后缀，aid 可继承主账号。
 * 原 spider 固定为 0，旧配置仍如此；推荐改为合并的原始查询串以保留签名。
 * Network 中复制真实请求的完整 Cookie，不依赖扩展 document.cookie（无法读取 HttpOnly）。
 * 签名有效期不保证；只能获取自己账号请求，不记录或分享任何凭据。
 * JUEJIN_FREE_LOTTERY=1、JUEJIN_DIP_LUCKY=1、JUEJIN_BUG_FIX=1 分别启用新动作，
 * 均默认关闭；抽奖只在明确剩余免费次数大于零时提交一次，绝不自动付费抽奖。
 * JUEJIN_LUCKY_QUERY=1 默认查询幸运值；设 0 可关闭新增查询。
 * JUEJIN_NOTIFY=false 兼容关闭通知，全局 QINGLONG_NOTIFY 优先关闭。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["f86741e6210934e9", "scripts/sudojia_juejin.js", "sudojia_juejin.js", "sudojia_juejin"];
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
const {spawn} = require('node:child_process');
const started = Date.now();
const dry = process.env.JUEJIN_DRY_RUN === '1';
const title = '稀土掘金每日签到';
const sources = [
  [process.env.JUEJIN_COOKIE, ''],
  [process.env.JUEJIN_COOKIE_2, '_2'],
  [process.env.JUEJIN_COOKIE_3, '_3'],
  [process.env.JUEJIN_COOKIE_4, '_4'],
  [process.env.JUEJIN_COOKIE_5, '_5']
];
const lines = sources.flatMap(([value, suffix]) => (value || '').split(/\r?\n/)
  .map(line => line.trim()).filter(Boolean).map(line => ({line, suffix})));
const legacyKeys = {
  "": {
    "aid": "JUEJIN_AID",
    "uuid": "JUEJIN_UUID",
    "msToken": "JUEJIN_MSTOKEN",
    "a_bogus": "JUEJIN_A_BOGUS"
  },
  "_2": {
    "aid": "JUEJIN_AID_2",
    "uuid": "JUEJIN_UUID_2",
    "msToken": "JUEJIN_MSTOKEN_2",
    "a_bogus": "JUEJIN_A_BOGUS_2"
  },
  "_3": {
    "aid": "JUEJIN_AID_3",
    "uuid": "JUEJIN_UUID_3",
    "msToken": "JUEJIN_MSTOKEN_3",
    "a_bogus": "JUEJIN_A_BOGUS_3"
  },
  "_4": {
    "aid": "JUEJIN_AID_4",
    "uuid": "JUEJIN_UUID_4",
    "msToken": "JUEJIN_MSTOKEN_4",
    "a_bogus": "JUEJIN_A_BOGUS_4"
  },
  "_5": {
    "aid": "JUEJIN_AID_5",
    "uuid": "JUEJIN_UUID_5",
    "msToken": "JUEJIN_MSTOKEN_5",
    "a_bogus": "JUEJIN_A_BOGUS_5"
  }
};
const options = {};
let configError = false;
for (const [key, fallback] of [['JUEJIN_FREE_LOTTERY','0'], ['JUEJIN_DIP_LUCKY','0'],
  ['JUEJIN_BUG_FIX','0'], ['JUEJIN_LUCKY_QUERY','1']]) {
  const value = process.env[key] ?? fallback;
  if (!['0','1'].includes(value)) configError = true;
  options[key] = value === '1';
}
const results = [];
const time = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = s => console.log(`[${time()}] ${s}`);
function parse(input) {
  const {line, suffix} = input;
  const n = line.indexOf('#');
  let credential, query;
  if (n >= 1) {
    credential = line.slice(0,n); query = line.slice(n+1);
  } else if (n === -1) {
    credential = line;
    const q = new URLSearchParams();
    const aid = process.env[legacyKeys[suffix].aid] || process.env.JUEJIN_AID || '2608';
    q.set('aid',aid); q.set('spider','0');
    for (const key of ['uuid','msToken','a_bogus']) {
      const value = process.env[legacyKeys[suffix][key]];
      if (!value || /[\r\n\x00-\x1f\x7f]/.test(value)) throw new Error('旧配置缺少本账号签名参数或格式错误，请改用合并参数');
      q.set(key,value);
    }
    query = q.toString();
  } else throw new Error('参数格式错误：需要 sessionid或完整Cookie#原始查询串');
  if (!credential || /[\x00-\x1f\x7f]/.test(credential) || !query || /[\s#\x00-\x1f\x7f]/.test(query)) throw new Error('凭据格式不合法');
  let cookie;
  if (/(^|;\s*)(sessionid|sessionid_ss|sid_tt)=/.test(credential) || credential.includes(';')) {
    const fields = credential.split(';').map(x=>x.trim()).filter(Boolean);
    if (!fields.length || fields.some(x => !/^[!#$%&'*+.^_`|~0-9A-Za-z-]+=[\x20-\x7e]*$/.test(x)) ||
      !fields.some(x => /^(sessionid|sessionid_ss|sid_tt)=.+$/.test(x))) throw new Error('完整 Cookie 缺少有效登录会话');
    cookie = credential;
  } else {
    if (/[\s;]/.test(credential)) throw new Error('会话值格式不合法');
    cookie = `sid_tt=${credential}; sessionid=${credential}; sessionid_ss=${credential}`;
  }
  const q = new URLSearchParams(query);
  for (const key of ['uuid','spider','msToken','a_bogus']) if (!q.get(key) || q.getAll(key).length !== 1) throw new Error(`查询串缺少或重复 ${key}`);
  if (q.has('aid') && (q.getAll('aid').length !== 1 || q.get('aid') !== '2608')) throw new Error('查询串 aid 必须为 2608');
  return {cookie, query:(q.has('aid') ? '' : 'aid=2608&') + query};
}
function request(account, endpoint, method='GET', body) {
  return new Promise((resolve,reject) => {
    if (dry) return reject(new Error('断网预演禁止网络请求'));
    const payload = body === undefined ? undefined : JSON.stringify(body);
    let req;
    try { req = https.request('https://api.juejin.cn'+endpoint, {method, headers:{
      Accept:'application/json', 'Accept-Encoding':'identity', 'Content-Type':'application/json',
      Referer:'https://juejin.cn/', Origin:'https://juejin.cn',
      'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
      Cookie:account.cookie,
      ...(payload ? {'Content-Length':Buffer.byteLength(payload)} : {})
    }}, res => {
      let size=0; const chunks=[];
      res.on('data', chunk => {size+=chunk.length; if(size>1048576) req.destroy(new Error('响应超过大小限制')); else chunks.push(chunk);});
      res.on('error', () => reject(new Error('响应传输失败')));
      res.on('end', () => {
        if(res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP 状态 ${res.statusCode}`));
        try {resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));} catch {reject(new Error('响应不是有效 JSON'));}
      });
    });
    } catch { return reject(new Error('请求参数或请求头不合法')); }
    const timer=setTimeout(() => req.destroy(new Error('请求超时')),15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    req.end(payload);
  });
}
function checked(r) {
  if (!r || r.err_no !== 0) throw new Error(r && r.err_no === 403 ? '登录失效，请重新获取凭据' : '业务接口未确认成功');
  return r.data;
}
function number(v) {if(typeof v !== 'number' || !Number.isFinite(v) || v<0) throw new Error('响应数值字段不符合预期'); return v;}
async function runAccount(line,index) {
  const begin=Date.now(), stat={index,total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  let account, status;
  const stages=[
    ['登录与今日签到状态',async()=>{account=parse(line); const d=checked(await request(account,'/growth_api/v1/get_today_status')); if(typeof d !== 'boolean') throw new Error('今日状态字段不符合预期'); status=d; return d?'今日已签到':'今日尚未签到';}],
    ['账号昵称',async()=>{const d=checked(await request(account,'/user_api/v1/user/get_info_pack?aid=2608','POST',{pack_req:{user_counter:true,user_growth_info:true,user:true}})); const name=d?.user_basic?.user_name; if(typeof name!=='string'||!name) throw new Error('未返回账号昵称'); return `账号昵称：${JSON.stringify(name)}`;}],
    ['每日签到',async()=>{if(status) return {already:true,text:'今日已签到'}; const r=await request(account,'/growth_api/v1/check_in?'+account.query,'POST'); if(r?.err_no===15001){if(checked(await request(account,'/growth_api/v1/get_today_status')) !== true) throw new Error('重复签到提示未通过状态复核'); return {already:true,text:'今日已签到（状态复核成功）'};} const d=checked(r); return `签到成功，获得 ${number(d?.incr_point)} 矿石`;}],
    ['矿石余额',async()=>`当前矿石数：${number(checked(await request(account,'/growth_api/v1/get_cur_point?'+account.query)))}`],
    ['签到天数',async()=>{const d=checked(await request(account,'/growth_api/v1/get_counts?aid=2608')); return `已连续签到${number(d?.cont_count)}天、累计签到${number(d?.sum_count)}天`;}]
    ,['免费抽奖',async()=>{
      if (!options.JUEJIN_FREE_LOTTERY) return {skipped:true,text:'默认关闭；JUEJIN_FREE_LOTTERY=1 启用'};
      const d=checked(await request(account,'/growth_api/v1/lottery_config/get?'+account.query));
      const free=number(d?.free_count);
      if (!Number.isInteger(free)) throw new Error('免费次数字段不符合预期');
      if (free===0) return {already:true,text:'免费次数已用完，不提交抽奖'};
      const result=checked(await request(account,'/growth_api/v1/lottery/draw?'+account.query,'POST',{}));
      if(typeof result?.lottery_name !== 'string' || !result.lottery_name) throw new Error('抽奖未返回奖品名称，不重试以免消耗矿石');
      return `免费抽奖成功，奖品：${JSON.stringify(result.lottery_name)}`;
    }],
    ['沾喜气',async()=>{
      if (!options.JUEJIN_DIP_LUCKY) return {skipped:true,text:'默认关闭；JUEJIN_DIP_LUCKY=1 启用'};
      const d=checked(await request(account,'/growth_api/v1/lottery_history/global_big?'+account.query,'POST',{page_no:1,page_size:5}));
      if (!Array.isArray(d?.lotteries)) throw new Error('幸运用户列表字段不符合预期');
      if (!d.lotteries.length) return {skipped:true,text:'暂无可沾喜气的用户'};
      const id=d.lotteries[0]?.history_id;
      if (!((typeof id==='string' && id) || (typeof id==='number' && Number.isFinite(id)))) throw new Error('幸运记录编号不符合预期');
      const result=checked(await request(account,'/growth_api/v1/lottery_lucky/dip_lucky?'+account.query,'POST',{lottery_history_id:id}));
      return `沾喜气成功，获得幸运值：${number(result?.dip_value)}`;
    }],
    ['Bug 消除',async()=>{
      if (!options.JUEJIN_BUG_FIX) return {skipped:true,text:'默认关闭；JUEJIN_BUG_FIX=1 启用'};
      const d=checked(await request(account,'/growth_api/v1/bugfix/not_collect?'+account.query));
      if (!Array.isArray(d)) throw new Error('未收集 Bug 列表字段不符合预期');
      if (!d.length) return {already:true,text:'暂无 Bug 可消除'};
      const bug=d[0]?.bug_type;
      if (!((typeof bug==='string' && bug) || (typeof bug==='number' && Number.isFinite(bug)))) throw new Error('Bug 类型字段不符合预期');
      checked(await request(account,'/growth_api/v1/bugfix/collect?'+account.query,'POST',{bug_type:bug}));
      const after=checked(await request(account,'/growth_api/v1/bugfix/not_collect?'+account.query));
      if (!Array.isArray(after) || after.some(x=>x?.bug_type===bug)) throw new Error('Bug 消除未通过状态复核');
      return 'Bug 消除成功（状态复核通过）';
    }],
    ['幸运值查询',async()=>{
      if (!options.JUEJIN_LUCKY_QUERY) return {skipped:true,text:'JUEJIN_LUCKY_QUERY=0 已关闭新增查询'};
      const d=checked(await request(account,'/growth_api/v1/lottery_lucky/my_lucky?'+account.query,'POST',{}));
      return `当前幸运值：${number(d?.total_value)}`;
    }]
  ];
  stat.total=stages.length;
  let valid=true;
  for(let i=0;i<stages.length;i++) {
    const t=Date.now(); log(`账号 ${index} 阶段 ${i+1}/${stages.length} ${stages[i][0]}`);
    try {
      if(i===0 && configError) throw new Error('动作开关配置错误，禁止所有请求');
      if(!valid){stat.skipped++; log('⏭️ 登录或配置检查失败，跳过'); continue;}
      if(dry){if(i===0) account=parse(line); stat.skipped++; log('⏭️ DRY_RUN：参数检查通过，不发送请求'); continue;}
      const r=await stages[i][1](); if(r?.skipped) stat.skipped++; else if(r?.already) stat.alreadyComplete++; else stat.success++;
      log(`${r?.skipped?'⏭️':r?.already?'☑️':'✅'} ${typeof r==='string'?r:r.text}`);
    } catch(e) {stat.failed++; if(i===0) valid=false; log(`❌ ${e instanceof Error ? e.message : '阶段执行失败'}`);}
    finally {log(`账号 ${index} 阶段 ${i+1} 耗时 ${Date.now()-t}ms`);}
  }
  stat.durationMs=Date.now()-begin; stat.status=stat.failed?'failure':dry?'dry-run':'success'; results.push(stat);
  log(`账号 ${index} 统计：总任务 ${stat.total}，成功 ${stat.success}，已完成 ${stat.alreadyComplete}，跳过 ${stat.skipped}，失败 ${stat.failed}，耗时 ${stat.durationMs}ms`);
}
async function notify(body) {
  if(/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY||'1') || process.env.JUEJIN_NOTIFY === 'false') return '已关闭';
  if(dry) return '断网预演：通知内容已生成，跳过投递';
  const candidates=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=candidates.find(p=>fs.existsSync(p));
  if(!file) return '不可用：未找到 sendNotify.js';
  return new Promise(resolve=>{
    const child=spawn(process.execPath,['-e','Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))',file,title,body],{stdio:'ignore'});
    const timer=setTimeout(()=>child.kill('SIGKILL'),20000);
    child.on('error',()=>{clearTimeout(timer);resolve('投递失败');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已投递':'投递失败或超时');});
  });
}
(async()=>{
  log(`========== ${title} ==========`); log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${lines.length}`);
  if(configError) log('❌ 配置错误：动作开关仅支持 0 或 1，所有请求已阻止');
  if(!lines.length) log('❌ 配置错误：JUEJIN_COOKIE 未提供账号');
  for(let i=0;i<lines.length;i++) await runAccount(lines[i],i+1);
  const failed=results.filter(r=>r.failed>0).length;
  const exitCode=failed||!lines.length||configError?1:0;
  const summary={task:title,mode:dry?'dry-run':'live',accounts:lines.length,success:results.filter(r=>r.status==='success').length,failed,dryRun:results.filter(r=>r.status==='dry-run').length,status:exitCode?(configError||!lines.length?'configuration-error':'failure'):dry?'dry-run':'success',results};
  if(!configError && failed>0 && failed<lines.length) summary.status='partial-failure';
  summary.notification=await notify(`账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${failed}，预演 ${summary.dryRun}；状态 ${summary.status}`).catch(()=> '投递失败');
  summary.durationMs=Date.now()-started; summary.finishedAt=new Date().toISOString();
  log('----------------------------------------');
  log(`最终统计：账号 ${summary.accounts}，成功 ${summary.success}，失败 ${failed}，预演 ${summary.dryRun}`);
  const totals=results.reduce((a,r)=>{for(const k of Object.keys(a)) a[k]+=r[k]; return a;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log(`子任务统计：总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`通知：${summary.notification}；总耗时 ${summary.durationMs}ms；完成时间 ${summary.finishedAt}；最终状态 ${summary.status}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary)); process.exitCode=exitCode;
})();
