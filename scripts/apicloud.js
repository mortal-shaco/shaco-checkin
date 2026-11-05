#!/usr/bin/env node
// name: APICloud每日签到
// cron: 12 9 * * *
/**
 * APICloud 每日签到 · 青龙独立维护版
 *
 * 上游：fstg0504/apicloudsignin · app.js + appConfig.js
 * 仓库：https://github.com/fstg0504/apicloudsignin
 * 分支：master · 提交：4b091e769a333bf18f904cc2950a60fde760a278
 * 授权：MIT（Copyright (c) 2022 fstgshow）
 *
 * 功能盘点（主来源 app.js + 相关 appConfig.js）：
 * - 使用登录 Cookie 调用 www.apicloud.com：POST /api/user/checkin 签到
 * - 上游将 Cookie / sid 写死在 appConfig.js，并依赖 log4js 写本地 cheese.log
 * - 上游无超时、无失败退出码、打印原始响应、重复 require、Promise reject 未定义
 * - 相关源仅提供 API 地址与凭据占位；sid 字段未被主脚本使用，维护版不单独要求
 * - 无发帖/评论等公开内容副作用；无已维护同产品覆盖（maintainedFeatureCoverage 为空）
 *
 * APICLOUD_COOKIE（必填）：每行一个账号的完整 Cookie（通常含 ul_token、connect.sid）。
 * 获取：浏览器登录 https://www.apicloud.com → 打开开发者工具 Network →
 *   找到发往 www.apicloud.com 的已登录请求 → 复制完整 Cookie 请求头值。
 * 勿填写他人 Cookie，勿写入公开仓库或日志。
 * 可选备注：「备注|cookie」，只在首个竖线处拆分，后续 Cookie 原文保留。
 * 兼容别名：COOKIE（仅当 APICLOUD_COOKIE 为空时读取）。
 * APICLOUD_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）。
 * APICLOUD_TIMEOUT_MS：请求超时毫秒，默认 15000（1000–60000）。
 * APICLOUD_CHECKIN_URL：可选签到完整 HTTPS URL，默认
 *   https://www.apicloud.com/api/user/checkin
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Copyright (c) 2022 fstgshow
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
      '5abd6992fd7b03aa',
      'scripts/apicloud_checkin.js',
      'apicloud_checkin.js',
      'app.js',
      'apicloud',
      'candidate.js',
    ];
    enabled = selectors.some((selector) => {
      const pattern =
        '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  } else {
    enabled = true;
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

const TITLE = 'APICloud每日签到';
const CATALOG_ID = '5abd6992fd7b03aa';
const CREDENTIAL_ENV = 'APICLOUD_COOKIE';
const CREDENTIAL_ALIASES = ['COOKIE'];
const DRY_RUN_ENV = 'APICLOUD_DRY_RUN';
const DEFAULT_CHECKIN_URL = 'https://www.apicloud.com/api/user/checkin';
const DEFAULT_TIMEOUT_MS = 15000;
const MAX_RESPONSE_BYTES = 256 * 1024;
const ACCOUNT_GAP_MS = 800;

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

function rememberCookieParts(cookie) {
  remember(cookie);
  for (const part of String(cookie || '').split(';')) {
    const item = part.trim();
    if (!item) continue;
    remember(item);
    const eq = item.indexOf('=');
    if (eq > 0) remember(item.slice(eq + 1).trim());
  }
}

function redact(value) {
  let text = String(value == null ? '' : value).replace(
    /[\r\n\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    ' '
  );
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
    if (secret && secret.length >= 6) text = text.split(secret).join('[已隐藏]');
  }
  text = text.replace(/\b(ul_token|connect\.sid)=[^;\s]+/gi, '$1=[已隐藏]');
  text = text.replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._~+/=-]+/g, '[已隐藏]');
  text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function sanitizeDisplayText(value, fallback = '') {
  const text = String(value == null ? '' : value)
    .replace(/\s+/g, ' ')
    .trim();
  if (!text) return fallback;
  return text.length > 160 ? `${text.slice(0, 157)}...` : text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.APICLOUD_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000
    ? value
    : DEFAULT_TIMEOUT_MS;
}

function checkinUrl() {
  const raw = String(process.env.APICLOUD_CHECKIN_URL || '').trim();
  return raw || DEFAULT_CHECKIN_URL;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
    'scripts/apicloud_checkin.js',
    'apicloud_checkin.js',
    'app.js',
    'apicloud',
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

function normalizeCookie(raw) {
  let cookie = String(raw || '').trim();
  if (!cookie) return '';
  cookie = cookie.replace(/^Cookie\s*:\s*/i, '').trim();
  return cookie;
}

