// name: 网际快车每日签到
// cron: 4 9 * * *
/**
 * 网际快车（wjkc.click）自动登录签到 · 青龙独立维护版
 *
 * 上游：ZZ0YY/wjkc-checkin · index.js
 * 仓库：https://github.com/ZZ0YY/wjkc-checkin.git
 * 分支：dev
 * 提交：060a41ee567250455abc3a9cc91929ba21437d23
 * 授权：MIT
 *
 * 功能盘点（主来源）：
 * - 使用邮箱 + MD5(密码) 登录 /api/user/login，从 Set-Cookie 提取 token
 * - POST /api/user/sign_use 完成每日签到，解析 base64 业务包
 * - 识别 SUCCESS 与 SIGN_USE_MULTY_TIMES（今日已签）
 * - 展示获得流量 MB 与连续签到天数
 * - 多账号：WJKC_CREDENTIALS 每行一个账号
 * - 上游 PushPlus/NOTIFY 自定义推送改为青龙 notify 策略；无发帖/评论等公开内容副作用
 *
 * WJKC_CREDENTIALS（必填）：每行一个账号，格式「邮箱,密码」；只在第一个逗号处拆分，
 * 密码中后续逗号原样保留。可选备注：「备注|邮箱,密码」，只在首个 | 处拆分。
 * 不使用 & 或 @ 分隔账号。账号与密码来自 https://wjkc.click 本人注册信息。
 * WJKC_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）。
 * WJKC_TIMEOUT_MS：请求超时毫秒，默认 15000（1000–60000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
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
    const identities = ["066f6353f92de3e0", "scripts/wjkc.js", "wjkc.js", "wjkc"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end

const crypto = require('node:crypto');
const https = require('node:https');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { URL } = require('node:url');
const { execFile } = require('node:child_process');

const TITLE = '网际快车每日签到';
const CATALOG_ID = '066f6353f92de3e0';
const CREDENTIAL_ENV = 'WJKC_CREDENTIALS';
const DRY_RUN_ENV = 'WJKC_DRY_RUN';
const HOST = 'wjkc.click';
const ORIGIN = `https://${HOST}`;
const UA =
  'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36 EdgA/143.0.0.0';
const DEFAULT_TIMEOUT_MS = 15000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const ACCOUNT_GAP_MS = 3000;

const secrets = new Set();
const stamp = () =>
  new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
const nowText = () =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
    .format(new Date())
    .replace(/\//g, '-');
const log = (text) => console.log(`[${stamp()}] ${text}`);
const enabled = (value) => /^(1|true|yes|on)$/i.test(String(value || '').trim());
const disabled = (value) => /^(0|false|no|off)$/i.test(String(value || '').trim());

function remember(value) {
  if (typeof value === 'string' && value) secrets.add(value);
}

function redact(value, maskPhone = true) {
  let text = String(value == null ? '' : value).replace(
    /[\r\n\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    ' '
  );
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
    if (secret) text = text.split(secret).join('[已隐藏]');
  }
  text = text.replace(/[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}/g, '[邮箱已隐藏]');
  if (maskPhone) text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.WJKC_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000 ? value : DEFAULT_TIMEOUT_MS;
}

function md5(text) {
  return crypto.createHash('md5').update(String(text), 'utf8').digest('hex');
}

function base64Encode(str) {
  return Buffer.from(String(str), 'utf8').toString('base64');
}

function base64Decode(str) {
  return Buffer.from(String(str), 'base64').toString('utf8');
}

function wrapPayload(obj) {
  return JSON.stringify({ data: base64Encode(JSON.stringify(obj)) });
}

function unwrapPayload(envelope) {
  if (!envelope || typeof envelope !== 'object' || typeof envelope.data !== 'string') {
    throw new Error('业务包缺少 data 字段');
  }
  let decoded;
  try {
    decoded = JSON.parse(base64Decode(envelope.data));
  } catch {
    throw new Error('业务包无法解码');
  }
  if (!decoded || typeof decoded !== 'object' || Array.isArray(decoded)) {
    throw new Error('业务包结构异常');
  }
  return decoded;
}

function notificationSelected() {
  if (disabled(process.env.QINGLONG_NOTIFY)) return false;
  if (enabled(process.env.QINGLONG_NOTIFY)) return true;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return false; /* listed-only default */
  const raw = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (String(raw).trim() === '') return false;
  const selectors = String(raw).split(/[,;\s]+/).filter(Boolean);
  if (selectors.includes('*')) return true;
  const filename = path.basename(process.argv[1] || 'candidate.js');
  const names = [
    CATALOG_ID,
    'scripts/wjkc_checkin.js',
    'wjkc_checkin.js',
    'wjkc',
    filename,
    'candidate.js',
  ];
  return selectors.some((selector) => {
    const pattern =
      '^' +
      selector
        .split('*')
        .map((part) =>
          part
            .split('?')
            .map((token) => token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
            .join('.')
        )
        .join('.*') +
      '$';
    return names.some((name) => new RegExp(pattern, 'i').test(name));
  });
}

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line, index) => {
    remember(line);
    let label = '';
    let credential = line;
    const pipe = line.indexOf('|');
    if (pipe > 0) {
      label = line.slice(0, pipe).trim();
      credential = line.slice(pipe + 1).trim();
    }
    const comma = credential.indexOf(',');
    const email = comma < 0 ? '' : credential.slice(0, comma).trim();
    const password = comma < 0 ? '' : credential.slice(comma + 1);
    remember(email);
    remember(password);
    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    const passwordOk = password.length > 0 && !/[\r\n]/.test(password);
    return {
      index: index + 1,
      label,
      email,
      password,
      valid: emailOk && passwordOk,
    };
  });
}

