// name: 蔚来APP每日签到
// cron: 8 9 * * *
/**
 * 蔚来 APP 每日签到 · 青龙独立维护版
 *
 * 上游：zzhCloud/weilai-auto-checkin · weilai-auto-checkin.js（融合版）
 * 仓库：https://github.com/zzhCloud/weilai-auto-checkin
 * 分支：main
 * 提交：1c836570c573f19cc595ace7f4f2fbbfa7aeef37
 * 授权：MIT
 *
 * 同产品参考：
 * - weilai-checkin.js（签到接口、连续/累计天数解析、重试）
 * - weilai-token-capture.js（Authorization 获取说明；Surge 拦截不可用于青龙，改为环境变量）
 *
 * 功能盘点（主来源 + 兼容合并）：
 * - POST gateway-front-external.nio.com /moat/10086/c/award_cn/checkin 完成每日签到
 * - 识别 result_code=success 与 data.checked_in=true（今日已签）
 * - 展示连续签到天数、累计签到天数与签到提示 tip
 * - 多账号：WEILAI_TOKEN 每行一个 Authorization
 * - 上游 Surge $persistentStore / HTTP 拦截抓 Token 改为青龙环境变量手工配置
 * - 上游 $notification / Surge 推送改为青龙 notify 策略
 * - 无发帖/评论等公开内容副作用
 *
 * WEILAI_TOKEN（必填）：每行一个账号的 Authorization。可写完整「Bearer …」或仅写 Bearer 后的 token
 * （脚本会自动补全 Bearer 前缀）。可选备注：「备注|token」，只在首个 | 处拆分。
 * 获取方式：抓包蔚来 APP / app.nio.com / gateway-front-external.nio.com 请求头 Authorization；
 * 或登录 https://www.nio.cn/ 后从请求头复制。不使用 & 或 @ 分隔账号。
 * 兼容别名：WEILAI_AUTHORIZATION、weilai（仅当 WEILAI_TOKEN 为空时读取）。
 * WEILAI_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）。
 * WEILAI_TIMEOUT_MS：请求超时毫秒，默认 15000（1000–60000）。
 * WEILAI_MAX_RETRIES：业务失败或网络失败重试次数，默认 3（0–5）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Copyright (c) 2024 蔚来自动签到脚本
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
    const identities = ["276c7c90b90de432", "scripts/weilai_auto_checkin.js", "weilai_auto_checkin.js", "weilai_auto_checkin"];
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

const TITLE = '蔚来APP每日签到';
const CATALOG_ID = '276c7c90b90de432';
const CREDENTIAL_ENV = 'WEILAI_TOKEN';
const CREDENTIAL_ALIASES = ['WEILAI_AUTHORIZATION', 'weilai'];
const DRY_RUN_ENV = 'WEILAI_DRY_RUN';
const BASE_URL = 'https://gateway-front-external.nio.com';
const APP_ID = '10086';
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 NIOAppCN/5.48.5 (com.do1.WeiLaiApp; build:2549; OS:iOS) webview/lg _dsbridge';
const DEFAULT_TIMEOUT_MS = 15000;
const DEFAULT_MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const ACCOUNT_GAP_MS = 2000;

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
  text = text.replace(/Bearer\s+[A-Za-z0-9._+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}/g, '[邮箱已隐藏]');
  if (maskPhone) text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.WEILAI_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000 ? value : DEFAULT_TIMEOUT_MS;
}

function maxRetries() {
  const value = Number.parseInt(process.env.WEILAI_MAX_RETRIES || '', 10);
  return Number.isFinite(value) && value >= 0 && value <= 5 ? value : DEFAULT_MAX_RETRIES;
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
    'scripts/weilai_checkin.js',
    'weilai_checkin.js',
    'weilai-auto-checkin.js',
    'weilai',
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

function normalizeAuthorization(rawToken) {
  const token = String(rawToken || '').trim();
  if (!token) return '';
  if (/^Bearer\s+\S+/i.test(token)) return token.replace(/^Bearer\s+/i, 'Bearer ');
  return `Bearer ${token}`;
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
    const authorization = normalizeAuthorization(credential);
    remember(authorization);
    remember(credential);
    if (authorization.startsWith('Bearer ')) {
      remember(authorization.slice('Bearer '.length));
    }
    const valid =
      /^Bearer\s+\S{8,}$/i.test(authorization) &&
      !/请替换|your[_-]?token|changeme/i.test(authorization);
    return {
      index: index + 1,
      label,
      authorization,
      valid,
    };
  });
}

function formatCheckinTime(timestamp) {
  const value = Number(timestamp);
  if (!Number.isFinite(value) || value <= 0) return '';
  const ms = value > 1e12 ? value : value * 1000;
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
    .format(new Date(ms))
    .replace(/\//g, '-');
}

function extractCheckinStats(result) {
  const data = (result && result.data) || {};
  const stats = data.stats || {};
  const awardInfo = data.award_info || {};
  const continuousDays =
    stats.continuous_checkin_days ||
    stats.continuousDays ||
    stats.consecutive_days ||
    data.continuous_checkin_days ||
    data.continuousDays ||
    data.consecutive_days ||
    awardInfo.continuous_days ||
    awardInfo.continuous_checkin_days ||
    0;
  const accumulateDays =
    stats.accumulate_days ||
    stats.accumulateDays ||
    stats.total_days ||
    data.accumulate_days ||
    data.accumulateDays ||
    data.total_days ||
    awardInfo.total_days ||
    awardInfo.accumulate_days ||
    0;
  const checkinTime = stats.checkin_time || data.checkin_time || '';
  const tip = typeof data.tip === 'string' && data.tip ? data.tip : '';
  return { continuousDays, accumulateDays, checkinTime, tip };
}

function showIdentity(obj, accountIndex) {
  if (!obj || typeof obj !== 'object') return;
  const bags = [obj.data, obj.user, obj.profile, obj].filter(
    (v) => v && typeof v === 'object' && !Array.isArray(v)
  );
  const fields = [
    'nickname',
    'nick_name',
    'username',
    'user_name',
    'display_name',
    'displayName',
    'name',
    'public_uid',
    'uid',
  ];
  for (const bag of bags) {
    for (const field of fields) {
      const value = bag[field];
      if ((typeof value === 'string' && value) || typeof value === 'number') {
        const maskPhone = !['public_uid', 'uid'].includes(field);
        log(`账号 ${accountIndex} 官方身份（${field}）：${redact(value, maskPhone)}`);
        return;
      }
    }
  }
}

function buildCheckinUrl() {
  const params = new URLSearchParams({
    app_id: APP_ID,
    timestamp: String(Date.now()),
  });
  return `${BASE_URL}/moat/10086/c/award_cn/checkin?${params.toString()}`;
}

function buildHeaders(authorization) {
  return {
    authority: 'gateway-front-external.nio.com',
    'content-type': 'application/x-www-form-urlencoded',
    accept: 'application/json, text/plain, */*',
    authorization,
    'sec-fetch-site': 'cross-site',
    priority: 'u=3, i',
    'accept-language': 'zh-CN,zh-Hans;q=0.9',
    'accept-encoding': 'gzip, deflate, br',
    'sec-fetch-mode': 'cors',
    origin: 'null',
    'user-agent': UA,
    'sec-fetch-dest': 'empty',
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function interpretCheckin(response) {
  let result;
  try {
    result = JSON.parse(response.text);
  } catch {
    throw new Error('checkin-non-json');
  }
  if (!result || typeof result !== 'object') throw new Error('checkin-invalid-body');

  const { continuousDays, accumulateDays, checkinTime, tip } = extractCheckinStats(result);
  const timeText = formatCheckinTime(checkinTime);
  const statsParts = [];
  if (timeText) statsParts.push(`签到时间 ${timeText}`);
  if (continuousDays) statsParts.push(`连续签到 ${continuousDays} 天`);
  if (accumulateDays) statsParts.push(`累计签到 ${accumulateDays} 天`);
  const statsSuffix = statsParts.length ? `（${statsParts.join('；')}）` : '';

  if (response.statusCode === 200 && result.result_code === 'success') {
    return {
      state: 'success',
      tip: tip || '签到完成',
      message: `${tip || '签到完成'}${statsSuffix}`,
      result,
    };
  }
  if (result.data && result.data.checked_in === true) {
    return {
      state: 'alreadyComplete',
      tip: tip || '今日已签到',
      message: `${tip || '今日已签到'}${statsSuffix}`,
      result,
    };
  }
  const errorMsg =
    (typeof result.message === 'string' && result.message) ||
    (typeof result.error === 'string' && result.error) ||
    (typeof result.result_code === 'string' && result.result_code) ||
    '签到失败';
  throw new Error(`checkin-business:${errorMsg}`);
}

