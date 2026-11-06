#!/usr/bin/env node
// name: AI打卡机四平台签到
// cron: 31 10 * * *
/**
 * aidaka · AI 打卡机四平台每日签到 · 青龙独立维护版
 *
 * 上游：a1007479270/aidaka · wps-airscript/checkin.js
 * 仓库：https://github.com/a1007479270/aidaka.git
 * 分支：main
 * 提交：7bf15f9330e7ce7114aa519880b4bc71b11c4275
 * 授权：MIT
 *
 * 功能盘点（主来源 checkin.js；相关 build.py 仅为 deploy.html 生成器，不作为账号任务）：
 * - ima（腾讯 AI 工作台）：refresh_token 换 access_token → 查活动 → 今日签到 → 满签奖励
 * - WorkBuddy / CodeBuddy CN：Bearer token 每日签到
 * - Qoder CN 个人版：设备头 + access/refresh → 查活动窗口 → 领取 Credits（建议 10:00 后）
 * - TraeWork 国内个人版：查签到状态 → claim Credits（9074 繁忙重试）
 * - 上游依赖金山文档表格读写、AirScript HTTP、Server酱/PushPlus/企微 Webhook
 *   → 维护版改为环境变量多账号、Node 标准库 HTTPS、青龙 notify；可选保留账号 JSON 内推送字段
 * - maintainedFeatureCoverage 为空，无已发布同产品完整重复覆盖
 *
 * AIDAKA_ACCOUNTS（必填）：每个非空行一个账号。推荐整行 JSON，须含 platform。
 * 也支持「platform|{json}」，只在首个 | 处拆分，后续 JSON 原文保留。
 * platform 取值：ima / workbuddy / qoder / traework（大小写不敏感）。
 * 账号 JSON 字段与上游一致：
 *   ima: ima_uid, uid_type, ima_guid, refresh_token, name
 *   workbuddy: token, uid, name
 *   qoder: name, refreshToken, accessToken, uid, device{...}
 *   traework: token, uid, device_id, name
 * 可选推送字段（兼容原 D/E/F 列）：serverchan / pushplus / qywx
 * 兼容别名：WPS_AIRSCRIPT_ACCOUNTS、AIDAKA_CHECKIN_ACCOUNTS（仅规范变量为空时读取）
 * AIDAKA_ACCOUNTS_FILE：可选私有 JSONL 文件路径；优先于环境变量；Qoder 刷新 token 后可原子写回
 * AIDAKA_DRY_RUN=1：完全断网预演，只校验参数并模拟阶段与通知摘要
 * AIDAKA_TIMEOUT_MS：单次 HTTP 超时毫秒，默认 30000（1000–120000）
 * AIDAKA_ACCOUNT_GAP_MS：账号间隔毫秒，默认 1500
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略
 *
 * MIT License
 *
 * Copyright (c) a1007479270 / aidaka contributors
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
    const identities = ["ea3ec6764f1fef21", "scripts/wps_airscript.js", "wps_airscript.js", "wps_airscript"];
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

const TITLE = 'AI打卡机四平台签到';
const CATALOG_ID = 'ea3ec6764f1fef21';
const CREDENTIAL_ENV = 'AIDAKA_ACCOUNTS';
const CREDENTIAL_ALIASES = ['WPS_AIRSCRIPT_ACCOUNTS', 'AIDAKA_CHECKIN_ACCOUNTS'];
const ACCOUNTS_FILE_ENV = 'AIDAKA_ACCOUNTS_FILE';
const DRY_RUN_ENV = 'AIDAKA_DRY_RUN';
const DEFAULT_TIMEOUT_MS = 30000;
const MAX_RESPONSE_BYTES = 512 * 1024;
const DEFAULT_ACCOUNT_GAP_MS = 1500;
const PLATFORMS = new Set(['ima', 'workbuddy', 'qoder', 'traework']);

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

function rememberDeep(obj) {
  if (!obj || typeof obj !== 'object') return;
  const keys = [
    'token',
    'accessToken',
    'access_token',
    'refreshToken',
    'refresh_token',
    'machineToken',
    'machineId',
    'machineCode',
    'ima_guid',
    'device_id',
    'serverchan',
    'pushplus',
    'qywx',
    'sct',
    'pp',
    'wx',
  ];
  for (const key of keys) {
    if (typeof obj[key] === 'string') remember(obj[key]);
  }
  if (obj.device && typeof obj.device === 'object') rememberDeep(obj.device);
}

function redact(value) {
  let text = String(value == null ? '' : value).replace(
    /[\r\n\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    ' '
  );
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
    if (secret && secret.length >= 6) text = text.split(secret).join('[已隐藏]');
  }
  text = text.replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/Cloud-IDE-JWT\s+[A-Za-z0-9._~+/=-]+/gi, 'Cloud-IDE-JWT [已隐藏]');
  text = text.replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._~+/=-]+/g, '[已隐藏]');
  text = text.replace(/IMA-TOKEN=[^;\s]+/gi, 'IMA-TOKEN=[已隐藏]');
  text = text.replace(/IMA-REFRESH-TOKEN=[^;\s]+/gi, 'IMA-REFRESH-TOKEN=[已隐藏]');
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
  const value = Number.parseInt(process.env.AIDAKA_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 120000
    ? value
    : DEFAULT_TIMEOUT_MS;
}

function accountGapMs() {
  const value = Number.parseInt(process.env.AIDAKA_ACCOUNT_GAP_MS || '', 10);
  return Number.isFinite(value) && value >= 0 && value <= 60000
    ? value
    : DEFAULT_ACCOUNT_GAP_MS;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
    'scripts/aidaka_checkin.js',
    'aidaka_checkin.js',
    'aidaka',
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
    const options = {
      protocol: parsed.protocol,
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
      path: parsed.pathname + parsed.search,
      method,
      headers: reqHeaders,
      timeout: remaining,
    };
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

function parseJsonSafe(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function toInt32(v) {
  v = v & 0xffffffff;
  return v >= 0x80000000 ? v - 0x100000000 : v;
}

function bkn(token) {
  let result = 5381;
  for (let i = 0; i < token.length; i++) {
    result = toInt32(result + toInt32(toInt32(result) << 5) + token.charCodeAt(i));
  }
  return toInt32(result) & 0x7fffffff;
}

function readCredentialRaw() {
  const filePath = String(process.env[ACCOUNTS_FILE_ENV] || '').trim();
  if (filePath) {
    try {
      const text = fs.readFileSync(filePath, 'utf8');
      if (String(text).trim()) return { raw: String(text), source: 'file', filePath };
    } catch {
      return { raw: '', source: 'file-missing', filePath };
    }
  }
  const primary = process.env[CREDENTIAL_ENV];
  if (primary != null && String(primary).trim() !== '') {
    return { raw: String(primary), source: 'env', filePath: '' };
  }
  for (const alias of CREDENTIAL_ALIASES) {
    const value = process.env[alias];
    if (value != null && String(value).trim() !== '') {
      return { raw: String(value), source: 'alias:' + alias, filePath: '' };
    }
  }
  return { raw: '', source: 'missing', filePath: '' };
}

function writeAccountsFile(filePath, accounts) {
  if (!filePath) return false;
  const lines = accounts.map((account) => {
    const payload = { platform: account.platform, ...account.acc };
    return JSON.stringify(payload);
  });
  const tmp = filePath + '.tmp';
  fs.writeFileSync(tmp, lines.join('\n') + '\n', { encoding: 'utf8', mode: 0o600 });
  fs.renameSync(tmp, filePath);
  try {
    fs.chmodSync(filePath, 0o600);
  } catch {
    /* ignore */
  }
  return true;
}

