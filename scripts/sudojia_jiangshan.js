// name: 多娇江山
// cron: 20 2 * * *
/**
 * name: 多娇江山
 * cron: 26 9 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 基于 sudojia/AutoTaskScript src/client/sudojia_jiangshan.js
 * 原作者 Telegram@sudojia · https://blog.imzjw.cn · 2024/08/29
 * JIANG_SHAN_SESSION：在多娇江山 APP 抓取 https://vapp.tmuyun.com
 * 请求头 X-SESSION-ID，每行一个账号，仅按换行分隔。
 * JIANG_SHAN_ACTIONS：默认 sign,read，可选 share,comment,like,local（会改变账号状态）。
 * JIANG_SHAN_DRY_RUN=1：完全断网预演；详见同目录 contract.json。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["db8583cdb3a987c1", "scripts/sudojia_jiangshan.js", "sudojia_jiangshan.js", "sudojia_jiangshan"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const env = process.env;
const dry = env.JIANG_SHAN_DRY_RUN === '1';
const sessions = (env.JIANG_SHAN_SESSION || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const actions = new Set((env.JIANG_SHAN_ACTIONS ?? 'sign,read').split(',').map(x => x.trim()).filter(Boolean));
const names = {sign:'签到',read:'阅读',share:'分享任务上报',comment:'评论',like:'点赞',local:'本地服务任务上报'};
const types = {2:'read',3:'share',4:'comment',5:'like',6:'local'};
const started = Date.now();
const results = [];
let configError = false;
function log(s) { console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`); }
function safeIdentity(v) {
  let s = String(v).replace(/[\r\n\u0000-\u001f]/g,' ');
  for (const secret of sessions) s = s.split(secret).join('[凭据已隐藏]');
  return s.replace(/\b1[3-9]\d{9}\b/g,'[手机号已隐藏]');
}
const wait = ms => new Promise(resolve => setTimeout(resolve,ms));
function request(url, options = {}, limit = 1048576, timeout = 15000) {
  if (dry) return Promise.reject(new Error('预演禁止网络'));
  return new Promise((resolve,reject) => {
    const req = https.request(url, options, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => { size += chunk.length; if(size > limit) req.destroy(new Error('响应过大')); else chunks.push(chunk); });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if(res.statusCode < 200 || res.statusCode >= 300) return reject(new Error('HTTP 状态失败'));
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); } catch { reject(new Error('响应不是有效 JSON')); }
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')),timeout);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    if(options.body) req.write(options.body);
    req.end();
  });
}
async function api(session, endpoint, query, body, json = false) {
  const id = crypto.randomUUID(), timestamp = String(Date.now());
  const headers = {'User-Agent':'Mozilla/5.0','X-TENANT-ID':'24','X-SESSION-ID':session,'X-REQUEST-ID':id,'X-TIMESTAMP':timestamp,
    'X-SIGNATURE':crypto.createHash('sha256').update(`${endpoint}&&${session}&&${id}&&${timestamp}&&FR*r!isE5W&&24`).digest('hex')};
  let payload;
  if(body) { payload = json ? JSON.stringify(body) : new URLSearchParams(body).toString(); headers['Content-Type'] = json ? 'application/json' : 'application/x-www-form-urlencoded'; }
  const data = await request(`https://vapp.tmuyun.com${endpoint}${query ? '?'+new URLSearchParams(query) : ''}`,{method:body?'POST':'GET',headers,body:payload});
  if(!data || data.code !== 0) throw new Error('业务返回未确认成功');
  return data.data;
}
function normalize(s) { return typeof s === 'string' ? s.replace(/\s+/g,' ').trim() : ''; }
async function commentText() {
  const fallback = normalize(env.JIANG_SHAN_COMMENT_TEXT || '感谢分享这则资讯。');
  try {
    const d = await request('https://v1.hitokoto.cn/?encode=json', {method:'GET'},16384,8000);
    const text = normalize(d.hitokoto), author = normalize(d.from_who), source = normalize(d.from);
    if(!text) throw new Error();
    const content = text + (author ? ` —— ${author}${source ? `《${source}》` : ''}` : source ? ` ——《${source}》` : '');
    if([...content].length > 280) throw new Error();
    log('评论文本：一言获取成功，已按作者及出处格式署名');
    return content;
  } catch { log('⚠️ 一言不可用，使用本地评论文本'); return fallback; }
}
async function taskList(session) {
  const d = await api(session,'/api/user_center/task',{type:1,current:1,size:20});
  if(!d || !Array.isArray(d.list)) throw new Error('任务列表结构异常');
  for(const t of d.list) if(!Number.isInteger(t.frequency) || !Number.isInteger(t.finish_times) || t.frequency < 0 || t.finish_times < 0 || t.frequency > 100) throw new Error('任务次数结构异常');
  return d.list;
}
async function article(session) {
  const channels = ['5da293a31b011b7c692ffda8','5d3fe981b198500f695bdebf','6264b0b6fe3fc11a653387d2','5d3fea3ab198500f695bdec4'];
  for(let n=0;n<5;n++) {
    try {
      const d = await api(session,'/api/article/channel_list',{channel_id:channels[n%4]});
      const list = d && d.article_list;
      if(Array.isArray(list) && list.length) { const a = list[Math.floor(Math.random()*list.length)]; if(typeof a.id === 'string' && a.id) return a.id; }
    } catch { log(`⚠️ 获取文章第 ${n+1}/5 次失败`); }
    if(n<4) await wait(2000);
  }
  throw new Error('未能取得文章');
}
async function account(session,index) {
  const begin = Date.now();
  const stats = {account:index,total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  let stage = 0;
  async function step(label, fn) {
    stats.total++; const time = Date.now();
    log(`账号 ${index} 阶段 ${++stage}：${label}`);
    try { await fn(); stats.success++; log(`✅ ${label}成功，耗时 ${Date.now()-time}ms`); return true; }
    catch(e) { stats.failed++; log(`❌ ${label}失败：${e.message}，耗时 ${Date.now()-time}ms`); return false; }
  }
  if(dry) {
    await step('断网预演',async () => { log(`DRY_RUN_OK 账号 ${index}：参数解析通过；计划执行 ${[...actions].map(x=>names[x]).join('、') || '仅查询'}；不请求业务接口或文本服务`); });
  } else {
    if(actions.has('sign')) await step('签到', async () => {
      const d = await api(session,'/api/user_mumber/sign');
      if(!d || !Number.isFinite(Number(d.serialdays)) || d.serialdays == null) throw new Error('签到响应结构异常');
      log(`签到成功，连续天数 ${Number(d.serialdays)}`);
    });
    let tasks;
    await step('获取任务列表',async () => { tasks = await taskList(session); });
    for(const task of tasks || []) {
      const action = types[task.member_task_type];
      if(!action || !actions.has(action)) { stats.total++; stats.skipped++; log(`⏭️ 任务类型 ${Number(task.member_task_type) || 0} 未启用`); continue; }
      if(task.finish_times >= task.frequency) { stats.total++; stats.alreadyComplete++; log(`☑️ ${names[action]}已完成`); continue; }
      for(let n=task.finish_times;n<task.frequency;n++) {
        await step(`${names[action]} ${n+1}/${task.frequency}`,async () => {
          const id = action === 'local' ? null : await article(session);
          if(action === 'read') { await api(session,'/api/article/detail',{id}); await wait(4000); }
          if(action === 'share' || action === 'local') await api(session,'/api/user_mumber/doTask',null,{memberType:action==='share'?3:6,member_type:action==='share'?3:6,...(id?{target_id:id}:{})});
          if(action === 'like') await api(session,'/api/favorite/like',null,{action:'true',id});
          if(action === 'comment') await api(session,'/api/comment/create/v2',null,{channel_article_id:id,content:await commentText()},true);
        });
        await wait(2500);
      }
    }
    await step('查询账号与积分',async () => {
      const d = await api(session,'/api/user_mumber/account_detail');
      if(!d || !d.rst || d.rst.total_integral == null || !Number.isFinite(Number(d.rst.total_integral))) throw new Error('账号响应结构异常');
      for(const k of ['nick_name','username','display_name','uid']) if(d.rst[k] != null) log(`账号身份 ${k}：${safeIdentity(d.rst[k])}`);
      log(`当前积分：${Number(d.rst.total_integral)}`);
    });
    await step('复查任务进度',async () => {
      const final = await taskList(session);
      for(const t of final) log(`任务类型 ${Number(t.member_task_type)||0}：${t.finish_times}/${t.frequency}`);
      const pending = final.some(t => actions.has(types[t.member_task_type]) && t.finish_times < t.frequency);
      const missing = (tasks || []).some(t => actions.has(types[t.member_task_type]) && !final.some(f => f.member_task_type === t.member_task_type));
      if(pending || missing) throw new Error('已启用任务未全部确认完成');
    });
  }
  stats.durationMs = Date.now()-begin;
  results.push(stats);
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs}ms`);
}
function notify(summary) {
  if(/^(0|false|no|off)$/i.test(env.QINGLONG_NOTIFY || '1')) return '已关闭';
  const locations = [env.QINGLONG_NOTIFY_DIR && path.join(env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = locations.find(f => fs.existsSync(f));
  if(!file) return '不可用：未找到 sendNotify.js';
  // 在独立进程中限时通知；预演时先封锁传输层，确保通知模块也不能联网。
  const code = `if(process.env.NOTIFY_DRY==='1'){const deny=()=>{throw Error('dry-run network disabled')};for(const m of ['http','https']){require(m).request=deny;require(m).get=deny;}require('net').Socket.prototype.connect=deny;require('dgram').Socket.prototype.send=deny;for(const k of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork'])require('child_process')[k]=deny;require('tls').connect=deny;for(const k of ['lookup','resolve','resolve4','resolve6'])require('dns')[k]=deny;global.fetch=deny;} Promise.resolve().then(()=>require(process.argv[1]).sendNotify('多娇江山',process.argv[2])).catch(()=>{process.exitCode=1});`;
  const childEnv = {...env,NOTIFY_DRY:dry?'1':'0'};
  delete childEnv.JIANG_SHAN_SESSION;
  const r = spawnSync(process.execPath,['-e',code,file,summary],{env:childEnv,timeout:20000,stdio:'ignore'});
  return r.status === 0 ? '已发送' : dry ? '预演通知已调用，网络传输已禁止' : '发送失败，保留业务退出码';
}
async function main() {
  log('========== 多娇江山 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${sessions.length}`);
  const fallback = normalize(env.JIANG_SHAN_COMMENT_TEXT || '感谢分享这则资讯。');
  if(!sessions.length || sessions.some(s=>/[\r\x00-\x20\x7f]/.test(s)) || [...actions].some(a=>!Object.hasOwn(names,a)) || !fallback || [...fallback].length>280 || (env.JIANG_SHAN_DRY_RUN && !['0','1'].includes(env.JIANG_SHAN_DRY_RUN))) {
    configError = true; log('❌ 阶段 1：配置错误，请检查账号、动作列表、预演开关或本地文本长度');
  } else for(let i=0;i<sessions.length;i++) await account(sessions[i],i+1);
}
main().catch(() => { configError=true; log('❌ 未预期执行错误，详细内容已隐藏'); }).finally(() => {
  const successful = results.filter(r=>!r.failed).length;
  const failed = results.filter(r=>r.failed).length;
  const exitCode = configError || failed ? 1 : 0;
  const status = configError ? 'configuration-error' : failed ? (successful?'partial-failure':'failure') : dry?'dry-run':'success';
  const text = `账号总数 ${sessions.length}，成功 ${successful}，失败 ${configError ? sessions.length : failed}，状态 ${status}`;
  let notification;
  try { notification = notify(text); } catch { notification = '通知异常，保留业务退出码'; }
  const taskStats = results.reduce((a,r)=>{for(const k of Object.keys(a))a[k]+=r[k];return a;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log('--------------------------------'); log(text);
  log(`子任务统计：${JSON.stringify(taskStats)}；总耗时 ${Date.now()-started}ms`);
  log(`完成时间：${new Date().toISOString()}；通知：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:'多娇江山',mode:dry?'dry-run':'live',accounts:sessions.length,successful,failed:configError?sessions.length:failed,configError,status,taskStats,results,notification,exitCode}));
  process.exitCode = exitCode;
});
