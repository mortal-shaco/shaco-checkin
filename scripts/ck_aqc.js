// name: 爱企查每日任务
// cron: 37 0-23/8 * * *
/*
 * name: 爱企查每日任务
 * cron: 37 0-23/8 * * *
 * License: MIT (上游许可，按任务 effectiveLicense 保留)
 * @url: https://raw.githubusercontent.com/Wenmoux/checkbox/master/scripts/aiqicha.js
 * @author: wenmoux
 * 来源：OreosLab/checkinpanel ck_aqc.js
 * 参数与获取方式见随附 contract.json。仅使用 Node.js 标准库。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const E = process.env;
const DRY = E.AQC_DRY_RUN === '1';
const names = {CX10002:'每日签到',CX10001:'每日登录',CX11001:'查询企业',CX11002:'查询老板',CX11003:'查询老赖',CX11004:'查询商标',CX11005:'查询地图',CX11006:'浏览新闻',CX11007:'浏览监控日报',CX11009:'查询关系',CX11010:'批量查询',CX12001:'添加监控',CX12002:'添加关注',CX12005:'获取分享链接',CX12006:'邀请任务',CX12007:'高级搜索',CX12008:'高级筛选',CX12009:'浏览互动',CX12011:'点赞观点'};
const defaults = ['CX10002','CX10001','CX11001','CX11002','CX11003','CX11004','CX11005','CX11006','CX11007','CX11009','CX12007','CX12008','CX12009'];
const started = Date.now();
const timestamp = () => new Date().toLocaleTimeString('zh-CN',{hour12:false});
const log = s => console.log(`[${timestamp()}] ${s}`);
const sleep = ms => new Promise(r=>setTimeout(r,ms));
class SafeError extends Error {}
const fail = s => {throw new SafeError(s);};
const stats = () => ({total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
let sequence = 0;
async function stage(a, label, fn) {
  const t = Date.now(); a.stats.total++;
  log(`账号 ${a.index} · 阶段 ${++sequence} ${label}`);
  try { const result = await fn(); const kind = result || 'success'; a.stats[kind]++; log(`${kind==='skipped'?'⏭️':kind==='alreadyComplete'?'☑️':'✅'} ${label}：${kind==='skipped'?'跳过':kind==='alreadyComplete'?'已完成':'通过'}，耗时 ${Date.now()-t} 毫秒`); return true; }
  catch(err) {a.stats.failed++; log(`❌ ${label}：${err instanceof SafeError?err.message:'执行失败（详情已脱敏）'}，耗时 ${Date.now()-t} 毫秒`); return false;}
}
function request(a, route, {method='GET',body,html=false}={}) {
  if(DRY) fail('预演模式禁止网络请求');
  const url = new URL(route, 'https://aiqicha.baidu.com/');
  if(url.origin!=='https://aiqicha.baidu.com') fail('请求地址不符合服务边界');
  return new Promise((resolve,reject)=>{
    const headers = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Safari/537.36',Referer:'https://aiqicha.baidu.com/m/s?t=3&q=%E5%B0%8F%E7%B1%B3&VNK=e73b55ef','X-Requested-With':'XMLHttpRequest',Cookie:a.cookie};
    if(body!==undefined) {headers['Content-Type']='application/x-www-form-urlencoded'; headers['Content-Length']=Buffer.byteLength(body);}
    let size=0, chunks=[];
    const req=https.request(url,{method,headers},res=>{
      res.on('data',chunk=>{size+=chunk.length;if(size>2*1024*1024) req.destroy(new SafeError('响应超过大小限制'));else chunks.push(chunk);});
      res.on('error',()=>reject(new SafeError('响应读取失败')));
      res.on('end',()=>{if(res.statusCode!==200) return reject(new SafeError(`HTTP 状态 ${res.statusCode}`));
        if(html) return resolve(null); // 页面仅为动作请求，必须另行复核任务进度。
        let value;try{value=JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch{return reject(new SafeError('响应不是有效 JSON'));}
        if(!value || ![0,'0'].includes(value.status)) return reject(new SafeError('业务状态未确认成功'));
        resolve(value.data);
      });
    });
    const timer=setTimeout(()=>req.destroy(new SafeError('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',err=>reject(err instanceof SafeError?err:new SafeError('网络请求失败')));
    if(body!==undefined) req.write(body);req.end();
  });
}
const query = (route,params) => `${route}?${new URLSearchParams(params)}`;
const ids = value => {const parts=(value||'').split(',').filter(Boolean);if(parts.some(v=>!/^\d+$/.test(v))) fail('目标编号必须为逗号分隔的数字');return parts;};
const complete = t => Number.isFinite(Number(t.count)) && Number.isFinite(Number(t.totalcount)) && Number(t.count)>=Number(t.totalcount);
function taskData(data) {
  if(!data || typeof data!=='object' || Array.isArray(data)) fail('任务列表结构变化');
  const result={};for(const [code,t] of Object.entries(data)) if(names[code]) {
    if(!t || !Number.isFinite(Number(t.count)) || !Number.isFinite(Number(t.totalcount)) || !Number.isFinite(Number(t.canClaim))) fail('任务进度字段缺失');
    result[code]=t;
  }
  if(!Object.keys(result).length) fail('未返回已知任务，无法确认业务结果');return result;
}
async function action(a, code) {
 const get = (r,o) => request(a,r,o); const word=()=>a.words[Math.floor(Math.random()*a.words.length)];
 const routes={CX10002:'usercenter/userSignAjax',CX11001:()=>query('s/getHeadBrandAndPersonAjax',{q:word()}),CX11002:()=>query('person/relevantPersonalAjax',{page:1,q:word(),size:10}),CX11003:()=>query('c/dishonestAjax',{q:word(),t:8,s:10,p:1,f:'{"type":"1"}'}),CX11004:()=>query('c/markproAjax',{q:word(),p:1,s:10,f:'{}',o:'{}'}),CX11005:'map/getAdvanceFilterListAjax?longitude=113.76343399&latitude=23.04302382&distance=2&page=1',CX11006:'m/getYuqingDetailAjax?yuqingId=993090dcb7574be014599996098459e3',CX11009:'relations/findrelationsAjax?from=e07a8ef1409bff3987f1b28d118ff826&to=6f5966de4af2eb29085ffbcc9cc0116a&pathNum=10',CX12007:()=>query('search/advanceSearchAjax',{q:word(),t:11,p:1,s:10,o:0,f:'{"searchtype":["1"]}'}),CX12008:'search/advanceFilterAjax?q=%E7%A6%8F%E5%B7%9E%E6%AF%8F%E6%97%A5&t=0&p=1&s=10&o=0'};
 if(routes[code]) {await get(typeof routes[code]==='function'?routes[code]():routes[code]);return;}
 switch(code){
 case 'CX10001': await get('m/getuserinfoAjax');break;
 case 'CX11007': {const d=await get('zxcenter/monitorDailyReportListAjax?page=1&size=10');if(!Array.isArray(d?.list)) fail('监控日报结构变化');if(!d.list.length) fail('没有可浏览的监控日报');for(const t of d.list.slice(0,2)){if(!t.reportDate) fail('缺少日报日期');await get(query('zxcenter/monitorDailyReportDetailAjax',{reportdate:t.reportDate}));}break;}
 case 'CX11010': if(!a.exportkey) fail('批量查询需要本账号 exportkey');await get(query('batchquery/show',{exportkey:a.exportkey}),{html:true});break;
 case 'CX12001': for(const pid of a.monitor) await get(query('zxcenter/addMonitorAjax',{pid}));break;
 case 'CX12002': for(const pid of a.follow) await get('my/addCollectAjax',{method:'POST',body:new URLSearchParams({pid}).toString()});break;
 case 'CX12005': {const d=await get('usercenter/getShareUrlAjax');if(typeof d!=='string'||!d.trim()) fail('未返回分享链接');log('已获取分享链接（含会话信息，不输出）；不模拟他人访问');break;}
 case 'CX12009': {const d=await get('smart/getHomeQuestionListAjax?page=2&size=10&type=recommend');if(!Array.isArray(d?.list)||!d.list.length) fail('没有可浏览的互动');const q=d.list[Math.floor(Math.random()*d.list.length)];if(!q.nid) fail('互动编号缺失');await get(query('smart/questionDetailAjax',{nid:q.nid}));break;}
 case 'CX12011': await get(query('smart/updownAjax',{undoType:0,clientType:'app',nid:a.like[0],parentId:a.like[1]}));break;
 default: fail('该任务没有可验证的执行接口');
 }
}
async function runAccount(a, selected) {
 const begin=Date.now();let tasks;
 const ok=await stage(a,'登录与身份核验',async()=>{const d=await request(a,'m/getuserinfoAjax');if(!d||![1,'1'].includes(d.isLogin)) fail('Cookie 失效或账号未登录');for(const field of ['userName','nickname','displayName','uid']) if(d[field]!==undefined && d[field]!==null) {const identity=String(d[field]);if(identity.includes(a.cookie)||(a.exportkey&&identity.includes(a.exportkey))||/1[3-9]\d{9}/.test(identity)) continue;log(`账号 ${a.index} ${field}：${identity.replace(/[\r\n\x00-\x1f\x7f]/g,' ')}`);}});
 if(ok){
 await stage(a,'获取热搜词',async()=>{const d=await request(a,'m/popularSearcheAjax');if(!Array.isArray(d)) fail('热搜词结构变化');a.words.push(...d.map(t=>t.words).filter(t=>typeof t==='string'&&t.trim()));});
 const loaded=await stage(a,'读取任务进度',async()=>{tasks=taskData(await request(a,'usercenter/checkTaskStatusAjax'));log(`账号 ${a.index} 返回 ${Object.keys(tasks).length} 个任务`);});
 if(loaded){
 for(const [code,t] of Object.entries(tasks)) if(!selected.has(code)) await stage(a,names[code],async()=> 'skipped');
 for(let pass=0;pass<2;pass++){
 for(const code of selected){if(code==='CX12005') {if(pass===0) await stage(a,names[code],()=>action(a,code));continue;}if(!tasks[code]) {if(pass===0) await stage(a,names[code],async()=> 'skipped');continue;}if(complete(tasks[code])) {if(pass===0) await stage(a,names[code],async()=> 'alreadyComplete');continue;}
 await stage(a,`${names[code]}（第 ${pass+1} 轮）`,()=>action(a,code));await sleep(10000+Math.floor(Math.random()*80000));}
 await sleep(5000);
 const refreshed=await stage(a,`复核第 ${pass+1} 轮任务进度`,async()=>{const next=taskData(await request(a,'usercenter/checkTaskStatusAjax'));for(const code of Object.keys(tasks)) if(!next[code]) fail('任务进度字段丢失');tasks=next;});if(!refreshed) break;
 }
 for(const code of selected) if(code!=='CX12005' && tasks[code]) await stage(a,`${names[code]}完成确认`,async()=>{if(!complete(tasks[code])) fail('服务端任务进度未完成');return 'alreadyComplete';});
 for(const [code,t] of Object.entries(tasks)) if(Number(t.canClaim)!==0) await stage(a,`领取${names[code]}奖励`,async()=>{const d=await request(a,query('zxcenter/claimUserTaskAjax',{taskCode:code}));if(!Number.isFinite(Number(d?.totalScore))) fail('奖励结果字段缺失');log(`奖励已领取：${Number(d.totalScore)} 爱豆`);await sleep(2500);});
 }
 await stage(a,'查询爱豆积分',async()=>{const d=await request(a,'usercenter/getvipinfoAjax');if(d?.consume===undefined||!Number.isFinite(Number(d.consume))) fail('积分字段缺失');log(`账号 ${a.index} 共 ${Number(d.consume)} 爱豆`);});
 }
 a.elapsedMs=Date.now()-begin;
 log(`账号 ${a.index} 统计：总任务 ${a.stats.total}，成功 ${a.stats.success}，已完成 ${a.stats.alreadyComplete}，跳过 ${a.stats.skipped}，失败 ${a.stats.failed}，耗时 ${a.elapsedMs} 毫秒`);
}
async function notify(summary) {
 if(['0','false','no','off'].includes((E.QINGLONG_NOTIFY||'1').toLowerCase())) return '已关闭';
 if(DRY) {log('预演通知：已生成脱敏总结；为保证断网，不调用通知投递器');return '预演未投递';}
 const paths=[E.QINGLONG_NOTIFY_DIR && path.join(E.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
 const p=paths.find(p=>fs.existsSync(p));if(!p) return '通知模块不可用';
 const body=`状态：${summary.status}\n账号总数 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${summary.failed}\n子任务：成功 ${summary.steps.success}，已完成 ${summary.steps.alreadyComplete}，跳过 ${summary.steps.skipped}，失败 ${summary.steps.failed}`;
 let timer;
 try {const mod=require(p);if(typeof mod.sendNotify!=='function') throw Error();await Promise.race([Promise.resolve().then(()=>mod.sendNotify('爱企查每日任务',body)),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error()),15000);})]);return '已投递';}catch{return '投递失败（已脱敏）';}finally{clearTimeout(timer);}
}
async function main(){
 log('========== 爱企查每日任务 ==========');log(`开始时间 ${new Date(started).toISOString()}；模式 ${DRY?'断网预演':'实跑'}`);
 const lines=(E.AQC_ACCOUNTS||E.AQC||'').split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
 log(`账号数量 ${lines.length}`);const accounts=[];let configError=false;
 try{
 if(!lines.length) fail('请配置 AQC_ACCOUNTS，每行一个 Cookie，可加 |exportkey');
 const selected=new Set((E.AQC_TASKS||defaults.join(',')).split(',').map(s=>s.trim()).filter(Boolean));if(!selected.size||[...selected].some(c=>!names[c]||c==='CX12006')) fail('任务开关包含未知或不支持的任务编号');
 for(let i=0;i<lines.length;i++){
 const a={index:i+1,stats:stats(),words:['苹果','华为','百度','一个','百事','厚墨']};accounts.push(a);
 const valid=await stage(a,'账号参数检查',async()=>{const cut=lines[i].indexOf('|');a.cookie=cut<0?lines[i]:lines[i].slice(0,cut).trim();a.exportkey=cut<0?'':lines[i].slice(cut+1);if(!a.cookie||/[\r\n\x00-\x1f\x7f]/.test(a.cookie)) fail('账号 Cookie 格式错误');a.monitor=ids(E.AQC_MONITOR_IDS);a.follow=ids(E.AQC_FOLLOW_IDS);a.like=(E.AQC_LIKE_TARGET||'').split(',');if(selected.has('CX12001')&&!a.monitor.length) fail('添加监控需配置目标编号');if(selected.has('CX12002')&&!a.follow.length) fail('添加关注需配置目标编号');if(selected.has('CX12011')&&(a.like.length!==2||a.like.some(s=>!/^\d+$/.test(s)))) fail('点赞需配置互动编号和观点编号');if(selected.has('CX11010')&&!a.exportkey) fail('批量查询需要 exportkey');});
 if(!valid) {configError=true;log(`账号 ${a.index} 统计：总任务 ${a.stats.total}，成功 ${a.stats.success}，已完成 ${a.stats.alreadyComplete}，跳过 ${a.stats.skipped}，失败 ${a.stats.failed}，耗时 0 毫秒`);}
 if(valid&&DRY){await stage(a,'断网流程预演',async()=>{log(`已验证 ${selected.size} 个任务开关；不会签到、领取奖励或发送 HTTP 请求`);});log(`账号 ${a.index} DRY_RUN_OK`);log(`账号 ${a.index} 统计：总任务 ${a.stats.total}，成功 ${a.stats.success}，已完成 0，跳过 0，失败 0，耗时 0 毫秒`);}else if(valid) await runAccount(a,selected);
 }
 }catch(err){configError=true;log(`❌ 配置错误：${err instanceof SafeError?err.message:'配置解析失败'}`);}
 const steps=stats();for(const a of accounts) for(const k of Object.keys(steps)) steps[k]+=a.stats[k];
 const failed=accounts.filter(a=>a.stats.failed>0).length;const succeeded=accounts.length-failed;
 const code=configError||failed?1:0;
 const status=configError?'configuration-error':failed?(succeeded?'partial-failure':'failure'):DRY?'dry-run':'success';
 const summary={status,mode:DRY?'dry-run':'live',accounts:lines.length,succeeded,failed,steps,elapsedMs:Date.now()-started,exitCode:code};
 summary.notification=await notify(summary);
 log('----------------------------------------');log(`任务统计：账号 ${lines.length}，成功 ${succeeded}，失败 ${failed}；子任务总数 ${steps.total}，成功 ${steps.success}，已完成 ${steps.alreadyComplete}，跳过 ${steps.skipped}，失败 ${steps.failed}`);log(`通知状态：${summary.notification}；总耗时 ${Date.now()-started} 毫秒`);log(`完成时间 ${new Date().toISOString()}；最终状态 ${status}`);
 console.log('TASK_SUMMARY='+JSON.stringify(summary));process.exitCode=code;
 // 通知模块可能留下活动连接；保持业务退出码并限制收尾等待。
 if(!DRY) setTimeout(()=>process.exit(code),100).unref();
}
if(require.main===module) main();
module.exports={main};
