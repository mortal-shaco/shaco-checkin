// name: 技实习自动签到
// cron: 42 8 * * *
/**
 * 广州市工贸技师学院 · 技实习自动签到打卡 · 青龙独立维护版
 *
 * 上游：1665169869/jishixi_auto_checkin · index.js
 * 仓库：https://github.com/1665169869/jishixi_auto_checkin
 * 分支：master
 * 提交：5a25a2e3c203d22ce16d451cf8a8e2081d4aacce
 * 授权：MIT
 * 原作者：白羽 <1665169869@qq.com>
 *
 * 功能盘点（主来源）：
 * - 学号+密码登录 https://gzgm.cydgsx.com（/logina → /mobileModelAdd → /m/home/appLogin → /m/s/Home/Index）
 * - 从 /m/s/Log/wLog 获取加密 Cookie 键值，TripleDES-ECB 加密后提交 /m/s/Log/SaveWriteLog 实习日志打卡
 * - 打卡载荷含实习状态、日志正文、经纬度与地址
 * - 上游硬编码 USERS、固定坐标与固定日志正文已移除；改为环境变量，坐标必须由用户配置
 *
 * JISHIXI_ACCOUNTS（必填）：每个非空行一个账号。
 *   - JSON：{"user_account":"学号","psw":"密码","posLong":经度,"posLati":纬度,"posAddress":"地址","interContent":"可选日志"}
 *   - 或：学号|密码（仅在首个竖线处拆分，后续全文视为密码；位置取共享环境变量）
 * 不使用 &、@ 分隔账号。学号、密码、Cookie、加密键永不打印；登录后若返回 loginUserName 则直接显示。
 * JISHIXI_POS_LONG / JISHIXI_POS_LATI / JISHIXI_POS_ADDRESS：共享默认坐标与地址；账号 JSON 内字段优先。
 * JISHIXI_INTER_CONTENT：共享默认实习日志正文；账号 JSON 的 interContent 优先。
 * JISHIXI_BASE_URL：接口根地址，默认 https://gzgm.cydgsx.com（其他学校需自行改成对应域名）。
 * JISHIXI_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递、不发业务请求）。
 * JISHIXI_TIMEOUT_MS：单次 HTTP 超时毫秒，默认 20000（1000–120000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * SPDX-License-Identifier: MIT
 *
 * MIT License
 * Copyright (c) 2024 白羽
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the Software), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
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
    const identities = ["9ae0664c90671962", "scripts/jishixi.js", "jishixi.js", "jishixi"];
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

const TITLE = '技实习自动签到';
const CATALOG_ID = '9ae0664c90671962';
const CREDENTIAL_ENV = 'JISHIXI_ACCOUNTS';
const DRY_RUN_ENV = 'JISHIXI_DRY_RUN';
const DEFAULT_BASE_URL = 'https://gzgm.cydgsx.com';
const DEFAULT_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const ACCOUNT_GAP_MS = 2000;
const DEFAULT_INTER_CONTENT = '今日实习正常，按计划完成工作。';
const DEFAULT_UA =
  'Mozilla/5.0 (Linux; Android 9; 23127PN0CC Build/PQ3A.190705.08211539; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Safari/537.36';

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
  text = text.replace(/Bearer\s+[A-Za-z0-9._+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/\b[a-fA-F0-9]{32,}\b/g, '[已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.JISHIXI_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 120000
    ? value
    : DEFAULT_TIMEOUT_MS;
}

function baseUrl() {
  const raw = String(process.env.JISHIXI_BASE_URL || DEFAULT_BASE_URL).trim();
  return raw.replace(/\/$/, '') || DEFAULT_BASE_URL;
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
    'scripts/jishixi_checkin.js',
    'jishixi_checkin.js',
    'index.js',
    'jishixi',
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

function readCredentialRaw() {
  const primary = process.env[CREDENTIAL_ENV];
  if (primary != null && String(primary).trim() !== '') return String(primary);
  return '';
}

function parseCoord(value) {
  if (value === undefined || value === null || value === '') return '';
  const num = Number(value);
  if (!Number.isFinite(num)) return '';
  return String(value).trim();
}

function parseAccountLine(line, index) {
  remember(line);
  const trimmed = String(line || '').trim();
  if (!trimmed) return { index, valid: false, reason: 'empty-line' };

  let raw = {};
  if (trimmed.startsWith('{')) {
    try {
      raw = JSON.parse(trimmed);
    } catch {
      return { index, valid: false, reason: 'invalid-json' };
    }
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      return { index, valid: false, reason: 'invalid-json' };
    }
  } else {
    const pipe = trimmed.indexOf('|');
    if (pipe <= 0) return { index, valid: false, reason: 'invalid-format' };
    const userAccount = trimmed.slice(0, pipe).trim();
    const rest = trimmed.slice(pipe + 1);
    remember(userAccount);
    remember(rest);
    raw = { user_account: userAccount, psw: rest };
  }

  const userAccount = String(raw.user_account || raw.account || raw.username || '').trim();
  const password = String(raw.psw || raw.password || raw.passwd || '').trim();
  remember(userAccount);
  remember(password);

  const posLong = parseCoord(
    raw.posLong != null ? raw.posLong : raw.longitude != null ? raw.longitude : process.env.JISHIXI_POS_LONG
  );
  const posLati = parseCoord(
    raw.posLati != null ? raw.posLati : raw.latitude != null ? raw.latitude : process.env.JISHIXI_POS_LATI
  );
  const posAddress = String(
    raw.posAddress != null
      ? raw.posAddress
      : raw.address != null
        ? raw.address
        : process.env.JISHIXI_POS_ADDRESS || ''
  ).trim();
  const interContent = String(
    raw.interContent != null
      ? raw.interContent
      : process.env.JISHIXI_INTER_CONTENT || DEFAULT_INTER_CONTENT
  ).trim();

  if (!userAccount || !password) {
    return { index, valid: false, reason: 'missing-credentials' };
  }
  if (!posLong || !posLati || !posAddress) {
    return { index, valid: false, reason: 'missing-location' };
  }
  const longNum = Number(posLong);
  const latiNum = Number(posLati);
  if (!Number.isFinite(longNum) || longNum < -180 || longNum > 180) {
    return { index, valid: false, reason: 'invalid-longitude' };
  }
  if (!Number.isFinite(latiNum) || latiNum < -90 || latiNum > 90) {
    return { index, valid: false, reason: 'invalid-latitude' };
  }

  return {
    index,
    valid: true,
    userAccount,
    password,
    posLong: longNum,
    posLati: latiNum,
    posAddress,
    interContent: interContent || DEFAULT_INTER_CONTENT,
  };
}

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line, index) => parseAccountLine(line, index + 1));
}

function encodeForm(data) {
  const parts = [];
  for (const [key, value] of Object.entries(data)) {
    if (value === undefined) continue;
    const text = value === null ? '' : String(value);
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(text)}`);
  }
  return parts.join('&');
}

function cookieHeader(cookieMap) {
  return Object.entries(cookieMap)
    .map(([key, value]) => `${key}=${value}`)
    .join('; ');
}

function parseSetCookiePair(setCookie) {
  const first = String(setCookie || '').split(';')[0];
  const index = first.indexOf('=');
  if (index <= 0) return null;
  const name = first.slice(0, index).trim();
  const value = first.slice(index + 1);
  if (!name) return null;
  remember(value);
  return { name, value };
}

function mergeSetCookies(cookieMap, setCookieHeader) {
  const list = Array.isArray(setCookieHeader)
    ? setCookieHeader
    : setCookieHeader
      ? [setCookieHeader]
      : [];
  for (const item of list) {
    const pair = parseSetCookiePair(item);
    if (pair) cookieMap[pair.name] = pair.value;
  }
  return cookieMap;
}

function encryptByDES(message, keyValue) {
  let key = Buffer.from(String(keyValue), 'utf8');
  if (key.length < 24) key = Buffer.concat([key, Buffer.alloc(24 - key.length)]);
  else if (key.length > 24) key = key.subarray(0, 24);
  const cipher = crypto.createCipheriv('des-ede3-ecb', key, null);
  cipher.setAutoPadding(true);
  return Buffer.concat([cipher.update(String(message), 'utf8'), cipher.final()]).toString('base64');
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
    if (payload) {
      reqHeaders['Content-Length'] = String(payload.length);
      if (!reqHeaders['Content-Type'] && !reqHeaders['content-type']) {
        reqHeaders['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function apiUrl(pathname) {
  const root = baseUrl();
  const pathPart = String(pathname || '').startsWith('/')
    ? String(pathname)
    : `/${String(pathname || '')}`;
  return root + pathPart;
}

function parseJsonSafe(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function pickIdentity(cookieMap, loginBody) {
  if (cookieMap && cookieMap.loginUserName) {
    return String(cookieMap.loginUserName);
  }
  const result = loginBody && loginBody.result;
  if (result && typeof result === 'object') {
    for (const key of ['user_name', 'userName', 'nickname', 'nickName', 'realName', 'name']) {
      if (result[key] != null && String(result[key]).trim()) return String(result[key]).trim();
    }
    if (result.user_id != null && String(result.user_id).trim()) {
      return `uid:${result.user_id}`;
    }
  }
  return '';
}

async function loginAccount(account) {
  const cookieMap = {};
  const commonHeaders = {
    'User-Agent': DEFAULT_UA,
    Accept: 'application/json, text/plain, */*',
  };

  const loginBody = encodeForm({
    params: JSON.stringify({
      psw: account.password,
      user_account: account.userAccount,
    }),
  });
  const loginaResponse = await httpRequest(apiUrl('/logina'), {
    method: 'POST',
    headers: {
      ...commonHeaders,
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    },
    body: loginBody,
  });
  log(`登录响应状态码：${loginaResponse.statusCode}；长度：${loginaResponse.text.length} 字节`);
  mergeSetCookies(cookieMap, loginaResponse.headers['set-cookie']);
  const loginJson = parseJsonSafe(loginaResponse.text);
  if (loginaResponse.statusCode !== 200 || !loginJson || loginJson.state !== 1) {
    throw new Error('login-failed');
  }
  const userId = loginJson.result && loginJson.result.user_id;
  if (userId == null || String(userId).trim() === '') {
    throw new Error('login-missing-userid');
  }
  remember(String(userId));

  const deviceBody = encodeForm({
    params: JSON.stringify({
      appType: 'android',
      appVersion: '5.0',
      brand: 'ipad',
      manufacturer: 'ipad',
      model: '23127PN0CC',
      release: '9',
      user_id: userId,
    }),
  });
  const deviceResponse = await httpRequest(apiUrl('/mobileModelAdd'), {
    method: 'POST',
    headers: {
      ...commonHeaders,
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      Cookie: cookieHeader(cookieMap),
    },
    body: deviceBody,
  });
  log(`设备登记响应状态码：${deviceResponse.statusCode}；长度：${deviceResponse.text.length} 字节`);
  mergeSetCookies(cookieMap, deviceResponse.headers['set-cookie']);

  const appLoginUrl = new URL(apiUrl('/m/home/appLogin'));
  appLoginUrl.searchParams.set('jxnApp', '0');
  appLoginUrl.searchParams.set('user_id', String(userId));
  appLoginUrl.searchParams.set('type', '1');
  const appLoginResponse = await httpRequest(appLoginUrl.toString(), {
    method: 'GET',
    headers: {
      ...commonHeaders,
      Cookie: cookieHeader(cookieMap),
    },
  });
  log(`会话跳转响应状态码：${appLoginResponse.statusCode}`);
  if (appLoginResponse.statusCode !== 302) {
    throw new Error('app-login-failed');
  }
  mergeSetCookies(cookieMap, appLoginResponse.headers['set-cookie']);

  const homeResponse = await httpRequest(apiUrl('/m/s/Home/Index'), {
    method: 'GET',
    headers: {
      ...commonHeaders,
      Cookie: cookieHeader(cookieMap),
    },
  });
  log(`首页响应状态码：${homeResponse.statusCode}；长度：${homeResponse.text.length} 字节`);
  mergeSetCookies(cookieMap, homeResponse.headers['set-cookie']);

  const identity = pickIdentity(cookieMap, loginJson);
  return { cookieMap, identity, loginJson };
}

