// name: HayFrp 每日签到
// cron: 34 1 * * *
/**
 * HayFrp 自动签到获取流量 · 青龙独立维护版
 *
 * 上游：wyf9/hayfrp-auto-sign · src/index.ts + src/utils.ts
 * 仓库：https://github.com/wyf9/hayfrp-auto-sign.git
 * 分支：main
 * 提交：f9b99a6c6465b276772ab7d4621ed49fde0aa4f5
 * 授权：MIT（Copyright (c) 2025 wyf9）
 *
 * 功能盘点（主来源；maintainedFeatureCoverage 为空，项目内无已发布同产品脚本）：
 * - 使用 HayFrp 用户名与密码调用官方 API 登录（type=login）
 * - 使用登录返回的 csrf/token 执行每日签到（type=sign），领取流量
 * - 识别今日已签到（业务码 403）与登录失败（403/404/500 等）
 * - 多账号：上游为 JSON USERS 数组；维护版改为每行一个账号
 * - Cloudflare Workers 定时/HTTP 入口、ACCESS_KEY、Discord WEBHOOK 改为青龙 cron + 脱敏通知
 * - 无发帖/评论等公开内容副作用
 *
 * HAYFRP_ACCOUNTS（必填）：每行一个账号，格式「用户名,密码」；只在第一个逗号处拆分，
 * 密码中后续逗号原样保留。可选备注：「备注|用户名,密码」，只在首个 | 处拆分。
 * 不使用 & 或 @ 分隔账号。凭据为 https://console.hayfrp.com 本人登录账号。
 * HAYFRP_API_URL（可选）：API 根地址，默认 https://api.hayfrp.com。
 * HAYFRP_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）。
 * HAYFRP_TIMEOUT_MS：请求超时毫秒，默认 20000（1000–60000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 * Copyright (c) 2025 wyf9
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
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = [
      '81b701d12d5b39f2',
      'scripts/hayfrp_auto_sign.js',
      'hayfrp_auto_sign.js',
      'hayfrp-auto-sign',
      'hayfrp',
      'candidate.js',
    ];
    enabled = selectors.some((selector) => {
      const pattern =
        '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
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

const TITLE = 'HayFrp 每日签到';
const CATALOG_ID = '81b701d12d5b39f2';
const CREDENTIAL_ENV = 'HAYFRP_ACCOUNTS';
const DRY_RUN_ENV = 'HAYFRP_DRY_RUN';
const DEFAULT_API = 'https://api.hayfrp.com';
const DEFAULT_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 1024 * 1024;

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
  text = text.replace(/(passwd|password|token|csrf|Authorization)=([^;\s&]+)/gi, '$1=[已隐藏]');
  text = text.replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.HAYFRP_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000 ? value : DEFAULT_TIMEOUT_MS;
}

function apiBase() {
  const raw = String(process.env.HAYFRP_API_URL || DEFAULT_API).trim() || DEFAULT_API;
  return raw.endsWith('/') ? raw.slice(0, -1) : raw;
}

function notificationSelected() {
  if (disabled(process.env.QINGLONG_NOTIFY)) return false;
  if (enabled(process.env.QINGLONG_NOTIFY)) return true;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const raw = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (String(raw).trim() === '') return false;
  const selectors = String(raw).split(/[,;\s]+/).filter(Boolean);
  if (selectors.includes('*')) return true;
  const filename = path.basename(process.argv[1] || 'candidate.js');
  const names = [
    CATALOG_ID,
    'scripts/hayfrp_auto_sign.js',
    'hayfrp_auto_sign.js',
    'hayfrp-auto-sign',
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
    remember(line);
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

async function sendApiRequest(route, data) {
  const base = apiBase();
  const url = `${base}/${String(route || '').replace(/^\//, '')}`;
  const response = await httpRequest(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json;charset=UTF-8',
      Accept: 'application/json, text/plain, */*',
      'User-Agent': 'hayfrp-auto-sign/qinglong',
      waf: 'off',
    },
    body: JSON.stringify(data || {}),
  });
  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new Error(`http-${response.statusCode}`);
  }
  let json;
  try {
    json = JSON.parse(response.text);
  } catch {
    throw new Error('invalid-json');
  }
  return json;
}

function pickIdentity(account, loginResp) {
  const bags = [loginResp].filter((v) => v && typeof v === 'object');
  for (const bag of bags) {
    for (const key of ['username', 'user', 'nickname', 'name', 'displayName', 'uid', 'id']) {
      if (bag[key] !== undefined && bag[key] !== null && String(bag[key]).trim()) {
        const value = String(bag[key]).trim();
        if (key === 'uid' || key === 'id') return value;
        return value;
      }
    }
  }
  return account.username || '';
}

