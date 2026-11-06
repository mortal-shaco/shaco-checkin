// name: HayFrp每日签到
// cron: 35 1 * * *
/**
 * HayFrp 每日签到领流量 · 青龙独立维护版
 *
 * 上游：luckylemonade24/hayfrp-auto-sign · src/index.ts（含同仓 src/utils.ts 签到实现）
 * 仓库：https://github.com/luckylemonade24/hayfrp-auto-sign.git
 * 分支：main
 * 提交：7742926094b8655170d4e2186b268f29deb52051
 * 授权：MIT
 *
 * 功能盘点（主来源 Cloudflare Workers 入口 + utils 签到逻辑；maintainedFeatureCoverage 为空，无重复覆盖）：
 * - 使用 HayFrp 用户名/密码登录 api.hayfrp.com/user（type=login），校验业务 status=200 与 csrf token
 * - 使用 csrf 调用 type=sign 签到；成功返回当日流量与总流量；status=403 视为当日已签到
 * - 可选 Discord Webhook 推送签到摘要（上游 WEBHOOK_URL）；默认不启用
 * - 上游 ACCESS_KEY HTTP 触发与 Workers 入口已移除，改为青龙 cron 调度
 * - 多账号：由 JSON USERS 改为每行一个「用户名,密码」；任一账号失败整体非零退出
 *
 * HAYFRP_ACCOUNTS（必填）：每行一个账号，格式「用户名,密码」；只在第一个逗号处拆分，
 * 密码中后续逗号原样保留。可选备注：「备注|用户名,密码」，只在首个 | 处拆分。
 * 不使用 & 或 @ 分隔账号。
 * HAYFRP_API_URL（可选）：HayFrp API 根地址，默认 https://api.hayfrp.com
 * HAYFRP_WEBHOOK_URL（可选）：Discord Webhook；未设置或 disabled 则跳过；预演不请求
 * HAYFRP_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）
 * HAYFRP_TIMEOUT_MS：请求超时毫秒，默认 20000（1000–60000）
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略
 *
 * Copyright (c) 2025 wyf9
 * Copyright (c) 2026 Qinglong maintained adaptation
 *
 * MIT License — see upstream LICENSE.
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
    const identities = ["2c89474a11ce9592", "scripts/task_2c89474a.js", "task_2c89474a.js", "task_2c89474a"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end

const https = require('node:https');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { URL } = require('node:url');
const { execFile } = require('node:child_process');

const TITLE = 'HayFrp每日签到';
const CATALOG_ID = '2c89474a11ce9592';
const CREDENTIAL_ENV = 'HAYFRP_ACCOUNTS';
const DRY_RUN_ENV = 'HAYFRP_DRY_RUN';
const DEFAULT_API_URL = 'https://api.hayfrp.com';
const DEFAULT_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 256 * 1024;
const ACCOUNT_GAP_MS = 1500;
const MAX_RETRIES = 3;

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

function redact(value) {
  let text = String(value == null ? '' : value).replace(
    /[\r\n\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    ' '
  );
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
    if (secret) text = text.split(secret).join('[已隐藏]');
  }
  text = text.replace(
    /(password|passwd|token|csrf|authorization|cookie)=([^&\s,;]+)/gi,
    '$1=[已隐藏]'
  );
  text = text.replace(/https:\/\/discord(?:app)?\.com\/api\/webhooks\/\S+/gi, '[Webhook已隐藏]');
  text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.HAYFRP_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000 ? value : DEFAULT_TIMEOUT_MS;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function apiBaseUrl() {
  const raw = String(process.env.HAYFRP_API_URL || DEFAULT_API_URL).trim() || DEFAULT_API_URL;
  return raw.endsWith('/') ? raw.slice(0, -1) : raw;
}

function webhookConfigured() {
  const raw = String(process.env.HAYFRP_WEBHOOK_URL || '').trim();
  if (!raw || /^disabled$/i.test(raw)) return '';
  return raw;
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
    'scripts/hayfrp_auto_sign.js',
    'hayfrp_auto_sign.js',
    'hayfrp-auto-sign.js',
    'hayfrp',
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
    let label = '';
    let credential = line;
    const pipe = line.indexOf('|');
    if (pipe > 0) {
      label = line.slice(0, pipe).trim();
      credential = line.slice(pipe + 1).trim();
    }
    const comma = credential.indexOf(',');
    const username = comma < 0 ? '' : credential.slice(0, comma).trim();
    const password = comma < 0 ? '' : credential.slice(comma + 1);
    remember(password);
    const usernameOk = username.length > 0 && !/[\r\n]/.test(username);
    const passwordOk = password.length > 0 && !/[\r\n]/.test(password);
    return {
      index: index + 1,
      label,
      username,
      password,
      valid: usernameOk && passwordOk,
    };
  });
}

function httpRequest(urlString, { method = 'GET', headers = {}, body = null } = {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
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
        timeout: timeoutMs(),
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

async function fetchWithRetry(urlString, options, retries = MAX_RETRIES) {
  let lastError = null;
  for (let left = retries; left > 0; left--) {
    try {
      const resp = await httpRequest(urlString, options);
      if (resp.statusCode === 429 && left > 1) {
        const retryAfter = Number(resp.headers['retry-after']) || 1;
        await sleep(Math.min(Math.max(retryAfter, 1), 30) * 1000);
        continue;
      }
      if ((resp.statusCode < 200 || resp.statusCode >= 300) && left > 1) {
        await sleep(1000);
        continue;
      }
      return resp;
    } catch (err) {
      lastError = err;
      if (left === 1) throw err;
      await sleep(1000);
    }
  }
  throw lastError || new Error('max-retries');
}

async function sendApiRequest(route, data) {
  const url = `${apiBaseUrl()}/${String(route || '').replace(/^\//, '')}`;
  const resp = await fetchWithRetry(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json;charset=UTF-8',
      Accept: 'application/json,text/plain,*/*',
      // 与上游一致：绕过雷池防火墙标记
      waf: 'off',
    },
    body: JSON.stringify(data || {}),
  });
  if (resp.statusCode < 200 || resp.statusCode >= 300) {
    throw new Error(`http-${resp.statusCode}`);
  }
  let json;
  try {
    json = JSON.parse(resp.text);
  } catch {
    throw new Error('non-json');
  }
  return json;
}