function cookieLooksValid(cookie) {
  if (!cookie || /[\x00-\x1f\x7f]/.test(cookie)) return false;
  if (cookie.length < 8 || cookie.length > 16384) return false;
  if (!/=/.test(cookie)) return false;
  if (/\r|\n/.test(cookie)) return false;
  return true;
}

function credentialRaw() {
  const primary = process.env[CREDENTIAL_ENV];
  if (primary != null && String(primary).trim() !== '') return String(primary);
  for (const alias of CREDENTIAL_ALIASES) {
    const value = process.env[alias];
    if (value != null && String(value).trim() !== '') return String(value);
  }
  return '';
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
    const cookie = normalizeCookie(credential);
    rememberCookieParts(cookie);
    return {
      index: index + 1,
      label,
      cookie,
      valid: cookieLooksValid(cookie),
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
    if (payload) {
      reqHeaders['Content-Length'] = String(payload.length);
      if (!reqHeaders['Content-Type'] && !reqHeaders['content-type']) {
        reqHeaders['Content-Type'] = 'application/json; charset=utf-8';
      }
    }
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
            headers: res.headers || {},
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

function authHeaders(cookie) {
  return {
    Accept: 'application/json, text/plain, */*',
    'Content-Type': 'application/json; charset=utf-8',
    Cookie: cookie,
    'User-Agent': 'Qinglong-APICloud-CheckIn/1.0',
  };
}

function parseJsonSafe(text) {
  try {
    return JSON.parse(String(text || ''));
  } catch {
    return null;
  }
}

function isAuthFailure(status, msg) {
  if (status === 401 || status === 403) return true;
  const text = String(msg || '');
  return /unauthorized|forbidden|invalid\s*(cookie|token|session)|login\s*(required|expired)|未登录|登录失效|鉴权失败|请先登录|cookie.*(无效|过期)/i.test(
    text
  );
}

function isAlreadyCheckedMessage(text) {
  const msg = String(text || '');
  if (!msg) return false;
  return /already\s*checked\s*in|already\s*check[\s-]*in|already\s*signed|今日已签|已经签到|已签到|重复签到/i.test(
    msg
  );
}

function isSuccessMessage(text) {
  const msg = String(text || '');
  if (!msg) return false;
  if (isAlreadyCheckedMessage(msg)) return false;
  if (/fail|error|invalid|denied|拒绝|失败|错误/i.test(msg)) return false;
  return /success|successful|check[\s-]*in|congrats|签到成功|打卡成功|成功/i.test(msg);
}

function pickIdentity(data) {
  if (!data || typeof data !== 'object') return '';
  const candidates = [data];
  if (data.data && typeof data.data === 'object') candidates.push(data.data);
  if (data.user && typeof data.user === 'object') candidates.push(data.user);
  if (data.result && typeof data.result === 'object') candidates.push(data.result);
  for (const obj of candidates) {
    for (const key of [
      'nickname',
      'nickName',
      'username',
      'userName',
      'displayName',
      'name',
      'uid',
      'userId',
      'id',
    ]) {
      if (obj[key] !== undefined && obj[key] !== null && String(obj[key]).trim()) {
        const value = String(obj[key]).trim();
        if (value.length > 64) continue;
        if (/^[A-Za-z0-9._~+/=-]{40,}$/.test(value) && !/^\d+$/.test(value)) continue;
        return value;
      }
    }
  }
  return '';
}

function summarizeResultPayload(payload) {
  if (!payload || typeof payload !== 'object') return '';
  const data =
    payload.data && typeof payload.data === 'object' && !Array.isArray(payload.data)
      ? payload.data
      : payload;
  const parts = [];
  for (const [label, key] of [
    ['连续签到', 'consecutiveDays'],
    ['连续签到', 'consecutive'],
    ['连续签到', 'streak'],
    ['累计签到', 'totalDays'],
    ['累计签到', 'total'],
    ['积分', 'points'],
    ['积分', 'point'],
    ['积分', 'score'],
    ['奖励', 'reward'],
    ['状态', 'status'],
    ['消息', 'msg'],
    ['消息', 'message'],
  ]) {
    if (data[key] !== undefined && data[key] !== null && String(data[key]).trim() !== '') {
      const text = sanitizeDisplayText(data[key]);
      if (text && !parts.some((p) => p.includes(text))) parts.push(`${label} ${text}`);
    }
  }
  return parts.join('；');
}

function classifyHttp(status) {
  if (status === 401 || status === 403) {
    return {
      ok: false,
      state: 'failure',
      message: `登录状态已失效（HTTP ${status}），请重新获取 Cookie`,
    };
  }
  if (!Number.isFinite(status) || status <= 0) {
    return { ok: false, state: 'failure', message: '请求失败（无有效 HTTP 状态）' };
  }
  if (status === 429) {
    return { ok: false, state: 'failure', message: '请求过于频繁（HTTP 429）' };
  }
  if (status >= 500) {
    return { ok: false, state: 'failure', message: `APICloud 服务暂时异常（HTTP ${status}）` };
  }
  if (status >= 400 && status < 500) {
    return { ok: false, state: 'failure', message: `请求被拒绝（HTTP ${status}）` };
  }
  if (status < 200 || status >= 300) {
    return { ok: false, state: 'failure', message: `请求失败（HTTP ${status}）` };
  }
  return null;
}

function classifyCheckInPayload(payload) {
  const msg = sanitizeDisplayText(
    payload && (payload.msg || payload.message || payload.error || payload.detail || '')
  );
  if (isAuthFailure(200, msg)) {
    return {
      ok: false,
      state: 'failure',
      message: msg || '登录状态已失效，请重新获取 Cookie',
    };
  }
  if (isAlreadyCheckedMessage(msg)) {
    return {
      ok: true,
      state: 'alreadyComplete',
      message: msg || '今日已签到',
    };
  }
  const code = payload && (payload.code ?? payload.status ?? payload.statusCode ?? payload.errno);
  if (
    code === 0 ||
    code === '0' ||
    code === 200 ||
    code === '200' ||
    code === 'ok' ||
    code === 'OK' ||
    code === true
  ) {
    return {
      ok: true,
      state: 'success',
      message: msg || '签到成功',
    };
  }
  if (isSuccessMessage(msg)) {
    return {
      ok: true,
      state: 'success',
      message: msg || '签到成功',
    };
  }
  if (msg && /fail|error|invalid|denied|拒绝|失败|错误/i.test(msg)) {
    return { ok: false, state: 'failure', message: msg };
  }
  if (payload && typeof payload === 'object') {
    const successFlag = payload.success ?? payload.ok ?? payload.result;
    if (successFlag === false || successFlag === 'false' || successFlag === 0) {
      return { ok: false, state: 'failure', message: msg || '签到失败' };
    }
    if (successFlag === true || successFlag === 'true' || successFlag === 1 || successFlag === '1') {
      return { ok: true, state: 'success', message: msg || '签到成功' };
    }
    // 上游仅打印 HTTP 状态与 data；HTTP 2xx 且无明确失败字段时视为成功
    return {
      ok: true,
      state: 'success',
      message: msg || '签到请求已接受',
    };
  }
  return {
    ok: false,
    state: 'failure',
    message: '签到接口返回了无法识别的业务响应',
  };
}

async function performCheckIn(cookie) {
  const response = await httpRequest(checkinUrl(), {
    method: 'POST',
    headers: authHeaders(cookie),
    body: '',
  });
  const httpFail = classifyHttp(Number(response.statusCode));
  if (httpFail) return { ...httpFail, identity: '', resultSummary: '' };
  const payload = parseJsonSafe(response.text);
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    const text = String(response.text || '').trim();
    if (!text) {
      return {
        ok: true,
        state: 'success',
        message: '签到请求已接受（空响应）',
        identity: '',
        resultSummary: '',
      };
    }
    if (isAlreadyCheckedMessage(text)) {
      return {
        ok: true,
        state: 'alreadyComplete',
        message: sanitizeDisplayText(text),
        identity: '',
        resultSummary: '',
      };
    }
    if (isSuccessMessage(text) || /ok|done|checked/i.test(text)) {
      return {
        ok: true,
        state: 'success',
        message: sanitizeDisplayText(text) || '签到成功',
        identity: '',
        resultSummary: '',
      };
    }
    return {
      ok: false,
      state: 'failure',
      message: '签到接口返回了无法识别的非 JSON 响应',
      identity: '',
      resultSummary: '',
    };
  }
  const classified = classifyCheckInPayload(payload);
  return {
    ...classified,
    identity: pickIdentity(payload),
    resultSummary: summarizeResultPayload(payload),
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
    delete env[CREDENTIAL_ENV];
    for (const alias of CREDENTIAL_ALIASES) delete env[alias];
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
    delete env[CREDENTIAL_ENV];
    for (const alias of CREDENTIAL_ALIASES) delete env[alias];
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
  const accounts = parseAccounts(credentialRaw());
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
  log(`阶段 1/3：配置检查 | API：${checkinUrl()}`);
  const configStarted = Date.now();
  let configurationError = false;

  if (!accounts.length) {
    configurationError = true;
    log(
      `❌ 配置错误：缺少 ${CREDENTIAL_ENV}（或兼容变量 ${CREDENTIAL_ALIASES.join(
        ' / '
      )}）的非空 Cookie 行`
    );
  } else {
    for (const account of accounts) {
      if (!account.valid) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} Cookie 格式无效`);
      }
    }
  }

  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ Cookie 行已读取'} | 耗时 ${
      Date.now() - configStarted
    }ms`
  );

  if (!configurationError) {
    for (let i = 0; i < accounts.length; i++) {
      const account = accounts[i];
      const began = Date.now();
      summary.tasks.total++;
      let outcome = 'failure';
      const labelHint = account.label ? `（${sanitizeDisplayText(account.label)}）` : '';
      log(`账号 ${account.index}${labelHint} | 阶段 2/3：每日签到`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log(
            `⏭️ DRY_RUN_OK：账号 ${account.index} Cookie 格式通过（长度 ${account.cookie.length}）；未请求网络，未验证真实业务`
          );
        } else {
          const result = await performCheckIn(account.cookie);
          if (result.identity) {
            log(`账号 ${account.index} | 官方身份：${sanitizeDisplayText(result.identity)}`);
          }
          if (result.resultSummary) {
            log(`账号 ${account.index} | 结果摘要：${redact(result.resultSummary)}`);
          }
          if (result.ok && result.state === 'success') {
            outcome = 'success';
            log(`✅ ${redact(result.message)}`);
          } else if (result.ok && result.state === 'alreadyComplete') {
            outcome = 'alreadyComplete';
            log(`☑️ ${redact(result.message)}`);
          } else {
            outcome = 'failure';
            log(`❌ ${redact(result.message)}`);
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
        };
        const code = err && err.message ? String(err.message) : '';
        log(`❌ ${reasons[code] || '请求失败'}；未确认签到成功`);
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
  cookieLooksValid,
  classifyCheckInPayload,
  CREDENTIAL_ENV,
  DRY_RUN_ENV,
};
