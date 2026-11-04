// name: 草榴社区每日签到
// cron: 31 8 * * *
/**
 * 草榴社区（t66y / 1024）每日签到 · 青龙独立维护版
 *
 * 上游：brandelkrefinery/t66y-automatic · src/checkin.js
 * 仓库：https://github.com/brandelkrefinery/t66y-automatic
 * 提交：0ea0b745a3a8598e3a1ede3ce59f52008fae910f
 * 授权：MIT（Copyright (c) 2026 brandelkrefinery）
 *
 * 功能盘点（主来源 checkin.js + 同仓 client/config）：
 * - 用 Cookie 校验登录 → 首页定位签到入口 → 打开签到页 → 提交表单或 GET → 解析成功/已签到
 * - 上游建议 cron：30 8 * * *；环境变量 T66Y_COOKIE / T66Y_BASE_URL / T66Y_PROXY
 * - 同仓回帖（1024 秒间隔、每日上限、发帖副作用）与长驻监控计划不同，本脚本不合并
 *
 * T66Y_COOKIE（必填）：浏览器登录论坛后，复制本站请求头 Cookie 完整值。
 * 每个非空行一个账号；可选「备注|Cookie」形式，仅在首个 | 处拆分，后续 Cookie 原文保留。
 * 不用 & 或 @ 分隔账号。Cookie 内分号、等号原样保留。
 * T66Y_BASE_URL：可选论坛根地址，默认 https://t66y.com
 * T66Y_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知，不发任何业务请求。
 * QINGLONG_NOTIFY：auto（默认，本任务在名单内）/ 强制开 / 强制关；见下方说明。
 *
 * MIT License
 * Copyright (c) 2026 brandelkrefinery
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
    const identities = ["845c9306e115e5e7", "scripts/task_845c9306.js", "task_845c9306.js", "task_845c9306"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');
const { execFile } = require('child_process');

const TITLE = '草榴社区每日签到';
const CATALOG_ID = '845c9306e115e5e7';
const DEFAULT_BASE = 'https://t66y.com';
const USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const REQUEST_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const MAX_REDIRECTS = 5;

const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = (text) => console.log(`[${stamp()}] ${text}`);
const enabled = (value) => /^(1|true|yes|on)$/i.test(String(value || ''));
const disabled = (value) => /^(0|false|no|off)$/i.test(String(value || ''));

function notificationSelected() {
  if (disabled(process.env.QINGLONG_NOTIFY)) return false;
  if (enabled(process.env.QINGLONG_NOTIFY)) return true;
  // defaultMode=listed-only + auto：未设置名单时本维护任务默认通知
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const raw = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (raw.trim() === '') return false;
  const selectors = raw.split(/[,;\s]+/).filter(Boolean);
  if (selectors.includes('*')) return true;
  const names = [
    CATALOG_ID,
    'scripts/t66y_checkin.js',
    't66y_checkin.js',
    path.basename(__filename),
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
    return names.some((name) => new RegExp(pattern).test(name));
  });
}

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line, index) => {
    let label = '';
    let cookie = line;
    const pipe = line.indexOf('|');
    if (pipe > 0) {
      label = line.slice(0, pipe).trim();
      cookie = line.slice(pipe + 1).trim();
    }
    return { index: index + 1, label, cookie };
  });
}

function cookieLooksValid(cookie) {
  if (!cookie || /[\x00-\x1f\x7f]/.test(cookie)) return false;
  // 至少一个 name=value；允许分号分隔的多段 Cookie
  return /^[^=;\s]+=\S/.test(cookie);
}

function resolveUrl(baseUrl, target) {
  if (!target) return baseUrl;
  try {
    return new URL(target, baseUrl.endsWith('/') ? baseUrl : baseUrl + '/').toString();
  } catch {
    return null;
  }
}

function httpRequest(urlString, { method = 'GET', headers = {}, body = null, cookie, timeoutMs } = {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let redirects = 0;
    const deadline = Date.now() + (timeoutMs || REQUEST_TIMEOUT_MS);

    const fail = (code) => {
      if (settled) return;
      settled = true;
      reject(new Error(code));
    };

    const go = (currentUrl, currentMethod, currentBody) => {
      let parsed;
      try {
        parsed = new URL(currentUrl);
      } catch {
        return fail('invalid-url');
      }
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return fail('invalid-url');
      const remaining = deadline - Date.now();
      if (remaining <= 0) return fail('timeout');
      const lib = parsed.protocol === 'https:' ? https : http;
      const payload = currentBody == null ? null : Buffer.from(currentBody, 'utf8');
      const reqHeaders = {
        'User-Agent': USER_AGENT,
        Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        Cookie: cookie,
        Referer: `${parsed.protocol}//${parsed.host}/`,
        ...headers,
      };
      if (payload) reqHeaders['Content-Length'] = payload.length;
      else delete reqHeaders['Content-Length'];
      if (currentMethod === 'GET') delete reqHeaders['Content-Type'];

      const req = lib.request(
        {
          protocol: parsed.protocol,
          hostname: parsed.hostname,
          port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
          path: parsed.pathname + parsed.search,
          method: currentMethod,
          headers: reqHeaders,
        },
        (res) => {
          const status = res.statusCode || 0;
          if ([301, 302, 303, 307, 308].includes(status) && res.headers.location) {
            redirects += 1;
            if (redirects > MAX_REDIRECTS) {
              res.resume();
              return fail('too-many-redirects');
            }
            const next = resolveUrl(currentUrl, res.headers.location);
            res.resume();
            if (!next) return fail('invalid-url');
            const forceGet = status === 303 || ((status === 301 || status === 302) && currentMethod !== 'GET');
            const nextMethod = forceGet ? 'GET' : currentMethod;
            const nextBody = nextMethod === 'GET' ? null : currentBody;
            return go(next, nextMethod, nextBody);
          }
          let size = 0;
          const chunks = [];
          res.on('data', (chunk) => {
            size += chunk.length;
            if (size > MAX_RESPONSE_BYTES) {
              req.destroy();
              fail('response-too-large');
            } else chunks.push(chunk);
          });
          res.on('error', () => fail('response-error'));
          res.on('aborted', () => fail('response-aborted'));
          res.on('end', () => {
            if (settled) return;
            settled = true;
            resolve({
              status,
              html: Buffer.concat(chunks).toString('utf8'),
              url: currentUrl,
            });
          });
        }
      );
      const timer = setTimeout(() => {
        req.destroy();
        fail('timeout');
      }, remaining);
      req.on('close', () => clearTimeout(timer));
      req.on('error', () => fail('network-error'));
      if (payload) req.write(payload);
      req.end();
    };

    go(urlString, method, body);
  });
}

function isLoggedIn(html) {
  const head = html.slice(0, 2000);
  return /logout|退出|短消息|我的主题/i.test(html) && !/action=login|游客/.test(head);
}

function extractIdentity(html, cookie) {
  const secrets = cookie
    .split(';')
    .map((part) => {
      const i = part.indexOf('=');
      return i >= 0 ? part.slice(i + 1).trim() : '';
    })
    .filter((v) => v.length >= 4);

  const patterns = [
    /欢迎您[，,:：\s]*<[^>]+>([^<]{1,40})</i,
    /欢迎[^<]{0,10}<a[^>]*>([^<]{1,40})</i,
    /用户名[：:\s]*([^\s<>'"]{2,40})/i,
    /昵称[：:\s]*([^\s<>'"]{2,40})/i,
    /uid[=:](\d{1,12})/i,
  ];
  for (const re of patterns) {
    const m = html.match(re);
    if (!m) continue;
    const text = String(m[1] || '').trim();
    if (!text || text.length > 100 || /[\r\n\x00-\x1f\x7f]/.test(text)) continue;
    if (/(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text)) continue;
    if (/cookie|token|session|authorization/i.test(text)) continue;
    if (secrets.some((secret) => text.includes(secret))) continue;
    return text;
  }
  return null;
}

function findSignUrl(html, baseUrl) {
  const re = /<a\b[^>]*href\s*=\s*["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
  let match;
  while ((match = re.exec(html))) {
    const href = match[1] || '';
    const text = String(match[2] || '').replace(/<[^>]+>/g, '').trim();
    if (/sign|qiandao|打卡|签到/i.test(href) || /每日签到|签到/.test(text)) {
      return resolveUrl(baseUrl, href);
    }
  }
  return null;
}

function extractForm(html, pageUrl) {
  const formMatch = html.match(/<form\b[^>]*action\s*=\s*["']([^"']+)["'][^>]*>([\s\S]*?)<\/form>/i);
  if (!formMatch) return null;
  const action = resolveUrl(pageUrl, formMatch[1]);
  if (!action) return null;
  const fields = {};
  const body = formMatch[2];
  const inputRe = /<input\b([^>]*)>/gi;
  let input;
  while ((input = inputRe.exec(body))) {
    const attrs = input[1] || '';
    const nameMatch = attrs.match(/\bname\s*=\s*["']([^"']+)["']/i);
    if (!nameMatch) continue;
    const typeMatch = attrs.match(/\btype\s*=\s*["']([^"']+)["']/i);
    const type = (typeMatch && typeMatch[1] || 'text').toLowerCase();
    if (type === 'file') continue;
    const valueMatch = attrs.match(/\bvalue\s*=\s*["']([^"']*)["']/i);
    fields[nameMatch[1]] = valueMatch ? valueMatch[1] : '';
  }
  return { action, fields };
}

function parseResult(html) {
  if (/签到成功|打卡成功|恭喜/.test(html)) {
    const money = html.match(/(\d+)\s*(金钱|金币|贡献)/);
    return {
      ok: true,
      state: 'success',
      message: money ? `签到成功,获得 ${money[1]} ${money[2]}` : '签到成功',
    };
  }
  if (/已签到|已经签到|今日已签/.test(html)) {
    return { ok: true, state: 'alreadyComplete', message: '今日已签到' };
  }
  return { ok: false, state: 'failure', message: '签到结果未知,请人工确认' };
}

async function checkinAccount(account, baseUrl) {
  const indexHtml = (await httpRequest(resolveUrl(baseUrl, 'index.php'), { cookie: account.cookie })).html;
  if (!isLoggedIn(indexHtml)) {
    return { ok: false, state: 'failure', message: 'Cookie 已失效或未登录,请重新获取 Cookie', identity: null };
  }
  const identity = extractIdentity(indexHtml, account.cookie);

  const signUrl = findSignUrl(indexHtml, baseUrl);
  if (!signUrl) {
    return {
      ok: false,
      state: 'failure',
      message: '未找到签到入口,论坛可能改版或今日已签到',
      identity,
    };
  }

  const signPage = await httpRequest(signUrl, { cookie: account.cookie });
  if (/已签到|已经签到|今日已签/.test(signPage.html)) {
    return { ok: true, state: 'alreadyComplete', message: '今日已签到,无需重复操作', identity };
  }

  const form = extractForm(signPage.html, signPage.url || signUrl);
  if (form) {
    const body = new URLSearchParams(form.fields).toString();
    const result = await httpRequest(form.action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
      cookie: account.cookie,
    });
    const parsed = parseResult(result.html);
    return { ...parsed, identity };
  }

  const parsed = parseResult(signPage.html);
  return { ...parsed, identity };
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
    delete env.T66Y_COOKIE;
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
    delete env.T66Y_COOKIE;
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
  const dryRun = enabled(process.env.T66Y_DRY_RUN);
  const baseUrl = String(process.env.T66Y_BASE_URL || DEFAULT_BASE).replace(/\/+$/, '') || DEFAULT_BASE;
  const accounts = parseAccounts(process.env.T66Y_COOKIE);
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

  log(`========== ${TITLE} ==========`);
  log(
    `开始时间：${new Date(started).toISOString()} | 模式：${dryRun ? '断网预演' : '正式执行'} | 账号数：${accounts.length}`
  );
  log(`阶段 1/3：配置检查 | 基地：${baseUrl}`);
  const configStarted = Date.now();
  let configurationError = false;

  if (!accounts.length) {
    configurationError = true;
    log('❌ 配置错误：缺少 T66Y_COOKIE 的非空账号行');
  } else {
    for (const account of accounts) {
      if (!cookieLooksValid(account.cookie)) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} 的 Cookie 格式无效`);
      }
    }
  }
  if (process.env.T66Y_PROXY && String(process.env.T66Y_PROXY).trim()) {
    log('⚠️ 已忽略 T66Y_PROXY：本独立维护版使用 Node 标准库直连，不加载代理组件');
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`
  );

  if (!configurationError) {
    for (const account of accounts) {
      const began = Date.now();
      summary.tasks.total++;
      let outcome = 'failure';
      const who = account.label ? `（${account.label}）` : '';
      log(`账号 ${account.index}${who} | 阶段 2/3：登录校验与签到`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log('⏭️ DRY_RUN_OK：Cookie 格式通过；未请求网络，未验证真实业务');
        } else {
          const result = await checkinAccount(account, baseUrl);
          if (result.identity) log(`账号 ${account.index} | 官方身份：${result.identity}`);
          if (result.ok && result.state === 'success') {
            outcome = 'success';
            log(`✅ ${result.message}`);
          } else if (result.ok && result.state === 'alreadyComplete') {
            outcome = 'alreadyComplete';
            log(`☑️ ${result.message}`);
          } else {
            outcome = 'failure';
            log(`❌ ${result.message}`);
          }
        }
      } catch (err) {
        const reasons = {
          timeout: '请求超时',
          'response-too-large': '响应过大',
          'network-error': '网络请求失败',
          'response-error': '响应读取失败',
          'response-aborted': '响应中断',
          'too-many-redirects': '重定向过多',
          'invalid-url': '地址无效',
        };
        log(`❌ ${reasons[err.message] || '请求失败'}；未确认签到成功`);
        outcome = 'failure';
      }
      summary.tasks[outcome]++;
      if (outcome === 'failure') summary.failedAccounts++;
      else summary.successfulAccounts++;
      log(
        `账号 ${account.index} 统计：总任务 1 | 成功 ${+(outcome === 'success')} | 已完成 ${+(outcome === 'alreadyComplete')} | 跳过 ${+(outcome === 'skipped')} | 失败 ${+(outcome === 'failure')} | 耗时 ${Date.now() - began}ms`
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
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
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

module.exports = { parseAccounts, cookieLooksValid, parseResult, isLoggedIn, findSignUrl };
