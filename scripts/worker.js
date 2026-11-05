#!/usr/bin/env node
// name: 科研通 AbleSci 每日签到
// cron: 9 8 * * *
/**
 * 科研通 AbleSci 每日签到 · 青龙独立维护版
 *
 * 上游：youkq95/ablesci · worker.js
 * 仓库：https://github.com/youkq95/ablesci
 * 分支：main · 提交：c580f5092b31b97093d6fe70f40de4f5588068be
 * 授权：MIT（Copyright (c) 2023 Kaiqiang）
 *
 * 功能盘点（主来源 worker.js；maintainedFeatureCoverage 为空，项目内无已发布同产品脚本）：
 * - 使用浏览器登录 Cookie 对 https://www.ablesci.com/user/sign 发起 GET 签到
 * - 识别签到成功（业务 code=0）、今日已签到文案、登录失效与 HTTP/网络失败
 * - 展示接口返回的积分奖励、当前积分、连续签到天数等非敏感业务字段
 * - 上游为 Cloudflare Workers 定时/HTTP 入口与单变量 COOKIE；维护版改为青龙 cron + 多账号
 * - 无发帖/评论等公开内容副作用
 *
 * ABLESCI_COOKIE（必填）：每行一个账号的完整 Cookie 字符串。不用 & 或 @ 分隔账号。
 * 获取：浏览器登录 https://www.ablesci.com → F12 网络面板 → 复制本站请求头 Cookie
 * （通常含 _identity-frontend 等会话字段；填写完整 Cookie，勿只截取部分）。
 * COOKIE（可选兼容）：上游 Cloudflare Worker 变量名；当 ABLESCI_COOKIE 为空时作为兼容输入。
 * ABLESCI_USER_AGENT（可选）：全局 UA；留空用默认浏览器 UA。
 * ABLESCI_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）。
 * ABLESCI_TIMEOUT_MS：请求超时毫秒，默认 15000（1000–60000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 * Copyright (c) 2023 Kaiqiang
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
    const identities = ["ac5bf2222e757d4e", "scripts/worker.js", "worker.js", "worker"];
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

const TITLE = '科研通 AbleSci 每日签到';
const CATALOG_ID = 'ac5bf2222e757d4e';
const CREDENTIAL_ENV = 'ABLESCI_COOKIE';
const LEGACY_CREDENTIAL_ENV = 'COOKIE';
const DRY_RUN_ENV = 'ABLESCI_DRY_RUN';
const SIGN_URL = 'https://www.ablesci.com/user/sign';
const REFERER = 'https://www.ablesci.com/';
const DEFAULT_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36';
const DEFAULT_TIMEOUT_MS = 15000;
const MAX_RESPONSE_BYTES = 256 * 1024;

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
  text = text.replace(/(Cookie|Authorization)=([^;\s]+)/gi, '$1=[已隐藏]');
  text = text.replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/_identity-frontend=[^;\s]*/gi, '_identity-frontend=[已隐藏]');
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
  const value = Number.parseInt(process.env.ABLESCI_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000 ? value : DEFAULT_TIMEOUT_MS;
}

function userAgent() {
  const raw = String(process.env.ABLESCI_USER_AGENT || '').trim();
  return raw || DEFAULT_UA;
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
    'scripts/ablesci_checkin.js',
    'ablesci_checkin.js',
    'ablesci',
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

function cookieLooksValid(cookie) {
  if (!cookie || /[\x00-\x1f\x7f]/.test(cookie)) return false;
  if (cookie.length < 8 || cookie.length > 16384) return false;
  return /(?:^|;\s*)[^=;\s]+=\S/.test(cookie);
}

function credentialRaw() {
  const primary = String(process.env[CREDENTIAL_ENV] || '');
  if (primary.trim()) return primary;
  return String(process.env[LEGACY_CREDENTIAL_ENV] || '');
}

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line, index) => {
    remember(line);
    const valid = cookieLooksValid(line);
    return {
      index: index + 1,
      cookie: line,
      valid,
    };
  });
}

function httpRequest(urlString, { method = 'GET', headers = {} } = {}) {
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
    const req = lib.request(
      {
        protocol: parsed.protocol,
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
        path: parsed.pathname + parsed.search,
        method,
        headers,
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
    req.end();
  });
}

function looksLikeLoginHtml(text) {
  const sample = String(text || '').slice(0, 4000).toLowerCase();
  if (!sample) return false;
  if (!sample.includes('<html') && !sample.includes('<!doctype') && !sample.includes('<form')) {
    return false;
  }
  return (
    sample.includes('/site/login') ||
    sample.includes('name="password"') ||
    sample.includes("name='password'") ||
    (sample.includes('登录') &&
      (sample.includes('password') || sample.includes('passwd') || sample.includes('用户名')))
  );
}

function isLoginMessage(text) {
  const msg = String(text || '');
  return (
    /请先登录|需要登录|未登录|登录已失效|登录失效|登录超时|请重新登录|未登录或登录已过期/.test(
      msg
    ) || /not\s*logged\s*in|please\s*login|login\s*required|unauthorized/i.test(msg)
  );
}

function isAlreadyCheckedMessage(text) {
  const msg = String(text || '');
  if (!msg) return false;
  if (/您今天已于.+签到/.test(msg)) return true;
  if (/今日已签到|今天已签到|已经签到|已签到过|重复签到|already\s*checked|already\s*signed/i.test(msg)) {
    return true;
  }
  return false;
}

