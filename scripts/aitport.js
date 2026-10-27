// name: 机场自动登录签到
// cron: 1 8 * * *
/**
 * name: 机场自动登录签到
 * cron: 0 8 * * *
 * 上游：lliei0x/aitport-auto-checkin，checkin.ts
 * 版本：793f17fd25e6257f990abcdcd55f0a64f8d4abd8
 * 许可：GPL-3.0，维护版本沿用上游许可与署名。
 * 上游原始说明：优雅的自动登录+签到脚本 (TypeScript 版)；运行方式: bun checkin.ts
 * 本文件运行方式：Node.js >= 18，node candidate.js；无需第三方依赖。
 *
 * 功能盘点：邮箱密码登录、签到、今日已签识别、奖励 MB / 累计流量 GB、PushPlus HTML 卡片。
 * 上游无 cron，本版本建议每日 08:00；无同产品维护脚本或相关来源需要合并。
 * 唯一业务写操作为签到（可能获得流量）；不修改密码、订阅或账户资料。
 *
 * AITPORT_ACCOUNTS：每行 邮箱|密码；只在第一个 | 分割，密码中的后续 | 和空格原样保留。
 * 从 https://flzt.top 的个人注册/登录信息获取，勿复制他人的凭据。
 * 单账号兼容 USER_EMAIL、USER_PASSWORD；设置 AITPORT_ACCOUNTS 时优先使用该变量。
 * AITPORT_DRY_RUN=1：验证配置并模拟步骤，禁止业务及通知网络，也不加载通知模块。
 * PUSHPLUS_TOKEN：可选，从 PushPlus 官网个人中心获取，保留上游 HTML 通知。
 * QINGLONG_NOTIFY=auto（默认）/1/0：自动按名单、强制启用、全部关闭。
 * QINGLONG_NOTIFY_SCRIPTS：自动模式白名单，支持目录相对路径、文件名、通配符及
 * be4fa480e7c5151e；以逗号、分号或空白分隔，* 为全部，空字符串关闭全部。
 * 默认 listed-only 无内置名单；auto 未配置名单时不发送青龙通知。
 * QINGLONG_NOTIFY_DIR：可选，青龙 sendNotify.js 或 notify.py 所在目录。
 * 通知只含账号序号及脱敏统计，失败不改变业务退出码；全局关闭同时关闭 PushPlus。
 */
'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["be4fa480e7c5151e", "scripts/aitport.js", "aitport.js", "aitport"];
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
const { spawn } = require('node:child_process');

const TITLE = '机场自动登录签到';
const CATALOG = 'be4fa480e7c5151e';
const BASE = 'https://flzt.top';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36';
const started = Date.now();
const dry = process.env.AITPORT_DRY_RUN === '1';
const secrets = new Set();
const accounts = [];
const results = [];
const summary = { task: TITLE, mode: dry ? 'dry-run' : 'live', accounts: 0,
  success: 0, failed: 0, skipped: 0, tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 },
  status: 'failure', notification: 'pending' };

function remember(value) { if (typeof value === 'string' && value) secrets.add(value); }
function redact(value, maskPhone = true) {
  let text = String(value).replace(/[\r\n\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g, ' ');
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) text = text.split(secret).join('[已隐藏]');
  text = text.replace(/[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}/g, '[邮箱已隐藏]');
  return maskPhone ? text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]') : text;
}
function time() { return new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }); }
function stamp() { return new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }); }
function log(message) { console.log(`[${time()}] ${message}`); }
function fail(message) { return new Error(message); }
function truth(value) { return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase()); }
function off(value) { return ['0', 'false', 'no', 'off'].includes(String(value).toLowerCase()); }

