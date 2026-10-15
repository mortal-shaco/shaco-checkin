// name: 胖哥俩肉蟹煲
// cron: 7 1 * * *
/**
 * name: 胖哥俩肉蟹煲
 * cron: 19 6 * * *
 * 来源：sudojia/AutoTaskScript，Telegram@sudojia，https://blog.imzjw.cn
 * 原文件 src/wx_mini/sudojia_pangGe.js；许可证 GPL-3.0，保留原作者署名。
 * PANG_GE_TOKEN：打开微信胖哥俩肉蟹煲小程序并登录，在本人授权抓包中
 * 获取 https://saash5.namek.com.cn 请求头 token。每个非空行一个账号，不用 & 分隔。
 * PANG_GE_DRY_RUN=1：仅本地预演，通知也模拟，绝不联网。
 * QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭。QINGLONG_NOTIFY_DIR 可指定通知模块目录。
 * Node.js >=18；无需安装依赖。不自动更新，不输出手机号及原始响应。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const title = '胖哥俩肉蟹煲';
const dry = process.env.PANG_GE_DRY_RUN === '1';
const tokens = (process.env.PANG_GE_TOKEN || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const start = Date.now();
const totals = {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
let ok = 0, failed = 0;
function log(s) { console.log(`[${new Date().toTimeString().slice(0,8)}] ${s}`); }
function identity(member) {
  for (const k of ['nickname', 'username', 'displayName']) {
    if (typeof member?.[k] === 'string' && member[k]) {
      const value = member[k];
      if (tokens.some(t => value.includes(t)) || /[\r\n\x00-\x1f]/.test(value) || /\b1[3-9]\d{9}\b/.test(value)) continue;
      log(`账号身份：${value}`); return;
    }
  }
}
function number(v) { if (typeof v !== 'number' || !Number.isFinite(v) || v < 0) throw Error('响应数值字段无效'); return v; }
function signedHeaders(token) {
  const timestamp = Date.now();
  const nonce = `174088${crypto.randomInt(100000,1000000)}` + Array.from(crypto.randomBytes(16), b => String.fromCharCode(65+b%26)).join('');
  return {deviceWidth:'414', clientVersionType:'1', serviceId:'namek-saas-web-page', accessPageType:'2', pageCatetory:'2', guidePageType:'13', deviceHeight:'780', clientVersion:'3.13.8', tenantId:'24', 'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 MicroMessenger/8.0', 'Content-Type':'application/json;charset=UTF-8', Referer:'https://servicewechat.com/wxe61905cae01a6c7d/81/page-frame.html', 'Accept-Language':'zh-CN,zh;q=0.9', token, timestamp:String(timestamp), nonce, sign:crypto.createHash('md5').update(`nonce=${nonce}&tenantId=24&timestamp=${timestamp}&token=${token}udHw9173SheXhd`).digest('hex')};
}
function request(token, route, method='GET') {
  if (dry) throw Error('预演禁止网络');
  return new Promise((resolve,reject) => {
    let timer;
    const req = https.request(new URL('https://saash5.namek.com.cn' + route), {method,headers:signedHeaders(token)}, res => {
      let size=0; const chunks=[];
      res.on('data', chunk => {size+=chunk.length; if(size>1048576) req.destroy(Error('响应过大')); else chunks.push(chunk);});
      res.on('error', () => reject(Error('响应读取失败')));
      res.on('end', () => {
        clearTimeout(timer);
        if(res.statusCode !== 200) return reject(Error('HTTP 请求失败'));
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if(data?.header?.code !== 0) throw Error('业务未确认成功');
          if(!data.body || typeof data.body !== 'object') throw Error('响应结构无效');
          resolve(data.body);
        } catch { reject(Error('业务失败或响应结构无效')); }
      });
    });
    timer=setTimeout(() => req.destroy(Error('请求超时')),15000);
    req.on('error', () => {clearTimeout(timer);reject(Error('网络请求失败或超时'));});
    req.end();
  });
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if(dry) {log('通知预演：'+body); return '预演完成（未联网）';}
  const candidates=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=candidates.find(f => fs.existsSync(f));
  if(!file) return '不可用（未找到 sendNotify.js）';
  return new Promise(resolve => {
    let done=false;
    const child=spawn(process.execPath,['-e',"Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))",file,title,body],{stdio:'ignore'});
    const finish = s => {if(done)return;done=true;clearTimeout(timer);resolve(s);};
    const timer=setTimeout(()=>{child.kill('SIGKILL');finish('失败（超时）');},20000);
    child.on('error',()=>finish('失败'));child.on('exit',code=>finish(code===0?'已发送':'失败'));
  });
}
async function main() {
  log(`========== ${title} ==========`);
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${tokens.length}`);
  if(!tokens.length) log('❌ 配置错误：请设置 PANG_GE_TOKEN，每个非空行一个账号');
  for(let i=0;i<tokens.length;i++) {
    const begun=Date.now(), stats={total:4,success:0,alreadyComplete:0,skipped:0,failed:0};
    let memberId, stopped=false;
    log(`账号 ${i+1} 开始`);
    const stages=[['登录校验',async()=>{const b=await request(tokens[i],'//api/v1/member/info/byToken?tenantId=24&agreementVer=');if(!b.member)throw Error('登录无效');identity(b.member);}],
      ['账号信息',async()=>{const b=await request(tokens[i],'//api/v1/member/index/personal?needPoints=1&needBalance=0&needCouponCount=1&needActivityCount=1&needFrozenState=0'); const id=b.member?.id;if(!/^\d+$/.test(String(id)))throw Error('会员标识缺失');memberId=String(id);identity(b.member);}],
      ['签到状态与签到',async()=>{const route='//api/v1/ope/checkin/100135/member?totalSignDayList=';const b=await request(tokens[i],route);log(`连续签到 ${number(b.signContinuedCount)} 天，累计 ${number(b.signTotalCount)} 天`);if(b.isSignToday===true || b.isSignToday===1) return 'already';if(b.isSignToday!==false && b.isSignToday!==0)throw Error('签到状态无效'); const signed=await request(tokens[i],'//api/v1/ope/checkin/member/sign','POST');log(`签到接口确认成功，积分 +${number(signed.getPoint)}`);const verified=await request(tokens[i],route);if(verified.isSignToday!==true && verified.isSignToday!==1)throw Error('签到后状态未确认');log('签到成功，已复核今日签到状态');}],
      ['积分查询',async()=>{const b=await request(tokens[i],`//api/v1/member/${memberId}/points/changed/list?startIndex=0&pageCount=20&shopId=24&memberId=${memberId}`);log(`当前积分：${number(b.points)}`);}]];
    for(let j=0;j<stages.length;j++) {
      const t=Date.now(), [name,run]=stages[j];log(`账号 ${i+1} 阶段 ${j+1}/4：${name}`);
      if(stopped){stats.skipped++;log('⏭️ 前置条件失败，跳过；耗时 0ms');continue;}
      try {if(/[\x00-\x20\x7f-\uffff]/.test(tokens[i]))throw Error('Token 格式无效');if(dry){log('⏭️ 预演：请求及状态变更均未执行');stats.skipped++;}else{const result=await run();if(result==='already'){stats.alreadyComplete++;log('☑️ 今日已签到');}else{stats.success++;log('✅ 阶段成功');}}}
      catch {stats.failed++;log('❌ 阶段失败：请求、业务状态或必要字段未通过校验；请核对凭据与服务接口');if(j<2)stopped=true;}
      log(`阶段耗时 ${Date.now()-t}ms`);
    }
    if(stats.failed)failed++;else ok++;
    for(const key of Object.keys(totals))totals[key]+=stats[key];
    log(`账号 ${i+1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${Date.now()-begun}ms`);
  }
  const code=failed || !tokens.length ? 1:0;
  const status=!tokens.length?'configuration-error':failed?(ok?'partial-failure':'failure'):dry?'dry-run':'success';
  const body=`模式：${dry?'断网预演':'正式执行'}；账号总数 ${tokens.length}，成功 ${ok}，失败 ${failed}；状态 ${status}；子任务成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`;
  let notification;try{notification=await notify(body);}catch{notification='失败';}
  log('----------------------------------------');log(body);log(`通知状态：${notification}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now()-start}ms；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:title,mode:dry?'dry-run':'live',accounts:tokens.length,success:ok,failed,stages:totals,status,notification,elapsedMs:Date.now()-start}));
  process.exitCode=code;
}
main();
