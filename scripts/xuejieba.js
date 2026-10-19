#!/usr/bin/env node
// name: 学姐吧每日签到
// cron: 0 50 11 * * *
/*
 * name: 学姐吧签到
 * cron: 0 50 11 * * *
 *
 * ql_sign_script : https://github.com/unitaryhighs/ql_sign_script
 * Source: sign/xuejieba.js (MIT License)
 * SPDX-License-Identifier: MIT
 *
 * 必填环境变量：XUEJIEBA_COOKIE_LIST
 * 每行一个账号 Cookie，Cookie 内必须包含 b2_token，例如字段形式为：
 * gg_info=<值>; b2_token=<值>
 * 请登录学姐吧后，从浏览器开发者工具的网络请求标头中复制完整 Cookie。
 * 不要把真实 Cookie 写入脚本、日志或公开仓库。
 *
 * 可选环境变量：
 * XUEJIEBA_DRY_RUN=1       完全断网预演
 * XUEJIEBA_TIMEOUT_MS=10000 请求超时毫秒数（1000~60000）
 * QINGLONG_NOTIFY=auto     通知开关：auto/1/0 等
 * QINGLONG_NOTIFY_SCRIPTS  auto 模式下的脚本选择器列表
 */

'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["0630d19a6fd1dd0b", "scripts/xuejieba.js", "xuejieba.js", "xuejieba"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const fs = require('fs');
const path = require('path');

const TASK_NAME = '学姐吧签到';
const CATALOG_ID = '0630d19a6fd1dd0b';
const CREDENTIAL_ENV = 'XUEJIEBA_COOKIE_LIST';
const DRY_RUN_ENV = 'XUEJIEBA_DRY_RUN';
const ENDPOINT = new URL('https://xuejieba2026.com/wp-json/b2/v1/userMission');
const MAX_RESPONSE_BYTES = 64 * 1024;
const DEFAULT_TIMEOUT_MS = 10000;

function nowText(date = new Date()) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date).replaceAll('/', '-');
}

function timeOnly() {
  return nowText().split(' ')[1];
}

function elapsedMs(startedAt) {
  return Date.now() - startedAt;
}

function envEnabled(name) {
  return /^(1|true|yes|on)$/i.test(String(process.env[name] || '').trim());
}

