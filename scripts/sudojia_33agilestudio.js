// name: 33台词每日签到
// cron: 24 0 * * *
/**
 * name: 33台词每日签到
 * cron: 1 11 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者：Telegram@sudojia，https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/web/sudojia_33agilestudio.js
 * 独立维护版本，Node.js >= 18，无第三方业务依赖。
 * 登录 https://33.agilestudio.cn 注册并设置邮箱密码。
 * AGILE_STUDIO_ACCOUNTS：每个非空行一个 邮箱#密码，仅首个 # 是分隔符。
 * AGILE_STUDIO_DRY_RUN=1：只校验配置及演示流程，不登录、不签到、不联网通知。
 * QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const dry = process.env.AGILE_STUDIO_DRY_RUN === '1';
const started = Date.now();
const lines = (process.env.AGILE_STUDIO_ACCOUNTS || '').split(/\r?\n/).filter(x => x.trim());
const secrets = lines.flatMap(line => { const n = line.indexOf('#'); return n < 0 ? [line] : [line, line.slice(0,n), line.slice(n+1)]; }).filter(Boolean);
function safeIdentity(value) {
    let s = String(value);
    for (const secret of secrets) s = s.split(secret).join('[已隐藏]');
    return s.replace(/\b\d{11}\b/g, '[手机号已隐藏]').replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
}
function log(s) { console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${s}`); }
function api(endpoint, method, token, body = {}) {
    return new Promise((resolve, reject) => {
        const params = {_platform:'web', _versioin:'0.2.5', _ts:Date.now()-9999};
        const sign = Object.keys(params).sort().map(k => `${k}=${params[k]},`).join('');
        const headers = {'User-Agent':'Mozilla/5.0', Accept:'application/json, text/plain, */*', Origin:'https://33.agilestudio.cn', 'Content-Type':'application/json;charset=UTF-8', 'X-Signature':crypto.createHash('md5').update(sign).digest('hex')};
        if (token) headers['X-Token'] = token;
        const payload = method === 'POST' ? JSON.stringify(body) : null;
        if (payload) headers['Content-Length'] = Buffer.byteLength(payload);
        const req = https.request(`https://ssv-api.agilestudio.cn/api${endpoint}?${new URLSearchParams(params)}`, {method, headers}, res => {
            let size = 0; const chunks = [];
            res.on('data', b => { size += b.length; if (size > 1024*1024) req.destroy(new Error('响应超过限制')); else chunks.push(b); });
            res.on('error', () => reject(new Error('响应读取失败')));
            res.on('end', () => {
                if (res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP 状态异常（${res.statusCode}）`));
                try { const data = JSON.parse(Buffer.concat(chunks).toString()); if (!data || data.code !== 0) throw new Error(); resolve(data.data); }
                catch { reject(new Error('响应格式异常或业务未成功（要求 code=0）')); }
            });
        });
        const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
        req.on('close', () => clearTimeout(timer));
        req.on('error', () => reject(new Error('网络请求失败或超时')));
        req.end(payload);
    });
}
async function notify(body) {
    if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
    if (dry) return '预演已生成脱敏通知，跳过联网投递';
    const paths = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
    const file = paths.find(p => fs.existsSync(p));
    if (!file) return '通知模块不可用，保留业务退出码';
    return new Promise(resolve => {
        const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify("33台词每日签到",process.argv[2])).then(()=>process.exit(0),()=>process.exit(1))';
        const child = spawn(process.execPath, ['-e',code,file,body], {stdio:'ignore'});
        const timer = setTimeout(() => child.kill('SIGKILL'), 20000);
        child.on('error', () => { clearTimeout(timer); resolve('通知失败，保留业务退出码'); });
        child.on('close', c => { clearTimeout(timer); resolve(c === 0 ? '通知已发送' : '通知失败，保留业务退出码'); });
    });
}
async function main() {
    log('========== 33台词每日签到 ==========');
    log(`开始时间：${new Date(started).toISOString()} | 模式：${dry ? '断网预演':'正式运行'} | 账号数：${lines.length}`);
    const accounts = [];
    for (let i=0; i<lines.length; i++) {
        const begin = Date.now();
        const stat = {account:i+1,total:4,success:0,alreadyComplete:0,skipped:0,failed:0};
        const delimiter = lines[i].indexOf('#');
        const email = lines[i].slice(0,delimiter).trim();
        const password = lines[i].slice(delimiter+1);
        let token;
        const actions = [
            ['登录', async () => { const d = await api('/auth/email-login','POST',null,{email,password}); if (!d || typeof d.token !== 'string' || !d.token || /[\r\n]/.test(d.token)) throw new Error('登录响应缺少有效令牌'); token=d.token; secrets.push(token); return '登录成功'; }],
            ['查询账户信息', async () => { const d = await api('/user/my-info','GET',token); if (!d || typeof d !== 'object' || Array.isArray(d)) throw new Error('账户信息格式异常'); const ids = ['nickname','username','displayName','display_name','uid','publicUid'].filter(k => typeof d[k] === 'string' || typeof d[k] === 'number').map(k => `${k}：${safeIdentity(d[k])}`); return `账户信息查询成功${ids.length ? ' | '+ids.join(' | ') : '（未返回公开身份，使用账号序号）'}`; }],
            ['每日签到', async () => { await api('/integral/do-daily-check','POST',token); return '签到成功'; }],
            ['查询积分', async () => { const d = await api('/user/user-info','GET',token); if (!d || !['string','number'].includes(typeof d.integral) || !/^\d+(\.\d+)?$/.test(String(d.integral))) throw new Error('积分响应格式异常'); return `当前积分：${d.integral}`; }]
        ];
        if (delimiter <= 0 || !/^[^\s@]+@[^\s@]+$/.test(email) || !password) {
            stat.failed=1; stat.skipped=3;
            log(`账号 ${i+1} 阶段 1/4 配置校验 ❌ 格式必须为邮箱#密码；其余 3 阶段跳过 | 耗时 ${Date.now()-begin}ms`);
        } else for (let n=0; n<actions.length; n++) {
            const t = Date.now(); const [label, action] = actions[n];
            if (dry) { stat.skipped++; log(`账号 ${i+1} 阶段 ${n+1}/4 ${label} ⏭️ 预演校验通过，无网络及状态变更 | 耗时 ${Date.now()-t}ms`); continue; }
            if (n && !token) { stat.skipped++; log(`账号 ${i+1} 阶段 ${n+1}/4 ${label} ⏭️ 登录失败，跳过 | 耗时 ${Date.now()-t}ms`); continue; }
            if (n) await new Promise(resolve => setTimeout(resolve, 1500));
            try { const result = await action(); stat.success++; log(`账号 ${i+1} 阶段 ${n+1}/4 ${label} ✅ ${result} | 耗时 ${Date.now()-t}ms`); }
            catch(e) { stat.failed++; log(`账号 ${i+1} 阶段 ${n+1}/4 ${label} ❌ ${e.message} | 耗时 ${Date.now()-t}ms`); }
        }
        stat.durationMs=Date.now()-begin; accounts.push(stat);
        log(`账号 ${i+1} 统计：任务 ${stat.total}，成功 ${stat.success}，已完成 ${stat.alreadyComplete}，跳过 ${stat.skipped}，失败 ${stat.failed}，耗时 ${stat.durationMs}ms`);
    }
    const failed = accounts.filter(a => a.failed).length;
    const success = dry ? 0 : accounts.length-failed;
    const status = !lines.length ? 'configuration-error' : failed ? (failed===lines.length?'failure':'partial-failure') : dry ? 'dry-run':'success';
    process.exitCode = !lines.length || failed ? 1 : 0;
    if (!lines.length) log('❌ 配置错误：AGILE_STUDIO_ACCOUNTS 未提供非空账号');
    const totals = accounts.reduce((s,a) => { for (const k of Object.keys(s)) s[k]+=a[k]; return s; },{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
    const body = `状态：${status}；账号总数 ${lines.length}，成功 ${success}，失败 ${failed}，预演通过 ${dry ? lines.length-failed:0}；子任务成功 ${totals.success}，失败 ${totals.failed}，跳过 ${totals.skipped}`;
    let notification; try { notification=await notify(body); } catch { notification='通知失败，保留业务退出码'; }
    log('----------------------------------------'); log(body);
    log(`子任务统计：${JSON.stringify(totals)}`);
    log(`完成时间：${new Date().toISOString()} | 总耗时：${Date.now()-started}ms | 通知：${notification} | 最终状态：${status}`);
    console.log('TASK_SUMMARY='+JSON.stringify({task:'33台词每日签到',mode:dry?'dry-run':'live',status,accountCount:lines.length,success,failed,accounts,totals,notification,durationMs:Date.now()-started}));
}
main().catch(() => { process.exitCode=1; console.error('任务发生内部异常，已隐藏异常详情'); });
