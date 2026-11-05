// name: 吉利汽车签到
// cron: 37 0 * * *
/**
 * 吉利汽车 APP 每日签到 · 青龙独立维护版
 *
 * 上游：xqy0213/script · geely.js
 * 仓库：https://github.com/xqy0213/script
 * 分支：master
 * 提交：64301325a938956d92d40ea631f4439956d159ca
 * 授权：MIT
 * 原始说明亦引用 wf021325/qx task/geely.js（Quantumult X 抓包/定时模板）
 *
 * 功能盘点（主来源）：
 * - POST /api/v1/userSign/sign/risk 完成风控签到（MD5 X-Data-Sign）
 * - POST /api/v1/userSign/getSignMsg 查询当月累计/连续签到天数
 * - GET  /api/v1/growthSystem/energyBody/summary 查询能量体总量
 * - 可选从 iTunes lookup 读取最新 App 版本号（失败回退本地默认）
 * - 上游 QX/Surge Cookie 重写抓取改为青龙环境变量配置
 * - 移除上游从外网下载 CryptoJS、调试打印原始请求/响应、以及 Node 固定 exit(1) 等不安全行为
 * - 无发帖/评论/分享等公开内容副作用
 *
 * GEELY_ACCOUNTS（必填）：每个非空行一个账号。
 * 推荐格式：token|devicesn（仅在首个 | 处拆分，后续凭据原文保留）
 * 亦支持单行 JSON：{"token":"...","devicesn":"..."}
 * 获取方式：在本人设备抓包吉利汽车 APP（host=app.geely.com）请求头中的 token 与 deviceSN/devicesn；
 * 亦可配合 Quantumult X 等对 getMyCenterCounts 响应脚本抓取后写入本变量。不要提交或分享真实凭据。
 * 兼容别名：geely_val（仅当 GEELY_ACCOUNTS 为空时读取；格式相同）。
 * GEELY_APP_VERSION：可选 App 版本号覆盖；未设置时 live 尝试 iTunes 查询，失败使用 3.25.0。
 * GEELY_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递、不发业务请求）。
 * GEELY_TIMEOUT_MS：请求超时毫秒，默认 15000（1000–60000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Copyright (c) xqy0213/script contributors
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
      '02e05daa6ec7b4fc',
      'scripts/geely.js',
      'geely.js',
      'geely',
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

const crypto = require('node:crypto');
const https = require('node:https');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { URL } = require('node:url');
const { execFile } = require('node:child_process');

const TITLE = '吉利汽车签到';
const CATALOG_ID = '02e05daa6ec7b4fc';
const CREDENTIAL_ENV = 'GEELY_ACCOUNTS';
const CREDENTIAL_ALIASES = ['geely_val'];
const DRY_RUN_ENV = 'GEELY_DRY_RUN';
const DEFAULT_APP_VERSION = '3.25.0';
const APP_STORE_LOOKUP = 'https://itunes.apple.com/cn/lookup?id=1518762715';
const SIGN_CID = 'BLqo2nmmoPgGuJtFDWlUjRI2b1b';
const SIGN_SALT = "0]3K@'9MK+6Jf";
const DEFAULT_TIMEOUT_MS = 15000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const ACCOUNT_GAP_MS = 1500;

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
  if (typeof value === 'string' && value.trim()) secrets.add(value.trim());
}

function redact(value, maskPhone = true) {
  let text = String(value == null ? '' : value).replace(
    /[\r\n\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    ' '
  );
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
    if (secret) text = text.split(secret).join('[已隐藏]');
  }
  text = text.replace(
    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi,
    '[已隐藏]'
  );
  if (maskPhone) text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.GEELY_TIMEOUT_MS || '', 10);
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
    'scripts/geely.js',
    'geely.js',
    'geely',
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

function parseAccountLine(line, index) {
  remember(line);
  let label = '';
  let token = '';
  let devicesn = '';

  const trimmed = String(line || '').trim();
  if (!trimmed) {
    return { index, label, token, devicesn, valid: false, reason: '空行' };
  }

  if (trimmed.startsWith('{')) {
    try {
      const obj = JSON.parse(trimmed);
      token = String(obj.token || obj.Token || '').trim();
      devicesn = String(
        obj.devicesn || obj.deviceSN || obj.deviceSn || obj.device_sn || ''
      ).trim();
      if (typeof obj.label === 'string') label = obj.label.trim();
    } catch {
      return { index, label, token, devicesn, valid: false, reason: 'JSON 解析失败' };
    }
  } else {
    const pipe = trimmed.indexOf('|');
    if (pipe <= 0) {
      return {
        index,
        label,
        token,
        devicesn,
        valid: false,
        reason: '缺少 token|devicesn 或 JSON 凭据',
      };
    }
    // 仅在首个 | 处拆分；devicesn 侧后续分隔符原样保留
    token = trimmed.slice(0, pipe).trim();
    devicesn = trimmed.slice(pipe + 1).trim();
  }

  remember(token);
  remember(devicesn);

  const placeholder = /请替换|your[_-]?token|changeme|xxxxxxxx|XXXXXXXX/i;
  const valid =
    token.length >= 8 &&
    devicesn.length >= 8 &&
    !placeholder.test(token) &&
    !placeholder.test(devicesn);

  return {
    index,
    label,
    token,
    devicesn,
    valid,
    reason: valid
      ? ''
      : !token || !devicesn
        ? 'token 与 devicesn 均必填（App 升级后缺 devicesn 会失败）'
        : '凭据过短或为示例占位',
  };
}

function parseAccounts(raw) {
  return String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, i) => parseAccountLine(line, i + 1));
}

function formatSignDate(tsSec) {
  const d = new Date(tsSec * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

function buildSignHeaders(account, appVersion, body) {
  const ts = Math.floor(Date.now() / 1000);
  const signDate = formatSignDate(ts);
  const payload =
    body != null
      ? body
      : JSON.stringify({
          signDate,
          ts: String(ts),
          cId: SIGN_CID,
        });
  const signRaw = `cId=${SIGN_CID}&signDate=${ts * 1000}&ts=${ts}${SIGN_SALT}`;
  const sign = crypto.createHash('md5').update(signRaw, 'utf8').digest('hex');
  const sweet = {
    appVersion,
    deviceUUID: account.devicesn,
    geelyDeviceId: account.devicesn,
  };
  return {
    headers: {
      'X-Data-Sign': sign,
      appVersion,
      deviceSN: account.devicesn,
      sweet_security_info: JSON.stringify(sweet),
      token: account.token,
      platform: 'iOS',
      'User-Agent': `GLMainProject/${appVersion} (iPhone; iOS 17.6.1; Scale/2.00)`,
      'Content-Type': 'application/json',
      Accept: 'application/json, text/plain, */*',
    },
    body: payload,
    ts,
    signDate,
  };
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

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function showIdentity(obj, accountIndex) {
  if (!obj || typeof obj !== 'object') return;
  const bags = [obj.data, obj.user, obj.profile, obj].filter(
    (v) => v && typeof v === 'object' && !Array.isArray(v)
  );
  const fields = [
    'nickname',
    'nickName',
    'nick_name',
    'username',
    'userName',
    'user_name',
    'displayName',
    'display_name',
    'name',
    'publicUid',
    'public_uid',
    'uid',
  ];
  for (const bag of bags) {
    for (const field of fields) {
      const value = bag[field];
      if ((typeof value === 'string' && value.trim()) || typeof value === 'number') {
        const maskPhone = !['publicUid', 'public_uid', 'uid'].includes(field);
        log(`账号 ${accountIndex} 官方身份（${field}）：${redact(String(value), maskPhone)}`);
        return;
      }
    }
  }
}

