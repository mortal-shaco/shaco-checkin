// name: YBT签到
// cron: 55 1 * * *
/**
 * name: YBT签到
 * cron: 1 0 * * *
 * YBT 签到脚本 for 青龙面板 (缓存版)
 * 原作者: CodeBuddy；上游更新时间: 2025-01-23
 * 来源: fuguang88/qinglong-scripts / ybt_sign.js
 * 许可: MIT
 *
 * YBT_USERS（必填）：在 YBT 注册/个人资料中查看用户名；不是邮箱、Cookie 或 Token。
 * 每个非空行一个账号，原样提交用户名，不使用 & 或 @ 分隔账号。
 * YBT_DRY_RUN=1：完全离线预演，不请求接口、不读写缓存、不调用通知模块。
 * YBT_CACHE_FILE：可选缓存路径，默认脚本目录的 ybt_sign_cache.json。
 * QINGLONG_NOTIFY：auto（默认启用本脚本）、1/true/yes/on、0/false/no/off。
 * QINGLONG_NOTIFY_SCRIPTS：设置后覆盖默认名单，逗号/分号/空白分隔，支持文件名通配符、路径、目录编号。
 * QINGLONG_NOTIFY_DIR：可选，指向青龙 sendNotify.js 所在目录。
 * Node.js >= 16，无第三方业务依赖；只进行签到及本地流量缓存，无发布/消费动作。
 *
 * MIT License
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  const raw = process.env.QINGLONG_NOTIFY;
  if (raw !== undefined && String(raw).trim() !== '' && String(raw).trim().toLowerCase() !== 'auto') return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["3460aa0a0b9700db", "scripts/ybt_sign.js", "ybt_sign.js", "ybt_sign"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFile } = require('child_process');
const TITLE = 'YBT签到';
const CATALOG = '3460aa0a0b9700db';
const API = 'https://api-v2.ybt.one/api/user/sign';
const USER_AGENT = 'Mozilla/5.0 (ScriptCat Smart) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const stamp = () => new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
const log = message => console.log(`[${stamp()}] ${message}`);
const today = () => new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit'
}).format(new Date());
const finite = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
const cacheKey = username => crypto.createHash('sha256').update(username).digest('hex');
const affirmative = value => ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase());

// 绝不将响应正文、服务器 message 或异常堆栈写入日志。
function requestSign(username) {
    return new Promise((resolve, reject) => {
        let timer;
        let settled = false;
        const finish = (error, result) => {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            if (error) reject(error); else resolve(result);
        };
        const body = new URLSearchParams({ username }).toString();
        const req = https.request(API, {
            method: 'POST', headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                Accept: 'application/json, text/plain, */*',
                'User-Agent': USER_AGENT,
                'Content-Length': Buffer.byteLength(body)
            }
        }, res => {
            const chunks = [];
            let bytes = 0;
            res.on('error', () => finish(new Error('响应读取失败')));
            res.on('aborted', () => finish(new Error('响应中断')));
            res.on('data', chunk => {
                bytes += chunk.length;
                if (bytes > 65536) {
                    finish(new Error('响应超过大小限制'));
                    res.destroy();
                    req.destroy();
                } else chunks.push(chunk);
            });
            res.on('end', () => {
                if (settled) return;
                if (![200, 400].includes(res.statusCode)) {
                    finish(new Error(`HTTP ${res.statusCode}`));
                    return;
                }
                try {
                    const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
                    finish(null, { status: res.statusCode, data });
                } catch (_) { finish(new Error('响应不是有效JSON')); }
            });
        });
        timer = setTimeout(() => {
            const error = new Error('请求超时');
            error.retryable = true;
            finish(error);
            req.destroy();
        }, 12000);
        req.on('error', error => {
            const safe = new Error('网络请求失败');
            safe.retryable = ['ECONNRESET', 'ETIMEDOUT', 'ENOTFOUND'].includes(error.code);
            finish(safe);
        });
        req.end(body);
    });
}

async function performSign(username) {
    for (let attempt = 0; ; attempt++) {
        try { return await requestSign(username); }
        catch (error) {
            if (!error.retryable || attempt >= 3) throw error;
            log(`⚠️ 签到请求暂时失败，2秒后第${attempt + 1}次重试`);
            await sleep(2000);
        }
    }
}