// 固定 HTTPS 目标，不跟随重定向；完整请求期限、响应体上限均独立于服务端行为。
function request(url, method = 'GET', body, headers = {}) {
  if (dry) return Promise.reject(fail('断网预演禁止 HTTP 请求'));
  return new Promise((resolve, reject) => {
    const bytes = body === undefined ? null : Buffer.from(JSON.stringify(body));
    let settled = false;
    let timer;
    const finish = (err, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (err) reject(err); else resolve(value);
    };
    const req = https.request(url, { method, headers: { ...headers,
      ...(bytes ? { 'Content-Type': 'application/json', 'Content-Length': bytes.length } : {}) } }, res => {
      const parts = [];
      let size = 0;
      res.on('data', part => {
        size += part.length;
        if (size > 1024 * 1024) {
          finish(fail('响应超过安全大小限制'));
          res.destroy(); req.destroy();
        } else parts.push(part);
      });
      res.on('error', () => finish(fail('响应读取失败')));
      res.on('aborted', () => finish(fail('响应被中断')));
      res.on('end', () => {
        if (settled) return;
        if (res.statusCode < 200 || res.statusCode >= 300) {
          finish(fail(`HTTP 状态异常（${res.statusCode}）`)); return;
        }
        try {
          const json = JSON.parse(Buffer.concat(parts).toString('utf8'));
          if (!json || typeof json !== 'object' || Array.isArray(json)) throw fail('结构异常');
          finish(null, json);
        } catch { finish(fail('接口未返回有效 JSON 对象')); }
      });
    });
    timer = setTimeout(() => { finish(fail('请求超时（15 秒）')); req.destroy(); }, 15000);
    req.on('error', () => finish(fail('网络请求失败，请检查连通性或证书')));
    if (bytes) req.write(bytes);
    req.end();
  });
}

function parseAccounts() {
  remember(process.env.PUSHPLUS_TOKEN);
  remember(process.env.USER_EMAIL);
  remember(process.env.USER_PASSWORD);
  const combined = process.env.AITPORT_ACCOUNTS;
  if (combined !== undefined) {
    for (const raw of combined.split(/\r?\n/).filter(line => line.trim())) {
      remember(raw);
      const split = raw.indexOf('|');
      const email = split < 0 ? '' : raw.slice(0, split).trim();
      const password = split < 0 ? '' : raw.slice(split + 1);
      remember(email); remember(password);
      accounts.push({ email, password, valid: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && password.length > 0 });
    }
  } else if (process.env.USER_EMAIL !== undefined || process.env.USER_PASSWORD !== undefined) {
    const email = (process.env.USER_EMAIL || '').trim();
    const password = process.env.USER_PASSWORD || '';
    accounts.push({ email, password, valid: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && password.length > 0 && !/[\r\n]/.test(password) });
  }
  summary.accounts = accounts.length;
}

function showIdentity(json, index) {
  const values = [json.data?.user, json.data, json.user, json].filter(v => v && typeof v === 'object');
  for (const obj of values) {
    for (const field of ['nickname', 'username', 'display_name', 'displayName', 'public_uid', 'uid']) {
      if ((typeof obj[field] === 'string' && obj[field]) || typeof obj[field] === 'number') {
        // 明确标注为公开 UID 的数字不是手机号，保留原值供用户核对。
        log(`账号 ${index} 官方身份（${field}）：${redact(obj[field], !['public_uid', 'uid'].includes(field))}`);
      }
    }
  }
}

async function stage(record, number, name, action) {
  const start = Date.now();
  log(`账号 ${record.account} · 阶段 ${number}/2 ${name} 开始`);
  try {
    const state = await action();
    record[state] += 1;
    log(`账号 ${record.account} · 阶段 ${number}/2 ${name} ${state === 'alreadyComplete' ? '☑️ 今日已完成' : state === 'skipped' ? '⏭️ 预演跳过请求' : '✅ 成功'}，耗时 ${Date.now() - start} 毫秒`);
    return state;
  } catch (error) {
    record.failed += 1;
    log(`账号 ${record.account} · 阶段 ${number}/2 ${name} ❌ ${redact(error.message)}，耗时 ${Date.now() - start} 毫秒`);
    throw error;
  }
}