async function runAccount(account) {
  const login = await sendApiRequest('user', {
    type: 'login',
    user: account.username,
    passwd: account.password,
  });
  const identity = pickIdentity(account, login);

  if (login.status === 403) {
    return { ok: false, state: 'failure', message: '密码错误（403）', identity };
  }
  if (login.status === 404) {
    return { ok: false, state: 'failure', message: '用户不存在（404）', identity };
  }
  if (login.status === 500) {
    return { ok: false, state: 'failure', message: '服务端错误（500）', identity };
  }
  if (login.status !== 200) {
    return {
      ok: false,
      state: 'failure',
      message: `登录失败（业务码 ${redact(login.status)}）`,
      identity,
    };
  }

  const token = login.token;
  if (!token || typeof token !== 'string') {
    return { ok: false, state: 'failure', message: '登录成功但未返回 token', identity };
  }
  remember(token);

  const sign = await sendApiRequest('user', {
    type: 'sign',
    csrf: token,
  });

  if (sign.status === 200) {
    const gained = sign.signflow != null ? sign.signflow : sign.flow;
    const total = sign.flow;
    const msg = redact(sign.message || '签到成功');
    const detail =
      `签到成功：${msg}` +
      (gained != null ? `；本次 +${redact(gained)} GB` : '') +
      (total != null ? `；当前流量 ${redact(total)} GB` : '');
    return { ok: true, state: 'success', message: detail, identity };
  }
  if (sign.status === 403) {
    return { ok: true, state: 'alreadyComplete', message: '今日已签到', identity };
  }
  if (sign.status === 404) {
    return { ok: false, state: 'failure', message: 'Token 失效（404）', identity };
  }
  if (sign.status === 500) {
    return { ok: false, state: 'failure', message: '签到服务端错误（500）', identity };
  }
  return {
    ok: false,
    state: 'failure',
    message: `签到失败（业务码 ${redact(sign.status)}）`,
    identity,
  };
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
  log(`阶段 1/3：配置检查 | API：${apiBase()}`);
  const configStarted = Date.now();
  let configurationError = false;

  if (!accounts.length) {
    configurationError = true;
    log(`❌ 配置错误：缺少 ${CREDENTIAL_ENV} 的非空账号行`);
  } else {
    for (const account of accounts) {
      if (!account.valid) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} 格式无效（需要「用户名,密码」）`);
      }
    }
  }

  try {
    const base = new URL(apiBase());
    if (base.protocol !== 'https:' && base.protocol !== 'http:') {
      configurationError = true;
      log('❌ 配置错误：HAYFRP_API_URL 协议无效');
    }
  } catch {
    configurationError = true;
    log('❌ 配置错误：HAYFRP_API_URL 不是合法 URL');
  }

  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${
      Date.now() - configStarted
    }ms`
  );

  if (!configurationError) {
    for (const account of accounts) {
      const began = Date.now();
      summary.tasks.total++;
      let outcome = 'failure';
      const who = account.label ? `（${redact(account.label)}）` : '';
      log(`账号 ${account.index}${who} | 阶段 2/3：登录并签到`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log(
            `⏭️ DRY_RUN_OK：账号格式通过（用户名长度 ${account.username.length}）；未请求网络，未验证真实业务`
          );
        } else {
          const result = await runAccount(account);
          if (result.identity) log(`账号 ${account.index} | 官方身份：${result.identity}`);
          if (result.ok && result.state === 'success') {
            outcome = 'success';
            log(`✅ ${result.message}`);
          } else if (result.ok && result.state === 'alreadyComplete') {
            outcome = 'alreadyComplete';
            log(`☑️ ${result.message}`);
          } else {
            outcome = 'failure';
            log(`❌ ${result.message}`);
          }
        }
      } catch (err) {
        const reasons = {
          timeout: '请求超时',
          'response-too-large': '响应过大',
          'network-error': '网络请求失败',
          'response-error': '响应读取失败',
          'response-aborted': '响应中断',
          'invalid-url': '地址无效',
          'invalid-json': '响应不是合法 JSON',
        };
        const code = err && err.message ? String(err.message) : '';
        if (code.startsWith('http-')) {
          log(`❌ HTTP 状态 ${code.slice(5)}；未确认签到成功`);
        } else {
          log(`❌ ${reasons[code] || '请求失败'}；未确认签到成功`);
        }
        outcome = 'failure';
      }
      summary.tasks[outcome]++;
      if (outcome === 'failure') summary.failedAccounts++;
      else summary.successfulAccounts++;
      log(
        `账号 ${account.index} 统计：总任务 1 | 成功 ${+(outcome === 'success')} | 已完成 ${+(
          outcome === 'alreadyComplete'
        )} | 跳过 ${+(outcome === 'skipped')} | 失败 ${+(outcome === 'failure')} | 耗时 ${
          Date.now() - began
        }ms`
      );
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
  apiBase,
  pickIdentity,
  redact,
};
