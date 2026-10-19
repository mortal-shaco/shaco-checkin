// name: Rousi 签到
// cron: 42 0 * * *
/*
 * name: Rousi 签到
 * cron: 37 0 * * *
 * 来源：chenggegedeid/rousi-checkin，rousi_checkin.js
 * 上游提交：627ec698dc9d35f69f44e479366a7c31dd46489c
 * 保留已发布维护任务的定时：每日 00:37。
 * 原始源码未含版权声明；保留上游归属，适用 MIT 许可。
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
 *
 * Node.js >= 16，无需第三方依赖。ROUSI_TOKEN 每个非空行一个账号，支持
 * 纯 Token 或 Bearer 前缀；ROUSI_COOKIE 每行一个完整 Cookie。
 * 登录 https://rousi.pro/，开发者工具→网络→站内 API 请求头，复制
 * Authorization 的 Bearer 后内容或 Cookie。请勿复制响应内容或公开凭据。
 * 兼容小写变量及 ROUSI_TOKEN_1..20、ROUSI_COOKIE_1..20（每项也按行读取）。
 * 不使用 & 分隔账号，Cookie 中的 & 保留为凭据内容。
 * ROUSI_DRY_RUN=1 完全断网预演，通知仅模拟；QINGLONG_NOTIFY=0 关闭通知。
 * QINGLONG_NOTIFY_SCRIPTS 可按目录、文件名、catalogId 或 * 筛选通知脚本。
 * QINGLONG_NOTIFY_DIR 可指定青龙通知脚本目录；通知失败不改变业务退出码。
 * 可选 PUSHPLUS_TOKEN（兼容 pushplus_token）、PUSHPLUS_TYPE，通过 HTTPS 推送。
 * 本脚本只执行普通签到，不发布内容、不消耗积分或修改账号配置。
 */
'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["3c5c6df4d8a81a7f", "scripts/rousi_checkin.js", "rousi_checkin.js", "rousi_checkin"];
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
const { spawn } = require('child_process');

const TITLE = 'Rousi 签到';
const BASE = 'https://rousi.pro';
const START = Date.now();
const DRY = /^(1|true|yes|on)$/i.test(process.env.ROUSI_DRY_RUN || '');
const CATALOG_IDS = ['89e5ca300227d2e7', '3c5c6df4d8a81a7f'];
const SCRIPT_SELECTORS = ['scripts/rousi_checkin.js', 'rousi_checkin.js', ...CATALOG_IDS];
const stamp = () => new Date().toLocaleTimeString('zh-CN', {
  timeZone: 'Asia/Shanghai',
  hour12: false
});
const log = text => console.log(`[${stamp()}] ${text}`);
const elapsed = start => ((Date.now() - start) / 1000).toFixed(2);
const lines = value => (value || '').split(/\r?\n/).map(value => value.trim()).filter(Boolean);
const accounts = [];

function addAuth(type, value) {
  for (let credential of lines(value)) {
    if (type === 'token') credential = credential.replace(/^Bearer\s+/i, '').trim();
    if (!credential) continue;
    if (!accounts.some(account => account.type === type && account.value === credential)) {
      accounts.push({ type, value: credential });
    }
  }
}

function readAuths() {
  addAuth('token', process.env.ROUSI_TOKEN || process.env.rousi_token);
  for (let index = 1; index <= 20; index++) {
    addAuth('token', process.env[`ROUSI_TOKEN_${index}`] || process.env[`rousi_token_${index}`]);
  }
  addAuth('cookie', process.env.ROUSI_COOKIE || process.env.rousi_cookie);
  for (let index = 1; index <= 20; index++) {
    addAuth('cookie', process.env[`ROUSI_COOKIE_${index}`] || process.env[`rousi_cookie_${index}`]);
  }
}