function parseAccountLine(line, index) {
  remember(line);
  let platform = '';
  let jsonText = line;
  const pipe = line.indexOf('|');
  if (pipe > 0) {
    const left = line.slice(0, pipe).trim().toLowerCase();
    if (PLATFORMS.has(left)) {
      platform = left;
      jsonText = line.slice(pipe + 1).trim();
    }
  }
  let acc;
  try {
    acc = JSON.parse(jsonText);
  } catch {
    return {
      index,
      platform: platform || '',
      acc: null,
      valid: false,
      error: 'json-parse',
      rawLine: line,
    };
  }
  if (!acc || typeof acc !== 'object' || Array.isArray(acc)) {
    return {
      index,
      platform: platform || '',
      acc: null,
      valid: false,
      error: 'json-object',
      rawLine: line,
    };
  }
  if (!platform) {
    platform = String(acc.platform || acc.app || '').trim().toLowerCase();
  }
  rememberDeep(acc);
  const validation = validateAccount(platform, acc);
  return {
    index,
    platform,
    acc,
    valid: validation.ok,
    error: validation.error,
    identityHint: sanitizeDisplayText(acc.name || acc.uid || acc.remark || ''),
    serverchan: String(acc.serverchan || acc.sct || '').trim(),
    pushplus: String(acc.pushplus || acc.pp || '').trim(),
    qywx: String(acc.qywx || acc.wx || '').trim(),
    tokenChanged: false,
  };
}

