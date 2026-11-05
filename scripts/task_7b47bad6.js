#!/usr/bin/env node
// name: MiniMax Code每日签到
// cron: 27 9 * * *
/**
 * MiniMax Code（mcode）每日签到 · 青龙独立维护版
 *
 * 上游：jk-uzi/minimax-proxy · src/signin.ts（签到客户端库）
 * 仓库：https://github.com/jk-uzi/minimax-proxy
 * 分支：main
 * 提交：7be1e3c5f585c2ad962813fd2cde2961cd2aef26
 * 授权：MIT
 *
 * 功能盘点（主来源 signin.ts；auth.ts / serve.ts 仅为代理库与长驻入口，不作为青龙任务依赖）：
 * - GET  /minimax-cloud/api/v1/signin/status?timezone_id=<IANA> 查询 7 日签到面板
 * - POST /minimax-cloud/api/v1/signin/claim?timezone_id=<IANA> 领取今日积分（空 body）
 * - 面板日状态：1 未开始 / 2 可领 / 3 已领 / 4 不可领；claim_result：1 本次领取 / 2 今天已领
 * - 区域：国内版 cn → https://agent.minimax.cn ；国际版 en → https://agent.minimax.io
 * - 上游设计红线：只使用 accessToken，绝不调用 refresh、不读写桌面端 auth 文件
 * - maintainedFeatureCoverage 为空；无已发布同产品完整重复覆盖
 * - 相关网页版签到（Cookie/完整 URL 签名）凭据边界不同，保持独立，不合并
 *
 * MINIMAX_CODE_TOKEN（必填）：每个非空行一个账号 accessToken。
 * 推荐「region|accessToken」，只在首个 | 处拆分，后续 token 原文保留；region 为 cn 或 en。
 * 也可整行 JSON：{"region":"cn","accessToken":"...","timezone":"Asia/Shanghai","label":"备注"}。
 * 仅 token 时默认 region=cn（可用 MINIMAX_CODE_REGION 覆盖默认）。
 * 获取方式：在已登录的 MiniMax Code 桌面端本地 auth.json 中复制 records 内 oauth 记录的 accessToken
 * （常见路径 ~/.minimax/auth/prod/cn|en/mcode-public/auth.json）。勿把 refreshToken 填入本变量，
 * 也勿在脚本中刷新令牌（会踢掉桌面端登录态）。accessToken 通常约 1 小时有效，过期后请重新复制。
 * 兼容别名：MINIMAX_MCODE_TOKEN、MINIMAX_ACCESS_TOKEN（仅规范变量为空时读取）。
 * MINIMAX_CODE_REGION：无行内 region 时的默认区域，cn 或 en，默认 cn。
 * MINIMAX_CODE_TIMEZONE：IANA 时区，默认本机时区，失败时 Asia/Shanghai。
 * MINIMAX_CODE_DRY_RUN=1：完全断网预演，只校验参数并模拟阶段与通知摘要。
 * MINIMAX_CODE_TIMEOUT_MS：单次 HTTP 超时毫秒，默认 20000（1000–120000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * MIT License
 *
 * Copyright (c) 2026 LaoDing (dingminhua/dsh-connect-trae)
 * Copyright (c) 2026 weixiaokuan123 (trae-proxy standalone adaptation)
 * Copyright (c) jk-uzi / minimax-proxy contributors
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
      '7b47bad620ba7931',
      'scripts/minimax_code_signin.js',
      'minimax_code_signin.js',
      'signin.ts',
      'signin',
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

const TITLE = 'MiniMax Code每日签到';
const CATALOG_ID = '7b47bad620ba7931';
const CREDENTIAL_ENV = 'MINIMAX_CODE_TOKEN';
const CREDENTIAL_ALIASES = ['MINIMAX_MCODE_TOKEN', 'MINIMAX_ACCESS_TOKEN'];
const DRY_RUN_ENV = 'MINIMAX_CODE_DRY_RUN';
const DEFAULT_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 512 * 1024;
const ACCOUNT_GAP_MS = 1200;

const SIGNIN_DAY_UPCOMING = 1;
const SIGNIN_DAY_CLAIMABLE = 2;
const SIGNIN_DAY_CLAIMED = 3;
const SIGNIN_DAY_DISABLED = 4;
const CLAIM_RESULT_CLAIMED = 1;
const CLAIM_RESULT_ALREADY = 2;

const REGIONS = {
  cn: {
    region: 'cn',
    origin: 'https://agent.minimax.cn',
    label: '国内版',
  },
  en: {
    region: 'en',
    origin: 'https://agent.minimax.io',
    label: '国际版',
  },
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
  text = text.replace(/Bearer\s+[A-Za-z0-9._\-+=\/]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.MINIMAX_CODE_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 120000 ? value : DEFAULT_TIMEOUT_MS;
}

function localTimezone() {
  const fromEnv = String(process.env.MINIMAX_CODE_TIMEZONE || '').trim();
  if (fromEnv) return fromEnv;
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai';
  } catch {
    return 'Asia/Shanghai';
  }
}

function defaultRegion() {
  const raw = String(process.env.MINIMAX_CODE_REGION || 'cn').trim().toLowerCase();
  return raw === 'en' ? 'en' : 'cn';
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
    'scripts/minimax_code_signin.js',
    'minimax_code_signin.js',
    'signin.ts',
    'signin',
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

function decodeJwtPayload(token) {
  const parts = String(token || '').split('.');
  if (parts.length < 2) return null;
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    return JSON.parse(Buffer.from(padded, 'base64').toString('utf8'));
  } catch {
    return null;
  }
}

function identityFromToken(token) {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload !== 'object') return null;
  const candidates = [
    payload.nickname,
    payload.name,
    payload.preferred_username,
    payload.username,
    payload.user_name,
    payload.subUserName,
    payload.display_name,
    payload.uid,
    payload.user_id,
    payload.userId,
    payload.sub,
  ];
  for (const item of candidates) {
    if (typeof item === 'string' && item.trim()) return item.trim();
    if (typeof item === 'number' && Number.isFinite(item)) return String(item);
  }
  return null;
}

function parseAccountLine(line, index) {
  const trimmed = String(line || '').trim();
  if (!trimmed || trimmed.startsWith('#')) {
    return {
      index,
      region: defaultRegion(),
      accessToken: '',
      timezone: localTimezone(),
      label: '',
      valid: false,
      reason: '空行',
    };
  }

  remember(trimmed);
  let region = defaultRegion();
  let accessToken = '';
  let timezone = localTimezone();
  let label = '';

  if (trimmed.startsWith('{')) {
    try {
      const obj = JSON.parse(trimmed);
      const regionRaw = String(obj.region || obj.Region || defaultRegion())
        .trim()
        .toLowerCase();
      region = regionRaw === 'en' ? 'en' : 'cn';
      accessToken = String(
        obj.accessToken || obj.access_token || obj.token || obj.Token || ''
      ).trim();
      if (typeof obj.timezone === 'string' && obj.timezone.trim()) timezone = obj.timezone.trim();
      if (typeof obj.label === 'string' && obj.label.trim()) label = obj.label.trim();
      else if (typeof obj.name === 'string' && obj.name.trim()) label = obj.name.trim();
    } catch {
      return {
        index,
        region,
        accessToken: '',
        timezone,
        label,
        valid: false,
        reason: 'JSON 解析失败',
      };
    }
  } else {
    const pipe = trimmed.indexOf('|');
    if (pipe > 0) {
      const head = trimmed.slice(0, pipe).trim().toLowerCase();
      const rest = trimmed.slice(pipe + 1).trim();
      if (head === 'cn' || head === 'en') {
        region = head;
        accessToken = rest;
      } else {
        // 非区域前缀：整行视为 token（兼容误用 | 的情况）
        accessToken = trimmed;
      }
    } else {
      accessToken = trimmed;
    }
  }

  remember(accessToken);
  const placeholder = /请替换|your[_-]?token|changeme|xxxxxxxx|placeholder/i;
  const valid =
    Boolean(accessToken) &&
    accessToken.length >= 20 &&
    !placeholder.test(accessToken) &&
    Boolean(REGIONS[region]);

  return {
    index,
    region,
    accessToken,
    timezone,
    label,
    valid,
    reason: valid
      ? ''
      : !accessToken
        ? '缺少 accessToken'
        : accessToken.length < 20 || placeholder.test(accessToken)
          ? 'accessToken 过短或为示例占位'
          : 'region 无效（仅支持 cn / en）',
  };
}

function parseAccounts(raw) {
  return String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))
    .map((line, i) => parseAccountLine(line, i + 1));
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
    if (payload) reqHeaders['Content-Length'] = String(payload.length);
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
        res.on('end', () => {
          if (settled) return;
          settled = true;
          resolve({
            statusCode: res.statusCode || 0,
            text: Buffer.concat(parts).toString('utf8'),
          });
        });
        res.on('error', () => fail('response-error'));
        res.on('aborted', () => fail('response-aborted'));
      }
    );
    req.on('timeout', () => {
      req.destroy();
      fail('timeout');
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

function authHeaders(accessToken) {
  return {
    Authorization: `Bearer ${accessToken}`,
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': 'qinglong-minimax-code-signin/1.0',
  };
}

function parsePanel(value) {
  const panel = value;
  if (!panel || typeof panel !== 'object' || !Array.isArray(panel.days)) {
    throw new Error('panel-missing');
  }
  const days = panel.days.map((raw) => {
    const d = raw && typeof raw === 'object' ? raw : {};
    return {
      dayNo: Number(d.day_no),
      points: Number(d.points ?? 0),
      status: Number(d.status),
      isToday: d.is_today === true,
    };
  });
  return { scene: Number(panel.scene ?? 0), days };
}

function getStreak(panel) {
  const sorted = [...panel.days].sort((a, b) => a.dayNo - b.dayNo);
  const todayIndex = sorted.findIndex((d) => d.isToday);
  if (todayIndex < 0) return 0;
  const todayStatus = sorted[todayIndex] && sorted[todayIndex].status;
  let index =
    todayStatus === SIGNIN_DAY_CLAIMED
      ? todayIndex
      : todayStatus === SIGNIN_DAY_CLAIMABLE
        ? todayIndex - 1
        : -1;
  if (index < 0) return 0;
  let streak = 0;
  for (; index >= 0; index -= 1) {
    if (!sorted[index] || sorted[index].status !== SIGNIN_DAY_CLAIMED) break;
    streak += 1;
  }
  return streak;
}

function summarize(panel) {
  const today = panel.days.find((d) => d.isToday);
  return {
    checkedInToday: today ? today.status === SIGNIN_DAY_CLAIMED : false,
    claimableToday: today ? today.status === SIGNIN_DAY_CLAIMABLE : false,
    todayPoints: today ? today.points : 0,
    streak: getStreak(panel),
    panel,
    todayStatus: today ? today.status : null,
  };
}

function assertBusinessOk(response, label) {
  const body = parseJson(response.text);
  const code = body && body.base_resp ? body.base_resp.status_code : undefined;
  const msg =
    body && body.base_resp && body.base_resp.status_msg
      ? String(body.base_resp.status_msg)
      : '';
  if (!response.statusCode || response.statusCode < 200 || response.statusCode >= 300) {
    throw new Error(`http-${label}:${response.statusCode}:${msg}`);
  }
  if (code !== undefined && code !== 0) {
    throw new Error(`biz-${label}:${code}:${msg}`);
  }
  if (!body) throw new Error(`non-json-${label}`);
  return body;
}

async function getPanel(account) {
  const origin = REGIONS[account.region].origin;
  const url = `${origin}/minimax-cloud/api/v1/signin/status?timezone_id=${encodeURIComponent(
    account.timezone
  )}`;
  const response = await httpRequest(url, {
    method: 'GET',
    headers: authHeaders(account.accessToken),
  });
  const body = assertBusinessOk(response, 'status');
  return summarize(parsePanel(body.data));
}

async function claimSignin(account) {
  const before = await getPanel(account);
  if (before.checkedInToday) {
    return {
      state: 'alreadyComplete',
      message: `今天已签到（连签 ${before.streak} 天）`,
      points: before.todayPoints,
      streak: before.streak,
      snapshot: before,
    };
  }
  if (!before.claimableToday) {
    const statusHint =
      before.todayStatus === SIGNIN_DAY_UPCOMING
        ? '未开始'
        : before.todayStatus === SIGNIN_DAY_DISABLED
          ? '不可领'
          : '未知';
    return {
      state: 'failure',
      message: `今天暂不可领（状态：${statusHint}）`,
      points: before.todayPoints,
      streak: before.streak,
      snapshot: before,
    };
  }

  const origin = REGIONS[account.region].origin;
  const url = `${origin}/minimax-cloud/api/v1/signin/claim?timezone_id=${encodeURIComponent(
    account.timezone
  )}`;
  const response = await httpRequest(url, {
    method: 'POST',
    headers: authHeaders(account.accessToken),
    body: '{}',
  });
  const body = assertBusinessOk(response, 'claim');
  const data = body.data || {};
  const result = data.claim_result;
  if (result === CLAIM_RESULT_ALREADY) {
    return {
      state: 'alreadyComplete',
      message: '今天已签到（服务端确认）',
      points: typeof data.points === 'number' ? data.points : before.todayPoints,
      streak: before.streak,
      snapshot: before,
    };
  }
  const points = typeof data.points === 'number' ? data.points : before.todayPoints;
  let after = before;
  if (data.panel) {
    try {
      after = summarize(parsePanel(data.panel));
    } catch {
      after = before;
    }
  } else {
    try {
      after = await getPanel(account);
    } catch {
      after = before;
    }
  }
  if (result !== undefined && result !== CLAIM_RESULT_CLAIMED && result !== CLAIM_RESULT_ALREADY) {
    return {
      state: 'failure',
      message: `签到领取未确认成功（claim_result=${result}）`,
      points,
      streak: after.streak,
      snapshot: after,
    };
  }
  return {
    state: 'success',
    message: `签到成功，+${points} 积分（连签 ${after.streak} 天）`,
    points,
    streak: after.streak,
    snapshot: after,
  };
}

function printIdentity(account) {
  const fromLabel = account.label;
  const fromJwt = identityFromToken(account.accessToken);
  if (fromLabel) {
    log(`账号身份：${redact(fromLabel)}`);
    return fromLabel;
  }
  if (fromJwt) {
    log(`账号身份：${fromJwt}`);
    return fromJwt;
  }
  log(`账号身份：账号 ${account.index}（${REGIONS[account.region].label}）`);
  return `账号${account.index}`;
}

function reasonText(code) {
  const map = {
    timeout: '请求超时',
    'response-too-large': '响应过大',
    'network-error': '网络请求失败',
    'response-error': '响应读取失败',
    'response-aborted': '响应中断',
    'invalid-url': '地址无效',
    'panel-missing': '签到面板数据缺失',
  };
  if (map[code]) return map[code];
  const text = String(code || '');
  if (text.startsWith('http-')) return `HTTP 失败：${redact(text.slice(5))}`;
  if (text.startsWith('biz-')) return `业务失败：${redact(text.slice(4))}`;
  if (text.startsWith('non-json-')) return '接口返回非 JSON';
  return '请求失败';
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
    delete env.MINIMAX_CODE_TOKEN;
    delete env.MINIMAX_MCODE_TOKEN;
    delete env.MINIMAX_ACCESS_TOKEN;
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
    delete env.MINIMAX_CODE_TOKEN;
    delete env.MINIMAX_MCODE_TOKEN;
    delete env.MINIMAX_ACCESS_TOKEN;
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
      } else {
        log(
          `✅ 账号 ${account.index} 参数可读：区域 ${REGIONS[account.region].label}（${account.region}），时区 ${account.timezone}`
        );
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`
  );

  if (!configurationError) {
    log('阶段 2/3：查询面板并领取签到');
    for (let i = 0; i < accounts.length; i++) {
      const account = accounts[i];
      const began = Date.now();
      summary.tasks.total += 1;
      let outcome = 'failure';

      log(`账号 ${account.index} | 子阶段 1/2：身份与配置`);
      printIdentity(account);

      log(`账号 ${account.index} | 子阶段 2/2：签到状态与领取`);
      try {
        if (dryRun) {
          outcome = 'skipped';
          log(
            '⏭️ DRY_RUN_OK：accessToken/region/timezone 格式通过；未请求 status/claim 接口，未验证真实业务'
          );
        } else {
          const result = await claimSignin(account);
          outcome = result.state;
          if (result.state === 'success') log(`✅ ${redact(result.message)}`);
          else if (result.state === 'alreadyComplete') log(`☑️ ${redact(result.message)}`);
          else log(`❌ ${redact(result.message)}`);
          if (result.streak != null) log(`连签天数：${result.streak}`);
          if (result.points != null) log(`今日积分：${result.points}`);
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
    console.error('任务执行异常（已脱敏）');
  });
}

module.exports = {
  parseAccounts,
  parsePanel,
  getStreak,
  summarize,
  TITLE,
  CATALOG_ID,
  REGIONS,
};