async function getEncryptKey(cookieMap) {
  const response = await httpRequest(apiUrl('/m/s/Log/wLog?articleId=0'), {
    method: 'GET',
    headers: {
      'User-Agent': DEFAULT_UA,
      Cookie: cookieHeader(cookieMap),
      Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    },
  });
  log(`加密页响应状态码：${response.statusCode}`);
  const setCookie = response.headers['set-cookie'];
  const list = Array.isArray(setCookie) ? setCookie : setCookie ? [setCookie] : [];
  if (!list.length) throw new Error('encrypt-key-missing');
  const pair = parseSetCookiePair(list[0]);
  if (!pair) throw new Error('encrypt-key-invalid');
  mergeSetCookies(cookieMap, setCookie);
  return pair;
}

function interpretSaveResult(response) {
  const contentType = String(
    (response.headers && (response.headers['content-type'] || response.headers['Content-Type'])) || ''
  );
  if (response.statusCode !== 200) {
    throw new Error('checkin-http-failed');
  }
  if (!contentType.includes('application/json')) {
    throw new Error('checkin-non-json');
  }
  const body = parseJsonSafe(response.text);
  if (!body || typeof body !== 'object') {
    throw new Error('checkin-non-json');
  }
  const state = body.state;
  const message = String(body.msg || body.message || body.info || '');
  if (/已打卡|已签到|重复|已经提交|勿重复/.test(message)) {
    return { state: 'alreadyComplete', message: message || '今日已打卡' };
  }
  if (state === 1 || state === '1' || body.success === true || body.code === 0 || body.code === 200) {
    return { state: 'success', message: message || '打卡成功' };
  }
  if (state === undefined && body.success === undefined && body.code === undefined) {
    // 上游仅核验 HTTP 200 + JSON；无业务码时按成功闭合
    return { state: 'success', message: message || '打卡成功（接口返回 JSON）' };
  }
  throw new Error(`checkin-business:${message || state || '打卡失败'}`);
}

