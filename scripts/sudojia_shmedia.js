// name: 上海杨浦
// cron: 53 1 * * *
/**
 * name: 上海杨浦
 * cron: 33 7 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Derived from sudojia/AutoTaskScript src/client/sudojia_shmedia.js
 * Copyright original author Telegram@sudojia, https://blog.imzjw.cn (2024/10/05).
 * SHYP_TOKEN: 登录上海杨浦 APP，抓取 https://ypapi.shmedia.tech 请求头 token；
 * 每个非空行一个账号，不使用 & 或 @ 分隔。不要公开凭据。
 * SHYP_DRY_RUN=1 完全断网预演。Node.js >=18，无第三方业务依赖。
 * SHYP_ENABLE_FAVOR / SHYP_ENABLE_COMMENT / SHYP_ENABLE_SHARE=1 显式开启对应动作。
 * QINGLONG_NOTIFY 未设置时按上架状态；QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 * 不自动兑换商品，不下载或安装任何程序。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["b9c2b0f38de689f1", "scripts/sudojia_shmedia.js", "sudojia_shmedia.js", "sudojia_shmedia"];
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
const DRY = process.env.SHYP_DRY_RUN === '1';
const TITLE = '上海杨浦';
const BASE = 'https://ypapi.shmedia.tech/media-basic-port/api/app/';
const BODY = { orderBy: 'release_desc', requestType: '2', siteId: '310110' };
const names = { '001': '签到', '002': '阅读', '003': '视频', '004': '上游跳过任务', '005': '收藏', '006': '评论', '007': '分享' };
const channels = ['a978f44b3e284e5e86777f9d4e3be7bb','01ff4b46f6bf4e19af6fe88e6320a6c1','ba1f152e715f4ee99e6e13a02f6a218e','0375dc90023f43ffafaf9bc161c30348','0ea24f917ab54157bcd2cecffbf9bfa2'];
const tokens = (process.env.SHYP_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const clean = value => {
  let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const token of tokens) s = s.split(token).join('[凭据已隐藏]');
  return s;
};
const log = text => console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${clean(text)}`);
const wait = ms => DRY ? Promise.resolve() : new Promise(r => setTimeout(r, ms));
function request(url, { token, body, timeout = 15000, maxBytes = 1048576 } = {}) {
  if (DRY) return Promise.reject(new Error('预演禁止网络请求'));
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (err, value) => { if (settled) return; settled = true; clearTimeout(timer); err ? reject(err) : resolve(value); };
    const headers = token ? { 'User-Agent':'okhttp/4.10.0', siteid:'310110', token, 'Content-Type':'application/json; charset=UTF-8' } : { Accept:'application/json' };
    const payload = body === undefined ? undefined : JSON.stringify(body);
    if (payload) headers['Content-Length'] = Buffer.byteLength(payload);
    const req = https.request(url, {method: payload === undefined ? 'GET' : 'POST', headers}, res => {
      let length = 0; const chunks = [];
      res.on('data', chunk => { length += chunk.length; if (length > maxBytes) { finish(new Error('响应超过大小限制')); res.destroy(); req.destroy(); } else chunks.push(chunk); });
      res.on('error', () => finish(new Error('响应传输失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error('HTTP 请求失败'));
        try { finish(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); } catch { finish(new Error('响应不是有效 JSON')); }
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超时')); req.destroy(); }, timeout);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(payload);
  });
}
function requireOK(r) {
  if (!r || r.code !== 0) throw new Error('业务未确认成功（响应码非 0）');
  return r.data;
}
const normalize = s => typeof s === 'string' ? s.replace(/\s+/g, ' ').trim() : '';
async function commentText() {
  const fallback = normalize(process.env.SHYP_COMMENT_TEXT || '感谢分享，愿生活每天都有新的收获。');
  if (!fallback || [...fallback].length > 280) throw new Error('本地评论文本须为 1 至 280 个字符');
  if (DRY) { log('⏭️ 预演使用本地评论，不请求文本服务'); return fallback; }
  try {
    const r = await request('https://v1.hitokoto.cn/?encode=json', {timeout:8000,maxBytes:16384});
    const text = normalize(r.hitokoto), author = normalize(r.from_who), source = normalize(r.from);
    if (!text) throw new Error('缺少文本');
    const result = text + (author && source ? ` —— ${author}《${source}》` : source ? ` ——《${source}》` : author ? ` —— ${author}` : '');
    if ([...result].length > 280) throw new Error('文本过长');
    log('✅ 评论文本服务成功，已应用署名格式');
    return result;
  } catch { log('⚠️ 评论文本服务不可用，使用本地文本'); return fallback; }
}
function client(token) {
  const jobs = Object.keys(names).map(id => ({id,progress:0,totalProgress:1}));
  return async (endpoint, body = BODY) => {
    if (!DRY) return requireOK(await request(BASE + endpoint, {token, body}));
    if (endpoint === 'personal/get') return {nickname:'预演账号'};
    if (endpoint === 'personal/score/info') return {jobs:jobs.map(x => ({...x})),totalScore:100};
    if (endpoint === 'news/content/list') return {records:[{id:'dry-run-article'}]};
    const id = {'personal/score/sign':'001','points/read/add':'002','points/video/add':'003','news/content/favor':'005','common/comment/add':'006','points/share/add':'007'}[endpoint];
    if (!id) throw new Error('未知预演接口');
    jobs.find(x=>x.id===id).progress++;
    return {score:1};
  };
}
function jobsOf(data) {
  if (!data || !Array.isArray(data.jobs)) throw new Error('任务列表格式错误');
  const seen = new Set();
  for (const job of data.jobs) {
    if (!job || typeof job.id !== 'string' || seen.has(job.id) || !Number.isFinite(Number(job.progress)) || !Number.isFinite(Number(job.totalProgress)) || job.progress === null || job.totalProgress === null || Number(job.progress)<0 || Number(job.totalProgress)<0) throw new Error('任务进度格式错误');
    seen.add(job.id);
  }
  return data.jobs;
}
async function runAccount(token, index) {
  const started = Date.now(), stats = {total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  let stageNo = 0;
  const api = client(token);
  async function stage(name, action) {
    const n=++stageNo, start=Date.now(); stats.total++;
    log(`账号 ${index} · 阶段 ${n} ${name} 开始`);
    try { const result = await action(); const state=result || 'success'; stats[state]++; log(`${state==='skipped'?'⏭️':state==='alreadyComplete'?'☑️':'✅'} 账号 ${index} · 阶段 ${n} ${name} ${state}，耗时 ${Date.now()-start}ms`); return true; }
    catch(e) { stats.failed++; log(`❌ 账号 ${index} · 阶段 ${n} ${name}：${e.message}，耗时 ${Date.now()-start}ms`); return false; }
  }
  const authenticated = await stage('账号身份', async () => {
    const user=await api('personal/get', {});
    if (!user || typeof user !== 'object' || Array.isArray(user)) throw new Error('账号信息格式错误');
    const identity=user.nickname ?? user.username ?? user.displayName ?? user.uid;
    log(identity === undefined || identity === null ? `账号 ${index}：接口未返回公开身份` : `账号 ${index}：${identity}`);
  });
  let jobs;
  if (authenticated) await stage('获取任务列表', async()=>{jobs=jobsOf(await api('personal/score/info'));});
  if (jobs) for (const job of jobs) await stage(names[job.id] || '未知任务', async () => {
    if (job.id==='004') return 'skipped';
    if (!names[job.id]) throw new Error('发现未支持的任务，未执行');
    if (Number(job.progress)>=Number(job.totalProgress)) return 'alreadyComplete';
    const opt = {'005':'SHYP_ENABLE_FAVOR','006':'SHYP_ENABLE_COMMENT','007':'SHYP_ENABLE_SHARE'}[job.id];
    if (opt && process.env[opt] !== '1') {log(`安全默认：未启用 ${opt}，跳过动作`);return 'skipped';}
    let progress = Number(job.progress);
    for (let attempt=0; progress<Number(job.totalProgress); attempt++) {
      if (attempt>=30) throw new Error('超过单任务 30 次上限');
      if (job.id==='001') await api('personal/score/sign');
      else if (['002','003','007'].includes(job.id)) await api(`points/${{'002':'read','003':'video','007':'share'}[job.id]}/add`, {...BODY,requestType:'1'});
      else {
        const articles=await api('news/content/list', {...BODY,requestType:'1',channel:{id:channels[Math.floor(Math.random()*channels.length)]},pageNo:1,pageSize:30});
        if (!articles || !Array.isArray(articles.records) || !articles.records.length) throw new Error('没有可用文章');
        const article = articles.records[Math.floor(Math.random()*articles.records.length)];
        if (!article || typeof article.id !== 'string' || !article.id) throw new Error('文章标识无效');
        if (job.id==='005') await api('news/content/favor', {...BODY,id:article.id});
        else await api('common/comment/add', {content:await commentText(),displayResources:[],targetId:article.id,targetType:'content',pageNo:0,pageSize:10,orderBy:'create_desc',requestType:'1',siteId:'310110'});
      }
      await wait(job.id==='006'?15000:5000);
      const updated=jobsOf(await api('personal/score/info')).find(x=>x.id===job.id);
      if (!updated || Number(updated.progress)<=progress) throw new Error('动作后任务进度未增加，停止重试');
      progress=Number(updated.progress);
      log(`账号 ${index} ${names[job.id]}：已核验进度 ${progress}/${job.totalProgress}`);
      await wait(1500);
    }
  });
  let points;
  if (authenticated) await stage('积分查询',async()=>{
    const data=await api('personal/score/info'); jobsOf(data);
    if (data.totalScore === undefined || data.totalScore === null || !Number.isFinite(Number(data.totalScore)) || Number(data.totalScore)<0) throw new Error('积分字段无效');
    points=Number(data.totalScore);log(`账号 ${index} 当前积分：${points}`);
  });
  if (points!==undefined) {
    for (const [label, params] of [ ['限时商品','seller_id=31011001&page_no=1&page_size=10&shop_cat_id=1544652237932859394&sort=create_desc'], ['虚拟商品','keyword=&page_no=1&page_size=20&sort=create_desc&seller_id=31011001&shop_cat_id=1431136756879056898'] ]) {
      await stage(label+'查询',async()=>{
        const r=DRY?{data:[{promotion:[{exchange:{goods_name:'预演商品',exchange_point:50}}]}]}:await request('https://mall-api.shmedia.tech/goods-service/goods/search?'+params,{token});
        // 上游商城以 data 数组表示结果；若含业务码，同时要求 code 为 0。
        if (!r || (r.code!==undefined && r.code!==0) || !Array.isArray(r.data)) throw new Error('商城未返回有效商品列表');
        let count=0;
        for (const item of r.data) {
          if (!item || !Array.isArray(item.promotion)) throw new Error('商品活动格式错误');
          for (const promotion of item.promotion) {
            const ex=promotion && promotion.exchange; if (!ex) continue;
            if (typeof ex.goods_name!=='string' || ex.exchange_point===null || ex.exchange_point===undefined || !Number.isFinite(Number(ex.exchange_point)) || Number(ex.exchange_point)<0) throw new Error('兑换信息格式错误');
            if (points>=Number(ex.exchange_point)) {count++;log(`可兑换[${ex.goods_name}]，所需[${Number(ex.exchange_point)}]积分`);}
          }
        }
        if (!count) log('当前积分暂无商品可兑换');
      });
    }
  }
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now()-started}ms`);
  return {index, ...stats, durationMs:Date.now()-started};
}
async function notificationWorker() {
  // 预演仍走通知入口，但封锁通知模块的网络与子进程，确保完全断网。
  if (DRY) {
    const denied = () => {throw new Error('dry-run network disabled');};
    for (const name of ['node:http','node:https']) {const m=require(name);m.request=denied;m.get=denied;}
    const net=require('node:net');net.connect=denied;net.createConnection=denied;net.Socket.prototype.connect=denied;
    require('node:tls').connect=denied; global.fetch=denied;
    const cp=require('node:child_process');for (const k of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork']) cp[k]=denied;
    const dns=require('node:dns');for(const k of Object.keys(dns)) if(typeof dns[k]==='function') dns[k]=denied;
    const dgram=require('node:dgram');dgram.createSocket=denied;
    require('node:http2').connect=denied;require('node:worker_threads').Worker=denied;
    const dp=require('node:dns/promises');for(const k of Object.keys(dp))if(typeof dp[k]==='function')dp[k]=denied;
  }
  const file=process.env.SHYP_INTERNAL_NOTIFY_FILE;
  const notify=require(file);
  if(typeof notify.sendNotify!=='function') throw new Error('notification unavailable');
  await notify.sendNotify(TITLE,process.env.SHYP_INTERNAL_NOTIFY_BODY);
}
async function notify(summary) {
  if (['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  const candidates=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=candidates.find(x=>fs.existsSync(x));
  if (!file) return '不可用：未找到 sendNotify.js';
  const body=`模式：${summary.mode}；状态：${summary.status}；账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；子任务成功 ${summary.tasks.success}，已完成 ${summary.tasks.alreadyComplete}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}`;
  return new Promise(resolve=>{
    const env={...process.env,SHYP_INTERNAL_NOTIFY_FILE:file,SHYP_INTERNAL_NOTIFY_BODY:body};
    delete env.SHYP_TOKEN;
    const child=spawn(process.execPath,[__filename,'--notify-worker'],{env,stdio:'ignore'});
    const timer=setTimeout(()=>{child.kill('SIGKILL');resolve('通知超时');},15000);
    child.on('error',()=>{clearTimeout(timer);resolve('通知不可用');});
    child.on('exit',code=>{clearTimeout(timer);resolve(code===0?'已发送':DRY?'预演通知未投递（网络已阻断）':'通知失败');});
  });
}
async function main() {
  const start=Date.now();const results=[];let configError=false;
  log(`========== ${TITLE} ==========`);log(`开始时间：${new Date().toISOString()}；模式：${DRY?'断网预演':'正式运行'}；账号数：${tokens.length}`);
  try {
    if (!tokens.length) throw new Error('请配置 SHYP_TOKEN，每个非空行一个账号');
    for(const key of ['SHYP_DRY_RUN','SHYP_ENABLE_FAVOR','SHYP_ENABLE_COMMENT','SHYP_ENABLE_SHARE']) if (process.env[key]!==undefined && !['0','1'].includes(process.env[key])) throw new Error(`${key} 只能为 0 或 1`);
    if (process.env.SHYP_ENABLE_COMMENT==='1') {const v=normalize(process.env.SHYP_COMMENT_TEXT || '感谢分享，愿生活每天都有新的收获。');if(!v || [...v].length>280)throw new Error('本地评论文本须为 1 至 280 个字符');}
    for(let i=0;i<tokens.length;i++) {
      try {results.push(await runAccount(tokens[i],i+1));}
      catch {log(`❌ 账号 ${i+1} 意外失败（详细信息已隐藏）`);results.push({index:i+1,total:1,success:0,failed:1,alreadyComplete:0,skipped:0});}
    }
  } catch(e) {configError=true;log(`❌ 配置错误：${e.message}`);}
  const failed=configError?tokens.length:results.filter(x=>x.failed>0).length;
  const success=results.filter(x=>x.failed===0).length;
  const tasks={total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  for(const r of results)for(const k of Object.keys(tasks))tasks[k]+=r[k];
  const status=configError?'configuration-error':failed?(success?'partial-failure':'failure'):DRY?'dry-run':'success';
  const summary={task:TITLE,mode:DRY?'dry-run':'live',status,accounts:tokens.length,success,failed,tasks,results,durationMs:Date.now()-start,finishedAt:new Date().toISOString()};
  process.exitCode=configError || failed?1:0;
  try {summary.notification=await notify(summary);}catch{summary.notification='通知失败';}
  summary.durationMs=Date.now()-start;summary.finishedAt=new Date().toISOString();
  log('----------------------------------------');
  log(`账号统计：总数 ${tokens.length}，成功 ${success}，失败 ${failed}`);
  log(`子任务统计：总数 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`总耗时 ${Date.now()-start}ms；完成时间 ${new Date().toISOString()}；最终状态 ${status}；通知：${summary.notification}`);
  if(DRY && process.exitCode===0)log('DRY_RUN_OK（模拟验证通过，不代表线上成功）');
  if(!DRY && process.exitCode===0)log('SHYP_SUCCESS');
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
}
if (require.main===module) {
  if(process.argv.includes('--notify-worker'))notificationWorker().catch(()=>{process.exitCode=1;});
  else main().catch(()=>{console.error('任务终结处理失败（详细信息已隐藏）');process.exitCode=1;});
}
