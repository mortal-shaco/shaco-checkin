// name: 智行火车每日签到与积分查询
// cron: 24 10 * * *
/*
 * name: 智行火车
 * cron: 0 8 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 原始来源：chavyleung/scripts，zxhc/zxhc.js、zxhc/zxhc.cookie.js。
 * 保留上游归属，维护版本按 GPL-3.0-only 分发。
 * Node.js >= 18，无第三方业务依赖。
 * ZXHC_ACCOUNTS：每个非空行一个 JSON 对象：{"headers":{...},"body":"原始请求体"}。
 * 在本人设备登录智行火车，使用本人信任的 HTTPS 调试工具，打开签到页并手动签到，
 * 捕获 m.suanya.cn/restapi/soa2/18903/attendanceDay 的请求头和完整请求体。
 * 将请求头对象与原始 body 合并为上述 JSON；不要分享抓包内容，不要复制响应到日志。
 * 兼容 senku_signheader_zxhc 与 senku_signbody_zxhc（逐行一一对应），不读取 box.dat。
 * ZXHC_DRY_RUN=1：只检查配置和阶段，不发网络请求，也不执行可能联网的通知助手。
 * 默认依次签到、查询积分和优惠券；不发帖、不消费，不重试签到，不自动改版本号。
 * 原文件未提供 cron，维护版采用每日 08:00，可在青龙任务中调整。
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
    const identities = ["38a2ed952649bfb6", "scripts/zxhc.js", "zxhc.js", "zxhc"];
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
const NAME = '智行火车';
const SIGN = 'https://m.suanya.cn/restapi/soa2/18903/attendanceDay';
const CREDIT = 'https://m.suanya.cn/restapi/soa2/17679/get2020ZtripIntergrationDailyAttendanceInfo';
const yes = v => /^(1|true|yes|on)$/i.test(v || '');
const no = v => /^(0|false|no|off)$/i.test(v || '');
const lines = v => (v || '').split(/\r?\n/).filter(v => v.trim());
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const started = Date.now();
const dry = yes(process.env.ZXHC_DRY_RUN);
const stamp = () => new Date().toTimeString().slice(0, 8);
const log = text => console.log(`[${stamp()}] ${text}`);
const elapsed = t => Number(((Date.now() - t) / 1000).toFixed(3));
const secrets = new Set();
function remember(value) {
  if (typeof value === 'string' && value.length >= 4) secrets.add(value);
  else if (object(value) || Array.isArray(value)) Object.values(value).forEach(remember);
}
function rememberCredentials(value) {
  if (!object(value) && !Array.isArray(value)) return;
  for (const [key, item] of Object.entries(value)) {
    if (/token|cookie|session|password|secret|signature|authorization|auth|phone|mobile|device|imei|imsi|^sign$/i.test(key)) remember(item);
    else rememberCredentials(item);
  }
}
function identity(res) {
  for (const obj of [res, res.data, res.user, res.data && res.data.user]) {
    if (!object(obj)) continue;
    for (const key of ['nickname', 'nickName', 'username', 'userName', 'displayName', 'publicUid']) {
      const v = obj[key];
      if (typeof v !== 'string' && typeof v !== 'number') continue;
      const text = String(v);
      // 身份字段原样展示，但排除手机号、控制字符和已知凭据内容。
      if (!text || text.length > 120 || /[\r\n\x00-\x1f\x7f]|(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text)) continue;
      if ([...secrets].some(s => text.includes(s))) continue;
      log(`官方账号身份：${text}`);
      return;
    }
  }
}
function parseAccount(raw) {
  let val;
  try { val = JSON.parse(raw); } catch { throw new Error('账号 JSON 无效'); }
  if (!object(val) || !object(val.headers) || !Object.keys(val.headers).length) throw new Error('缺少请求头对象');
  remember(val.headers);
  const body = typeof val.body === 'string' ? val.body : object(val.body) ? JSON.stringify(val.body) : '';
  if (!body.trim()) throw new Error('缺少完整请求体');
  remember(body);
  try { rememberCredentials(JSON.parse(body)); }
  catch { for (const [key, value] of new URLSearchParams(body)) rememberCredentials({ [key]: value }); }
  const headers = Object.create(null);
  const ignored = new Set(['host', 'content-length', 'connection', 'transfer-encoding', 'accept-encoding', 'proxy-connection']);
  for (const [name, value] of Object.entries(val.headers)) {
    if (name.startsWith(':')) continue;
    const key = name.toLowerCase();
    if (!/^[!#$%&'*+.^_`|~0-9a-z-]+$/.test(key) || typeof value !== 'string' || /[\r\n]/.test(value)) throw new Error('请求头格式无效');
    if (ignored.has(key)) continue;
    if (Object.hasOwn(headers, key)) throw new Error('请求头大小写重复');
    headers[key] = value;
  }
  if (!Object.keys(headers).length) throw new Error('缺少有效请求头');
  headers['content-type'] ||= 'application/x-www-form-urlencoded';
  headers['accept-encoding'] = 'identity';
  headers['content-length'] = String(Buffer.byteLength(body));
  return { headers, body };
}
function accountLines() {
  if ((process.env.ZXHC_ACCOUNTS || '').trim()) return lines(process.env.ZXHC_ACCOUNTS);
  const h = lines(process.env.senku_signheader_zxhc);
  const b = lines(process.env.senku_signbody_zxhc);
  if (h.length !== b.length) throw new Error('兼容变量的请求头与请求体行数必须一致');
  return h.map((header, i) => {
    // 将单账号格式错误保留到账号循环，避免阻断其他账号。
    try { return JSON.stringify({ headers: JSON.parse(header), body: b[i] }); }
    catch { return '{}'; }
  });
}
function post(url, account) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    let done = false;
    let req;
    const timer = setTimeout(() => {
      finish(new Error('请求超时'));
      if (req) req.destroy();
    }, 15000);
    function finish(err, value) {
      if (done) return;
      done = true;
      clearTimeout(timer);
      err ? reject(err) : resolve(value);
    }
    try {
      req = https.request(url, { method: 'POST', headers: account.headers }, res => {
        const parts = [];
        let size = 0;
        res.on('data', part => {
          size += part.length;
          if (size > 1024 * 1024) {
            finish(new Error('响应超过大小限制'));
            res.destroy();
          } else parts.push(part);
        });
        res.on('error', () => finish(new Error('响应传输失败')));
        res.on('aborted', () => finish(new Error('响应中断')));
        res.on('end', () => {
          if (done) return;
          if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error(`HTTP 状态异常 ${res.statusCode}`));
          try {
            const value = JSON.parse(Buffer.concat(parts).toString('utf8'));
            if (!object(value)) throw new Error();
            finish(null, value);
          } catch { finish(new Error('响应不是有效 JSON 对象')); }
        });
      });
      req.on('error', () => finish(new Error('网络请求失败')));
      req.end(account.body);
    } catch { finish(new Error('无法构造请求')); }
  });
}
function signResult(res) {
  // 参考源码仅明确 resultMessage；不臆造 resultCode 的含义。
  // 未知状态一律失败，避免把 HTTP 200 或任意业务提示误判为成功。
  if (res.success === false || res.isSuccess === false) throw new Error('签到接口明确返回失败');
  const msg = typeof res.resultMessage === 'string' ? res.resultMessage.trim() : '';
  if (/^(?:签到成功|今日签到成功|今日已签到|今天已签到|已签到|您今日已签到|您今天已签到)[！!。.]?$/.test(msg)) {
    return msg.includes('已签到') ? 'alreadyComplete' : 'success';
  }
  throw new Error('签到未得到明确成功或今日已签到确认，请检查凭据及接口契约');
}
function creditResult(res) {
  if (res.success === false || res.isSuccess === false) throw new Error('余额查询接口明确返回失败');
  const parts = [];
  for (const [key, label] of [['credit', '积分'], ['coupon', '优惠券']]) {
    const value = res[key];
    if (value === undefined || value === null) continue;
    if (!['number', 'string'].includes(typeof value) || !/^\d+(?:\.\d+)?$/.test(String(value)) || !Number.isFinite(Number(value))) throw new Error('余额字段格式发生变化');
    parts.push(`${label}: ${value}`);
  }
  if (!parts.length) throw new Error('未返回可验证的积分或优惠券字段');
  return parts.join(' ');
}
function selection() {
  const global = process.env.QINGLONG_NOTIFY || 'auto';
  if (no(global)) return false;
  if (yes(global)) return true;
  const configured = process.env.QINGLONG_NOTIFY_SCRIPTS;
  // 策略为 listed-only；没有指定名单时，本脚本不默认入选。
  if (configured === undefined) return false;
  const names = ['38a2ed952649bfb6', 'zxhc/zxhc.js', 'zxhc.js', path.basename(__filename), path.basename(path.dirname(__filename)) + '/' + path.basename(__filename)];
  return configured.split(/[,;\s]+/).filter(Boolean).some(pattern => {
    const re = new RegExp('^' + pattern.split('*').map(v => v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(n => re.test(n));
  });
}
async function notify(summary) {
  if (!selection()) return '未入选或全局关闭';
  if (dry) return '预演已生成通知摘要（断网模式不执行通知助手）';
  const paths = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const helper = paths.find(p => fs.existsSync(p));
  if (!helper) return '通知助手不可用，保留业务退出码';
  const body = `模式：${summary.mode}；状态：${summary.status}；账号总数：${summary.accounts}；成功：${summary.success}；失败：${summary.failed}；子任务成功：${summary.tasks.success}；已完成：${summary.tasks.alreadyComplete}；跳过：${summary.tasks.skipped}；失败：${summary.tasks.failed}`;
  // 隔离助手输出与异常，防止助手日志携带凭据，超时不会修改业务结果。
  return new Promise(resolve => {
    let child;
    let timer;
    let settled = false;
    const finish = value => { if (!settled) { settled = true; clearTimeout(timer); resolve(value); } };
    try {
      child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', helper, NAME, body], { stdio: 'ignore' });
      timer = setTimeout(() => { child.kill('SIGKILL'); finish('通知超时，保留业务退出码'); }, 15000);
      child.on('error', () => finish('通知启动失败，保留业务退出码'));
      child.on('close', code => finish(code === 0 ? '已发送' : '通知失败，保留业务退出码'));
    } catch { finish('通知启动失败，保留业务退出码'); }
  });
}
async function main() {
  console.log(`========== ${NAME} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}`);
  const summary = { task: NAME, mode: dry ? 'dry-run' : 'live', accounts: 0, success: 0, failed: 0, configurationErrors: 0, tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, results: [] };
  let rows = [];
  try {
    rows = accountLines();
    if (!rows.length) throw new Error('请配置 ZXHC_ACCOUNTS，每个非空行一个账号');
  } catch (err) { summary.configurationErrors++; log(`❌ 配置错误：${err.message}`); }
  summary.accounts = rows.length;
  log(`账号数量：${rows.length}`);
  for (let i = 0; i < rows.length; i++) {
    const begin = Date.now();
    const stats = { account: i + 1, total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let account;
    log(`账号 ${i + 1} 开始`);
    const stage = async (number, title, action) => {
      const t = Date.now();
      log(`账号 ${i + 1} 阶段 ${number}/3 ${title} 开始`);
      try {
        const result = await action();
        stats[result]++;
        log(`${result === 'skipped' ? '⏭️' : result === 'alreadyComplete' ? '☑️' : '✅'} 账号 ${i + 1} 阶段 ${number}/3 ${title} ${result === 'skipped' ? '预演跳过请求' : result === 'alreadyComplete' ? '今日已完成' : '成功'}；耗时 ${elapsed(t)} 秒`);
      } catch (err) {
        stats.failed++;
        log(`❌ 账号 ${i + 1} 阶段 ${number}/3 ${title}：${err.message}；耗时 ${elapsed(t)} 秒`);
      }
    };
    await stage(1, '校验账号配置', async () => {
      account = parseAccount(rows[i]);
      return 'success';
    });
    if (!account) {
      summary.configurationErrors++;
      stats.skipped += 2;
      log(`⏭️ 账号 ${i + 1} 阶段 2/3 每日签到、阶段 3/3 积分与优惠券查询：配置无效，跳过；耗时 0 秒`);
    } else {
      await stage(2, '每日签到', async () => {
        if (dry) return 'skipped';
        const res = await post(SIGN, account);
        identity(res);
        return signResult(res);
      });
      await stage(3, '积分与优惠券查询', async () => {
        if (dry) return 'skipped';
        const res = await post(CREDIT, account);
        identity(res);
        log(creditResult(res));
        return 'success';
      });
    }
    if (stats.failed) summary.failed++; else summary.success++;
    stats.elapsedSeconds = elapsed(begin);
    summary.results.push(stats);
    for (const key of Object.keys(summary.tasks)) summary.tasks[key] += stats[key];
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}；成功 ${stats.success}；已完成 ${stats.alreadyComplete}；跳过 ${stats.skipped}；失败 ${stats.failed}；耗时 ${stats.elapsedSeconds} 秒`);
  }
  const failed = summary.failed > 0 || summary.configurationErrors > 0;
  summary.status = summary.configurationErrors ? 'configuration-error' : failed ? (summary.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  process.exitCode = failed ? 1 : 0;
  try { summary.notification = await notify(summary); } catch { summary.notification = '通知失败，保留业务退出码'; }
  summary.elapsedSeconds = elapsed(started);
  summary.finishedAt = new Date().toISOString();
  console.log('----------------------------------------');
  log(`账号统计：总数 ${summary.accounts}；成功 ${summary.success}；失败 ${summary.failed}；配置错误 ${summary.configurationErrors}`);
  log(`子任务统计：总数 ${summary.tasks.total}；成功 ${summary.tasks.success}；已完成 ${summary.tasks.alreadyComplete}；跳过 ${summary.tasks.skipped}；失败 ${summary.tasks.failed}`);
  log(`通知状态：${summary.notification}`);
  log(`完成时间：${summary.finishedAt}；总耗时 ${summary.elapsedSeconds} 秒；最终状态：${summary.status}`);
  if (dry && !failed) log('DRY_RUN_OK：配置有效，未发起网络请求');
  if (!dry && !failed) log('ZXHC_SUCCESS：所有账号签到和余额查询均已验证');
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
}
main().catch(() => { process.exitCode = 1; console.error('任务异常结束，未输出原始异常以保护凭据'); });
