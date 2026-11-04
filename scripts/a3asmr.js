// name: 爱上ASMR每日签到
// cron: 15 9 * * *
/**
 * 爱上ASMR（a3asmr.com）每日签到 · 青龙独立维护版
 *
 * 上游：igugyj/AutoSign · src/sites/a3asmr/index.ts + config.ts
 * 仓库：https://github.com/igugyj/AutoSign.git
 * 提交：dda144379a6bbec3b450113c5282d5d40ff488c9
 * 授权：MIT（Copyright (c) 2026 Pfolg）
 *
 * 功能盘点（主来源 + related config）：
 * - 携带登录 Cookie 访问 /mission，从页面 dtapi 提取 rest_url 与 wp_rest nonce
 * - POST {rest_url}as/v1/userMission?_wpnonce=... 完成每日签到
 * - 识别按钮「已签到」/ API success=1 / msg「已经签到」
 * - 浏览器扩展同域凭据改为青龙环境变量 Cookie；无发帖/评论等公开内容副作用
 *
 * A3ASMR_COOKIE（必填）：浏览器登录 https://www.a3asmr.com/ 后，开发者工具→网络，
 * 复制发往本站请求的完整 Cookie。每个非空行一个账号；可选「备注|Cookie」，
 * 仅在首个 | 处拆分。不使用 & 或 @ 分隔账号。
 * A3ASMR_BASE_URL：可选站点根地址，默认 https://www.a3asmr.com
 * A3ASMR_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知。
 * A3ASMR_TIMEOUT_MS：请求超时毫秒，默认 20000（1000–60000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 * Copyright (c) 2026 Pfolg
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
    const identities = ["7453e17a3ed8abac", "scripts/a3asmr.js", "a3asmr.js", "a3asmr"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');
const { execFile } = require('child_process');

const TITLE = '爱上ASMR每日签到';
const CATALOG_ID = '7453e17a3ed8abac';
const CREDENTIAL_ENV = 'A3ASMR_COOKIE';
const DRY_RUN_ENV = 'A3ASMR_DRY_RUN';
const DEFAULT_BASE = 'https://www.a3asmr.com';
const API_ENDPOINT = 'as/v1/userMission';
const MISSION_PATH = '/mission';
const USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const DEFAULT_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const MAX_REDIRECTS = 5;

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

function timeoutMs() {
  const value = Number.parseInt(process.env.A3ASMR_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000 ? value : DEFAULT_TIMEOUT_MS;
}

function notificationSelected() {
  if (disabled(process.env.QINGLONG_NOTIFY)) return false;
  if (enabled(process.env.QINGLONG_NOTIFY)) return true;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const raw = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (String(raw).trim() === '') return false;
  const selectors = String(raw).split(/[,;\s]+/).filter(Boolean);
  if (selectors.includes('*')) return true;
  const names = [
    CATALOG_ID,
    'scripts/a3asmr_checkin.js',
    'a3asmr_checkin.js',
    path.basename(process.argv[1] || 'candidate.js'),
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
    let cookie = line;
    const pipe = line.indexOf('|');
    if (pipe > 0) {
      label = line.slice(0, pipe).trim();
      cookie = line.slice(pipe + 1).trim();
    }
    return { index: index + 1, label, cookie };
  });
}

function cookieLooksValid(cookie) {
  if (!cookie || /[\x00-\x1f\x7f]/.test(cookie)) return false;
  return /^[^=;\s]+=\S/.test(cookie);
}

function resolveUrl(baseUrl, target) {
  if (!target) return baseUrl;
  try {
    return new URL(target, baseUrl.endsWith('/') ? baseUrl : baseUrl + '/').toString();
  } catch {
    return null;
  }
}

function httpRequest(urlString, { method = 'GET', headers = {}, body = null, cookie, timeout } = {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let redirects = 0;
    const deadline = Date.now() + (timeout || timeoutMs());

    const fail = (code) => {
      if (settled) return;
      settled = true;
      reject(new Error(code));
    };

    const go = (currentUrl, currentMethod, currentBody) => {
      let parsed;
      try {
        parsed = new URL(currentUrl);
      } catch {
        return fail('invalid-url');
      }
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return fail('invalid-url');
      const remaining = deadline - Date.now();
      if (remaining <= 0) return fail('timeout');
      const lib = parsed.protocol === 'https:' ? https : http;
      const payload = currentBody == null ? null : Buffer.from(String(currentBody), 'utf8');
      const reqHeaders = {
        'User-Agent': USER_AGENT,
        Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        Cookie: cookie,
        Referer: `${parsed.protocol}//${parsed.host}/`,
        Origin: `${parsed.protocol}//${parsed.host}`,
        ...headers,
      };
      if (payload) reqHeaders['Content-Length'] = payload.length;
      else delete reqHeaders['Content-Length'];
      if (currentMethod === 'GET') delete reqHeaders['Content-Type'];

      const req = lib.request(
        {
          protocol: parsed.protocol,
          hostname: parsed.hostname,
          port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
          path: parsed.pathname + parsed.search,
          method: currentMethod,
          headers: reqHeaders,
        },
        (res) => {
          const status = res.statusCode || 0;
          if ([301, 302, 303, 307, 308].includes(status) && res.headers.location) {
            redirects += 1;
            if (redirects > MAX_REDIRECTS) {
              res.resume();
              return fail('too-many-redirects');
            }
            const next = resolveUrl(currentUrl, res.headers.location);
            res.resume();
            if (!next) return fail('invalid-url');
            const forceGet =
              status === 303 || ((status === 301 || status === 302) && currentMethod !== 'GET');
            const nextMethod = forceGet ? 'GET' : currentMethod;
            const nextBody = nextMethod === 'GET' ? null : currentBody;
            return go(next, nextMethod, nextBody);
          }
          let size = 0;
          const chunks = [];
          res.on('data', (chunk) => {
            size += chunk.length;
            if (size > MAX_RESPONSE_BYTES) {
              req.destroy();
              fail('response-too-large');
            } else chunks.push(chunk);
          });
          res.on('error', () => fail('response-error'));
          res.on('aborted', () => fail('response-aborted'));
          res.on('end', () => {
            if (settled) return;
            settled = true;
            resolve({
              status,
              body: Buffer.concat(chunks).toString('utf8'),
              url: currentUrl,
            });
          });
        }
      );
      const timer = setTimeout(() => {
        req.destroy();
        fail('timeout');
      }, remaining);
      req.on('close', () => clearTimeout(timer));
      req.on('error', () => fail('network-error'));
      if (payload) req.write(payload);
      req.end();
    };

    go(urlString, method, body);
  });
}

function extractDtapi(html) {
  const m = String(html || '').match(/var\s+dtapi\s*=\s*({[\s\S]*?});/);
  if (!m) return null;
  try {
    const parsed = JSON.parse(m[1]);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

function missionButtonState(html) {
  const m = String(html || '').match(
    /id\s*=\s*["']missionbtn["'][^>]*class\s*=\s*["']([^"']*)["'][^>]*>([\s\S]*?)<\/(?:a|button|div|span)/i
  );
  const alt = String(html || '').match(
    /id\s*=\s*["']missionbtn["'][^>]*>([\s\S]*?)<\/(?:a|button|div|span)/i
  );
  const cls = (m && m[1]) || '';
  const txt = ((m && m[2]) || (alt && alt[1]) || '').replace(/<[^>]+>/g, '').trim();
  const hasBtn = /id\s*=\s*["']missionbtn["']/i.test(html);
  return { hasBtn, cls, txt };
}

function detectLoginPage(html) {
  return (
    /id\s*=\s*["']loginform["']/i.test(html) ||
    /<body[^>]*class\s*=\s*["'][^"']*\blogin\b/i.test(html)
  );
}

function sanitizeMessage(value) {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  let text = String(value)
    .replace(/<[^>]*>/g, ' ')
    .replace(/bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [已隐藏]')
    .replace(/(?:cookie|token|session|authorization|_wpnonce|wp_rest)\s*[=:]\s*[^\s;,]+/gi, '[凭据已隐藏]')
    .replace(/\b1\d{10}\b/g, '[手机号已隐藏]')
    .replace(/[A-Za-z0-9_-]{48,}/g, '[敏感值已隐藏]')
    .replace(/\s+/g, ' ')
    .trim();
  return text.slice(0, 160);
}

function extractIdentity(html, cookie) {
  const secrets = String(cookie || '')
    .split(';')
    .map((part) => {
      const i = part.indexOf('=');
      return i >= 0 ? part.slice(i + 1).trim() : '';
    })
    .filter((v) => v.length >= 4);

  const patterns = [
    /display[_-]?name["']?\s*[:=]\s*["']([^"']{1,40})["']/i,
    /nickname["']?\s*[:=]\s*["']([^"']{1,40})["']/i,
    /用户名[：:\s]*([^\s<>'"]{2,40})/i,
    /昵称[：:\s]*([^\s<>'"]{2,40})/i,
    /欢迎[^<]{0,12}<a[^>]*>([^<]{1,40})</i,
    /uid["']?\s*[:=]\s*["']?(\d{1,12})/i,
  ];
  for (const re of patterns) {
    const m = String(html || '').match(re);
    if (!m) continue;
    const text = String(m[1] || '').trim();
    if (!text || text.length > 80 || /[\r\n\x00-\x1f\x7f]/.test(text)) continue;
    if (/(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text)) continue;
    if (/cookie|token|session|authorization|nonce/i.test(text)) continue;
    if (secrets.some((secret) => text.includes(secret))) continue;
    return text;
  }
  return null;
}

function parseApiResult(bodyText, status) {
  let data = null;
  try {
    data = JSON.parse(String(bodyText || '').replace(/^\uFEFF/, ''));
  } catch {
    return { ok: false, state: 'failure', message: '签到响应不是有效 JSON，无法验证业务成功' };
  }
  if (status < 200 || status >= 300) {
    const msg = data && typeof data === 'object' ? data.msg || data.message || data.code : '';
    return {
      ok: false,
      state: 'failure',
      message: `HTTP ${status}${msg ? '：' + sanitizeMessage(msg) : ''}`,
    };
  }
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    if (Number(data.success) === 1 || data.success === true) {
      const msg = sanitizeMessage(data.msg || data.message || '签到成功');
      return { ok: true, state: 'success', message: msg || '签到成功' };
    }
    const msg = sanitizeMessage(data.msg || data.message || '');
    if (msg && /已经签到|已签到|今日已签|重复签到/.test(msg)) {
      return { ok: true, state: 'alreadyComplete', message: msg };
    }
    return {
      ok: false,
      state: 'failure',
      message: msg || '签到失败：未返回可验证的成功标记',
    };
  }
  return { ok: false, state: 'failure', message: '签到响应结构无法识别' };
}

async function checkinAccount(account, baseUrl) {
  const missionUrl = resolveUrl(baseUrl, MISSION_PATH);
  if (!missionUrl) {
    return { ok: false, state: 'failure', message: '站点地址无效', identity: null };
  }

  const page = await httpRequest(missionUrl, { cookie: account.cookie });
  if (detectLoginPage(page.body)) {
    return {
      ok: false,
      state: 'failure',
      message: 'Cookie 已失效或未登录，请重新获取 Cookie',
      identity: null,
    };
  }

  const identity = extractIdentity(page.body, account.cookie);
  const btn = missionButtonState(page.body);
  if (
    btn.hasBtn &&
    (btn.cls.includes('signed') ||
      btn.cls.includes('singed') ||
      /已签到/.test(btn.txt))
  ) {
    return {
      ok: true,
      state: 'alreadyComplete',
      message: '今日已签到（页面状态）',
      identity,
    };
  }

  const dtapi = extractDtapi(page.body);
  if (!dtapi || !dtapi.rest_url || !dtapi.wp_rest) {
    if (!btn.hasBtn) {
      return {
        ok: false,
        state: 'failure',
        message: '未找到签到入口或 dtapi，站点可能改版或未登录',
        identity,
      };
    }
    return {
      ok: false,
      state: 'failure',
      message: 'mission 页面未提取到 dtapi.rest_url / wp_rest',
      identity,
    };
  }

  const restBase = String(dtapi.rest_url);
  const nonce = String(dtapi.wp_rest);
  const apiUrl = resolveUrl(restBase, `${API_ENDPOINT}?_wpnonce=${encodeURIComponent(nonce)}`);
  if (!apiUrl || !/^https?:\/\//i.test(apiUrl)) {
    return { ok: false, state: 'failure', message: 'REST 签到地址无效', identity };
  }

  const api = await httpRequest(apiUrl, {
    method: 'POST',
    headers: {
      Accept: 'application/json, text/plain, */*',
      'Content-Type': 'application/json',
      'X-WP-Nonce': nonce,
      Referer: missionUrl,
    },
    body: '',
    cookie: account.cookie,
  });

  const parsed = parseApiResult(api.body, api.status);
  return { ...parsed, identity };
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
    delete env.A3ASMR_COOKIE;
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
    delete env.A3ASMR_COOKIE;
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
  const baseUrl = String(process.env.A3ASMR_BASE_URL || DEFAULT_BASE).replace(/\/+$/, '') || DEFAULT_BASE;
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
  log(`阶段 1/3：配置检查 | 站点：${baseUrl}`);
  const configStarted = Date.now();
  let configurationError = false;

  if (!accounts.length) {
    configurationError = true;
    log(`❌ 配置错误：缺少 ${CREDENTIAL_ENV} 的非空账号行`);
  } else {
    for (const account of accounts) {
      if (!cookieLooksValid(account.cookie)) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} 的 Cookie 格式无效`);
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`
  );

  if (!configurationError) {
    for (const account of accounts) {
      const began = Date.now();
      summary.tasks.total++;
      let outcome = 'failure';
      const who = account.label ? `（${account.label}）` : '';
      log(`账号 ${account.index}${who} | 阶段 2/3：提取 nonce 并签到`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log('⏭️ DRY_RUN_OK：Cookie 格式通过；未请求网络，未验证真实业务');
        } else {
          const result = await checkinAccount(account, baseUrl);
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
          'too-many-redirects': '重定向过多',
          'invalid-url': '地址无效',
        };
        log(`❌ ${reasons[err.message] || '请求失败'}；未确认签到成功`);
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
  cookieLooksValid,
  extractDtapi,
  parseApiResult,
  missionButtonState,
};
