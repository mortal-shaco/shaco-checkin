// name: 百度贴吧成长任务签到
// cron: 19 7 * * *
/**
 * name: 百度贴吧成长任务签到
 * cron: 19 7 * * *
 * 百度贴吧APP - 我的 - 成长任务 - 每日签到
 * 就成长值，没什么用
 * 原作者：@author Telegram@sudojia
 * @site https://blog.imzjw.cn
 * @date 2024/09/07
 * 来源：sudojia/AutoTaskScript src/client/sudojia_tieba_taskSign.js
 * 许可证：GPL-3.0（沿用上游及任务指定的有效许可证）
 *
 * Node.js 18 及以上，无第三方业务依赖。
 * TIE_BA_COOKIE：在自己的贴吧APP登录后，用本机抓包工具查看
 * https://tieba.baidu.com 请求的 Cookie，复制含 BDUSS 和 CUID 的完整值。
 * 凭据必须来自同一账号；不要公开、不要发送给他人。
 * 每个非空行一个账号，Cookie 内字段用分号分隔，字段只在第一个等号处分割。
 * 不使用 & 或 @ 分隔账号。保留原变量名，不接受缺少 CUID 的单独 BDUSS。
 * TIEBA_GROWTH_DRY_RUN=1：完全离线配置预演，不签到、不加载通知组件。
 * QINGLONG_NOTIFY=0/false/no/off：关闭通知，默认开启。
 * QINGLONG_NOTIFY_DIR：可选，青龙 sendNotify.js 所在目录。
 * 本任务只执行成长签到；关注贴吧签到由现有独立维护任务提供。
 */
'use strict';

const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const TITLE = '百度贴吧成长任务签到';
const BASE = 'https://tieba.baidu.com';
const INFO_PATH = '/mo/q/usergrowth/showUserGrowth?client_type=2&client_version=12.60.1.2';
const TIMEOUT_MS = 15000;
const MAX_BYTES = 1024 * 1024;
const start = Date.now();
const dryRun = /^(1|true|yes|on)$/i.test(process.env.TIEBA_GROWTH_DRY_RUN || '');
const lines = (process.env.TIE_BA_COOKIE || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const secrets = [];
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const accounts = [];

function timestamp() { return new Date().toLocaleTimeString('zh-CN', { hour12: false }); }
function log(s) { console.log(`[${timestamp()}] ${s}`); }
function fail(code) { const err = new Error(code); err.safeCode = code; return err; }
function safeError(e) { return e && e.safeCode ? e.safeCode : '执行异常（已隐藏底层信息）'; }
function cleanIdentity(value) {
    if (!['string', 'number'].includes(typeof value)) return '';
    let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ').trim();
    for (const secret of secrets) if (secret) s = s.split(secret).join('[凭据已隐藏]');
    return s.replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, '[手机号已隐藏]');
}

function parseCookie(line) {
    if (/[\x00-\x1f\x7f]/.test(line)) throw fail('Cookie 含无效控制字符');
    const entries = new Map();
    for (const field of line.split(';')) {
        if (!field.trim()) continue;
        const delimiter = field.indexOf('=');
        if (delimiter < 1) throw fail('Cookie 格式错误：需使用字段名=字段值');
        const name = field.slice(0, delimiter).trim();
        const value = field.slice(delimiter + 1).trim();
        if (!/^[A-Za-z0-9_-]+$/.test(name) || !value) throw fail('Cookie 字段格式错误');
        if (entries.has(name)) throw fail('Cookie 字段重复，请每行只配置一个账号');
        entries.set(name, value);
        secrets.push(value);
    }
    if (!entries.get('BDUSS') || !entries.get('CUID')) throw fail('需配置同一账号的 BDUSS 和 CUID');
    return { cookie: [...entries].map(([k, v]) => `${k}=${v}`).join('; '), cuid: entries.get('CUID') };
}