async function performCheckin(account) {
  const retries = maxRetries();
  let lastError = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      if (attempt > 0) {
        log(`⏳ 第 ${attempt + 1}/${retries + 1} 次重试…`);
        await sleep(RETRY_DELAY_MS);
      } else {
        log(`🚗 开始签到（尝试 ${attempt + 1}/${retries + 1}）`);
      }
      const response = await httpRequest(buildCheckinUrl(), {
        method: 'POST',
        headers: buildHeaders(account.authorization),
        body: 'event=checkin',
      });
      log(`响应状态码：${response.statusCode}；长度：${response.text ? response.text.length : 0} 字节`);
      return interpretCheckin(response);
    } catch (err) {
      lastError = err;
      const code = err && err.message ? String(err.message) : 'unknown';
      if (attempt >= retries) break;
      if (
        code === 'timeout' ||
        code === 'network-error' ||
        code === 'response-error' ||
        code === 'response-aborted' ||
        code.startsWith('checkin-business:')
      ) {
        continue;
      }
      break;
    }
  }
  throw lastError || new Error('checkin-failed');
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
    delete env.WEILAI_TOKEN;
    delete env.WEILAI_AUTHORIZATION;
    delete env.weilai;
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
    delete env.WEILAI_TOKEN;
    delete env.WEILAI_AUTHORIZATION;
    delete env.weilai;
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
    'checkin-non-json': '签到接口返回非 JSON',
    'checkin-invalid-body': '签到接口返回结构异常',
    'checkin-failed': '签到失败',
  };
  if (map[code]) return map[code];
  if (String(code).startsWith('checkin-business:')) {
    return `签到失败：${redact(String(code).slice('checkin-business:'.length))}`;
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
        log(
          `❌ 配置错误：账号 ${account.index} 的 Authorization 无效；请填写真实 Bearer Token，勿使用示例占位`
        );
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`
  );

  if (!configurationError) {
    log('阶段 2/3：账号签到');
    for (let i = 0; i < accounts.length; i++) {
      const account = accounts[i];
      const began = Date.now();
      const who = account.label ? `（${account.label}）` : '';
      let checkinOutcome = 'failure';
      summary.tasks.total += 1;

      log(`账号 ${account.index}${who} | 子阶段 1/1：每日签到`);
      try {
        if (dryRun) {
          checkinOutcome = 'skipped';
          log('⏭️ DRY_RUN_OK：Authorization 格式通过；未请求签到接口，未验证真实业务');
        } else {
          const result = await performCheckin(account);
          showIdentity(result.result, account.index);
          checkinOutcome = result.state;
          if (result.state === 'success') log(`✅ ${redact(result.message)}`);
          else log(`☑️ ${redact(result.message)}`);
        }
      } catch (err) {
        checkinOutcome = 'failure';
        log(`❌ ${reasonText(err && err.message)}；未确认签到成功`);
      }

      if (checkinOutcome === 'success') summary.tasks.success += 1;
      else if (checkinOutcome === 'alreadyComplete') summary.tasks.alreadyComplete += 1;
      else if (checkinOutcome === 'skipped') summary.tasks.skipped += 1;
      else summary.tasks.failure += 1;

      const accountFailed = checkinOutcome === 'failure';
      if (accountFailed) summary.failedAccounts += 1;
      else summary.successfulAccounts += 1;

      log(
        `账号 ${account.index} 统计：总任务 1 | 成功 ${+(checkinOutcome === 'success')} | 已完成 ${+(
          checkinOutcome === 'alreadyComplete'
        )} | 跳过 ${+(checkinOutcome === 'skipped')} | 失败 ${+(checkinOutcome === 'failure')} | 耗时 ${
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
  normalizeAuthorization,
  extractCheckinStats,
  interpretCheckin,
  readCredentialRaw,
};
