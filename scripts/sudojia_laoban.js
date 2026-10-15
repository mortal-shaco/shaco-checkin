// name: 老板电器服务微商城
// cron: 6 1 * * *
/**
 * name: 老板电器服务微商城
 * cron: 15 9 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 源作者：Telegram@sudojia https://blog.imzjw.cn，2024/07/19
 * 来源：sudojia/AutoTaskScript src/wx_mini/sudojia_laoban.js
 * 独立维护版本：Node.js >= 18，仅使用内置模块。
 * LAOBAN_OPENID：登录老板电器服务微商城微信小程序，抓取 vip.foxech.com
 * 请求正文中的 openid（不是请求头）；每行一个账号，不用 & 或 @ 分隔。
 * LAOBAN_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 * 默认仅签到、领取积分奖励、浏览商品和资讯、同步积分，不消费或修改资料。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const NAME = '老板电器服务微商城';
const dry = process.env.LAOBAN_DRY_RUN === '1';
const accounts = (process.env.LAOBAN_OPENID || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const started = Date.now();
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
const results = [];
const log = text => console.log(`[${new Date().toLocaleTimeString('zh-CN', { hour12: false })}] ${text}`);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function requireData(ok) { if (!ok) throw new Error('响应字段异常，未确认成功'); }
function number(value) { requireData((typeof value === 'number' || typeof value === 'string') && String(value).trim() !== '' && Number.isFinite(Number(value))); return Number(value); }
function today() { const p = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()); return ['year', 'month', 'day'].map(k => p.find(x => x.type === k).value).join(''); }
function request(openid, endpoint, extra = {}, sync = false) {
    if (dry) throw new Error('预演禁止网络请求');
    const timestamp = Date.now();
    const body = { timestamp, token: crypto.createHash('md5').update(`${timestamp}ae1fd50f${openid}`).digest('hex'), openid, ...extra };
    if (sync) body.is_need_sync = 1;
    const payload = JSON.stringify(body);
    return new Promise((resolve, reject) => {
        const req = https.request(`https://vip.foxech.com/index.php/api/${endpoint}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload), 'User-Agent': 'Mozilla/5.0', 'xweb_xhr': '1', 'Accept': '*/*', 'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty', 'Referer': 'https://servicewechat.com/wxc8c90950cf4546f6/157/page-frame.html' }
        }, res => {
            let size = 0; const chunks = [];
            res.on('data', chunk => { size += chunk.length; if (size > 1024 * 1024) req.destroy(new Error('响应过大')); else chunks.push(chunk); });
            res.on('error', () => reject(new Error('响应读取失败')));
            res.on('end', () => {
                if (res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP 状态异常（${res.statusCode}）`));
                try {
                    const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
                    if (!value || !['200', 200].includes(value.code)) throw new Error('业务接口未确认成功');
                    requireData(value.data && typeof value.data === 'object');
                    resolve(value.data);
                } catch (e) { reject(new Error(e.message === '业务接口未确认成功' ? e.message : '响应格式异常')); }
            });
        });
        const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
        req.on('close', () => clearTimeout(timer));
        req.on('error', () => reject(new Error('网络请求失败或超时')));
        req.end(payload);
    });
}
async function runAccount(openid, index) {
    const began = Date.now(); let stage = 0;
    const stats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
    async function step(title, action) {
        const begin = Date.now(); const n = ++stage; stats.total++;
        log(`账号 ${index} · 阶段 ${n} ${title} 开始`);
        try {
            const state = await action() || 'success'; stats[state]++;
            log(`账号 ${index} · 阶段 ${n} ${title} ${ {success:'✅ 成功', alreadyComplete:'☑️ 已完成', skipped:'⏭️ 跳过'}[state] } · 耗时 ${Date.now() - begin}ms`);
            return true;
        } catch (e) {
            stats.failure++;
            // 仅输出本脚本定义的错误，不转储底层异常、凭据或响应。
            log(`账号 ${index} · 阶段 ${n} ${title} ❌ 未确认成功 · 耗时 ${Date.now() - begin}ms`);
            return false;
        }
    }
    const api = (endpoint, extra, sync) => request(openid, endpoint, extra, sync);
    if (/[&@\s]/.test(openid)) {
        await step('账号配置检查', async () => { throw new Error('账号格式错误'); });
    } else if (dry) {
        for (const title of ['账号信息', '每日签到与连续奖励', '商品浏览及状态复查', '资讯浏览及状态复查', '积分同步查询']) {
            await step(title, async () => { log(`账号 ${index} 预演：已检查执行计划，不发送请求、不改变账号状态`); return 'skipped'; });
        }
    } else {
        const valid = await step('账号信息', async () => {
            const d = await api('member/get_member_info', {}, true);
            requireData(d.info && typeof d.info === 'object');
            if (typeof d.info.nickname === 'string' && d.info.nickname) log(`账号 ${index} 昵称：${JSON.stringify(d.info.nickname)}`);
        });
        if (valid) {
            let days;
            await step('每日签到', async () => {
                let d = await api('member/get_sign_week');
                requireData(Array.isArray(d.list)); days = number(d.day);
                log(`账号 ${index} 累计签到 ${days} 天`);
                const record = d.list.find(x => String(x.date) === today());
                requireData(record && [0, 1].includes(record.is_sign));
                if (record.is_sign === 1) return 'alreadyComplete';
                await sleep(1300);
                const signed = await api('member/user_sign', {}, true);
                log(`账号 ${index} 签到成功，积分 +${number(signed.score)}`);
                d = await api('member/get_sign_week');
                requireData(Array.isArray(d.list) && d.list.some(x => String(x.date) === today() && x.is_sign === 1));
                days = number(d.day);
            });
            await step('连续签到奖励列表', async () => {
                if (days === undefined) throw new Error('签到天数不可用');
                if (days < 7) { log(`账号 ${index} 尚未达到连续奖励查询天数`); return 'skipped'; }
                const d = await api('member/get_sign_prize_list'); requireData(Array.isArray(d.list));
                for (let i = 0; i < d.list.length; i++) {
                    const reward = d.list[i];
                    await step(`连续奖励 ${i + 1}`, async () => {
                        requireData([0, 1, 2].includes(reward.status));
                        if (reward.status === 2) return 'alreadyComplete';
                        if (reward.status === 0) return 'skipped';
                        requireData(['string', 'number'].includes(typeof reward.id));
                        await sleep(1200);
                        const r = await api('member/get_sign_prize', { id: reward.id });
                        log(`账号 ${index} 连续签到奖励领取成功，积分 +${number(r.score)}`);
                    });
                }
            });
            const missions = async () => { const d = await api('member/get_member_score_mission_list', {page:1, limit:10000}); requireData(Array.isArray(d.list)); return d.list; };
            let list;
            await step('积分任务列表', async () => { list = await missions(); });
            for (const id of [7, 8, 12]) {
                await step({7:'浏览三个商品',8:'秒杀任务',12:'浏览资讯'}[id], async () => {
                    requireData(list);
                    const task = list.find(x => x.id === id);
                    if (!task) { log(`账号 ${index} 接口未提供此任务`); return 'skipped'; }
                    requireData([0, 1].includes(task.isOver));
                    if (task.isOver === 1) return 'alreadyComplete';
                    if (id === 8) { log(`账号 ${index} 秒杀任务沿用上游停用状态，无可验证执行接口`); return 'skipped'; }
                    const type = id === 7 ? 'goods' : 'news';
                    const config = id === 7 ? {page:1,limit:20,category:3} : {page:1,list:20,category:4,flag:1};
                    const d = await api(`common/get_${type}_list`, config);
                    requireData(Array.isArray(d.list) && d.list.length > 0);
                    for (let i = 0; i < 3; i++) {
                        const item = d.list[i % d.list.length]; requireData(item && ['string','number'].includes(typeof item.id));
                        const detail = await api(`common/get_${type}_detail`, {id:item.id, ...(id === 7 ? {is_act:''} : {})});
                        requireData(detail.info && typeof detail.info === 'object');
                        log(`账号 ${index} 第 ${i + 1}/3 次浏览请求成功`); await sleep(5500);
                    }
                    const refreshed = (await missions()).find(x => x.id === id);
                    requireData(refreshed && refreshed.isOver === 1);
                    log(`账号 ${index} 浏览任务完成状态已核实`);
                });
            }
            await step('积分同步查询', async () => {
                const d = await api('member/sync_crm_member_score'); requireData(d.userinfo);
                log(`账号 ${index} 当前积分：${number(d.userinfo.score)}`);
            });
        } else {
            await step('后续账号动作', async () => { log(`账号 ${index} 身份校验失败，停止后续请求`); return 'skipped'; });
        }
    }
    for (const key of Object.keys(totals)) totals[key] += stats[key];
    const result = { account: index, status: stats.failure ? 'failure' : dry ? 'dry-run' : 'success', ...stats, durationMs: Date.now() - began };
    results.push(result);
    log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failure}，耗时 ${result.durationMs}ms`);
}
async function notify(body) {
    if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
    const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
    const file = dirs.map(d => path.resolve(d, 'sendNotify.js')).find(f => fs.existsSync(f));
    if (!file) return '不可用：未找到 sendNotify.js，保留业务退出码';
    // 预演也调用青龙通知入口，但封锁子进程网络和外部命令以保证完全断网。
    const code = `
        if (process.env.LAOBAN_DRY_RUN === '1') {
            const deny = () => { throw new Error('dry-run: network disabled'); };
            for (const m of ['http','https']) { const x = require(m); x.request = deny; x.get = deny; }
            const net = require('net'); net.connect = deny; net.createConnection = deny; net.Socket.prototype.connect = deny;
            require('tls').connect = deny; require('dgram').createSocket = deny; global.fetch = deny;
            const cp = require('child_process'); for (const k of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork']) cp[k] = deny;
        }
        Promise.resolve().then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).then(() => process.exit(0), () => process.exit(1));`;
    return new Promise(resolve => {
        const env = {...process.env}; delete env.LAOBAN_OPENID;
        const child = spawn(process.execPath, ['-e', code, file, NAME, body], {env, stdio:'ignore'});
        const timer = setTimeout(() => child.kill('SIGKILL'), 12000);
        child.on('error', () => { clearTimeout(timer); resolve('通知不可用，保留业务退出码'); });
        child.on('close', c => { clearTimeout(timer); resolve(c === 0 ? '已调用青龙通知' : dry ? '预演通知发送受断网限制，保留业务退出码' : '通知失败，保留业务退出码'); });
    });
}
async function main() {
    log(`========== ${NAME} ==========`);
    log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式运行'}；账号数：${accounts.length}`);
    let configError = !accounts.length;
    if (configError) log('❌ 配置错误：LAOBAN_OPENID 必须每行一个非空 openid，不支持 &、@ 或行内空白');
    else for (let i = 0; i < accounts.length; i++) await runAccount(accounts[i], i + 1);
    const failed = configError ? accounts.length : results.filter(x => x.failure).length;
    const success = results.filter(x => !x.failure).length;
    const status = configError ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
    process.exitCode = configError || failed ? 1 : 0;
    const body = `状态：${status}；账号总数：${accounts.length}；成功数：${success}；失败数：${failed}；子任务成功：${totals.success}；已完成：${totals.alreadyComplete}；跳过：${totals.skipped}；失败：${totals.failure}${dry ? '；仅断网预演，未验证业务结果' : ''}`;
    let notification;
    try { notification = await notify(body); } catch (_) { notification = '通知异常，保留业务退出码'; }
    log('----------------------------------------'); log(body);
    log(`通知状态：${notification}；总耗时：${Date.now() - started}ms；完成时间：${new Date().toISOString()}；最终状态：${status}`);
    if (dry && !process.exitCode) log('DRY_RUN_OK');
    if (status === 'success') log('LAOBAN_SUCCESS');
    console.log('TASK_SUMMARY=' + JSON.stringify({status, mode:dry?'dry-run':'live', accounts:accounts.length, success, failed, configurationError:configError, tasks:totals, results, notification, durationMs:Date.now()-started}));
}
main().catch(() => { process.exitCode = 1; log('❌ 未预期运行错误'); });
