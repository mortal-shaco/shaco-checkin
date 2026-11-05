#!/usr/bin/env node
// name: 成都大学ISP每日登记
// cron: 1 7 * * *
/**
 * 成都大学 ISP 系统每日位置登记 · 青龙独立维护版
 *
 * 上游：hanhan9449/auto-sign-in
 * 仓库：https://github.com/hanhan9449/auto-sign-in
 * 分支：main · 提交：a45455042f05eefc2cece5b3f1cc123494e9469b
 * 原始路径：src/services/signIn.ts（合并同仓 getUrls / getCredit / getLoginModel / registerToken）
 * 授权：MIT（Copyright (c) 2020 Han Han）
 *
 * 功能盘点（主来源 + 同仓关联）：
 * - 从 ISP 门户页发现可用 weblogin.asp 登录入口（可配置固定入口跳过发现）
 * - 拉取登录页图形验证码与会话 Cookie
 * - 使用学号/密码提交登录表单注册会话
 * - 按当日日期与用户自填地址/坐标提交 project_addx 每日登记
 * - 识别「登记已存在」「成功」等业务结果；学号或密码错误视为失败
 * - 上游硬编码成都市武侯区具体住址与坐标已移除，改为必填环境参数
 * - 上游 dayjs.month()/day() 误用（0–11 月、星期）改为上海时区年/月/日
 * - 无发帖/评论/分享等公开内容副作用
 *
 * CDU_ACCOUNTS（必填）：每个非空行一个账号。
 * 推荐格式：学号|密码（仅在首个 | 处拆分，后续密码原文保留）
 * 亦可单行 JSON：{"username":"...","password":"..."}
 * 获取：成都大学 ISP / 学工在线（xsswzx.cdu.edu.cn）登录学号与密码；勿提交真实凭据。
 * 兼容别名：USERNAME + PASSWORD（仅当 CDU_ACCOUNTS 为空时，作为单账号读取）。
 * CDU_ADDRESS（必填）：登记地址中文文本，须由账号本人填写真实位置，无默认值。
 * CDU_ADDSXY（必填）：经度,纬度，例如 104.07859,30.55403；无默认值。
 * CDU_LOGIN_URL：可选。直接指定 weblogin.asp 完整 URL，跳过门户发现。
 * CDU_INDEX_URL：可选。门户发现页，默认 https://xsswzx.cdu.edu.cn/isp/website.asp
 * CDU_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要。
 * CDU_TIMEOUT_MS：请求超时毫秒，默认 15000（1000–60000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Copyright (c) 2020 Han Han
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
      '9798376670c63280',
      'scripts/cdu_isp_signin.js',
      'cdu_isp_signin.js',
      'signIn.ts',
      'signIn.js',
      'cdu_isp',
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

const TITLE = '成都大学ISP每日登记';
const CATALOG_ID = '9798376670c63280';
const CREDENTIAL_ENV = 'CDU_ACCOUNTS';
const CREDENTIAL_ALIASES = ['USERNAME', 'PASSWORD'];
const DRY_RUN_ENV = 'CDU_DRY_RUN';
const DEFAULT_INDEX_URL = 'https://xsswzx.cdu.edu.cn/isp/website.asp';
const SIGN_MAGIC =
  '/project_addx.asp?id=2cac2bcd340407662b58f58d7d36208484167d55095a&id2=';
const DEFAULT_TIMEOUT_MS = 15000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const ACCOUNT_GAP_MS = 1200;
const DEFAULT_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_1_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36';

const secrets = new Set();
const statusIcons = {
  success: '✅',
  alreadyComplete: '☑️',
  skipped: '⏭️',
  warning: '⚠️',
  failure: '❌',
};

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
  if (typeof value === 'string' && value.trim()) secrets.add(value.trim());
}

function redact(value) {
  let text = String(value == null ? '' : value).replace(
    /[\r\n\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    ' '
  );
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
    if (secret) text = text.split(secret).join('[已隐藏]');
  }
  text = text.replace(/(?:^|;\s*)([^=;\s]+)=([^;]+)/g, (match, key, val) => {
    if (/cookie|token|session|passwd|password|pwd|userpwd/i.test(String(key))) {
      return match.replace(val, '[已隐藏]');
    }
    return match;
  });
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
  const value = Number.parseInt(process.env.CDU_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000
    ? value
    : DEFAULT_TIMEOUT_MS;
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
    'scripts/cdu_isp_signin.js',
    'cdu_isp_signin.js',
    'signIn.ts',
    'signIn.js',
    'cdu_isp',
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

function shanghaiDateParts() {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  }).formatToParts(new Date());
  const map = {};
  for (const part of parts) {
    if (part.type !== 'literal') map[part.type] = Number(part.value);
  }
  return {
    year: map.year,
    month: map.month,
    day: map.day,
  };
}

function todayLabelZh() {
  const { year, month, day } = shanghaiDateParts();
  return `${year}年${month}月${day}日`;
}

function indexUrl() {
  const raw = String(process.env.CDU_INDEX_URL || '').trim();
  return raw || DEFAULT_INDEX_URL;
}

function fixedLoginUrl() {
  return String(process.env.CDU_LOGIN_URL || '').trim();
}

function readAddress() {
  return String(process.env.CDU_ADDRESS || '').trim();
}

function readAddsxy() {
  return String(process.env.CDU_ADDSXY || '').trim();
}

function addsxyLooksValid(value) {
  const text = String(value || '').trim();
  if (!text) return false;
  const m = text.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
  if (!m) return false;
  const lng = Number(m[1]);
  const lat = Number(m[2]);
  return Number.isFinite(lng) && Number.isFinite(lat) && Math.abs(lng) <= 180 && Math.abs(lat) <= 90;
}

function credentialRaw() {
  const primary = process.env[CREDENTIAL_ENV];
  if (primary != null && String(primary).trim() !== '') return String(primary);

  const username = String(process.env.USERNAME || '').trim();
  const password = String(process.env.PASSWORD || '');
  if (username && password) return `${username}|${password}`;
  return '';
}

function parseAccountLine(line, index) {
  remember(line);
  const trimmed = String(line || '').trim();
  let username = '';
  let password = '';
  let valid = false;
  let reason = '';

  if (!trimmed) {
    return { index, username, password, valid: false, reason: '空行' };
  }

  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    try {
      const obj = JSON.parse(trimmed);
      username = String(obj.username || obj.user || obj.USER || obj.学号 || '').trim();
      password = String(obj.password || obj.passwd || obj.PASSWORD || obj.密码 || '');
    } catch {
      return { index, username: '', password: '', valid: false, reason: 'JSON 账号行无法解析' };
    }
  } else {
    const pipe = trimmed.indexOf('|');
    if (pipe <= 0) {
      return {
        index,
        username: '',
        password: '',
        valid: false,
        reason: '缺少学号|密码分隔',
      };
    }
    username = trimmed.slice(0, pipe).trim();
    password = trimmed.slice(pipe + 1);
  }

  remember(username);
  remember(password);
  if (!username || !password) {
    reason = '学号或密码为空';
    valid = false;
  } else {
    valid = true;
  }
  return { index, username, password, valid, reason };
}

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line, i) => parseAccountLine(line, i + 1));
}

function joinCookies(existing, setCookieHeader) {
  const jar = new Map();
  const ingest = (cookieText) => {
    const first = String(cookieText || '').split(';')[0].trim();
    if (!first || !first.includes('=')) return;
    const eq = first.indexOf('=');
    const name = first.slice(0, eq).trim();
    const value = first.slice(eq + 1).trim();
    if (!name) return;
    jar.set(name, value);
    remember(value);
  };
  for (const part of String(existing || '')
    .split(';')
    .map((s) => s.trim())
    .filter(Boolean)) {
    ingest(part);
  }
  const headers = setCookieHeader;
  const list = Array.isArray(headers) ? headers : headers ? [headers] : [];
  for (const item of list) ingest(item);
  return [...jar.entries()].map(([k, v]) => `${k}=${v}`).join('; ');
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
    const reqHeaders = {
      'User-Agent': DEFAULT_UA,
      'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
      Accept:
        'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
      ...headers,
    };
    if (payload) {
      reqHeaders['Content-Length'] = String(payload.length);
      if (!reqHeaders['Content-Type'] && !reqHeaders['content-type']) {
        reqHeaders['Content-Type'] = 'application/x-www-form-urlencoded';
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

function baseFromLoginUrl(loginUrl) {
  return String(loginUrl || '').replace(/\/weblogin\.asp(?:\?.*)?$/i, '');
}

async function discoverLoginUrls() {
  const fixed = fixedLoginUrl();
  if (fixed) return [fixed];
  const res = await httpRequest(indexUrl(), { method: 'GET' });
  if (!res.statusCode || res.statusCode >= 400) {
    throw new Error('discover-failed');
  }
  const urls = [...String(res.text || '').matchAll(/https:\/\/xsswzx\.cdu\.edu\.cn.*?(?=\/weblogin\.asp)/g)]
    .map((o) => o.toString())
    .map((s) => s + '/weblogin.asp');
  const unique = [...new Set(urls)];
  if (!unique.length) throw new Error('discover-empty');
  return unique;
}

async function getCredit(loginUrl) {
  const res = await httpRequest(loginUrl, { method: 'GET' });
  if (!res.statusCode || res.statusCode >= 400) {
    return { ok: false, message: `获取验证码页失败（HTTP ${res.statusCode || 0}）` };
  }
  const codeMatch = String(res.text || '').match(/(?:&nbsp;){2}(\d{4})/);
  const code = codeMatch ? codeMatch[1] : '';
  const cookie = joinCookies('', res.headers['set-cookie']);
  if (!code || !cookie) {
    return { ok: false, message: '获取验证码或会话 Cookie 失败' };
  }
  remember(code);
  remember(cookie);
  return { ok: true, code, cookie };
}

async function registerToken(loginUrl, credit, account) {
  const form = new URLSearchParams();
  form.append('username', account.username);
  form.append('userpwd', account.password);
  form.append('code', credit.code);
  form.append('login', 'login');
  form.append('checkcode', '1');
  form.append('rank', '0');
  form.append('action', 'login');
  form.append('m5', '1');

  const res = await httpRequest(loginUrl, {
    method: 'POST',
    headers: {
      Cookie: credit.cookie,
      Referer: loginUrl,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: form.toString(),
  });
  const text = String(res.text || '');
  if (text.includes('学号或密码错误')) {
    return { ok: false, message: '学号或密码错误', cookie: credit.cookie };
  }
  if (!res.statusCode || (res.statusCode >= 400 && res.statusCode !== 302)) {
    return {
      ok: false,
      message: `登录请求失败（HTTP ${res.statusCode || 0}）`,
      cookie: credit.cookie,
    };
  }
  const cookie = joinCookies(credit.cookie, res.headers['set-cookie']);
  remember(cookie);
  return { ok: true, message: '登录会话已建立', cookie };
}

function buildSignUrl(loginUrl, address, addsxy) {
  const base = baseFromLoginUrl(loginUrl);
  const datePart = encodeURI(todayLabelZh());
  const adds = encodeURI(address);
  return `${base}${SIGN_MAGIC}${datePart}&adds=${adds}&addsxy=${encodeURIComponent(addsxy)}`;
}

async function signIn(loginUrl, cookie, address, addsxy) {
  const url = buildSignUrl(loginUrl, address, addsxy);
  const res = await httpRequest(url, {
    method: 'GET',
    headers: {
      Cookie: cookie,
      Referer: loginUrl,
    },
  });
  const text = String(res.text || '');
  if (text.includes('登记已存在')) {
    return { ok: true, state: 'alreadyComplete', message: '今日登记已存在' };
  }
  if (text.includes('成功')) {
    return { ok: true, state: 'success', message: '登记成功' };
  }
  if (!res.statusCode || res.statusCode >= 400) {
    return {
      ok: false,
      state: 'failure',
      message: `登记请求失败（HTTP ${res.statusCode || 0}）`,
    };
  }
  return {
    ok: false,
    state: 'failure',
    message: '登记接口返回无法识别的业务结果（未包含成功/已存在）',
  };
}

async function runAccountOnUrl(account, loginUrl, address, addsxy) {
  const credit = await getCredit(loginUrl);
  if (!credit.ok) {
    return { ok: false, state: 'failure', message: credit.message, identity: account.username };
  }
  const login = await registerToken(loginUrl, credit, account);
  if (!login.ok) {
    return { ok: false, state: 'failure', message: login.message, identity: account.username };
  }
  const signed = await signIn(loginUrl, login.cookie, address, addsxy);
  return {
    ...signed,
    identity: account.username,
  };
}

async function runAccount(account, address, addsxy) {
  const urls = await discoverLoginUrls();
  let lastFailure = { ok: false, state: 'failure', message: '全部登录入口均失败', identity: account.username };
  for (const loginUrl of urls) {
    try {
      const result = await runAccountOnUrl(account, loginUrl, address, addsxy);
      if (result.ok) return result;
      lastFailure = result;
      if (/学号或密码错误/.test(result.message || '')) return result;
    } catch (err) {
      const code = err && err.message ? String(err.message) : '';
      const reasons = {
        timeout: '请求超时',
        'response-too-large': '响应过大',
        'network-error': '网络请求失败',
        'response-error': '响应读取失败',
        'response-aborted': '响应中断',
        'invalid-url': '地址无效',
        'discover-failed': '门户页请求失败',
        'discover-empty': '未发现可用登录入口',
      };
      lastFailure = {
        ok: false,
        state: 'failure',
        message: reasons[code] || '当前入口尝试失败',
        identity: account.username,
      };
    }
  }
  return lastFailure;
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
    delete env.USERNAME;
    delete env.PASSWORD;
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
    delete env.USERNAME;
    delete env.PASSWORD;
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
  const address = readAddress();
  const addsxy = readAddsxy();
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

  log(`阶段 1/3：配置检查 | 登记日：${todayLabelZh()}`);
  const configStarted = Date.now();
  let configurationError = false;

  if (!accounts.length) {
    configurationError = true;
    log(
      `${statusIcons.failure} 配置错误：缺少 ${CREDENTIAL_ENV}（或兼容变量 USERNAME+PASSWORD）的非空账号行`
    );
  } else {
    for (const account of accounts) {
      if (!account.valid) {
        configurationError = true;
        log(
          `${statusIcons.failure} 配置错误：账号 ${account.index} ${account.reason || '凭据无效'}`
        );
      }
    }
  }

  if (!address) {
    configurationError = true;
    log(`${statusIcons.failure} 配置错误：缺少必填 CDU_ADDRESS（登记地址，无默认硬编码）`);
  }
  if (!addsxyLooksValid(addsxy)) {
    configurationError = true;
    log(`${statusIcons.failure} 配置错误：CDU_ADDSXY 须为「经度,纬度」且无默认硬编码`);
  }

  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 参数已读取'} | 耗时 ${
      Date.now() - configStarted
    }ms`
  );

  if (!configurationError) {
    for (let i = 0; i < accounts.length; i++) {
      const account = accounts[i];
      const began = Date.now();
      summary.tasks.total++;
      let outcome = 'failure';
      const identityHint = sanitizeDisplayText(account.username) || `账号${account.index}`;
      log(`账号 ${account.index}（${identityHint}） | 阶段 2/3：登录并每日登记`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log(
            `${statusIcons.skipped} DRY_RUN_OK：账号 ${account.index} 学号格式通过；地址与坐标已校验；未请求网络，未验证真实业务`
          );
        } else {
          const result = await runAccount(account, address, addsxy);
          if (result.identity) {
            log(`账号 ${account.index} | 学号身份：${sanitizeDisplayText(result.identity)}`);
          }
          if (result.ok && result.state === 'success') {
            outcome = 'success';
            log(`${statusIcons.success} ${redact(result.message)}`);
          } else if (result.ok && result.state === 'alreadyComplete') {
            outcome = 'alreadyComplete';
            log(`${statusIcons.alreadyComplete} ${redact(result.message)}`);
          } else {
            outcome = 'failure';
            log(`${statusIcons.failure} ${redact(result.message)}`);
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
          'discover-failed': '门户页请求失败',
          'discover-empty': '未发现可用登录入口',
        };
        const code = err && err.message ? String(err.message) : '';
        log(`${statusIcons.failure} ${reasons[code] || '请求失败'}；未确认登记成功`);
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
    `失败数：${summary.failedAccounts}；登记成功：${summary.tasks.success}；已完成：${summary.tasks.alreadyComplete}；` +
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
  addsxyLooksValid,
  todayLabelZh,
  CREDENTIAL_ENV,
  DRY_RUN_ENV,
};