function businessMessage(payload) {
  if (!payload || typeof payload !== 'object') return '';
  const msg = payload.message || payload.msg || payload.error || '';
  return typeof msg === 'string' ? msg : String(msg || '');
}

async function doSign(account) {
  const login = await sendApiRequest('user', {
    type: 'login',
    user: account.username,
    passwd: account.password,
  });
  const loginStatus = Number(login && login.status);
  if (loginStatus === 403) throw new Error('login-business:密码错误 (403)');
  if (loginStatus === 404) throw new Error('login-business:用户不存在 (404)');
  if (loginStatus === 500) throw new Error('login-business:服务端错误 (500)');
  if (loginStatus !== 200) {
    throw new Error(`login-business:未知登录状态码 ${loginStatus || '缺失'}`);
  }
  const token = login && login.token;
  if (!token || typeof token !== 'string') throw new Error('login-business:未返回 csrf token');
  remember(token);

  const identityFields = ['username', 'nickname', 'name', 'uid', 'id', 'user'];
  let officialIdentity = '';
  for (const field of identityFields) {
    const value = login[field];
    if ((typeof value === 'string' && value) || typeof value === 'number') {
      officialIdentity = String(value);
      break;
    }
  }

  const sign = await sendApiRequest('user', {
    type: 'sign',
    csrf: token,
  });
  const signStatus = Number(sign && sign.status);
  if (signStatus === 200) {
    const gained = sign.signflow != null ? sign.signflow : sign.flow;
    const total = sign.flow;
    return {
      state: 'success',
      message: businessMessage(sign) || '签到成功',
      sign: gained,
      total,
      identity: officialIdentity || account.username,
    };
  }
  if (signStatus === 403) {
    return {
      state: 'alreadyComplete',
      message: businessMessage(sign) || '今日已签到',
      sign: null,
      total: sign && sign.flow != null ? sign.flow : null,
      identity: officialIdentity || account.username,
    };
  }
  if (signStatus === 404) throw new Error('sign-business:Token 失效 (404)');
  if (signStatus === 500) throw new Error('sign-business:服务端错误 (500)');
  throw new Error(`sign-business:未知签到状态码 ${signStatus || '缺失'}`);
}

