// name: 什么值得买签到
// cron: 58 0 * * *
'use strict';
// SPDX-License-Identifier: MIT
// Copyright (c) 2023 Hex
// Source: hex-ci/smzdm_script, smzdm_checkin.js (MIT).
// Upstream attribution: agluo/ql-script-hub (SMZDM_checkin.py).
// MIT License: Copyright (c) 2023 Hex
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.
// Additional source: deeplee/personal-scripts, smzdm_checkin.py (MIT).
// Additional references: agluo/ql-script-hub, SMZDM_checkin.py (MIT).
// Lottery source: hex-ci/smzdm_script, smzdm_lottery.js (MIT).
// Additional source: OreosLab/checkinpanel, ck_smzdm.js (MIT).
// Original attribution: https://raw.githubusercontent.com/Tsukasa007/my_script/master/smzdm_mission.js
// 上游互动调度 29 0-23/8 * * *；可自定义本任务调度，不重复建立同产品签到任务。
// SMZDM_INTERACTION=none（默认）、value（好价点值）、article（好文点赞）、both（两者）。
// 每类最多 7 次；仅显式开启后执行，改变账号投票/点赞状态，不自动重试写入。
// 删除无奖励的去购买点击和收藏/取消切换，避免外站凭据传播及改变已有收藏。
// 互动开启时查询前后资产、未读消息和近期经验；无需发布公开文本。
// 参数：SMZDM_ACCOUNT 每行 sk|完整 Cookie；只在第一个 | 分割。
// 获取：登录自己的什么值得买客户端，从本人 /checkin 请求取得 sk 和 Cookie 的 sess。
// 默认 SMZDM_ACTION=checkin，保留签到 31 8 * * *；抽奖单独调度 20 8 * * *，设为 lottery。
// 抽奖兼容 SMZDM_COOKIE，每行完整 Cookie；从本人已登录网页请求头获取，不要公开。
// SMZDM_ACTION=all 显式同时执行；抽奖可能消耗机会或活动资产，请先核对官方活动规则。
// SMZDM_LOTTERY_LIFE=1 显式启用原上游未默认执行的生活频道；不自动重试抽奖。
// SMZDM_DRY_RUN=1 完全离线；QINGLONG_NOTIFY=0 关闭通知。
// SMZDM_TOKEN_MODE=sess（默认）保留维护接口；robot 显式启用上游 10.4.1 Robot Token 流程。
// 兼容 SMZDM_COOKIES 或 SMZDM_COOKIE 每行 Cookie，需提供同顺序逐行 SMZDM_SK，或 Cookie 自带 sk。
// 上游每日 30 9 * * * 可作为签到自定义调度；不要重复建立每日签到任务。
// 通知按青龙 → PushPlus → Server酱回退；PUSHPLUS_TOKEN、SENDKEY 可选且受 QINGLONG_NOTIFY 控制。
// Additional source: yuxian158/check, dailycheckin_scripts/ck_smzdm.py (MIT).
// 网页模式 SMZDM_TOKEN_MODE=web：SMZDM_ACCOUNT 每行 |完整 Cookie，无需 sk。
// 登录本人 www.smzdm.com，在开发者工具 Network 中复制 zhiyou.smzdm.com 请求的完整 Cookie。
// 网页模式仅执行原上游网页签到和资产查询；仍可显式组合抽奖/互动，不替代默认客户端奖励流程。
// 原上游网页签到调度 30 8 * * * 可自定义；默认继续使用维护任务 31 8 * * *，避免重复签到任务。
// 网页签到写入后重新查询本人账号的 has_checkin 与签到天数，验证失败不重试写入。
// Additional source: unitaryhighs/ql_sign_script, sign/smzdm.js (MIT).
// Original attribution: ql_sign_script : https://github.com/unitaryhighs/ql_sign_script
// 固定活动使用 SMZDM_ACTION=upstream-lottery 单独运行，每账号仅 POST 一次，不自动重试。
// 原调度 45 0 15 * * *（每日 15:00:45），保留独立活动运行时机；不加入 lottery 或 all。
// 兼容 SMZDM_COOKIE_LIST，每个非空行一个完整 Cookie；优先使用 SMZDM_ACCOUNT 的 |Cookie 格式。
// 固定活动可能已结束：HTTP 200 不代表成功，须同时验证 error_code=0 和非空 error_msg。
// Maintained standalone derivative; no private repository or external executable required.

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const NAME = '什么值得买签到';
const API = 'https://user-api.smzdm.com';
const APP_VERSION = '11.1.90';
const APP_REV = '1190';
const SIGN_KEY = 'apr1$AwP!wRRT$gJ/q.X24poeBInlUJC';
const TIMEOUT_MS = 15000;

const truthy = (v) => /^(1|true|yes|on)$/i.test(String(v || '').trim());
const now = () => new Date().toLocaleString('zh-CN', {hour12: false}).replaceAll('/', '-');
// 时间轴展示等价于 strftime 的 %H:%M:%S 格式。
const clock = () => new Date().toLocaleTimeString('zh-CN', {hour12: false});
const log = (message, branch = '◆') => console.log(`${clock()}  ${branch} ${message}`);

function cookieValue(cookie, name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return cookie.match(new RegExp(`(?:^|;\\s*)${escaped}=([^;]+)`))?.[1] || '';
}

function accountLines(value) {
  return String(value || '').split(/\r?\n/).map((v) => v.trim()).filter(Boolean);
}

function tokenMode(env = process.env) {
  const mode = String(env.SMZDM_TOKEN_MODE || 'sess').trim().toLowerCase();
  if (!['sess', 'robot', 'web'].includes(mode)) throw new Error('SMZDM_TOKEN_MODE 必须为 sess、robot 或 web');
  return mode;
}