async function runAccount(account, index) {
  const start = Date.now();
  const record = { account: index, total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, status: 'failure' };
  let token;
  try {
    await stage(record, 1, '配置与登录', async () => {
      if (!account.valid) throw fail('账号配置错误：每行应为邮箱|密码；也可使用单账号兼容变量');
      if (dry) return 'skipped';
      const json = await request(`${BASE}/api/v1/passport/auth/login`, 'POST',
        { email: account.email, password: account.password }, { 'User-Agent': UA });
      token = json.data?.auth_data || json.data?.token;
      if (typeof token !== 'string' || !token.trim() || /[\r\n]/.test(token)) throw fail('登录业务失败：未获得有效授权');
      remember(token);
      showIdentity(json, index);
      return 'success';
    });
    await stage(record, 2, '每日签到', async () => {
      if (dry) return 'skipped';
      const json = await request(`${BASE}/api/v1/user/checkIn`, 'GET', undefined,
        { authorization: token, 'User-Agent': UA });
      showIdentity(json, index);
      if (json.status === 'success') {
        const reward = json.data?.reward_mb;
        const total = json.data?.total_checkin_traffic;
        const validNumber = v => typeof v === 'number' && Number.isFinite(v) && v >= 0;
        const rewardText = validNumber(reward) ? `${reward} MB` : '接口未提供';
        const totalText = validNumber(total) ? `${(total / 1024 ** 3).toFixed(2)} GB` : '接口未提供';
        record.reward = rewardText; record.traffic = totalText;
        log(`账号 ${index} 签到成功：获得流量 ${rewardText}；累计签到流量 ${totalText}`);
        return 'success';
      }
      if (typeof json.message === 'string' && json.message.toLowerCase().includes('already checked in')) return 'alreadyComplete';
      throw fail('签到业务失败：未收到成功或今日已签确认');
    });
    record.status = dry ? 'dry-run' : 'success';
  } catch {
    record.skipped = record.total - record.success - record.alreadyComplete - record.failed;
    record.status = account.valid ? 'failure' : 'configuration-error';
  } finally {
    record.durationMs = Date.now() - start;
    results.push(record);
    log(`账号 ${index} 统计：总任务 ${record.total}，成功 ${record.success}，已完成 ${record.alreadyComplete}，跳过 ${record.skipped}，失败 ${record.failed}，耗时 ${record.durationMs} 毫秒；状态 ${record.status}`);
  }
}

function selectedForQinglong() {
  const flag = process.env.QINGLONG_NOTIFY || 'auto';
  if (off(flag)) return false;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (selection !== undefined && !selection.trim()) return false;
  if (truth(flag)) return true;
  if (selection === undefined) return false;
  const filename = path.basename(__filename);
  const normalized = __filename.replace(/\\/g, '/');
  const scriptsAt = normalized.lastIndexOf('/scripts/');
  const relative = scriptsAt < 0 ? filename : normalized.slice(scriptsAt + 9);
  const names = [CATALOG, filename, relative];
  return selection.split(/[,;\s]+/).filter(Boolean).some(selector => {
    const regex = new RegExp('^' + selector.split('*').map(part => part.split('?')
      .map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.')).join('.*') + '$');
    return names.some(name => regex.test(name));
  });
}

// 在独立子进程运行青龙通知工具；限制执行时间、不回显插件输出、不通过命令行传递内容。
function notifyChild(command, args, payload) {
  return new Promise(resolve => {
    let done = false;
    let timer;
    const finish = ok => { if (!done) { done = true; clearTimeout(timer); resolve(ok); } };
    const child = spawn(command, args, { stdio: ['pipe', 'ignore', 'ignore'] });
    timer = setTimeout(() => { child.kill('SIGKILL'); finish(false); }, 15000);
    child.on('error', () => finish(false));
    child.on('close', code => finish(code === 0));
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(payload));
  });
}

async function qinglongNotify(payload) {
  const directories = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const jsDriver = `const fs=require('node:fs'); const p=JSON.parse(fs.readFileSync(0,'utf8')); Promise.resolve().then(()=>require(process.argv[1]).sendNotify(p.title,p.body)).then(r=>process.exit(r===false?1:0),()=>process.exit(1));`;
  for (const directory of [...new Set(directories)]) {
    const file = path.resolve(directory, 'sendNotify.js');
    if (fs.existsSync(file) && await notifyChild(process.execPath, ['-e', jsDriver, file], payload)) return true;
  }
  const pythonDriver = 'import sys,json,importlib.util\np=json.load(sys.stdin)\nif len(sys.argv)>1:\n s=importlib.util.spec_from_file_location("qinglong_notification",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)\nelse:\n import notify as m\nr=m.send(p["title"],p["body"])\nif r is False: sys.exit(1)\n';
  for (const directory of [...new Set(directories)]) {
    const file = path.resolve(directory, 'notify.py');
    if (fs.existsSync(file) && await notifyChild('python3', ['-c', pythonDriver, file], payload)) return true;
  }
  return notifyChild('python3', ['-c', pythonDriver], payload);
}

function escapeHtml(value) { return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]); }
function renderCard(body) {
  const color = summary.failed ? '#f5222d' : '#52c41a';
  return `<div style="max-width:400px;margin:auto;font-family:sans-serif"><div style="background:${color};color:white;padding:15px;border-radius:12px 12px 0 0;font-weight:bold">${escapeHtml(TITLE)}</div><div style="padding:20px;border:1px solid #eee;white-space:pre-wrap">${escapeHtml(body)}</div></div>`;
}