function commonHeaders(extra = {}) {
  return {
    Host: HOST,
    Connection: 'keep-alive',
    Accept: 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
    'User-Agent': UA,
    Origin: ORIGIN,
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    Referer: `${ORIGIN}/`,
    'Accept-Language': 'zh-CN,zh;q=0.9',
    ...extra,
  };
}

function extractTokenFromSetCookie(headerValue) {
  const values = Array.isArray(headerValue) ? headerValue : headerValue ? [headerValue] : [];
  for (const item of values) {
    const match = String(item).match(/(?:^|,\s*)token=([^;,\s]+)/i) || String(item).match(/token=([^;]+)/i);
    if (match && match[1]) return match[1].trim();
  }
  return '';
}

function showIdentity(obj, accountIndex) {
  if (!obj || typeof obj !== 'object') return;
  const bags = [obj.data, obj.user, obj.profile, obj].filter((v) => v && typeof v === 'object' && !Array.isArray(v));
  const fields = ['nickname', 'username', 'display_name', 'displayName', 'name', 'public_uid', 'uid'];
  for (const bag of bags) {
    for (const field of fields) {
      const value = bag[field];
      if ((typeof value === 'string' && value) || typeof value === 'number') {
        const maskPhone = !['public_uid', 'uid'].includes(field);
        log(`账号 ${accountIndex} 官方身份（${field}）：${redact(value, maskPhone)}`);
        return;
      }
    }
  }
}