function validateAccount(platform, acc) {
  if (!PLATFORMS.has(platform)) {
    return { ok: false, error: 'unknown-platform' };
  }
  if (platform === 'ima') {
    if (!acc.refresh_token) return { ok: false, error: 'ima-missing-refresh' };
    if (!acc.ima_uid) return { ok: false, error: 'ima-missing-uid' };
    if (!acc.ima_guid) return { ok: false, error: 'ima-missing-guid' };
    return { ok: true, error: '' };
  }
  if (platform === 'workbuddy') {
    if (!acc.token) return { ok: false, error: 'workbuddy-missing-token' };
    return { ok: true, error: '' };
  }
  if (platform === 'qoder') {
    const hasToken = !!(acc.accessToken || acc.token || acc.refreshToken || acc.refresh_token);
    if (!hasToken) return { ok: false, error: 'qoder-missing-token' };
    const device = acc.device || {};
    if (!device.machineToken) return { ok: false, error: 'qoder-missing-device' };
    return { ok: true, error: '' };
  }
  if (platform === 'traework') {
    if (!acc.token) return { ok: false, error: 'traework-missing-token' };
    if (!acc.device_id) return { ok: false, error: 'traework-missing-device' };
    return { ok: true, error: '' };
  }
  return { ok: false, error: 'unknown-platform' };
}

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'));
  return lines.map((line, index) => parseAccountLine(line, index + 1));
}

function configErrorText(code) {
  const map = {
    'json-parse': '账号 JSON 解析失败',
    'json-object': '账号须为 JSON 对象',
    'unknown-platform': '未知平台，须为 ima / workbuddy / qoder / traework',
    'ima-missing-refresh': 'ima 缺少 refresh_token',
    'ima-missing-uid': 'ima 缺少 ima_uid',
    'ima-missing-guid': 'ima 缺少 ima_guid',
    'workbuddy-missing-token': 'workbuddy 缺少 token',
    'qoder-missing-token': 'qoder 缺少 accessToken 或 refreshToken',
    'qoder-missing-device': 'qoder 缺少 device.machineToken',
    'traework-missing-token': 'traework 缺少 token',
    'traework-missing-device': 'traework 缺少 device_id',
    'file-missing': 'AIDAKA_ACCOUNTS_FILE 指定的文件不存在或不可读',
  };
  return map[code] || redact(code || '配置错误');
}

function reasonText(code) {
  const map = {
    timeout: '请求超时',
    'response-too-large': '响应过大',
    'network-error': '网络请求失败',
    'response-error': '响应读取失败',
    'response-aborted': '响应中断',
    'invalid-url': '地址无效',
  };
  if (map[code]) return map[code];
  return redact(code || '请求失败');
}

