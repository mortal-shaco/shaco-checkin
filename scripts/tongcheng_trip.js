// name: 同程旅行签到
// cron: 5 12 * * *
/**
 * name: 同程旅行签到
 * cron: 5 12 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 来源：chavyleung/scripts，tongcheng-trip/tongcheng-trip.js
 * 上游：https://github.com/chavyleung/scripts（保留原作者归属，按 GPL-3.0-only 分发）
 * 原计划：Surge / QuanX / Loon 均为 5 12 * * *。
 * 原获取方式：打开同程旅行 APP → 领福利，捕获
 * https://app.17u.cn/welfarecenter/index/signIndex 的请求头（含 phone、apptoken、device）。
 *
 * Node.js >= 18，无第三方业务依赖；无需代理脚本或 box.dat。
 * TONGCHENG_TRIP_ACCOUNTS：每个非空行是一个账号的完整请求头 JSON 对象。
 * 同一账号的 phone、apptoken、device 必须来自同一次登录；保留所需版本及 User-Agent 等头。
 * 兼容 tongcheng_trip_signheader（同样格式）；规范变量存在时优先，不拼接两个变量。
 * 不使用 &、@ 分隔账号，不输出凭据。抓包应仅在本人授权设备完成并安全保存。
 * TONGCHENG_TRIP_TASKS=1 才执行浏览任务 start → 等待 → finish → receive。
 * 默认关闭自动模拟浏览/领奖；签到仍默认执行。不涉及发帖、分享、消费或修改个人资料。
 * TONGCHENG_TRIP_DRY_RUN=1：离线模拟全流程，不请求业务、文案或通知网络。
 * QINGLONG_NOTIFY=auto：仅匹配 QINGLONG_NOTIFY_SCRIPTS 时通知；显式 1 强制启用，0 关闭。
 * 通知使用青龙 sendNotify.js；失败不影响业务退出码。离线模式仅显示通知预演。
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
    const identities = ["0a730847ceb97039", "scripts/tongcheng_trip.js", "tongcheng_trip.js", "tongcheng_trip"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '同程旅行签到';
const CATALOG = '0a730847ceb97039';
const started = Date.now();
const dry = /^(1|true|yes|on)$/i.test(process.env.TONGCHENG_TRIP_DRY_RUN || '');
const tasksEnabled = /^(1|true|yes|on)$/i.test(process.env.TONGCHENG_TRIP_TASKS || '0');
const accounts = [];
let configError = false;
const timestamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${timestamp()}] ${text}`);
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
function failure(message) { return new Error(message); }
const safeErrors = new Set(['HTTP 状态异常', '请求超时', '网络请求失败', '响应过大', '响应不是有效 JSON', '业务码不是 2200', '响应字段缺失或类型异常', '签到状态未确认', '请求头格式无效', '缺少 phone、apptoken 或 device', '浏览时长无效或超过安全上限', '任务标识无效', '响应流异常']);
function explain(error) { return safeErrors.has(error.message) ? error.message : '步骤异常，已隐藏错误详情'; }
function parseHeaders(line) {
  let source;
  try { source = JSON.parse(line); } catch { throw failure('请求头格式无效'); }
  if (!source || typeof source !== 'object' || Array.isArray(source)) throw failure('请求头格式无效');
  const headers = Object.create(null);
  const blocked = new Set(['host', 'content-length', 'content-type', 'connection', 'transfer-encoding', 'accept-encoding', 'proxy-authorization', 'proxy-connection', 'upgrade', 'te', 'trailer', 'keep-alive']);
  for (const [key, value] of Object.entries(source)) {
    const k = key.toLowerCase();
    if (key.startsWith(':') || blocked.has(k)) continue;
    if (!/^[!#$%&'*+.^_`|~0-9a-z-]+$/.test(k) || typeof value !== 'string' || !value.trim() || /[\r\n\0]/.test(value)) throw failure('请求头格式无效');
    headers[k] = value;
  }
  if (!['phone', 'apptoken', 'device'].every(k => headers[k])) throw failure('缺少 phone、apptoken 或 device');
  return headers;
}
function requestApi(endpoint, body, headers) {
  if (dry) return Promise.reject(failure('离线模式禁止网络'));
  // 固定来源，禁止重定向、远程代码及接口地址覆盖，凭据只交给同程业务域名。
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body);
    let settled = false;
    let timer;
    const done = (error, value) => {
      if (settled) return;
      settled = true; clearTimeout(timer);
      error ? reject(error) : resolve(value);
    };
    const req = https.request({ hostname: 'app.17u.cn', port: 443, path: '/welfarecenter' + endpoint, method: 'POST', headers: { ...headers, 'content-type': 'application/json', 'accept-encoding': 'identity', 'content-length': Buffer.byteLength(payload) } }, res => {
      if (res.statusCode !== 200) { done(failure('HTTP 状态异常')); res.destroy(); return; }
      let size = 0;
      const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1048576) { done(failure('响应过大')); res.destroy(); req.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => done(failure('响应流异常')));
      res.on('aborted', () => done(failure('响应流异常')));
      res.on('end', () => {
        try { done(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch { done(failure('响应不是有效 JSON')); }
      });
    });
    timer = setTimeout(() => { done(failure('请求超时')); req.destroy(); }, 15000);
    req.on('error', () => done(failure('网络请求失败')));
    req.end(payload);
  });
}
function business(response) {
  if (!response || response.code !== 2200) throw failure('业务码不是 2200');
  return response.data;
}
function snapshot(data) {
  if (!data || ![true, false, 0, 1].includes(data.todaySign)) throw failure('响应字段缺失或类型异常');
  return data;
}
function isSigned(data) { return data.todaySign === true || data.todaySign === 1; }
function number(value) { return typeof value === 'number' && Number.isFinite(value) && value >= 0; }
function identity(data, headers) {
  // 只显示官方明确命名的公开身份字段，绝不把 phone 或会话字段作为账号名称。
  for (const field of ['nickname', 'nickName', 'username', 'displayName', 'publicUid']) {
    const value = data[field];
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const text = String(value);
    if (!text || /[\r\n\x00-\x1f]/.test(text) || /(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text)) continue;
    if (Object.entries(headers).some(([k, v]) => /phone|token|cookie|session|device|authorization/i.test(k) && (text.includes(v) || v.includes(text)))) continue;
    log(`官方账号身份（${field}）：${text}`);
    return;
  }
}
async function step(account, title, action) {
  const t = Date.now();
  const n = ++account.total;
  log(`账号 ${account.index} · 阶段 ${n}：${title}`);
  try {
    const result = await action();
    const status = result && result.stepStatus || 'success';
    account[status]++;
    log(`账号 ${account.index} · 阶段 ${n} ${status === 'skipped' ? '⏭️ 跳过' : status === 'alreadyComplete' ? '☑️ 已完成' : '✅ 成功'} · 耗时 ${Date.now() - t}ms`);
    return { ok: true, value: result };
  } catch (error) {
    account.failed++;
    log(`账号 ${account.index} · 阶段 ${n} ❌ ${explain(error)} · 耗时 ${Date.now() - t}ms`);
    return { ok: false };
  }
}
function dateInChina() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const get = k => parts.find(p => p.type === k).value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}
async function runAccount(line, index) {
  const a = { index, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, durationMs: 0 };
  accounts.push(a);
  const start = Date.now();
  let headers;
  const config = await step(a, '检查账号参数', async () => { headers = parseHeaders(line); });
  if (!config.ok) { configError = true; }
  else {
    let api;
    if (dry) {
      // 本地固定响应仅用于预演；不读取或伪称真实业务状态。
      let signed = false;
      api = async endpoint => {
        log(`离线预演：POST ${endpoint}（不发送请求）`);
        if (endpoint === '/index/signIndex') return { todaySign: signed, cycleSighNum: 1, mileageBalance: { mileage: 10, todayMileage: 1 } };
        if (endpoint === '/index/sign') { signed = true; return {}; }
        if (endpoint.startsWith('/task/taskList')) return [{ state: 1, browserTime: 1, taskCode: 'dry-run-task' }];
        if (endpoint === '/task/start') return 'dry-run-id';
        return {};
      };
    } else api = async (endpoint, body = {}) => business(await requestApi(endpoint, body, headers));
    const initial = await step(a, '查询签到状态与里程', async () => {
      const data = snapshot(await api('/index/signIndex'));
      identity(data, headers);
      log(`今日${isSigned(data) ? '已' : '未'}签到；当前里程：${number(data.mileageBalance?.mileage) ? data.mileageBalance.mileage : '未返回'}`);
      return data;
    });
    if (initial.ok) {
      await step(a, '每日签到', async () => {
        if (isSigned(initial.value)) return { stepStatus: 'alreadyComplete' };
        await api('/index/sign', { type: 1, day: dateInChina() });
        if (!isSigned(snapshot(await api('/index/signIndex')))) throw failure('签到状态未确认');
      });
      const list = await step(a, '获取浏览任务列表', async () => {
        const data = await api('/task/taskList?version=11.0.7');
        if (!Array.isArray(data)) throw failure('响应字段缺失或类型异常');
        log(`返回 ${data.length} 项任务（不输出原始标题或任务标识）`);
        return data;
      });
      if (list.ok) {
        if (!tasksEnabled) await step(a, '浏览与领奖：开关未开启', async () => ({ stepStatus: 'skipped' }));
        else {
          for (let i = 0; i < list.value.length; i++) {
            const task = list.value[i];
            await step(a, `浏览任务 ${i + 1} 与领奖`, async () => {
              if (!task || typeof task !== 'object') throw failure('响应字段缺失或类型异常');
              if (task.state !== 1 || task.browserTime === 0) return { stepStatus: 'skipped' };
              if (!Number.isInteger(task.browserTime) || task.browserTime < 1 || task.browserTime > 300) throw failure('浏览时长无效或超过安全上限');
              if (!['string', 'number'].includes(typeof task.taskCode) || !String(task.taskCode).trim()) throw failure('任务标识无效');
              const id = await api('/task/start', { taskCode: task.taskCode });
              if (!['string', 'number'].includes(typeof id) || !String(id).trim()) throw failure('任务标识无效');
              log(`浏览任务 ${i + 1}：启动业务码确认；等待 ${task.browserTime} 秒${dry ? '（预演跳过等待）' : ''}`);
              if (!dry) await wait(task.browserTime * 1000);
              for (let attempt = 0; attempt < 3; attempt++) {
                try { await api('/task/finish', { id }); break; }
                catch (error) {
                  if (attempt === 2) throw error;
                  log(`浏览任务 ${i + 1}：完成步骤未确认；准备第 ${attempt + 2} 次尝试`);
                  if (!dry) await wait(2000 * (attempt + 1));
                }
              }
              log(`浏览任务 ${i + 1}：完成业务码确认`);
              await api('/task/receive', { id });
              log(`浏览任务 ${i + 1}：领取奖励业务码确认`);
            });
          }
        }
      }
      await step(a, '复核签到与里程汇总', async () => {
        const data = snapshot(await api('/index/signIndex'));
        if (!isSigned(data)) throw failure('签到状态未确认');
        const balance = data.mileageBalance;
        if (!balance || !number(balance.mileage) || !number(balance.todayMileage) || !number(data.cycleSighNum)) throw failure('响应字段缺失或类型异常');
        log(`本月签到 ${data.cycleSighNum} 天；今日里程 ${balance.todayMileage}；当前里程 ${balance.mileage}`);
      });
    }
  }
  a.durationMs = Date.now() - start;
  a.status = a.failed ? 'failure' : dry ? 'dry-run' : 'success';
  log(`账号 ${index} 统计：总任务 ${a.total}，成功 ${a.success}，已完成 ${a.alreadyComplete}，跳过 ${a.skipped}，失败 ${a.failed}，耗时 ${a.durationMs}ms；状态 ${a.status}`);
}
function notificationSelected() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (/^(0|false|no|off)$/.test(mode)) return false;
  if (/^(1|true|yes|on)$/.test(mode)) return true;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (selection === undefined) return false; // 策略为 listed-only，本任务无预设入选名单。
  const scriptPath = __filename.replace(/\\/g, '/');
  const names = [CATALOG, scriptPath, path.basename(__filename), 'tongcheng-trip.js', 'checkin/tongcheng-trip.js', 'scripts/tongcheng-trip.js'];
  return selection.split(/[,;\s]+/).filter(Boolean).some(pattern => {
    const regex = new RegExp('^' + pattern.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(name => regex.test(name) || scriptPath.endsWith('/' + pattern));
  });
}
async function notify(body) {
  if (!notificationSelected()) { log('通知：未入选或已关闭'); return 'disabled'; }
  if (dry) { log('通知：离线预演，摘要已生成，不调用通知网络'); return 'dry-run'; }
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = candidates.find(p => fs.existsSync(p));
  if (!file) { log('⚠️ 通知组件不可用，保留业务退出码'); return 'unavailable'; }
  // 子进程隔离通知模块的输出和异常；硬超时，不把账号凭据传给通知进程。
  return new Promise(resolve => {
    const env = { ...process.env };
    delete env.TONGCHENG_TRIP_ACCOUNTS; delete env.tongcheng_trip_signheader;
    const child = spawn(process.execPath, ['-e', `let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',async()=>{try{const v=JSON.parse(s);const n=require(v.file);if(typeof n.sendNotify!=='function')throw Error();await n.sendNotify(v.title,v.body);process.exit(0)}catch{process.exit(1)}});`], { env, stdio: ['pipe', 'ignore', 'ignore'] });
    let settled = false;
    const done = state => { if (settled) return; settled = true; clearTimeout(timer); log(`通知：${state === 'sent' ? '已发送' : '发送失败，保留业务退出码'}`); resolve(state); };
    const timer = setTimeout(() => { child.kill('SIGKILL'); done('failed'); }, 20000);
    child.on('error', () => done('failed'));
    child.on('exit', code => done(code === 0 ? 'sent' : 'failed'));
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify({ file, title: TITLE, body }));
  });
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '离线预演' : '正式执行'}；浏览任务：${tasksEnabled ? '开启' : '关闭'}`);
  const raw = process.env.TONGCHENG_TRIP_ACCOUNTS !== undefined ? process.env.TONGCHENG_TRIP_ACCOUNTS : process.env.tongcheng_trip_signheader || '';
  const lines = raw.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  log(`账号数：${lines.length}`);
  if (!lines.length) { configError = true; log('❌ 配置错误：请设置 TONGCHENG_TRIP_ACCOUNTS，每行一个请求头 JSON'); }
  for (let i = 0; i < lines.length; i++) await runAccount(lines[i], i + 1);
}
async function finish() {
  const failed = accounts.filter(a => a.failed).length;
  const success = accounts.length - failed;
  const exitCode = configError || failed ? 1 : 0;
  const status = configError ? 'configuration-error' : failed ? success ? 'partial-failure' : 'failure' : dry ? 'dry-run' : 'success';
  const steps = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  for (const a of accounts) for (const k of Object.keys(steps)) steps[k] += a[k];
  const body = `状态：${status}；模式：${dry ? '离线预演（非真实业务成功）' : '正式执行'}；账号总数 ${accounts.length}，成功 ${success}，失败 ${failed}；子任务总数 ${steps.total}，成功 ${steps.success}，已完成 ${steps.alreadyComplete}，跳过 ${steps.skipped}，失败 ${steps.failed}`;
  log('----------------------------------------');
  log(body);
  let notification;
  try { notification = await notify(body); } catch { notification = 'failed'; log('⚠️ 通知异常，保留业务退出码'); }
  const finishedAt = new Date().toISOString();
  log(`完成时间：${finishedAt}；总耗时 ${Date.now() - started}ms；通知 ${notification}；最终状态 ${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, mode: dry ? 'dry-run' : 'live', status, accountCount: accounts.length, success, failed, configError, steps, accounts, notification, startedAt: new Date(started).toISOString(), finishedAt, durationMs: Date.now() - started, exitCode }));
  process.exitCode = exitCode;
}
main().catch(() => { configError = true; log('❌ 执行异常，详情已隐藏'); }).then(finish);