function timeoutMs() {
  const value = Number.parseInt(process.env.XUEJIEBA_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000
    ? value
    : DEFAULT_TIMEOUT_MS;
}

function parseAccounts(raw) {
  return String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function tokenFromCookie(cookie) {
  const match = String(cookie).match(/(?:^|;\s*)b2_token=([^;]+)/i);
  return match ? match[1].trim() : '';
}

function sanitizeMessage(value) {
  if (typeof value !== 'string' && typeof value !== 'number') return '服务未提供可识别的结果说明';
  let text = String(value)
    .replace(/<[^>]*>/g, ' ')
    .replace(/bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [已隐藏]')
    .replace(/(?:b2_token|token|cookie|session|device[_-]?id)\s*[=:]\s*[^\s;,]+/gi, '$1=[已隐藏]')
    .replace(/\b1\d{10}\b/g, '[手机号已隐藏]')
    .replace(/[A-Za-z0-9_-]{48,}/g, '[敏感值已隐藏]')
    .replace(/\s+/g, ' ')
    .trim();
  if (!text) text = '服务未提供可识别的结果说明';
  return text.slice(0, 160);
}

function safeNumber(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value === 'string' && /^-?\d+(?:\.\d+)?$/.test(value.trim())) return value.trim();
  return null;
}

function safeIdentityValue(value, allowNumeric) {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  const text = String(value).replace(/\s+/g, ' ').trim().slice(0, 80);
  if (!text) return '';
  if (!allowNumeric && /^\+?\d[\d -]{6,}$/.test(text)) return '';
  return sanitizeMessage(text);
}

function findIdentity(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return '';
  const containers = [payload, payload.user, payload.data, payload.mission].filter(
    (item) => item && typeof item === 'object' && !Array.isArray(item),
  );
  const nameKeys = ['nickname', 'nick_name', 'username', 'user_name', 'display_name'];
  for (const container of containers) {
    for (const key of nameKeys) {
      const identity = safeIdentityValue(container[key], false);
      if (identity) return `${key}：${identity}`;
    }
  }
  for (const container of containers) {
    for (const key of ['uid', 'user_id']) {
      const identity = safeIdentityValue(container[key], true);
      if (identity) return `${key}：${identity}`;
    }
  }
  return '';
}

function businessResult(statusCode, payload) {
  if (statusCode !== 200) {
    const message = payload && typeof payload === 'object'
      ? payload.message || payload.error
      : undefined;
    return { ok: false, state: 'failure', detail: `HTTP ${statusCode}：${sanitizeMessage(message || '签到请求失败')}` };
  }

  if (
    payload
    && typeof payload === 'object'
    && !Array.isArray(payload)
    && payload.mission
    && typeof payload.mission === 'object'
    && !Array.isArray(payload.mission)
  ) {
    const mission = payload.mission;
    const credit = safeNumber(payload.credit != null ? payload.credit : mission.credit);
    const always = safeNumber(mission.always);
    const totalCredit = safeNumber(mission.my_credit);
    const details = ['签到成功'];
    if (credit !== null) details.push(`积分+${credit}`);
    if (always !== null) details.push(`连续签到${always}天`);
    if (totalCredit !== null) details.push(`当前积分${totalCredit}`);
    return { ok: true, state: 'success', detail: details.join('，') };
  }

  const numeric = safeNumber(payload);
  if (numeric !== null) {
    return { ok: true, state: 'alreadyComplete', detail: `今日已签到（今日积分+${numeric}）` };
  }

  const message = payload && typeof payload === 'object'
    ? payload.message || payload.error
    : undefined;
  const detail = sanitizeMessage(message || '响应缺少可验证的签到成功字段');
  if (/(今日|今天).*(已签到|签到过)|已完成.*签到|请勿重复签到/.test(detail)) {
    return { ok: true, state: 'alreadyComplete', detail };
  }
  return { ok: false, state: 'failure', detail };
}

function networkFailureReason(error) {
  const code = error && typeof error.code === 'string' ? error.code : '';
  const known = {
    ETIMEDOUT: '请求超时',
    ECONNRESET: '连接被重置',
    ECONNREFUSED: '连接被拒绝',
    ENOTFOUND: '域名解析失败',
    EAI_AGAIN: '域名解析暂时失败',
    ERESPONSETOOLARGE: '响应内容超过安全限制',
  };
  return known[code] || '网络请求失败';
}

function requestMission(cookie, token) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finishReject = (error) => {
      if (settled) return;
      settled = true;
      reject(error);
    };
    const request = https.request({
      protocol: ENDPOINT.protocol,
      hostname: ENDPOINT.hostname,
      port: ENDPOINT.port || 443,
      path: `${ENDPOINT.pathname}${ENDPOINT.search}`,
      method: 'POST',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Linux; Qinglong) AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36',
        Cookie: cookie,
        Authorization: `Bearer ${token}`,
        Origin: 'https://xuejieba2026.com',
        Referer: 'https://xuejieba2026.com/bbs',
        Accept: 'application/json, text/plain, */*',
        'Content-Length': '0',
      },
      timeout: timeoutMs(),
    }, (response) => {
      const chunks = [];
      let bytes = 0;
      response.on('data', (chunk) => {
        bytes += chunk.length;
        if (bytes > MAX_RESPONSE_BYTES) {
          const error = new Error('response too large');
          error.code = 'ERESPONSETOOLARGE';
          response.destroy(error);
          return;
        }
        chunks.push(chunk);
      });
      response.on('error', finishReject);
      response.on('end', () => {
        if (settled) return;
        const body = Buffer.concat(chunks).toString('utf8').replace(/^\uFEFF/, '');
        let payload;
        try {
          payload = JSON.parse(body);
        } catch {
          settled = true;
          resolve({ statusCode: response.statusCode || 0, invalidJson: true, payload: null });
          return;
        }
        settled = true;
        resolve({ statusCode: response.statusCode || 0, invalidJson: false, payload });
      });
    });
    request.on('timeout', () => {
      const error = new Error('timeout');
      error.code = 'ETIMEDOUT';
      request.destroy(error);
    });
    request.on('error', finishReject);
    request.end();
  });
}

function stage(accountNumber, stageNumber, name, detail, icon = '✅', startedAt = Date.now()) {
  console.log(`[${timeOnly()}] 账号${accountNumber}｜阶段${stageNumber} ${name}｜${icon} ${detail}｜耗时 ${elapsedMs(startedAt)}ms`);
}