async function imaCheckin(acc) {
  const BASE = 'https://ima.qq.com';
  const refreshBody = JSON.stringify({
    userId: acc.ima_uid || '',
    refreshToken: acc.refresh_token || '',
    tokenType: -1,
  });
  const refreshHeaders = {
    'Content-Type': 'application/json',
    from_browser_ima: '1',
    extension_version: '5.17.2',
    'x-ima-cookie': 'IMA-GUID=' + (acc.ima_guid || '') + '; PLATFORM=H5',
  };
  const r1 = await httpRequest(BASE + '/cgi-bin/auth_login/refresh', {
    method: 'POST',
    headers: refreshHeaders,
    body: refreshBody,
  });
  log(`ima 刷新登录 HTTP ${r1.statusCode}；长度 ${r1.text.length} 字节`);
  const d1 = parseJsonSafe(r1.text) || {};
  const token = d1.token || '';
  if (token) remember(token);
  if (d1.code !== 0 || !token) {
    return {
      status: 'error',
      action: 'refresh_failed',
      msg:
        '刷新登录失败 code=' +
        d1.code +
        ' msg=' +
        sanitizeDisplayText(d1.msg || '') +
        '（refresh_token 可能已失效）',
    };
  }

  const cookieParts = [
    'IMA-UID=' + (acc.ima_uid || ''),
    'IMA-TOKEN=' + token,
    'IMA-REFRESH-TOKEN=' + (acc.refresh_token || ''),
    'UID-TYPE=' + (acc.uid_type || '1'),
    'IMA-GUID=' + (acc.ima_guid || ''),
    'PLATFORM=H5',
  ];
  const authHeaders = () => ({
    'Content-Type': 'application/json',
    from_browser_ima: '1',
    extension_version: '5.17.2',
    'x-ima-cookie': cookieParts.join('; '),
    'x-ima-bkn': String(bkn(token)),
  });

  const r2 = await httpRequest(BASE + '/cgi-bin/daily_login_activity/get_activity_info', {
    method: 'POST',
    headers: authHeaders(),
    body: '{}',
  });
  log(`ima 查询活动 HTTP ${r2.statusCode}；长度 ${r2.text.length} 字节`);
  const info = parseJsonSafe(r2.text) || {};
  if (info.code !== 0) {
    return {
      status: 'error',
      action: 'query_failed',
      msg: '查询活动失败 code=' + info.code + ' msg=' + sanitizeDisplayText(info.msg || ''),
    };
  }
  let today = null;
  let bonus = null;
  const infos = info.infos || [];
  for (let i = 0; i < infos.length; i++) {
    if (infos[i].top === '今日') today = infos[i];
    if (infos[i].top === '满签奖励') bonus = infos[i];
  }
  if (!today) {
    return { status: 'error', action: 'structure_changed', msg: '未找到今日条目，活动可能已改版' };
  }

  const result = { status: 'ok', action: '', msg: '', points: undefined };
  const st = today.status;
  if (st === 3) {
    const r3 = await httpRequest(BASE + '/cgi-bin/daily_login_activity/check_in', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ type: 1 }),
    });
    log(`ima 签到 HTTP ${r3.statusCode}；长度 ${r3.text.length} 字节`);
    const d3 = parseJsonSafe(r3.text) || {};
    if (d3.code === 0) {
      result.action = 'clicked';
      result.points = d3.rewardReceived || today.reward;
      result.msg = '签到成功';
    } else if (/已签到|请明天/.test(JSON.stringify(d3))) {
      result.action = 'skip_already_signed';
      result.msg = '今天已签到';
    } else {
      result.status = 'error';
      result.action = 'checkin_failed';
      result.msg = 'code=' + d3.code + ' msg=' + sanitizeDisplayText(d3.msg || '');
    }
  } else if (st === 2) {
    result.action = 'skip_already_signed';
    result.msg = '今天已签到';
  } else {
    result.action = 'not_available';
    result.msg = '今天不可签到 (status=' + st + ')';
    result.status = 'error';
  }

  if (bonus && bonus.status === 3) {
    const r4 = await httpRequest(BASE + '/cgi-bin/daily_login_activity/check_in', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ type: 2 }),
    });
    log(`ima 满签奖励 HTTP ${r4.statusCode}；长度 ${r4.text.length} 字节`);
    const d4 = parseJsonSafe(r4.text) || {};
    if (d4.code === 0) result.msg += '；满签奖励已领取';
  }
  return result;
}

async function wbCheckin(acc) {
  const BASE = 'https://www.codebuddy.cn';
  const headers = {
    Authorization: 'Bearer ' + (acc.token || ''),
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) WorkBuddyCheckin/1.0',
    Accept: 'application/json, text/plain, */*',
    Origin: BASE,
    Referer: BASE + '/',
  };
  const r = await httpRequest(BASE + '/v2/billing/meter/daily-checkin', {
    method: 'POST',
    headers,
    body: '{}',
  });
  log(`workbuddy 签到 HTTP ${r.statusCode}；长度 ${r.text.length} 字节`);
  const body = parseJsonSafe(r.text) || {};
  const text = JSON.stringify(body);
  const msg = sanitizeDisplayText(body.msg || '');
  if (/已签到|明天再来|请明天|already/i.test(text)) {
    return { status: 'ok', action: 'skip_already_signed', msg: msg || '今天已签到' };
  }
  const code = body.code;
  const data = body.data || {};
  if (code === 0 || /^(OK|SUCCESS)$/i.test(msg) || /成功/.test(msg)) {
    const points =
      (data && (data.credit || data.points || data.point || data.reward)) ||
      body.points ||
      body.reward;
    return { status: 'ok', action: 'clicked', points, msg: msg || '领取成功' };
  }
  return {
    status: 'error',
    action: 'checkin_failed',
    msg: 'HTTP ' + r.statusCode + ' 业务失败',
  };
}