function number(value) {
  if ((typeof value !== 'number' && typeof value !== 'string') || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function metric(value, decimals = 2) {
  const parsed = number(value);
  return parsed === null ? '未提供' : parsed.toFixed(decimals);
}

function size(value) {
  let parsed = number(value);
  if (parsed === null || parsed < 0) return '未提供';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let index = 0;
  while (parsed >= 1024 && index < units.length - 1) {
    parsed /= 1024;
    index++;
  }
  return `${parsed.toFixed(2)} ${units[index]}`;
}

function isSafePublicText(value, maximum = 120) {
  if (typeof value !== 'string' && typeof value !== 'number') return false;
  const text = String(value);
  if (!text || text.length > maximum || /[\r\n\x00-\x1f]/.test(text)) return false;
  if (/(?:\+?86)?1[3-9]\d{9}/.test(text)) return false;
  return !accounts.some(account => account.value && text.includes(account.value));
}

function publicIdentity(data) {
  for (const field of ['nickname', 'username', 'display_name', 'displayName', 'uid']) {
    if (data && isSafePublicText(data[field])) return `${field}: ${String(data[field])}`;
  }
  return '';
}

function request(url, method = 'GET', headers = {}, data) {
  if (DRY) return Promise.reject(new Error('预演禁止网络请求'));
  return new Promise((resolve, reject) => {
    const body = data === undefined ? undefined : JSON.stringify(data);
    let settled = false;
    let timer;
    const finish = (handler, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      handler(value);
    };
    const req = https.request(url, {
      method,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(body ? { 'Content-Length': Buffer.byteLength(body) } : {}),
        ...headers
      }
    }, response => {
      let bytes = 0;
      const chunks = [];
      response.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 262144) {
          finish(reject, new Error('响应超过大小限制'));
          req.destroy();
          return;
        }
        chunks.push(chunk);
      });
      response.on('error', () => finish(reject, new Error('响应读取失败')));
      response.on('aborted', () => finish(reject, new Error('响应中断')));
      response.on('end', () => {
        if (settled) return;
        if (response.statusCode < 200 || response.statusCode >= 300) {
          finish(reject, new Error(`HTTP ${response.statusCode}`));
          return;
        }
        try {
          const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error();
          finish(resolve, parsed);
        } catch (_) {
          finish(reject, new Error('响应格式无效'));
        }
      });
    });
    timer = setTimeout(() => {
      finish(reject, new Error('请求超时'));
      req.destroy();
    }, 30000);
    req.on('error', () => finish(reject, new Error('网络请求失败或超时')));
    req.end(body);
  });
}

async function api(auth, endpoint, method = 'GET', body) {
  const headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    Origin: BASE,
    Referer: `${BASE}/`,
    ...(auth.type === 'token'
      ? { Authorization: `Bearer ${auth.value}` }
      : { Cookie: auth.value })
  };
  return request(BASE + endpoint, method, headers, body);
}

function checkedData(response) {
  if (response.code !== 0 || !response.data || typeof response.data !== 'object' || Array.isArray(response.data)) {
    throw new Error('接口未确认业务成功或数据格式已变化');
  }
  return response.data;
}

