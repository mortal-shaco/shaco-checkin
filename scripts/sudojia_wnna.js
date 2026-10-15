// name: 薇诺娜专柜商城
// cron: 29 0 * * *
/**
 * name: 薇诺娜专柜商城
 * cron: 39 9 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者 Telegram@sudojia，https://blog.imzjw.cn
 * 来源 sudojia/AutoTaskScript src/wx_mini/sudojia_wnna.js
 * WNNA_TOKEN：打开微信小程序“薇诺娜专柜商城”，在本人授权的抓包环境中
 * 查看 api.qiumeiapp.com 请求体 appUserToken；每行一个账号，勿使用 & 分隔。
 * WNNA_DRY_RUN=1 完全断网预演。QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方业务依赖。签到日期按 Asia/Shanghai 计算。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const TITLE = '薇诺娜专柜商城';
const dry = process.env.WNNA_DRY_RUN === '1';
const started = Date.now();
const accounts = (process.env.WNNA_TOKEN || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const totals = {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
const results = [];
const summaries = [];
function log(s) { console.log(`[${new Date().toLocaleTimeString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false})}] ${s}`); }
function safe(value) {
    let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
    for (const token of accounts) s = s.split(token).join('[凭据已隐藏]');
    return s.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function request(endpoint, field, token) {
    return new Promise((resolve, reject) => {
        const body = new URLSearchParams({[field]: token}).toString();
        let timer;
        const req = https.request({hostname:'api.qiumeiapp.com', path:endpoint, method:'POST', headers:{
            'User-Agent':'Mozilla/5.0', 'Content-Type':'application/x-www-form-urlencoded',
            'Content-Length':Buffer.byteLength(body),
            Referer:'https://servicewechat.com/wx250394ab3f680bfa/599/page-frame.html',
            'Accept-Language':'zh-CN,zh;q=0.9'
        }}, res => {
            const chunks = []; let size = 0;
            res.on('data', chunk => {size += chunk.length; if(size > 1048576) req.destroy(new Error('响应过大')); else chunks.push(chunk);});
            res.on('error', () => reject(new Error('响应读取失败')));
            res.on('end', () => {
                clearTimeout(timer);
                if(res.statusCode !== 200) return reject(new Error('HTTP 状态异常'));
                let data; try {data = JSON.parse(Buffer.concat(chunks).toString('utf8'));} catch {return reject(new Error('响应不是有效 JSON'));}
                if(!data || data.code !== 200) return reject(new Error('业务状态未确认成功'));
                resolve(data.data);
            });
        });
        timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
        req.on('error', () => {clearTimeout(timer); reject(new Error('网络请求失败或超时'));});
        req.end(body);
    });
}
async function stage(index, number, title, stats, action) {
    const start = Date.now(); stats.total++;
    log(`账号 ${index} · 阶段 ${number} ${title}`);
    try {
        const result = await action();
        stats[result.kind || 'success']++;
        log(`账号 ${index} · ${result.kind === 'skipped' ? '⏭️' : result.kind === 'alreadyComplete' ? '☑️' : '✅'} ${safe(result.text)}（${Date.now()-start}ms）`);
        if(!dry) summaries.push(`账号 ${index}：${safe(result.text)}`);
        return true;
    } catch (e) {stats.failed++; log(`账号 ${index} · ❌ ${title}失败：${safe(e.message)}（${Date.now()-start}ms）`); return false;}
}
function number(value) {return (typeof value === 'number' || typeof value === 'string') && String(value).trim() !== '' && Number.isFinite(Number(value)) && Number(value) >= 0;}
async function notify(body) {
    if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
    if(dry) {log(`断网预演通知摘要：${body}`); return '断网预演，仅生成摘要';}
    const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
    const file = dirs.map(d => path.join(d,'sendNotify.js')).find(f => fs.existsSync(f));
    if(!file) return '不可用：未找到 sendNotify.js';
    return new Promise(resolve => {
        const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>{process.exitCode=1})', file, TITLE, body], {stdio:'ignore'});
        const timer = setTimeout(()=>{child.kill('SIGKILL');resolve('失败：通知超时');}, 20000);
        child.on('error', ()=>{clearTimeout(timer);resolve('失败：无法启动通知');});
        child.on('close', code=>{clearTimeout(timer);resolve(code===0?'已发送':'失败：通知模块异常');});
    });
}
async function main() {
    log(`========== ${TITLE} ==========`);
    log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式'}；账号数：${accounts.length}`);
    if(!accounts.length) log('❌ 配置错误：请设置 WNNA_TOKEN，每行一个账号');
    for(let i=0;i<accounts.length;i++) {
        const token = accounts[i], index = i+1, begin = Date.now();
        const stats = {total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
        await stage(index,1,'查询当日签到并按需签到',stats,async()=>{
            if(dry) return {kind:'skipped',text:'DRY_RUN_OK：已解析凭据；将查询签到状态，仅未签到时提交签到；未发起请求'};
            const data = await request('/zg-activity/zg-daily/getZgSigninCalendarNew','appUserToken',token);
            const day = new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Shanghai',day:'numeric'}).format(new Date());
            const list = data?.currentMonth?.signinList;
            if(!Array.isArray(list)) throw new Error('签到日历结构异常');
            const today = list.find(d=>d && Number(d.date) === Number(day));
            if(!today || ![0,1].includes(today.isSignin)) throw new Error('无法确认当日签到状态，未执行签到');
            if(today.isSignin===1) return {kind:'alreadyComplete',text:'今天已经签过到了'};
            log(`账号 ${index} · 已确认今日未签到，提交签到`);
            const signed = await request('/zg-activity/zg-daily/zgSigninNew','appUserToken',token);
            if(!number(signed?.signinCount)) throw new Error('签到响应缺少有效连续天数');
            return {text:`签到成功，已连续签到 ${signed.signinCount} 天`};
        });
        await stage(index,2,'查询账号身份、等级和积分',stats,async()=>{
            if(dry) return {kind:'skipped',text:'DRY_RUN_OK：将查询昵称、等级和积分；未发起请求'};
            const user = await request('/zgxcx/10001/getZgUserInfo','zgUserToken',token);
            if(!user || typeof user.nickname !== 'string' || typeof user.levelName !== 'string' || !number(user.winonaPoint)) throw new Error('用户信息结构异常');
            return {text:`${user.nickname}（${user.levelName}），当前积分：${user.winonaPoint}`};
        });
        for(const key of Object.keys(totals)) totals[key] += stats[key];
        results.push({account:index,status:stats.failed?'failed':dry?'dry-run':'success',...stats,durationMs:Date.now()-begin});
        log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now()-begin}ms`);
    }
    const failed = results.filter(r=>r.failed).length;
    const status = !accounts.length?'configuration-error':failed?(failed===accounts.length?'failure':'partial-failure'):dry?'dry-run':'success';
    process.exitCode = !accounts.length || failed ? 1 : 0;
    const body = `状态：${status}；账号总数 ${accounts.length}，成功 ${dry?0:accounts.length-failed}，失败 ${failed}，预演 ${dry?accounts.length:0}${summaries.length?'\n'+summaries.join('\n'):''}`;
    const notification = await notify(body);
    log('----------------------------------------');
    log(body); log(`子任务统计：${JSON.stringify(totals)}`);
    const finishedAt = new Date().toISOString();
    log(`通知：${notification}；总耗时：${Date.now()-started}ms；完成时间：${finishedAt}；最终状态：${status}`);
    console.log('TASK_SUMMARY='+JSON.stringify({task:TITLE,mode:dry?'dry-run':'live',status,accounts:accounts.length,success:dry?0:accounts.length-failed,failed,totals,results,notification,finishedAt,durationMs:Date.now()-started}));
}
main();