function httpRequest(urlString, { method = 'GET', headers = {}, body = null } = {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const deadline = Date.now() + timeoutMs();
    const fail = (code) => {
      if (settled) return;
      settled = true;
      reject(new Error(code));
    };
    let parsed;
    try {
      parsed = new URL(urlString);
    } catch {
      return fail('invalid-url');
    }
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return fail('invalid-url');
    const remaining = deadline - Date.now();
    if (remaining <= 0) return fail('timeout');
    const lib = parsed.protocol === 'https:' ? https : http;
    const payload = body == null ? null : Buffer.from(String(body), 'utf8');
    const reqHeaders = { ...headers };
    if (payload) reqHeaders['Content-Length'] = String(payload.length);
    const req = lib.request(
      {
        protocol: parsed.protocol,
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
        path: parsed.pathname + parsed.search,
        method,
        headers: reqHeaders,
        timeout: remaining,
      },
      (res) => {
        const parts = [];
        let size = 0;
        res.on('data', (chunk) => {
          size += chunk.length;
          if (size > MAX_RESPONSE_BYTES) {
            fail('response-too-large');
            res.destroy();
            req.destroy();
            return;
          }
          parts.push(chunk);
        });
        res.on('error', () => fail('response-error'));
        res.on('aborted', () => fail('response-aborted'));
        res.on('end', () => {
          if (settled) return;
          settled = true;
          resolve({
            statusCode: res.statusCode || 0,
            headers: res.headers,
            text: Buffer.concat(parts).toString('utf8'),
          });
        });
      }
    );
    req.on('timeout', () => {
      fail('timeout');
      req.destroy();
    });
    req.on('error', () => fail('network-error'));
    if (payload) req.write(payload);
    req.end();
  });
}

async function login(account) {
  const body = wrapPayload({ email: account.email, password: md5(account.password) });
  const response = await httpRequest(`${ORIGIN}/api/user/login`, {
    method: 'POST',
    headers: commonHeaders(),
    body,
  });
  let envelope;
  try {
    envelope = JSON.parse(response.text);
  } catch {
    throw new Error('login-non-json');
  }
  const token = extractTokenFromSetCookie(response.headers['set-cookie']);
  if (token) {
    remember(token);
    try {
      showIdentity(unwrapPayload(envelope), account.index);
    } catch {
      /* 登录成功但无业务身份字段时忽略 */
    }
    return token;
  }
  try {
    const decoded = unwrapPayload(envelope);
    const msg = typeof decoded.msg === 'string' ? decoded.msg : '登录失败';
    throw new Error(`login-business:${msg}`);
  } catch (err) {
    if (String(err.message).startsWith('login-business:')) throw err;
    throw new Error('login-no-token');
  }
}

async function checkin(token, accountIndex) {
  const response = await httpRequest(`${ORIGIN}/api/user/sign_use`, {
    method: 'POST',
    headers: commonHeaders({ Cookie: `token=${token}; platform=Android;` }),
    body: JSON.stringify({ data: 'e30=' }),
  });
  let envelope;
  try {
    envelope = JSON.parse(response.text);
  } catch {
    throw new Error('checkin-non-json');
  }
  const decoded = unwrapPayload(envelope);
  showIdentity(decoded, accountIndex);
  const code = decoded.code;
  const msg = typeof decoded.msg === 'string' ? decoded.msg : '';
  if (code === 0 && msg === 'SUCCESS') {
    const addedTraffic = Number(decoded.data && decoded.data.addTraffic);
    const continueDays = decoded.data && decoded.data.haveContinueSignUseData;
    const trafficInMB =
      Number.isFinite(addedTraffic) && addedTraffic >= 0
        ? String(Math.floor(addedTraffic / 1024 / 1024))
        : '接口未提供';
    const daysText =
      continueDays === undefined || continueDays === null ? '接口未提供' : String(continueDays);
    return {
      state: 'success',
      message: `签到成功：获得 ${trafficInMB} MB 流量；连续签到 ${daysText} 天`,
    };
  }
  if (msg.includes('SIGN_USE_MULTY_TIMES')) {
    return { state: 'alreadyComplete', message: '今日已签到' };
  }
  throw new Error(`checkin-business:${msg || '未确认成功'}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendNotify(body, dryRun) {
  if (!notificationSelected()) return '已关闭';
  if (dryRun) return '通知预演已跳过真实投递（断网）';

  const jsCandidates = [
    process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js',
    '/ql/scripts/sendNotify.js',
  ].filter(Boolean);
  const jsFile = jsCandidates.find((file) => fs.existsSync(file));
  if (jsFile) {
    const code = `
      Promise.resolve()
        .then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3]))
        .catch(() => { process.exitCode = 1; });
    `;
    const env = { ...process.env };
    delete env.WJKC_CREDENTIALS;
    return new Promise((resolve) => {
      execFile(
        process.execPath,
        ['-e', code, jsFile, TITLE, body],
        { env, timeout: 10000, maxBuffer: 65536 },
        (err) => resolve(err ? '通知失败（保留业务退出码）' : '通知已发送')
      );
    });
  }

  const pyCandidates = [
    process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'notify.py'),
    '/ql/data/scripts/notify.py',
    '/ql/scripts/notify.py',
  ].filter(Boolean);
  const pyFile = pyCandidates.find((file) => fs.existsSync(file));
  if (pyFile) {
    const env = { ...process.env };
    delete env.WJKC_CREDENTIALS;
    const script = `