async function saveWriteLog(account, cookieMap, encryptPair) {
  const data = {
    InternStateId: 1,
    interContent: account.interContent,
    logImg: '',
    posAddress: account.posAddress,
    posLong: account.posLong,
    posLati: account.posLati,
    locationType: 2,
    ArticleId: 0,
  };
  data[encryptPair.name] = encryptByDES(encryptPair.name, encryptPair.value);
  const response = await httpRequest(apiUrl('/m/s/Log/SaveWriteLog'), {
    method: 'POST',
    headers: {
      'User-Agent': DEFAULT_UA,
      Cookie: cookieHeader(cookieMap),
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      Accept: 'application/json, text/plain, */*',
    },
    body: encodeForm(data),
  });
  log(`打卡响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
  return interpretSaveResult(response);
}

async function processAccount(account) {
  const stages = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
  const mark = (key) => {
    stages.total += 1;
    stages[key] += 1;
  };

  log(`账号 ${account.index} | 子阶段 1/3：登录`);
  const stage1 = Date.now();
  const session = await loginAccount(account);
  if (session.identity) log(`账号 ${account.index} 官方身份：${session.identity}`);
  else log(`账号 ${account.index} 登录成功（未返回公开昵称，使用序号）`);
  log(`✅ 登录完成 | 耗时 ${Date.now() - stage1}ms`);
  mark('success');

  log(`账号 ${account.index} | 子阶段 2/3：获取打卡加密参数`);
  const stage2 = Date.now();
  const encryptPair = await getEncryptKey(session.cookieMap);
  log(`✅ 加密参数已获取 | 耗时 ${Date.now() - stage2}ms`);
  mark('success');

  log(`账号 ${account.index} | 子阶段 3/3：提交实习日志打卡`);
  const stage3 = Date.now();
  const saved = await saveWriteLog(account, session.cookieMap, encryptPair);
  if (saved.state === 'alreadyComplete') {
    log(`☑️ ${redact(saved.message)} | 耗时 ${Date.now() - stage3}ms`);
    mark('alreadyComplete');
  } else {
    log(`✅ ${redact(saved.message)} | 耗时 ${Date.now() - stage3}ms`);
    mark('success');
  }
  return { ok: true, stages, identity: session.identity, checkinState: saved.state };
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
    delete env.JISHIXI_ACCOUNTS;
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
    delete env.JISHIXI_ACCOUNTS;
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
    'login-failed': '登录业务失败，请核对学号与密码',
    'login-missing-userid': '登录未返回 user_id',
    'app-login-failed': '获取应用会话失败（未收到预期跳转）',
    'encrypt-key-missing': '未获取到打卡加密 Cookie',
    'encrypt-key-invalid': '打卡加密 Cookie 无效',
    'checkin-http-failed': '打卡接口 HTTP 状态异常',
    'checkin-non-json': '打卡接口未返回 JSON',
    'invalid-json': '账号 JSON 格式错误',
    'invalid-format': '账号行格式错误，需为 JSON 或 学号|密码',
    'missing-credentials': '缺少学号或密码',
    'missing-location': '缺少经度、纬度或地址（账号 JSON 或 JISHIXI_POS_*）',
    'invalid-longitude': '经度无效',
    'invalid-latitude': '纬度无效',
    'empty-line': '空账号行',
  };
  if (map[code]) return map[code];
  if (String(code).startsWith('checkin-business:')) {
    return `打卡失败：${redact(String(code).slice('checkin-business:'.length))}`;
  }
  return redact(code || '请求失败');
}

async function main() {
  const started = Date.now();
  const dryRun = enabled(process.env[DRY_RUN_ENV]);
  const accounts = parseAccounts(readCredentialRaw());
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
  console.log(`接口根地址：${baseUrl()}`);
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
        log(`❌ 配置错误：账号 ${account.index} ${reasonText(account.reason)}`);
      } else {
        log(`账号 ${account.index} 配置可读：地址长度=${account.posAddress.length}；日志长度=${account.interContent.length}`);
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${
      Date.now() - configStarted
    }ms`
  );

  if (!configurationError) {
    log('阶段 2/3：账号打卡');
    for (let i = 0; i < accounts.length; i++) {
      const account = accounts[i];
      const began = Date.now();
      log(`-------- 账号 ${account.index}/${accounts.length} --------`);
      try {
        if (dryRun) {
          summary.tasks.total += 1;
          summary.tasks.skipped += 1;
          summary.successfulAccounts += 1;
          log(
            '⏭️ DRY_RUN_OK：学号/密码/坐标字段校验通过；未请求技实习 API，未验证真实业务'
          );
          log(
            `账号 ${account.index} 统计：总任务 1 | 成功 0 | 已完成 0 | 跳过 1 | 失败 0 | 耗时 ${
              Date.now() - began
            }ms`
          );
        } else {
          const result = await processAccount(account);
          summary.tasks.total += result.stages.total;
          summary.tasks.success += result.stages.success;
          summary.tasks.alreadyComplete += result.stages.alreadyComplete;
          summary.tasks.skipped += result.stages.skipped;
          summary.tasks.failure += result.stages.failure;
          if (result.ok) summary.successfulAccounts += 1;
          else summary.failedAccounts += 1;
          if (result.identity) log(`账号 ${account.index} 核对身份：${result.identity}`);
          log(
            `账号 ${account.index} 统计：总任务 ${result.stages.total} | 成功 ${result.stages.success} | 已完成 ${result.stages.alreadyComplete} | 跳过 ${result.stages.skipped} | 失败 ${result.stages.failure} | 耗时 ${Date.now() - began}ms`
          );
        }
      } catch (err) {
        summary.failedAccounts += 1;
        summary.tasks.total += 1;
        summary.tasks.failure += 1;
        const code = err && err.message ? String(err.message) : 'unknown';
        log(`❌ ${reasonText(code)}；未确认打卡成功`);
        log(
          `账号 ${account.index} 统计：总任务 1 | 成功 0 | 已完成 0 | 跳过 0 | 失败 1 | 耗时 ${
            Date.now() - began
          }ms`
        );
      }
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
    `失败数：${summary.failedAccounts}；子任务成功：${summary.tasks.success}；已完成：${summary.tasks.alreadyComplete}；` +
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
  encryptByDES,
  interpretSaveResult,
  TITLE,
  CATALOG_ID,
};
