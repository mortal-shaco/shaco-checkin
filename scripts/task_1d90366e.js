#!/usr/bin/env node
// name: OpenLayer每日签到
// cron: 23 8,20 * * *
/**
 * OpenLayer 每日签到 · 青龙独立维护版
 *
 * 上游：dante4rt/openlayer-airdrop-bot · src/checkIn.js（合并同仓 src/userData.js）
 * 仓库：https://github.com/dante4rt/openlayer-airdrop-bot
 * 分支：main · 提交：2615961c4baff07dd8e4e60fa7995a297b3a3ea9
 * 授权：MIT（Copyright (c) 2024 Dante4rt）
 *
 * 功能盘点（主来源 checkIn.js + 同仓 userData.js / index.js）：
 * - 使用 Bearer Token 调用 OpenOracle Cloud Functions：GET userInfo、POST checkIn
 * - 展示官方返回的 X 显示名（xName）、X 用户名（xUsername）、钱包地址、当前积分、
 *   倍数、连续签到次数与宠物信息（非凭据身份字段直接展示）
 * - 识别今日已签到（msg 含 already checked in）与签到成功
 * - 上游 bearers.json 多账号 + 交互菜单 + 进程内 12 小时 cron；维护版改为青龙环境变量与 cron
 * - 上游无超时、无失败退出码、依赖 axios/moment/colors；维护版改用 Node 内置 HTTPS
 * - 无发帖/评论等公开内容副作用
 *
 * OPENLAYER_BEARER（必填）：每行一个账号的 Bearer Token（不含 “Bearer ” 前缀亦可，脚本会补全）。
 * 获取：打开 OpenLayer 扩展并登录 → 右键检查 → Console 执行
 *   console.log(localStorage.getItem('_open_layer_token_'))
 * 复制返回值。勿填写他人 Token，勿写入公开仓库或日志。
 * 可选备注：「备注|token」，只在首个竖线处拆分，后续 token 原文保留。
 * 兼容别名：OPENLAYER_TOKEN、BEARERS（仅当 OPENLAYER_BEARER 为空时读取；BEARERS 可为 JSON 数组文本）。
 * OPENLAYER_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）。
 * OPENLAYER_TIMEOUT_MS：请求超时毫秒，默认 15000（1000–60000）。
 * OPENLAYER_BASE_URL：可选 API 根地址，默认官方 Cloud Functions 地址。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Copyright (c) 2024 Dante4rt
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
    const identities = ["1d90366e2210d9c6", "scripts/task_1d90366e.js", "task_1d90366e.js", "task_1d90366e"];
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

const TITLE = 'OpenLayer每日签到';
const CATALOG_ID = '1d90366e2210d9c6';
const CREDENTIAL_ENV = 'OPENLAYER_BEARER';
const CREDENTIAL_ALIASES = ['OPENLAYER_TOKEN', 'BEARERS'];
const DRY_RUN_ENV = 'OPENLAYER_DRY_RUN';
const DEFAULT_BASE_URL = 'https://us-central1-openoracle-de73b.cloudfunctions.net';
const USERINFO_PATH = '/backend_apis/api/service/userInfo';
const CHECKIN_PATH = '/backend_apis/api/service/checkIn';
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

function redact(value) {
  let text = String(value == null ? '' : value).replace(
    /[\r\n\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    ' '
  );
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
    if (secret) text = text.split(secret).join('[已隐藏]');
  }
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
  const value = Number.parseInt(process.env.OPENLAYER_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000
    ? value
    : DEFAULT_TIMEOUT_MS;
}

function baseUrl() {
  const raw = String(process.env.OPENLAYER_BASE_URL || '').trim().replace(/\/+$/, '');
  return raw || DEFAULT_BASE_URL;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
    'scripts/openlayer_checkin.js',
    'openlayer_checkin.js',
    'checkIn.js',
    'openlayer',
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

function normalizeToken(raw) {
  let token = String(raw || '').trim();
  if (!token) return '';
  token = token.replace(/^Bearer\s+/i, '').trim();
  return token;
}

function tokenLooksValid(token) {
  if (!token || /[\x00-\x1f\x7f]/.test(token)) return false;
  if (token.length < 16 || token.length > 8192) return false;
  if (/\s/.test(token)) return false;
  return true;
}

function expandCredentialBlob(raw) {
  const text = String(raw || '').trim();
  if (!text) return '';
  if (text.startsWith('[')) {
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        return parsed
          .map((item) => String(item == null ? '' : item).trim())
          .filter(Boolean)
          .join('\n');
      }
    } catch {
      // 非 JSON 时按普通多行文本处理
    }
  }
  return String(raw || '');
}

function credentialRaw() {
  const primary = process.env[CREDENTIAL_ENV];
  if (primary != null && String(primary).trim() !== '') return expandCredentialBlob(primary);
  for (const alias of CREDENTIAL_ALIASES) {
    const value = process.env[alias];
    if (value != null && String(value).trim() !== '') return expandCredentialBlob(value);
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
    const token = normalizeToken(credential);
    remember(token);
    remember(`Bearer ${token}`);
    return {
      index: index + 1,
      label,
      token,
      valid: tokenLooksValid(token),
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
        reqHeaders['Content-Type'] = 'application/json';
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

function authHeaders(token) {
  return {
    Accept: 'application/json, text/plain, */*',
    Authorization: `Bearer ${token}`,
    'User-Agent': 'Qinglong-OpenLayer-CheckIn/1.0',
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
  return /unauthorized|forbidden|invalid\s*token|token\s*(expired|invalid)|未授权|登录失效|鉴权失败/i.test(
    text
  );
}

