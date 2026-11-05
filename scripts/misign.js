#!/usr/bin/env node
// name: Discuz k_misign 每日签到
// cron: 19 8 * * *
/**
 * Discuz k_misign 签到插件 · 青龙独立维护版
 *
 * 上游：lwhx/daily-checkin-panel · src/sites/misign.js
 * 仓库：https://github.com/lwhx/daily-checkin-panel.git
 * 分支：master · 提交：1ff7daeefbdfa2d444ab5bad989e4ad0ad4d9db5
 * 授权：MIT
 *
 * 功能盘点（主来源 misign.js）：
 * - 打开 {base}/plugin.php?id=k_misign:sign；页面含「您的签到排名」视为今日已签到
 * - 否则提取 <a id="JD_sign"> 或含 k_misign 的签到链接并 GET 执行
 * - 再次打开签到页确认排名；可选读取 lxreward 奖励文案
 * - 凭据：论坛首页地址 + 浏览器登录后 Cookie；可选 User-Agent
 * - 同仓相关源（akile / http / hutue / index）属不同站点或注册表，不合并进本任务
 *
 * MISIGN_ACCOUNT（必填）：每行「论坛根地址|完整 Cookie」，仅在首个 | 处拆分，
 * 后续 Cookie 原文保留。不用 & 或 @ 分隔账号。
 * 获取：浏览器登录目标论坛 → F12 网络面板 → 复制本站请求头 Cookie。
 * 先确认签到页形如 plugin.php?id=k_misign:sign。
 * MISIGN_USER_AGENT（可选）：全局 UA；留空用默认浏览器 UA。
 * MISIGN_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知。
 * QINGLONG_NOTIFY：auto（默认，本任务在名单内）/ 强制开 / 强制关。
 *
 * MIT License
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
    const identities = ["a4947a6ba0940e49", "scripts/misign.js", "misign.js", "misign"];
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

const TITLE = 'Discuz k_misign 每日签到';
const CATALOG_ID = 'a4947a6ba0940e49';
const DEFAULT_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
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
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const raw = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (raw.trim() === '') return false;
  const selectors = raw.split(/[,;\s]+/).filter(Boolean);
  if (selectors.includes('*')) return true;
  const names = [
    CATALOG_ID,
    'scripts/misign.js',
    'misign.js',
    'candidate.js',
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

function unesc(s) {
  return String(s || '')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
}

function normBase(raw) {
  let b = String(raw || '').trim().replace(/\/+$/, '');
  if (!b) throw new Error('missing-base');
  if (!/^https?:\/\//i.test(b)) b = 'https://' + b;
  try {
    const u = new URL(b);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error('invalid-base');
    return u.origin + u.pathname.replace(/\/+$/, '');
  } catch {
    throw new Error('invalid-base');
  }
}

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line, index) => {
    const pipe = line.indexOf('|');
    if (pipe <= 0 || pipe === line.length - 1) {
      return { index: index + 1, configurationError: 'format', base: '', cookie: '' };
    }
    const baseRaw = line.slice(0, pipe).trim();
    const cookie = line.slice(pipe + 1).trim();
    let base = '';
    try {
      base = normBase(baseRaw);
    } catch {
      return { index: index + 1, configurationError: 'base', base: '', cookie };
    }
    return { index: index + 1, base, cookie, configurationError: null };
  });
}

function cookieLooksValid(cookie) {
  if (!cookie || /[\x00-\x1f\x7f]/.test(cookie)) return false;
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

function httpRequest(urlString, { method = 'GET', headers = {}, cookie, ua, timeoutMs } = {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let redirects = 0;
    const deadline = Date.now() + (timeoutMs || REQUEST_TIMEOUT_MS);

    const fail = (code) => {
      if (settled) return;
      settled = true;
      reject(new Error(code));
    };

    const go = (currentUrl, currentMethod) => {
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
      const reqHeaders = {
        'User-Agent': ua || DEFAULT_UA,
        Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        Cookie: cookie,
        Referer: `${parsed.protocol}//${parsed.host}/`,
        ...headers,
      };

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
            return go(next, 'GET');
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
      req.end();
    };

    go(urlString, method);
  });
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
    /<strong\b[^>]*class=["'][^"']*\bvwmy\b[^"']*["'][^>]*>\s*<a\b[^>]*>([^<>]+)<\/a>/i,
    /title=["']访问我的空间["'][^>]*>([^<]{1,40})<\/a>/i,
    /欢迎您[，,:：\s]*<[^>]+>([^<]{1,40})</i,
  ];
  for (const re of patterns) {
    const m = html.match(re);
    if (!m) continue;
    const text = unesc(String(m[1] || '').trim());
    if (!text || text.length > 100 || /[\r\n\x00-\x1f\x7f]/.test(text)) continue;
    if (/(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text)) continue;
    if (/cookie|token|session|authorization/i.test(text)) continue;
    if (secrets.some((secret) => text.includes(secret))) continue;
    return text;
  }
  return null;
}

function looksLikeLoginPage(html) {
  return /mod=logging/i.test(html) && /action=login/i.test(html);
}

function alreadySigned(html) {
  return /您的签到排名/.test(html);
}

function extractSignHref(html) {
  const m =
    html.match(/<a[^>]*id=["']JD_sign["'][^>]*href=["']([^"']+)["']/i) ||
    html.match(/href=["']([^"']*k_misign[^"']*)["']/i);
  return m ? unesc(m[1]) : '';
}

function extractReward(html) {
  const rw = html.match(/id=["']lxreward["'][^>]*value=["']([^"']*)["']/i);
  return rw ? unesc(rw[1]).trim() : '';
}

async function checkinAccount(account, ua) {
  const signUrl = account.base + '/plugin.php?id=k_misign:sign';
  const get = (url) => httpRequest(url, { cookie: account.cookie, ua });

  let page = await get(signUrl);
  const identity = extractIdentity(page.html, account.cookie);

  if (alreadySigned(page.html)) {
    const reward = extractReward(page.html);
    return {
      ok: true,
      state: 'alreadyComplete',
      message: reward ? `今日已签到，无需重复（奖励栏：${reward}）` : '今日已签到，无需重复',
      identity,
    };
  }
  if (looksLikeLoginPage(page.html)) {
    return {
      ok: false,
      state: 'failure',
      message: 'Cookie 已失效，请重新登录后复制新的 Cookie',
      identity,
    };
  }

  const href = extractSignHref(page.html);
  if (!href) {
    return {
      ok: false,
      state: 'failure',
      message: '未找到签到按钮，该论坛可能不是 k_misign 插件或页面已改版',
      identity,
    };
  }
  if (/mod=logging/i.test(href)) {
    return {
      ok: false,
      state: 'failure',
      message: 'Cookie 已失效，请重新登录后复制新的 Cookie',
      identity,
    };
  }

  const signLink = /^https?:\/\//i.test(href)
    ? href
    : resolveUrl(account.base + '/', href.replace(/^\/+/, ''));
  if (!signLink) {
    return { ok: false, state: 'failure', message: '签到链接无效', identity };
  }

  await get(signLink);
  page = await get(signUrl);
  if (alreadySigned(page.html)) {
    const reward = extractReward(page.html);
    return {
      ok: true,
      state: 'success',
      message: reward ? `签到成功：${reward}` : '签到成功',
      identity: extractIdentity(page.html, account.cookie) || identity,
    };
  }
  return {
    ok: false,
    state: 'failure',
    message: '签到失败：确认页未显示签到排名',
    identity,
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
    delete env.MISIGN_ACCOUNT;
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
    delete env.MISIGN_ACCOUNT;
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
  const dryRun = enabled(process.env.MISIGN_DRY_RUN);
  const ua = String(process.env.MISIGN_USER_AGENT || '').trim() || DEFAULT_UA;
  const accounts = parseAccounts(process.env.MISIGN_ACCOUNT);
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
  log('阶段 1/3：配置检查');
  const configStarted = Date.now();
  let configurationError = false;

  if (!accounts.length) {
    configurationError = true;
    log('❌ 配置错误：缺少 MISIGN_ACCOUNT 的非空账号行');
  } else {
    for (const account of accounts) {
      if (account.configurationError === 'format') {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} 应为「论坛地址|Cookie」，且仅在首个 | 处拆分`);
      } else if (account.configurationError === 'base') {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} 的论坛地址无效`);
      } else if (!cookieLooksValid(account.cookie)) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} 的 Cookie 格式无效`);
      } else {
        log(`账号 ${account.index}：论坛 ${account.base} · Cookie 字段已读入`);
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`
  );

  if (!configurationError) {
    for (const account of accounts) {
      const began = Date.now();
      summary.tasks.total++;
      let outcome = 'failure';
      log(`账号 ${account.index} | 阶段 2/3：打开签到页并执行 k_misign 签到`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log('⏭️ DRY_RUN_OK：论坛地址与 Cookie 格式通过；未请求网络，未验证真实业务');
        } else {
          const result = await checkinAccount(account, ua);
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

module.exports = {
  parseAccounts,
  cookieLooksValid,
  alreadySigned,
  extractSignHref,
  extractReward,
  looksLikeLoginPage,
  normBase,
};
