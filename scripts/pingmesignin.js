// name: PingMe签到与可选视频奖励
// cron: 0 16 * * *
// SPDX-License-Identifier: MIT
// 来源仓库 jiu-you/qinglongScripts，原文件 PingMeSignin.js
// 来源提交 a26784dba70a1d9f401453971c5251ce354b5691
/*
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
/*
@Name：PingMe 自动化签到+视频奖励
@Author：怎么肥事 https://raw.githubusercontent.com/ZenmoFeiShi/Qx/refs/heads/main/PingMe.js
@modify 奶思做了修改，理论支持 Qx,Loon,Surge,Egern,ShadowRocket,青龙
@date 2026-04-17 14:00:00

============QuanX============
[rewrite_local]
^https:\/\/api\.pingmeapp\.net\/app\/queryBalanceAndBonus url script-request-header https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cookie/get_cookie.js

[task_local]
30 8,20 * * * https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/PingMe/PingMeSignin.js, img-url=https://raw.githubusercontent.com/fmz200/wool_scripts/main/icons/apps/PingMe.png, tag=PingMe签到, enabled=true

[MITM]
hostname = api.pingmeapp.net

============其他工具自行转换============
*/

/*
维护版功能清单
- 保留余额查询、签到、原始参数 UTC 签名、视频奖励及合并通知。
- 青龙计划保持每天 16 点。上游代理工具另有 8:30、20:30 示例，由使用者自行配置。
- pingme_capture_v3 为必填，每个非空行保存一个账号的完整 JSON。
  在本人已登录的 PingMe 中，通过可信本地抓包工具捕获
  https://api.pingmeapp.net/app/queryBalanceAndBonus 的请求头与查询参数。
  将请求头保存到 headers 对象，将原始查询字符串按 & 分项、仅在首个 = 分割，
  不做 URL 解码，保存到 paramsRaw 对象。保留全部账号认证字段，不公开抓参内容。
  兼容原单账号格式化 JSON。sign/signDate 每次重建，其他字段保持原值。
- PINGME_SECRET 可覆盖上游应用签名常量。不是用于分隔账号的字段。
- PINGME_VIDEO_ENABLED=1 显式允许视频奖励，默认关闭自动申领奖励，开启后保留 5 次、
  首次等待 1.5 秒、后续等待 8 秒。仅在符合服务规则且允许该动作时开启。
- PINGME_DRY_RUN=1 完全离线，仅验证配置、签名组装和任务计划，通知为本地预览。
- QINGLONG_NOTIFY=auto 默认仅通知 QINGLONG_NOTIFY_SCRIPTS 选中的脚本。
  1/true/yes/on 强制开启，0/false/no/off 关闭。列表支持逗号、分号、空白及通配符。
- Node.js >=18，无第三方业务依赖。不会改写环境、抓参文件或账户资料。
许可证采用来源任务声明的 MIT，原署名与说明保留于上方。
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
    const identities = ["6807cb14d5312bb8", "scripts/pingmesignin.js", "pingmesignin.js", "pingmesignin"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const { validateHeaderName, validateHeaderValue } = require('node:http');
const path = require('node:path');
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
const TITLE = 'PingMe签到';
const CATALOG_ID = '6807cb14d5312bb8';
const SECRET = process.env.PINGME_SECRET || ['0fOiukQq7jXZV2GR', 'i9LGlO'].join('');
const enabled = value => /^(1|true|yes|on)$/i.test(value || '');
const dryRun = enabled(process.env.PINGME_DRY_RUN);
const videoEnabled = enabled(process.env.PINGME_VIDEO_ENABLED);
const started = Date.now();
const records = [];
const log = message => console.log(`[${new Date().toTimeString().slice(0, 8)}] ${message}`);
const elapsed = start => Number(((Date.now() - start) / 1000).toFixed(3));

function parseCapture(line) {
    let capture;
    try { capture = JSON.parse(line); } catch { throw new Error('账号 JSON 格式错误，请重新核对抓参'); }
    if (!capture || typeof capture !== 'object' || Array.isArray(capture)) {
        throw new Error('账号必须为包含 headers 和 paramsRaw 的 JSON 对象');
    }
    for (const key of ['headers', 'paramsRaw']) {
        const value = capture[key];
        if (!value || typeof value !== 'object' || Array.isArray(value) || !Object.keys(value).length) {
            throw new Error(`账号缺少非空 ${key} 对象，请完整获取原始请求`);
        }
        for (const [name, field] of Object.entries(value)) {
            if (!name || !['string', 'number'].includes(typeof field) || /[\r\n]/.test(String(field)) ||
                (key === 'paramsRaw' && !/^[A-Za-z0-9_.-]+$/.test(name))) {
                throw new Error(`账号 ${key} 字段格式错误`);
            }
        }
    }
    if (!Object.keys(capture.paramsRaw).some(key => !['sign', 'signDate'].includes(key))) {
        throw new Error('paramsRaw 缺少原始账号参数');
    }
    return capture;
}

function accountLines(raw) {
    if (!raw || !raw.trim()) return [];
    // 保留原单账号格式化 JSON 的兼容性，多账号仍仅按非空行划分。
    try {
        const single = JSON.parse(raw);
        if (single && typeof single === 'object' && !Array.isArray(single)) return [raw];
    } catch { /* 多行账号逐个解析，损坏账号不会阻止其他账号。 */ }
    return raw.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
}