async function qoderCheckin(acc) {
  const BASE = String(acc.base || 'https://openapi.qoder.com.cn').replace(/\/$/, '');
  const COSY = {
    clientType: 'Cosy-ClientType',
    machineOS: 'Cosy-MachineOS',
    machineHostname: 'Cosy-MachineHostname',
    machineId: 'Cosy-MachineId',
    machineToken: 'Cosy-MachineToken',
    machineCode: 'Cosy-MachineCode',
    machineType: 'Cosy-MachineType',
    version: 'Cosy-Version',
  };
  const device = acc.device || {};
  if (!device.machineToken) {
    return {
      status: 'error',
      action: 'no_device',
      msg: '缺少设备标识(Cosy-MachineToken)，活动接口不会下发活动',
    };
  }
  function headers(token) {
    const h = {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'User-Agent': 'Qoder/claim',
    };
    for (const k of Object.keys(COSY)) {
      if (device[k] !== undefined && device[k] !== null && String(device[k]) !== '') {
        h[COSY[k]] = String(device[k]);
      }
    }
    if (!h['Cosy-ClientType']) h['Cosy-ClientType'] = '10';
    if (token) h.Authorization = 'Bearer ' + token;
    return h;
  }
  async function refreshToken() {
    const r = await httpRequest(BASE + '/api/v1/deviceToken/refresh', {
      method: 'POST',
      headers: headers(null),
      body: JSON.stringify({ refresh_token: acc.refreshToken || acc.refresh_token || '' }),
    });
    log(`qoder 刷新 token HTTP ${r.statusCode}；长度 ${r.text.length} 字节`);
    const d = parseJsonSafe(r.text) || {};
    if (r.statusCode !== 200) {
      return { token: null, err: '刷新失败 HTTP ' + r.statusCode, changed: false };
    }
    const tk = d.token || d.accessToken || d.access_token || '';
    if (!tk) return { token: null, err: '刷新响应里没有 token', changed: false };
    remember(tk);
    acc.accessToken = tk;
    if (d.refreshToken || d.refresh_token) {
      const rt = d.refreshToken || d.refresh_token;
      remember(rt);
      acc.refreshToken = rt;
    }
    return { token: tk, err: '', changed: true };
  }

  let token = acc.accessToken || acc.token || '';
  let tokenChanged = false;
  if (!token) {
    const rf = await refreshToken();
    if (!rf.token) return { status: 'error', action: 'token_expired', msg: rf.err };
    token = rf.token;
    tokenChanged = true;
  }

  let r = await httpRequest(BASE + '/sash/api/v1/me/campaigns', {
    method: 'GET',
    headers: headers(token),
  });
  log(`qoder 活动列表 HTTP ${r.statusCode}；长度 ${r.text.length} 字节`);
  let st = r.statusCode;
  let data = parseJsonSafe(r.text) || {};
  if (st === 401) {
    const rf2 = await refreshToken();
    if (!rf2.token) return { status: 'error', action: 'token_expired', msg: rf2.err };
    token = rf2.token;
    tokenChanged = true;
    r = await httpRequest(BASE + '/sash/api/v1/me/campaigns', {
      method: 'GET',
      headers: headers(token),
    });
    log(`qoder 活动列表（续期后）HTTP ${r.statusCode}；长度 ${r.text.length} 字节`);
    st = r.statusCode;
    data = parseJsonSafe(r.text) || {};
  }
  if (st !== 200) {
    return {
      status: 'error',
      action: 'campaign_failed',
      msg: 'HTTP ' + st + ' 获取活动失败',
      tokenChanged,
    };
  }
  const campaigns = data.campaigns || [];
  if (!campaigns.length) {
    return {
      status: 'ok',
      action: 'no_campaign',
      msg: '活动列表为空：可能未到10:00窗口、活动已下线，或设备头与客户端版本不符',
      tokenChanged,
    };
  }

  const now = Date.now();
  const UNCLAIMED = ['UNCLAIMED', 'NOT_CLAIMED', 'PENDING', 'AVAILABLE', 'CLAIMABLE'];
  const pending = [];
  for (let i = 0; i < campaigns.length; i++) {
    const c = campaigns[i];
    if (!c.campaignId) continue;
    const cst = String(c.claimStatus || '').toUpperCase();
    if (cst === 'CLAIMED') continue;
    const start = c.startAt || 0;
    const end = c.endAt || 0;
    const inWindow = (!start || now >= start) && (!end || now <= end);
    if (UNCLAIMED.indexOf(cst) >= 0 || (inWindow && !cst)) pending.push(c);
  }
  if (!pending.length) {
    return {
      status: 'ok',
      action: 'skip_already_claimed',
      msg: '本轮已领',
      tokenChanged,
    };
  }

  let gained = 0;
  const failed = [];
  for (let j = 0; j < pending.length; j++) {
    const c2 = pending[j];
    const key = c2.campaignKey || c2.campaignId;
    const expect = (c2.benefit || {}).amount || 0;
    let r2 = await httpRequest(BASE + '/sash/api/v1/me/campaigns/' + c2.campaignId + '/claim', {
      method: 'POST',
      headers: headers(token),
      body: '{}',
    });
    log(`qoder 领取 ${sanitizeDisplayText(key)} HTTP ${r2.statusCode}；长度 ${r2.text.length} 字节`);
    let st2 = r2.statusCode;
    let d2 = parseJsonSafe(r2.text) || {};
    if (st2 === 401) {
      const rf3 = await refreshToken();
      if (!rf3.token) {
        failed.push(key + ':token失效');
        break;
      }
      token = rf3.token;
      tokenChanged = true;
      r2 = await httpRequest(BASE + '/sash/api/v1/me/campaigns/' + c2.campaignId + '/claim', {
        method: 'POST',
        headers: headers(token),
        body: '{}',
      });
      st2 = r2.statusCode;
      d2 = parseJsonSafe(r2.text) || {};
    }
    const claimStatus = String(d2.status || '').toUpperCase();
    if (st2 === 200 && ['CLAIMED', 'REPLAYED', 'SUCCESS'].indexOf(claimStatus) >= 0) {
      if (d2.replayed) continue;
      gained += Number((d2.benefit || {}).amount || expect || 0);
    } else {
      failed.push(key + ':HTTP' + st2);
    }
  }
  if (failed.length) {
    return {
      status: gained > 0 ? 'ok' : 'error',
      action: 'claim_failed',
      msg: failed.join('; ') + (gained ? '（已领 ' + gained + ' Credits）' : ''),
      credits: gained || undefined,
      tokenChanged,
    };
  }
  return {
    status: 'ok',
    action: 'clicked',
    credits: gained,
    msg: '领取成功 ' + gained + ' Credits',
    tokenChanged,
  };
}

