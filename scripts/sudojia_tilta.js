// name: TILTA影像城
// cron: 24 1 * * *
/**
 * name: TILTA影像城
 * cron: 5 10 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia；https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_tilta.js
 * 使用 Node.js >=18，无第三方依赖。
 * TILTA_TOKEN：打开 TILTA影像城小程序，在本人授权的抓包工具中查看
 * https://java.vrupup.com 请求头 authorization，原样复制；每个非空行一个账号。
 * 凭据有效期短，失效后重新获取。不要使用 & 或 @ 分隔账号。
 * TILTA_ALLOW_LIKE=1 才执行社区点赞；默认跳过，订单评价始终排除。
 * TILTA_DRY_RUN=1 完全断网预演（通知也只演练）；QINGLONG_NOTIFY=0 关闭通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["8a2853d90ebdcb0c", "scripts/sudojia_tilta.js", "sudojia_tilta.js", "sudojia_tilta"];
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
const { spawn } = require('node:child_process');
const started = Date.now();
const dry = process.env.TILTA_DRY_RUN === '1';
const allowLike = process.env.TILTA_ALLOW_LIKE === '1';
const tokens = (process.env.TILTA_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const names = {1:'社区点赞',2:'浏览两件商品',3:'社区阅读',7:'新闻中心阅读',8:'配件研究所阅读'};
const results = [];
let configError = false;
const log = s => console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${s}`);
const sleep = ms => new Promise(r => setTimeout(r, ms));
function fail(message) { throw new Error(message); }
function idOf(item) {
  if (!item || !['string','number'].includes(typeof item.id) || !String(item.id).trim()) fail('列表缺少有效标识');
  return item.id;
}
function pick(list) {
  if (!Array.isArray(list) || !list.length) fail('接口列表为空或结构异常');
  return list[Math.floor(Math.random()*list.length)];
}
function request(token, endpoint, body) {
  if (dry) fail('预演禁止网络调用');
  return new Promise((resolve,reject) => {
    const bytes = body === undefined ? null : Buffer.from(JSON.stringify(body));
    let finished = false;
    let timer;
    const done = (err, value) => { if (finished) return; finished=true; clearTimeout(timer); err ? reject(err) : resolve(value); };
    const req = https.request({hostname:'java.vrupup.com',path:'/tietou-shop/api/'+endpoint,method:'POST',headers:{
      authorization:token,'xweb_xhr':'1','User-Agent':'Mozilla/5.0','Content-Type':'application/json',Accept:'application/json',
      Referer:'https://servicewechat.com/wxca94758d1196d2ff/33/page-frame.html', ...(bytes ? {'Content-Length':bytes.length}: {})
    }}, res => {
      if (res.statusCode !== 200) { res.resume(); done(new Error('HTTP请求失败')); return; }
      let size=0; const chunks=[];
      res.on('data', c => { size+=c.length; if(size>1024*1024) { done(new Error('响应超过大小限制')); res.destroy(); } else chunks.push(c); });
      res.on('error', () => done(new Error('响应读取失败')));
      res.on('end', () => {
        if(finished) return;
        let data; try { data=JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { done(new Error('响应不是有效JSON')); return; }
        if (!data || data.code !== 1) { done(new Error('业务未成功（需要检查凭据有效期或小程序状态）')); return; }
        done(null,data.data);
      });
    });
    timer=setTimeout(() => { done(new Error('请求超时')); req.destroy(); },15000);
    req.on('error', () => done(new Error('网络请求失败')));
    req.end(bytes);
  });
}
function calendarToday(data) {
  if (!data || !Array.isArray(data.calendar)) fail('签到日历结构异常');
  const row=data.calendar.find(x => x.day === new Date().getDate());
  if (!row || ![0,1].includes(row.status)) fail('未找到有效的今日签到状态');
  return row.status;
}
function dateBody() { const d=new Date(); return {planDate:`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${d.getDate()}`}; }
function taskList(data) {
  if(!Array.isArray(data) || !data.length) fail('任务列表为空或结构异常');
  if(data.some(t => !t || !Number.isInteger(t.id) || ![0,1].includes(t.taskStatus))) fail('任务状态不受支持');
  return data;
}
async function account(token,index) {
  const begin=Date.now(); const stats={account:index,total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  let seq=0;
  async function stage(name,fn) {
    const start=Date.now(); stats.total++; log(`账号${index} 阶段${++seq} ${name} 开始`);
    try { const outcome=await fn() || 'success'; stats[outcome]++; log(`账号${index} 阶段${seq} ${name} ${outcome==='skipped'?'⏭️ 跳过':outcome==='alreadyComplete'?'☑️ 已完成':'✅ 成功'}，耗时${Date.now()-start}ms`); return true; }
    catch(e) { stats.failed++; log(`账号${index} 阶段${seq} ${name} ❌ ${e.message}，耗时${Date.now()-start}ms`); return false; }
  }
  const api=(ep,b) => request(token,ep,b);
  const authenticated=await stage('身份核验',async()=>{
    if(dry) { log('预演：检查身份接口及严格业务码，不发送请求'); return; }
    const data=await api('get_user_detail');
    if(!data || typeof data !== 'object') fail('账号信息结构异常');
    if(typeof data.nickName==='string') {
      // 仅输出官方昵称，禁止凭据、手机号或换行注入。
      const nick=data.nickName;
      if (!tokens.some(t=>nick.includes(t)) && !/[\r\n\x00-\x1f]|\+?\d[\d -]{9,}\d/.test(nick)) log(`账号${index} 昵称：${nick}`);
    }
  });
  if(authenticated) {
    await stage('每日签到',async()=>{
      if(dry) {log('预演：检查日历，未签到时提交并复查');return;}
      if(calendarToday(await api('personal/sign/list',dateBody()))===1) return 'alreadyComplete';
      await api('personal/sign/save');
      if(calendarToday(await api('personal/sign/list',dateBody()))!==1) fail('签到提交后未验证完成');
    });
    let tasks;
    await stage('获取任务列表',async()=>{tasks=dry?[1,2,3,7,8].map(id=>({id,taskStatus:0})):taskList(await api('task/list'));});
    if(tasks) for(const task of tasks) {
      await stage(names[task.id] || (task.id===6?'订单评价（排除）':'未知任务（不执行）'),async()=>{
        if(task.id===6 || task.id===1&&!allowLike) return 'skipped';
        if(!names[task.id]) fail('发现未支持任务，请手动核对');
        if(task.taskStatus===1) return 'alreadyComplete';
        if(dry) {log(`预演：计划执行任务${task.id}并复查 taskStatus=1`);return;}
        if(task.id===1) {
          const articles=await api('article/page',{pageNumber:1,pageSize:100,articleCategoryId:3});
          await api('article/like',{articleId:idOf(pick(articles?.list))});
        } else if(task.id===2) {
          for(let n=0;n<2;n++) {
            const cate=idOf(pick(await api('product/cate/list',{pid:15,type:2})));
            const page=await api('product/page',{pageNumber:1,pageSize:10,cateOneId:'15',cateTwoId:cate,name:'',productType:'1',sort:''});
            const id=idOf(pick(page?.list));
            await api('product/detail',{id}); await sleep(1500); await api('v2/pt/queryptlist',{id});
          }
        } else { await api('task/finishTask',{id:task.id}); await sleep(10500); }
        await sleep(1500);
        const row=taskList(await api('task/list')).find(t=>t.id===task.id);
        if(!row || row.taskStatus!==1) fail('提交后任务未验证完成');
      });
    }
    await stage('最终任务复查',async()=>{
      if(dry) return;
      const current=taskList(await api('task/list'));
      const required=current.filter(t=>t.id!==6 && (t.id!==1 || allowLike));
      if(!tasks || tasks.some(t=>t.id!==6 && (t.id!==1||allowLike) && !current.some(c=>c.id===t.id))) fail('复查缺少任务');
      if(required.some(t=>!names[t.id] || t.taskStatus!==1)) fail('存在未完成或未支持任务');
    });
    await stage('积分查询',async()=>{
      if(dry) {log('预演：查询当前积分');return;}
      const data=await api('get_user_detail');
      if(!data || !/^-?\d+(\.\d+)?$/.test(String(data.point))) fail('积分字段无效');
      log(`账号${index} 当前积分：${data.point}`);
    });
  }
  stats.elapsedMs=Date.now()-begin; stats.ok=stats.failed===0;
  results.push(stats);
  log(`账号${index} 统计：总任务${stats.total} 成功${stats.success} 已完成${stats.alreadyComplete} 跳过${stats.skipped} 失败${stats.failed} 耗时${stats.elapsedMs}ms`);
}
async function notify(body) {
  if(['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  if(dry) {log('通知预演：'+body);return '预演（未发送网络请求）';}
  const files=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=files.find(f=>fs.existsSync(f));
  if(!file) return '不可用：未找到青龙 sendNotify.js';
  return new Promise(resolve=>{
    const child=spawn(process.execPath,['-e',`Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))`,file,'TILTA影像城',body],{stdio:'ignore'});
    const timer=setTimeout(()=>child.kill('SIGKILL'),20000);
    child.on('error',()=>{clearTimeout(timer);resolve('发送失败');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':'发送失败');});
  });
}
async function main() {
  log('========== TILTA影像城 ==========');
  log(`开始时间：${new Date(started).toISOString()} 模式：${dry?'断网预演':'正式运行'} 账号数：${tokens.length}`);
  if(!tokens.length || ['TILTA_DRY_RUN','TILTA_ALLOW_LIKE'].some(k=>process.env[k]!==undefined&&!['0','1'].includes(process.env[k]))) {
    configError=true; log('❌ 配置错误：须设置每行一个账号的 TILTA_TOKEN；开关仅允许0或1');
  } else for(let i=0;i<tokens.length;i++) await account(tokens[i],i+1);
}
(async()=>{
  try {await main();} catch {configError=true;log('❌ 执行异常（详细异常已抑制，防止泄漏敏感信息）');}
  const success=results.filter(r=>r.ok).length;
  const failed=results.filter(r=>!r.ok).length;
  const exitCode=configError||failed?1:0;
  const status=configError?'configuration-error':failed?(success?'partial-failure':'failure'):dry?'dry-run':'success';
  const body=`状态：${status}，账号总数${tokens.length}，成功${success}，失败${failed}，配置错误${configError?'是':'否'}。${dry?'仅预演，未验证线上业务。':''}`;
  let notification; try {notification=await notify(body);} catch {notification='发送失败';}
  log('--------------------------------');log(body);
  const totals={total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  for(const r of results) for(const k of Object.keys(totals)) totals[k]+=r[k];
  log(`子任务统计：总数${totals.total} 成功${totals.success} 已完成${totals.alreadyComplete} 跳过${totals.skipped} 失败${totals.failed}`);
  const finishedAt=new Date().toISOString();
  log(`完成时间：${finishedAt} 总耗时${Date.now()-started}ms 通知：${notification} 最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:'tilta',mode:dry?'dry-run':'live',status,accountCount:tokens.length,success,failed,configError,totals,accounts:results,notification,finishedAt,elapsedMs:Date.now()-started,exitCode}));
  process.exitCode=exitCode;
})();