function readCache(filename) {
    try {
        if (!fs.existsSync(filename)) return {};
        if (fs.statSync(filename).size > 1048576) throw new Error();
        const value = JSON.parse(fs.readFileSync(filename, 'utf8'));
        if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error();
        const cache = Object.create(null);
        for (const [key, item] of Object.entries(value)) {
            if (!item || item.date !== today()) continue;
            // 兼容旧缓存用户名键，但后续写入仅使用摘要键及白名单数值。
            cache[/^[a-f0-9]{64}$/.test(key) ? key : cacheKey(key)] = {
                date: item.date, sign_count: finite(item.sign_count) ? item.sign_count : 0,
                get_traffic: finite(item.get_traffic) ? item.get_traffic : undefined,
                total_traffic: finite(item.total_traffic) ? item.total_traffic : undefined
            };
        }
        return cache;
    } catch (_) { log('⚠️ 当日缓存不可用，将以接口结果为准'); return {}; }
}

function writeCache(filename, cache) {
    const temporary = `${filename}.${process.pid}.tmp`;
    try {
        fs.writeFileSync(temporary, JSON.stringify(cache, null, 2), { mode: 0o600, flag: 'wx' });
        fs.renameSync(temporary, filename);
        return true;
    } catch (_) {
        log('⚠️ 流量缓存保存失败，本次签到结果仍有效');
        return false;
    } finally {
        try { fs.unlinkSync(temporary); } catch (_) { /* 不输出本地路径 */ }
    }
}

function identity(data) {
    for (const field of ['nickname', 'username', 'display_name', 'displayName', 'public_uid', 'uid']) {
        const value = data && data[field];
        if (typeof value !== 'string' && typeof value !== 'number') continue;
        const text = String(value);
        // 身份按官方原值显示；手机号、控制字符及会话格式不输出。
        if (!text || text.length > 120 || /[\r\n\x00-\x1f\x7f]|(?:\+?86[- ]?)?1[3-9]\d{9}|(?:token|cookie|session|bearer)[=: ]/i.test(text)) continue;
        return text;
    }
    return null;
}

function processResult(result, username, cache) {
    const data = result.data && result.data.data;
    if (!data || typeof data !== 'object' || data.sign_status !== true) {
        return { success: false, message: result.data && result.data.message === '用户不存在' ? '用户不存在，请检查用户名' : '接口未确认签到成功', dataSource: 'error' };
    }
    const first = result.status === 200 && finite(data.get_traffic) && finite(data.total_traffic);
    const cached = cache[cacheKey(username)];
    const details = first ? data : (cached || data);
    return {
        success: true, isFirstSign: first, identity: identity(data) || identity(result.data),
        message: first ? '签到成功' : '今日已签到',
        dataSource: first ? 'api' : (cached ? 'cache' : 'api_limited'),
        sign_count: finite(details.sign_count) ? details.sign_count : 0,
        get_traffic: finite(details.get_traffic) ? details.get_traffic : undefined,
        total_traffic: finite(details.total_traffic) ? details.total_traffic : undefined
    };
}

function notificationEnabled() {
    const flag = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
    if (['0', 'false', 'no', 'off'].includes(flag)) return false;
    if (affirmative(flag)) return true;
    const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
    if (selection === undefined) return true; // 上游已通知的脚本保留默认通知
    const names = [CATALOG, 'ybt_sign.js', 'candidate.js', __filename, path.basename(__filename)];
    return selection.split(/[,;\s]+/).filter(Boolean).some(pattern => {
        const regex = new RegExp('^' + pattern.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
        return names.some(name => regex.test(name) || name.endsWith('/' + pattern));
    });
}

async function notify(summary, results, dry) {
    if (!notificationEnabled()) return '已关闭';
    const body = `账号总数：${summary.accounts}，成功：${summary.success}，失败：${summary.failed}\n状态：${summary.status}\n` +
        results.map((r, i) => `账号${i + 1}${r.identity ? '（' + r.identity + '）' : ''}：${r.message}` +
            (r.success && !r.skipped ? `；累计签到${r.sign_count}天；获得流量${r.get_traffic === undefined ? '需首次签到获取' : r.get_traffic + ' MB'}；总流量${r.total_traffic === undefined ? '需首次签到获取' : r.total_traffic + ' MB'}；数据来源${r.dataSource}` : '')).join('\n');
    if (dry) { log(`⏭️ 离线通知预演：${body.replace(/\n/g, ' | ')}；不调用通知模块`); return '预演'; }
    const dirs = [process.env.QINGLONG_NOTIFY_DIR, __dirname, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
    for (const directory of [...new Set(dirs)]) {
        const filename = path.join(directory, 'sendNotify.js');
        if (!fs.existsSync(filename)) continue;
        // 子进程隔离通知模块的输出/超时，避免泄漏模块调试信息及改变业务退出码。
        const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))';
        const ok = await new Promise(resolve => execFile(process.execPath, ['-e', code, filename, TITLE, body],
            { timeout: 15000, maxBuffer: 65536 }, error => resolve(!error)));
        if (ok) return '已发送';
    }
    log('⚠️ 通知模块不可用或发送失败，保留业务退出码');
    return '不可用或失败';
}

