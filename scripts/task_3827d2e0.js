// name: 蘑菇钉工学云打卡
// cron: 3 8,18 * * *
/**
 * 蘑菇钉（工学云）自动打卡 · 青龙独立维护版
 *
 * 上游：YingxiaQwQ/Auto-Moguding · index.js
 * 仓库：https://github.com/YingxiaQwQ/Auto-Moguding
 * 分支：main
 * 提交：4e99ceb2fbd24d749b773bf2a3c2c8cd4b5e2927
 * 授权：GPL-3.0
 *
 * 功能盘点（主来源）：
 * - 手机号+密码登录 api.moguding.net（AES-ECB 加密凭据）
 * - 获取实习计划 planId，查询考勤同步列表判断今日上班/下班状态
 * - 按状态提交 START（上班）或 END（下班）打卡，含地址与经纬度
 * - 可选多次打卡（按上次类型交替）、可选关闭打卡、可选坐标末三位抖动、可选自定义 UA
 * - 可选提供 token/userId/planId 跳过首次登录（失效后自动重新登录）
 * - 上游 user.json / uaList.json 本地文件与 autoUpdate 写回已移除（不安全默认突变）
 *
 * MOGUDING_ACCOUNTS（必填）：每个非空行一个账号。推荐单行 JSON；也可
 * 「手机号|其余」，只在首个竖线处拆分，其余为密码或「密码|位置JSON」。
 * 不使用 &、@ 分隔账号。手机号、密码、Cookie、Token 永不打印。
 * 兼容别名：MOGUDING_USER（仅当 MOGUDING_ACCOUNTS 为空时读取）。
 * MOGUDING_SIGN_IN：全局默认是否打卡，1/true 开启（默认），0/false 关闭；账号 JSON 的 signIn 优先。
 * MOGUDING_MULTIPLE：全局默认是否多次交替打卡，默认关闭；账号 multiple 优先。
 * MOGUDING_RANDOM_LOCATION：全局默认是否抖动经纬度末三位，默认关闭；账号 randomLocation 优先。
 * MOGUDING_TYPE：设备类型，默认 android；账号 type 优先。
 * MOGUDING_DESC：签到备注默认值；账号 description/desc 优先。
 * MOGUDING_UA：全局 UA；账号 UA 优先。未设置时使用内置安卓 UA。
 * MOGUDING_DRY_RUN=1：完全断网预演，校验账号字段并模拟阶段，不请求 API、不真实通知。
 * MOGUDING_TIMEOUT_MS：单次 HTTP 超时毫秒，默认 20000（1000–120000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * 本维护版基于 YingxiaQwQ/Auto-Moguding，按 GPL-3.0 保留并传播。
 * Copyright (C) 上游作者 YingxiaQwQ 及贡献者
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */
'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection
      .trim()
      .toLowerCase()
      .split(/[,;\s]+/)
      .filter(Boolean);
    const identities = [
      '3827d2e03a385b9d',
      'scripts/moguding_clock.js',
      'moguding_clock.js',
      'index.js',
      'moguding',
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

const TITLE = '蘑菇钉工学云打卡';
const CATALOG_ID = '3827d2e03a385b9d';
const CREDENTIAL_ENV = 'MOGUDING_ACCOUNTS';
const CREDENTIAL_ALIASES = ['MOGUDING_USER'];
const DRY_RUN_ENV = 'MOGUDING_DRY_RUN';
const API_BASE = 'https://api.moguding.net:9000';
const AES_KEY = '23DbtQHR2UMbH6mJ';
const SIGN_SALT = '3478cbbc33f84bd00d75d7dfa69e0daa';
const DEFAULT_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const ACCOUNT_GAP_MS = 1500;
const DEFAULT_UA =
  'Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';

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
  text = text.replace(/1[3-9]\d{9}/g, '[已隐藏手机号]');
  text = text.replace(/Bearer\s+[A-Za-z0-9._+/=-]+/gi, 'Bearer [已隐藏]');
  text = text.replace(/\b[a-fA-F0-9]{32,}\b/g, '[已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.MOGUDING_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 120000
    ? value
    : DEFAULT_TIMEOUT_MS;
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
    'scripts/moguding_clock.js',
    'moguding_clock.js',
    'index.js',
    'moguding',
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

function boolFrom(value, fallback) {
  if (value === undefined || value === null || value === '') return fallback;
  if (typeof value === 'boolean') return value;
  if (enabled(value)) return true;
  if (disabled(value)) return false;
  return fallback;
}

function encryptAES(str, key) {
  const cipher = crypto.createCipheriv('aes-128-ecb', Buffer.from(key, 'utf8'), null);
  cipher.setAutoPadding(true);
  return cipher.update(String(str), 'utf8', 'hex') + cipher.final('hex');
}

function getSign(text) {
  return crypto
    .createHash('md5')
    .update(String(text) + SIGN_SALT, 'utf8')
    .digest('hex');
}

function applyRandomLocation(longitude, latitude) {
  const lon = String(longitude);
  const lat = String(latitude);
  const nextLon = lon.slice(0, Math.max(0, lon.length - 3)) + String(Math.floor(Math.random() * 1000)).padStart(3, '0');
  const nextLat = lat.slice(0, Math.max(0, lat.length - 3)) + String(Math.floor(Math.random() * 1000)).padStart(3, '0');
  return { longitude: nextLon, latitude: nextLat };
}

function parseAccountLine(line, index) {
  remember(line);
  let raw = {};
  const trimmed = String(line || '').trim();
  if (!trimmed) {
    return { index, valid: false, reason: 'empty-line' };
  }

  if (trimmed.startsWith('{')) {
    try {
      raw = JSON.parse(trimmed);
    } catch {
      return { index, valid: false, reason: 'invalid-json' };
    }
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      return { index, valid: false, reason: 'invalid-json' };
    }
  } else {
    const pipe = trimmed.indexOf('|');
    if (pipe <= 0) {
      return { index, valid: false, reason: 'invalid-format' };
    }
    const phone = trimmed.slice(0, pipe).trim();
    const rest = trimmed.slice(pipe + 1);
    remember(phone);
    remember(rest);
    const second = rest.indexOf('|');
    if (second < 0) {
      return { index, valid: false, reason: 'missing-location' };
    }
    const password = rest.slice(0, second);
    const locationPart = rest.slice(second + 1).trim();
    remember(password);
    if (locationPart.startsWith('{')) {
      try {
        raw = JSON.parse(locationPart);
      } catch {
        return { index, valid: false, reason: 'invalid-location-json' };
      }
    } else {
      const parts = locationPart.split('|');
      // longitude|latitude|address|province|city|area|country
      raw = {
        longitude: parts[0] || '',
        latitude: parts[1] || '',
        address: parts[2] || '',
        province: parts[3] || '',
        city: parts[4] || '',
        area: parts[5] || '',
        country: parts[6] || '中国',
      };
    }
    raw.phone = phone;
    raw.password = password;
  }

  const phone = String(raw.phone || raw.mobile || '').trim();
  const password = String(raw.password || raw.passwd || '').trim();
  remember(phone);
  remember(password);
  remember(String(raw.token || ''));
  remember(String(raw.userId || ''));
  remember(String(raw.planId || ''));

  const country = String(raw.country || '').trim() || '中国';
  const province = String(raw.province || '').trim();
  const city = String(raw.city || '').trim();
  const area = String(raw.area || '').trim();
  const address = String(raw.address || '').trim();
  let longitude = String(raw.longitude || raw.lng || '').trim();
  let latitude = String(raw.latitude || raw.lat || '').trim();
  const deviceType = String(raw.type || process.env.MOGUDING_TYPE || 'android').trim() || 'android';
  const description = String(
    raw.description != null ? raw.description : raw.desc != null ? raw.desc : process.env.MOGUDING_DESC || ''
  );
  const ua = String(raw.UA || raw.ua || process.env.MOGUDING_UA || DEFAULT_UA).trim() || DEFAULT_UA;
  const signIn = boolFrom(
    raw.signIn,
    boolFrom(process.env.MOGUDING_SIGN_IN, true)
  );
  const multiple = boolFrom(
    raw.multiple,
    boolFrom(process.env.MOGUDING_MULTIPLE, false)
  );
  const randomLocation = boolFrom(
    raw.randomLocation,
    boolFrom(process.env.MOGUDING_RANDOM_LOCATION, false)
  );
  const token = String(raw.token || '').trim();
  const userId = String(raw.userId || '').trim();
  const planId = String(raw.planId || '').trim();

  if (!phone || !password) {
    return { index, valid: false, reason: 'missing-credentials' };
  }
  if (!province || !address || !longitude || !latitude) {
    return { index, valid: false, reason: 'missing-location' };
  }

  if (randomLocation) {
    const jittered = applyRandomLocation(longitude, latitude);
    longitude = jittered.longitude;
    latitude = jittered.latitude;
  }

  return {
    index,
    valid: true,
    phone,
    password,
    country,
    province,
    city,
    area,
    address,
    longitude,
    latitude,
    type: deviceType,
    description,
    ua,
    signIn,
    multiple,
    randomLocation,
    token,
    userId,
    planId,
  };
}

function parseAccounts(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line, index) => parseAccountLine(line, index + 1));
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
      if (!reqHeaders['Content-Type'] && !reqHeaders['content-type']) {
        reqHeaders['Content-Type'] = 'application/json; charset=UTF-8';
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
  return API_BASE.replace(/\/$/, '') + '/' + String(pathname).replace(/^\//, '');
}

function pickIdentity(data) {
  if (!data || typeof data !== 'object') return '';
  const keys = [
    'nikeName',
    'nickName',
    'nickname',
    'userName',
    'username',
    'realName',
    'name',
    'displayName',
  ];
  for (const key of keys) {
    if (data[key] != null && String(data[key]).trim()) return String(data[key]).trim();
  }
  if (data.userId != null && String(data.userId).trim()) return `uid:${data.userId}`;
  return '';
}

function localDateText(ms) {
  return new Date(ms).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' });
}

async function loginAccount(account) {
  const postData = {
    phone: encryptAES(account.phone, AES_KEY),
    password: encryptAES(account.password, AES_KEY),
    t: encryptAES(String(Date.now()), AES_KEY),
    loginType: account.type,
  };
  const response = await httpRequest(apiUrl('/session/user/v3/login'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json; charset=UTF-8',
      'User-Agent': account.ua,
      Accept: 'application/json',
    },
    body: JSON.stringify(postData),
  });
  log(`登录响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
  const body = parseJsonBody(response.text, 'login');
  if (body.code !== 200 || !body.data) {
    throw new Error('login-failed');
  }
  const token = String(body.data.token || '');
  const userId = String(body.data.userId || '');
  if (!token || !userId) throw new Error('login-missing-fields');
  remember(token);
  remember(userId);
  const identity = pickIdentity(body.data);
  return { token, userId, identity, raw: body.data };
}

async function getPlanId(account, token, userId) {
  const sign = getSign(userId + 'student');
  const response = await httpRequest(apiUrl('/practice/plan/v3/getPlanByStu'), {
    method: 'POST',
    headers: {
      roleKey: 'student',
      authorization: token,
      sign,
      'Content-Type': 'application/json; charset=UTF-8',
      'User-Agent': account.ua,
      Accept: 'application/json',
    },
    body: JSON.stringify({ state: '' }),
  });
  log(`计划列表响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
  const body = parseJsonBody(response.text, 'plan');
  if (body.code !== 200 || !Array.isArray(body.data) || !body.data[0] || !body.data[0].planId) {
    throw new Error('plan-failed');
  }
  const planId = String(body.data[0].planId);
  remember(planId);
  return planId;
}

async function listAttendance(account, token) {
  const response = await httpRequest(apiUrl('/attendence/clock/v1/listSynchro'), {
    method: 'POST',
    headers: {
      'accept-encoding': 'gzip',
      'content-type': 'application/json;charset=UTF-8',
      rolekey: 'student',
      host: 'api.moguding.net:9000',
      authorization: token,
      'user-agent': account.ua,
      Accept: 'application/json',
    },
    body: JSON.stringify({
      t: encryptAES(String(Date.now()), AES_KEY),
    }),
  });
  log(`考勤同步响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
  const body = parseJsonBody(response.text, 'attendance');
  return body;
}

async function saveClock(account, token, userId, planId, type) {
  const text = account.type + type + planId + userId + account.address;
  const headers = {
    roleKey: 'student',
    authorization: token,
    sign: getSign(text),
    'content-type': 'application/json; charset=UTF-8',
    'user-agent': account.ua,
    Accept: 'application/json',
  };
  const data = {
    country: account.country,
    address: account.address,
    province: account.province,
    city: account.city,
    area: account.area,
    latitude: account.latitude,
    description: account.description,
    planId,
    type,
    device: account.type,
    longitude: account.longitude,
  };
  const response = await httpRequest(apiUrl('/attendence/clock/v2/save'), {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  });
  log(`打卡响应状态码：${response.statusCode}；长度：${response.text.length} 字节`);
  const body = parseJsonBody(response.text, 'clock');
  if (body.code !== 200) {
    throw new Error('clock-failed');
  }
  const createTime =
    body.data && body.data.createTime != null ? String(body.data.createTime) : '';
  return { createTime, type };
}

function decideClockAction(account, attendanceBody) {
  if (!account.signIn) {
    return { action: 'skip-disabled', detail: '账号已关闭打卡（signIn=false）' };
  }
  if (attendanceBody.code !== 200 || !Array.isArray(attendanceBody.data)) {
    throw new Error('attendance-failed');
  }
  if (!attendanceBody.data.length) {
    return { action: 'START', detail: '无历史考勤记录，准备上班打卡' };
  }
  const lastSign = attendanceBody.data[0];
  const lastSignType = String(lastSign.type || '');
  const lastMs = Number(lastSign.attendenceTimeLong || lastSign.attendanceTimeLong || 0);
  const lastSignTime = Number.isFinite(lastMs) && lastMs > 0 ? localDateText(lastMs) : '';
  const currentTime = localDateText(Date.now());

  if (account.multiple) {
    if (lastSignType === 'END') {
      return { action: 'START', detail: '多次打卡模式：上次为下班，本次上班' };
    }
    return { action: 'END', detail: '多次打卡模式：上次为上班或其他，本次下班' };
  }
  if (lastSignTime === currentTime && lastSignType === 'END') {
    return {
      action: 'already',
      detail: `今日已完成下班打卡（${lastSignTime}/${lastSignType}）`,
    };
  }
  if (lastSignTime === currentTime && lastSignType === 'START') {
    return { action: 'END', detail: '今日已上班打卡，准备下班打卡' };
  }
  return { action: 'START', detail: '今日尚未打卡，准备上班打卡' };
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

  let token = account.token;
  let userId = account.userId;
  let planId = account.planId;
  let identity = '';

  log(`账号 ${account.index} | 子阶段 1/4：登录或复用会话`);
  const stage1 = Date.now();
  if (token && userId && planId) {
    log(`账号 ${account.index} 使用行内 token/userId/planId 尝试跳过登录`);
  } else {
    const login = await loginAccount(account);
    token = login.token;
    userId = login.userId;
    identity = login.identity;
    if (identity) log(`账号 ${account.index} 官方身份：${identity}`);
    else log(`账号 ${account.index} 登录成功（未返回公开昵称，使用序号）`);
    planId = await getPlanId(account, token, userId);
  }
  log(`✅ 会话就绪 | 耗时 ${Date.now() - stage1}ms`);
  mark('success');

  log(`账号 ${account.index} | 子阶段 2/4：查询考勤`);
  const stage2 = Date.now();
  let attendance = await listAttendance(account, token);
  if (attendance.code === 401) {
    log('⚠️ token 失效，重新登录');
    const login = await loginAccount(account);
    token = login.token;
    userId = login.userId;
    identity = login.identity || identity;
    if (identity) log(`账号 ${account.index} 官方身份：${identity}`);
    planId = await getPlanId(account, token, userId);
    attendance = await listAttendance(account, token);
  }
  if (attendance.code !== 200) {
    throw new Error('attendance-failed');
  }
  log(`✅ 考勤同步成功 | 耗时 ${Date.now() - stage2}ms`);
  mark('success');

  log(`账号 ${account.index} | 子阶段 3/4：判定打卡类型`);
  const stage3 = Date.now();
  const decision = decideClockAction(account, attendance);
  log(decision.detail);
  if (decision.action === 'skip-disabled') {
    log(`⏭️ 已跳过打卡 | 耗时 ${Date.now() - stage3}ms`);
    mark('skipped');
    return { ok: true, skipped: true, stages, identity };
  }
  if (decision.action === 'already') {
    log(`☑️ 今日打卡已完成 | 耗时 ${Date.now() - stage3}ms`);
    mark('alreadyComplete');
    return { ok: true, alreadyComplete: true, stages, identity };
  }
  log(`✅ 判定完成：${decision.action} | 耗时 ${Date.now() - stage3}ms`);
  mark('success');

  log(`账号 ${account.index} | 子阶段 4/4：提交打卡`);
  const stage4 = Date.now();
  if (account.randomLocation) {
    log(`已启用坐标抖动（仅日志说明，不输出具体坐标）`);
  }
  const saved = await saveClock(account, token, userId, planId, decision.action);
  const timePart = saved.createTime ? `；完成时间：${saved.createTime}` : '';
  log(`✅ 打卡成功：类型 ${saved.type}${timePart} | 耗时 ${Date.now() - stage4}ms`);
  mark('success');
  return { ok: true, alreadyComplete: false, stages, identity, clockType: saved.type };
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
    delete env.MOGUDING_ACCOUNTS;
    delete env.MOGUDING_USER;
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
    delete env.MOGUDING_ACCOUNTS;
    delete env.MOGUDING_USER;
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
    'login-non-json': '登录接口返回非 JSON',
    'plan-non-json': '计划接口返回非 JSON',
    'attendance-non-json': '考勤接口返回非 JSON',
    'clock-non-json': '打卡接口返回非 JSON',
    'login-failed': '登录业务失败',
    'login-missing-fields': '登录未返回 token/userId',
    'plan-failed': '获取实习计划失败',
    'attendance-failed': '查询考勤失败',
    'clock-failed': '打卡业务失败或未返回成功码',
    'invalid-json': '账号 JSON 格式错误',
    'invalid-format': '账号行格式错误',
    'invalid-location-json': '位置 JSON 格式错误',
    'missing-credentials': '缺少手机号或密码',
    'missing-location': '缺少省市区地址或经纬度',
    'empty-line': '空账号行',
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
      if (!account.valid) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} ${reasonText(account.reason)}`);
      } else {
        log(
          `账号 ${account.index} 配置可读：省=${account.province || '-'}；打卡=${
            account.signIn ? '开' : '关'
          }；多次=${account.multiple ? '开' : '关'}；抖动=${account.randomLocation ? '开' : '关'}`
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
    log('阶段 2/3：账号打卡');
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
            `⏭️ DRY_RUN_OK：账号字段校验通过；未请求蘑菇钉 API，未写入本地文件，未验证真实业务`
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
          if (result.identity) log(`账号 ${account.index} 核对身份：${result.identity}`);
          log(
            `账号 ${account.index} 统计：总任务 ${result.stages.total} | 成功 ${result.stages.success} | 已完成 ${result.stages.alreadyComplete} | 跳过 ${result.stages.skipped} | 失败 ${result.stages.failure} | 耗时 ${Date.now() - began}ms`
          );
        }
      } catch (err) {
        summary.failedAccounts += 1;
        summary.tasks.total += 1;
        summary.tasks.failure += 1;
        const code = err && err.message ? String(err.message) : 'unknown';
        log(`❌ ${reasonText(code)}；未确认打卡成功`);
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
  encryptAES,
  getSign,
  decideClockAction,
  pickIdentity,
};
