// name: 薄荷公益站每日签到
// cron: 4 8 * * *
/**
 * 薄荷公益站（up.x666.me）每日签到 · 青龙独立维护版
 *
 * 上游：484198xx/bohe-auto-signin · background.js（主）+ popup.js（同产品 UI 参考）
 * 仓库：https://github.com/484198xx/bohe-auto-signin.git
 * 分支：main
 * 提交：14ebac3bdc338d6cf261477324df8fa556f1798f
 * 授权：MIT（Copyright (c) 2026 484198xx）
 *
 * 功能盘点（主来源 background.js + related popup.js）：
 * - 使用站点 Cookie（server_session_58ffd1cb，可选 auth_token）访问公益站 API
 * - GET /api/user/info 校验登录并展示 username / linux_do_id
 * - GET /api/checkin/status 判断 can_spin / today_record / 当前额度
 * - POST /api/checkin/spin 执行每日抽奖签到；识别今日已签与未登录
 * - GET /api/checkin/history 汇总连续签到天数与累计额度（只读展示）
 * - Chrome 扩展闹钟/标签页注入/本地存储/图表 UI 改为青龙环境变量 Cookie + 时间轴日志
 * - 无发帖/评论等公开内容副作用
 *
 * BOHE_COOKIE（必填）：登录 https://up.x666.me 后，从浏览器开发者工具→应用/网络复制
 * 本站 Cookie（至少包含 server_session_58ffd1cb=...；可附带 auth_token=...）。
 * 每个非空行一个账号；可选「备注|Cookie」，仅在首个 | 处拆分。不使用 & 或 @ 分隔账号。
 * BOHE_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）。
 * BOHE_TIMEOUT_MS：请求超时毫秒，默认 20000（1000–60000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 * Copyright (c) 2026 484198xx
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
    const identities = ["5d8ba0f271781047", "scripts/background.js", "background.js", "background"];
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

const TITLE = '薄荷公益站每日签到';
const CATALOG_ID = '5d8ba0f271781047';
const CREDENTIAL_ENV = 'BOHE_COOKIE';
const DRY_RUN_ENV = 'BOHE_DRY_RUN';
const DEFAULT_BASE = 'https://up.x666.me';
const SESSION_COOKIE = 'server_session_58ffd1cb';
const UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const DEFAULT_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const QUOTA_DIV = 500;
const PRIZE_LABEL = {
  1: '一等奖',
  2: '二等奖',
  3: '三等奖',
  4: '四等奖',
  5: '五等奖',
  6: '六等奖',
  7: '七等奖',
  8: '八等奖',
};

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
  text = text.replace(/(server_session_58ffd1cb|auth_token)=([^;\s]+)/gi, '$1=[已隐藏]');
  text = text.replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.BOHE_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000 ? value : DEFAULT_TIMEOUT_MS;
}

function fmtTimes(quotaAmount) {
  const n = Number(quotaAmount);
  if (!Number.isFinite(n) || n <= 0) return '0次';
  return Math.floor(n / QUOTA_DIV) + '次';
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
    'scripts/bohe_checkin.js',
    'bohe_checkin.js',
    'bohe',
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

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line, index) => {
    remember(line);
    let label = '';
    let cookie = line;
    const pipe = line.indexOf('|');
    if (pipe > 0) {
      label = line.slice(0, pipe).trim();
      cookie = line.slice(pipe + 1).trim();
    }
    remember(cookie);
    const sessionMatch = cookie.match(
      new RegExp('(?:^|;\\s*)' + SESSION_COOKIE + '=([^;\\s]+)', 'i')
    );
    if (sessionMatch && sessionMatch[1]) remember(sessionMatch[1]);
    const authMatch = cookie.match(/(?:^|;\s*)auth_token=([^;\s]+)/i);
    if (authMatch && authMatch[1]) remember(authMatch[1]);
    return { index: index + 1, label, cookie };
  });
}

function cookieLooksValid(cookie) {
  if (!cookie || /[\x00-\x1f\x7f]/.test(cookie)) return false;
  if (!new RegExp('(?:^|;\\s*)' + SESSION_COOKIE + '=[^;\\s]+', 'i').test(cookie)) return false;
  return /^[^=;\s]+=\S/.test(cookie);
}

function calcStreakDays(records) {
  if (!records || records.length === 0) return 0;
  const dateSet = new Set();
  for (const r of records) {
    const d = String(r.spin_date || '').substring(0, 10);
    if (/^\d{4}-\d{2}-\d{2}$/.test(d)) dateSet.add(d);
  }
  if (dateSet.size === 0) return 0;

  const now = new Date();
  const todayStr =
    now.getFullYear() +
    '-' +
    String(now.getMonth() + 1).padStart(2, '0') +
    '-' +
    String(now.getDate()).padStart(2, '0');
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr =
    yesterday.getFullYear() +
    '-' +
    String(yesterday.getMonth() + 1).padStart(2, '0') +
    '-' +
    String(yesterday.getDate()).padStart(2, '0');

  const dates = Array.from(dateSet).sort().reverse();
  const latest = dates[0];
  if (latest !== todayStr && latest !== yesterdayStr) return 0;

  let streak = 0;
  let [curY, curM, curD] = latest.split('-').map(Number);
  while (true) {
    const dStr =
      curY + '-' + String(curM).padStart(2, '0') + '-' + String(curD).padStart(2, '0');
    if (dateSet.has(dStr)) {
      streak++;
      curD--;
      if (curD <= 0) {
        curM--;
        if (curM <= 0) {
          curM = 12;
          curY--;
        }
        curD = new Date(curY, curM, 0).getDate();
      }
    } else {
      break;
    }
  }
  return streak;
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

function apiHeaders(cookie, extra = {}) {
  return {
    'User-Agent': UA,
    Accept: 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Content-Type': 'application/json',
    Origin: DEFAULT_BASE,
    Referer: DEFAULT_BASE + '/',
    Cookie: cookie,
    ...extra,
  };
}

async function apiJson(cookie, apiPath, method = 'GET', bodyObj = null) {
  const url = DEFAULT_BASE + apiPath;
  const body = bodyObj == null ? null : JSON.stringify(bodyObj);
  const response = await httpRequest(url, {
    method,
    headers: apiHeaders(cookie),
    body,
  });
  let data = null;
  try {
    data = JSON.parse(response.text);
  } catch {
    data = null;
  }
  return { status: response.statusCode, data, ok: response.statusCode >= 200 && response.statusCode < 300 };
}

function pickIdentity(infoData, statusData) {
  const bags = [infoData, statusData].filter((v) => v && typeof v === 'object');
  for (const bag of bags) {
    if (typeof bag.username === 'string' && bag.username.trim()) return bag.username.trim();
  }
  for (const bag of bags) {
    if (bag.linux_do_id !== undefined && bag.linux_do_id !== null && String(bag.linux_do_id)) {
      return 'ID:' + String(bag.linux_do_id);
    }
  }
  return '';
}

function historyRecords(historyData) {
  if (!historyData || typeof historyData !== 'object') return [];
  if (Array.isArray(historyData.data)) return historyData.data;
  if (Array.isArray(historyData.records)) return historyData.records;
  return [];
}

async function runAccount(account) {
  const info = await apiJson(account.cookie, '/api/user/info');
  if (info.status === 401 || (info.data && info.data.success === false)) {
    return { ok: false, state: 'failure', message: '未登录或 Cookie 已过期', identity: '' };
  }
  if (!info.data || !info.data.success) {
    return {
      ok: false,
      state: 'failure',
      message: '无法获取用户信息（接口未返回 success）',
      identity: '',
    };
  }

  const status = await apiJson(account.cookie, '/api/checkin/status');
  if (!status.data || !status.data.success) {
    return {
      ok: false,
      state: 'failure',
      message: '无法获取签到状态，请稍后重试',
      identity: pickIdentity(info.data, status.data),
    };
  }

  const identity = pickIdentity(info.data, status.data);
  const canSpin = status.data.can_spin ?? false;
  const hasRecord = !!status.data.today_record;
  const balanceTimes = fmtTimes(status.data.current_quota || 0);

  let streakDays = Number(status.data.streak_days) || 0;
  let totalTimes = '0';
  try {
    const history = await apiJson(account.cookie, '/api/checkin/history');
    if (history.data && history.data.success) {
      const records = historyRecords(history.data);
      let totalQuota = 0;
      for (const r of records) totalQuota += Number(r.quota_amount) || 0;
      totalTimes = String(Math.floor(totalQuota / QUOTA_DIV));
      const computed = calcStreakDays(records);
      if (computed > 0) streakDays = computed;
    }
  } catch {
    /* 历史只读失败不阻断签到 */
  }

  if (!canSpin || hasRecord) {
    const today = status.data.today_record;
    let detail = `今日已签到；余额 ${balanceTimes}`;
    if (today && typeof today === 'object') {
      const label =
        PRIZE_LABEL[today.prize_level] ||
        (today.prize_level != null ? '等级' + today.prize_level : '');
      if (label) detail += `；今日 ${label} +${fmtTimes(today.quota_amount || 0)}`;
    }
    if (streakDays) detail += `；连续 ${streakDays} 天`;
    if (totalTimes && totalTimes !== '0') detail += `；累计 ${totalTimes} 次额度`;
    return { ok: true, state: 'alreadyComplete', message: detail, identity };
  }

  const spin = await apiJson(account.cookie, '/api/checkin/spin', 'POST', {});
  if (spin.status === 401) {
    return { ok: false, state: 'failure', message: '未登录或 Cookie 已过期', identity };
  }
  if (spin.data && spin.data.success) {
    const d = spin.data;
    const label = d.label || '未知';
    const quota = fmtTimes(d.quota || 0);
    const balance = fmtTimes(d.new_balance || 0);
    const rank = d.today_rank || '-';
    const streak = d.streak_days != null ? d.streak_days : streakDays;
    return {
      ok: true,
      state: 'success',
      message: `签到成功：${label}；获得额度 ${quota}；余额 ${balance}；今日排名 ${rank}；连续 ${streak} 天`,
      identity,
    };
  }

  const msg = String((spin.data && spin.data.message) || '');
  if (/已签到|checked|already/i.test(msg)) {
    return {
      ok: true,
      state: 'alreadyComplete',
      message: '今日已签到',
      identity,
    };
  }
  if (/登录|login|unauthorized/i.test(msg) || spin.status === 401) {
    return { ok: false, state: 'failure', message: '未登录或 Cookie 已过期', identity };
  }
  return {
    ok: false,
    state: 'failure',
    message: redact(msg || '签到失败（接口未确认成功）'),
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
    delete env.BOHE_COOKIE;
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
    delete env.BOHE_COOKIE;
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
  const accounts = parseAccounts(process.env[CREDENTIAL_ENV]);
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
  log(`阶段 1/3：配置检查 | 站点：${DEFAULT_BASE}`);
  const configStarted = Date.now();
  let configurationError = false;

  if (!accounts.length) {
    configurationError = true;
    log(`❌ 配置错误：缺少 ${CREDENTIAL_ENV} 的非空账号行`);
  } else {
    for (const account of accounts) {
      if (!cookieLooksValid(account.cookie)) {
        configurationError = true;
        log(
          `❌ 配置错误：账号 ${account.index} 的 Cookie 无效（需含 ${SESSION_COOKIE}=...）`
        );
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${
      Date.now() - configStarted
    }ms`
  );

  if (!configurationError) {
    for (const account of accounts) {
      const began = Date.now();
      summary.tasks.total++;
      let outcome = 'failure';
      const who = account.label ? `（${redact(account.label)}）` : '';
      log(`账号 ${account.index}${who} | 阶段 2/3：查询状态并签到`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log('⏭️ DRY_RUN_OK：Cookie 格式通过；未请求网络，未验证真实业务');
        } else {
          const result = await runAccount(account);
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
          'invalid-url': '地址无效',
        };
        log(`❌ ${reasons[err.message] || '请求失败'}；未确认签到成功`);
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
  calcStreakDays,
  fmtTimes,
  pickIdentity,
};