async function main() {
    const started = Date.now();
    const dry = affirmative(process.env.YBT_DRY_RUN);
    const users = (process.env.YBT_USERS || '').split(/\r?\n/).map(user => user.trim()).filter(Boolean);
    const results = [];
    log(`========== ${TITLE} ==========`);
    log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '离线预演' : '正式签到'}；账号数：${users.length}`);
    log('阶段1 配置检查');
    if (!users.length) log('❌ 配置错误：请设置 YBT_USERS，每个非空行一个用户名');
    const filename = process.env.YBT_CACHE_FILE || path.join(__dirname, 'ybt_sign_cache.json');
    const cache = !dry && users.length ? readCache(filename) : {};
    log(`阶段1结束：配置${users.length ? '有效' : '缺失'}；耗时${Date.now() - started}毫秒`);
    for (let index = 0; index < users.length; index++) {
        const accountStarted = Date.now();
        log(`账号${index + 1} / 阶段2 ${dry ? '预演签到' : '请求签到'}`);
        let result;
        try {
            if (dry) {
                result = { success: true, skipped: true, message: '离线预演通过', dataSource: 'dry-run' };
                log('⏭️ 将使用POST表单提交用户名；跳过网络、重试等待及缓存写入');
            } else {
                result = processResult(await performSign(users[index]), users[index], cache);
                if (result.isFirstSign) {
                    cache[cacheKey(users[index])] = { date: today(), sign_count: result.sign_count,
                        get_traffic: result.get_traffic, total_traffic: result.total_traffic };
                    writeCache(filename, cache);
                }
            }
        } catch (_) { result = { success: false, message: '签到失败：网络异常、超时或响应无效', dataSource: 'error' }; }
        results.push(result);
        if (result.identity) log(`官方账号身份：${result.identity}`);
        log(`${result.success ? (result.skipped ? '⏭️' : '✅') : '❌'} ${result.message}；数据来源：${result.dataSource}`);
        if (!dry && result.success) {
            log(`累计签到：${result.sign_count}天；获得流量：${result.get_traffic === undefined ? '需首次签到获取' : result.get_traffic + ' MB'}；总流量：${result.total_traffic === undefined ? '需首次签到获取' : result.total_traffic + ' MB'}`);
        }
        log(`账号${index + 1}统计：总任务1，成功${result.success && !result.skipped && result.isFirstSign ? 1 : 0}，已完成${result.success && !result.skipped && !result.isFirstSign ? 1 : 0}，跳过${result.skipped ? 1 : 0}，失败${result.success ? 0 : 1}；阶段2耗时${Date.now() - accountStarted}毫秒`);
        if (!dry && index < users.length - 1) await sleep(1000);
    }
    const failed = results.filter(result => !result.success).length;
    const exitCode = users.length ? (failed ? 1 : 0) : 1;
    const summary = { task: TITLE, mode: dry ? 'dry-run' : 'live', accounts: users.length,
        success: results.length - failed, failed, tasks: results.length,
        firstSign: results.filter(r => r.isFirstSign).length,
        alreadyComplete: results.filter(r => r.success && !r.skipped && !r.isFirstSign).length,
        cached: results.filter(r => r.dataSource === 'cache').length,
        skipped: results.filter(r => r.skipped).length,
        status: !users.length ? 'configuration-error' : failed ? (failed === users.length ? 'failure' : 'partial-failure') : dry ? 'dry-run' : 'success', exitCode };
    const notifyStarted = Date.now();
    log('阶段3 汇总与通知');
    try { summary.notification = await notify(summary, results, dry); }
    catch (_) { summary.notification = '不可用或失败'; log('⚠️ 通知失败，保留业务退出码'); }
    log(`阶段3结束：通知${summary.notification}；耗时${Date.now() - notifyStarted}毫秒`);
    summary.durationMs = Date.now() - started;
    summary.finishedAt = new Date().toISOString();
    log('----------------------------------------');
    log(`账号结果：总数${summary.accounts}，成功${summary.success}，失败${summary.failed}`);
    log(`子任务结果：总数${summary.tasks}，成功${summary.firstSign}，已完成${summary.alreadyComplete}，跳过${summary.skipped}，失败${summary.failed}；缓存${summary.cached}`);
    log(`总耗时：${summary.durationMs}毫秒；完成时间：${summary.finishedAt}；通知：${summary.notification}；最终状态：${summary.status}`);
    console.log('TASK_SUMMARY=' + JSON.stringify(summary));
    process.exitCode = exitCode;
    return summary;
}
if (require.main === module) main().catch(() => { process.exitCode = 1; });
module.exports = { main };
