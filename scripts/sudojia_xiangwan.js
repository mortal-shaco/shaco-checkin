// name: 享玩游戏APP
// cron: 33 0 * * *
/**
 * name: 享玩游戏APP
 * cron: 33 0 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 源作者：Telegram@sudojia https://blog.imzjw.cn
 * 来源：sudojia/AutoTaskScript src/client/sudojia_xiangwan.js
 * 提交：4a55327baed0321bdf95802a75cc8363cae118b0；独立维护版本。
 * Node.js >= 18，仅使用标准库。
 * XWGAME_ACCOUNTS：享玩游戏APP注册的手机号#登录密码，每个非空行一个账号。
 * 仅按首个 # 分割；密码内的 #、&、@ 均原样保留。不支持 & 分隔账号。
 * 在享玩游戏APP注册并设置登录密码；非短信验证码，无需抓包。
 * XWGAME_DRY_RUN=1 完全断网预演，不读写缓存、不发送通知。
 * XWGAME_TOKEN_CACHE：可选缓存文件路径，默认不保存 Token；启用后权限为 0600。
 * QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭。QINGLONG_NOTIFY_DIR 为通知模块目录。
 * 默认动作仅为登录、每日签到和查询余额；不兑换、不邀请、不发布内容。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');

const TITLE = '享玩游戏APP';
const DRY = process.env.XWGAME_DRY_RUN === '1';
const KEY = Buffer.from('5snOI0E5WUpP99pG5+fzug==', 'base64');
const IV = Buffer.from('KhVRUtkYTNM82dSDxb7/YQ==', 'base64');
const common = () => ({app_channel:'xw_100016', app_version:'1.3', invite_uid:'', app_os:'android', server_device_id:'176'});
const stamp = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = s => console.log(`[${stamp()}] ${s}`);
const encrypt = s => { const c = crypto.createCipheriv('aes-128-cbc', KEY, IV); return Buffer.concat([c.update(s, 'utf8'), c.final()]).toString('base64'); };
const decrypt = s => { const c = crypto.createDecipheriv('aes-128-cbc', KEY, IV); return Buffer.concat([c.update(s, 'base64'), c.final()]).toString('utf8'); };
const safeError = e => e && e.safe ? e.message : '处理异常（详细内容已隐藏）';
function fail(message) { const e = new Error(message); e.safe = true; return e; }

function request(endpoint, fields, token) {
    if (DRY) throw fail('预演禁止网络请求');
    const body = new URLSearchParams({params:encrypt(JSON.stringify({...common(), ...fields}))}).toString();
    return new Promise((resolve, reject) => {
        let done = false;
        const finish = (err, data) => { if (done) return; done = true; clearTimeout(timer); err ? reject(err) : resolve(data); };
        const headers = {'User-Agent':'okhttp/4.11.0', 'Content-Type':'application/x-www-form-urlencoded', 'Accept-Encoding':'identity', 'Content-Length':Buffer.byteLength(body)};
        if (token) headers.authorization = `Bearer ${token}`;
        const req = https.request({hostname:'sdk-api.xiangwan.com', path:endpoint, method:'POST', headers}, res => {
            if (res.statusCode !== 200) { res.resume(); finish(fail('HTTP 状态异常')); return; }
            const chunks = []; let size = 0;
            res.on('data', chunk => { size += chunk.length; if (size > 1024 * 1024) { finish(fail('响应超过大小限制')); res.destroy(); } else chunks.push(chunk); });
            res.on('error', () => finish(fail('响应读取失败')));
            res.on('end', () => {
                if (done) return;
                try {
                    let raw = Buffer.concat(chunks).toString('utf8').trim();
                    if (raw.startsWith('"')) raw = JSON.parse(raw);
                    if (typeof raw !== 'string' || !/^[A-Za-z0-9+/=\r\n]+$/.test(raw)) throw Error();
                    const data = JSON.parse(decrypt(raw));
                    if (!data || data.status_code !== 200) { finish(fail('接口业务未成功')); return; }
                    finish(null, data.data);
                } catch { finish(fail('响应格式或加密协议不匹配')); }
            });
        });
        const timer = setTimeout(() => { finish(fail('请求超时')); req.destroy(); }, 15000);
        req.on('error', () => finish(fail('网络请求失败')));
        req.end(body);
    });
}

const cachePath = process.env.XWGAME_TOKEN_CACHE;
async function cachedToken(account) {
    if (!cachePath) return null;
    try {
        const stat = await fs.lstat(cachePath);
        if (!stat.isFile() || (stat.mode & 0o077) !== 0 || stat.uid !== process.getuid?.()) throw Error();
        const cache = JSON.parse(await fs.readFile(cachePath, 'utf8'));
        return typeof cache[account] === 'string' ? cache[account] : null;
    } catch (e) { if (e.code !== 'ENOENT') log('⚠️ 缓存不可安全读取，改用密码登录'); return null; }
}
async function saveToken(account, token) {
    if (!cachePath) return;
    let handle;
    try {
        const flags = require('node:fs').constants;
        handle = await fs.open(cachePath, flags.O_RDWR | flags.O_CREAT | flags.O_NOFOLLOW, 0o600);
        const st = await handle.stat();
        if (!st.isFile() || st.nlink !== 1 || st.uid !== process.getuid?.() || (st.mode & 0o077) !== 0) throw Error();
        let cache = {};
        const old = await handle.readFile('utf8');
        if (old.trim()) { cache = JSON.parse(old); if (!cache || typeof cache !== 'object' || Array.isArray(cache)) throw Error(); }
        cache[account] = token;
        const data = Buffer.from(JSON.stringify(cache));
        await handle.write(data, 0, data.length, 0);
        await handle.truncate(data.length);
        log('✅ Token 缓存已更新（受限权限）');
    } catch { log('⚠️ Token 缓存未保存，不影响本次业务结果'); }
    finally { if (handle) await handle.close().catch(() => {}); }
}
function day() {
    return new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Shanghai', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date()).replace(/-/g, '');
}
function numeric(v) { return (typeof v === 'number' && Number.isFinite(v)) || (typeof v === 'string' && /^\d+(\.\d+)?$/.test(v)); }
async function runAccount(line, index) {
    const start = Date.now();
    const stats = {account:index, total:3, success:0, alreadyComplete:0, skipped:0, failed:0};
    let token;
    async function stage(n, label, fn) {
        const t = Date.now(); log(`账号 ${index} · 阶段 ${n}/3 ${label}`);
        try { await fn(); stats.success++; log(`✅ ${label}成功，耗时 ${Date.now()-t}ms`); return true; }
        catch(e) { stats.failed++; log(`❌ ${label}失败：${safeError(e)}，耗时 ${Date.now()-t}ms`); return false; }
    }
    const pos = line.indexOf('#');
    const account = pos > 0 ? line.slice(0, pos) : '';
    const password = pos > 0 ? line.slice(pos+1) : '';
    const loggedIn = await stage(1, DRY ? '参数校验与登录预演' : '登录', async () => {
        if (!/^1\d{10}$/.test(account) || !password) throw fail('参数格式错误，应为手机号#密码，每行一个账号');
        if (DRY) { log('⏭️ 参数有效；密码加密、登录和缓存读写均未执行'); return; }
        const cacheKey = crypto.createHash('sha256').update(account).digest('hex');
        token = await cachedToken(cacheKey);
        if (token) {
            try { await request('/me/member_account', {}, token); log('✅ 缓存 Token 验证成功'); return; }
            catch { token = null; log('⚠️ 缓存验证失败，回退密码登录'); }
        }
        const data = await request('/account/account_login', {account, password});
        if (!data || typeof data.token !== 'string' || !data.token.trim() || /[\r\n]/.test(data.token)) throw fail('登录未返回有效 Token');
        token = data.token;
        await saveToken(cacheKey, token);
    });
    if (loggedIn) {
        await stage(2, DRY ? '每日签到预演' : '每日签到', async () => {
            if (DRY) { log('⏭️ 将调用每日签到；未发出请求、未增加玩豆'); return; }
            const data = await request('/discover/sign', {days:day()}, token);
            if (!data || !numeric(data.score)) throw fail('签到响应缺少有效奖励数量');
            log(`签到成功，获得 ${data.score} 玩豆`);
        });
        await stage(3, DRY ? '用户信息查询预演' : '用户信息查询', async () => {
            if (DRY) { log('⏭️ 将查询官方昵称与玩豆余额；未发出请求'); return; }
            const data = await request('/me/member_info', {}, token);
            if (!data || !numeric(data.balance)) throw fail('用户信息响应缺少有效余额');
            if (typeof data.nickname === 'string' && data.nickname) log(`账号 ${index} 官方昵称：${data.nickname}`);
            log(`当前玩豆：${data.balance}`);
        });
    } else { stats.skipped = 2; log(`⏭️ 账号 ${index} 阶段 2/3、3/3 跳过：登录或参数失败`); }
    stats.durationMs = Date.now()-start;
    log(`账号 ${index} 统计：总任务 ${stats.total}，${DRY ? '预演通过' : '成功'} ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs}ms`);
    return stats;
}

async function notify(summary) {
    if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
    if (DRY) return '预演：已生成脱敏通知，禁止网络发送';
    const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
    for (const file of locations) {
        try { await fs.access(file); } catch { continue; }
        // 在子进程执行青龙通知：隔离其输出、异常和退出操作，避免污染业务状态。
        return new Promise(resolve => {
            const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))', file, TITLE, summary], {stdio:'ignore'});
            const timer = setTimeout(() => { child.kill('SIGKILL'); }, 15000);
            child.on('error', () => { clearTimeout(timer); resolve('通知失败，保留业务退出码'); });
            child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '通知失败，保留业务退出码'); });
        });
    }
    return '通知模块不可用，保留业务退出码';
}
async function main() {
    const start = Date.now();
    const lines = (process.env.XWGAME_ACCOUNTS || '').split(/\r?\n/).filter(s => s.trim());
    log(`========== ${TITLE} ==========`);
    log(`开始时间：${new Date(start).toISOString()}；模式：${DRY ? '断网预演' : '正式执行'}；账号数：${lines.length}`);
    const results = [];
    if (!lines.length) log('❌ 配置错误：未提供 XWGAME_ACCOUNTS');
    for (let i=0; i<lines.length; i++) results.push(await runAccount(lines[i], i+1));
    const success = results.filter(r => r.failed === 0).length;
    const failed = results.length-success;
    const code = !lines.length || failed ? 1 : 0;
    const status = !lines.length ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : DRY ? 'dry-run' : 'success';
    const tasks = results.reduce((a,r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, {total:0, success:0, alreadyComplete:0, skipped:0, failed:0});
    const body = `模式：${DRY ? '断网预演（非真实签到）' : '正式执行'}；状态：${status}；账号总数 ${lines.length}，成功数 ${success}，失败数 ${failed}；子任务总数 ${tasks.total}，通过 ${tasks.success}，失败 ${tasks.failed}，跳过 ${tasks.skipped}`;
    const notification = await notify(body);
    log('----------------------------------------'); log(body);
    log(`通知状态：${notification}`);
    const finish = new Date().toISOString();
    log(`完成时间：${finish}；总耗时 ${Date.now()-start}ms；最终状态：${status}`);
    console.log('TASK_SUMMARY='+JSON.stringify({task:TITLE, mode:DRY?'dry-run':'live', status, accounts:{total:lines.length, success, failed}, tasks, results, notification, startedAt:new Date(start).toISOString(), finishedAt:finish, durationMs:Date.now()-start, exitCode:code}));
    process.exitCode = code;
}
main();