// 不跟随重定向，Cookie 仅送往固定的贴吧 HTTPS 主机；不打印请求/原始响应。
function request(endpoint, credential, body) {
    if (dryRun) return Promise.reject(fail('离线模式禁止业务网络请求'));
    return new Promise((resolve, reject) => {
        let settled = false;
        let timer;
        const finish = (err, value) => {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            err ? reject(err) : resolve(value);
        };
        const headers = {
            Accept: 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36',
            Cookie: credential.cookie
        };
        if (body !== undefined) {
            headers['Content-Type'] = 'application/x-www-form-urlencoded';
            headers['Content-Length'] = Buffer.byteLength(body);
        }
        const req = https.request(BASE + endpoint, { method: body === undefined ? 'GET' : 'POST', headers }, res => {
            if (res.statusCode !== 200) {
                finish(fail(`HTTP 请求失败（状态 ${res.statusCode}）`));
                res.destroy();
                return;
            }
            const chunks = [];
            let size = 0;
            res.on('data', chunk => {
                size += chunk.length;
                if (size > MAX_BYTES) {
                    finish(fail('响应超过大小限制'));
                    res.destroy(); req.destroy();
                } else chunks.push(chunk);
            });
            res.on('error', () => finish(fail('响应读取失败')));
            res.on('aborted', () => finish(fail('响应传输中断')));
            res.on('end', () => {
                if (settled) return;
                try { finish(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
                catch (_) { finish(fail('响应不是有效 JSON')); }
            });
        });
        timer = setTimeout(() => {
            finish(fail('请求超时')); req.destroy();
        }, TIMEOUT_MS);
        req.on('error', () => finish(fail('网络请求失败')));
        req.end(body);
    });
}

function businessResult(response) {
    if (!response || typeof response !== 'object' || ![0, '0'].includes(response.no)) {
        throw fail('业务接口未确认成功，请检查登录状态或接口契约');
    }
    return response.data;
}
function numeric(value, label) {
    if (!['string', 'number'].includes(typeof value) || !/^\d+(?:\.\d+)?$/.test(String(value)) || !Number.isFinite(Number(value))) {
        throw fail(`${label}字段缺失或格式变化`);
    }
    return Number(value);
}

async function stage(account, number, label, action) {
    const began = Date.now();
    account.tasks.total++;
    log(`账号[${account.index}] 阶段 ${number}/3：${label}`);
    try {
        await action();
        account.tasks.success++;
        log(`✅ 账号[${account.index}] ${label}完成，耗时 ${Date.now() - began} 毫秒`);
    } catch (e) {
        account.tasks.failed++;
        log(`❌ 账号[${account.index}] ${label}失败：${safeError(e)}，耗时 ${Date.now() - began} 毫秒`);
        throw e;
    }
}

async function runAccount(line, index) {
    const began = Date.now();
    const account = { index, status: 'failure', tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 } };
    accounts.push(account);
    log(`----- 账号[${index}] -----`);
    let credential;
    try {
        credential = parseCookie(line);
    } catch (e) {
        account.status = 'configuration-error';
        account.tasks.total = 3; account.tasks.failed = 1; account.tasks.skipped = 2;
        log(`❌ 账号[${index}] 阶段 1/3：配置检查失败：${safeError(e)}，耗时 ${Date.now() - began} 毫秒`);
        for (let n = 2; n <= 3; n++) log(`⏭️ 账号[${index}] 阶段 ${n}/3：配置错误，跳过，耗时 0 毫秒`);
    }
    if (credential) {
        if (dryRun) {
            account.status = 'dry-run';
            account.tasks.total = 3; account.tasks.skipped = 3;
            log(`✅ 账号[${index}] BDUSS 与 CUID 格式检查通过（未验证登录或签到）`);
            ['登录状态与昵称查询', '成长任务签到', '成长值、贴贝余额及等级查询'].forEach((name, i) => {
                log(`⏭️ 账号[${index}] 阶段 ${i + 1}/3：${name}，离线预演跳过，耗时 0 毫秒`);
            });
        } else {
            try {
                let tbs;
                await stage(account, 1, '登录状态与昵称查询', async () => {
                    const data = businessResult(await request(INFO_PATH, credential));
                    if (!data || !data.user || typeof data.tbs !== 'string' || !data.tbs.trim()) throw fail('登录响应缺少用户信息或 TBS');
                    tbs = data.tbs;
                    secrets.push(tbs);
                    const identity = data.user.uname ?? data.user.nickname ?? data.user.username ?? data.user.uid;
                    const display = cleanIdentity(identity);
                    if (display) log(`账号[${index}] 昵称／公开身份：${display}`);
                    else log(`账号[${index}] 接口未提供可显示的账号身份`);
                });
                await new Promise(resolve => setTimeout(resolve, 1000));
                await stage(account, 2, '成长任务签到', async () => {
                    const body = new URLSearchParams({
                        tbs, act_type: 'page_sign', cuid: credential.cuid, client_type: '2',
                        brand: 'OPPO', model: 'OPPO R9s', zid: '', clientVersion: '12.60.1.2', clientType: '2'
                    }).toString();
                    businessResult(await request('/mo/q/usergrowth/commitUGTaskInfo', credential, body));
                    log(`账号[${index}] 成长签到成功（业务码为 0）`);
                });
                await new Promise(resolve => setTimeout(resolve, 1000));
                await stage(account, 3, '成长值、贴贝余额及等级查询', async () => {
                    const data = businessResult(await request(INFO_PATH, credential));
                    const current = data && Array.isArray(data.level_info) && data.level_info.find(item => item && [1, '1'].includes(item.is_current));
                    if (!current) throw fail('当前等级字段缺失或格式变化');
                    const value = numeric(data.growth_info && data.growth_info.value, '成长值');
                    const money = numeric(data.tmoney && data.tmoney.current, '贴贝余额');
                    const level = numeric(current.level, '当前等级');
                    const remaining = numeric(current.next_level_value, '下一等级') - numeric(current.growth_value, '等级成长值');
                    log(`账号[${index}] 当前成长值：${value}；当前贴贝余额：${money}；当前等级：Lv.${level}；距离下一等级还需 ${remaining} 成长值`);
                });
                account.status = 'success';
            } catch (_) {
                const pending = 3 - account.tasks.total;
                for (let n = account.tasks.total + 1; n <= 3; n++) log(`⏭️ 账号[${index}] 阶段 ${n}/3：前置阶段失败，跳过，耗时 0 毫秒`);
                account.tasks.total += pending; account.tasks.skipped += pending;
            }
        }
    }
    account.elapsedMs = Date.now() - began;
    for (const key of Object.keys(totals)) totals[key] += account.tasks[key];
    log(`账号[${index}] 统计：总任务 ${account.tasks.total}，成功 ${account.tasks.success}，已完成 ${account.tasks.alreadyComplete}，跳过 ${account.tasks.skipped}，失败 ${account.tasks.failed}，耗时 ${account.elapsedMs} 毫秒，状态 ${account.status}`);
}

async function notify(summary) {
    if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return 'disabled';
    // 断网预演优先：通知组件可能自行联网，因此仅展示本地通知摘要。
    if (dryRun) { log(`通知离线预演：${summary}`); return 'dry-run-local'; }
    const files = [
        process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
        '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'
    ].filter(Boolean);
    const file = files.find(f => fs.existsSync(f));
    if (!file) { log('⚠️ 青龙通知组件不可用，保留业务退出码'); return 'unavailable'; }
    try {
        const module = require(file);
        if (typeof module.sendNotify !== 'function') throw new Error('invalid notify');
        let timer;
        try {
            await Promise.race([
                Promise.resolve().then(() => module.sendNotify(TITLE, summary)),
                new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('timeout')), TIMEOUT_MS); })
            ]);
        } finally { clearTimeout(timer); }
        return 'sent';
    } catch (_) { log('⚠️ 通知发送失败或超时，保留业务退出码'); return 'failed'; }
}