async function sendNotifications() {
  const body = [`${TITLE}：${summary.status}`, `账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}，预演 ${summary.skipped}`,
    ...results.map(r => `账号 ${r.account}：${r.status}；任务成功 ${r.success}，已完成 ${r.alreadyComplete}，跳过 ${r.skipped}，失败 ${r.failed}${r.reward ? `；获得 ${r.reward}，累计 ${r.traffic}` : ''}`)].join('\n');
  if (dry) { log('通知：断网预演，已生成脱敏摘要，跳过所有通知投递'); return 'dry-run'; }
  if (off(process.env.QINGLONG_NOTIFY)) { log('通知：全局开关已关闭'); return 'disabled'; }
  const outcomes = [];
  if (selectedForQinglong()) {
    let ok = false;
    try { ok = await qinglongNotify({ title: TITLE, body }); } catch { /* 保持业务结果 */ }
    outcomes.push(ok ? 'qinglong-sent' : 'qinglong-unavailable-or-failed');
    log(`青龙通知：${ok ? '✅ 已交付通知模块' : '⚠️ 通知工具不可用或投递失败，保留业务退出码'}`);
  } else log('青龙通知：未列入自动通知名单');
  if (process.env.PUSHPLUS_TOKEN) {
    try {
      const response = await request('https://www.pushplus.plus/send', 'POST', {
        token: process.env.PUSHPLUS_TOKEN, title: TITLE, content: renderCard(body), template: 'html'
      });
      if (response.code !== 200) throw fail('通知业务未确认');
      outcomes.push('pushplus-sent'); log('PushPlus 通知：✅ 已确认发送');
    } catch { outcomes.push('pushplus-failed'); log('PushPlus 通知：⚠️ 投递失败，保留业务退出码'); }
  }
  return outcomes.join(',') || 'not-selected';
}

async function main() {
  const configStart = Date.now();
  parseAccounts();
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${stamp()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${accounts.length}`);
  log(`阶段 1/3 配置检查完成，耗时 ${Date.now() - configStart} 毫秒：账号逐行独立处理，不输出邮箱、密码或接口原文`);
  if (!accounts.length) log('❌ 配置错误：请填写 AITPORT_ACCOUNTS，或单账号 USER_EMAIL 与 USER_PASSWORD');
  const accountsStart = Date.now();
  log('阶段 2/3 账号任务开始');
  for (let i = 0; i < accounts.length; i++) await runAccount(accounts[i], i + 1);
  log(`阶段 2/3 账号任务结束，耗时 ${Date.now() - accountsStart} 毫秒`);
  summary.success = results.filter(r => r.status === 'success').length;
  summary.failed = results.filter(r => r.failed > 0).length;
  summary.skipped = results.filter(r => r.status === 'dry-run').length;
  for (const r of results) for (const key of Object.keys(summary.tasks)) summary.tasks[key] += r[key];
  const bad = !accounts.length || summary.failed > 0;
  summary.status = !accounts.length || results.some(r => r.status === 'configuration-error') ? 'configuration-error' :
    summary.failed ? (summary.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  process.exitCode = bad ? 1 : 0;
  const notificationStart = Date.now();
  log('阶段 3/3 脱敏汇总与通知开始');
  try { summary.notification = await sendNotifications(); }
  catch { summary.notification = 'failed'; log('⚠️ 通知异常，保留业务退出码'); }
  log(`阶段 3/3 脱敏汇总与通知结束，耗时 ${Date.now() - notificationStart} 毫秒`);
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`账号统计：总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}，预演 ${summary.skipped}`);
  log(`子任务统计：总数 ${summary.tasks.total}，成功 ${summary.tasks.success}，已完成 ${summary.tasks.alreadyComplete}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}`);
  log(`总耗时：${summary.durationMs} 毫秒；完成时间：${stamp()}；通知状态：${summary.notification}`);
  log(`最终状态：${summary.status}；退出码：${process.exitCode}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
}

main().catch(async () => {
  process.exitCode = 1;
  summary.status = 'failure';
  log('❌ 任务运行异常，异常细节已隐藏');
  try { summary.notification = await sendNotifications(); } catch { summary.notification = 'failed'; }
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  log(`完成时间：${stamp()}；最终状态：failure；退出码：1`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
});