async function runAccount(auth, index) {
  const began = Date.now();
  const details = [];
  const stats = { total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let stage = 0;
  let stageStart;
  const begin = title => {
    stage++;
    stageStart = Date.now();
    log(`账号 ${index} · 阶段 ${stage}/3 ${title}`);
  };
  const report = text => {
    log(text);
    details.push(text);
  };
  const finish = (text, kind = 'success') => {
    stats[kind]++;
    log(`${text}（阶段耗时 ${elapsed(stageStart)} 秒）`);
  };

  log(`---------- 账号 ${index} ----------`);
  try {
    if (/[\r\n\x00-\x1f\x7f]/.test(auth.value) || (auth.type === 'token' && /[&\s]/.test(auth.value))) {
      throw new Error('凭据格式无效；Token 请按行分隔且不要使用 &');
    }

    begin('读取积分与签到状态');
    const init = DRY
      ? { balance: { karma: 0, credits: 0 }, attendance: { server_today: '2026-01-01', attended_dates: [], current_streak: 0 } }
      : checkedData(await api(auth, '/api/points/init'));
    if (!init.balance || typeof init.balance !== 'object' || Array.isArray(init.balance) ||
        !['karma', 'credits'].some(key => number(init.balance[key]) !== null)) {
      throw new Error('积分数据格式已变化');
    }
    const identity = publicIdentity(init) || publicIdentity(init.user) || publicIdentity(init.account);
    if (identity) log(`官方账号身份：${identity}`);
    const label = (value, fallback) => isSafePublicText(value, 40) ? value : fallback;
    const karmaName = label(init.config?.karma_name, '魔力值');
    const creditsName = label(init.config?.credits_name, 'PT币');
    report(`${karmaName}：${metric(init.balance.karma)}；${creditsName}：${metric(init.balance.credits)}`);
    const attendance = init.attendance || {};
    report(`连续签到：${metric(attendance.current_streak, 0)} 天；累计签到：${Array.isArray(attendance.attended_dates) ? attendance.attended_dates.length : '未提供'} 天`);
    finish(DRY ? '✅ 预演积分读取通过（模拟数据）' : '✅ 积分读取成功');

    begin('读取分享率与上传下载统计');
    try {
      const response = DRY
        ? { ratio: 0, bonus: 0, uploaded: 0, downloaded: 0 }
        : await api(auth, '/api/account/stats');
      if (response.code !== undefined && response.code !== 0) {
        throw new Error('账户统计接口未确认业务成功');
      }
      const accountStats = response.code === 0 && response.data ? response.data : response;
      if (!['ratio', 'bonus', 'uploaded', 'downloaded', 'upload', 'download', 'seeding', 'leeching', 'invites']
        .some(key => number(accountStats[key]) !== null)) {
        throw new Error('账户统计响应字段已变化');
      }
      const statsIdentity = publicIdentity(accountStats);
      if (statsIdentity && statsIdentity !== identity) log(`官方账号身份：${statsIdentity}`);
      report(`分享率：${metric(accountStats.ratio, 3)}；${karmaName}：${metric(accountStats.bonus ?? init.balance.karma)}；累计上传：${size(accountStats.uploaded)}；累计下载：${size(accountStats.downloaded)}`);
      finish(DRY ? '✅ 预演统计读取通过（模拟数据）' : '✅ 账户统计读取成功');
    } catch (_) {
      finish('❌ 账户统计读取失败；继续尝试签到，整体仍按失败退出', 'failed');
    }

    begin('普通签到');
    const today = attendance.server_today;
    if (!DRY && typeof today === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(today) &&
        Array.isArray(attendance.attended_dates) && attendance.attended_dates.includes(today)) {
      finish('☑️ 今日已签到，跳过重复签到', 'alreadyComplete');
    } else if (DRY) {
      finish('✅ DRY_RUN_OK：已预演普通签到 POST /api/points/attendance，未发送请求');
    } else {
      const result = await api(auth, '/api/points/attendance', 'POST', { mode: 'normal' });
      if (result.code !== 0) throw new Error('签到接口未确认业务成功');
      const data = result.data && typeof result.data === 'object' ? result.data : {};
      report(`本次奖励：${metric(data.bonus)} ${karmaName}；连续签到奖励：${metric(data.streak_bonus)} ${karmaName}；当前连续：${metric(data.current_streak, 0)} 天`);
      finish('✅ 签到成功');
    }
  } catch (error) {
    stats.failed++;
    stats.skipped = Math.max(0, stats.total - stats.success - stats.alreadyComplete - stats.failed);
    log(`❌ 账号 ${index} 失败：${error.message}（阶段耗时 ${elapsed(stageStart || began)} 秒）；其余阶段跳过`);
  }
  const ok = stats.failed === 0;
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${elapsed(began)} 秒`);
  return { account: index, ok, ...stats, details };
}

function globMatches(pattern, value) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
  return new RegExp(`^${escaped}$`).test(value);
}

function notificationEnabled() {
  const global = (process.env.QINGLONG_NOTIFY || 'auto').trim();
  if (/^(0|false|no|off)$/i.test(global)) return false;
  const configured = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (configured === undefined) return true;
  const selectors = configured.split(/[,;\s]+/).map(value => value.trim()).filter(Boolean);
  if (!selectors.length) return false;
  return selectors.some(selector => selector === '*' || SCRIPT_SELECTORS.some(value => globMatches(selector, value)));
}

function runNotifier(command, args) {
  return new Promise(resolve => {
    const child = spawn(command, args, { stdio: 'ignore' });
    let finished = false;
    const settle = value => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      resolve(value);
    };
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      settle(false);
    }, 15000);
    child.on('error', () => settle(false));
    child.on('close', code => settle(code === 0));
  });
}

async function helperNotify(file, body) {
  if (file.endsWith('.js')) {
    const program = [
      'const m=require(process.argv[1]);',
      'const f=typeof m==="function"?m:(m.sendNotify||m.default);',
      'if(typeof f!=="function")throw new Error("invalid notifier");',
      'Promise.resolve(f(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1));'
    ].join('');
    return runNotifier(process.execPath, ['-e', program, file, TITLE, body]);
  }
  return runNotifier('python3', [file, TITLE, body]);
}

async function moduleNotify(body) {
  const program = 'from notify import send; send(__import__("sys").argv[1], __import__("sys").argv[2])';
  return runNotifier('python3', ['-c', program, TITLE, body]);
}

async function notify(body) {
  if (!notificationEnabled()) {
    log('⏭️ 通知已由 QINGLONG_NOTIFY 或 QINGLONG_NOTIFY_SCRIPTS 关闭');
    return 'disabled';
  }
  if (DRY) {
    log('⏭️ 预演通知：已生成脱敏总结，禁止调用通知模块或网络');
    return 'dry-run';
  }

  const directory = process.env.QINGLONG_NOTIFY_DIR;
  const files = [
    directory && path.resolve(directory, 'notify.py'),
    directory && path.resolve(directory, 'sendNotify.js'),
    '/ql/data/scripts/notify.py',
    '/ql/data/scripts/sendNotify.js',
    '/ql/scripts/notify.py',
    '/ql/scripts/sendNotify.js'
  ].filter(Boolean);
  let state = await moduleNotify(body) ? 'sent' : 'unavailable';
  if (state !== 'sent') {
    for (const file of [...new Set(files)]) {
      if (!fs.existsSync(file)) continue;
      if (await helperNotify(file, body)) {
        state = 'sent';
        break;
      }
      state = 'failed';
    }
  }
  log(state === 'sent' ? '✅ 青龙通知已发送' : '⚠️ 青龙通知不可用或发送失败，保留业务退出码');

  const token = process.env.PUSHPLUS_TOKEN || process.env.pushplus_token;
  if (token) {
    try {
      const type = process.env.PUSHPLUS_TYPE || 'wechat';
      const result = await request('https://www.pushplus.plus/send', 'POST', {}, {
        token,
        title: TITLE,
        content: body,
        timestamp: Date.now(),
        type: ['pushplusvip', 'wxgo', 'qywxgo', 'email', 'feishu', 'dingtalk', 'bark'].includes(type) ? type : 'send'
      });
      log(result.code === 0 || result.code === 200
        ? '✅ PushPlus 通知发送成功'
        : '⚠️ PushPlus 通知业务失败');
    } catch (_) {
      log('⚠️ PushPlus 通知发送失败，保留业务退出码');
    }
  }
  return state;
}

async function main() {
  readAuths();
  log(`============ ${TITLE} ============`);
  log(`开始时间：${new Date(START).toISOString()}；模式：${DRY ? '断网预演' : '正式执行'}；账号数：${accounts.length}`);
  const results = [];
  if (!accounts.length) {
    log('❌ 配置错误：请设置 ROUSI_TOKEN（兼容 ROUSI_TOKEN_1 或 ROUSI_COOKIE）');
  }
  for (let index = 0; index < accounts.length; index++) {
    results.push(await runAccount(accounts[index], index + 1));
  }
  const succeeded = results.filter(result => result.ok).length;
  const failed = results.length - succeeded;
  const status = !accounts.length
    ? 'configuration-error'
    : failed
      ? (succeeded ? 'partial-failure' : 'failure')
      : (DRY ? 'dry-run' : 'success');
  const exitCode = !accounts.length || failed ? 1 : 0;
  const tasks = results.reduce((summary, result) => {
    for (const key of ['total', 'success', 'alreadyComplete', 'skipped', 'failed']) {
      summary[key] += result[key];
    }
    return summary;
  }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  const body = `模式：${DRY ? '断网预演' : '正式执行'}；状态：${status}；账号总数：${accounts.length}；成功：${succeeded}；失败：${failed}；子任务成功：${tasks.success}；已完成：${tasks.alreadyComplete}；失败：${tasks.failed}。${!accounts.length ? '缺少账号凭据。' : ''}\n` +
    results.map(result => `账号 ${result.account}：${result.ok ? '通过' : '失败'}\n${result.details.join('\n')}`).join('\n');
  let notification;
  try {
    notification = await notify(body);
  } catch (_) {
    notification = 'failed';
    log('⚠️ 通知异常，保留业务退出码');
  }

  console.log('----------------------------------------');
  log(`任务统计：账号 ${accounts.length}，成功 ${succeeded}，失败 ${failed}；子任务 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  const finishedAt = new Date().toISOString();
  log(`结束时间：${finishedAt}；总耗时：${elapsed(START)} 秒；通知状态：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({
    task: TITLE,
    mode: DRY ? 'dry-run' : 'live',
    status,
    accounts: accounts.length,
    succeeded,
    failed,
    tasks,
    results,
    notification,
    startedAt: new Date(START).toISOString(),
    finishedAt,
    exitCode
  }));
  process.exitCode = exitCode;
}

main().catch(async () => {
  const finishedAt = new Date().toISOString();
  let notification = 'failed';
  log('❌ 脚本发生未处理异常');
  try {
    notification = await notify('模式：正式执行；状态：failure；账号总数：未知；成功：0；失败：1。脚本发生未处理异常。');
  } catch (_) {
    log('⚠️ 通知异常，保留业务退出码');
  }
  console.log('----------------------------------------');
  log('任务统计：脚本在汇总前异常退出；业务退出码为 1');
  log(`结束时间：${finishedAt}；总耗时：${elapsed(START)} 秒；通知状态：${notification}；最终状态：failure`);
  console.log('TASK_SUMMARY=' + JSON.stringify({
    task: TITLE,
    mode: DRY ? 'dry-run' : 'live',
    status: 'failure',
    accounts: 0,
    succeeded: 0,
    failed: 1,
    tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 1 },
    results: [],
    notification,
    startedAt: new Date(START).toISOString(),
    finishedAt,
    exitCode: 1
  }));
  process.exitCode = 1;
});