async function resolveAppVersion(dryRun) {
  const override = String(process.env.GEELY_APP_VERSION || '').trim();
  if (override) return override;
  if (dryRun) return DEFAULT_APP_VERSION;
  try {
    const response = await httpRequest(APP_STORE_LOOKUP, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; QinglongGeelyCheckin/1.0)',
      },
    });
    const data = parseJson(response.text);
    const version = data && data.results && data.results[0] && data.results[0].version;
    if (typeof version === 'string' && version.trim()) return version.trim();
  } catch {
    // fall through
  }
  return DEFAULT_APP_VERSION;
}

function interpretSignIn(response) {
  const result = parseJson(response.text);
  if (!result || typeof result !== 'object') throw new Error('sign-non-json');
  const code = String(result.code == null ? '' : result.code);
  const message = typeof result.message === 'string' ? result.message : '';
  if (/token/i.test(code) || /token/i.test(message)) {
    throw new Error('credential-invalid');
  }
  if (response.statusCode === 200 && code === 'success') {
    return { state: 'success', message: message || '签到成功', result };
  }
  if (/已签到|请勿重复|重复操作/.test(message) || code === 'already') {
    return { state: 'alreadyComplete', message: message || '今日已签到', result };
  }
  throw new Error(`sign-business:${message || code || '签到失败'}`);
}

