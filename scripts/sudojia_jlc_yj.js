// name: 嘉立创硬件开源平台
// cron: 44 5 * * *
/**
 * name: 嘉立创硬件开源平台
 * cron: 44 5 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 基于 sudojia/AutoTaskScript src/web/sudojia_jlc_yj.js
 * 原作者 Telegram@sudojia；https://blog.imzjw.cn；2025/01/02
 * 登录 https://oshwhub.com/sign_in，在浏览器开发者工具网络面板中，
 * 从 oshwhub.com 已登录请求复制完整 Cookie 到 JLC_COOKIE，每个非空行一个账号。
 * 不以 & 或 @ 分隔账号。JLC_YJ_DRY_RUN=1 完全离线预演。
 * QINGLONG_NOTIFY 默认开启；0/false/no/off 关闭；QINGLONG_NOTIFY_DIR 可指定通知模块目录。
 * 默认 JLC_TASKS=oshwhub，保留开源平台身份、签到、积分和 44 5 * * * 调度。
 * JLC_TASKS=mapp：下单助手，原调度 30 6 * * *；all：依次执行两套流程。
 * 可在青龙为同一文件设置两条任务，分别注入上述开关，保留各自调度。
 * JLC_TOKEN：登录 https://m.jlc.com/mapp/ 或嘉立创下单助手小程序，
 * 从 m.jlc.com 已登录请求头获取 x-jlc-accesstoken 与 secretkey，
 * 合并为 令牌#密钥；只在第一个 # 切分，每个非空行一个账号，不以 & 或 @ 分隔。
 * JLC_CLAIM_REWARD=1 显式授权领取待选奖励；默认关闭，不擅自选择奖励类型。
 * 使用上游 receiveVoucher 原接口及默认语义，不猜测新的奖励类型参数。
 * 待选奖励未授权时报告未完成并非零退出；最多补签一次，避免递归重复领取。
 * JLC_YJ_DRY_RUN=1 或 JLC_DRY_RUN=1 完全离线预演（含模拟通知）。
 * 合并来源：xz0609/oshwhub-checkin-ql oshwhub-checkin-ql.py（原许可 MIT）。
 * 原脚本 cron: 10 8 * * *；如需保留原签到时点，可为同一文件设该调度。
 * OSHW_COOKIE 为 JLC_COOKIE 的兼容别名，二者同时存在时优先 JLC_COOKIE。
 * Cookie 获取：登录 oshwhub.com，F12 → Network，刷新 sign_in 页面，
 * 找到 getSignInProfile，复制请求头完整 Cookie；每行一个账号，勿复制响应。
 * 签到前后查询 getSignInProfile，确认今日状态并展示积分增量、周/月统计。
 * RANDOM_SIGNIN=true 可启用随机延迟；保持维护版默认无延迟。
 * MAX_RANDOM_DELAY 默认 1800 秒，仅在启用延迟时生效，上限 1800。
 * 只读查询遇到网络错误最多重试三次；不自动重试签到/领取等写入。
 * 不沿用 X_FORWARDED_FOR 伪装来源 IP，也不从 Cookie 提取身份用于日志。
 * OSHW_DRY_RUN=1 为兼容离线开关，离线不等待随机延迟。
 * 不更新账号资料，不关注、不发帖、不评论，不访问文本提供方。
 * 合并来源：sudojia/AutoTaskScript src/web/sudojia_jlc.js
 * 原作者 Telegram@sudojia；https://blog.imzjw.cn；2024/08/30
 * 官网：https://m.jlc.com/mapp/；小程序：嘉立创下单助手
 * 机械行业可以跑跑，基本兑换的实物都是有关机械的
 * 许可：GPL-3.0（保留上述两个来源的版权与归属）。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { fork } = require('node:child_process');
const { randomInt } = require('node:crypto');
function isDry() { return ['JLC_YJ_DRY_RUN', 'JLC_DRY_RUN', 'OSHW_DRY_RUN'].some(name => process.env[name] === '1'); }

// 通知单独进程运行，防止通知模块输出敏感内容、挂起或改变业务退出码。
if (process.argv[2] === '--notification-worker') {
  process.once('message', async ({ modulePath, title, body }) => {
    try {
      const mod = require(modulePath);
      if (typeof mod.sendNotify !== 'function') throw new Error();
      await mod.sendNotify(title, body);
      process.exit(0);
    } catch { process.exit(1); }
  });
} else {
  // 等待所有接口常量初始化后再启动，支持直接选择下单助手。
  Promise.resolve().then(main).catch(() => { process.exitCode = 1; });
}

function stamp() { return new Date().toTimeString().slice(0, 8); }
function log(text) { console.log(`[${stamp()}] ${text}`); }
function request(cookie, method, endpoint, body, mappHeaders) {
  if (isDry()) throw new Error('离线模式禁止网络请求');
  return new Promise((resolve, reject) => {
    const payload = body === undefined ? undefined : JSON.stringify(body);
    const headers = mappHeaders || { Cookie: cookie, Accept: 'application/json', 'User-Agent': 'Qinglong-OSHWHub/1.0', Referer: 'https://oshwhub.com/sign_in', 'Accept-Language': 'zh-CN,zh;q=0.9' };
    if (payload) { headers['Content-Type'] = 'application/json'; headers['Content-Length'] = Buffer.byteLength(payload); }
    let settled = false;
    let timer;
    const finish = (err, data) => {
      if (settled) return;
      settled = true; clearTimeout(timer);
      err ? reject(new Error(err)) : resolve(data);
    };
    const req = https.request({ hostname: mappHeaders ? 'm.jlc.com' : 'oshwhub.com', path: endpoint, method, headers }, res => {
      if (res.statusCode !== 200) { res.resume(); finish(`HTTP 状态异常（${res.statusCode}）`); return; }
      const chunks = []; let bytes = 0;
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 262144) { finish('响应超过大小限制'); res.destroy(); req.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => finish('响应读取失败'));
      res.on('aborted', () => finish('响应中断'));
      res.on('end', () => {
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || data.success !== true) return finish('官方未确认业务成功，请检查登录状态');
          finish(null, data);
        } catch { finish('响应格式无效'); }
      });
    });
    timer = setTimeout(() => { finish('请求超时'); req.destroy(); }, 15000);
    req.on('error', () => finish('网络请求失败'));
    req.end(payload);
  });
}
async function notify(body, dry) {
  if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  if (dry) return '离线模拟通知完成';
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  for (const dir of [...new Set(dirs)]) {
    const modulePath = path.resolve(dir, 'sendNotify.js');
    if (!fs.existsSync(modulePath)) continue;
    const ok = await new Promise(resolve => {
      let child; let timer; let done = false;
      const finish = value => { if (done) return; done = true; clearTimeout(timer); if (child) child.kill(); resolve(value); };
      try {
        const env = { ...process.env }; delete env.JLC_COOKIE; delete env.JLC_TOKEN; delete env.OSHW_COOKIE;
        child = fork(__filename, ['--notification-worker'], { silent: true, env });
        child.stdout.resume(); child.stderr.resume();
        child.on('error', () => finish(false));
        child.on('exit', code => finish(code === 0));
        timer = setTimeout(() => finish(false), 15000);
        child.send({ modulePath, title: '嘉立创硬件开源平台', body }, err => { if (err) finish(false); });
      } catch { finish(false); }
    });
    if (ok) return '发送成功';
  }
  return '通知不可用或发送失败（保留业务退出码）';
}
function lines(value) { return (value || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean); }
function numeric(value) { return (typeof value === 'number' && Number.isFinite(value)) || (typeof value === 'string' && /^\d+(\.\d+)?$/.test(value)); }
function credential(account) {
  const value = account.value;
  if (/[\x00-\x1f\x7f]/.test(value)) throw new Error('凭据格式无效');
  if (account.type === 'oshwhub') {
    if (!value.includes('=')) throw new Error('Cookie 格式无效');
    return;
  }
  const delimiter = value.indexOf('#');
  if (delimiter <= 0 || delimiter === value.length - 1) throw new Error('JLC_TOKEN 格式无效，应为令牌#密钥');
  account.headers = {
    'x-jlc-accesstoken': value.slice(0, delimiter), secretkey: value.slice(delimiter + 1),
    'user-agent': 'Mozilla/5.0 Qinglong-JLC/1.0', 'x-jlc-clienttype': 'WEB',
    accept: 'application/json, text/plain, */*', Referer: 'https://m.jlc.com/mapp/pages/my/index'
  };
}
function api(account, endpoint) { return request(undefined, 'GET', endpoint, undefined, account.headers); }
const SIGN_CONFIG = '/api/activity/sign/getCurrentUserSignInConfig';
const SIGN = '/api/activity/sign/signIn?source=4';
const REWARD = '/api/activity/sign/receiveVoucher';
function signed(data) {
  if (!data.data || typeof data.data.haveSignIn !== 'boolean') throw new Error('签到状态响应字段无效');
  return data.data.haveSignIn;
}
function gain(data) {
  if (!data.data || typeof data.data !== 'object') throw new Error('签到响应字段无效');
  // 上游以 gainNum 缺失或为零表示待选奖励，不猜测奖励类型或附加参数。
  if (data.data.gainNum === undefined || data.data.gainNum === null || data.data.gainNum === 0 || data.data.gainNum === '0') return false;
  if (!numeric(data.data.gainNum)) throw new Error('签到奖励响应字段无效');
  return true;
}
// 只读查询可重试；写入请求始终仅执行一次，避免未知响应引起重复副作用。
async function readOsh(account, endpoint) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    try { return await request(account.value, 'GET', endpoint); }
    catch (err) {
      if (attempt === 3 || !['网络请求失败', '请求超时', '响应中断', '响应读取失败'].includes(err.message)) throw err;
      log(`开源平台只读查询第 ${attempt}/3 次失败，进行有界重试（不输出响应）`);
    }
  }
}
async function profile(account) {
  const data = await readOsh(account, `/api/users/getSignInProfile?_t=${Date.now()}`);
  const result = data.result;
  if (!result || typeof result.isTodaySignIn !== 'boolean') throw new Error('签到状态响应字段无效');
  if (result.total_point !== undefined && !numeric(result.total_point)) throw new Error('积分响应字段无效');
  return result;
}
function profileStats(before, after) {
  const details = [];
  if (numeric(after.total_point)) details.push(`当前总积分：${after.total_point}`);
  if (numeric(before.total_point) && numeric(after.total_point)) {
    const delta = Number(after.total_point) - Number(before.total_point);
    details.push(`本次积分变化：${delta}`);
  }
  if (numeric(after.week_signIn_days)) details.push(`本周签到 ${after.week_signIn_days} 天`);
  if (numeric(after.month_signIn_days)) details.push(`本月连续签到 ${after.month_signIn_days} 天`);
  return details.join('；');
}
async function oshStage(account, j, dry) {
  if (j > 0 && !account.identified) return { kind: 'skipped', text: '身份查询未成功，跳过' };
  if (dry) {
    if (j === 0) account.identified = true;
    return { kind: 'success', text: `离线预演：${j === 1 ? 'GET getSignInProfile → 未签时 POST /api/users/signIn，正文仅含 _t → GET getSignInProfile 复查；统计积分变化及周/月签到；随机延迟不等待' : 'GET /api/users'}；未发起请求` };
  }
  if (j === 1) {
    const before = await profile(account);
    if (before.isTodaySignIn) return { kind: 'alreadyComplete', text: `今日已签到，不重复写入；${profileStats(before, before)}` };
    if ((process.env.RANDOM_SIGNIN || 'false').toLowerCase() === 'true') {
      const maximum = Number(process.env.MAX_RANDOM_DELAY || '1800');
      const delay = randomInt(maximum + 1);
      log(`签到前随机延迟 ${delay} 秒；阶段计时包含等待`);
      await new Promise(resolve => setTimeout(resolve, delay * 1000));
      // 延迟期间另一任务可能已经签到，写入前再次查询。
      const latest = await profile(account);
      if (latest.isTodaySignIn) return { kind: 'alreadyComplete', text: `等待后确认今日已签到，不重复写入；${profileStats(before, latest)}` };
    }
    await request(account.value, 'POST', '/api/users/signIn', { _t: Date.now() });
    const after = await profile(account);
    if (!after.isTodaySignIn) throw new Error('签到复查未确认今日已签到');
    return { kind: 'success', text: `签到成功（官方 success=true 且复查今日已签到）；${profileStats(before, after)}` };
  }
  const data = await readOsh(account, '/api/users');
  if (j === 0) {
    if (!data.result || typeof data.result.nickname !== 'string' || !data.result.nickname.trim()) throw new Error('身份响应缺少昵称');
    account.identified = true;
    return { kind: 'success', text: `昵称：${JSON.stringify(data.result.nickname)}` };
  }
  const points = data.result && data.result.points;
  if (!numeric(points)) throw new Error('积分响应字段无效');
  return { kind: 'success', text: `当前积分：${points}` };
}
async function mappStage(account, j, dry, claim) {
  if (j > 0 && !account.identified) return { kind: 'skipped', text: '身份查询未成功，跳过' };
  if (dry) {
    if (j === 0) account.identified = true;
    const routes = ['/api/appPlatform/center/setting/selectPersonalInfo', SIGN_CONFIG, SIGN, REWARD, SIGN_CONFIG, '/api/activity/front/getCustomerIntegral'];
    return { kind: 'success', text: `离线预演：GET ${routes[j]}；未发起请求${j === 3 ? (claim ? '；奖励领取已授权，正式运行仅在待选时领取' : '；奖励领取默认关闭，待选时需显式授权') : ''}` };
  }
  if (j === 0) {
    const data = await api(account, '/api/appPlatform/center/setting/selectPersonalInfo');
    const identity = data.data && data.data.customerCode;
    if (!((typeof identity === 'string' && identity.trim()) || (typeof identity === 'number' && Number.isFinite(identity)))) throw new Error('身份响应缺少公开账号标识');
    account.identified = true;
    return { kind: 'success', text: `昵称：${identity}` };
  }
  if (j === 1) {
    account.signed = signed(await api(account, SIGN_CONFIG));
    account.checked = true;
    return { kind: account.signed ? 'alreadyComplete' : 'success', text: account.signed ? '今日已签到' : '今日尚未签到' };
  }
  if (j === 2) {
    if (!account.checked) return { kind: 'skipped', text: '签到状态未确认，跳过写入' };
    if (account.signed) return { kind: 'alreadyComplete', text: '今日已签到，不重复写入' };
    const data = await api(account, SIGN);
    account.pending = !gain(data);
    return { kind: 'success', text: account.pending ? '官方确认签到请求成功，有待选奖励；等待领取与复查' : `签到成功，金豆+${data.data.gainNum}` };
  }
  if (j === 3) {
    if (!account.pending) return { kind: 'skipped', optional: true, text: '未发现待选奖励，不调用领取接口' };
    if (!claim) throw new Error('待选奖励未领取；请确认默认奖励语义后设置 JLC_CLAIM_REWARD=1');
    await api(account, REWARD);
    log('待选奖励领取成功（官方 success=true）；进行一次有界补签');
    // 原来源领取后重新签到；最多一次，不递归、不重复领取。
    const data = await api(account, SIGN);
    if (!gain(data)) throw new Error('补签后仍有待选奖励，停止重试');
    return { kind: 'success', text: `领取成功，补签金豆+${data.data.gainNum}` };
  }
  if (j === 4) {
    if (!signed(await api(account, SIGN_CONFIG))) throw new Error('签到复查未确认今日已签到');
    return { kind: 'success', text: '签到复查成功：今日已签到' };
  }
  const data = await api(account, '/api/activity/front/getCustomerIntegral');
  const points = data.data && data.data.integralVoucher;
  if (!numeric(points)) throw new Error('金豆余额响应字段无效');
  return { kind: 'success', text: `当前金豆：${points}` };
}
async function main() {
  const start = Date.now();
  const dry = isDry();
  const selection = process.env.JLC_TASKS || 'oshwhub';
  const claimValue = process.env.JLC_CLAIM_REWARD || '0';
  const claim = claimValue === '1';
  const accounts = [];
  let configurationError = false;
  const errors = [];
  const randomValue = (process.env.RANDOM_SIGNIN || 'false').toLowerCase();
  const delayValue = process.env.MAX_RANDOM_DELAY || '1800';
  const usesOsh = selection === 'oshwhub' || selection === 'all';
  const delayInvalid = usesOsh && randomValue === 'true' && (!/^\d+$/.test(delayValue) || Number(delayValue) > 1800);
  const randomInvalid = usesOsh && !['true', 'false'].includes(randomValue);
  if (randomInvalid) errors.push('RANDOM_SIGNIN 仅支持 true 或 false');
  if (delayInvalid) errors.push('MAX_RANDOM_DELAY 必须为 0 至 1800 的整数秒');
  if (!['oshwhub', 'mapp', 'all'].includes(selection)) errors.push('JLC_TASKS 仅支持 oshwhub、mapp、all');
  if (!['0', '1'].includes(claimValue)) errors.push('JLC_CLAIM_REWARD 仅支持 0 或 1');
  for (const [type, name] of [['oshwhub', 'JLC_COOKIE'], ['mapp', 'JLC_TOKEN']]) {
    if (selection !== type && selection !== 'all') continue;
    const raw = type === 'oshwhub' ? (process.env.JLC_COOKIE || process.env.OSHW_COOKIE) : process.env[name];
    const values = lines(raw).filter(value => type !== 'oshwhub' || !value.startsWith('#'));
    if (!values.length) errors.push(`${name} 必须包含至少一个账号凭据`);
    for (const value of values) accounts.push({ type, value });
  }
  configurationError = errors.length > 0;
  const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  const results = [];
  log('========== 嘉立创硬件开源平台 ==========');
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry ? '完全离线预演' : '正式执行'}；账号数：${accounts.length}`);
  for (const error of errors) log(`❌ 配置错误：${error}`);
  // 无效开关阻止写入；一组缺失凭据不阻塞另一组有效账号。
  const invalidSwitch = randomInvalid || delayInvalid || !['oshwhub', 'mapp', 'all'].includes(selection) || !['0', '1'].includes(claimValue);
  for (let i = 0; i < accounts.length; i++) {
    const account = accounts[i]; const accountStart = Date.now();
    const stages = account.type === 'oshwhub' ? ['查询账号身份', '每日签到', '查询积分'] : ['查询账号身份', '查询签到状态', '每日签到', '待选奖励领取', '签到复查', '查询金豆余额'];
    const stats = { total: stages.length, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let blockingSkip = false;
    log(`----- 账号 ${i + 1}（${account.type === 'oshwhub' ? '硬件开源平台' : '下单助手'}） -----`);
    let valid = !invalidSwitch;
    try { credential(account); } catch { valid = false; }
    for (let j = 0; j < stages.length; j++) {
      const stageStart = Date.now();
      let outcome;
      try {
        if (!valid) throw new Error('凭据或任务开关格式无效');
        const result = account.type === 'oshwhub' ? await oshStage(account, j, dry) : await mappStage(account, j, dry, claim);
        stats[result.kind]++;
        if (result.kind === 'skipped' && !result.optional) blockingSkip = true;
        outcome = `${{ success: '✅', alreadyComplete: '☑️', skipped: '⏭️' }[result.kind]} ${result.text}`;
      } catch (err) {
        stats.failed++;
        // 仅输出固定内部错误；不输出官方 message、异常对象或响应。
        const safe = /^(HTTP 状态异常（\d+）|官方未确认业务成功，请检查登录状态|响应超过大小限制|响应读取失败|响应中断|响应格式无效|请求超时|网络请求失败|身份响应缺少昵称|身份响应缺少公开账号标识|积分响应字段无效|签到状态响应字段无效|签到响应字段无效|签到奖励响应字段无效|金豆余额响应字段无效|签到复查未确认今日已签到|补签后仍有待选奖励，停止重试|待选奖励未领取；请确认默认奖励语义后设置 JLC_CLAIM_REWARD=1|凭据或任务开关格式无效)$/;
        outcome = `❌ ${safe.test(err.message) ? err.message : '请求配置或执行失败'}`;
      }
      log(`账号 ${i + 1} 阶段 ${j + 1}/${stages.length} ${stages[j]}：${outcome}；耗时 ${Date.now() - stageStart}ms`);
    }
    const ok = stats.failed === 0 && !blockingSkip;
    results.push({ account: i + 1, workflow: account.type, ...stats, ok, durationMs: Date.now() - accountStart });
    for (const key of Object.keys(totals)) totals[key] += stats[key];
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}；成功 ${stats.success}；已完成 ${stats.alreadyComplete}；跳过 ${stats.skipped}；失败 ${stats.failed}；耗时 ${Date.now() - accountStart}ms`);
  }
  const successCount = results.filter(r => r.ok).length;
  const failureCount = accounts.length - successCount;
  const exitCode = configurationError || failureCount ? 1 : 0;
  const status = configurationError ? 'configuration-error' : failureCount ? (successCount ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `账号总数 ${accounts.length}，成功 ${successCount}，失败 ${failureCount}；状态 ${status}；子任务成功 ${totals.success}、失败 ${totals.failed}、跳过 ${totals.skipped}`;
  let notification;
  try { notification = await notify(body, dry); } catch { notification = '通知失败（保留业务退出码）'; }
  log('----------------------------------------');
  log(body);
  log(`子任务总数 ${totals.total}；已完成 ${totals.alreadyComplete}；通知状态：${notification}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now() - start}ms；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: '嘉立创硬件开源平台', mode: dry ? 'dry-run' : 'live', status, accounts: accounts.length, success: successCount, failed: failureCount, configurationError, tasks: totals, results, notification, durationMs: Date.now() - start, exitCode }));
  process.exitCode = exitCode;
}
