// name: 特步会员中心
// cron: 26 10 * * *
/**
 * name: 特步会员中心
 * cron: 26 10 * * *
 * 特步会员中心小程序；来源 sudojia/AutoTaskScript/src/wx_mini/sudojia_tebu.js
 * 原作者 Telegram@sudojia，https://blog.imzjw.cn；许可证 GPL-3.0。
 * 本维护版本依 GPL-3.0 发布，保留原作者署名；无更新检查或安装引导。
 * Node.js >= 18，无第三方业务依赖。
 * TEBU_TOKEN：登录特步会员中心小程序，抓取发往
 * https://mall-mobile-v6.vecrp.com 的请求头 token；每个非空行一个账号。
 * 不支持 & 或 @ 分隔账号；不要填入 Cookie 或整个请求头。
 * TEBU_DRY_RUN=1：完全断网预演，不签到，不加载通知模块，仅生成通知摘要。
 * QINGLONG_NOTIFY 默认 1，0/false/no/off 关闭；QINGLONG_NOTIFY_DIR 可指定通知目录。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const TITLE = '特步会员中心';
const BASE = 'https://mall-mobile-v6.vecrp.com';
const SHOP = '100656040';
const dry = process.env.TEBU_DRY_RUN === '1';
const tokens = (process.env.TEBU_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const started = Date.now();
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const results = [];
let configError = false;
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = s => console.log(`[${stamp()}] ${s}`);
const number = x => (typeof x === 'number' && Number.isFinite(x)) || (typeof x === 'string' && /^-?\d+(\.\d+)?$/.test(x));
function request(token, route, body) {
    return new Promise((resolve, reject) => {
        const payload = body === undefined ? undefined : JSON.stringify(body);
        const req = https.request(BASE + route, {
            method: payload === undefined ? 'GET' : 'POST',
            headers: {
                'user-agent': 'Mozilla/5.0', ts: String(Date.now()), token,
                'Content-Type': 'application/json;charset=UTF-8', appid: 'wx12e1cb3b09a0e6f0',
                Referer: 'https://servicewechat.com/wx12e1cb3b09a0e6f0/132/page-frame.html',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {})
            }
        }, res => {
            const chunks = []; let bytes = 0;
            res.on('data', chunk => {
                bytes += chunk.length;
                if (bytes > 1048576) req.destroy(new Error('响应超过大小限制'));
                else chunks.push(chunk);
            });
            res.on('error', () => reject(new Error('响应读取失败')));
            res.on('end', () => {
                if (res.statusCode < 200 || res.statusCode >= 300) return reject(new Error(`HTTP 状态异常（${res.statusCode}）`));
                try {
                    const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
                    if (!data || data.success !== true) throw new Error('接口未明确确认业务成功');
                    resolve(data.result);
                } catch (e) {
                    reject(new Error(e.message === '接口未明确确认业务成功' ? e.message : '响应格式无法识别'));
                }
            });
        });
        const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
        req.on('close', () => clearTimeout(timer));
        req.on('error', e => reject(new Error(e.message === '请求超时' ? '请求超时' : '网络请求失败')));
        if (payload) req.write(payload);
        req.end();
    });
}
function signDate() {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
    const p = Object.fromEntries(parts.map(x => [x.type, x.value]));
    return `${p.year}-${p.month}-${p.day}`;
}
function identity(customer) {
    // 仅输出官方明确的公开身份字段，不输出手机号、会话或原始对象。
    for (const key of ['customerName', 'nickname', 'username', 'displayName', 'publicUid']) {
        const value = customer[key];
        if (typeof value !== 'string' && typeof value !== 'number') continue;
        const s = String(value);
        if (!s || /[\r\n\x00-\x1f]/.test(s) || /(?:\+?86[- ]?)?1[3-9]\d{9}/.test(s) || tokens.some(t => s.includes(t))) continue;
        log(`官方账号身份：${s}`);
    }
}
async function account(token, index) {
    const begin = Date.now();
    const stats = { total: 4, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let authenticated = false; let activityId;
    const names = ['查询账号身份', '发现签到活动', '每日签到', '查询当前积分'];
    for (let i = 0; i < names.length; i++) {
        const stepStart = Date.now();
        log(`账号 ${index} · 阶段 ${i + 1}/4 ${names[i]} 开始`);
        try {
            if (i === 0 && /[\s&@\x00-\x1f\x7f-\uffff]/.test(token)) throw new Error('账号 token 格式错误，每行只允许一个请求头 token');
            if (dry) {
                stats.skipped++;
                log(`⏭️ 断网预演：已检查${names[i]}请求计划，不发送请求`);
            } else if ((i > 0 && !authenticated) || (i === 2 && !activityId)) {
                stats.skipped++;
                log('⏭️ 前置阶段未通过，跳过依赖操作');
            } else {
                if (i === 0) {
                    const r = await request(token, `/mobile/customer/initMy?shopId=${SHOP}`);
                    if (!r || !r.customer || typeof r.customer !== 'object') throw new Error('缺少账号信息');
                    identity(r.customer); authenticated = true;
                    log('✅ 账号信息验证成功');
                } else if (i === 1) {
                    const r = await request(token, `/mobile/customer/queryMobilePersonCenterTemplateByShopId?shopId=${SHOP}`);
                    const component = r && Array.isArray(r.views) && r.views.find(x => x && x.componentId === 'WHXG8614883');
                    const imgs = component && component.defaultConfig && component.defaultConfig.img;
                    const img = Array.isArray(imgs) && imgs.find(x => x && x.link && x.link.path === '/pages/ehd/activities/signIn/index');
                    const id = img && img.link.id;
                    if (!((typeof id === 'string' && id.trim()) || (typeof id === 'number' && Number.isFinite(id) && id > 0))) throw new Error('未找到有效签到活动');
                    activityId = id; log('✅ 已发现本账号签到活动');
                } else if (i === 2) {
                    const r = await request(token, '/mobile/activity/sign/sign', { shopId: SHOP, activityId, signDate: signDate() });
                    if (!r || !number(r.integral)) throw new Error('签到结果缺少有效积分，无法验证完整结果');
                    log(`✅ 签到成功，积分+${r.integral}`);
                } else {
                    const r = await request(token, `/mobile/customer/getMyAllPoint?shopId=${SHOP}`);
                    if (!Array.isArray(r) || !r[0] || !number(r[0].score)) throw new Error('积分结果格式异常');
                    log(`✅ 当前积分：${r[0].score}`);
                }
                stats.success++;
            }
        } catch (e) {
            stats.failed++;
            // 仅上述自定义固定错误可进入日志，不打印库错误、请求参数或服务端消息。
            log(`❌ ${names[i]}失败：${e.message}`);
        }
        log(`账号 ${index} · 阶段 ${i + 1}/4 耗时 ${Date.now() - stepStart} 毫秒`);
    }
    const ok = stats.failed === 0 && (dry || stats.success === 4);
    for (const key of Object.keys(totals)) totals[key] += stats[key];
    results.push({ index, status: !ok ? 'failure' : dry ? 'dry-run' : 'success', ...stats, durationMs: Date.now() - begin });
    log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${Date.now() - begin} 毫秒`);
}
async function notify(body) {
    if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
    if (dry) { log(`通知预演摘要：${body}`); return '断网预演已生成，未投递'; }
    const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
    const file = dirs.map(d => path.resolve(d, 'sendNotify.js')).find(f => fs.existsSync(f));
    if (!file) return '通知模块不可用，保留业务退出码';
    return new Promise(resolve => {
        // 在独立进程中投递并限制时间，避免通知模块泄漏日志或覆盖业务退出码。
        const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', file, TITLE, body], { stdio: 'ignore' });
        const timer = setTimeout(() => { child.kill('SIGKILL'); }, 15000);
        child.on('error', () => { clearTimeout(timer); resolve('通知投递失败，保留业务退出码'); });
        child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '通知投递失败，保留业务退出码'); });
    });
}
async function main() {
    log(`========== ${TITLE} ==========`);
    log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${tokens.length}`);
    if (!tokens.length) {
        configError = true; log('❌ 配置错误：TEBU_TOKEN 必须为每行一个有效请求头 token，不支持其他账号分隔符');
    } else {
        for (let i = 0; i < tokens.length; i++) await account(tokens[i], i + 1);
    }
    const failed = configError ? tokens.length : results.filter(x => x.status === 'failure').length;
    const success = results.filter(x => x.status === 'success').length;
    const status = configError ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
    const exitCode = configError || failed ? 1 : 0;
    const body = `状态：${status}；账号总数：${tokens.length}，成功：${success}，失败：${failed}，预演：${results.filter(x => x.status === 'dry-run').length}；配置错误：${configError ? '是' : '否'}；子任务成功：${totals.success}，失败：${totals.failed}，跳过：${totals.skipped}`;
    let notification;
    try { notification = await notify(body); } catch { notification = '通知失败，保留业务退出码'; }
    log('----------------------------------------');
    log(body);
    log(`子任务总数：${totals.total}；已完成：${totals.alreadyComplete}；总耗时：${Date.now() - started} 毫秒`);
    log(`通知状态：${notification}；完成时间：${new Date().toISOString()}；最终状态：${status}`);
    console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, status, mode: dry ? 'dry-run' : 'live', accountCount: tokens.length, success, failed, configError, tasks: totals, accounts: results, notification, durationMs: Date.now() - started, exitCode }));
    process.exitCode = exitCode;
}
main().catch(() => { console.error('任务发生未预期内部错误'); process.exitCode = 1; });
