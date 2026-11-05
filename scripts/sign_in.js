// name: 上马官网每日签到
// cron: 24 8 * * *
/**
 * 上马（上海马拉松官网 shang-ma.com）每日积分签到 · 青龙独立维护版
 *
 * 上游：zhaohongxuan/shangma_auto_sign · sign_in.js（合并同仓 cookies.js / lib 登录链路）
 * 仓库：https://github.com/zhaohongxuan/shangma_auto_sign
 * 分支：main
 * 提交：22f34579e7f8cef33a0a99538be19afbde3006a4
 * 授权：MIT
 *
 * 功能盘点（主来源 sign_in.js + 同仓登录辅助）：
 * - SSO attach 获取护照站初始化 Cookie
 * - 使用账号密码登录 passport.shang-ma.com，取得 SHM_JWT_TOKEN
 * - POST www.shang-ma.com/api/v1/user/integral/sign-in 完成每日积分签到
 * - 业务码 code=0 视为签到成功；code=5001 视为今日已签（不失败）
 * - 上游 GitHub Action cron「0 0 * * *」UTC → 北京时间每日 08:00
 * - 无发帖/评论等公开内容副作用
 *
 * SHANGMA_ACCOUNT（必填）：每行一个账号，格式「用户名|密码」，只在首个 | 处拆分，密码中后续 | 保留。
 * 用户名为上马官网手机号或邮箱；密码为官网登录密码。注册/登录：https://www.shang-ma.com/ 或 https://passport.shang-ma.com/
 * 不使用 & 或 @ 分隔账号。
 * 兼容别名（仅当 SHANGMA_ACCOUNT 为空时）：SM_USERNAME + SM_PASSWORD（单账号，与上游一致）。
 * SHANGMA_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）。
 * SHANGMA_TIMEOUT_MS：请求超时毫秒，默认 15000（1000–60000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Copyright (c) 2023 HankZhao
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
    const identities = ["398c67c56c038d25", "scripts/sign_in.js", "sign_in.js", "sign_in"];
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

const TITLE = '上马官网每日签到';
const CATALOG_ID = '398c67c56c038d25';
const CREDENTIAL_ENV = 'SHANGMA_ACCOUNT';
const DRY_RUN_ENV = 'SHANGMA_DRY_RUN';
const APP_ID = '5PFuGr3Q7AA0vbJAFior';
const DEVICE_ID = 'Z8T23iCPme3DWGRAQLpJO2w0qY2Kq9-R';
const CHANNEL = 'windows-PC';
const SIGN_SALT = 'xbbaUe8PPVblLWaVP-iIJnUGhnDXmrm_';
const AES_NONCE = 'yVew0P4g8Mo8wNDyATc1_c5yns1UqZuag1Rim97MP11kovoWbhaJ6nBUUGN8Ph3h';
const JWT_APP =
  'JwtApp eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.MmwTuGPzzXKkDFQOX9Gn-Av9YO9J_4Q7LXeXr23js20';
const EMPTY_BODY_ENCRYPT = 'S1uAYaf/g6oBpv8DWUaQlQ==';
const ATTACH_URL = 'https://passport.shang-ma.com/api/sso/client/attach';
const LOGIN_URL = 'https://passport.shang-ma.com/api/login/index';
const SIGN_IN_URL = 'https://www.shang-ma.com/api/v1/user/integral/sign-in';
const UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36';
const DEFAULT_TIMEOUT_MS = 15000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const ACCOUNT_GAP_MS = 2000;
const MAX_REDIRECTS = 8;

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
  text = text.replace(/JwtUser\s+\S+/gi, 'JwtUser [已隐藏]');
  text = text.replace(/JwtApp\s+\S+/gi, 'JwtApp [已隐藏]');
  text = text.replace(/SHM_JWT_TOKEN=[^;\s]+/gi, 'SHM_JWT_TOKEN=[已隐藏]');
  text = text.replace(/Bearer\s+[A-Za-z0-9._+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}/g, '[邮箱已隐藏]');
  if (maskPhone) text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.SHANGMA_TIMEOUT_MS || '', 10);
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
  const filename = path.basename(process.argv[1] || 'candidate.js');
  const names = [
    CATALOG_ID,
    'scripts/shangma_sign.js',
    'shangma_sign.js',
    'shangma_auto_sign',
    'sign_in.js',
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

function md5Hex(text) {
  return crypto.createHash('md5').update(String(text), 'utf8').digest('hex');
}

function aesKeyIv() {
  const digest = crypto.createHash('sha256').update(AES_NONCE, 'utf8').digest('hex');
  const digestSign = md5Hex(digest);
  return {
    key: Buffer.from(digestSign.substring(0, 16), 'utf8'),
    iv: Buffer.from(digestSign.substring(16), 'utf8'),
  };
}

function encryptBody(plain) {
  const { key, iv } = aesKeyIv();
  const cipher = crypto.createCipheriv('aes-128-cbc', key, iv);
  const encrypted = Buffer.concat([cipher.update(String(plain), 'utf8'), cipher.final()]);
  return encrypted.toString('base64');
}

function concatParams(signParams) {
  return Object.entries(signParams)
    .map(([key, value]) => `${key}=${value}`)
    .join('&');
}

function marathonHeaders({ username, password, isLogin }) {
  const noncesr = Date.now();
  const ts = Math.floor(noncesr / 1000);
  const base = {
    appid: APP_ID,
    channel: CHANNEL,
    device_id: DEVICE_ID,
    language: 'zh-CN',
    model: '',
    noncesr,
    sys_version: '',
    ts,
    version: 'V1.0',
  };
  const signParams = isLogin
    ? { ...base, password, username }
    : base;
  const signature = md5Hex(concatParams(signParams) + SIGN_SALT);
  return {
    'Marathon-App-Id': APP_ID,
    'Marathon-Device-Id': DEVICE_ID,
    'Marathon-Ts': String(ts),
    'Marathon-Noncesr': String(noncesr),
    'Marathon-Language': 'zh-CN',
    'Marathon-Sign': signature,
    'Marathon-Version': 'V1.0',
    'Marathon-Model': '',
    'Marathon-Sys-Version': '',
    'Marathon-Channel': CHANNEL,
  };
}

function commonHeaders(authority, referer) {
  return {
    authority,
    accept: 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7,zh-TW;q=0.6',
    'content-type': 'application/json',
    referer,
    'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': UA,
  };
}

function cookieHeader(cookieList) {
  return cookieList
    .map((item) => {
      const [name, value] = Object.entries(item)[0];
      return `${encodeURIComponent(name)}=${encodeURIComponent(value)}`;
    })
    .join('; ');
}

function parseSetCookie(headers) {
  const raw = headers['set-cookie'];
  if (!raw) return [];
  const list = Array.isArray(raw) ? raw : [raw];
  const out = [];
  for (const header of list) {
    const first = String(header).split(';')[0];
    const at = first.indexOf('=');
    if (at < 1) continue;
    const name = first.slice(0, at).trim();
    const value = first.slice(at + 1).trim();
    const attrs = String(header)
      .split(';')
      .slice(1)
      .map((part) => part.trim().toLowerCase());
    let maxAge;
    for (const attr of attrs) {
      if (attr.startsWith('max-age=')) {
        maxAge = Number.parseInt(attr.slice(8), 10);
      }
    }
    if (maxAge !== undefined && maxAge <= 0) continue;
    if (!name) continue;
    remember(value);
    out.push({ [name]: value });
  }
  return out;
}

function parseAccounts() {
  const primary = process.env[CREDENTIAL_ENV];
  if (primary != null && String(primary).trim() !== '') {
    const lines = String(primary)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    return lines.map((line, index) => {
      const pipe = line.indexOf('|');
      if (pipe < 1 || pipe === line.length - 1) {
        return { index: index + 1, username: '', password: '', valid: false, reason: 'format' };
      }
      const username = line.slice(0, pipe).trim();
      const password = line.slice(pipe + 1);
      remember(username);
      remember(password);
      remember(line);
      const placeholder = /请替换|your[_-]?(phone|email|password|username)|changeme|example/i;
      const valid =
        Boolean(username) &&
        Boolean(password) &&
        !placeholder.test(username) &&
        !placeholder.test(password);
      return {
        index: index + 1,
        username,
        password,
        valid,
        reason: valid ? '' : 'placeholder',
      };
    });
  }

  const username = String(process.env.SM_USERNAME || '').trim();
  const password = process.env.SM_PASSWORD == null ? '' : String(process.env.SM_PASSWORD);
  if (!username && !password) return [];
  remember(username);
  remember(password);
  const placeholder = /请替换|your[_-]?(phone|email|password|username)|changeme|example/i;
  const valid =
    Boolean(username) &&
    Boolean(password) &&
    !placeholder.test(username) &&
    !placeholder.test(password);
  return [
    {
      index: 1,
      username,
      password,
      valid,
      reason: valid ? '' : username && password ? 'placeholder' : 'missing',
    },
  ];
}

function httpRequest(urlString, { method = 'GET', headers = {}, body = null, allowRedirectStatuses = false } = {}) {
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
            allowRedirectStatuses,
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

function showIdentity(obj, accountIndex) {
  if (!obj || typeof obj !== 'object') return;
  const bags = [obj.data, obj.user, obj.profile, obj.result, obj].filter(
    (v) => v && typeof v === 'object' && !Array.isArray(v)
  );
  const fields = [
    'nickname',
    'nick_name',
    'nickName',
    'username',
    'user_name',
    'userName',
    'display_name',
    'displayName',
    'name',
    'public_uid',
    'uid',
    'userId',
    'user_id',
  ];
  for (const bag of bags) {
    for (const field of fields) {
      const value = bag[field];
      if ((typeof value === 'string' && value) || typeof value === 'number') {
        const maskPhone = !['public_uid', 'uid', 'userId', 'user_id'].includes(field);
        log(`账号 ${accountIndex} 官方身份（${field}）：${redact(String(value), maskPhone)}`);
        return;
      }
    }
  }
}

async function attachCookies(url, cookies = [], depth = 0) {
  if (depth > MAX_REDIRECTS) throw new Error('redirect-loop');
  const headers = {
    ...marathonHeaders({ isLogin: false }),
    ...commonHeaders('passport.shang-ma.com', 'https://passport.shang-ma.com'),
  };
  if (cookies.length) headers.cookie = cookieHeader(cookies);
  const response = await httpRequest(url, {
    method: 'GET',
    headers,
    allowRedirectStatuses: true,
  });
  cookies.push(...parseSetCookie(response.headers));
  let verify;
  try {
    const parsed = JSON.parse(response.text || '{}');
    if (parsed && typeof parsed.verify === 'string' && parsed.verify) verify = parsed.verify;
  } catch {
    // attach 重定向中间页可能非 JSON
  }
  if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
    const next = new URL(response.headers.location, url).toString();
    return attachCookies(next, cookies, depth + 1);
  }
  if (response.statusCode < 200 || response.statusCode >= 400) {
    throw new Error(`attach-http-${response.statusCode}`);
  }
  if (verify) {
    remember(verify);
    cookies.push({ sso_verify_passport: verify });
  }
  return cookies;
}

async function login(account) {
  const initCookies = await attachCookies(ATTACH_URL, []);
  const headers = {
    ...marathonHeaders({
      username: account.username,
      password: account.password,
      isLogin: true,
    }),
    ...commonHeaders('passport.shang-ma.com', 'https://passport.shang-ma.com'),
    cookie: cookieHeader(initCookies),
    authorization: JWT_APP,
  };
  const body = JSON.stringify({
    encryptBody: encryptBody(JSON.stringify({ username: account.username, password: account.password })),
  });
  const response = await httpRequest(LOGIN_URL, { method: 'POST', headers, body });
  log(`登录响应状态码：${response.statusCode}；长度：${response.text ? response.text.length : 0} 字节`);
  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new Error(`login-http-${response.statusCode}`);
  }
  let payload = null;
  try {
    payload = JSON.parse(response.text);
  } catch {
    throw new Error('login-non-json');
  }
  if (payload && typeof payload === 'object') {
    const code = payload.code;
    if (code !== undefined && code !== 0 && code !== '0') {
      const msg =
        (typeof payload.message === 'string' && payload.message) ||
        (typeof payload.msg === 'string' && payload.msg) ||
        `code=${code}`;
      throw new Error(`login-business:${msg}`);
    }
    showIdentity(payload, account.index);
  }
  const jar = [...initCookies, ...parseSetCookie(response.headers)];
  const tokenEntry = jar.find((entry) => entry.SHM_JWT_TOKEN !== undefined);
  if (!tokenEntry || !tokenEntry.SHM_JWT_TOKEN) {
    throw new Error('login-missing-token');
  }
  remember(tokenEntry.SHM_JWT_TOKEN);
  return { token: tokenEntry.SHM_JWT_TOKEN, loginPayload: payload };
}

async function signIn(token) {
  const headers = {
    ...marathonHeaders({ isLogin: false }),
    ...commonHeaders('www.shang-ma.com', 'https://www.shang-ma.com/'),
    authorization: `JwtUser ${token}`,
  };
  const body = JSON.stringify({ encryptBody: EMPTY_BODY_ENCRYPT });
  const response = await httpRequest(SIGN_IN_URL, { method: 'POST', headers, body });
  log(`签到响应状态码：${response.statusCode}；长度：${response.text ? response.text.length : 0} 字节`);
  if (response.statusCode !== 200) {
    throw new Error(`signin-http-${response.statusCode}`);
  }
  let payload;
  try {
    payload = JSON.parse(response.text);
  } catch {
    throw new Error('signin-non-json');
  }
  if (!payload || typeof payload !== 'object') throw new Error('signin-invalid-body');
  const code = payload.code;
  const message =
    (typeof payload.message === 'string' && payload.message) ||
    (typeof payload.msg === 'string' && payload.msg) ||
    '';
  if (code === 0 || code === '0') {
    return { state: 'success', message: message || '签到成功', payload };
  }
  if (code === 5001 || code === '5001') {
    return { state: 'alreadyComplete', message: message || '请勿重复签到', payload };
  }
  throw new Error(`signin-business:${message || `code=${code}`}`);
}

async function runAccountLive(account) {
  log(`账号 ${account.index} | 子阶段 1/2：登录护照站`);
  const stageLogin = Date.now();
  const { token, loginPayload } = await login(account);
  log(`✅ 登录成功，已取得会话令牌 | 耗时 ${Date.now() - stageLogin}ms`);
  showIdentity(loginPayload, account.index);

  log(`账号 ${account.index} | 子阶段 2/2：每日积分签到`);
  const stageSign = Date.now();
  const result = await signIn(token);
  showIdentity(result.payload, account.index);
  if (result.state === 'success') log(`✅ ${redact(result.message)} | 耗时 ${Date.now() - stageSign}ms`);
  else log(`☑️ ${redact(result.message)} | 耗时 ${Date.now() - stageSign}ms`);
  return result.state;
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
    delete env.SHANGMA_ACCOUNT;
    delete env.SM_USERNAME;
    delete env.SM_PASSWORD;
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
    delete env.SHANGMA_ACCOUNT;
    delete env.SM_USERNAME;
    delete env.SM_PASSWORD;
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
    'redirect-loop': 'SSO 重定向次数过多',
    'login-non-json': '登录接口返回非 JSON',
    'login-missing-token': '登录成功但未返回 SHM_JWT_TOKEN',
    'signin-non-json': '签到接口返回非 JSON',
    'signin-invalid-body': '签到接口返回结构异常',
  };
  if (map[code]) return map[code];
  if (String(code).startsWith('attach-http-')) return `SSO 初始化 HTTP ${String(code).slice(12)}`;
  if (String(code).startsWith('login-http-')) return `登录 HTTP ${String(code).slice(11)}`;
  if (String(code).startsWith('signin-http-')) return `签到 HTTP ${String(code).slice(12)}`;
  if (String(code).startsWith('login-business:')) {
    return `登录失败：${redact(String(code).slice('login-business:'.length))}`;
  }
  if (String(code).startsWith('signin-business:')) {
    return `签到失败：${redact(String(code).slice('signin-business:'.length))}`;
  }
  return '请求失败';
}

async function main() {
  const started = Date.now();
  const dryRun = enabled(process.env[DRY_RUN_ENV]);
  const accounts = parseAccounts();
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
    log(
      `❌ 配置错误：缺少 ${CREDENTIAL_ENV}（每行 用户名|密码），或兼容别名 SM_USERNAME + SM_PASSWORD`
    );
  } else {
    for (const account of accounts) {
      if (!account.valid) {
        configurationError = true;
        if (account.reason === 'format') {
          log(`❌ 配置错误：账号 ${account.index} 格式无效；请使用「用户名|密码」，只在首个 | 拆分`);
        } else {
          log(`❌ 配置错误：账号 ${account.index} 凭据无效；请填写真实上马官网用户名与密码，勿使用示例占位`);
        }
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
      let outcome = 'failure';
      summary.tasks.total += 1;

      log(`账号 ${account.index} | 开始处理`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log(
            `⏭️ DRY_RUN_OK：账号 ${account.index} 用户名/密码格式通过；未请求 SSO/登录/签到接口，未验证真实业务`
          );
        } else {
          outcome = await runAccountLive(account);
        }
      } catch (err) {
        outcome = 'failure';
        log(`❌ ${reasonText(err && err.message)}；未确认签到成功`);
      }

      if (outcome === 'success') summary.tasks.success += 1;
      else if (outcome === 'alreadyComplete') summary.tasks.alreadyComplete += 1;
      else if (outcome === 'skipped') summary.tasks.skipped += 1;
      else summary.tasks.failure += 1;

      const accountFailed = outcome === 'failure';
      if (accountFailed) summary.failedAccounts += 1;
      else summary.successfulAccounts += 1;

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
  });
}

module.exports = { main, encryptBody, parseAccounts };