async function traeworkCheckin(acc) {
  const BASE = 'https://api.trae.cn';
  const token = acc.token || '';
  const deviceId = acc.device_id || '';
  const headers = () => ({
    Authorization: 'Cloud-IDE-JWT ' + token,
    'Content-Type': 'application/json',
    Accept: 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TraeWorkCheckin/1.0',
    'X-User-Region': 'CN',
    'x-device-id': deviceId,
  });
  const r = await httpRequest(BASE + '/trae/api/v2/ug/checkin_credits/status', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ req_source: 2 }),
  });
  log(`traework 状态 HTTP ${r.statusCode}；长度 ${r.text.length} 字节`);
  const status = parseJsonSafe(r.text) || {};
  if (r.statusCode !== 200 || status.checked_in === undefined) {
    return {
      status: 'error',
      action: 'query_failed',
      msg:
        '查询签到状态失败（HTTP ' +
        r.statusCode +
        '）：' +
        sanitizeDisplayText(status.message || ''),
    };
  }
  if (status.checked_in) {
    return {
      status: 'ok',
      action: 'skip_already_signed',
      msg: '今天已签到',
      credits: status.credits,
    };
  }
  if (status.enable === false) {
    return { status: 'ok', action: 'disabled', msg: '该账号未开启签到功能' };
  }
  for (let attempt = 0; attempt < 4; attempt++) {
    const r2 = await httpRequest(BASE + '/trae/api/v2/ug/checkin_credits/claim', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ req_source: 2 }),
    });
    log(`traework 领取 HTTP ${r2.statusCode}；长度 ${r2.text.length} 字节（尝试 ${attempt + 1}）`);
    const resp = parseJsonSafe(r2.text) || {};
    if (r2.statusCode === 200 && resp.code === 0) {
      const data = resp.data || {};
      return {
        status: 'ok',
        action: 'clicked',
        credits: data.credits !== undefined ? data.credits : status.credits,
        msg: sanitizeDisplayText(resp.message || '签到成功'),
      };
    }
    const bizCode = resp.code;
    const msg = sanitizeDisplayText(resp.message || '');
    if (bizCode === 9074 && attempt < 3) {
      await sleep(5000);
      continue;
    }
    let m = '签到失败（HTTP ' + r2.statusCode + '）：' + msg;
    if (bizCode === 9074) m += '（服务端繁忙，已重试多次）';
    if (bizCode === 9004) m += '；请重新获取带设备ID的账号配置';
    return { status: 'error', action: 'claim_failed', msg: m };
  }
  return { status: 'error', action: 'claim_failed', msg: '重试后仍失败' };
}