function buildHeaders(capture) {
    const headers = {};
    const excluded = new Set(['host', 'content-length', 'connection', 'transfer-encoding', 'accept-encoding']);
    for (const [name, value] of Object.entries(capture.headers)) {
        if (!name.startsWith(':') && !excluded.has(name.toLowerCase())) headers[name.toLowerCase()] = String(value);
    }
    headers.host = 'api.pingmeapp.net';
    headers.accept = headers.accept || 'application/json';
    try {
        for (const [name, value] of Object.entries(headers)) {
            validateHeaderName(name);
            validateHeaderValue(name, value);
        }
    } catch { throw new Error('请求头格式错误，请重新抓参'); }
    return headers;
}

function buildUrl(action, capture) {
    const params = Object.create(null);
    for (const [key, value] of Object.entries(capture.paramsRaw)) {
        if (!['sign', 'signDate'].includes(key)) params[key] = String(value);
    }
    params.signDate = new Date().toISOString().slice(0, 19).replace('T', ' ');
    const base = Object.keys(params).sort().map(key => `${key}=${params[key]}`).join('&');
    params.sign = MD5(base + SECRET);
    // 沿用上游对 paramsRaw 值再次编码的签名与传输契约。
    const query = Object.keys(params).map(key => `${key}=${encodeURIComponent(params[key])}`).join('&');
    return `https://api.pingmeapp.net/app/${action}?${query}`;
}

function request(action, capture) {
    if (dryRun) throw new Error('离线模式禁止网络请求');
    return new Promise((resolve, reject) => {
        let settled = false;
        let req;
        const finish = (error, value) => {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            error ? reject(error) : resolve(value);
        };
        const timer = setTimeout(() => {
            finish(new Error('请求超过 15 秒，未重试以避免重复领奖'));
            if (req) req.destroy();
        }, 15000);
        try {
            req = https.get(buildUrl(action, capture), { headers: buildHeaders(capture) }, response => {
                if (response.statusCode !== 200) {
                    finish(new Error(`HTTP 状态异常（${response.statusCode}）`));
                    response.destroy();
                    return;
                }
                let size = 0;
                const chunks = [];
                response.on('data', chunk => {
                    size += chunk.length;
                    if (size > 262144) {
                        finish(new Error('响应超过大小限制'));
                        response.destroy();
                    } else chunks.push(chunk);
                });
                response.on('error', () => finish(new Error('响应传输失败')));
                response.on('aborted', () => finish(new Error('响应意外中断')));
                response.on('end', () => {
                    if (settled) return;
                    let data;
                    try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
                    catch { finish(new Error('响应不是有效 JSON')); return; }
                    if (!data || typeof data !== 'object' || data.retcode !== 0) {
                        const code = Number.isSafeInteger(data?.retcode) ? `（业务码 ${data.retcode}）` : '';
                        finish(new Error(`接口未确认成功${code}`));
                        return;
                    }
                    if (action === 'queryBalanceAndBonus' &&
                        !(typeof data.result?.balance === 'number' && Number.isFinite(data.result.balance) ||
                          typeof data.result?.balance === 'string' && /^-?\d+(\.\d+)?$/.test(data.result.balance))) {
                        finish(new Error('余额响应缺少有效 balance 字段')); return;
                    }
                    finish(null, data);
                });
            });
            req.on('error', () => finish(new Error('网络请求失败，请核对连接及抓参')));
        } catch {
            finish(new Error('请求组装失败，请核对抓参字段'));
            if (req) req.destroy();
        }
    });
}