async function main() {
    log(`========== ${TITLE} ==========`);
    log(`开始时间：${new Date(start).toISOString()}；运行模式：${dryRun ? '完全离线预演' : '正式执行'}；账号数：${lines.length}`);
    if (!lines.length) log('❌ 配置错误：请设置 TIE_BA_COOKIE，每行一个含 BDUSS 和 CUID 的账号 Cookie');
    for (let i = 0; i < lines.length; i++) {
        await runAccount(lines[i], i + 1);
        if (!dryRun && i + 1 < lines.length) await new Promise(resolve => setTimeout(resolve, 2000));
    }
    const succeeded = accounts.filter(a => ['success', 'dry-run'].includes(a.status)).length;
    const failed = lines.length - succeeded;
    const status = !lines.length || accounts.every(a => a.status === 'configuration-error') ? 'configuration-error'
        : failed ? (succeeded ? 'partial-failure' : 'failure') : (dryRun ? 'dry-run' : 'success');
    const exitCode = !lines.length || failed ? 1 : 0;
    const body = `账号总数 ${lines.length}，${dryRun ? '预演通过' : '成功'} ${succeeded}，失败 ${failed}；状态 ${status}；子任务成功 ${totals.success}，跳过 ${totals.skipped}，失败 ${totals.failed}${!lines.length ? '；缺少账号配置' : ''}`;
    const notification = await notify(body);
    log('----------------------------------------');
    log(`任务统计：${body}；已完成 ${totals.alreadyComplete}；总任务 ${totals.total}`);
    const finishedAt = new Date().toISOString();
    log(`完成时间：${finishedAt}；总耗时 ${Date.now() - start} 毫秒；通知状态 ${notification}；最终状态 ${status}`);
    console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, mode: dryRun ? 'dry-run' : 'live', status, accountCount: lines.length, success: succeeded, failed, tasks: totals, accounts, notification, startedAt: new Date(start).toISOString(), finishedAt, elapsedMs: Date.now() - start, exitCode }));
    return exitCode;
}

main().then(code => { process.exitCode = code; }).catch(() => {
    // 所有业务错误在账号内处理；此分支只报告意外运行错误，不暴露原始异常。
    log('❌ 任务执行异常（已隐藏底层信息）');
    process.exitCode = 1;
});