function optionalMetric(data, key) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
  if (!Object.prototype.hasOwnProperty.call(data, key)) return null;
  const value = data[key];
  if (value == null || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value === 'string') {
    const text = value.trim();
    return text || null;
  }
  return null;
}

function pickIdentity(payload) {
  const bags = [];
  if (payload && typeof payload === 'object') {
    bags.push(payload);
    if (payload.data && typeof payload.data === 'object') bags.push(payload.data);
    if (payload.user && typeof payload.user === 'object') bags.push(payload.user);
  }
  for (const bag of bags) {
    for (const key of ['nickname', 'username', 'name', 'displayName', 'display_name', 'uid']) {
      if (bag[key] !== undefined && bag[key] !== null && String(bag[key]).trim()) {
        return String(bag[key]).trim();
      }
    }
  }
  return '';
}

function buildSuccessText(payload) {
  const parts = [];
  const msg = sanitizeDisplayText(payload && (payload.msg || payload.message), '签到成功');
  parts.push(msg);
  const data = payload && payload.data;
  const signpoint = optionalMetric(data, 'signpoint');
  const points = optionalMetric(data, 'points');
  const signcount = optionalMetric(data, 'signcount');
  const signDays = signcount != null ? signcount : optionalMetric(data, 'sign_days');
  if (signpoint != null) parts.push(`本次积分+${signpoint}`);
  if (points != null) parts.push(`当前积分${points}`);
  if (signDays != null) parts.push(`连续${signDays}天`);
  return parts.join('；');
}

function classifySignResponse(response) {
  const status = Number(response && response.statusCode);
  const rawText = String((response && response.text) || '');

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
    return { ok: false, state: 'failure', message: `科研通服务暂时异常（HTTP ${status}）` };
  }
  if (status >= 400 && status < 500) {
    return { ok: false, state: 'failure', message: `请求被拒绝（HTTP ${status}）` };
  }
  if (status < 200 || status >= 300) {
    return { ok: false, state: 'failure', message: `请求失败（HTTP ${status}）` };
  }

  if (looksLikeLoginHtml(rawText) || isLoginMessage(rawText)) {
    return {
      ok: false,
      state: 'failure',
      message: '登录状态已失效，请重新获取 Cookie',
    };
  }

  let payload = null;
  try {
    payload = JSON.parse(rawText);
  } catch {
    payload = null;
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return {
      ok: false,
      state: 'failure',
      message: '签到接口返回了无法识别的非 JSON 响应',
    };
  }

  const msg = sanitizeDisplayText(payload.msg || payload.message || '');
  const identity = pickIdentity(payload);

  if (isLoginMessage(msg)) {
    return {
      ok: false,
      state: 'failure',
      message: msg || '登录状态已失效，请重新获取 Cookie',
      identity,
    };
  }
  if (isAlreadyCheckedMessage(msg)) {
    return {
      ok: true,
      state: 'alreadyComplete',
      message: msg || '今天已经签到',
      identity,
    };
  }
  if (Number(payload.code) === 0) {
    return {
      ok: true,
      state: 'success',
      message: buildSuccessText(payload),
      identity,
    };
  }
  if (msg) {
    return { ok: false, state: 'failure', message: msg, identity };
  }
  return {
    ok: false,
    state: 'failure',
    message: '签到接口返回了无法识别的业务响应',
    identity,
  };
}

async function runAccount(account) {
  const response = await httpRequest(SIGN_URL, {
    method: 'GET',
    headers: {
      Accept: 'application/json, text/javascript, */*; q=0.01',
      'Accept-Language': 'zh-CN,zh;q=0.9',
      Cookie: account.cookie,
      DNT: '1',
      Referer: REFERER,
      'User-Agent': userAgent(),
      'X-Requested-With': 'XMLHttpRequest',
    },
  });
  return classifySignResponse(response);
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
    delete env[LEGACY_CREDENTIAL_ENV];
    delete env.COOKIE;
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
    delete env[LEGACY_CREDENTIAL_ENV];
    delete env.COOKIE;
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
  log(`阶段 1/3：配置检查 | 签到地址：${SIGN_URL}`);
  const configStarted = Date.now();
  let configurationError = false;

  if (!accounts.length) {
    configurationError = true;
    log(
      `❌ 配置错误：缺少 ${CREDENTIAL_ENV}（或兼容变量 ${LEGACY_CREDENTIAL_ENV}）的非空 Cookie 行`
    );
  } else {
    for (const account of accounts) {
      if (!account.valid) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} Cookie 格式无效（需要 name=value 形式）`);
      }
    }
  }

  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ Cookie 行已读取'} | 耗时 ${
      Date.now() - configStarted
    }ms`
  );

  if (!configurationError) {
    for (const account of accounts) {
      const began = Date.now();
      summary.tasks.total++;
      let outcome = 'failure';
      log(`账号 ${account.index} | 阶段 2/3：每日签到`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log(
            `⏭️ DRY_RUN_OK：账号 ${account.index} Cookie 格式通过（长度 ${account.cookie.length}）；未请求网络，未验证真实业务`
          );
        } else {
          const result = await runAccount(account);
          if (result.identity) log(`账号 ${account.index} | 官方身份：${result.identity}`);
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
  classifySignResponse,
  redact,
};