function showIdentity(result, capture) {
    if (!result || typeof result !== 'object') return;
    const secrets = [...Object.entries(capture.headers), ...Object.entries(capture.paramsRaw)]
        .filter(([key]) => /cookie|token|session|auth|secret|sign|device|phone|mobile/i.test(key))
        .map(([, value]) => String(value)).concat(SECRET).filter(value => value.length >= 4);
    for (const field of ['nickname', 'username', 'displayName', 'uid']) {
        const value = result[field];
        if (!['string', 'number'].includes(typeof value)) continue;
        const text = String(value);
        if (!text || /[\r\n\x00-\x1f\x7f]/.test(text) || /^\+?[\d ()-]{7,}$/.test(text) && field !== 'uid' ||
            secrets.some(secret => text.includes(secret))) continue;
        log(`官方账号身份 ${field}=${text}`);
    }
}

async function runAccount(line, index) {
    const begin = Date.now();
    const stats = { account: index, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, seconds: 0 };
    records.push(stats);
    log(`账号 ${index} 开始`);
    let stageNumber = 0;
    async function stage(name, operation, skipReason) {
        const stageStart = Date.now();
        stats.total++;
        const label = `账号 ${index} 阶段 ${++stageNumber} ${name}`;
        log(`${label} 开始`);
        if (skipReason) {
            stats.skipped++;
            log(`⏭️ ${label} ${skipReason}，耗时 ${elapsed(stageStart)} 秒`);
            return null;
        }
        try {
            const result = await operation();
            stats.success++;
            log(`✅ ${label} ${result.detail || '接口 retcode=0'}，耗时 ${elapsed(stageStart)} 秒`);
            return result;
        } catch (error) {
            stats.failed++;
            log(`❌ ${label} ${error.message}，耗时 ${elapsed(stageStart)} 秒`);
            return null;
        }
    }
    let capture;
    await stage('配置与签名核验', async () => {
        const parsed = parseCapture(line);
        buildHeaders(parsed);
        buildUrl('queryBalanceAndBonus', parsed);
        capture = parsed;
        return { detail: 'JSON、请求头和签名组装通过' };
    });
    stats.configurationError = !capture;
    const skip = !capture ? '账号配置失败' : dryRun ? '离线预演，未请求接口' : '';
    const before = await stage('查询运行前余额', async () => {
        const data = await request('queryBalanceAndBonus', capture);
        showIdentity(data.result, capture);
        return { detail: `余额 ${data.result.balance} Coins` };
    }, skip);
    await stage('每日签到', async () => {
        const data = await request('checkIn', capture);
        showIdentity(data.result, capture);
        return { detail: '签到接口确认成功' };
    }, skip || (!before ? '前置余额核验失败，停止账号变更' : ''));
    let videoStopped = false;
    for (let i = 0; i < 5; i++) {
        const video = await stage(`视频奖励 ${i + 1}/5`, async () => {
            await new Promise(resolve => setTimeout(resolve, i === 0 ? 1500 : 8000));
            const data = await request('videoBonus', capture);
            const bonus = data.result?.bonus;
            return { detail: typeof bonus === 'number' && Number.isFinite(bonus) ? `奖励 ${bonus} Coins` : '奖励接口确认成功' };
        }, skip || (!videoEnabled ? '未显式开启视频奖励' : !before ? '前置余额核验失败' : videoStopped ? '此前视频奖励失败，停止后续领取' : ''));
        if (!video) videoStopped = true;
    }
    await stage('查询最新余额', async () => {
        const data = await request('queryBalanceAndBonus', capture);
        showIdentity(data.result, capture);
        return { detail: `最新余额 ${data.result.balance} Coins` };
    }, skip);
    stats.seconds = elapsed(begin);
    log(`账号 ${index} 统计 总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.seconds} 秒`);
}

