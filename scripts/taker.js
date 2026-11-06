// name: Taker每日挖矿
// cron: 26 8 * * *
/**
 * Taker Protocol 每日挖矿 · 青龙独立维护版
 *
 * 上游：jessdy/Taker-Bot-Jad · taker.js
 * 仓库：https://github.com/jessdy/Taker-Bot-Jad
 * 分支：main
 * 提交：a79c046964e6168d7a6dbd1115b2c4f3bc09eb3c
 * 授权：MIT
 *
 * 功能盘点（主来源）：
 * - 使用钱包私钥本地签名，调用 lightmining-api.taker.xyz 完成 nonce → 登录 → 用户信息
 * - 展示官方返回的 Twitter/X 绑定名（twName）、userId、totalReward 与钱包地址
 * - 查询 assignment/totalMiningTime，判断 24 小时冷却后是否可挖矿
 * - 调用 assignment/startMining 启动挖矿，再通过 Taker 主网合约 active() 链上激活
 * - 多钱包批量；上游 wallets.json / 无限循环改为青龙环境变量 + 每日 cron 单次执行
 * - 上游可选 MySQL 记分（含硬编码内网库地址与默认口令）已移除，不作为青龙任务副作用
 * - 上游硬编码 invitationCode 已改为可选环境变量，默认不附带他人邀请码
 *
 * TAKER_PRIVATE_KEY（必填）：每行一个钱包私钥。可选「地址|私钥」，只在首个 | 处拆分，
 * 若提供地址将与私钥推导地址核对。私钥可带或不带 0x。不使用 & 或 @ 分隔账号。
 * 获取方式：在 earn.taker.xyz 注册并绑定 X/Twitter 的钱包私钥（本人保管）；确保钱包有足够
 * TAKER 余额支付链上激活。勿将私钥写入公开仓库或日志。
 * 兼容别名：TAKER_WALLETS（仅当 TAKER_PRIVATE_KEY 为空时读取）。
 * TAKER_INVITE_CODE：可选邀请码；未设置时登录请求不附带邀请码。
 * TAKER_RPC_URL：可选 Taker RPC，默认 https://rpc-mainnet.taker.xyz/
 * TAKER_DRY_RUN=1：完全断网预演，只校验私钥格式并模拟流程与通知摘要（不投递）。
 * TAKER_TIMEOUT_MS：单次 HTTP/RPC 超时毫秒，默认 20000（1000–120000）。
 * TAKER_MAX_RETRIES：网络或业务失败重试次数，默认 3（0–5）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Copyright (c) [2025] [zlkcyber]
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
    const identities = ["e6b938e23e5d9750", "scripts/taker.js", "taker.js", "taker"];
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

const TITLE = 'Taker每日挖矿';
const CATALOG_ID = 'e6b938e23e5d9750';
const CREDENTIAL_ENV = 'TAKER_PRIVATE_KEY';
const CREDENTIAL_ALIASES = ['TAKER_WALLETS'];
const DRY_RUN_ENV = 'TAKER_DRY_RUN';
const API_BASE = 'https://lightmining-api.taker.xyz/';
const DEFAULT_RPC = 'https://rpc-mainnet.taker.xyz/';
const CONTRACT_ADDRESS = '0xB3eFE5105b835E5Dd9D206445Dbd66DF24b912AB';
const CONTRACT_ABI = ['function active() external'];
const DEFAULT_TIMEOUT_MS = 20000;
const DEFAULT_MAX_RETRIES = 3;
const RETRY_DELAY_MS = 3000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const ACCOUNT_GAP_MS = 2000;
const MINING_COOLDOWN_SEC = 24 * 60 * 60;

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
  text = text.replace(/\b0x[a-fA-F0-9]{64}\b/g, '0x[已隐藏]');
  text = text.replace(/\b[a-fA-F0-9]{64}\b/g, '[已隐藏]');
  text = text.replace(/Bearer\s+[A-Za-z0-9._+/=-]+/gi, 'Bearer [已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.TAKER_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 120000
    ? value
    : DEFAULT_TIMEOUT_MS;
}

function maxRetries() {
  const value = Number.parseInt(process.env.TAKER_MAX_RETRIES || '', 10);
  return Number.isFinite(value) && value >= 0 && value <= 5 ? value : DEFAULT_MAX_RETRIES;
}

function rpcUrl() {
  const value = String(process.env.TAKER_RPC_URL || '').trim();
  return value || DEFAULT_RPC;
}

function inviteCode() {
  return String(process.env.TAKER_INVITE_CODE || '').trim();
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
    'scripts/taker_mining.js',
    'taker_mining.js',
    'taker.js',
    'taker',
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
  for (const alias of CREDENTIAL_ALIASES) {
    const value = process.env[alias];
    if (value != null && String(value).trim() !== '') return String(value);
  }
  return '';
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
  if (!/^0x[a-fA-F0-9]{40}$/.test(value)) return value;
  return `${value.slice(0, 6)}…${value.slice(-4)}`;
}

function loadEthers() {
  try {
    return require('ethers');
  } catch {
    throw new Error('ethers-missing');
  }
}

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
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
          // dry-run / 语法预检允许仅校验十六进制格式；正式运行会再次强制加载
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
      valid: formatOk && !addressMismatch && !deriveError,
      formatOk,
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseJsonBody(text, label) {
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${label}-non-json`);
  }
}

function apiUrl(pathname) {
  return new URL(pathname.replace(/^\//, ''), API_BASE).toString();
}

async function withRetries(label, runner) {
  const retries = maxRetries();
  let lastError = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      if (attempt > 0) {
        log(`⏳ ${label} 第 ${attempt + 1}/${retries + 1} 次重试…`);
        await sleep(RETRY_DELAY_MS);
      }
      return await runner(attempt);
    } catch (err) {
      lastError = err;
      const code = err && err.message ? String(err.message) : 'unknown';
      if (attempt >= retries) break;
      if (
        code === 'timeout' ||
        code === 'network-error' ||
        code === 'response-error' ||
        code === 'response-aborted' ||
        code.endsWith('-retryable')
      ) {
        continue;
      }
      break;
    }
  }
  throw lastError || new Error(`${label}-failed`);
}

async function getNonce(walletAddress) {
  return withRetries('获取 nonce', async () => {
    const response = await httpRequest(apiUrl('wallet/generateNonce'), {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ walletAddress }),
    });
    log(`nonce 响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
    const body = parseJsonBody(response.text, 'nonce');
    const nonce = body && body.data && body.data.nonce;
    if (!(response.statusCode >= 200 && response.statusCode < 300) || !nonce) {
      throw new Error('nonce-retryable');
    }
    return String(nonce);
  });
}

async function signMessage(message, privateKey) {
  const { Wallet } = loadEthers();
  const wallet = new Wallet(privateKey);
  return wallet.signMessage(message);
}

async function login(address, message, signature) {
  return withRetries('登录', async () => {
    const payload = { address, message, signature };
    const code = inviteCode();
    if (code) payload.invitationCode = code;
    const response = await httpRequest(apiUrl('wallet/login'), {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    log(`登录响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
    const body = parseJsonBody(response.text, 'login');
    // 上游 axios：res.data.data.token → HTTP JSON 为 { data: { token } }
    const nested =
      (body && body.data && body.data.token) ||
      (body && body.data && body.data.data && body.data.data.token) ||
      (body && body.token);
    if (!(response.statusCode >= 200 && response.statusCode < 300) || !nested) {
      throw new Error('login-retryable');
    }
    remember(String(nested));
    return String(nested);
  });
}

async function getUser(token) {
  return withRetries('获取用户信息', async () => {
    const response = await httpRequest(apiUrl('user/getUserInfo'), {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });
    log(`用户信息响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
    const body = parseJsonBody(response.text, 'user');
    if (!(response.statusCode >= 200 && response.statusCode < 300) || !body || !body.data) {
      throw new Error('user-retryable');
    }
    return body.data;
  });
}

async function getMinerStatus(token) {
  return withRetries('查询挖矿状态', async () => {
    const response = await httpRequest(apiUrl('assignment/totalMiningTime'), {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });
    log(`挖矿状态响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
    const body = parseJsonBody(response.text, 'miner');
    if (!(response.statusCode >= 200 && response.statusCode < 300) || !body || !body.data) {
      throw new Error('miner-retryable');
    }
    return body.data;
  });
}

function isApiBusinessSuccess(body) {
  if (!body || typeof body !== 'object') return false;
  if (body.code === 200 || body.code === 0 || body.code === '200' || body.code === '0') return true;
  if (body.success === true || body.status === 'success' || body.status === true) return true;
  // 上游仅判断响应体真值；在 HTTP 2xx 且无明确失败码时视为可继续
  if (body.code == null && body.success == null && body.status == null) return true;
  return false;
}

async function startMine(token) {
  return withRetries('启动挖矿 API', async () => {
    const response = await httpRequest(apiUrl('assignment/startMining'), {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: '{}',
    });
    log(`启动挖矿响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
    const body = parseJsonBody(response.text, 'start-mine');
    if (!(response.statusCode >= 200 && response.statusCode < 300) || !isApiBusinessSuccess(body)) {
      throw new Error('start-mine-retryable');
    }
    return body;
  });
}

async function activateMiningOnChain(privateKey) {
  const { ethers, FetchRequest } = loadEthers();
  if (typeof FetchRequest === 'function' && typeof FetchRequest.setDefaultTimeout === 'function') {
    FetchRequest.setDefaultTimeout(timeoutMs());
  }
  const provider = new ethers.JsonRpcProvider(rpcUrl(), undefined, { staticNetwork: true });
  const wallet = new ethers.Wallet(privateKey, provider);
  const contract = new ethers.Contract(CONTRACT_ADDRESS, CONTRACT_ABI, wallet);
  const tx = await Promise.race([
    contract.active(),
    sleep(timeoutMs()).then(() => {
      throw new Error('timeout');
    }),
  ]);
  if (!tx || !tx.hash) throw new Error('onchain-no-tx');
  const receipt = await Promise.race([
    tx.wait(),
    sleep(Math.max(timeoutMs(), 60000)).then(() => {
      throw new Error('timeout');
    }),
  ]);
  if (!receipt || (receipt.status != null && Number(receipt.status) === 0)) {
    throw new Error('onchain-reverted');
  }
  return String(tx.hash);
}

function formatUnix(sec) {
  const value = Number(sec);
  if (!Number.isFinite(value) || value <= 0) return '';
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
    .format(new Date(value * 1000))
    .replace(/\//g, '-');
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

  log(`账号 ${account.index} | 子阶段 1/4：钱包登录`);
  const stage1 = Date.now();
  if (!account.address) {
    const { Wallet } = loadEthers();
    account.address = new Wallet(account.privateKey).address;
  }
  log(`账号 ${account.index} 钱包地址：${account.address}`);
  const nonce = await getNonce(account.address);
  const signature = await signMessage(nonce, account.privateKey);
  remember(signature);
  const token = await login(account.address, nonce, signature);
  log(`✅ 登录成功 | 耗时 ${Date.now() - stage1}ms`);
  mark('success');

  log(`账号 ${account.index} | 子阶段 2/4：用户信息`);
  const stage2 = Date.now();
  const user = await getUser(token);
  const twName = user.twName || user.twitterName || user.xName || '';
  const userId = user.userId != null ? String(user.userId) : '';
  const totalReward = user.totalReward != null ? String(user.totalReward) : '';
  if (twName) log(`账号 ${account.index} 官方身份（twName）：${twName}`);
  else if (userId) log(`账号 ${account.index} 官方身份（userId）：${userId}`);
  if (totalReward) log(`账号 ${account.index} 累计奖励：${totalReward}`);
  if (!twName) {
    log(`❌ 未绑定 Twitter/X，无法挖矿 | 耗时 ${Date.now() - stage2}ms`);
    mark('failure');
    return { ok: false, stages, reason: 'twitter-unbound' };
  }
  log(`✅ 用户信息已确认 | 耗时 ${Date.now() - stage2}ms`);
  mark('success');

  log(`账号 ${account.index} | 子阶段 3/4：挖矿窗口检查`);
  const stage3 = Date.now();
  const miner = await getMinerStatus(token);
  const lastMiningTime = Number(miner.lastMiningTime || 0);
  const nextMiningTime = lastMiningTime + MINING_COOLDOWN_SEC;
  const lastText = formatUnix(lastMiningTime);
  const nextText = formatUnix(nextMiningTime);
  if (lastText) log(`上次挖矿时间：${lastText}`);
  const nowSec = Math.floor(Date.now() / 1000);
  if (lastMiningTime > 0 && nowSec <= nextMiningTime) {
    log(`☑️ 今日挖矿已完成，下次可挖：${nextText || '冷却中'} | 耗时 ${Date.now() - stage3}ms`);
    mark('alreadyComplete');
    return { ok: true, alreadyComplete: true, stages };
  }
  log(`✅ 当前可启动挖矿 | 耗时 ${Date.now() - stage3}ms`);
  mark('success');

  log(`账号 ${account.index} | 子阶段 4/4：API 启动 + 链上激活`);
  const stage4 = Date.now();
  await startMine(token);
  log('API startMining 已接受');
  const txHash = await activateMiningOnChain(account.privateKey);
  log(`✅ 链上激活成功；交易哈希：${txHash} | 耗时 ${Date.now() - stage4}ms`);
  mark('success');
  return { ok: true, alreadyComplete: false, stages, txHash };
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
    delete env.TAKER_PRIVATE_KEY;
    delete env.TAKER_WALLETS;
    delete env.TAKER_INVITE_CODE;
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
    delete env.TAKER_PRIVATE_KEY;
    delete env.TAKER_WALLETS;
    delete env.TAKER_INVITE_CODE;
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
    'nonce-non-json': 'nonce 接口返回非 JSON',
    'login-non-json': '登录接口返回非 JSON',
    'user-non-json': '用户信息接口返回非 JSON',
    'miner-non-json': '挖矿状态接口返回非 JSON',
    'start-mine-non-json': '启动挖矿接口返回非 JSON',
    'nonce-retryable': '获取 nonce 失败',
    'login-retryable': '钱包登录失败',
    'user-retryable': '获取用户信息失败',
    'miner-retryable': '查询挖矿状态失败',
    'start-mine-retryable': '启动挖矿 API 失败',
    'onchain-no-tx': '链上激活未返回交易',
    'onchain-reverted': '链上激活交易失败',
    'twitter-unbound': '钱包未绑定 Twitter/X',
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
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${
      Date.now() - configStarted
    }ms`
  );

  if (!configurationError) {
    log('阶段 2/3：账号挖矿');
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
            }；未请求 API/RPC，未验证真实业务`
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
        log(`❌ ${reasonText(code)}；未确认挖矿成功`);
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
  readCredentialRaw,
  isApiBusinessSuccess,
};