import importlib.util, sys
spec = importlib.util.spec_from_file_location('ql_notify', sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
send = getattr(mod, 'send', None) or getattr(mod, 'notify', None)
if callable(send):
    send(sys.argv[2], sys.argv[3])
else:
    sys.exit(1)
`;
    return new Promise((resolve) => {
      execFile(
        'python3',
        ['-c', script, pyFile, TITLE, body],
        { env, timeout: 10000, maxBuffer: 65536 },
        (err) => resolve(err ? '通知失败（保留业务退出码）' : '通知已发送')
      );
    });
  }
  return '通知不可用（未找到青龙 notify）';
}

function reasonText(code) {
  const map = {
    timeout: '请求超时',
    'response-too-large': '响应过大',
    'network-error': '网络请求失败',
    'response-error': '响应读取失败',
    'response-aborted': '响应中断',
    'invalid-url': '地址无效',
    'login-non-json': '登录接口返回非 JSON',
    'login-no-token': '登录未返回有效 Token',
    'checkin-non-json': '签到接口返回非 JSON',
  };
  if (map[code]) return map[code];
  if (String(code).startsWith('login-business:')) return `登录失败：${redact(String(code).slice('login-business:'.length))}`;
  if (String(code).startsWith('checkin-business:')) return `签到失败：${redact(String(code).slice('checkin-business:'.length))}`;
  return '请求失败';
}

async function main() {
  const started = Date.now();
  const dryRun = enabled(process.env[DRY_RUN_ENV]);
  const accounts = parseAccounts(process.env[CREDENTIAL_ENV]);
  const summary = {
    task: TITLE,
    catalogId: CATALOG_ID,
    mode: dryRun ? 'dry-run' : 'live',
    accounts: accounts.length,
    successfulAccounts: 0,
    failedAccounts: 0,
    tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 },
    status: '',
    notification: '',
  };

  console.log('========================================');
  console.log(`【${TITLE}】`);
  console.log(`开始时间：${nowText()}`);
  console.log(`运行模式：${dryRun ? 'DRY_RUN（完全断网）' : 'LIVE'}`);
  console.log(`账号数量：${accounts.length}`);
  console.log('========================================');

  log('阶段 1/3：配置检查');
  const configStarted = Date.now();
  let configurationError = false;
  if (!accounts.length) {
    configurationError = true;
    log(`❌ 配置错误：缺少 ${CREDENTIAL_ENV} 的非空账号行`);
  } else {
    for (const account of accounts) {
      if (!account.valid) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} 格式无效，应为「邮箱,密码」或「备注|邮箱,密码」`);
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`
  );

  if (!configurationError) {
    log('阶段 2/3：账号登录与签到');
    for (let i = 0; i < accounts.length; i++) {
      const account = accounts[i];
      const began = Date.now();
      const who = account.label ? `（${account.label}）` : '';
      let loginOutcome = 'failure';
      let checkinOutcome = 'failure';
      summary.tasks.total += 2;

      log(`账号 ${account.index}${who} | 子阶段 1/2：登录`);
      try {
        if (dryRun) {
          loginOutcome = 'skipped';
          log('⏭️ DRY_RUN_OK：凭据格式通过；未请求登录接口');
        } else {
          const token = await login(account);
          loginOutcome = 'success';
          log(`✅ 登录成功（已获取会话，不输出 Token）`);

          log(`账号 ${account.index}${who} | 子阶段 2/2：签到`);
          const result = await checkin(token, account.index);
          checkinOutcome = result.state;
          if (result.state === 'success') log(`✅ ${result.message}`);
          else log(`☑️ ${result.message}`);
        }
        if (dryRun) {
          log(`账号 ${account.index}${who} | 子阶段 2/2：签到`);
          checkinOutcome = 'skipped';
          log('⏭️ DRY_RUN_OK：未请求签到接口，未验证真实业务');
        }
      } catch (err) {
        const message = reasonText(err && err.message);
        if (loginOutcome === 'failure') {
          log(`❌ ${message}；未确认登录成功`);
          checkinOutcome = 'skipped';
          log(`账号 ${account.index}${who} | 子阶段 2/2：签到 ⏭️ 因登录失败跳过`);
        } else {
          log(`❌ ${message}；未确认签到成功`);
          checkinOutcome = 'failure';
        }
      }

      for (const outcome of [loginOutcome, checkinOutcome]) {
        if (outcome === 'success') summary.tasks.success += 1;
        else if (outcome === 'alreadyComplete') summary.tasks.alreadyComplete += 1;
        else if (outcome === 'skipped') summary.tasks.skipped += 1;
        else summary.tasks.failure += 1;
      }

      const accountFailed = loginOutcome === 'failure' || checkinOutcome === 'failure';
      if (accountFailed) summary.failedAccounts += 1;
      else summary.successfulAccounts += 1;

      log(
        `账号 ${account.index} 统计：总任务 2 | 成功 ${+(loginOutcome === 'success') + +(checkinOutcome === 'success')} | 已完成 ${+(
          checkinOutcome === 'alreadyComplete'
        )} | 跳过 ${+(loginOutcome === 'skipped') + +(checkinOutcome === 'skipped')} | 失败 ${+(
          loginOutcome === 'failure'
        ) + +(checkinOutcome === 'failure')} | 耗时 ${Date.now() - began}ms`
      );

      if (!dryRun && i < accounts.length - 1) await sleep(ACCOUNT_GAP_MS);
    }
  }

  const exitCode = configurationError || summary.failedAccounts ? 1 : 0;
  summary.status = configurationError
    ? 'configuration-error'
    : summary.failedAccounts
      ? summary.successfulAccounts
        ? 'partial-failure'
        : 'failure'
      : dryRun
        ? 'dry-run'
        : 'success';

  const body =
    `状态：${summary.status}；账号总数：${summary.accounts}；成功数：${summary.successfulAccounts}；` +
    `失败数：${summary.failedAccounts}；签到成功：${summary.tasks.success}；已完成：${summary.tasks.alreadyComplete}；` +
    `预演跳过：${summary.tasks.skipped}`;

  log('阶段 3/3：脱敏总结通知');
  const notifyStarted = Date.now();
  summary.notification = await sendNotify(body, dryRun);
  log(`阶段 3 完成：${summary.notification} | 耗时 ${Date.now() - notifyStarted}ms`);

  summary.durationMs = Date.now() - started;
  summary.finishedAt = nowText();
  console.log('----------------------------------------');
  log(body);
  log(
    `子任务统计：总数 ${summary.tasks.total} | 成功 ${summary.tasks.success} | 已完成 ${summary.tasks.alreadyComplete} | 跳过 ${summary.tasks.skipped} | 失败 ${summary.tasks.failure}`
  );
  log(
    `总耗时：${summary.durationMs}ms | 完成时间：${summary.finishedAt} | 通知状态：${summary.notification} | 最终状态：${summary.status}`
  );
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
}

if (require.main === module) {
  main().catch(() => {
    process.exitCode = 1;
    console.error('任务执行异常（已脱敏）');
  });
}

module.exports = {
  parseAccounts,
  extractTokenFromSetCookie,
  unwrapPayload,
  wrapPayload,
  md5,
};