function notificationEnabled() {
    const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
    if (/^(0|false|no|off)$/.test(mode)) return false;
    if (enabled(mode)) return true;
    const selectors = (process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
    const names = [CATALOG_ID, 'PingMeSignin.js', 'scripts/PingMeSignin.js', 'candidate.js', path.basename(__filename)];
    return selectors.some(selector => {
        const expression = '^' + selector.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$';
        return names.some(name => new RegExp(expression).test(name));
    });
}

function notify(summary) {
    const body = `模式 ${summary.mode}，状态 ${summary.status}；账号总数 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${summary.failed}；子任务成功 ${summary.steps.success}，跳过 ${summary.steps.skipped}，失败 ${summary.steps.failed}`;
    if (!notificationEnabled()) return '未选中或已关闭';
    if (dryRun) {
        log(`离线通知预览 ${TITLE} ${body}`);
        return '离线预览，未联网投递';
    }
    const candidates = [
        process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
        path.join(__dirname, 'sendNotify.js'),
        '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'
    ].filter(Boolean);
    for (const filename of [...new Set(candidates)]) {
        if (!fs.existsSync(filename)) continue;
        const script = `Promise.resolve().then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).then(() => process.exit(0)).catch(() => process.exit(1));`;
        const child = spawnSync(process.execPath, ['-e', script, filename, TITLE, body], {
            stdio: 'ignore', timeout: 15000, killSignal: 'SIGKILL'
        });
        if (child.status === 0) return '已发送';
    }
    return '通知模块不可用或投递失败，保留业务退出码';
}

async function main() {
    log(`========== ${TITLE} ==========`);
    log(`开始时间 ${new Date(started).toISOString()}，模式 ${dryRun ? '离线预演' : '实际运行'}`);
    const lines = accountLines(process.env.pingme_capture_v3);
    log(`账号数 ${lines.length}`);
    let configurationError = lines.length === 0;
    if (configurationError) log('❌ 阶段 1 配置检查 缺少必填 pingme_capture_v3，耗时 0 秒');
    for (let index = 0; index < lines.length; index++) await runAccount(lines[index], index + 1);
    configurationError = configurationError || records.some(record => record.configurationError);
    const failed = records.filter(record => record.failed > 0).length;
    const steps = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    for (const record of records) for (const key of Object.keys(steps)) steps[key] += record[key];
    const summary = {
        task: TITLE, mode: dryRun ? 'dry-run' : 'live', accounts: lines.length,
        succeeded: records.length - failed, failed, configurationError,
        status: configurationError ? 'configuration-error' : failed ? (failed === lines.length ? 'failure' : 'partial-failure') : dryRun ? 'dry-run' : 'success',
        steps, accountResults: records
    };
    summary.notification = notify(summary);
    summary.seconds = elapsed(started);
    summary.finishedAt = new Date().toISOString();
    log('----------------------------------------');
    log(`账号统计 总数 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${failed}`);
    log(`子任务统计 总数 ${steps.total}，成功 ${steps.success}，已完成 ${steps.alreadyComplete}，跳过 ${steps.skipped}，失败 ${steps.failed}`);
    log(`通知状态 ${summary.notification}`);
    log(`完成时间 ${summary.finishedAt}，总耗时 ${summary.seconds} 秒，最终状态 ${summary.status}`);
    console.log('TASK_SUMMARY=' + JSON.stringify(summary));
    process.exitCode = configurationError || failed ? 1 : 0;
}

function MD5(string) {
    function RotateLeft(lValue, iShiftBits) { return (lValue << iShiftBits) | (lValue >>> (32 - iShiftBits)); }
    function AddUnsigned(lX, lY) {
        const lX4 = lX & 0x40000000, lY4 = lY & 0x40000000, lX8 = lX & 0x80000000, lY8 = lY & 0x80000000;
        const lResult = (lX & 0x3FFFFFFF) + (lY & 0x3FFFFFFF);
        if (lX4 & lY4) return lResult ^ 0x80000000 ^ lX8 ^ lY8;
        if (lX4 | lY4) return (lResult & 0x40000000) ? (lResult ^ 0xC0000000 ^ lX8 ^ lY8) : (lResult ^ 0x40000000 ^ lX8 ^ lY8);
        return lResult ^ lX8 ^ lY8;
    }
    function F(x, y, z) { return (x & y) | ((~x) & z); }
    function G(x, y, z) { return (x & z) | (y & (~z)); }
    function H(x, y, z) { return x ^ y ^ z; }
    function I(x, y, z) { return y ^ (x | (~z)); }
    function FF(a, b, c, d, x, s, ac) { a = AddUnsigned(a, AddUnsigned(AddUnsigned(F(b, c, d), x), ac)); return AddUnsigned(RotateLeft(a, s), b); }
    function GG(a, b, c, d, x, s, ac) { a = AddUnsigned(a, AddUnsigned(AddUnsigned(G(b, c, d), x), ac)); return AddUnsigned(RotateLeft(a, s), b); }
    function HH(a, b, c, d, x, s, ac) { a = AddUnsigned(a, AddUnsigned(AddUnsigned(H(b, c, d), x), ac)); return AddUnsigned(RotateLeft(a, s), b); }
    function II(a, b, c, d, x, s, ac) { a = AddUnsigned(a, AddUnsigned(AddUnsigned(I(b, c, d), x), ac)); return AddUnsigned(RotateLeft(a, s), b); }
    function ConvertToWordArray(str) {
        const lMessageLength = str.length;
        const lNumberOfWords_temp1 = lMessageLength + 8;
        const lNumberOfWords_temp2 = (lNumberOfWords_temp1 - (lNumberOfWords_temp1 % 64)) / 64;
        const lNumberOfWords = (lNumberOfWords_temp2 + 1) * 16;
        const lWordArray = Array(lNumberOfWords - 1).fill(0);
        let lBytePosition = 0, lByteCount = 0;
        while (lByteCount < lMessageLength) {
            const lWordCount = (lByteCount - (lByteCount % 4)) / 4;
            lBytePosition = (lByteCount % 4) * 8;
            lWordArray[lWordCount] |= str.charCodeAt(lByteCount) << lBytePosition;
            lByteCount++;
        }
        const lWordCount = (lByteCount - (lByteCount % 4)) / 4;
        lBytePosition = (lByteCount % 4) * 8;
        lWordArray[lWordCount] |= 0x80 << lBytePosition;
        lWordArray[lNumberOfWords - 2] = lMessageLength << 3;
        lWordArray[lNumberOfWords - 1] = lMessageLength >>> 29;
        return lWordArray;
    }
    function WordToHex(lValue) {
        let WordToHexValue = '';
        for (let lCount = 0; lCount <= 3; lCount++) {
            const lByte = (lValue >>> (lCount * 8)) & 255;
            const WordToHexValue_temp = '0' + lByte.toString(16);
            WordToHexValue += WordToHexValue_temp.substr(WordToHexValue_temp.length - 2, 2);
        }
        return WordToHexValue;
    }
    const x = ConvertToWordArray(string);
    let a = 0x67452301, b = 0xEFCDAB89, c = 0x98BADCFE, d = 0x10325476;
    const S11 = 7, S12 = 12, S13 = 17, S14 = 22, S21 = 5, S22 = 9, S23 = 14, S24 = 20;
    const S31 = 4, S32 = 11, S33 = 16, S34 = 23, S41 = 6, S42 = 10, S43 = 15, S44 = 21;
    for (let k = 0; k < x.length; k += 16) {
        const AA = a, BB = b, CC = c, DD = d;
        a = FF(a,b,c,d,x[k+0],S11,0xD76AA478); d = FF(d,a,b,c,x[k+1],S12,0xE8C7B756); c = FF(c,d,a,b,x[k+2],S13,0x242070DB); b = FF(b,c,d,a,x[k+3],S14,0xC1BDCEEE);
        a = FF(a,b,c,d,x[k+4],S11,0xF57C0FAF); d = FF(d,a,b,c,x[k+5],S12,0x4787C62A); c = FF(c,d,a,b,x[k+6],S13,0xA8304613); b = FF(b,c,d,a,x[k+7],S14,0xFD469501);
        a = FF(a,b,c,d,x[k+8],S11,0x698098D8); d = FF(d,a,b,c,x[k+9],S12,0x8B44F7AF); c = FF(c,d,a,b,x[k+10],S13,0xFFFF5BB1); b = FF(b,c,d,a,x[k+11],S14,0x895CD7BE);
        a = FF(a,b,c,d,x[k+12],S11,0x6B901122); d = FF(d,a,b,c,x[k+13],S12,0xFD987193); c = FF(c,d,a,b,x[k+14],S13,0xA679438E); b = FF(b,c,d,a,x[k+15],S14,0x49B40821);
        a = GG(a,b,c,d,x[k+1],S21,0xF61E2562); d = GG(d,a,b,c,x[k+6],S22,0xC040B340); c = GG(c,d,a,b,x[k+11],S23,0x265E5A51); b = GG(b,c,d,a,x[k+0],S24,0xE9B6C7AA);
        a = GG(a,b,c,d,x[k+5],S21,0xD62F105D); d = GG(d,a,b,c,x[k+10],S22,0x02441453); c = GG(c,d,a,b,x[k+15],S23,0xD8A1E681); b = GG(b,c,d,a,x[k+4],S24,0xE7D3FBC8);
        a = GG(a,b,c,d,x[k+9],S21,0x21E1CDE6); d = GG(d,a,b,c,x[k+14],S22,0xC33707D6); c = GG(c,d,a,b,x[k+3],S23,0xF4D50D87); b = GG(b,c,d,a,x[k+8],S24,0x455A14ED);
        a = GG(a,b,c,d,x[k+13],S21,0xA9E3E905); d = GG(d,a,b,c,x[k+2],S22,0xFCEFA3F8); c = GG(c,d,a,b,x[k+7],S23,0x676F02D9); b = GG(b,c,d,a,x[k+12],S24,0x8D2A4C8A);
        a = HH(a,b,c,d,x[k+5],S31,0xFFFA3942); d = HH(d,a,b,c,x[k+8],S32,0x8771F681); c = HH(c,d,a,b,x[k+11],S33,0x6D9D6122); b = HH(b,c,d,a,x[k+14],S34,0xFDE5380C);
        a = HH(a,b,c,d,x[k+1],S31,0xA4BEEA44); d = HH(d,a,b,c,x[k+4],S32,0x4BDECFA9); c = HH(c,d,a,b,x[k+7],S33,0xF6BB4B60); b = HH(b,c,d,a,x[k+10],S34,0xBEBFBC70);
        a = HH(a,b,c,d,x[k+13],S31,0x289B7EC6); d = HH(d,a,b,c,x[k+0],S32,0xEAA127FA); c = HH(c,d,a,b,x[k+3],S33,0xD4EF3085); b = HH(b,c,d,a,x[k+6],S34,0x04881D05);
        a = HH(a,b,c,d,x[k+9],S31,0xD9D4D039); d = HH(d,a,b,c,x[k+12],S32,0xE6DB99E5); c = HH(c,d,a,b,x[k+15],S33,0x1FA27CF8); b = HH(b,c,d,a,x[k+2],S34,0xC4AC5665);
        a = II(a,b,c,d,x[k+0],S41,0xF4292244); d = II(d,a,b,c,x[k+7],S42,0x432AFF97); c = II(c,d,a,b,x[k+14],S43,0xAB9423A7); b = II(b,c,d,a,x[k+5],S44,0xFC93A039);
        a = II(a,b,c,d,x[k+12],S41,0x655B59C3); d = II(d,a,b,c,x[k+3],S42,0x8F0CCC92); c = II(c,d,a,b,x[k+10],S43,0xFFEFF47D); b = II(b,c,d,a,x[k+1],S44,0x85845DD1);
        a = II(a,b,c,d,x[k+8],S41,0x6FA87E4F); d = II(d,a,b,c,x[k+15],S42,0xFE2CE6E0); c = II(c,d,a,b,x[k+6],S43,0xA3014314); b = II(b,c,d,a,x[k+13],S44,0x4E0811A1);
        a = II(a,b,c,d,x[k+4],S41,0xF7537E82); d = II(d,a,b,c,x[k+11],S42,0xBD3AF235); c = II(c,d,a,b,x[k+2],S43,0x2AD7D2BB); b = II(b,c,d,a,x[k+9],S44,0xEB86D391);
        a = AddUnsigned(a,AA); b = AddUnsigned(b,BB); c = AddUnsigned(c,CC); d = AddUnsigned(d,DD);
    }
    return (WordToHex(a) + WordToHex(b) + WordToHex(c) + WordToHex(d)).toLowerCase();
}


main();