async function runAccount(cookie, index, dryRun) {
  const accountStartedAt = Date.now();
  const stats = { total: 1, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  console.log(`\n[${timeOnly()}] ── 账号${index}开始 ──`);

  const validationStartedAt = Date.now();
  const token = tokenFromCookie(cookie);
  if (!token) {
    stats.failed = 1;
    stage(index, 1, '参数检查', 'Cookie 缺少 b2_token 字段', '❌', validationStartedAt);
    console.log(`[${timeOnly()}] 账号${index}统计｜总任务 1｜成功 0｜已完成 0｜跳过 0｜失败 1｜耗时 ${elapsedMs(accountStartedAt)}ms`);
    return { ok: false, state: 'failure', stats, identity: '' };
  }
  stage(index, 1, '参数检查', 'Cookie 格式检查通过（敏感值未输出）', '✅', validationStartedAt);

  if (dryRun) {
    const dryStartedAt = Date.now();
    stats.skipped = 1;
    stage(index, 2, '断网预演', '已验证请求配置；未发起网络请求、未执行签到', '⏭️', dryStartedAt);
    console.log(`[${timeOnly()}] 账号${index}统计｜总任务 1｜成功 0｜已完成 0｜跳过 1｜失败 0｜耗时 ${elapsedMs(accountStartedAt)}ms`);
    return { ok: true, state: 'dryRun', stats, identity: '' };
  }

  const requestStartedAt = Date.now();
  try {
    const response = await requestMission(cookie, token);
    if (response.invalidJson) {
      stats.failed = 1;
      stage(index, 2, '执行签到', '服务响应不是有效 JSON，无法验证业务成功', '❌', requestStartedAt);
      console.log(`[${timeOnly()}] 账号${index}统计｜总任务 1｜成功 0｜已完成 0｜跳过 0｜失败 1｜耗时 ${elapsedMs(accountStartedAt)}ms`);
      return { ok: false, state: 'failure', stats, identity: '' };
    }
    const result = businessResult(response.statusCode, response.payload);
    const identity = findIdentity(response.payload);
    if (identity) console.log(`[${timeOnly()}] 账号${index}身份｜${identity}`);
    if (result.ok && result.state === 'success') stats.success = 1;
    else if (result.ok) stats.alreadyComplete = 1;
    else stats.failed = 1;
    stage(index, 2, '执行签到', result.detail, result.ok ? (result.state === 'success' ? '✅' : '☑️') : '❌', requestStartedAt);
    console.log(`[${timeOnly()}] 账号${index}统计｜总任务 1｜成功 ${stats.success}｜已完成 ${stats.alreadyComplete}｜跳过 0｜失败 ${stats.failed}｜耗时 ${elapsedMs(accountStartedAt)}ms`);
    return { ok: result.ok, state: result.state, stats, identity };
  } catch (error) {
    stats.failed = 1;
    stage(index, 2, '执行签到', networkFailureReason(error), '❌', requestStartedAt);
    console.log(`[${timeOnly()}] 账号${index}统计｜总任务 1｜成功 0｜已完成 0｜跳过 0｜失败 1｜耗时 ${elapsedMs(accountStartedAt)}ms`);
    return { ok: false, state: 'failure', stats, identity: '' };
  }
}

function globMatches(pattern, value) {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.');
  return new RegExp(`^${escaped}$`, 'i').test(value);
}

function notificationDecision() {
  const rawSwitch = String(process.env.QINGLONG_NOTIFY || 'auto').trim().toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(rawSwitch)) return { enabled: false, reason: '全局开关已关闭' };
  if (['1', 'true', 'yes', 'on'].includes(rawSwitch)) return { enabled: true, reason: '全局开关已开启' };
  if (rawSwitch !== '' && rawSwitch !== 'auto') return { enabled: false, reason: '全局开关值无效，按 auto 处理且未启用' };

  if (!Object.prototype.hasOwnProperty.call(process.env, 'QINGLONG_NOTIFY_SCRIPTS')) {
    return { enabled: false, reason: 'auto 模式仅通知已列出的脚本' };
  }
  const selection = String(process.env.QINGLONG_NOTIFY_SCRIPTS || '').trim();
  if (!selection) return { enabled: false, reason: '脚本选择器为空' };
  const selectors = selection.split(/[,;\s]+/).filter(Boolean);
  const currentFilename = path.basename(process.argv[1] || 'candidate.js');
  const identities = [CATALOG_ID, 'sign/xuejieba.js', 'xuejieba.js', 'candidate.js', currentFilename];
  const matched = selectors.some((selector) => selector === '*' || identities.some((identity) => globMatches(selector, identity)));
  return { enabled: matched, reason: matched ? '脚本选择器匹配' : '脚本选择器未匹配' };
}

