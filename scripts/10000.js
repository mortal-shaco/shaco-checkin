// name: 中国电信签到与金币查询
// cron: 10 10 * * *
// SPDX-License-Identifier: GPL-3.0-only
// 来源：chavyleung/scripts，10000/10000.js、10000/10000.cookie.js。
// 上游未提供定时表达式；此处建议每天 08:00 执行。
/*
 * 功能清点：主脚本逐手机号签到、识别已签到、可选查询金币及首页提示；
 * 关联脚本仅捕获请求头/请求体，不是独立定时业务。无已维护功能覆盖。
 * 保留 POST 地址、AES-128-ECB/PKCS7、data.code 与 resoultCode 判定。
 * TELECOM_ACCOUNTS：每个非空行 手机号 或 手机号|首页请求体JSON；只切第一个 |。
 * 手机号取自本人中国电信账号。可选请求体从本人授权调试工具捕获
 * https://wapside.189.cn:9001/api/home/homeInfo 的完整 JSON body，原样保存，
 * 绑定同一手机号。无需 Cookie/header；上游仅发送 JSON Content-Type。
 * 兼容环境变量 chavy_mobile_10000（改为每行一个号码）、chavy_signbody_10000
 * （仅绑定旧变量的首个账号）。不读取 BoxJs 私有文件；请手动迁移环境变量。
 * 不支持逗号、&、@ 分隔账号。TELECOM_DRY_RUN=1 完全离线（通知也仅预览）。
 * 真实运行会签到；可选首页查询不修改账户。不会发帖、评论、分享或花费金币。
 * QINGLONG_NOTIFY=1 启用，0 禁用，auto 仅通知选中脚本；选择列表可用逗号、
 * 分号或空白列出 catalog-id、脚本路径、文件名或文件名 glob，空值禁用所有。
 * 通知失败不改变业务退出码。无通知组件时脚本仍可独立执行。
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
    const identities = ["82197f801fb35ac3", "scripts/10000.js", "10000.js", "10000"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { fork } = require('child_process');
const TITLE = '中国电信签到与金币查询';
const DRY = process.env.TELECOM_DRY_RUN === '1';
const started = Date.now();
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${stamp()}] ${text}`);
const has = key => Object.prototype.hasOwnProperty.call(process.env, key);
const canonical = has('TELECOM_ACCOUNTS');
const lines = (canonical ? process.env.TELECOM_ACCOUNTS : process.env.chavy_mobile_10000 || '')
  .split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const secrets = [];
const accounts = lines.map((line, i) => {
  const at = line.indexOf('|');
  const phone = (at < 0 ? line : line.slice(0, at)).trim();
  const body = at < 0 ? (!canonical && i === 0 ? process.env.chavy_signbody_10000 || '' : '') : line.slice(at + 1).trim();
  secrets.push(phone, body);
  return { phone, body };
});
function safe(value) {
  let text = String(value ?? '');
  for (const secret of secrets.filter(Boolean).sort((a, b) => b.length - a.length)) text = text.split(secret).join('[已隐藏]');
  return text.replace(/(?:\+?86[- ]?)?1\d{10}/g, '[手机号已隐藏]')
    .replace(/(?:cookie|token|session|sign|deviceId|imei|imsi)\s*[=:：]\s*[^\s，；]+/gi, '[敏感字段已隐藏]')
    .replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
}
function encrypt(phone) {
  const cipher = crypto.createCipheriv('aes-128-ecb', Buffer.from('34d7cb0bcdf07523'), null);
  return Buffer.concat([cipher.update(JSON.stringify({ phone, date: Date.now(), signSource: 'smlprgrm' }), 'utf8'), cipher.final()]).toString('hex');
}
function post(endpoint, body) {
  if (DRY) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    let finished = false;
    const req = https.request({ hostname: 'wapside.189.cn', port: 9001, path: `/api/home/${endpoint}`,
      method: 'POST', headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Content-Length': Buffer.byteLength(body) } }, res => {
      let size = 0;
      const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) { fail('响应超过大小限制'); res.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => fail('响应读取失败'));
      res.on('aborted', () => fail('响应被中断'));
      res.on('end', () => {
        if (finished) return;
        if (res.statusCode < 200 || res.statusCode >= 300) return fail(`HTTP 状态异常 ${res.statusCode}`);
        try {
          const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!value || typeof value !== 'object' || Array.isArray(value)) return fail('响应格式错误');
          finished = true; clearTimeout(timer); resolve(value);
        } catch { fail('响应不是有效 JSON'); }
      });
    });
    const timer = setTimeout(() => fail('请求超时（15秒）'), 15000);
    function fail(message) {
      if (finished) return;
      finished = true; clearTimeout(timer); req.destroy(); reject(new Error(message));
    }
    req.on('error', () => fail('网络或 TLS 请求失败'));
    req.end(body);
  });
}
function validate(account) {
  if (!/^1\d{10}$/.test(account.phone)) throw new Error('手机号格式错误；每行一个账号，禁止逗号等账号分隔符');
  if (account.body) {
    let body;
    try { body = JSON.parse(account.body); } catch { throw new Error('首页请求体必须是完整 JSON 对象'); }
    if (!body || typeof body !== 'object' || Array.isArray(body) || Object.keys(body).length === 0) throw new Error('首页请求体必须是非空 JSON 对象');
    if (body.phone !== undefined && String(body.phone) !== account.phone) throw new Error('首页请求体与本行账号不匹配');
    if (body.encode !== undefined && typeof body.encode !== 'string') throw new Error('首页请求体 encode 格式错误');
  }
}
function glob(pattern, value) {
  const regex = pattern.split('*').map(x => x.split('?').map(y => y.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.')).join('.*');
  return new RegExp(`^${regex}$`).test(value);
}
function notificationSelected() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(mode)) return false;
  if (!['auto', '1', 'true', 'yes', 'on'].includes(mode)) return false;
  // listed-only：未提供选择列表时，auto 不扩大通知范围；显式启用可发送。
  if (!has('QINGLONG_NOTIFY_SCRIPTS')) return mode !== 'auto';
  const names = ['82197f801fb35ac3', '10000/10000.js', '10000.js', path.basename(__filename), __filename];
  return process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(p => names.some(n => glob(p, n)));
}
async function notify(body) {
  if (!notificationSelected()) return '已禁用或未选中';
  if (DRY) { log(`通知离线预览：${body}`); return '离线预览'; }
  const paths = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = paths.find(p => fs.existsSync(p));
  if (!file) { log('⚠️ 通知组件不可用，保留业务退出码'); return '组件不可用'; }
  // 隔离通知组件的日志、异常与退出行为，不将账号环境变量传入通知子进程。
  const env = { ...process.env };
  for (const key of ['TELECOM_ACCOUNTS', 'chavy_mobile_10000', 'chavy_signbody_10000']) delete env[key];
  return new Promise(resolve => {
    let child;
    let done = false;
    const finish = state => { if (done) return; done = true; clearTimeout(timer); if (child) child.kill(); resolve(state); };
    const timer = setTimeout(() => finish('通知超时'), 15000);
    try {
      child = fork(__filename, [], { env: { ...env, TELECOM_NOTIFY_CHILD: '1' }, stdio: ['ignore', 'ignore', 'ignore', 'ipc'] });
      child.on('message', result => finish(result === 'ok' ? '已发送' : '通知失败'));
      child.on('error', () => finish('通知启动失败'));
      child.on('exit', () => finish('通知组件退出'));
      child.send({ file, title: TITLE, body });
    } catch { finish('通知启动失败'); }
  });
}
function showIdentity(data, index) {
  const objects = [data, data.data, data.data?.userInfo];
  const seen = new Set();
  for (const obj of objects) {
    if (!obj || typeof obj !== 'object') continue;
    for (const key of ['nickname', 'nickName', 'username', 'displayName', 'uid']) {
      if (typeof obj[key] !== 'string' && typeof obj[key] !== 'number') continue;
      const text = safe(obj[key]);
      if (seen.has(text)) continue;
      seen.add(text); log(`账号 ${index} ${key}：${text}`);
    }
  }
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${DRY ? '离线预演' : '真实执行'}；账号数：${accounts.length}`);
  const results = [];
  let configError = accounts.length === 0;
  if (configError) log('❌ 配置错误：请设置 TELECOM_ACCOUNTS，每行一个本人账号');
  for (const [i, account] of accounts.entries()) {
    const begin = Date.now();
    const stats = { account: i + 1, total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    log(`账号 ${i + 1} 开始`);
    async function stage(number, name, action) {
      const time = Date.now();
      log(`账号 ${i + 1} [${number}/3] ${name}`);
      try {
        const result = await action();
        stats[result.status]++;
        log(`账号 ${i + 1} [${number}/3] ${result.status === 'skipped' ? '⏭️' : result.status === 'alreadyComplete' ? '☑️' : '✅'} ${safe(result.message)}；耗时 ${Date.now() - time}ms`);
        return true;
      } catch (e) {
        stats.failed++;
        log(`账号 ${i + 1} [${number}/3] ❌ ${safe(e.message)}；耗时 ${Date.now() - time}ms`);
        return false;
      }
    }
    const valid = await stage(1, '检查账号参数', async () => {
      try { validate(account); } catch (e) { configError = true; throw e; }
      return { status: 'success', message: '参数格式通过（不代表凭据有效）' };
    });
    await stage(2, '签到', async () => {
      if (!valid) return { status: 'skipped', message: '参数无效，跳过签到' };
      const body = JSON.stringify({ encode: encrypt(account.phone) });
      if (DRY) return { status: 'skipped', message: '离线检查加密请求构造通过，不发送请求' };
      const data = await post('sign', body);
      showIdentity(data, i + 1);
      if (data.data?.code === 1) return { status: 'success', message: '签到成功（data.code=1）' };
      if (data.data?.code === 0 && typeof data.data.msg === 'string' && /已签到/.test(data.data.msg)) return { status: 'alreadyComplete', message: '今日已签到' };
      throw new Error('签到业务未确认成功，请核对参数或接口状态');
    });
    await stage(3, '查询金币与首页提示', async () => {
      if (!valid || !account.body || DRY) return { status: 'skipped', message: !valid ? '参数无效' : DRY ? '离线预演，不查询首页' : '未配置本账号首页请求体' };
      const data = await post('homeInfo', account.body);
      const user = data.data?.userInfo;
      if (![0, '0'].includes(data.resoultCode) || !user || !/^[0-9]+(?:\.[0-9]+)?$/.test(String(user.totalCoin))) throw new Error('金币查询未确认成功或响应字段缺失');
      showIdentity(data, i + 1);
      return { status: 'success', message: `金币总数：${user.totalCoin}；首页提示：${safe(data.data?.tipInfo?.tipInfoLeft || '未返回')}` };
    });
    stats.durationMs = Date.now() - begin;
    stats.status = stats.failed ? 'failure' : DRY ? 'dry-run' : 'success';
    results.push(stats);
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${stats.durationMs}ms`);
  }
  const failed = results.filter(r => r.failed).length;
  const succeeded = results.length - failed;
  const status = configError ? 'configuration-error' : failed ? (succeeded ? 'partial-failure' : 'failure') : DRY ? 'dry-run' : 'success';
  const summary = { task: TITLE, mode: DRY ? 'dry-run' : 'live', status, accounts: accounts.length, succeeded, failed, results };
  process.exitCode = configError || failed ? 1 : 0;
  log('----------------------------------------');
  const body = `状态：${status}；账号总数 ${accounts.length}，成功 ${succeeded}，失败 ${failed}${DRY ? '（仅格式预演，未验证业务）' : ''}`;
  log(body);
  const totals = results.reduce((a, r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  log(`子任务统计：总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  summary.notification = await notify(body);
  summary.durationMs = Date.now() - started;
  log(`完成时间：${new Date().toISOString()}；总耗时 ${summary.durationMs}ms；通知：${summary.notification}；最终状态：${status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
}
if (process.env.TELECOM_NOTIFY_CHILD === '1' && process.send) {
  process.once('message', async ({ file, title, body }) => {
    try { const module = require(file); await module.sendNotify(title, body); process.send('ok'); }
    catch { process.send('failed'); }
  });
} else {
  main().catch(async () => {
    process.exitCode = 1;
    log('❌ 执行异常（详情已脱敏）');
    const notification = await notify(`状态：failure；账号总数 ${accounts.length}，成功 0，失败 ${accounts.length}`);
    log(`完成时间：${new Date().toISOString()}；最终状态：failure；通知：${notification}`);
    console.log(`TASK_SUMMARY=${JSON.stringify({ task: TITLE, status: 'failure', accounts: accounts.length, succeeded: 0, failed: accounts.length, notification })}`);
  });
}