function isAlreadyCheckedMessage(text) {
  const msg = String(text || '');
  if (!msg) return false;
  return /already\s*checked\s*in|already\s*check[\s-]*in|今日已签|已经签到|已签到|重复签到/i.test(
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

function pickIdentity(userData) {
  if (!userData || typeof userData !== 'object') return '';
  for (const key of ['xName', 'xUsername', 'name', 'username', 'nickname', 'displayName']) {
    if (userData[key] !== undefined && userData[key] !== null && String(userData[key]).trim()) {
      return String(userData[key]).trim();
    }
  }
  const point = userData.point;
  if (point && typeof point === 'object' && point.address) {
    return String(point.address).trim();
  }
  return '';
}

function formatUserInfo(userData) {
  if (!userData || typeof userData !== 'object') return '未获取到用户信息';
  const parts = [];
  const xName = sanitizeDisplayText(userData.xName);
  const xUsername = sanitizeDisplayText(userData.xUsername);
  if (xName) parts.push(`名称 ${xName}`);
  if (xUsername) parts.push(`X @${xUsername}`);
  const point = userData.point && typeof userData.point === 'object' ? userData.point : {};
  if (point.address) parts.push(`地址 ${sanitizeDisplayText(point.address)}`);
  if (point.currentPoints != null && point.currentPoints !== '') {
    parts.push(`积分 ${sanitizeDisplayText(point.currentPoints)}`);
  }
  if (point.multiplier != null && point.multiplier !== '') {
    parts.push(`倍数 ${sanitizeDisplayText(point.multiplier)}x`);
  }
  if (point.consecutiveCheckinCount != null && point.consecutiveCheckinCount !== '') {
    parts.push(`连续签到 ${sanitizeDisplayText(point.consecutiveCheckinCount)}`);
  }
  const egg =
    userData.eggInfo &&
    userData.eggInfo.eggInfo &&
    typeof userData.eggInfo.eggInfo === 'object'
      ? userData.eggInfo.eggInfo
      : null;
  if (egg) {
    const eggParts = [];
    if (egg.name) eggParts.push(sanitizeDisplayText(egg.name));
    if (egg.type) eggParts.push(sanitizeDisplayText(egg.type));
    if (egg.info) eggParts.push(sanitizeDisplayText(egg.info));
    if (eggParts.length) parts.push(`宠物 [${eggParts.join(' | ')}]`);
  }
  return parts.length ? parts.join('；') : '用户信息字段为空';
}

function classifyHttp(status) {
  if (status === 401 || status === 403) {
    return {
      ok: false,
      state: 'failure',
      message: `登录状态已失效（HTTP ${status}），请重新获取 Bearer Token`,
    };
  }
  if (!Number.isFinite(status) || status <= 0) {
    return { ok: false, state: 'failure', message: '请求失败（无有效 HTTP 状态）' };
  }
  if (status === 429) {
    return { ok: false, state: 'failure', message: '请求过于频繁（HTTP 429）' };
  }
  if (status >= 500) {
    return { ok: false, state: 'failure', message: `OpenLayer 服务暂时异常（HTTP ${status}）` };
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
    payload && (payload.msg || payload.message || payload.error || '')
  );
  if (isAuthFailure(200, msg)) {
    return {
      ok: false,
      state: 'failure',
      message: msg || '登录状态已失效，请重新获取 Bearer Token',
    };
  }
  if (isAlreadyCheckedMessage(msg)) {
    return {
      ok: true,
      state: 'alreadyComplete',
      message: msg || '今日已签到',
    };
  }
  const code = payload && (payload.code ?? payload.status ?? payload.statusCode);
  if (code === 0 || code === '0' || code === 200 || code === '200' || code === 'ok' || code === 'OK') {
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
  // 上游仅用 msg 是否包含 already checked in 区分；其余非空业务 msg 视为成功
  if (msg) {
    return { ok: true, state: 'success', message: msg };
  }
  return {
    ok: false,
    state: 'failure',
    message: '签到接口返回了无法识别的业务响应',
  };
}

async function fetchUserInfo(token) {
  const response = await httpRequest(baseUrl() + USERINFO_PATH, {
    method: 'GET',
    headers: authHeaders(token),
  });
  const httpFail = classifyHttp(Number(response.statusCode));
  if (httpFail) return { ok: false, ...httpFail, userData: null };
  const payload = parseJsonSafe(response.text);
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return {
      ok: false,
      state: 'failure',
      message: '用户信息接口返回了无法识别的非 JSON 响应',
      userData: null,
    };
  }
  const userData =
    payload.data && typeof payload.data === 'object' && !Array.isArray(payload.data)
      ? payload.data
      : payload;
  const identity = pickIdentity(userData);
  const msg = sanitizeDisplayText(payload.msg || payload.message || '');
  if (isAuthFailure(Number(response.statusCode), msg)) {
    return {
      ok: false,
      state: 'failure',
      message: msg || '登录状态已失效，请重新获取 Bearer Token',
      userData: null,
      identity: '',
    };
  }
  return {
    ok: true,
    state: 'success',
    message: formatUserInfo(userData),
    userData,
    identity,
  };
}

async function performCheckIn(token) {
  const response = await httpRequest(baseUrl() + CHECKIN_PATH, {
    method: 'POST',
    headers: {
      ...authHeaders(token),
      'Content-Type': 'application/json',
    },
    body: '{}',
  });
  const httpFail = classifyHttp(Number(response.statusCode));
  if (httpFail) return httpFail;
  const payload = parseJsonSafe(response.text);
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return {
      ok: false,
      state: 'failure',
      message: '签到接口返回了无法识别的非 JSON 响应',
    };
  }
  return classifyCheckInPayload(payload);
}

async function runAccount(account) {
  const info = await fetchUserInfo(account.token);
  if (!info.ok) {
    return {
      ok: false,
      state: 'failure',
      message: info.message,
      identity: info.identity || '',
      infoMessage: '',
    };
  }
  const check = await performCheckIn(account.token);
  return {
    ok: check.ok,
    state: check.state,
    message: check.message,
    identity: info.identity || '',
    infoMessage: info.message,
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
  log(`阶段 1/3：配置检查 | API：${baseUrl()}`);
  const configStarted = Date.now();
  let configurationError = false;

  if (!accounts.length) {
    configurationError = true;
    log(
      `❌ 配置错误：缺少 ${CREDENTIAL_ENV}（或兼容变量 ${CREDENTIAL_ALIASES.join(
        ' / '
      )}）的非空 Token 行`
    );
  } else {
    for (const account of accounts) {
      if (!account.valid) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} Bearer Token 格式无效`);
      }
    }
  }

  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ Token 行已读取'} | 耗时 ${
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
      log(`账号 ${account.index}${labelHint} | 阶段 2/3：用户信息 + 每日签到`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log(
            `⏭️ DRY_RUN_OK：账号 ${account.index} Token 格式通过（长度 ${account.token.length}）；未请求网络，未验证真实业务`
          );
        } else {
          const result = await runAccount(account);
          if (result.identity) {
            log(`账号 ${account.index} | 官方身份：${sanitizeDisplayText(result.identity)}`);
          }
          if (result.infoMessage) {
            log(`账号 ${account.index} | 用户信息：${redact(result.infoMessage)}`);
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
  tokenLooksValid,
  classifyCheckInPayload,
  redact,
};