function notificationCandidates() {
  const candidates = [];
  if (process.env.QINGLONG_NOTIFY_DIR) {
    candidates.push(path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'));
  }
  candidates.push('/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js');
  return [...new Set(candidates)];
}

async function sendNotification(body) {
  const decision = notificationDecision();
  if (!decision.enabled) return `未启用（${decision.reason}）`;
  for (const candidate of notificationCandidates()) {
    try {
      if (!fs.existsSync(candidate)) continue;
      const moduleValue = require(candidate);
      const sender = typeof moduleValue === 'function'
        ? moduleValue
        : moduleValue && (moduleValue.sendNotify || moduleValue.default);
      if (typeof sender !== 'function') continue;
      await sender(TASK_NAME, body);
      return '发送成功';
    } catch {
      return '发送失败（不影响业务退出码）';
    }
  }
  return '通知组件不可用（不影响业务退出码）';
}

function totalStats(results) {
  return results.reduce((totals, result) => {
    totals.total += result.stats.total;
    totals.success += result.stats.success;
    totals.alreadyComplete += result.stats.alreadyComplete;
    totals.skipped += result.stats.skipped;
    totals.failed += result.stats.failed;
    return totals;
  }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
}

async function main() {
  const startedAt = Date.now();
  const startedText = nowText(new Date(startedAt));
  const dryRun = envEnabled(DRY_RUN_ENV);
  const accounts = parseAccounts(process.env[CREDENTIAL_ENV]);

  console.log('========================================');
  console.log(`【${TASK_NAME}】`);
  console.log(`开始时间：${startedText}`);
  console.log(`运行模式：${dryRun ? 'DRY_RUN（完全断网）' : 'LIVE'}`);
  console.log(`账号数量：${accounts.length}`);
  console.log('========================================');

  let results = [];
  let businessExitCode = 0;
  let finalStatus;

  if (accounts.length === 0) {
    businessExitCode = 2;
    finalStatus = 'CONFIGURATION_ERROR';
    console.log(`[${timeOnly()}] 阶段1 配置检查｜❌ 缺少必填环境变量 ${CREDENTIAL_ENV}，需每行填写一个账号 Cookie`);
  } else {
    for (let index = 0; index < accounts.length; index += 1) {
      // 顺序执行，避免多个账号同时触发签到接口。
      results.push(await runAccount(accounts[index], index + 1, dryRun));
    }
    const failedAccounts = results.filter((item) => !item.ok).length;
    businessExitCode = failedAccounts > 0 ? 1 : 0;
    finalStatus = dryRun
      ? (businessExitCode === 0 ? 'DRY_RUN' : 'FAILURE')
      : (businessExitCode === 0 ? 'SUCCESS' : (failedAccounts < accounts.length ? 'PARTIAL_FAILURE' : 'FAILURE'));
  }

  const totals = totalStats(results);
  const successfulAccounts = results.filter((item) => item.ok).length;
  const failedAccounts = accounts.length - successfulAccounts;
  const notificationBody = `模式：${dryRun ? '断网预演' : '正式运行'}\n账号总数：${accounts.length}\n成功账号：${successfulAccounts}\n失败账号：${failedAccounts}\n最终状态：${finalStatus}`;
  const notificationStatus = await sendNotification(notificationBody);
  const finishedText = nowText();

  console.log('\n----------------------------------------');
  console.log(`账号结果：总数 ${accounts.length}｜成功 ${successfulAccounts}｜失败 ${failedAccounts}`);
  console.log(`子任务结果：总数 ${totals.total}｜成功 ${totals.success}｜已完成 ${totals.alreadyComplete}｜跳过 ${totals.skipped}｜失败 ${totals.failed}`);
  console.log(`总耗时：${elapsedMs(startedAt)}ms`);
  console.log(`完成时间：${finishedText}`);
  console.log(`通知状态：${notificationStatus}`);
  console.log(`最终状态：${finalStatus}`);
  console.log('----------------------------------------');

  const summary = {
    task: 'xuejieba',
    mode: dryRun ? 'dry-run' : 'live',
    status: finalStatus.toLowerCase().replaceAll('_', '-'),
    accounts: { total: accounts.length, success: successfulAccounts, failed: failedAccounts },
    subtasks: totals,
    notification: notificationStatus.startsWith('发送成功') ? 'sent' : (notificationStatus.startsWith('未启用') ? 'disabled' : 'unavailable'),
    exitCode: businessExitCode,
  };
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = businessExitCode;
}

main().catch(async () => {
  const notificationStatus = await sendNotification('账号总数：0\n成功账号：0\n失败账号：0\n最终状态：FAILURE');
  console.log(`通知状态：${notificationStatus}`);
  console.log('最终状态：FAILURE');
  console.log('TASK_SUMMARY={"task":"xuejieba","mode":"unknown","status":"failure","accounts":{"total":0,"success":0,"failed":0},"subtasks":{"total":0,"success":0,"alreadyComplete":0,"skipped":0,"failed":0},"notification":"unavailable","exitCode":1}');
  process.exitCode = 1;
});
