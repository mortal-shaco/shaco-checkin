#!/usr/bin/env node
// name: Web3Go每日签到
// cron: 48 8 * * *
/**
 * Web3Go / Reiki 每日签到 · 青龙独立维护版
 *
 * 上游：shuail0/web3go-chekin · src/web3go/web3go.js（类库）+ src/index.js（批量入口）
 * 仓库：https://github.com/shuail0/web3go-chekin
 * 分支：main
 * 提交：01afe7cb7a8d9718d6bd2cffa4ca6f79c73014f6
 * 授权：MIT（Copyright (c) 2024 shuail0）
 *
 * 功能盘点（主来源 web3go.js + 入口 index.js）：
 * - 使用钱包私钥本地 SIWE 签名，调用 reiki.web3go.xyz：
 *   POST /api/account/web3/web3_nonce → POST /api/account/web3/web3_challenge 登录
 * - PUT /api/checkin?day=YYYY-MM-DD 每日签到
 * - GET /api/profile 查询资料（金叶子等非敏感字段，用于核对身份）
 * - 类库另含 mintPass（BSC 合约 safeMint，消耗 Gas）；入口未调用，维护版默认关闭且不自动铸造
 * - 上游硬编码本机 CSV 私钥路径、本机代理、Ankr RPC、成功/失败 CSV 追加写入 → 全部移除
 * - 上游依赖 axios / random-useragent / https-proxy-agent / papaparse / 本地 ABI 文件
 *   → 维护版自实现 HTTPS，签名依赖可公开安装的 ethers；代理可选
 * - maintainedFeatureCoverage 为空，无已发布同产品重复覆盖
 *
 * WEB3GO_PRIVATE_KEY（必填）：每行一个钱包私钥。可选「地址|私钥」，只在首个 | 处拆分，
 * 若提供地址将与私钥推导地址核对。私钥可带或不带 0x。不使用 & 或 @ 分隔账号。
 * 获取方式：在 https://reiki.web3go.xyz 使用的以太坊钱包私钥（本人保管）。
 * 勿将私钥写入公开仓库或日志。
 * 兼容别名：WEB3GO_PRIVATE_KEYS、WEB3GO_WALLETS（仅当规范变量为空时读取）。
 * WEB3GO_PROXY：可选 HTTP(S) 代理 URL；设置时需已安装 https-proxy-agent。
 * WEB3GO_DRY_RUN=1：完全断网预演，只校验私钥格式并模拟流程与通知摘要（不投递）。
 * WEB3GO_TIMEOUT_MS：单次 HTTP 超时毫秒，默认 15000（1000–120000）。
 * WEB3GO_ENABLE_MINT：默认关闭。设为 1 时才允许铸造 Pass（高副作用、耗 Gas），本维护版仍拒绝执行铸造，
 *   避免默认可变链上状态；日常签到不需要铸造。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Copyright (c) 2024 shuail0
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
  let enabledFlag = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = [
      'be421593e7049fc0',
      'scripts/web3go_checkin.js',
      'web3go_checkin.js',
      'web3go.js',
      'web3go',
      'candidate.js',
    ];
    enabledFlag = selectors.some((selector) => {
      const pattern =
        '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  } else {
    enabledFlag = true;
  }
  process.env.QINGLONG_NOTIFY = enabledFlag ? '1' : '0';
})();
// qinglong-notification-policy: end

const https = require('node:https');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { URL } = require('node:url');
const { execFile } = require('node:child_process');

const TITLE = 'Web3Go每日签到';
const CATALOG_ID = 'be421593e7049fc0';
const CREDENTIAL_ENV = 'WEB3GO_PRIVATE_KEY';
const CREDENTIAL_ALIASES = ['WEB3GO_PRIVATE_KEYS', 'WEB3GO_WALLETS'];
const DRY_RUN_ENV = 'WEB3GO_DRY_RUN';
const BASE_URL = 'https://reiki.web3go.xyz';
const DEFAULT_TIMEOUT_MS = 15000;
const MAX_RESPONSE_BYTES = 512 * 1024;
const ACCOUNT_GAP_MS = 1500;
const USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Qinglong-Web3Go-CheckIn/1.0';

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
    if (secret && secret.length >= 6) text = text.split(secret).join('[已隐藏]');
  }
  text = text.replace(/\b0x[a-fA-F0-9]{64}\b/g, '0x[已隐藏]');
  text = text.replace(/\b[a-fA-F0-9]{64}\b/g, '[已隐藏]');
  text = text.replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._~+/=-]+/g, '[已隐藏]');
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
  const value = Number.parseInt(process.env.WEB3GO_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 120000
    ? value
    : DEFAULT_TIMEOUT_MS;
}

function proxyUrl() {
  return String(process.env.WEB3GO_PROXY || '').trim();
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
    'scripts/web3go_checkin.js',
    'web3go_checkin.js',
    'web3go.js',
    'web3go',
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

function loadEthers() {
  try {
    return require('ethers');
  } catch {
    throw new Error('ethers-missing');
  }
}

function normalizePrivateKey(raw) {
  let key = String(raw || '').trim();
  if (!key) return '';
  if (!key.startsWith('0x') && !key.startsWith('0X')) key = '0x' + key;
  return key;
}

function isValidPrivateKeyFormat(key) {
  return /^0x[a-fA-F0-9]{64}$/.test(key);
}

function shortAddress(address) {
  const value = String(address || '');
  if (!/^0x[a-fA-F0-9]{40}$/i.test(value)) return value;
  return `${value.slice(0, 6)}…${value.slice(-4)}`;
}

function readCredentialRaw() {
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
    .filter((line) => line && !line.startsWith('#'));
  return lines.map((line, index) => {
    remember(line);
    let expectedAddress = '';
    let credential = line;
    const pipe = line.indexOf('|');
    if (pipe > 0) {
      const left = line.slice(0, pipe).trim();
      const right = line.slice(pipe + 1).trim();
      if (/^0x[a-fA-F0-9]{40}$/i.test(left)) {
        expectedAddress = left;
        credential = right;
      }
    }
    const privateKey = normalizePrivateKey(credential);
    remember(privateKey);
    remember(privateKey.replace(/^0x/i, ''));
    const formatOk = isValidPrivateKeyFormat(privateKey);
    let address = '';
    let addressMismatch = false;
    let deriveError = '';
    if (formatOk) {
      try {
        const { Wallet } = loadEthers();
        address = new Wallet(privateKey).address;
        if (expectedAddress && expectedAddress.toLowerCase() !== address.toLowerCase()) {
          addressMismatch = true;
        }
      } catch (err) {
        if (err && err.message === 'ethers-missing') {
          address = expectedAddress || '';
        } else {
          deriveError = 'invalid-private-key';
        }
      }
    }
    return {
      index: index + 1,
      privateKey,
      address,
      expectedAddress,
      addressMismatch,
      deriveError,
      formatOk,
      valid: formatOk && !addressMismatch && !deriveError,
    };
  });
}

function createProxyAgent(targetUrl) {
  const proxy = proxyUrl();
  if (!proxy) return null;
  let ProxyAgent;
  try {
    ({ HttpsProxyAgent: ProxyAgent } = require('https-proxy-agent'));
  } catch {
    throw new Error('proxy-agent-missing');
  }
  return new ProxyAgent(proxy);
}

function baseHeaders() {
  return {
    Accept: 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    Origin: BASE_URL,
    Referer: `${BASE_URL}/taskboard`,
    'User-Agent': USER_AGENT,
  };
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
    let agent = null;
    try {
      agent = createProxyAgent(urlString);
    } catch (err) {
      return fail(err && err.message ? String(err.message) : 'proxy-agent-missing');
    }
    const options = {
      protocol: parsed.protocol,
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
      path: parsed.pathname + parsed.search,
      method,
      headers: reqHeaders,
      timeout: remaining,
    };
    if (agent) options.agent = agent;
    const req = lib.request(options, (res) => {
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
    });
    req.on('timeout', () => {
      fail('timeout');
      req.destroy();
    });
    req.on('error', () => fail('network-error'));
    if (payload) req.write(payload);
    req.end();
  });
}

function parseJsonBody(text, label) {
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${label}-non-json`);
  }
}

function randomSignNonce(length = 17) {
  const alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
  let out = '';
  for (let i = 0; i < length; i++) {
    out += alphabet.charAt(Math.floor(Math.random() * alphabet.length));
  }
  return out;
}

function buildSiweMessage(address, serverNonce, signNonce, issuedAt) {
  return (
    `reiki.web3go.xyz wants you to sign in with your Ethereum account:\n` +
    `${address}\n\n` +
    `Welcome to Web3Go! Click to sign in and accept the Web3Go Terms of Service. ` +
    `This request will not trigger any blockchain transaction or cost any gas fees. ` +
    `Your authentication status will reset after 7 days. Wallet address: ${address} Nonce: ${serverNonce}\n\n` +
    `URI: https://reiki.web3go.xyz\n` +
    `Version: 1\n` +
    `Chain ID: 56\n` +
    `Nonce: ${signNonce}\n` +
    `Issued At: ${issuedAt}`
  );
}

function pickIdentity(profile) {
  if (!profile || typeof profile !== 'object') return '';
  const candidates = [profile];
  if (profile.data && typeof profile.data === 'object') candidates.push(profile.data);
  if (profile.user && typeof profile.user === 'object') candidates.push(profile.user);
  if (profile.account && typeof profile.account === 'object') candidates.push(profile.account);
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
        if (/^0x[a-fA-F0-9]{40}$/.test(value)) continue;
        return value;
      }
    }
  }
  return '';
}

function summarizeProfile(profile) {
  if (!profile || typeof profile !== 'object') return '';
  const data =
    profile.data && typeof profile.data === 'object' && !Array.isArray(profile.data)
      ? profile.data
      : profile;
  const parts = [];
  for (const [label, key] of [
    ['金叶子', 'goldenLeaf'],
    ['金叶子', 'goldLeaf'],
    ['金叶子', 'leaf'],
    ['积分', 'point'],
    ['积分', 'points'],
    ['积分', 'score'],
    ['等级', 'level'],
  ]) {
    if (data[key] !== undefined && data[key] !== null && String(data[key]).trim() !== '') {
      const text = sanitizeDisplayText(data[key]);
      if (text && !parts.some((p) => p.includes(text))) parts.push(`${label} ${text}`);
    }
  }
  return parts.join('；');
}

function isAlreadyCheckedMessage(text) {
  const msg = String(text || '');
  if (!msg) return false;
  return /already\s*checked|already\s*check[\s-]*in|already\s*signed|今日已签|已经签到|已签到|重复签到/i.test(
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

function classifyCheckIn(statusCode, payload, rawText) {
  if (statusCode === 401 || statusCode === 403) {
    return { ok: false, state: 'failure', message: `登录态失效（HTTP ${statusCode}）` };
  }
  if (!(statusCode >= 200 && statusCode < 300)) {
    return { ok: false, state: 'failure', message: `签到请求失败（HTTP ${statusCode}）` };
  }
  const msg = sanitizeDisplayText(
    (payload && (payload.msg || payload.message || payload.error || payload.detail)) || rawText || ''
  );
  if (isAlreadyCheckedMessage(msg)) {
    return { ok: true, state: 'alreadyComplete', message: msg || '今日已签到' };
  }
  if (payload === true || payload === 'ok' || payload === 'OK') {
    return { ok: true, state: 'success', message: '签到成功' };
  }
  if (payload && typeof payload === 'object') {
    const code = payload.code ?? payload.status ?? payload.statusCode;
    if (
      code === 0 ||
      code === '0' ||
      code === 200 ||
      code === '200' ||
      code === 'ok' ||
      code === 'OK' ||
      code === true
    ) {
      return { ok: true, state: 'success', message: msg || '签到成功' };
    }
    const flag = payload.success ?? payload.ok ?? payload.result;
    if (flag === false || flag === 'false' || flag === 0) {
      return { ok: false, state: 'failure', message: msg || '签到失败' };
    }
    if (flag === true || flag === 'true' || flag === 1 || flag === '1') {
      return { ok: true, state: 'success', message: msg || '签到成功' };
    }
    if (msg && /fail|error|invalid|denied|拒绝|失败|错误/i.test(msg)) {
      return { ok: false, state: 'failure', message: msg };
    }
    if (isSuccessMessage(msg)) {
      return { ok: true, state: 'success', message: msg };
    }
    // 上游仅打印响应；HTTP 2xx 且无明确失败字段时视为签到已接受
    return { ok: true, state: 'success', message: msg || '签到请求已接受' };
  }
  if (!String(rawText || '').trim()) {
    return { ok: true, state: 'success', message: '签到请求已接受（空响应）' };
  }
  if (isAlreadyCheckedMessage(rawText)) {
    return { ok: true, state: 'alreadyComplete', message: sanitizeDisplayText(rawText) };
  }
  if (isSuccessMessage(rawText)) {
    return { ok: true, state: 'success', message: sanitizeDisplayText(rawText) || '签到成功' };
  }
  return { ok: false, state: 'failure', message: '签到接口返回了无法识别的业务响应' };
}

async function loginWithWallet(privateKey, address) {
  const nonceUrl = `${BASE_URL}/api/account/web3/web3_nonce`;
  const nonceRes = await httpRequest(nonceUrl, {
    method: 'POST',
    headers: { ...baseHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ address }),
  });
  log(`nonce 响应状态码：${nonceRes.statusCode}；长度：${nonceRes.text.length} 字节`);
  if (!(nonceRes.statusCode >= 200 && nonceRes.statusCode < 300)) {
    throw new Error('nonce-http');
  }
  const nonceBody = parseJsonBody(nonceRes.text, 'nonce');
  const serverNonce = nonceBody && nonceBody.nonce;
  if (!serverNonce) throw new Error('nonce-missing');

  const signNonce = randomSignNonce(17);
  const issuedAt = new Date().toISOString();
  const msg = buildSiweMessage(address, serverNonce, signNonce, issuedAt);
  const { Wallet } = loadEthers();
  const wallet = new Wallet(privateKey);
  const signature = await wallet.signMessage(msg);
  remember(signature);

  const challengeUrl = `${BASE_URL}/api/account/web3/web3_challenge`;
  const challengePayload = {
    address,
    nonce: serverNonce,
    challenge: JSON.stringify({ msg }),
    signature,
  };
  const challengeRes = await httpRequest(challengeUrl, {
    method: 'POST',
    headers: { ...baseHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(challengePayload),
  });
  log(`challenge 响应状态码：${challengeRes.statusCode}；长度：${challengeRes.text.length} 字节`);
  if (!(challengeRes.statusCode >= 200 && challengeRes.statusCode < 300)) {
    throw new Error('challenge-http');
  }
  const challengeBody = parseJsonBody(challengeRes.text, 'challenge');
  const token =
    (challengeBody &&
      challengeBody.extra &&
      (challengeBody.extra.token || challengeBody.extra.accessToken)) ||
    (challengeBody && challengeBody.token) ||
    (challengeBody && challengeBody.data && challengeBody.data.token);
  if (!token) throw new Error('token-missing');
  remember(String(token));
  return String(token);
}

async function fetchProfile(token) {
  const response = await httpRequest(`${BASE_URL}/api/profile`, {
    method: 'GET',
    headers: {
      ...baseHeaders(),
      Authorization: `Bearer ${token}`,
    },
  });
  log(`profile 响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
  if (!(response.statusCode >= 200 && response.statusCode < 300)) {
    return null;
  }
  try {
    return parseJsonBody(response.text, 'profile');
  } catch {
    return null;
  }
}

async function claimCheckIn(token) {
  const day = new Date().toISOString().split('T')[0];
  const url = `${BASE_URL}/api/checkin?day=${encodeURIComponent(day)}`;
  const response = await httpRequest(url, {
    method: 'PUT',
    headers: {
      ...baseHeaders(),
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: '{}',
  });
  log(`checkin 响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
  let payload = null;
  try {
    payload = parseJsonBody(response.text, 'checkin');
  } catch {
    payload = null;
  }
  return classifyCheckIn(response.statusCode, payload, response.text);
}

async function processAccount(account) {
  const stages = {
    total: 0,
    success: 0,
    alreadyComplete: 0,
    skipped: 0,
    failure: 0,
  };
  const mark = (key) => {
    stages.total += 1;
    stages[key] += 1;
  };

  if (!account.address) {
    const { Wallet } = loadEthers();
    account.address = new Wallet(account.privateKey).address;
  }

  log(`账号 ${account.index} | 子阶段 1/3：钱包登录`);
  const stage1 = Date.now();
  log(`账号 ${account.index} 钱包地址：${account.address}`);
  const token = await loginWithWallet(account.privateKey, account.address);
  log(`✅ 登录成功 | 耗时 ${Date.now() - stage1}ms`);
  mark('success');

  log(`账号 ${account.index} | 子阶段 2/3：资料查询`);
  const stage2 = Date.now();
  let identity = '';
  try {
    const profile = await fetchProfile(token);
    identity = pickIdentity(profile);
    const summary = summarizeProfile(profile);
    if (identity) log(`账号 ${account.index} 官方身份：${sanitizeDisplayText(identity)}`);
    if (summary) log(`账号 ${account.index} 资料摘要：${redact(summary)}`);
    log(`✅ 资料查询完成 | 耗时 ${Date.now() - stage2}ms`);
    mark('success');
  } catch {
    log(`⚠️ 资料查询失败（不阻断签到） | 耗时 ${Date.now() - stage2}ms`);
    mark('skipped');
  }

  log(`账号 ${account.index} | 子阶段 3/3：每日签到`);
  const stage3 = Date.now();
  const result = await claimCheckIn(token);
  if (result.ok && result.state === 'success') {
    log(`✅ ${redact(result.message)} | 耗时 ${Date.now() - stage3}ms`);
    mark('success');
    return { ok: true, alreadyComplete: false, stages, identity };
  }
  if (result.ok && result.state === 'alreadyComplete') {
    log(`☑️ ${redact(result.message)} | 耗时 ${Date.now() - stage3}ms`);
    mark('alreadyComplete');
    return { ok: true, alreadyComplete: true, stages, identity };
  }
  log(`❌ ${redact(result.message)} | 耗时 ${Date.now() - stage3}ms`);
  mark('failure');
  return { ok: false, stages, identity, reason: result.message };
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
    delete env.WEB3GO_PROXY;
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
    delete env.WEB3GO_PROXY;
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
    'ethers-missing': '缺少依赖 ethers（请 npm 安装 ethers@6）',
    'proxy-agent-missing': '已设置 WEB3GO_PROXY 但缺少 https-proxy-agent',
    'nonce-non-json': 'nonce 接口返回非 JSON',
    'challenge-non-json': 'challenge 接口返回非 JSON',
    'checkin-non-json': '签到接口返回非 JSON',
    'nonce-http': '获取 nonce 失败',
    'nonce-missing': 'nonce 缺失',
    'challenge-http': '钱包登录 challenge 失败',
    'token-missing': '登录未返回 token',
    'invalid-private-key': '私钥无效',
  };
  if (map[code]) return map[code];
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
  console.log('========================================');

  log('阶段 1/3：配置检查');
  const configStarted = Date.now();
  let configurationError = false;

  if (enabled(process.env.WEB3GO_ENABLE_MINT)) {
    log('⚠️ WEB3GO_ENABLE_MINT 已设置，但维护版拒绝自动铸造 Pass（耗 Gas）；仅执行每日签到');
  }

  if (!accounts.length) {
    configurationError = true;
    log(
      `❌ 配置错误：缺少 ${CREDENTIAL_ENV}（或兼容别名 ${CREDENTIAL_ALIASES.join(' / ')}）的非空账号行`
    );
  } else {
    for (const account of accounts) {
      if (!account.formatOk) {
        configurationError = true;
        log(
          `❌ 配置错误：账号 ${account.index} 私钥格式无效；需 64 位十六进制（可选 0x），勿使用示例占位`
        );
      } else if (account.addressMismatch) {
        configurationError = true;
        log(
          `❌ 配置错误：账号 ${account.index} 行内地址与私钥推导地址不一致（${shortAddress(
            account.expectedAddress
          )}）`
        );
      } else if (account.deriveError) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} ${reasonText(account.deriveError)}`);
      } else if (!dryRun) {
        try {
          loadEthers();
        } catch {
          configurationError = true;
          log(`❌ 配置错误：${reasonText('ethers-missing')}`);
          break;
        }
        if (proxyUrl()) {
          try {
            createProxyAgent(BASE_URL);
          } catch (err) {
            configurationError = true;
            log(`❌ 配置错误：${reasonText(err && err.message)}`);
            break;
          }
        }
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${
      Date.now() - configStarted
    }ms`
  );

  if (!configurationError) {
    log('阶段 2/3：账号签到');
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
            `⏭️ DRY_RUN_OK：私钥格式通过${
              account.address ? `；推导地址 ${account.address}` : ''
            }；未请求网络，未验证真实业务`
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
          log(
            `账号 ${account.index} 统计：总任务 ${result.stages.total} | 成功 ${result.stages.success} | 已完成 ${result.stages.alreadyComplete} | 跳过 ${result.stages.skipped} | 失败 ${result.stages.failure} | 耗时 ${Date.now() - began}ms`
          );
        }
      } catch (err) {
        summary.failedAccounts += 1;
        summary.tasks.total += 1;
        summary.tasks.failure += 1;
        const code = err && err.message ? String(err.message) : 'unknown';
        log(`❌ ${reasonText(code)}；未确认签到成功`);
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
  normalizePrivateKey,
  isValidPrivateKeyFormat,
  classifyCheckIn,
  buildSiweMessage,
  CREDENTIAL_ENV,
  DRY_RUN_ENV,
};
