// name: Cafe123 每日签到
// cron: 30 11 14 * * *
/*
name: Cafe123 每日签到
cron: 30 11 14 * * *

来源 https://github.com/cafehaus/check-in，原文件 index.js，作者 cafehaus。
许可证 MIT。原输入未包含额外版权声明。

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

Node.js >=18，青龙每次调度执行一轮，不安装 node-cron。
CAFE123_ACCOUNTS 每个非空行填写 邮箱|密码，仅第一个 | 分隔字段。
从 https://cafe123.cn/auth/login 使用本人注册的邮箱和密码取得参数。
密码后续的 | 原样保留，账号行首尾不裁剪。禁止使用换行符作为密码内容。
CAFE123_DRY_RUN=1 完全离线校验配置并模拟阶段，通知仅生成脱敏摘要。
正式运行仅登录及签到，不修改账号资料，不重试有副作用的请求。
业务成功要求 JSON ret 为数字 1，其他响应均失败闭合，需实际验证接口契约。
原始调度为每天 14:11:30，使用青龙时区，保留六字段表达式。
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
    const identities = ["dd37430b249399f1", "scripts/task_dd37430b.js", "task_dd37430b.js", "task_dd37430b"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');

const title = 'Cafe123 每日签到';
const catalogId = 'dd37430b249399f1';
const origin = 'https://cafe123.cn';
const dryRun = process.env.CAFE123_DRY_RUN === '1';
const started = Date.now();
const rows = (process.env.CAFE123_ACCOUNTS || '').split(/\r?\n/).filter(row => row.trim());
const results = [];

function log(message) {
    console.log(`[${new Date().toTimeString().slice(0, 8)}] ${message}`);
}

// 错误仅使用固定文案，禁止记录请求、响应、凭据或底层异常。
function request(route, body, cookie) {
    return new Promise((resolve, reject) => {
        const headers = {
            accept: 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'zh-CN,zh;q=0.9',
            'x-requested-with': 'XMLHttpRequest',
            Referer: `${origin}${route === '/auth/login' ? '/auth/login' : '/user'}`,
        };
        if (body !== null) {
            headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
            headers['content-length'] = Buffer.byteLength(body);
        }
        if (cookie) headers.cookie = cookie;
        const req = https.request(`${origin}${route}`, { method: 'POST', headers }, res => {
            const chunks = [];
            let size = 0;
            res.on('data', chunk => {
                size += chunk.length;
                if (size > 262144) req.destroy(new Error('响应超过大小限制'));
                else chunks.push(chunk);
            });
            res.on('error', () => reject(new Error('响应读取失败')));
            res.on('end', () => {
                if (res.statusCode !== 200) return reject(new Error('接口 HTTP 状态异常'));
                try {
                    const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
                    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error();
                    resolve({ data, cookies: res.headers['set-cookie'] || [] });
                } catch {
                    reject(new Error('接口未返回有效 JSON 对象'));
                }
            });
        });
        const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
        req.on('close', () => clearTimeout(timer));
        req.on('error', () => reject(new Error('网络请求失败或超时')));
        req.end(body);
    });
}

function sessionCookies(values) {
    const jar = new Map();
    for (const value of values) {
        const [pair, ...attributes] = value.split(';');
        const split = pair.indexOf('=');
        if (split <= 0) continue;
        const name = pair.slice(0, split).trim();
        const contents = pair.slice(split + 1).trim();
        let allowed = true;
        for (const attribute of attributes) {
            const [key, ...parts] = attribute.trim().split('=');
            const setting = parts.join('=').trim();
            if (key.toLowerCase() === 'domain' && setting.replace(/^\./, '').toLowerCase() !== 'cafe123.cn') allowed = false;
            if (key.toLowerCase() === 'path' && !'/user/checkin'.startsWith(setting)) allowed = false;
            if (key.toLowerCase() === 'max-age' && Number(setting) <= 0) allowed = false;
            if (key.toLowerCase() === 'expires' && Date.parse(setting) <= Date.now()) allowed = false;
        }
        if (allowed && contents && /^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(name) && !/[\r\n]/.test(contents)) jar.set(name, contents);
    }
    return [...jar].map(([name, value]) => `${name}=${value}`).join('; ');
}

function identity(data, email, password) {
    const user = data.user && typeof data.user === 'object' ? data.user : data;
    for (const key of ['nickname', 'username', 'display_name', 'name', 'uid']) {
        const value = user[key];
        if (typeof value !== 'string' && typeof value !== 'number') continue;
        const text = String(value);
        if (!text || text.includes(email) || text.includes(password) || /[\r\n\x00-\x1f]|\d{11}|@/.test(text)) continue;
        return text;
    }
    return null;
}

async function stage(account, number, label, action) {
    const start = Date.now();
    log(`账号 ${account.index} · 阶段 ${number} ${label} · 开始`);
    try {
        const result = await action();
        account.success++;
        log(`账号 ${account.index} · 阶段 ${number} ${label} · ✅ ${dryRun ? '离线模拟通过' : '业务校验通过'} · ${Date.now() - start}ms`);
        return result;
    } catch (error) {
        account.failed++;
        log(`账号 ${account.index} · 阶段 ${number} ${label} · ❌ ${error.message} · ${Date.now() - start}ms`);
        throw error;
    }
}

async function runAccount(row, index) {
    const start = Date.now();
    const account = { index, total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, status: 'failure' };
    results.push(account);
    try {
        const split = row.indexOf('|');
        if (split <= 0 || split === row.length - 1) throw new Error('账号格式错误，应为邮箱|密码');
        const email = row.slice(0, split);
        const password = row.slice(split + 1);
        if (!/^[^\s@|]+@[^\s@|]+\.[^\s@|]+$/.test(email)) throw new Error('账号邮箱格式错误');
        const login = await stage(account, 1, '登录并校验会话', async () => {
            if (dryRun) return { cookie: null };
            const body = new URLSearchParams({ email, passwd: password, code: '', remember_me: 'week' }).toString();
            const response = await request('/auth/login', body, null);
            if (response.data.ret !== 1) throw new Error('登录业务成功码未通过');
            const cookie = sessionCookies(response.cookies);
            if (!cookie) throw new Error('登录未取得有效会话');
            const name = identity(response.data, email, password);
            if (name) log(`账号 ${index} · 官方身份 ${name}`);
            return { cookie };
        });
        await stage(account, 2, '每日签到', async () => {
            if (dryRun) return;
            const response = await request('/user/checkin', null, login.cookie);
            if (response.data.ret !== 1) throw new Error('签到业务成功码未通过');
            const name = identity(response.data, email, password);
            if (name) log(`账号 ${index} · 官方身份 ${name}`);
        });
        account.status = dryRun ? 'dry-run' : 'success';
    } catch (error) {
        if (!account.failed) {
            account.failed = 1;
            log(`账号 ${index} · ❌ ${error.message}`);
        }
        account.skipped = account.total - account.success - account.failed;
    }
    account.elapsedMs = Date.now() - start;
    log(`账号 ${index} · 总任务 ${account.total}，成功 ${account.success}，已完成 ${account.alreadyComplete}，跳过 ${account.skipped}，失败 ${account.failed} · ${account.elapsedMs}ms · ${account.status}`);
}

function notificationSelected() {
    const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
    if (['0', 'false', 'no', 'off'].includes(mode)) return false;
    if (['1', 'true', 'yes', 'on'].includes(mode)) return true;
    const selectors = process.env.QINGLONG_NOTIFY_SCRIPTS;
    if (selectors === undefined) return false;
    const names = [catalogId, 'candidate.js', path.basename(__filename), `scripts/${path.basename(__filename)}`];
    return selectors.split(/[,;\s]+/).filter(Boolean).some(selector => {
        const pattern = selector.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
        return names.some(name => new RegExp(`^${pattern}$`).test(name));
    });
}

function notify(body) {
    if (dryRun) return '离线模式已生成摘要，未发送';
    if (!notificationSelected()) return '全局策略未选中';
    const roots = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
    for (const root of roots) {
        const file = path.join(root, 'sendNotify.js');
        if (!fs.existsSync(file)) continue;
        const code = 'Promise.resolve().then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).catch(() => {process.exitCode = 1})';
        const result = spawnSync(process.execPath, ['-e', code, file, title, body], { timeout: 20000, stdio: 'ignore' });
        if (!result.error && result.status === 0) return '已发送';
    }
    const code = 'import sys, importlib.util\np=sys.argv[1]\nif p:\n s=importlib.util.spec_from_file_location("qinglong_notify",p)\n m=importlib.util.module_from_spec(s)\n s.loader.exec_module(m)\nelse:\n import notify as m\nm.send(sys.argv[2],sys.argv[3])';
    const files = roots.map(root => path.join(root, 'notify.py')).filter(file => fs.existsSync(file));
    for (const file of ['', ...files]) {
        const result = spawnSync('python3', ['-c', code, file, title, body], { timeout: 20000, stdio: 'ignore' });
        if (!result.error && result.status === 0) return '已发送';
    }
    return '通知不可用或发送失败，保留业务退出码';
}

async function main() {
    log(`========== ${title} ==========`);
    log(`开始时间 ${new Date(started).toISOString()} · 模式 ${dryRun ? '离线预演' : '正式执行'} · 账号数 ${rows.length}`);
    if (!rows.length) log('❌ 配置错误，缺少 CAFE123_ACCOUNTS');
    for (const [index, row] of rows.entries()) await runAccount(row, index + 1);
    const success = results.filter(account => account.status !== 'failure').length;
    const failed = results.length - success;
    const exitCode = rows.length && !failed ? 0 : 1;
    const status = !rows.length ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
    const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    for (const account of results) for (const key of Object.keys(totals)) totals[key] += account[key];
    const body = `状态 ${status}；账号总数 ${rows.length}，成功 ${success}，失败 ${failed}；子任务总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`;
    const notification = notify(body);
    log('----------------------------------------');
    log(body);
    log(`通知 ${notification}`);
    const finishedAt = new Date().toISOString();
    log(`完成时间 ${finishedAt} · 总耗时 ${Date.now() - started}ms · 最终状态 ${status}`);
    console.log(`TASK_SUMMARY=${JSON.stringify({ task: title, mode: dryRun ? 'dry-run' : 'live', status, accounts: rows.length, success, failed, tasks: totals, results, notification, finishedAt, elapsedMs: Date.now() - started, exitCode })}`);
    process.exitCode = exitCode;
}

main();
