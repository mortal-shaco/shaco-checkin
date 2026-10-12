// name: 奈雪点单
// cron: 36 9 * * *
/**
 * name: 奈雪点单
 * cron: 36 9 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_naixue.js
 * 保留 GPL-3.0 授权；维护版：独立请求、脱敏日志、离线预演。
 * NAIXUE_TOKEN：登录奈雪点单小程序，抓取 tm-api.pin-dao.cn 请求头
 * Authorization 的值，去掉 Bearer 前缀。每个非空行一个账号，不使用 & 或 @ 分隔。
 * NAIXUE_DRY_RUN=1 完全离线预演（通知也模拟）；QINGLONG_NOTIFY=0 关闭通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。运行时 Node.js >=18。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const baseUrl = 'https://tm-web.pin-dao.cn';
const openId = 'QL6ZOftGzbziPlZwfiXM';
const dry = process.env.NAIXUE_DRY_RUN === '1';
const tokens = (process.env.NAIXUE_TOKEN || '').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
const started = Date.now();
function log(s) { console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${s}`); }
function dateString(d) { return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
function identity(data) {
  for (const key of ['nickName', 'nickname', 'username', 'displayName', 'userId']) {
    const value = data[key];
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const s = String(value);
    if (!s || tokens.some(t => s.includes(t)) || /[\r\n\x00-\x1f]|(?:\+?86)?1[3-9]\d{9}/.test(s)) continue;
    log(`账号身份 ${key}：${s}`);
  }
}
async function request(token, endpoint, params) {
  if (dry) throw new Error('离线模式禁止请求');
  const payload = await getBody();
  Object.assign(payload.params, params);
  const body = JSON.stringify(payload);
  return new Promise((resolve,reject)=>{
    const req = https.request(baseUrl+endpoint, {method:'POST', headers:{
      'Content-Type':'application/json', 'Content-Length':Buffer.byteLength(body),
      Authorization:`Bearer ${token}`, Referer:baseUrl+'/', Origin:baseUrl,
      'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/6945'
    }},res=>{
      let size=0; const chunks=[];
      res.on('data', c=>{ size+=c.length; if(size>1048576) req.destroy(new Error('响应过大')); else chunks.push(c); });
      res.on('error',()=>reject(new Error('响应读取失败')));
      res.on('end',()=>{
        if(res.statusCode<200 || res.statusCode>=300) return reject(new Error(`HTTP 状态异常 ${res.statusCode}`));
        let data; try { data=JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return reject(new Error('响应不是有效 JSON')); }
        if(!data || data.code!==0 || !data.data || typeof data.data!=='object') return reject(new Error('业务未成功或响应结构异常'));
        resolve(data.data);
      });
    });
    const timer=setTimeout(()=>req.destroy(new Error('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',()=>reject(new Error('网络请求失败或超时')));
    req.end(body);
  });
}
async function notify(summary) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) { log('通知预演：'+summary); return '离线模拟'; }
  const files=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=files.find(f=>fs.existsSync(f));
  if(!file) return '不可用（未找到 sendNotify.js）';
  return new Promise(resolve=>{
    const child=spawn(process.execPath,['-e',"Promise.resolve().then(()=>require(process.argv[1]).sendNotify('奈雪点单',process.argv[2])).then(()=>process.exit(0),()=>process.exit(1))",file,summary],{stdio:'ignore'});
    const timer=setTimeout(()=>{child.kill('SIGKILL');resolve('失败（超时）');},15000);
    child.on('error',()=>{clearTimeout(timer);resolve('失败');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':'失败');});
  });
}
async function main() {
  log('========== 奈雪点单 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'离线预演':'正式执行'}；账号数：${tokens.length}`);
  const accounts=[];
  let configError=tokens.length===0;
  if(configError) log('❌ 配置错误：请设置 NAIXUE_TOKEN，每个非空行一个账号');
  for(let i=0;i<tokens.length;i++) {
    const begin=Date.now(), stats={account:i+1,total:3,success:0,alreadyComplete:0,skipped:0,failed:0};
    let authenticated=false, count;
    async function stage(n,title,fn) {
      const t=Date.now();log(`账号 ${i+1} 阶段 ${n}/3 ${title}`);
      try { const already=await fn(); if(already) stats.alreadyComplete++;else stats.success++;log(`账号 ${i+1} ${already?'☑️ 已完成':'✅ 成功'}：${title}；耗时 ${Date.now()-t}ms`); }
      catch(e) {stats.failed++;log(`账号 ${i+1} ❌ ${title}：${e.message}；耗时 ${Date.now()-t}ms`);}
    }
    await stage(1,'校验账号',async()=>{
      if(/[\s&@]/.test(tokens[i]) || /^Bearer/i.test(tokens[i])) throw new Error('凭据格式错误：去掉 Bearer 前缀，每行一个账号');
      if(dry) log('预演：校验凭据格式，不验证登录有效性');
      else identity(await request(tokens[i],'/user/base-userinfo',{}));
      authenticated=true;
    });
    if(authenticated) {
      await stage(2,'查询状态并按需签到',async()=>{
        if(dry) {log('预演：查询签到记录；未签到时提交签到；不发送请求');return;}
        const now=new Date(), today=dateString(now);
        const data=await request(tokens[i],'/user/sign/records',{signDate:dateString(new Date(now.getFullYear(),now.getMonth(),1)),startDate:today});
        if(typeof data.status!=='boolean' || !Number.isInteger(data.signCount) || data.signCount<0) throw new Error('签到状态或天数字段异常');
        count=data.signCount;log(`签到记录天数：${count}；今日${data.status?'已签到':'未签到'}`);
        if(data.status) return true;
        const result=await request(tokens[i],'/user/sign/save',{signDate:today});
        if(result.flag!==true) throw new Error('签到未获明确成功确认');
        log('签到成功');
      });
      await stage(3,'查询奈雪币',async()=>{
        if(dry) {log('预演：查询奈雪币，不发送请求');return;}
        const data=await request(tokens[i],'/user/account/user-account',{});
        if(!['number','string'].includes(typeof data.coin) || !/^\d+(?:\.\d+)?$/.test(String(data.coin))) throw new Error('奈雪币字段异常');
        log(`当前奈雪币：${data.coin}`);
      });
    } else {stats.skipped=2;log(`账号 ${i+1} 阶段 2/3、3/3 ⏭️ 跳过：账号校验失败；耗时 0ms`);}
    stats.durationMs=Date.now()-begin;accounts.push(stats);
    log(`账号 ${i+1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${stats.durationMs}ms`);
  }
  const failed=accounts.filter(a=>a.failed>0).length, success=accounts.length-failed;
  const status=configError?'configuration-error':failed?(success?'partial-failure':'failure'):(dry?'dry-run':'success');
  const summary={status,mode:dry?'dry-run':'live',total:tokens.length,success,failed,accounts};
  const body=`账号总数 ${tokens.length}，成功 ${success}，失败 ${failed}；状态 ${status}${dry?'（仅离线预演）':''}`;
  summary.notification=await notify(body);
  summary.durationMs=Date.now()-started;summary.finishedAt=new Date().toISOString();
  log('------------------------------');log(body);
  for(const key of ['total','success','alreadyComplete','skipped','failed']) log(`子任务 ${key}：${accounts.reduce((sum,a)=>sum+a[key],0)}`);
  log(`通知状态：${summary.notification}；总耗时 ${summary.durationMs}ms；完成时间 ${summary.finishedAt}；最终状态 ${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
  process.exitCode=configError||failed?1:0;
}
main().catch(()=>{console.error('任务运行异常（详情已脱敏）');process.exitCode=1;});

async function getBody() {
    const nonce = Array.from({length: 6}, () => crypto.randomInt(1, 10)).join('');
    const timestamp = Math.floor(Date.now() / 1000);
    const urlPath = `nonce=${nonce}&openId=${openId}&timestamp=${timestamp}`;
    // https://tm-web-cdn.pin-dao.cn/static/js/1.b718167c.chunk.js
    // var u = t.params && 26000252 === t.params.brand && c && t.common && "wxapp" === t.common.platform ? "sArMTldQ9tqU19XIRDMWz7BO5WaeBnrezA" : "iYkcDMF8Eti255hti5M629RQTQ4Z2XihG";
    const hmacDigest = crypto.createHmac('sha1', 'sArMTldQ9tqU19XIRDMWz7BO5WaeBnrezA')
        .update(urlPath)
        .digest();
    const signature = Buffer.from(hmacDigest).toString('base64');
    const common = {
        platform: 'wxapp',
        version: '5.2.38',
        imei: '',
        osn: 'microsoft',
        sv: 'Windows 10 x64',
        lang: 'zh_CN',
        currency: 'CNY',
        timeZone: '',
        nonce,
        openId,
        timestamp,
        signature
    };
    const params = {
        businessType: 1,
        brand: 26000252,
        tenantId: 1,
        channel: 2,
        stallType: null,
        storeId: '',
        storeType: '',
        cityId: '',
        appId: 'wxab7430e6e8b9a4ab'
    };
    return {
        common,
        params
    };
}

