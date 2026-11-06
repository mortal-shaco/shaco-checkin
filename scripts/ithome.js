// name: IT之家签到
// cron: 36 1 * * *
// SPDX-License-Identifier: GPL-3.0-only
// 来源：chavyleung/scripts，ithome/ithome.js 与 ithome/ithome.cookie.js。
// 原参考说明：获取方式:app进入签到页面获取；解密参考GitHub @Grergo  @daimiaopeng
// Node.js >= 18；仅使用标准库，无安装引导。
// ITHOME_USER_HASH：登录 IT之家 App 后进入签到页，在本人授权的 HTTPS 抓包中
// 找到 napi.ithome.com/api/usersign/getsigninfo 请求的 userHash 参数，URL 解码一次
// 后填入青龙环境变量。每行一个账号；不要填整个 URL，不使用 & 或 @ 分隔账号。
// 兼容旧变量 senku_ithome_userHash（仅当规范变量未设置时使用），不读取 box.dat。
// ITHOME_DRY_RUN=1 完全离线预演，既不签到也不发送网络通知。
// 默认每天签到一次，不重试写操作；查询连续/累计天数及金币，无其他业务写操作。
// 通知：QINGLONG_NOTIFY=1 强制启用，0 关闭；auto 仅选中列表内任务。
// QINGLONG_NOTIFY_SCRIPTS 支持目录相对路径、文件名通配符、目录编号或 *。
// 离线模式生成通知预览；正式模式从青龙 sendNotify.js 发送脱敏汇总。
'use strict';
// qinglong-notification-policy: begin
(() => {
  const raw = process.env.QINGLONG_NOTIFY;
  if (raw !== undefined && String(raw).trim() !== '' && String(raw).trim().toLowerCase() !== 'auto') return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["2d56412ced04fdd3", "scripts/ithome.js", "ithome.js", "ithome"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = 'IT之家签到';
const CATALOG = '2d56412ced04fdd3';
const DRY = process.env.ITHOME_DRY_RUN === '1';
const started = Date.now();
const UA_SIGN = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 ithome/rmsdklevel2/day/7.63';
const UA_INFO = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 ithome/rmsdklevel2/day/7.32';
const lines = (process.env.ITHOME_USER_HASH !== undefined ? process.env.ITHOME_USER_HASH : process.env.senku_ithome_userHash || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
function log(text) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${text}`); }
function elapsed(t) { return ((Date.now() - t) / 1000).toFixed(3); }
// 所有错误均使用本地固定描述，不输出请求 URL、异常堆栈、响应正文。
function fail(message) { const e = new Error(message); e.safe = true; return e; }
function httpJSON(url, ua) {
  if (DRY) throw fail('离线模式禁止网络请求');
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { 'User-Agent': ua, Accept: 'application/json' } }, res => {
      if (res.statusCode !== 200) { res.resume(); reject(fail('HTTP 状态异常（不跟随重定向）')); return; }
      const chunks = []; let bytes = 0;
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 65536) req.destroy(fail('响应超过安全大小限制'));
        else chunks.push(chunk);
      });
      res.on('error', () => reject(fail('响应读取失败')));
      res.on('end', () => {
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || typeof data !== 'object' || Array.isArray(data)) throw 0;
          resolve(data);
        } catch { reject(fail('响应不是有效业务对象')); }
      });
    });
    const timer = setTimeout(() => req.destroy(fail('请求超时')), 10000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', e => reject(e.safe ? e : fail('网络请求失败')));
  });
}
// 上游 8 字节 TripleDES 密钥等价于重复三次的 DES 密钥；显式零填充，避免全局 CryptoJS 依赖。
function encrypt(text, key) {
  const b = Buffer.from(text, 'utf8');
  const padded = Buffer.alloc(Math.ceil(b.length / 8) * 8); b.copy(padded);
  const k = Buffer.from(key, 'utf8');
  if (k.length !== 8) throw fail('签名密钥长度异常');
  const cipher = crypto.createCipheriv('des-ede3', Buffer.concat([k, k, k]), null);
  cipher.setAutoPadding(false);
  return Buffer.concat([cipher.update(padded), cipher.final()]).toString('hex');
}
const SKEY = "hd7%b4f8p9)*fd4h5l6|)123/*-+!#$@%^*()_+?>?njidfds[]rfbcvnb3rz/ird|opqqyh487874515/%90hggigadfihklhkopjj`b3hsdfdsf84215456fi15451%q(#@Fzd795hn^Ccl$vK^L%#w$^yr%ETvX#0TaPSRm5)OeG)^fQnn6^%^UTtJI#3EZ@p6^Rf$^!O$(jnkOiBjn3#inhOQQ!aTX8R)9O%#o3zCVxo3tLyVorwYwA^$%^b9Yy$opSEAOOlFBsS^5d^HoF%tJ$dx%3)^q^c^$al%b4I)QHq^#^AlcK^KZFYf81#bL$n@$%j^H(%m^";
function signing(now) {
  // IT之家签到按北京时间生成日期与日内时间，避免青龙容器时区偏差。
  const d = new Date(now + 8 * 3600000), day = d.getUTCDate();
  const value = Math.round(now / 50000) * day * 3;
  function gekk(n) {
    const places = n === 3 ? [1000, 100, 10] : [10000000, 1000000, 100000, 10000, 1000, 100, 10, 1];
    return places.map(p => SKEY[Math.floor((value % (p * 10)) / p) * day]).join('');
  }
  const pad = n => String(n).padStart(2, '0');
  const time = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(day)} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
  return ['k' + encrypt(gekk(3), gekk(8)), encrypt(time, gekk(8))];
}
function signURL(hash) {
  const now = Date.now(); const [key, value] = signing(now);
  const u = new URL('https://napi.ithome.com/api/usersign/sign');
  u.search = new URLSearchParams({ userHash: hash, type: '0', timestamp: String(now), [key]: value }).toString();
  return u;
}
function identity(data, hash) {
  for (const k of ['nickname', 'username', 'displayName', 'uid']) {
    const v = data[k];
    if ((typeof v === 'string' || typeof v === 'number') && String(v) && String(v) !== hash) {
      // 身份原值显示；不把手机号、会话或控制字符当身份打印。
      const text = String(v);
      if (!/[\r\n\x00-\x1f\x7f]/.test(text) && !/\b1[3-9]\d{9}\b/.test(text) && !lines.some(s => text.includes(s))) log(`账号身份：${text}`);
    }
  }
}
async function account(hash, index) {
  const t = Date.now(); const stats = { total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let valid = !/[\s&@?#]/.test(hash) && hash.length <= 8192;
  for (const [n, title] of [[1, '每日签到'], [2, '签到统计查询']]) {
    const s = Date.now(); log(`账号 ${index} · 阶段 ${n}/2 ${title} 开始`);
    try {
      if (!valid) throw fail('凭据格式无效；请仅填写解码后的 userHash');
      if (DRY) {
        signURL(hash); // 本地验证签名实现，不生成或打印网络结果。
        stats.skipped++; log(`⏭️ 账号 ${index} · ${title} DRY_RUN_OK：已验证本地参数与签名，未联网`);
      } else if (n === 1) {
        const data = await httpJSON(signURL(hash), UA_SIGN); identity(data, hash);
        if (data.ok === 1) { stats.success++; log(`✅ 账号 ${index} · 签到成功（ok=1）`); }
        else if (data.ok === 0 && typeof data.msg === 'string' && /^(?:今天已经签到|今天已签到|今日已签到|已经签到|您今天已经签到)[！!。\s]*$/.test(data.msg)) {
          stats.alreadyComplete++; log(`☑️ 账号 ${index} · 今日已签到`);
        } else throw fail('签到未获明确成功结果；请在 App 核验凭据和签到状态');
      } else {
        const u = new URL('https://napi.ithome.com/api/usersign/getsigninfo'); u.searchParams.set('userHash', hash);
        const data = await httpJSON(u, UA_INFO); identity(data, hash);
        if (data.ok === 0 || !['cdays', 'mdays', 'totalcoin'].every(k => (typeof data[k] === 'number' || (typeof data[k] === 'string' && /^\d+$/.test(data[k]))) && Number.isSafeInteger(Number(data[k])) && Number(data[k]) >= 0)) throw fail('签到统计字段或业务状态无效');
        stats.success++; log(`✅ 账号 ${index} · 连续:${data.cdays}天,累计:${data.mdays}天,金币:${data.totalcoin}个`);
      }
    } catch (e) { stats.failed++; log(`❌ 账号 ${index} · ${title}：${e.safe ? e.message : '本地处理失败'}`); }
    log(`账号 ${index} · 阶段 ${n}/2 耗时 ${elapsed(s)} 秒`);
  }
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${elapsed(t)} 秒`);
  return { account: index, status: stats.failed ? 'failure' : DRY ? 'dry-run' : 'success', ...stats };
}
function selectedNotify() {
  const sw = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(sw)) return false;
  if (['1', 'true', 'yes', 'on'].includes(sw)) return true;
  const names = [CATALOG, 'ithome.js', path.basename(__filename), path.relative(process.cwd(), __filename).split(path.sep).join('/')];
  return (process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean).some(pattern => {
    const escaped = pattern.split('*').map(p => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    return names.some(name => new RegExp(`^${escaped}$`).test(name));
  });
}
async function notify(body) {
  if (!selectedNotify()) return '未选中或已关闭';
  if (DRY) { log(`通知离线预览：${body}`); return '离线预览，未联网'; }
  const paths = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = paths.find(p => fs.existsSync(p));
  if (!file) return '通知模块不可用，保留业务退出码';
  // 隔离通知模块的日志与异常，限制总耗时，避免泄漏其内部配置。
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', file, TITLE, body], { stdio: 'ignore' });
    const timer = setTimeout(() => child.kill('SIGKILL'), 15000);
    child.on('error', () => { clearTimeout(timer); resolve('通知启动失败，保留业务退出码'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '通知失败，保留业务退出码'); });
  });
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${DRY ? '离线预演' : '正式执行'}；账号数：${lines.length}`);
  const results = [];
  if (!lines.length) log('❌ 配置错误：请配置 ITHOME_USER_HASH，每行一个账号');
  for (let i = 0; i < lines.length; i++) results.push(await account(lines[i], i + 1));
  const failed = results.filter(r => r.failed).length;
  const success = results.length - failed;
  const status = !lines.length ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : DRY ? 'dry-run' : 'success';
  const code = failed || !lines.length ? 1 : 0;
  const body = `状态 ${status}；账号总数 ${lines.length}，成功 ${DRY ? 0 : success}，预演通过 ${DRY ? success : 0}，失败 ${failed}；${!lines.length ? '缺少凭据配置' : '详见本次脱敏日志'}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '通知失败，保留业务退出码'; }
  const tasks = results.reduce((a, r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  log('----------------------------------------');
  log(body); log(`子任务统计：总数 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`通知状态：${notification}；总耗时：${elapsed(started)} 秒`);
  log(`完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, status, mode: DRY ? 'dry-run' : 'live', accounts: { total: lines.length, success: DRY ? 0 : success, dryRun: DRY ? success : 0, failed }, tasks, results, notification, durationSeconds: Number(elapsed(started)), exitCode: code }));
  process.exitCode = code;
}
main().catch(() => { process.exitCode = 1; log('❌ 任务执行器异常'); });