function parseAccounts(env = process.env) {
  const action = taskAction(env);
  const needsSk = !['lottery', 'upstream-lottery'].includes(action) && tokenMode(env) !== 'web';
  interactionMode(env);
  const canonical = accountLines(env.SMZDM_ACCOUNT);
  if (!canonical.length) {
    // 抽奖保留维护目标原有 SMZDM_COOKIE 优先级；签到兼容上游复数变量优先级。
    const legacyCookies = action === 'upstream-lottery'
      ? (env.SMZDM_COOKIE_LIST || env.SMZDM_COOKIE || env.SMZDM_COOKIES)
      : action === 'lottery' ? (env.SMZDM_COOKIE || env.SMZDM_COOKIES || env.SMZDM_COOKIE_LIST)
      : (env.SMZDM_COOKIES || env.SMZDM_COOKIE || env.SMZDM_COOKIE_LIST);
    const cookies = accountLines(legacyCookies)
      .filter((line) => !line.startsWith('#'))
      .map((line) => line.replace(/^(['"])([\s\S]*)\1$/, '$2'));
    if (!cookies.length) throw new Error('未配置 SMZDM_ACCOUNT');
    const sks = accountLines(env.SMZDM_SK);
    if (sks.length && sks.length !== cookies.length && needsSk) {
      throw new Error('SMZDM_SK 行数必须与 Cookie 账号行数相同');
    }
    return cookies.map((cookie, i) => {
      const sk = sks[i] || cookieValue(cookie, 'sk');
      if (!cookieValue(cookie, 'sess')) return {configurationError: `第 ${i + 1} 行 Cookie 缺少 sess`};
      if (needsSk && !sk) return {configurationError: `第 ${i + 1} 行缺少本人 sk；请改用 SMZDM_ACCOUNT 或配置配套 SMZDM_SK`};
      return {sk, cookie};
    });
  }
  return canonical.map((line, i) => {
    const split = line.indexOf('|');
    if ((split < 1 && needsSk) || split < 0 || split === line.length - 1) return {configurationError: `invalid_SMZDM_ACCOUNT_format_at_line_${i + 1}：第 ${i + 1} 行应为 sk|Cookie`};
    const sk = line.slice(0, split).trim();
    const cookie = line.slice(split + 1).trim();
    if ((!sk && needsSk) || !cookieValue(cookie, 'sess')) return {configurationError: `第 ${i + 1} 行缺少 sk 或 sess`};
    return {sk, cookie};
  });
}

function requestProfile(cookie, override = '') {
  const overrideText = String(override).trim();
  const platform = cookieValue(cookie, 'device_smzdm').toLowerCase();
  const androidCookie = !['iphone', 'ios'].includes(platform);
  const version = (androidCookie && (cookieValue(cookie, 'device_smzdm_version') || cookieValue(cookie, 'v')))
    || overrideText.match(/smzdm_android_V([\d.]+)/i)?.[1]
    || APP_VERSION;
  const revision = (androidCookie && cookieValue(cookie, 'device_smzdm_version_code'))
    || overrideText.match(/\brv:([\d.]+)/i)?.[1]
    || APP_REV;
  return {
    revision,
    version,
    userAgent: overrideText || `smzdm_android_V${version} rv:${revision} (Android10.0;zh)smzdmapp`,
  };
}

const profile = requestProfile;

function signedForm(data, version) {
  const body = {weixin: 1, basic_v: 0, f: 'android', v: version, time: `${Math.round(Date.now() / 1000)}000`, ...data};
  const raw = Object.keys(body).filter((k) => body[k] !== '').sort()
    .map((k) => `${k}=${String(body[k]).replace(/\s+/g, '')}`).join('&');
  body.sign = crypto.createHash('md5').update(`${raw}&key=${SIGN_KEY}`).digest('hex').toUpperCase();
  return new URLSearchParams(body).toString();
}

function requestKey() {
  return Array.from(crypto.randomBytes(18), (b) => String(b % 10)).join('');
}

async function fetchLimited(url, options = {}, maxBytes = 1024 * 1024) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, {...options, redirect: 'error', signal: controller.signal});
    const size = Number(response.headers?.get?.('content-length') || 0);
    if (size > maxBytes) throw new Error('response_too_large');
    if (!response.body && typeof response.text === 'function') {
      const text = await response.text();
      if (Buffer.byteLength(text) > maxBytes) throw new Error('response_too_large');
      return {status: response.status, text};
    }
    const chunks = [];
    let bytes = 0;
    for await (const chunk of response.body) {
      bytes += chunk.byteLength;
      if (bytes > maxBytes) { controller.abort(); throw new Error('response_too_large'); }
      chunks.push(Buffer.from(chunk));
    }
    const text = Buffer.concat(chunks).toString('utf8');
    return {status: response.status, text};
  } finally { clearTimeout(timer); }
}

async function apiRequest(endpoint, account, data = {}, userAgentOverride = '') {
  const p = profile(account.cookie, userAgentOverride || process.env.SMZDM_USER_AGENT_APP);
  const response = await fetchLimited(`${API}${endpoint}`, {
    method: 'POST',
    headers: {
      Accept: '*/*', 'Accept-Language': 'zh-Hans-CN;q=1',
      'Content-Type': 'application/x-www-form-urlencoded',
      'User-Agent': p.userAgent, Cookie: account.cookie, request_key: requestKey(),
    },
    body: signedForm(data, p.version),
  });
  let payload = null;
  try { payload = JSON.parse(response.text); } catch { /* raw response is intentionally discarded */ }
  return {status: response.status, httpStatus: response.status, payload};
}

// 此模式严格采用三个 Python 来源一致的旧客户端签名，不猜测接口变更。
async function robotRequest(endpoint, account, fields = {}) {
  const body = {f: 'android', v: '10.4.1', weixin: 1, time: Date.now(), ...fields};
  const raw = Object.keys(body).sort().map((key) => `${key}=${body[key]}`).join('&');
  body.sign = crypto.createHash('md5').update(`${raw}&key=${SIGN_KEY}`).digest('hex').toUpperCase();
  const response = await fetchLimited(`${API}${endpoint}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded', Cookie: account.cookie,
      'User-Agent': 'smzdm_android_V10.4.1 rv:841 (22021211RC;Android12;zh)smzdmapp'},
    body: new URLSearchParams(body).toString(),
  });
  let payload = null;
  try { payload = JSON.parse(response.text); } catch { /* 不输出原始响应 */ }
  return {status: response.status, httpStatus: response.status, payload};
}

function safeCode(value) { return /^-?\d{1,10}$/.test(String(value)) ? String(value) : '缺失或未知'; }

function queryFailure(response) {
  if (!apiFailure(response)) return null;
  const status = response.httpStatus ?? response.status ?? null;
  const errorClass = [401, 403].includes(status) ? 'authentication_invalid'
    : status === 429 ? 'rate_limited'
      : (!status || status >= 500) ? 'network_error' : 'business_failure';
  return {
    class: errorClass,
    http_status: status,
    error_code: safeCode(response.payload?.error_code),
  };
}

function apiFailure(response) {
  if (response.status !== 200) return `HTTP_${response.status}`;
  if (!response.payload || typeof response.payload !== 'object') return '响应不是有效 JSON';
  if (String(response.payload.error_code) !== '0') {
    return `业务码_${safeCode(response.payload.error_code)}`;
  }
  return null;
}

function signResult(response) {
  if (!apiFailure(response)) return {ok: true, state: '签到成功'};
  const message = String(response.payload?.error_msg || response.payload?.error_message || '');
  if (response.status === 200 && /^(?:今日|今天)?(?:已签到|已经签到|重复签到)(?:[！!。\s]|$)|^already checked in[.!\s]*$/i.test(message)) return {ok: true, state: '今日已签到'};
  if (/验证码|验证|captcha/i.test(message)) return {ok: false, state: '需要人工验证'};
  if (/限制|风控|异常活动|restricted/i.test(message)) return {ok: false, state: '账号受限'};
  return {ok: false, state: apiFailure(response)};
}

async function accountOverview(account) {
  const response = await fetchLimited('https://zhiyou.smzdm.com/user/', {
    headers: {Cookie: account.cookie, 'User-Agent': profile(account.cookie).userAgent, Accept: 'text/html'},
  });
  if (response.status !== 200) throw new Error(`HTTP_${response.status}`);
  const identityMatch = response.text.match(/(?:user-name|nickname|user_name)[^>]*>\s*([^<]{1,80})</i)
    || response.text.match(/<a href="https:\/\/zhiyou\.smzdm\.com\/user">\s*([^<]+)\s*<\/a>/i)
    || response.text.match(/<title>\s*([^<]{1,80}?)(?:的个人主页|个人主页|_什么值得买)/i);
  const identity = identityMatch?.[1]?.replace(/&(?:nbsp|#160);/gi, ' ').replace(/&amp;/gi, '&').trim() || null;
  return {
    identity,
    level: response.text.match(/\/level\/(\d+)\.png/i)?.[1] || null,
    gold: response.text.match(/assets-gold[\s\S]*?assets-num[^>]*>([^<]+)/i)?.[1]?.trim() || null,
    silver: response.text.match(/assets-prestige[\s\S]*?assets-num[^>]*>([^<]+)/i)?.[1]?.trim() || null,
  };
}

async function monthlyExperience(account) {
  const month = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}`;
  let total = 0;
  for (let page = 1; page <= 3; page += 1) {
    const response = await fetchLimited(`https://zhiyou.m.smzdm.com/user/exp/ajax_log?page=${page}`, {
      headers: {Cookie: account.cookie, 'User-Agent': profile(account.cookie).userAgent, Accept: 'application/json'},
    });
    if (response.status !== 200) throw new Error(`HTTP_${response.status}`);
    let payload;
    try { payload = JSON.parse(response.text); } catch { throw new Error('响应不是有效 JSON'); }
    if (payload?.error_code !== undefined && String(payload.error_code) !== '0') throw new Error('经验业务失败');
    const rows = payload?.data?.rows;
    if (!Array.isArray(rows)) throw new Error('经验响应字段缺失');
    if (!rows.length) break;
    for (const row of rows) {
      const rowMonth = String(row?.creation_date || '').slice(0, 7);
      if (rowMonth === month) {
        const value = Number(row?.add_exp);
        if (row?.add_exp === undefined || !Number.isFinite(value)) throw new Error('经验数值无效');
        total += value;
      }
      else if (rowMonth && rowMonth < month) return total;
    }
  }
  return total;
}

// 只输出明确的业务展示字段；屏蔽凭据和手机号，保留普通公开身份。
function display(value, account) {
  let text = String(value ?? '未取得').replace(/<[^>]*>/g, '').replace(/[\r\n\x00-\x1f]/g, ' ');
  const values = account.cookie.split(';').map((part) => {
    const split = part.indexOf('=');
    const key = part.slice(0, split).trim();
    return split >= 0 && !['smzdm_id', 'device_smzdm', 'device_smzdm_version', 'device_smzdm_version_code', 'v'].includes(key)
      ? part.slice(split + 1).trim() : '';
  });
  for (const secret of [account.sk, account.cookie, ...values, ...(account.runtimeSecrets || [])]) {
    if (secret) text = text.split(secret).join('[凭据已隐藏]');
  }
  text = text.replace(/(?:cookie|token|sess|session|device_id|request_key|sign)\s*[:=]\s*[^\s;,]+/gi, '[凭据已隐藏]');
  return text.replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, '[手机号已隐藏]');
}

// 网页端 URL、GET 方法及字段来自 ck_smzdm.py；不猜测新业务码或接口。
async function webCurrent(account) {
  const response = await fetchLimited('https://zhiyou.smzdm.com/user/info/jsonp_get_current', {
    headers: {Cookie: account.cookie, Accept: 'application/json', Referer: 'https://www.smzdm.com/',
      'User-Agent': 'Mozilla/5.0'},
  });
  if (response.status !== 200) throw new Error('网页概览 HTTP 失败');
  const data = JSON.parse(response.text);
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('网页概览结构无效');
  if (data.error_code !== undefined && String(data.error_code) !== '0') throw new Error('网页概览业务失败');
  const identity = typeof data.nickname === 'string' && data.nickname.trim() ? data.nickname
    : (/^[1-9]\d*$/.test(String(data.smzdm_id || '')) ? String(data.smzdm_id) : null);
  if (!identity) throw new Error('网页账号身份未验证');
  const flag = data.checkin?.has_checkin;
  if (![true, false, 0, 1, '0', '1'].includes(flag)) throw new Error('网页签到状态缺失');
  const days = data.checkin?.daily_checkin_num;
  if (days === undefined || days === null || String(days).trim() === '' || !Number.isInteger(Number(days)) || Number(days) < 0) throw new Error('网页签到天数字段无效');
  return {identity, signed: [true, 1, '1'].includes(flag), days: Number(days),
    point: data.point, exp: data.exp, gold: data.gold, silver: data.silver,
    prestige: data.prestige, level: data.level ?? data.rank};
}

async function runWeb(account, report = () => {}) {
  const counts = {total: 0, success: 0, already: 0, skipped: 0, failed: 0};
  async function stage(name, action) {
    const started = Date.now();
    counts.total++;
    report(`[${counts.total}/3] ${name}`);
    try {
      const value = await action();
      counts.success++;
      report(`${name}：已验证，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '✅');
      return value;
    } catch (error) {
      counts.failed++;
      report(`${name}：${error?.name === 'AbortError' ? '请求超时' : 'HTTP、业务或响应字段校验失败'}，不自动重试写入，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '❌');
      return null;
    }
  }
  function overview(info) {
    report(`账号身份 ${display(info.identity, account)}，积分 ${display(info.point, account)}，经验 ${display(info.exp, account)}，金币 ${display(info.gold, account)}，碎银 ${display(info.silver, account)}，威望 ${display(info.prestige, account)}，等级 ${display(info.level, account)}，已经签到 ${info.days} 天`, '└─');
  }
  const before = await stage('网页账号与签到状态', () => webCurrent(account));
  if (before) overview(before);
  if (!before || before.signed) {
    counts.total += 2;
    counts.skipped++;
    if (before) counts.already++; else counts.skipped++;
    report('[2/3] 网页每日签到：' + (before ? '今日已签到，不重复写入' : '身份或状态未验证，停止写入') + '，用时 0.0 秒', before ? '☑️' : '⏭️');
    report('[3/3] 写入后核验：无需写入，跳过，用时 0.0 秒', '⏭️');
    return {ok: !!before, state: before ? '今日已签到' : '网页账号未验证', counts};
  }
  const signed = await stage('网页每日签到', async () => {
    const response = await fetchLimited('https://zhiyou.smzdm.com/user/checkin/jsonp_checkin', {
      headers: {Cookie: account.cookie, Accept: 'application/json', Referer: 'https://www.smzdm.com/', 'User-Agent': 'Mozilla/5.0'},
    });
    if (response.status !== 200) throw new Error('网页签到 HTTP 失败');
    const payload = JSON.parse(response.text);
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('网页签到结构无效');
    if (payload.error_code !== undefined && String(payload.error_code) !== '0') throw new Error('网页签到业务失败');
    const days = payload.data?.checkin_num;
    if (days === undefined || days === null || String(days).trim() === '' || !Number.isInteger(Number(days)) || Number(days) < 1) throw new Error('网页签到结果未验证');
    // 不输出原始响应或未经验证的错误消息。
    return {days: Number(days)};
  });
  const after = await stage('网页签到后状态核验', async () => {
    const info = await webCurrent(account);
    if (!info.signed || info.identity !== before.identity || info.days < before.days || (signed && info.days !== signed.days)) throw new Error('网页签到状态未确认');
    overview(info);
    return info;
  });
  return {ok: counts.failed === 0 && !!after, state: counts.failed ? '网页签到未全部验证' : '网页签到成功', counts};
}

async function runLive(account, userAgentOverride = '', report = () => {}, env = process.env) {
  const session = {sk: account.sk, token: cookieValue(account.cookie, 'sess')};
  const counts = {total: 0, success: 0, already: 0, skipped: 0, failed: 0};
  const robot = tokenMode(env) === 'robot';
  const stageTotal = robot ? 8 : 7;
  const steps = {};
  const warnings = [];
  async function stage(name, action) {
    const started = Date.now();
    counts.total++;
    report(`[${counts.total}/${stageTotal}] ${name}`);
    try {
      const value = await action();
      counts.success++;
      steps[name] = 'ok';
      report(`${name}：已验证，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '✅');
      return value;
    } catch (error) {
      counts.failed++;
      steps[name] = 'failed';
      const reason = error?.name === 'AbortError' ? '请求超时' : 'HTTP、业务或响应字段校验失败';
      warnings.push(`${name}：${reason}`);
      report(`${name}：${reason}，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '❌');
      return null;
    }
  }
  async function checked(endpoint, fields = session) {
    const response = await apiRequest(endpoint, account, fields, userAgentOverride);
    if (apiFailure(response)) throw new Error('业务失败');
    if (!response.payload?.data || typeof response.payload.data !== 'object') throw new Error('字段缺失');
    return response.payload.data;
  }
  let robotToken = null;
  if (robot) {
    robotToken = await stage('获取 Robot Token', async () => {
      const response = await robotRequest('/robot/token', account);
      if (apiFailure(response) || typeof response.payload?.data?.token !== 'string' || !response.payload.data.token.trim()) throw new Error('Token 未验证');
      return response.payload.data.token;
    });
    if (robotToken) account.runtimeSecrets = [robotToken];
  }
  const signed = await stage('每日签到', async () => {
    if (robot && !robotToken) throw new Error('Token 未取得，不提交签到');
    const response = robot
      ? await robotRequest('/checkin', account, {sk: account.sk, token: robotToken})
      : await apiRequest('/checkin', account, {...session, touchstone_event: '', captcha: ''}, userAgentOverride);
    const result = signResult(response);
    if (!result.ok) throw new Error('签到失败');
    return {...result, data: response.payload?.data};
  });
  if (signed?.state === '今日已签到') { counts.success--; counts.already++; }
  if (signed?.data) report(`签到天数 ${display(signed.data.daily_num, account)}，金币 ${display(signed.data.cgold, account)}，碎银 ${display(signed.data.pre_re_silver, account)}，补签卡 ${display(signed.data.cards, account)}`, '└─');
  let reward = null, view = null, extra = '无需领取';
  if (signed) {
    reward = await stage('普通签到奖励', async () => {
      const data = robot ? await (async () => {
        const response = await robotRequest('/checkin/all_reward', account, {sk: account.sk, token: robotToken});
        if (apiFailure(response) || !response.payload?.data || typeof response.payload.data !== 'object') throw new Error('奖励未验证');
        return response.payload.data;
      })() : await checked('/checkin/all_reward');
      if (!data.normal_reward || typeof data.normal_reward !== 'object') throw new Error('字段缺失');
      const normal = data.normal_reward;
      report(`奖励 ${display(normal.reward_add?.title, account)}：${display(normal.reward_add?.content, account)}；连续签到 ${display(normal.sub_title, account)}`, '└─');
      report(`礼包 ${display(normal.gift?.title, account)}：${display(normal.gift?.content_str ?? normal.gift?.sub_content, account)}`, '└─');
      return data;
    });
    view = await stage('连续签到状态', async () => {
      const data = await checked('/checkin/show_view_v2');
      if (!Array.isArray(data.rows)) throw new Error('字段缺失');
      return data;
    });
    const available = view?.rows.find((item) => String(item?.cell_type) === '18001')?.cell_data?.checkin_continue?.continue_checkin_reward_show;
    if (available === true || available === 1 || available === '1') {
      const claimed = await stage('额外签到奖励', async () => {
        const data = await checked('/checkin/extra_reward');
        report(`${display(data.title, account)}：${display(data.gift?.content, account)}`, '└─');
        return data;
      });
      extra = claimed ? '领取成功' : '领取失败';
    } else {
      counts.total++; counts.skipped++;
      extra = view ? '无需领取' : '状态未验证，跳过领取';
      report(`[${counts.total}/${stageTotal}] 额外签到奖励：${extra}，用时 0.0 秒`, '⏭️');
    }
  } else {
    counts.total += 3; counts.skipped += 3;
    report(`[${robot ? '3-5' : '2-4'}/${stageTotal}] 奖励流程：签到失败，跳过奖励请求，用时 0.0 秒`, '⏭️');
  }
  const vip = await stage('会员详情', async () => {
    const data = await checked('/vip', {token: session.token});
    if (!data.vip || typeof data.vip !== 'object') throw new Error('字段缺失');
    report(`总经验 ${display(data.vip.exp_current, account)}，值会员等级 ${display(data.vip.exp_level, account)}，等级经验 ${display(data.vip.exp_current_level, account)}，有效期 ${display(data.vip.exp_level_expire, account)}`, '└─');
    return data.vip;
  });
  const overview = await stage('账号概览', async () => {
    const data = await accountOverview(account);
    if (!data.identity && !data.level && !data.gold && !data.silver) throw new Error('字段缺失');
    report(`账号身份 ${display(data.identity ?? '接口未返回', account)}，等级 ${display(data.level, account)}，金币 ${display(data.gold, account)}，碎银 ${display(data.silver, account)}`, '└─');
    return data;
  });
  const experience = await stage('本月经验', async () => {
    const value = await monthlyExperience(account);
    report(`本月经验（最近三页） ${value}`, '└─'); return value;
  });
  return {ok: counts.failed === 0, state: counts.failed ? '部分任务失败' : signed.state, extra, overview, experience, vip, warnings, counts, steps,
    sign_status: signed?.state ?? '签到失败', sign_days: signed?.data?.daily_num ?? null,
    reward_status: reward ? 'confirmed' : 'pending_confirmation',
    extra_reward_status: extra === '领取成功' ? 'confirmed' : (extra === '无需领取' ? 'not_available' : 'pending_confirmation')};
}

// 保留维护目标的公开接口与结果字段，失败闭合。
async function runAccount(account, userAgentOverride = '') {
  const result = await runLive(account, userAgentOverride);
  return {execution: result.ok ? 'ok' : 'failed', sign_status: result.sign_status, sign_days: result.sign_days,
    reward_status: result.reward_status, extra_reward_status: result.extra_reward_status,
    ...(result.ok ? {} : {error_class: 'business_failure'})};
}


function taskAction(env = process.env) {
  const action = String(env.SMZDM_ACTION || 'checkin').trim().toLowerCase();
  if (!['checkin', 'lottery', 'all', 'upstream-lottery'].includes(action)) throw new Error('SMZDM_ACTION 必须为 checkin、lottery、all 或 upstream-lottery');
  return action;
}

// JSONP 不使用 eval。未知业务码、缺失活动和失效页面均失败闭合。
function lotteryPayload(text, callback) {
  const escaped = callback.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = String(text).trim().match(new RegExp(`^${escaped}\\s*\\(([\\s\\S]*)\\)\\s*;?$`));
  if (!match) throw new Error('抽奖 JSONP 无效');
  const data = JSON.parse(match[1]);
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('抽奖响应无效');
  return data;
}

function activityId(text, life = false) {
  const normalized = String(text).replace(/\\"/g, '"').replace(/&quot;/g, '"');
  const match = life
    ? normalized.match(/name\s*=\s*["']lottery_activity_id["']\s+value\s*=\s*["']([a-zA-Z0-9_-]+)["']/i)
    : normalized.match(/"hashId"\s*:\s*"([a-zA-Z0-9_-]+)"/i);
  if (!match || match[1].length > 128) throw new Error('未取得活动 ID');
  return match[1];
}

async function runLottery(account, env, report = () => {}) {
  const campaigns = [
    {name: '会员转盘一', url: 'https://m.smzdm.com/topic/bwrzf5/516lft'},
    {name: '会员转盘二', url: 'https://m.smzdm.com/topic/zhyzhuanpan/cjzp/'},
  ];
  if (truthy(env.SMZDM_LOTTERY_LIFE)) campaigns.push({name: '生活频道转盘', url: 'https://m.smzdm.com/zhuanti/life/choujiang/', life: true});
  const counts = {total: 0, success: 0, already: 0, skipped: 0, failed: 0};
  const headers = {Cookie: account.cookie, 'User-Agent': profile(account.cookie, env.SMZDM_USER_AGENT_APP).userAgent,
    'x-requested-with': 'com.smzdm.client.android', Referer: 'https://m.smzdm.com/'};
  for (const campaign of campaigns) {
    let id;
    let started = Date.now();
    counts.total++;
    report(`[${counts.total}/${campaigns.length * 2}] ${campaign.name}：查询活动`);
    try {
      const response = await fetchLimited(campaign.url, {method: 'GET', headers});
      if (response.status !== 200) throw new Error('HTTP 失败');
      id = activityId(response.text, campaign.life);
      counts.success++;
      report(`${campaign.name}：活动 ID 已取得，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '✅');
    } catch {
      counts.failed++; counts.total++; counts.skipped++;
      report(`${campaign.name}：活动查询或字段校验失败，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '❌');
      report(`[${counts.total}/${campaigns.length * 2}] ${campaign.name}：跳过抽奖，用时 0.0 秒`, '⏭️');
      continue;
    }
    // 保留上游请求间隔，避免快速连续抽奖。
    await new Promise((resolve) => setTimeout(resolve, 3000 + crypto.randomInt(7001)));
    counts.total++;
    started = Date.now();
    report(`[${counts.total}/${campaigns.length * 2}] ${campaign.name}：执行一次抽奖`);
    try {
      const callback = `jQuery34107538452897131465_${Date.now()}`;
      const url = new URL('https://zhiyou.smzdm.com/user/lottery/jsonp_draw');
      url.search = new URLSearchParams({active_id: id, callback}).toString();
      const response = await fetchLimited(url, {method: 'GET', headers});
      if (response.status !== 200) throw new Error('HTTP 失败');
      const data = lotteryPayload(response.text, callback);
      if (String(data.error_code) !== '0') {
        report(`${campaign.name}：业务未成功，业务码 ${safeCode(data.error_code)}`, '❌');
        throw new Error('业务失败');
      }
      if (typeof data.error_msg !== 'string' || !data.error_msg.trim()) throw new Error('结果字段缺失');
      counts.success++;
      report(`${campaign.name}：抽奖已验证，${display(data.error_msg, account)}，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '✅');
    } catch {
      counts.failed++;
      report(`${campaign.name}：抽奖未验证成功，不自动重试，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '❌');
    }
    if (campaign !== campaigns[campaigns.length - 1]) await new Promise((resolve) => setTimeout(resolve, 5000 + crypto.randomInt(10001)));
  }
  return {ok: counts.failed === 0, state: counts.failed ? '抽奖任务失败' : '抽奖全部已验证', counts};
}

// 上游固定活动与动态会员转盘没有同活动证据，保持独立开关、方法与时机。
async function runUpstreamLottery(account, env, report = () => {}) {
  const started = Date.now();
  const counts = {total: 1, success: 0, already: 0, skipped: 0, failed: 0};
  report('[1/1] 固定活动：执行一次抽奖');
  try {
    const response = await fetchLimited('https://zhiyou.smzdm.com/user/lottery/jsonp_draw?active_id=ljX8qVlEA7', {
      method: 'POST',
      headers: {
        Accept: '*/*', Cookie: account.cookie, 'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
        'Content-Type': 'application/json', Referer: 'https://m.smzdm.com/',
        'User-Agent': env.SMZDM_USER_AGENT_APP || 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/smzdm 10.4.6 rv:130.1 (iPhone 13; iOS 15.6; zh_CN)/iphone_smzdmapp/10.4.6/wkwebview/jsbv_1.0.0',
      },
      body: JSON.stringify({}),
    });
    if (response.status !== 200) throw new Error('抽奖 HTTP 失败');
    const data = JSON.parse(response.text);
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('抽奖响应无效');
    // 可用的官方公开身份原样展示；凭据和手机号仍由统一脱敏函数处理。
    const identity = data.data?.nickname ?? data.nickname ?? data.data?.username ?? data.username
      ?? data.data?.display_name ?? data.display_name ?? data.data?.smzdm_id ?? data.smzdm_id;
    if (typeof identity === 'string' || typeof identity === 'number') report(`账号身份 ${display(identity, account)}`, '└─');
    if (String(data.error_code) !== '0') {
      report(`固定活动：业务未成功，业务码 ${safeCode(data.error_code)}`, '❌');
      throw new Error('抽奖业务失败');
    }
    if (typeof data.error_msg !== 'string' || !data.error_msg.trim()) throw new Error('结果字段缺失');
    counts.success++;
    report(`固定活动：抽奖已验证，${display(data.error_msg, account)}，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '✅');
  } catch {
    counts.failed++;
    report(`固定活动：HTTP、业务或响应字段校验失败；活动可能失效，不自动重试，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '❌');
  }
  return {ok: counts.failed === 0, state: counts.failed ? '固定活动抽奖失败' : '固定活动抽奖已验证', counts};
}

function interactionMode(env = process.env) {
  const mode = String(env.SMZDM_INTERACTION || 'none').trim().toLowerCase();
  if (!['none', 'value', 'article', 'both'].includes(mode)) throw new Error('SMZDM_INTERACTION 必须为 none、value、article 或 both');
  return mode;
}

async function webAssets(account) {
  const callback = `smzdmInfo_${Date.now()}`;
  const url = new URL('https://zhiyou.smzdm.com/user/info/jsonp_get_current');
  url.search = new URLSearchParams({with_avatar_ornament: '1', callback, _: String(Date.now())}).toString();
  const response = await fetchLimited(url, {headers: {Cookie: account.cookie,
    'User-Agent': profile(account.cookie).userAgent, Referer: 'https://zhiyou.smzdm.com/user/'}});
  if (response.status !== 200) throw new Error('概览 HTTP 失败');
  const data = lotteryPayload(response.text, callback);
  if (!data.smzdm_id || String(data.smzdm_id) === '0' || typeof data.nickname !== 'string' || !data.nickname.trim()) throw new Error('账号身份未验证');
  const assets = {};
  for (const key of ['point', 'exp', 'gold', 'silver']) {
    if (data[key] === null || data[key] === undefined || String(data[key]).trim() === '' || !Number.isFinite(Number(data[key]))) throw new Error('资产字段缺失');
    assets[key] = Number(data[key]);
  }
  const unread = data.unread?.notice?.num;
  if (unread === undefined || unread === null || !Number.isFinite(Number(unread))) throw new Error('消息字段缺失');
  return {identity: data.nickname, level: data.vip_level, checkin: data.checkin?.has_checkin, unread: Number(unread), ...assets};
}

async function recentExperience(account) {
  const response = await fetchLimited('https://zhiyou.smzdm.com/user/exp/', {
    headers: {Cookie: account.cookie, 'User-Agent': profile(account.cookie).userAgent}});
  if (response.status !== 200) throw new Error('经验 HTTP 失败');
  const text = response.text;
  // 登录身份与经验资产必须存在，不能把登录页或空页面判为成功。
  if (!/info-stuff-nickname/i.test(text) || !/assets-num/i.test(text)) throw new Error('经验页面未验证');
  const times = [...text.matchAll(/<div\s+class=['"]scoreLeft['"][^>]*>([\s\S]*?)<\/div>/gi)];
  const details = [...text.matchAll(/<div\s+class=['"]scoreRight ellipsis['"][^>]*>([\s\S]*?)<\/div>/gi)];
  if (times.length !== details.length) throw new Error('经验记录字段不匹配');
  const assets = [...text.matchAll(/assets-num[^>]*>([^<]*)</gi)].map((m) => Number(m[1].trim().replaceAll(',', '')));
  if (assets.length < 4 || !Number.isFinite(assets[1])) throw new Error('总经验字段缺失');
  return {total: assets[1], rows: times.slice(0, 20).map((m, i) => ({time: m[1], detail: details[i][1]}))};
}

async function runInteraction(account, env, report = () => {}) {
  const mode = interactionMode(env);
  const counts = {total: 0, success: 0, already: 0, skipped: 0, failed: 0};
  async function stage(name, action) {
    const started = Date.now();
    counts.total++;
    report(`[${counts.total}] ${name}`);
    try {
      const value = await action();
      if (value?.already) counts.already++; else counts.success++;
      report(`${name}：${value?.already ? '已完成' : '已验证'}，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, value?.already ? '☑️' : '✅');
      return value;
    } catch {
      counts.failed++;
      report(`${name}：HTTP、业务或响应字段校验失败，未计为成功，用时 ${((Date.now() - started) / 1000).toFixed(1)} 秒`, '❌');
      return null;
    }
  }
  const before = await stage('互动前资产与身份', () => webAssets(account));
  if (before) report(`账号身份 ${display(before.identity, account)}，等级 ${display(before.level, account)}，积分 ${before.point}，金币 ${before.gold}，碎银 ${before.silver}，未读消息 ${before.unread}，签到状态 ${display(before.checkin, account)}`, '└─');
  const beforeExp = await stage('互动前总经验', () => recentExperience(account));
  if (!before) {
    report('账号身份未验证，停止互动写入', '⏭️');
    return {ok: false, state: '互动账号未验证', counts};
  }
  const kinds = [];
  if (['value', 'both'].includes(mode)) kinds.push({name: '好价点值', url: 'https://faxian.smzdm.com/', channel: '3', pattern: /https?:\/\/www\.smzdm\.com\/p\/(\d+)/g});
  if (['article', 'both'].includes(mode)) kinds.push({name: '好文点赞', url: 'https://post.smzdm.com/', channel: '11', pattern: /data-article=["'](\d+)["']\s+data-type=["']zan["']/g});
  for (const kind of kinds) {
    const ids = await stage(`${kind.name}列表`, async () => {
      // 公共列表不携带账号凭据。
      const response = await fetchLimited(kind.url, {headers: {'User-Agent': profile(account.cookie).userAgent}});
      if (response.status !== 200) throw new Error('列表 HTTP 失败');
      const ids = [...new Set([...response.text.matchAll(kind.pattern)].map((m) => m[1]))].slice(0, 7);
      if (!ids.length) throw new Error('列表为空或结构改变');
      return ids;
    });
    if (!ids) continue;
    for (let i = 0; i < ids.length; i++) {
      await stage(`${kind.name} ${i + 1}/${ids.length}`, async () => {
        const response = await fetchLimited('https://zhiyou.smzdm.com/user/rating/ajax_add', {
          method: 'POST', headers: {Cookie: account.cookie, 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            Accept: 'application/json, text/javascript, */*; q=0.01', 'User-Agent': profile(account.cookie).userAgent,
            Origin: new URL(kind.url).origin, Referer: kind.url},
          body: new URLSearchParams({article_id: ids[i], channel_id: kind.channel, rating: '1', client_type: 'PC',
            event_key: '点值', otype: kind.channel === '3' ? '值' : '点赞', aid: ids[i], p: kind.channel === '3' ? '16' : '2',
            cid: kind.channel === '3' ? '2' : '11', source: '无', atp: kind.channel === '3' ? '3' : '76', tagID: '无',
            sourcePage: kind.url, sourceMode: '无'}).toString(),
        });
        if (response.status !== 200) throw new Error('互动 HTTP 失败');
        const data = JSON.parse(response.text);
        if (String(data.error_code) === '0') return {already: false};
        if (String(data.error_code) === '1' && /^(已喜欢|已点值|已经点值|重复点值)[！!。\s]*$/.test(String(data.error_msg || ''))) return {already: true};
        throw new Error('互动业务失败');
      });
      if (i < ids.length - 1) await new Promise((resolve) => setTimeout(resolve, 3100));
    }
  }
  await new Promise((resolve) => setTimeout(resolve, 3000));
  const after = await stage('互动后资产与消息', () => webAssets(account));
  if (after) {
    report(`账号身份 ${display(after.identity, account)}，等级 ${display(after.level, account)}，未读消息 ${after.unread}，签到状态 ${display(after.checkin, account)}`, '└─');
    report(`积分 ${after.point}（变化 ${after.point - before.point}），金币 ${after.gold}（变化 ${after.gold - before.gold}），碎银 ${after.silver}（变化 ${after.silver - before.silver}）`, '└─');
  }
  const afterExp = await stage('互动后总经验与近期记录', () => recentExperience(account));
  if (afterExp) {
    report(`总经验 ${afterExp.total}${beforeExp ? `（变化 ${afterExp.total - beforeExp.total}）` : ''}；经验记录可能延迟`, '└─');
    for (const row of afterExp.rows) report(`${display(row.time, account)} ${display(row.detail, account)}`, '└─');
  }
  return {ok: counts.failed === 0, state: counts.failed ? '部分互动任务失败' : '互动任务已验证', counts};
}

function notifier(env = process.env) {
  const roots = [env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  for (const root of roots) {
    const file = path.join(root, 'sendNotify.js');
    if (!fs.existsSync(file)) continue;
    try {
      const loaded = require(file);
      const send = loaded.sendNotify || loaded;
      if (typeof send === 'function') return send;
    } catch { /* notification cannot alter the business result */ }
  }
  return null;
}

async function sendNotification(summary, env = process.env) {
  if (env.QINGLONG_NOTIFY !== undefined && /^(0|false|no|off)$/i.test(env.QINGLONG_NOTIFY.trim())) return '已关闭';
  if (truthy(env.SMZDM_DRY_RUN)) return '离线预演：已生成脱敏通知，未调用联网组件';
  const content = `账号总数 ${summary.accounts_total}，成功 ${summary.accounts_success}，失败 ${summary.accounts_failed}。模式 ${summary.mode}，状态 ${summary.execution}\nBENEFIT_SUMMARY=${JSON.stringify(summary)}`;
  const outcomes = [];
  const send = notifier(env);
  if (send) {
    try {
      let timer;
      try {
        const delivered = await Promise.race([Promise.resolve().then(() => send(NAME, content)),
          new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('通知超时')), TIMEOUT_MS); })]);
        if (delivered === false) throw new Error('通知失败');
      } finally { clearTimeout(timer); }
      return '发送成功（青龙）';
    } catch { outcomes.push('青龙发送失败'); }
  } else outcomes.push('通知组件不可用');
  if (String(env.PUSHPLUS_TOKEN || '').trim()) {
    try {
      const response = await fetchLimited('https://www.pushplus.plus/send', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token: env.PUSHPLUS_TOKEN.trim(), title: NAME, content}),
      });
      if (response.status !== 200 || Number(JSON.parse(response.text)?.code) !== 200) throw new Error('推送未确认');
      return '发送成功（PushPlus）';
    } catch { outcomes.push('PushPlus 发送失败'); }
  }
  if (String(env.SENDKEY || '').trim()) {
    try {
      const response = await fetchLimited(`https://sctapi.ftqq.com/${encodeURIComponent(env.SENDKEY.trim())}.send`, {
        method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams({title: NAME, desp: content}).toString(),
      });
      if (response.status !== 200 || String(JSON.parse(response.text)?.code) !== '0') throw new Error('推送未确认');
      return '发送成功（Server酱）';
    } catch { outcomes.push('Server酱发送失败'); }
  }
  return outcomes.join('；');
}

function emitResult(result) { console.log(`BENEFIT_RESULT=${JSON.stringify(result)}`); }

async function finish(summary, code, started, env) {
  console.log(`BENEFIT_SUMMARY=${JSON.stringify(summary)}`);
  const notification = await sendNotification(summary, env);
  const elapsed = Number(((Date.now() - started) / 1000).toFixed(1));
  const complete = {...summary, elapsed_seconds: elapsed, notification};
  log('生成任务总结');
  console.log(`\n${'═'.repeat(24)} 任务统计 ${'═'.repeat(24)}`);
  console.log(`账号统计  总数 ${summary.accounts_total} │ 成功 ${summary.accounts_success} │ 失败 ${summary.accounts_failed}`);
  console.log(`子任务统计  总数 ${summary.tasks_total} │ 成功 ${summary.tasks_success} │ 已完成 ${summary.tasks_already} │ 跳过 ${summary.tasks_skipped} │ 失败 ${summary.tasks_failed}`);
  console.log(`通知状态  ${notification}`);
  console.log(`总耗时    ${elapsed.toFixed(1)} 秒`);
  console.log(`完成时间  ${now()}`);
  console.log(`最终状态  ${code === 0 ? (summary.mode === 'dry-run' ? '预演通过' : '全部成功') : '失败'}`);
  console.log('═'.repeat(62));
  console.log(`TASK_SUMMARY=${JSON.stringify(complete)}`);
  process.exitCode = code;
}

async function run(env = process.env) {
  const started = Date.now();
  const dryRun = truthy(env.SMZDM_DRY_RUN);
  let accounts, action;
  try { action = taskAction(env); accounts = parseAccounts(env); } catch (error) {
    console.log(NAME); console.log('═'.repeat(62));
    console.log(`开始时间  ${now()}\n运行模式  配置检查\n账号数量  0`);
    log(`[1/1] 参数校验失败：${error.message}`, '❌');
    return finish({execution: 'failed', mode: 'configuration', accounts_total: 0, accounts_success: 0, accounts_failed: 0, accounts_pending_confirmation: 0, tasks_total: 1, tasks_success: 0, tasks_already: 0, tasks_skipped: 0, tasks_failed: 1}, 2, started, env);
  }
  console.log(NAME); console.log('═'.repeat(62));
  console.log(`开始时间  ${now()}\n运行模式  ${dryRun ? '离线预演' : '正式执行'}\n账号数量  ${accounts.length}`);
  console.log('═'.repeat(62));
  const results = [];
  for (let i = 0; i < accounts.length; i += 1) {
    const label = `账号 ${String(i + 1).padStart(2, '0')}`;
    const accountStarted = Date.now();
    console.log('');
    log(`${label}：[1/4] 校验账号参数`); log(`${label}：参数检查完成（内容已隐藏），用时 0.0 秒`, '└─');
    let result;
    if (accounts[i].configurationError) {
      result = {ok: false, configurationError: true, state: accounts[i].configurationError, counts: {total: 7, success: 0, already: 0, skipped: 6, failed: 1}};
      log(`${label}：${result.state}`, '❌');
    } else if (dryRun) {
      log(`${label}：[2/4] 规划签到请求`); log(`${label}：离线预演，未发出网络请求，用时 0.0 秒`, '⏭️');
      log(`${label}：[3/4] 规划奖励、概览与经验查询`); log(`${label}：离线预演，未发出网络请求，用时 0.0 秒`, '⏭️');
      const interactionPlan = interactionMode(env) === 'none' ? 0 : (interactionMode(env) === 'both' ? 20 : 12);
      const planned = action === 'upstream-lottery' ? interactionPlan + 1 : interactionPlan + (action === 'lottery' ? 0 : (tokenMode(env) === 'web' ? 3 : (tokenMode(env) === 'robot' ? 8 : 7))) + (action === 'checkin' ? 0 : (truthy(env.SMZDM_LOTTERY_LIFE) ? 6 : 4));
      log(`${label}：互动开关 ${interactionMode(env)}（离线预演不查询列表、不提交互动）`, '└─');
      if (action === 'upstream-lottery') log(`${label}：固定活动仅规划一次 POST，不访问网络、不执行签到或会员转盘`, '⏭️');
      log(`${label}：任务开关 ${action}，计划 ${planned} 个步骤上限（互动按实际列表长度执行）；抽奖仅在显式选择后执行`, '└─');
      result = {ok: true, state: '预演通过', planned_requests: planned,
        counts: {total: planned + 1, success: 1, already: 0, skipped: planned, failed: 0}};
    } else {
      log(`${label}：[2/4] 执行签到`);
      try {
        const report = (message, icon) => log(`${label}：${message}`, icon);
        if (action === 'upstream-lottery') result = await runUpstreamLottery(accounts[i], env, report);
        else if (action === 'lottery') result = await runLottery(accounts[i], env, report);
        else {
          result = tokenMode(env) === 'web' ? await runWeb(accounts[i], report)
            : await runLive(accounts[i], env.SMZDM_USER_AGENT_APP, report, env);
          if (action === 'all') {
            const lottery = await runLottery(accounts[i], env, report);
            result.ok = result.ok && lottery.ok;
            result.state = result.ok ? '签到与抽奖均已验证' : '部分任务失败';
            for (const key of Object.keys(result.counts)) result.counts[key] += lottery.counts[key];
          }
        }
        if (interactionMode(env) !== 'none') {
          const interaction = await runInteraction(accounts[i], env, report);
          result.ok = result.ok && interaction.ok;
          if (!result.ok) result.state = '部分任务失败';
          for (const key of Object.keys(result.counts)) result.counts[key] += interaction.counts[key];
        }
      } catch (error) {
        result = {ok: false, state: error?.name === 'AbortError' ? '请求超时' : '网络或处理异常'};
      }
      log(`${label}：${result.state}`, result.ok ? '✅' : '❌');
      log(`${label}：[3/4] 核对奖励、概览与本月经验`);
      for (const warning of result.warnings || []) log(`${label}：${warning}`, '⚠️');
    }
    log(`${label}：[4/4] 生成账号结果`);
    const tasksTotal = result.counts?.total ?? 7;
    const failed = result.counts?.failed ?? (result.ok ? 0 : 1);
    const already = result.counts?.already ?? (result.state === '今日已签到' ? 1 : 0);
    const skipped = result.counts?.skipped ?? (dryRun ? 6 : (result.ok ? 0 : 6));
    const succeeded = tasksTotal - failed - already - skipped;
    emitResult({account: i + 1, execution: result.ok ? 'ok' : 'failed', status: result.state});
    log(`${label}：总任务 ${tasksTotal} │ 成功 ${succeeded} │ 已完成 ${already} │ 跳过 ${skipped} │ 失败 ${failed} │ 用时 ${((Date.now() - accountStarted) / 1000).toFixed(1)} 秒`, '└─');
    results.push({...result, tasksTotal, tasksSucceeded: succeeded, tasksAlready: already, tasksSkipped: skipped, tasksFailed: failed});
  }
  const failures = results.filter((r) => !r.ok).length;
  const skipped = results.reduce((n, r) => n + r.tasksSkipped, 0);
  const totalTasks = results.reduce((n, r) => n + r.tasksTotal, 0);
  const already = results.reduce((n, r) => n + r.tasksAlready, 0);
  const succeeded = results.reduce((n, r) => n + r.tasksSucceeded, 0);
  const failedTasks = results.reduce((n, r) => n + r.tasksFailed, 0);
  return finish({
    execution: failures ? 'failed' : 'ok', mode: dryRun ? 'dry-run' : 'live',
    accounts_total: accounts.length, accounts_success: accounts.length - failures, accounts_failed: failures,
    accounts_pending_confirmation: results.filter((r) => r.reward_status === 'pending_confirmation' || r.extra_reward_status === 'pending_confirmation').length,
    tasks_total: totalTasks, tasks_success: succeeded,
    tasks_already: already, tasks_skipped: skipped, tasks_failed: failedTasks,
  }, failures ? (results.some((r) => r.configurationError) ? 2 : 1) : 0, started, env);
}

if (require.main === module) run().catch(async () => {
  const started = Date.now();
  await finish({execution: 'failed', mode: 'live', accounts_total: 0, accounts_success: 0, accounts_failed: 1, tasks_total: 1, tasks_success: 0, tasks_already: 0, tasks_skipped: 0, tasks_failed: 1}, 1, started, process.env);
});

module.exports = {runUpstreamLottery, webCurrent, runWeb, interactionMode, webAssets, recentExperience, runInteraction, tokenMode, robotRequest, fetchLimited, runLive, display, activityId, lotteryPayload, taskAction, runLottery, accountLines, apiFailure, cookieValue, parseAccounts, profile, queryFailure, requestProfile, run, runAccount, signedForm, signResult, sendNotification};
