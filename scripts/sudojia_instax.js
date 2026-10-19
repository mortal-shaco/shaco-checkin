// name: 玩拍由我俱乐部
// cron: 26 2 * * *
/**
 * name: 玩拍由我俱乐部
 * cron: 41 9 * * *
 * 富士 instax 小程序；上游 sudojia/AutoTaskScript
 * 原作者 Telegram@sudojia https://blog.imzjw.cn
 * 原文件 src/wx_mini/sudojia_instax.js；GPL-3.0（保留上游许可）
 * INSTAX_TOKEN：每个非空行一个 Authorization 值（去掉 Bearer）。
 * 在小程序「我的」绑定手机号加入会员；仅在本人授权的抓包中读取
 * https://instax.app.xcxd.net.cn 请求头 Authorization，不要分享凭据。
 * 可兼容 token#false；抽奖改为默认关闭，使用独立 INSTAX_DRAW=1 开启。
 * INSTAX_DRY_RUN=1 完全离线预演；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方业务依赖。抽奖会消耗机会，签到会改变签到状态/积分。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["e229880f6ad33d6f", "scripts/sudojia_instax.js", "sudojia_instax.js", "sudojia_instax"];
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
const dry = process.env.INSTAX_DRY_RUN === '1';
const lines = (process.env.INSTAX_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const secrets = lines.flatMap(x => [x, x.split('#')[0]]);
const title = '玩拍由我俱乐部';
const summary = { mode: dry ? 'dry-run' : 'live', accounts: lines.length, success: 0, failed: 0, tasks: {success:0, alreadyComplete:0, skipped:0, failed:0}, notification: 'pending' };
const stamp = () => new Date().toTimeString().slice(0, 8);
function safe(value) {
  let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const secret of secrets) if (secret) s = s.split(secret).join('[凭据已隐藏]');
  return s.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function log(s) { console.log(`[${stamp()}] ${s}`); }
function request(token, route, method = 'GET') {
  return new Promise((resolve, reject) => {
    const req = https.request({hostname:'instax.app.xcxd.net.cn', path:route, method,
      headers:{Authorization:`Bearer ${token}`, 'User-Agent':'Mozilla/5.0', Referer:'https://servicewechat.com/wx3cb572fbf3aa30c8/136/page-frame.html', 'Content-Type':'application/json', Accept:'application/json'}}, res => {
      const chunks=[]; let bytes=0;
      res.on('data', chunk => {bytes+=chunk.length; if(bytes>1048576) req.destroy(new Error('响应超限')); else chunks.push(chunk);});
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if(res.statusCode<200 || res.statusCode>=300) return reject(new Error(`HTTP ${res.statusCode}，未确认业务成功`));
        let data; try {data=JSON.parse(Buffer.concat(chunks).toString('utf8'));} catch {return reject(new Error('响应不是有效 JSON'));}
        if(!data || data.error !== false) return reject(new Error('接口未明确返回 error=false'));
        resolve(data.data);
      });
    });
    const timer=setTimeout(() => req.destroy(new Error('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',()=>reject(new Error('网络请求失败或超时')));
    req.end();
  });
}
const delay = ms => new Promise(r=>setTimeout(r,ms));
async function account(line, index) {
  const begin=Date.now(); const stats={success:0,alreadyComplete:0,skipped:0,failed:0}; let stage=0;
  async function step(name, action) {
    const n=++stage, t=Date.now(); log(`账号 ${index} · 阶段 ${n} ${name}`);
    try {const result=await action(); stats.success++; log(`✅ 账号 ${index} · 阶段 ${n} ${name}完成 (${Date.now()-t}ms)`); return result;}
    catch(e) {stats.failed++; log(`❌ 账号 ${index} · 阶段 ${n} ${e.message} (${Date.now()-t}ms)`); throw e;}
  }
  try {
    let token, draw;
    await step('参数检查',async()=>{
      const at=line.indexOf('#'); token=(at<0?line:line.slice(0,at)).trim(); const option=at<0?'':line.slice(at+1);
      if (!token || /\s|[&@]/.test(token) || (option && !['false','true'].includes(option))) throw new Error('账号格式无效，请使用每行一个令牌，可附加 #false');
      if(!['0','1',undefined].includes(process.env.INSTAX_DRAW)) throw new Error('INSTAX_DRAW 仅支持 0 或 1');
      draw=process.env.INSTAX_DRAW==='1' && option!=='false';
    });
    if(dry) {
      await step('离线流程预演', async()=>log(`账号 ${index}：将查询身份、积分、等级并签到；抽奖${draw?'已显式开启':'关闭'}；不发送任何网络请求`));
      stats.skipped+=draw?3:1;
    } else {
      const user=await step('查询账号信息',async()=>{
        const data=await request(token,'/api/me'); const u=data && data.user;
        if(!u || !['string','number'].includes(typeof u.id) || !String(u.id)) throw new Error('账号响应缺少有效用户 ID');
        if(typeof u.nickname==='string') log(`昵称：${safe(u.nickname)}`);
        log(`公开 UID：${safe(u.id)}`);
        if(['string','number'].includes(typeof u.credit)) log(`当前积分：${safe(u.credit)}`);
        if(['string','number'].includes(typeof u.user_level_id)) log(`等级：${safe(u.user_level_id)}`);
        return u;
      });
      const base=`/api/user/${encodeURIComponent(user.id)}`;
      await delay(1600);
      await step('每日签到',()=>request(token,`${base}/sign-activity/25/sign`,'POST'));
      if(!draw) {stats.skipped++; log(`⏭️ 账号 ${index} · 阶段 ${++stage} 抽奖未开启 (0ms)`);}
      else {
        const chance=()=>step('查询抽奖次数',async()=>{
          const n=await request(token,`${base}/draw-activities/42/chance`);
          if(!Number.isSafeInteger(n) || n<0) throw new Error('抽奖次数格式无效'); return n;
        });
        let count=await chance(); const limit=count; let draws=0;
        while(count>0) {
          if(draws>=limit) throw new Error('抽奖次数超过初始机会，停止执行');
          await delay(3200);
          await step('执行抽奖',async()=>{
            const d=await request(token,`${base}/draw-activities/42/draw`,'POST');
            if(!d || !d.record || typeof d.record.desc!=='string') throw new Error('抽奖响应缺少中奖结果，不重试');
            log(`抽奖获得：${safe(d.record.desc)}`);
          }); draws++;
          await delay(2300); const next=await chance();
          if(next>=count) {await step('抽奖进度检查',async()=>{throw new Error('机会未递减，停止抽奖以避免重复消耗');});}
          count=next;
        }
        log(`☑️ 账号 ${index} 抽奖机会已用完`);
      }
    }
    summary.success++;
  } catch { summary.failed++; if(!stats.failed) stats.failed++; }
  for(const k of Object.keys(stats)) summary.tasks[k]+=stats[k];
  log(`账号 ${index} 统计：总任务 ${Object.values(stats).reduce((a,b)=>a+b,0)}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now()-begin}ms`);
}
async function notify(body) {
  if(['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY||'1').toLowerCase())) return 'disabled';
  // 离线预演优先保证零网络；输出相同脱敏通知正文，不调用可能联网的通知模块。
  if(dry) {log(`离线通知预演：${body}`); return 'dry-run-local';}
  const files=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file=files.find(f=>fs.existsSync(f)); if(!file) return 'unavailable';
  return new Promise(resolve=>{
    const child=spawn(process.execPath,['-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))',file,title,body],{stdio:'ignore'});
    const timer=setTimeout(()=>{child.kill('SIGKILL');resolve('failed');},20000);
    child.on('error',()=>{clearTimeout(timer);resolve('failed');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'sent':'failed');});
  });
}
(async()=>{
  log(`===== ${title} =====`); log(`开始时间：${new Date(started).toISOString()}；模式：${summary.mode}；账号数：${lines.length}`);
  let configError=false;
  if(!lines.length || ![undefined,'0','1'].includes(process.env.INSTAX_DRY_RUN)) {configError=true;log('❌ 阶段 1 配置错误：需提供 INSTAX_TOKEN，INSTAX_DRY_RUN 仅支持 0 或 1 (0ms)');}
  else for(let i=0;i<lines.length;i++) await account(lines[i],i+1);
  const code=configError || summary.failed ? 1:0;
  summary.status=configError?'configuration-error':summary.failed?(summary.success?'partial-failure':'failure'):(dry?'dry-run':'success');
  summary.notification=await notify(`模式：${summary.mode}；账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；状态：${summary.status}`);
  summary.durationMs=Date.now()-started;
  log('--------------------------------');
  log(`任务统计：账号 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；子任务 ${JSON.stringify(summary.tasks)}；总耗时 ${summary.durationMs}ms`);
  log(`完成时间：${new Date().toISOString()}；最终状态：${summary.status}；通知状态：${summary.notification}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`); process.exitCode=code;
})().catch(()=>{process.exitCode=1; console.error('任务内部异常，未确认成功');});