async function runPlatform(account) {
  const platform = account.platform;
  const acc = account.acc;
  if (platform === 'ima') return imaCheckin(acc);
  if (platform === 'workbuddy') return wbCheckin(acc);
  if (platform === 'qoder') return qoderCheckin(acc);
  if (platform === 'traework') return traeworkCheckin(acc);
  return { status: 'error', action: 'unknown_platform', msg: '未知平台: ' + platform };
}

function classifyResult(res) {
  if (!res || res.status !== 'ok') {
    return { ok: false, state: 'failure', message: (res && res.msg) || '失败' };
  }
  if (
    res.action === 'skip_already_signed' ||
    res.action === 'skip_already_claimed' ||
    res.action === 'disabled' ||
    res.action === 'no_campaign'
  ) {
    return { ok: true, state: 'alreadyComplete', message: res.msg || '已完成/无需领取' };
  }
  if (res.action === 'not_available') {
    return { ok: false, state: 'failure', message: res.msg || '今日不可签到' };
  }
  return { ok: true, state: 'success', message: res.msg || '成功' };
}

async function sendLegacyChannelNotify(account, title, text, dryRun) {
  if (dryRun) return [];
  const sent = [];
  const sct = account.serverchan;
  const pp = account.pushplus;
  const wx = account.qywx;
  if (sct) {
    remember(sct);
    try {
      const r = await httpRequest('https://sctapi.ftqq.com/' + sct + '.send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'title=' + encodeURIComponent(title) + '&desp=' + encodeURIComponent(text),
      });
      sent.push('Server酱:' + r.statusCode);
    } catch (e) {
      sent.push('Server酱失败');
    }
  }
  if (pp) {
    remember(pp);
    try {
      const r2 = await httpRequest('https://www.pushplus.plus/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: pp, title, content: text }),
      });
      sent.push('PushPlus:' + r2.statusCode);
    } catch (e) {
      sent.push('PushPlus失败');
    }
  }
  if (wx) {
    remember(wx);
    try {
      const r3 = await httpRequest(wx, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ msgtype: 'text', text: { content: title + '\n' + text } }),
      });
      sent.push('企业微信:' + r3.statusCode);
    } catch (e) {
      sent.push('企业微信失败');
    }
  }
  return sent;
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
    delete env[ACCOUNTS_FILE_ENV];
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
    delete env[ACCOUNTS_FILE_ENV];
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

  const identity =
    account.identityHint ||
    sanitizeDisplayText(account.acc.name || account.acc.uid || '') ||
    '';
  if (identity) log(`账号 ${account.index} 身份：${identity}（平台 ${account.platform}）`);
  else log(`账号 ${account.index} 平台：${account.platform}`);

  log(`账号 ${account.index} | 子阶段 1/1：${account.platform} 签到/领取`);
  const stageStarted = Date.now();
  const res = await runPlatform(account);
  if (res.tokenChanged) account.tokenChanged = true;
  const classified = classifyResult(res);
  let detail = redact(classified.message);
  if (res.points !== undefined && res.points !== null) detail += ` (+${res.points})`;
  if (res.credits !== undefined && res.credits !== null) detail += ` (${res.credits} Credits)`;

  if (classified.ok && classified.state === 'success') {
    log(`✅ ${detail} | 耗时 ${Date.now() - stageStarted}ms`);
    mark('success');
    return { ok: true, alreadyComplete: false, stages, identity, res };
  }
  if (classified.ok && classified.state === 'alreadyComplete') {
    log(`☑️ ${detail} | 耗时 ${Date.now() - stageStarted}ms`);
    mark('alreadyComplete');
    return { ok: true, alreadyComplete: true, stages, identity, res };
  }
  log(`❌ ${detail} | 耗时 ${Date.now() - stageStarted}ms`);
  mark('failure');
  return { ok: false, stages, identity, reason: classified.message, res };
}

