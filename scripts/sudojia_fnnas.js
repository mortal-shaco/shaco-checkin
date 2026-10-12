// name: 飞牛私有云签到
// cron: 10 0 * * *
/**
 * name: 飞牛私有云签到
 * cron: 10 0 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 基于 sudojia/AutoTaskScript src/web/sudojia_fnnas.js
 * 原作者 Telegram@sudojia，https://blog.imzjw.cn，2024/09/20
 * FN_NAS_COOKIE：登录 https://club.fnnas.com 后，在浏览器开发者工具的
 * 网络面板复制本站已登录请求的 Cookie，须包含 pvRK_2132_auth 和
 * pvRK_2132_saltkey；每行一个账号，完整 Cookie 不拆分。不要公开凭据。
 * FN_NAS_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * 依赖：Node.js >=18；npm install cheerio@1.0.0（由用户自行安装）。
 * 已移除自动关注固定用户和上游更新检查。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const BASE = 'https://club.fnnas.com';
const dry = process.env.FN_NAS_DRY_RUN === '1';
const started = Date.now();
const accounts = (process.env.FN_NAS_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const lines = [];
const totals = {total:0, success:0, alreadyComplete:0, skipped:0, failed:0};
function log(s) { const line = `[${new Date().toTimeString().slice(0,8)}] ${s}`; console.log(line); lines.push(line); }
function safe(s) {
  let v = String(s).replace(/[\r\n\t]+/g, ' ');
  for (const cookie of accounts) for (const part of cookie.split(';')) {
    const at = part.indexOf('='); const secret = part.slice(at+1).trim();
    if (at >= 0 && secret) v = v.split(secret).join('[凭据已隐藏]');
  }
  return v.replace(/\b1[3-9]\d{9}\b/g,'[手机号已隐藏]').replace(/(?:token|cookie|session|formhash)\s*[:=]\s*\S+/gi,'[敏感字段已隐藏]');
}
function request(url, cookie) {
  const u = new URL(url, BASE);
  if (u.origin !== BASE || u.username || u.password) throw Error('拒绝非本站地址');
  if (dry) throw Error('预演禁止网络请求');
  return new Promise((resolve,reject) => {
    let size=0; const chunks=[];
    const req=https.get(u,{headers:{Cookie:cookie,'User-Agent':'Mozilla/5.0','Accept-Encoding':'identity'}},res=>{
      if(res.statusCode!==200) { res.resume(); reject(Error(`HTTP 状态异常 ${res.statusCode}`)); return; }
      res.on('data',chunk=>{ size+=chunk.length; if(size>2*1024*1024) req.destroy(Error('响应过大')); else chunks.push(chunk); });
      res.on('end',()=>resolve(Buffer.concat(chunks).toString('utf8')));
      res.on('error',()=>reject(Error('响应读取失败')));
    });
    const timer=setTimeout(()=>req.destroy(Error('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer)); req.on('error',()=>reject(Error('请求失败或超时')));
  });
}
function authenticated($) { return $('a[href*="action=logout"][href*="formhash="]').length > 0; }
function signState($) {
  // 不能将“点击打卡”缺失当作成功；必须有明确的已打卡文案。
  const text=$('body').text();
  if(/今日已打卡|今天已打卡|今日已签到|今天已签到|您今天已经(?:打卡|签到)|您今日已经(?:打卡|签到)/.test(text)) return 'done';
  if(text.includes('点击打卡')) return 'pending';
  return 'unknown';
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if(dry) return '预演：已生成通知摘要，禁止发送网络通知';
  const files=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  for(const file of files) {
    if(!fs.existsSync(file)) continue;
    return new Promise(resolve=>{
      const child=spawn(process.execPath,['-e', 'Promise.resolve(require(process.argv[1]).sendNotify("飞牛私有云签到",process.argv[2])).catch(()=>process.exitCode=1)', file, body],{stdio:'ignore'});
      const timer=setTimeout(()=>{child.kill('SIGKILL'); resolve('通知超时');},20000);
      child.on('error',()=>{clearTimeout(timer);resolve('通知启动失败');});
      child.on('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':'通知失败');});
    });
  }
  return '通知不可用：未找到 sendNotify.js';
}
async function main() {
  log('========== 飞牛私有云签到 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${accounts.length}`);
  let ok=0, bad=0, configError=false;
  if(!accounts.length) { configError=true; log('❌ 配置错误：请设置 FN_NAS_COOKIE'); }
  for(let i=0;i<accounts.length;i++) {
    const begin=Date.now(), stats={total:4,success:0,alreadyComplete:0,skipped:0,failed:0};
    let stage=0;
    const run=async(name,fn)=>{stage++;const t=Date.now();log(`账号 ${i+1} 阶段 ${stage}/4：${name}`); let state; try { state=await fn(); } catch(e) { log(`账号 ${i+1} 阶段 ${stage} ❌ 失败；耗时 ${Date.now()-t}ms`); throw e; } stats[state==='already'?'alreadyComplete':dry?'skipped':'success']++;log(`账号 ${i+1} 阶段 ${stage} ${dry?'⏭️ 预演检查通过':state==='already'?'☑️ 已完成':'✅ 成功'}；耗时 ${Date.now()-t}ms`);};
    try {
      const cookie=accounts[i];
      if(!/(?:^|;\s*)pvRK_2132_auth=[^;\s]+/.test(cookie)||!/(?:^|;\s*)pvRK_2132_saltkey=[^;\s]+/.test(cookie)||/[\r\n\x00-\x1f]/.test(cookie)) throw Error('配置错误：Cookie 缺少必需字段或包含控制字符');
      let load, uid, formhash, signUrl;
      await run('读取身份和签到入口',async()=>{
        if(dry) return;
        try { load=require('cheerio').load; } catch { throw Error('缺少依赖 cheerio@1.0.0'); }
        const $=load(await request(BASE,cookie));
        if(!authenticated($)) throw Error('登录身份无法确认，请更新 Cookie');
        const href=$('.icon_msg a').first().attr('href');
        uid=href && new URL(href,BASE).searchParams.get('uid');
        const logout=$('li.l4 a[href*="formhash="]').attr('href');
        formhash=logout && new URL(logout,BASE).searchParams.get('formhash');
        const link=$('a[href*="plugin.php?id=zqlj_sign"]').first().attr('href');
        if(!uid || !/^\d+$/.test(uid) || !formhash || !link) throw Error('身份或签到参数解析失败');
        signUrl=new URL(link,BASE); if(signUrl.origin!==BASE || signUrl.pathname!=='/plugin.php' || signUrl.searchParams.get('id')!=='zqlj_sign') throw Error('签到入口不符合预期');
        log(`账号 ${i+1} 身份：${safe($('.quater_phone_nav .z').text().trim())}；公开 UID：${uid}`);
      });
      await run('签到并验证结果',async()=>{
        if(dry) return;
        let $=load(await request(signUrl,cookie));
        if(!authenticated($)) throw Error('签到页面登录失效');
        const state=signState($); if(state==='done') return 'already';
        if(state!=='pending') throw Error('签到状态未知，未执行变更');
        const action=new URL(signUrl); action.searchParams.set('sign',formhash);
        await request(action,cookie);
        $=load(await request(signUrl,cookie));
        if(!authenticated($)||signState($)!=='done') throw Error('未取得明确的今日签到成功证据');
        log('打卡成功！');
      });
      await run('查询打卡统计',async()=>{
        if(dry) return;
        const $=load(await request(signUrl,cookie)); if(!authenticated($)) throw Error('统计页面登录失效');
        const labels=['最近打卡','本月打卡','连续打卡','累计打卡','累计奖励','最近奖励','当前打卡'];
        const texts=$('.xl li').toArray().map(el=>$(el).text().trim());
        for(const label of labels) { const value=texts.find(s=>s.startsWith(label)); if(!value || !/\d/.test(value)) throw Error('打卡统计字段缺失或格式变化'); log(safe(value)); }
      });
      await run('查询积分和登录天数',async()=>{
        if(dry) return;
        const $=load(await request(`${BASE}/home.php?mod=space&uid=${uid}&do=profile&from=space`,cookie)); if(!authenticated($)) throw Error('积分页面登录失效');
        const values={}; $('.pf_l li').each((_,el)=>{const label=$(el).find('em').text().trim();values[label]=$(el).text().replace(label,'').trim();});
        for(const label of ['积分','牛值','飞牛币','登陆天数']) {const value=values[label];if(!value||!/^\d+(?:\s|$)/.test(value)) throw Error('积分字段缺失或格式变化'); log(`${label}：${parseInt(value,10)}`);}
      });
      ok++;
    } catch(e) { bad++;stats.failed++;stats.skipped=Math.max(0,4-stats.success-stats.alreadyComplete-stats.failed-stats.skipped)+stats.skipped; log(`❌ 账号 ${i+1}：${safe(e.message)}`); }
    for(const key of Object.keys(totals)) totals[key]+=stats[key];
    log(`账号 ${i+1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${Date.now()-begin}ms`);
  }
  const status=configError?'configuration-error':bad?(ok?'partial-failure':'failure'):dry?'dry-run':'success';
  const exitCode=configError||bad?1:0;
  log('----------------------------------------');
  log(`最终状态：${status}；账号总数 ${accounts.length}，成功 ${ok}，失败 ${bad}；子任务统计 ${JSON.stringify(totals)}`);
  const notification=await notify(lines.join('\n'));log(`通知状态：${notification}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now()-started}ms`);
  console.log('TASK_SUMMARY='+JSON.stringify({status,mode:dry?'dry-run':'live',accounts:accounts.length,success:ok,failed:bad,configurationError:configError,tasks:totals,notification,elapsedMs:Date.now()-started,exitCode}));
  process.exitCode=exitCode;
}
main();