async function sendDiscordWebhook(payload, dryRun) {
  const url = webhookConfigured();
  if (!url) return '未配置 Discord Webhook';
  if (!/^https:\/\//i.test(url)) throw new Error('webhook-insecure');
  if (dryRun) return 'Webhook 预演已跳过真实投递（断网）';
  remember(url);
  const resp = await fetchWithRetry(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (resp.statusCode < 200 || resp.statusCode >= 300) {
    throw new Error(`webhook-http-${resp.statusCode}`);
  }
  return 'Discord Webhook 已发送';
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
    delete env.HAYFRP_ACCOUNTS;
    delete env.HAYFRP_WEBHOOK_URL;
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
    delete env.HAYFRP_ACCOUNTS;
    delete env.HAYFRP_WEBHOOK_URL;
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
    'non-json': '接口返回非 JSON',
    'max-retries': '超过最大重试次数',
    'webhook-insecure': 'Discord Webhook 必须使用 HTTPS',
  };
  if (map[code]) return map[code];
  if (String(code).startsWith('login-business:')) {
    return `登录失败：${redact(String(code).slice('login-business:'.length))}`;
  }
  if (String(code).startsWith('sign-business:')) {
    return `签到失败：${redact(String(code).slice('sign-business:'.length))}`;
  }
  if (String(code).startsWith('webhook-http-')) {
    return `Webhook HTTP 状态异常：${String(code).slice('webhook-http-'.length)}`;
  }
  if (String(code).startsWith('http-')) return `HTTP 状态异常：${String(code).slice(5)}`;
  return redact(code || '请求失败');
}

async function processAccount(account, dryRun, summary) {
  const began = Date.now();
  const who = account.label ? `（${account.label}）` : '';
  const accountStats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
  let identity = account.label || account.username || `账号${account.index}`;
  let failed = false;
  let note = '';

  log(`账号 ${account.index}${who} | 子阶段 1/2：登录并签到`);
  accountStats.total += 1;
  if (dryRun) {
    accountStats.skipped += 1;
    note = 'DRY_RUN_OK：凭据格式通过；未请求 HayFrp API';
    log(`⏭️ ${note}`);
  } else {
    try {
      const result = await doSign(account);
      identity = result.identity || identity;
      log(`账号 ${account.index} 官方身份（username）：${identity}`);
      if (result.state === 'success') {
        accountStats.success += 1;
        note = `签到成功：+${result.sign} GB，总流量 ${result.total} GB — ${redact(result.message)}`;
        log(`✅ ${note}`);
      } else {
        accountStats.alreadyComplete += 1;
        note =
          result.total != null
            ? `今日已签到：总流量 ${result.total} GB — ${redact(result.message)}`
            : `今日已签到 — ${redact(result.message)}`;
        log(`☑️ ${note}`);
      }
    } catch (err) {
      accountStats.failure += 1;
      failed = true;
      note = reasonText(err && err.message);
      log(`❌ ${note}；未确认签到成功`);
    }
  }

  log(`账号 ${account.index}${who} | 子阶段 2/2：可选 Discord Webhook`);
  accountStats.total += 1;
  if (dryRun) {
    accountStats.skipped += 1;
    log('⏭️ DRY_RUN_OK：未请求 Discord Webhook');
  } else if (failed) {
    accountStats.skipped += 1;
    log('⏭️ 因签到失败跳过 Discord Webhook');
  } else if (!webhookConfigured()) {
    accountStats.skipped += 1;
    log('⏭️ 未配置 HAYFRP_WEBHOOK_URL，跳过 Discord Webhook');
  } else {
    try {
      const title =
        accountStats.success > 0
          ? `[${identity}] HayFrp Auto Sign Finished!`
          : `[${identity}] (HayFrp) Already signed!`;
      const webhookResult = await sendDiscordWebhook(
        {
          embeds: [
            {
              title,
              description: redact(note),
            },
          ],
        },
        dryRun
      );
      accountStats.success += 1;
      log(`✅ ${webhookResult}`);
    } catch (err) {
      accountStats.failure += 1;
      failed = true;
      log(`❌ Discord Webhook 失败：${reasonText(err && err.message)}`);
    }
  }

  summary.tasks.total += accountStats.total;
  summary.tasks.success += accountStats.success;
  summary.tasks.alreadyComplete += accountStats.alreadyComplete;
  summary.tasks.skipped += accountStats.skipped;
  summary.tasks.failure += accountStats.failure;
  if (failed) summary.failedAccounts += 1;
  else summary.successfulAccounts += 1;

  log(
    `账号 ${account.index}（${identity}）统计：总任务 ${accountStats.total} | 成功 ${accountStats.success} | 已完成 ${accountStats.alreadyComplete} | 跳过 ${accountStats.skipped} | 失败 ${accountStats.failure} | 耗时 ${Date.now() - began}ms`
  );
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
        log(`❌ 配置错误：账号 ${account.index} 格式无效，应为「用户名,密码」或「备注|用户名,密码」`);
      }
    }
  }

  const apiUrl = apiBaseUrl();
  if (!/^https:\/\//i.test(apiUrl)) {
    configurationError = true;
    log('❌ 配置错误：HAYFRP_API_URL 必须是 https:// 开头');
  } else {
    log(`API 地址：${apiUrl}`);
  }

  const webhook = webhookConfigured();
  if (webhook && !/^https:\/\//i.test(webhook)) {
    configurationError = true;
    log('❌ 配置错误：HAYFRP_WEBHOOK_URL 必须是 https:// 开头（或 disabled）');
  } else if (webhook) {
    log('Discord Webhook：已配置（地址已脱敏）');
  }

  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`
  );

  if (!configurationError) {
    log('阶段 2/3：账号签到');
    for (let i = 0; i < accounts.length; i++) {
      await processAccount(accounts[i], dryRun, summary);
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
  apiBaseUrl,
  doSign,
  redact,
};