async function main() {
  const started = Date.now();
  const dryRun = enabled(process.env[DRY_RUN_ENV]);
  const loaded = readCredentialRaw();
  const accounts = parseAccounts(loaded.raw);
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

  if (loaded.source === 'file-missing') {
    configurationError = true;
    log(`❌ 配置错误：${configErrorText('file-missing')}`);
  } else if (!accounts.length) {
    configurationError = true;
    log(
      `❌ 配置错误：缺少 ${CREDENTIAL_ENV}（或兼容别名 ${CREDENTIAL_ALIASES.join(
        ' / '
      )} / ${ACCOUNTS_FILE_ENV}）的非空账号行`
    );
  } else {
    for (const account of accounts) {
      if (!account.valid) {
        configurationError = true;
        log(
          `❌ 配置错误：账号 ${account.index} ${configErrorText(account.error)}（平台 ${
            account.platform || '未指定'
          }）`
        );
      } else {
        log(
          `✅ 账号 ${account.index} 参数格式通过（平台 ${account.platform}${
            account.identityHint ? '；' + account.identityHint : ''
          }）`
        );
      }
    }
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${
      Date.now() - configStarted
    }ms`
  );

  const legacyLines = [];

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
            `⏭️ DRY_RUN_OK：平台 ${account.platform} 参数校验通过；未请求网络，未验证真实业务`
          );
          log(
            `账号 ${account.index} 统计：总任务 1 | 成功 0 | 已完成 0 | 跳过 1 | 失败 0 | 耗时 ${
              Date.now() - began
            }ms`
          );
          legacyLines.push({
            account,
            line: `[${account.platform}] ${account.identityHint || '#' + account.index} → dry-run`,
          });
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
          legacyLines.push({
            account,
            line: `[${account.platform}] ${
              result.identity || account.identityHint || '#' + account.index
            } → ${(result.res && result.res.action) || ''}：${redact(
              (result.res && result.res.msg) || result.reason || ''
            )}`,
          });
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
        legacyLines.push({
          account,
          line: `[${account.platform}] ${account.identityHint || '#' + account.index} → 异常`,
        });
      }
      if (!dryRun && i < accounts.length - 1) await sleep(accountGapMs());
    }

    if (!dryRun && loaded.filePath && accounts.some((a) => a.tokenChanged)) {
      try {
        writeAccountsFile(loaded.filePath, accounts);
        log('✅ Qoder token 已刷新并写回账号文件');
      } catch {
        log('⚠️ token 写回账号文件失败（不影响本次业务判定）');
      }
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

  if (!configurationError && !dryRun) {
    const channels = {};
    for (const item of legacyLines) {
      const row = item.account;
      if (!row.serverchan && !row.pushplus && !row.qywx) continue;
      const key = row.serverchan + '|' + row.pushplus + '|' + row.qywx;
      if (!channels[key]) {
        channels[key] = {
          sct: row.serverchan,
          pp: row.pushplus,
          wx: row.qywx,
          lines: [],
        };
      }
      channels[key].lines.push(item.line);
    }
    const title = 'ai自动签到 ' + nowText().slice(0, 10);
    for (const key of Object.keys(channels)) {
      const ch = channels[key];
      const fakeAccount = { serverchan: ch.sct, pushplus: ch.pp, qywx: ch.wx };
      const sent = await sendLegacyChannelNotify(fakeAccount, title, ch.lines.join('\n'), dryRun);
      if (sent.length) log(`兼容推送：${sent.join(' ')}`);
    }
  }

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
  validateAccount,
  classifyResult,
  CREDENTIAL_ENV,
  DRY_RUN_ENV,
};