async function doSignIn(account, appVersion) {
  const built = buildSignHeaders(account, appVersion);
  const response = await httpRequest('https://app.geely.com/api/v1/userSign/sign/risk', {
    method: 'POST',
    headers: built.headers,
    body: built.body,
  });
  log(`签到响应状态码：${response.statusCode}；长度：${response.text ? response.text.length : 0} 字节`);
  return interpretSignIn(response);
}

async function getSignMsg(account) {
  const now = new Date();
  const body = JSON.stringify({
    year: String(now.getFullYear()),
    month: String(now.getMonth() + 1),
  });
  const response = await httpRequest('https://app.geely.com/api/v1/userSign/getSignMsg', {
    method: 'POST',
    headers: {
      token: account.token,
      'Content-Type': 'application/json',
      'User-Agent':
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/ios/geelyApp',
      Accept: 'application/json, text/plain, */*',
    },
    body,
  });
  const result = parseJson(response.text);
  if (!result || result.code !== 'success') {
    return { ok: false, message: '累计签到查询未成功' };
  }
  const days = result.data && result.data.continuousSignDay;
  showIdentity(result, account.index);
  return {
    ok: true,
    message: `累计签到：${days != null ? days : '?'}天`,
    result,
  };
}

async function getEnergySummary(account, appVersion) {
  const response = await httpRequest(
    'https://app.geely.com/api/v1/growthSystem/energyBody/summary',
    {
      method: 'GET',
      headers: {
        appVersion,
        deviceSN: account.devicesn,
        token: account.token,
        platform: 'iOS',
        'User-Agent': `GLMainProject/${appVersion} (iPhone; iOS 17.6.1; Scale/2.00)`,
        Accept: 'application/json, text/plain, */*',
      },
    }
  );
  const result = parseJson(response.text);
  if (!result || result.code !== 'success') {
    return { ok: false, message: '能量体查询未成功' };
  }
  const total = result.data && result.data.total;
  showIdentity(result, account.index);
  return {
    ok: true,
    message: `能量体：${total != null ? parseFloat(total) : '?'}`,
    result,
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
    delete env.GEELY_ACCOUNTS;
    delete env.geely_val;
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
    delete env.GEELY_ACCOUNTS;
    delete env.geely_val;
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
    'sign-non-json': '签到接口返回非 JSON',
    'credential-invalid': 'Token 无效或已过期，请重新抓包更新凭据',
  };
  if (map[code]) return map[code];
  if (String(code).startsWith('sign-business:')) {
    return `签到失败：${redact(String(code).slice('sign-business:'.length))}`;
  }
  return '请求失败';
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
      if (!account.valid) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} ${account.reason}`);
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`
  );

  let appVersion = DEFAULT_APP_VERSION;
  if (!configurationError) {
    log('阶段 2/3：账号签到与查询');
    const verStarted = Date.now();
    appVersion = await resolveAppVersion(dryRun);
    log(
      `App 版本：${appVersion}${dryRun ? '（预演未联网查询）' : ''} | 耗时 ${Date.now() - verStarted}ms`
    );

    for (let i = 0; i < accounts.length; i++) {
      const account = accounts[i];
      const began = Date.now();
      const who = account.label ? `（${account.label}）` : '';
      let signOutcome = 'failure';
      let queryOk = 0;
      let queryFail = 0;
      summary.tasks.total += 1;

      log(`账号 ${account.index}${who} | 子阶段 1/3：每日签到`);
      try {
        if (dryRun) {
          signOutcome = 'skipped';
          log('⏭️ DRY_RUN_OK：token/devicesn 格式通过；未请求签到接口，未验证真实业务');
        } else {
          const result = await doSignIn(account, appVersion);
          showIdentity(result.result, account.index);
          signOutcome = result.state;
          if (result.state === 'success') log(`✅ 签到：${redact(result.message)}`);
          else log(`☑️ 签到：${redact(result.message)}`);
        }
      } catch (err) {
        signOutcome = 'failure';
        log(`❌ ${reasonText(err && err.message)}；未确认签到成功`);
      }

      if (signOutcome === 'success') summary.tasks.success += 1;
      else if (signOutcome === 'alreadyComplete') summary.tasks.alreadyComplete += 1;
      else if (signOutcome === 'skipped') summary.tasks.skipped += 1;
      else summary.tasks.failure += 1;

      // 查询类能力：签到凭据错误时跳过；其余情况尽量查询（失败不单独判定账号失败）
      const skipQueries =
        dryRun || signOutcome === 'failure';

      log(`账号 ${account.index}${who} | 子阶段 2/3：累计签到查询`);
      if (dryRun) {
        log('⏭️ DRY_RUN_OK：跳过累计签到查询（断网）');
      } else if (skipQueries) {
        log('⏭️ 因签到未确认成功，跳过累计签到查询');
      } else {
        try {
          const msg = await getSignMsg(account);
          if (msg.ok) {
            queryOk += 1;
            log(`✅ ${redact(msg.message)}`);
          } else {
            queryFail += 1;
            log(`⚠️ ${msg.message}`);
          }
        } catch {
          queryFail += 1;
          log('⚠️ 累计签到查询失败');
        }
      }

      log(`账号 ${account.index}${who} | 子阶段 3/3：能量体查询`);
      if (dryRun) {
        log('⏭️ DRY_RUN_OK：跳过能量体查询（断网）');
      } else if (skipQueries) {
        log('⏭️ 因签到未确认成功，跳过能量体查询');
      } else {
        try {
          const energy = await getEnergySummary(account, appVersion);
          if (energy.ok) {
            queryOk += 1;
            log(`✅ ${redact(energy.message)}`);
          } else {
            queryFail += 1;
            log(`⚠️ ${energy.message}`);
          }
        } catch {
          queryFail += 1;
          log('⚠️ 能量体查询失败');
        }
      }

      const accountFailed = signOutcome === 'failure';
      if (accountFailed) summary.failedAccounts += 1;
      else summary.successfulAccounts += 1;

      log(
        `账号 ${account.index} 统计：总任务 1 | 成功 ${+(signOutcome === 'success')} | 已完成 ${+(
          signOutcome === 'alreadyComplete'
        )} | 跳过 ${+(signOutcome === 'skipped')} | 失败 ${+(signOutcome === 'failure')} | 查询成功 ${queryOk} | 查询告警 ${queryFail} | 耗时 ${
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
  buildSignHeaders,
  interpretSignIn,
  TITLE,
  CATALOG_ID,
};
