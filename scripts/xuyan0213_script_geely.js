// name: 吉利汽车签到
// cron: 28 1 * * *
/*
name: 吉利汽车签到
cron: 28 1 * * *

来源：xuyan0213/script，geely.js
提交：64301325a938956d92d40ea631f4439956d159ca
原始说明：吉利汽车签到，测试 Quantumult-X、nodejs，其他自测。
原始日期：2024-06-22、2024-08-28；签到风控升级后需要重新获取 token 和 devicesn。
原始重写来源：https://raw.githubusercontent.com/wf021325/qx/master/task/geely.js
原始定时：1 0 * * *，吉利汽车签到。
本维护版运行于 Node.js >=18；无需第三方业务依赖，不下载或执行远程代码。

参数：geely_val，每个非空行是一个 JSON 对象，包含同一账号的 token、devicesn。
兼容旧大写变量 GEELY_VAL，geely_val 非空时优先。多个账号使用换行，不能用 & 或 @ 分隔。
获取：在本人授权设备的抓包工具中解密 app.geely.com HTTPS，打开已登录的
“吉利汽车”App 个人中心，查看 /my/getMyCenterCounts 请求头 token、devicesn，
将二者原样存入同一行 JSON；完成后关闭抓包。不要分享请求头或凭据。
签到提示登录失效或风控升级时，从同一账号同一次登录重新获取两项。
GEELY_DRY_RUN=1：只验证配置和请求构造，完全不联网，也不加载通知模块。
QINGLONG_NOTIFY=auto（默认）：仅通知 QINGLONG_NOTIFY_SCRIPTS 选中的脚本；
未设置名单时本脚本不在默认名单。1/true/yes/on 强制通知，0/false/no/off 关闭。
名单支持逗号、分号、空白分隔，匹配目录相对路径、文件名、文件名通配符或目录编号。
QINGLONG_NOTIFY_DIR 可指定含 sendNotify.js 的青龙通知目录；通知失败不改变业务退出码。
默认副作用仅签到；余额和连续签到查询均只读，不发布内容或变更账户资料。

License: MIT（来源任务授予的有效许可证）。上游未附具名版权行，保留上述来源署名。
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
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
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
    const identities = ["0909dbea8968ed50", "scripts/xuyan0213_script_geely.js", "xuyan0213_script_geely.js", "xuyan0213_script_geely"];
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
const TITLE = '吉利汽车签到';
const CATALOG_ID = '0909dbea8968ed50';
const DRY = /^(1|true|yes|on)$/i.test(process.env.GEELY_DRY_RUN || '');
const started = Date.now();
const rawAccounts = process.env.geely_val || process.env.GEELY_VAL || '';
const lines = rawAccounts.split(/\r?\n/).filter(line => line.trim());
const accounts = [];
const secrets = [];
// 提前收集所有账号凭据，避免一个账号返回的身份中意外包含另一个账号的凭据。
for (const line of lines) {
  try {
    const value = JSON.parse(line);
    for (const key of ['token', 'devicesn']) {
      if (typeof value?.[key] === 'string' && value[key]) secrets.push(value[key]);
    }
  } catch { /* 配置错误在各账号阶段分别报告；绝不回显输入。 */ }
}
function clock() { return new Date().toLocaleTimeString('zh-CN', { hour12: false }); }
function log(message) { console.log(`[${clock()}] ${message}`); }
function elapsed(since) { return ((Date.now() - since) / 1000).toFixed(2); }
function safeIdentity(value) {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  const text = String(value);
  if (!text || text.length > 160 || /[\r\n\x00-\x1f\x7f]/.test(text) ||
      /(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text) ||
      secrets.some(secret => text.includes(secret)) || text.includes('TASK_SUMMARY=')) return '';
  return text;
}
function showIdentity(response) {
  for (const source of [response?.data?.userInfo, response?.data, response]) {
    if (!source || typeof source !== 'object') continue;
    for (const key of ['nickname', 'nickName', 'username', 'userName', 'displayName', 'publicUid', 'uid']) {
      const identity = safeIdentity(source[key]);
      if (identity) { log(`账号身份（${key}）：${identity}`); return; }
    }
  }
}
function failure(message, auth = false) {
  const error = new Error(message);
  error.auth = auth;
  return error;
}
function requestJSON(url, method = 'GET', headers = {}, body) {
  if (DRY) return Promise.reject(failure('预演模式禁止网络请求'));
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer;
    let req;
    function finish(error, value) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(value);
    }
    try {
      const payload = body === undefined ? undefined : JSON.stringify(body);
      req = https.request(url, { method, headers: { ...headers,
        ...(payload === undefined ? {} : { 'Content-Length': Buffer.byteLength(payload) }) }
      }, res => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          res.destroy();
          finish(failure(`HTTP 请求失败（状态 ${res.statusCode}）`, [401, 403].includes(res.statusCode)));
          return;
        }
        const buffers = [];
        let size = 0;
        res.on('data', chunk => {
          size += chunk.length;
          if (size > 1024 * 1024) {
            finish(failure('响应超过大小限制'));
            res.destroy(); req.destroy();
          } else buffers.push(chunk);
        });
        res.on('end', () => {
          if (settled) return;
          try { finish(null, JSON.parse(Buffer.concat(buffers).toString('utf8'))); }
          catch { finish(failure('响应不是有效 JSON')); }
        });
        res.on('error', () => finish(failure('响应读取失败')));
        res.on('aborted', () => finish(failure('响应中断')));
      });
      timer = setTimeout(() => { finish(failure('请求超时（15秒）')); req.destroy(); }, 15000);
      req.on('error', () => finish(failure('网络请求失败')));
      req.end(payload);
    } catch { finish(failure('请求构造失败')); if (req) req.destroy(); }
  });
}
function beijingDate(now) {
  const date = new Date(now + 8 * 3600000);
  return { year: String(date.getUTCFullYear()), month: String(date.getUTCMonth() + 1),
    formatted: date.toISOString().slice(0, 19).replace('T', ' ') };
}
function buildRequests(account, version, now = Date.now()) {
  const ts = Math.floor(now / 1000);
  const date = beijingDate(ts * 1000);
  const cId = 'BLqo2nmmoPgGuJtFDWlUjRI2b1b';
  const signature = crypto.createHash('md5')
    .update(`cId=${cId}&signDate=${ts * 1000}&ts=${ts}0]3K@'9MK+6Jf`).digest('hex');
  const common = {
    appVersion: version, deviceSN: account.devicesn, token: account.token, platform: 'iOS',
    'User-Agent': `GLMainProject/${version} (iPhone; iOS 17.6.1; Scale/2.00)`
  };
  return [
    { url: 'https://app.geely.com/api/v1/userSign/sign/risk', method: 'POST',
      headers: { ...common, 'X-Data-Sign': signature, 'Content-Type': 'application/json',
        sweet_security_info: JSON.stringify({ appVersion: version,
          deviceUUID: account.devicesn, geelyDeviceId: account.devicesn }) },
      body: { signDate: date.formatted, ts: String(ts), cId } },
    { url: 'https://app.geely.com/api/v1/userSign/getSignMsg', method: 'POST',
      headers: { token: account.token, 'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/ios/geelyApp' },
      body: { year: date.year, month: date.month } },
    { url: 'https://app.geely.com/api/v1/growthSystem/energyBody/summary', method: 'GET', headers: common }
  ];
}
function requireBusiness(response) {
  if (!response || response.code !== 'success') {
    const auth = /token/i.test(String(response?.code || '')) ||
      /登录.*(失效|过期)|未登录|token/i.test(String(response?.message || ''));
    throw failure(auth ? '凭据失效，请重新获取同一账号的 token 和 devicesn' : '业务未成功（响应详情已隐藏）', auth);
  }
}
function numberValue(value) {
  if ((typeof value !== 'number' && typeof value !== 'string') || String(value).trim() === '') return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : null;
}
async function runAccount(line, index, version) {
  const since = Date.now();
  const result = { account: index, total: 4, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  log(`账号 ${index} ────────────────`);
  let account;
  let requests;
  let valid = true;
  let auth = false;
  const stages = ['配置与签名检查', '每日签到', '连续签到查询', '能量体查询'];
  for (let stage = 0; stage < 4; stage++) {
    const stepStart = Date.now();
    log(`账号 ${index} 阶段 ${stage + 1}/4：${stages[stage]}`);
    try {
      if (stage === 0) {
        try { account = JSON.parse(line); } catch { throw failure('账号行不是有效 JSON'); }
        if (!account || typeof account !== 'object' || Array.isArray(account) ||
            ['token', 'devicesn'].some(key => typeof account[key] !== 'string' ||
              !account[key].trim() || account[key].length > 4096 || /[^\x20-\x7e]/.test(account[key]))) {
          throw failure('每行必须提供同一账号的非空 token 和 devicesn，且均为有效请求头字符串');
        }
        requests = buildRequests(account, version);
        result.success++;
        log('✅ 配置及三个请求构造通过（不显示凭据或签名）');
      } else if (!valid || auth || DRY) {
        result.skipped++;
        log(`⏭️ ${DRY && valid ? '预演：已构造请求，未执行网络或签到' : '前置配置或认证失败，跳过请求'}`);
      } else {
        const req = requests[stage - 1];
        const response = await requestJSON(req.url, req.method, req.headers, req.body);
        showIdentity(response);
        // 这是原脚本唯一给出的“已签到”响应，不将任意失败或模糊消息视作成功。
        if (stage === 1 && response?.code === 'fail' && response.message === '您已签到,请勿重复操作!') {
          result.alreadyComplete++;
          log('☑️ 今日已签到，无需重复操作');
        } else {
          requireBusiness(response);
          if (stage === 2) {
            const days = numberValue(response.data?.continuousSignDay);
            if (days === null || !Number.isInteger(days)) throw failure('连续签到天数字段缺失或无效');
            log(`✅ 累计签到：${days}天`);
          } else if (stage === 3) {
            const total = numberValue(response.data?.total);
            if (total === null) throw failure('能量体余额字段缺失或无效');
            log(`✅ 能量体：${total}`);
          } else log('✅ 签到业务成功');
          result.success++;
        }
      }
    } catch (error) {
      result.failed++;
      if (stage === 0) valid = false;
      if (error.auth) auth = true;
      // 仅显示本脚本创建的错误，避免标准库或通知器回显请求参数。
      log(`❌ ${error.auth !== undefined ? error.message : '处理失败（详情已隐藏）'}`);
    }
    log(`账号 ${index} 阶段 ${stage + 1}/4 完成，耗时 ${elapsed(stepStart)}秒`);
  }
  result.configurationError = !valid;
  result.status = result.failed ? 'failure' : DRY ? 'dry-run' : 'success';
  result.durationSeconds = Number(elapsed(since));
  log(`账号 ${index} 统计：总任务 ${result.total}，成功 ${result.success}，已完成 ${result.alreadyComplete}，跳过 ${result.skipped}，失败 ${result.failed}，耗时 ${result.durationSeconds}秒`);
  return result;
}
function notificationSelected() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (/^(0|false|no|off)$/.test(mode)) return false;
  if (/^(1|true|yes|on)$/.test(mode)) return true;
  if (mode !== 'auto') return false;
  const selectors = (process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const names = [CATALOG_ID, 'geely.js', path.basename(__filename),
    path.relative(process.cwd(), __filename).split(path.sep).join('/'), 'output/candidate.js'];
  return selectors.some(selector => {
    const pattern = selector.split('*').map(part => part.split('?')
      .map(x => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.')).join('.*');
    return names.some(name => new RegExp(`^${pattern}$`).test(name));
  });
}
async function notify(summary) {
  if (!notificationSelected()) return 'disabled';
  if (DRY) return 'dry-run-suppressed';
  const paths = [
    ...(process.env.QINGLONG_NOTIFY_DIR ? [path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js')] : []),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js',
    path.join(__dirname, 'sendNotify.js'), path.join(__dirname, 'utils/sendNotify.js')
  ];
  const file = paths.find(name => { try { return fs.statSync(name).isFile(); } catch { return false; } });
  if (!file) return 'unavailable';
  const body = `状态：${summary.status}\n账号总数：${summary.totalAccounts}\n成功：${summary.successAccounts}\n失败：${summary.failedAccounts}\n预演：${summary.dryRunAccounts}\n配置错误：${summary.configurationErrors}\n子任务成功：${summary.steps.success}，已完成：${summary.steps.alreadyComplete}，跳过：${summary.steps.skipped}，失败：${summary.steps.failed}`;
  // 独立进程限制通知耗时，屏蔽通知模块自身日志，且不向它传递账号环境变量。
  return new Promise(resolve => {
    let completed = false;
    const finish = status => { if (!completed) { completed = true; clearTimeout(timer); resolve(status); } };
    let child;
    let timer;
    try {
      const env = { ...process.env };
      delete env.geely_val; delete env.GEELY_VAL;
      child = spawn(process.execPath, ['-e',
        'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))',
        file, TITLE, body], { stdio: 'ignore', env });
      timer = setTimeout(() => { child.kill('SIGKILL'); finish('timeout'); }, 15000);
      child.on('error', () => finish('failed'));
      child.on('exit', code => finish(code === 0 ? 'sent' : 'failed'));
    } catch { finish('failed'); }
  });
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}`);
  log(`运行模式：${DRY ? '断网预演' : '正式执行'}；账号数量：${lines.length}`);
  let fatal = false;
  try {
    log('全局阶段 1/1：查询 App 版本');
    const versionStart = Date.now();
    let version = '3.25.0';
    if (DRY || !lines.length) log('⏭️ 预演或未配置账号，跳过版本查询，使用上游兼容版本 3.25.0');
    else {
      try {
        const data = await requestJSON('https://itunes.apple.com/cn/lookup?id=1518762715');
        const value = data?.results?.[0]?.version;
        if (typeof value !== 'string' || !/^\d+(?:\.\d+){1,3}$/.test(value)) throw failure('版本字段无效');
        version = value;
        log(`✅ 最新版本号：${version}`);
      } catch { log('⚠️ 版本查询不可用，保留上游回退版本 3.25.0；业务成功仍须由签到接口核验'); }
    }
    log(`全局阶段完成，耗时 ${elapsed(versionStart)}秒`);
    if (!lines.length) log('❌ 配置错误：请设置 geely_val，每行提供 token、devicesn 的 JSON');
    for (let i = 0; i < lines.length; i++) accounts.push(await runAccount(lines[i], i + 1, version));
  } catch { fatal = true; log('❌ 任务内部处理失败（详情已隐藏）'); }
  const failedAccounts = accounts.filter(a => a.failed > 0).length;
  const configurationErrors = accounts.filter(a => a.configurationError).length + (lines.length ? 0 : 1);
  const ok = !fatal && lines.length > 0 && accounts.length === lines.length && failedAccounts === 0;
  const summary = {
    task: TITLE, mode: DRY ? 'dry-run' : 'live',
    status: configurationErrors ? 'configuration-error' : ok ? (DRY ? 'dry-run' : 'success') :
      accounts.some(a => a.status === 'success') ? 'partial-failure' : 'failure',
    totalAccounts: lines.length,
    successAccounts: accounts.filter(a => a.status === 'success').length,
    failedAccounts, dryRunAccounts: accounts.filter(a => a.status === 'dry-run').length,
    configurationErrors, steps: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, accounts,
    exitCode: ok ? 0 : 1, startTime: new Date(started).toISOString()
  };
  for (const account of accounts) for (const key of Object.keys(summary.steps)) summary.steps[key] += account[key];
  try { summary.notification = await notify(summary); } catch { summary.notification = 'failed'; }
  summary.finishTime = new Date().toISOString();
  summary.durationSeconds = Number(elapsed(started));
  log('────────────────────────────────');
  log(`账号统计：总数 ${summary.totalAccounts}，成功 ${summary.successAccounts}，失败 ${failedAccounts}，预演 ${summary.dryRunAccounts}，配置错误 ${configurationErrors}`);
  log(`子任务统计：总数 ${summary.steps.total}，成功 ${summary.steps.success}，已完成 ${summary.steps.alreadyComplete}，跳过 ${summary.steps.skipped}，失败 ${summary.steps.failed}`);
  log(`通知状态：${summary.notification}；总耗时：${summary.durationSeconds}秒`);
  log(`完成时间：${summary.finishTime}；最终状态：${summary.status}；退出码：${summary.exitCode}`);
  if (DRY && ok) log('GEELY_DRY_RUN_OK：仅配置及请求构造通过，未验证真实业务');
  if (!DRY && ok) log('GEELY_SUCCESS：所有账号签到与查询均已核验成功');
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = summary.exitCode;
}
main();
