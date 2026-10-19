#!/usr/bin/env node
// name: 知末签到
// cron: 0 55 11 * * *
// 原始项目: ql_sign_script https://github.com/unitaryhighs/ql_sign_script
// 原始文件: sign/znzmo.js，MIT License
// SPDX-License-Identifier: MIT

'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["43ad6c3466e9d02c", "scripts/znzmo.js", "znzmo.js", "znzmo"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const path = require('path');

const TASK_NAME = '知末签到';
const CATALOG_ID = '43ad6c3466e9d02c';
const COOKIE_ENV = 'ZNZMO_COOKIE_LIST';
const DRY_RUN_ENV = 'ZNZMO_DRY_RUN';
const SIGN_URL = new URL('https://api.znzmo.com/member/sign/doSign');
const REQUEST_TIMEOUT_MS = 10_000;
const MAX_RESPONSE_BYTES = 256 * 1024;

function now() {
  return new Date().toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function elapsed(startedAt) {
  return `${Date.now() - startedAt}ms`;
}

function isEnabled(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase());
}

function logStage(accountNumber, stageNumber, title, detail, startedAt) {
  const suffix = startedAt === undefined ? '' : `，耗时 ${elapsed(startedAt)}`;
  console.log(`[${now()}] [账号 ${accountNumber}] 阶段 ${stageNumber}：${title} - ${detail}${suffix}`);
}

function parseAccounts(rawValue) {
  return String(rawValue || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function validateCookie(cookie) {
  if (/[\r\n]/.test(cookie)) return 'Cookie 不能包含换行符';
  if (!cookie.includes('=')) return 'Cookie 格式无效，应为名称=值形式';
  return '';
}

function safeCode(value) {
  const code = String(value === undefined || value === null ? '' : value);
  return /^[A-Za-z0-9_.-]{1,32}$/.test(code) ? code : '未知';
}

function cleanIdentity(value) {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  return String(value).replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, 120);
}

function findPublicIdentity(payload) {
  const identityKeys = ['nickname', 'nickName', 'username', 'userName', 'displayName', 'uid', 'publicUid'];
  const containers = [payload && payload.data, payload && payload.data && payload.data.userInfo, payload && payload.data && payload.data.member];
  for (const container of containers) {
    if (!container || typeof container !== 'object' || Array.isArray(container)) continue;
    for (const key of identityKeys) {
      const value = cleanIdentity(container[key]);
      if (value) return { key, value };
    }
  }
  return null;
}

function requestSign(cookie) {
  return new Promise((resolve, reject) => {
    const request = https.request(
      SIGN_URL,
      {
        method: 'POST',
        headers: {
          Accept: 'application/json, text/plain, */*',
          'Content-Length': '0',
          Cookie: cookie,
          Origin: 'https://www.znzmo.com',
          Referer: 'https://www.znzmo.com/',
          'User-Agent': 'Mozilla/5.0 (compatible; Qinglong-ZNZMO/1.0)',
        },
        timeout: REQUEST_TIMEOUT_MS,
      },
      (response) => {
        const chunks = [];
        let size = 0;
        response.on('error', reject);
        response.on('data', (chunk) => {
          size += chunk.length;
          if (size > MAX_RESPONSE_BYTES) {
            request.destroy(new Error('响应超过大小限制'));
            return;
          }
          chunks.push(chunk);
        });
        response.on('end', () => {
          resolve({
            statusCode: response.statusCode || 0,
            body: Buffer.concat(chunks).toString('utf8'),
          });
        });
      },
    );

    request.setTimeout(REQUEST_TIMEOUT_MS, () => {
      request.destroy(new Error(`请求超时（${REQUEST_TIMEOUT_MS / 1000} 秒）`));
    });
    request.on('error', reject);
    request.end();
  });
}

function evaluateResponse(response) {
  if (response.statusCode !== 200) {
    return { ok: false, alreadyComplete: false, detail: `HTTP 状态码 ${response.statusCode}` };
  }

  let payload;
  try {
    payload = JSON.parse(response.body);
  } catch {
    return { ok: false, alreadyComplete: false, detail: '接口未返回有效 JSON' };
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { ok: false, alreadyComplete: false, detail: '接口响应结构无效' };
  }

  const error = payload.error && typeof payload.error === 'object' ? payload.error : {};
  const errorCode = String(error.errorCode === undefined || error.errorCode === null ? '' : error.errorCode);
  const errorMessage = typeof error.errorMsg === 'string' ? error.errorMsg : '';
  const identity = findPublicIdentity(payload);

  if (errorCode === '0') {
    const integralValue = payload.data && payload.data.integralValue;
    const reward = typeof integralValue === 'number' || (typeof integralValue === 'string' && integralValue.length <= 32 && /^[-+]?\d+(?:\.\d+)?$/.test(integralValue.trim()))
      ? `，积分奖励 ${String(integralValue).replace(/^\+/, '')}`
      : '';
    return { ok: true, alreadyComplete: false, detail: `签到成功${reward}`, identity };
  }

  if (/(?:今天)?已(?:经)?签到|重复签到/.test(errorMessage)) {
    return { ok: true, alreadyComplete: true, detail: '今天已经签到', identity };
  }

  const detail = /登录|未登录|过期|失效/.test(errorMessage)
    ? '登录状态无效，请更新 Cookie'
    : `接口返回业务失败（错误码 ${safeCode(errorCode)}）`;
  return { ok: false, alreadyComplete: false, detail, identity };
}

function selectorMatches(pattern, candidate) {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.');
  return new RegExp(`^${escaped}$`, 'i').test(candidate);
}

function shouldNotify() {
  const switchValue = String(process.env.QINGLONG_NOTIFY || 'auto').trim().toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(switchValue)) return { enabled: false, reason: '全局通知开关已关闭' };

  if (Object.prototype.hasOwnProperty.call(process.env, 'QINGLONG_NOTIFY_SCRIPTS')) {
    const raw = process.env.QINGLONG_NOTIFY_SCRIPTS || '';
    const selectors = raw.split(/[,;\s]+/).filter(Boolean);
    if (selectors.length === 0) return { enabled: false, reason: '通知脚本列表为空' };
    const candidates = [CATALOG_ID, 'znzmo.js', path.basename(process.argv[1] || 'candidate.js')];
    const selected = selectors.includes('*') || selectors.some((selector) => candidates.some((candidate) => selectorMatches(selector, candidate)));
    if (!selected) return { enabled: false, reason: '当前脚本未被通知列表选中' };
  }

  return { enabled: true, reason: '' };
}

function notifierCandidates() {
  const candidates = [];
  if (process.env.QINGLONG_NOTIFY_DIR) {
    candidates.push(path.resolve(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'));
  }
  candidates.push('/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js');
  return [...new Set(candidates)];
}

async function sendSummaryNotification(body, dryRun) {
  const decision = shouldNotify();
  if (!decision.enabled) return { status: 'disabled', detail: decision.reason };
  if (dryRun) return { status: 'skipped-dry-run', detail: '断网预演不调用通知网络' };

  for (const candidate of notifierCandidates()) {
    let loaded;
    try {
      loaded = require(candidate);
    } catch (error) {
      if (error && error.code === 'MODULE_NOT_FOUND') continue;
      console.log(`[${now()}] ⚠️ 通知模块加载失败：${path.basename(candidate)}`);
      continue;
    }
    const sendNotify = typeof loaded === 'function'
      ? loaded
      : loaded && typeof loaded.sendNotify === 'function'
        ? loaded.sendNotify
        : loaded && typeof loaded.default === 'function'
          ? loaded.default
          : null;
    if (!sendNotify) continue;
    try {
      await Promise.resolve(sendNotify(TASK_NAME, body));
      return { status: 'sent', detail: `已通过 ${path.basename(candidate)} 发送` };
    } catch {
      return { status: 'failed', detail: '通知发送失败，业务退出码保持不变' };
    }
  }
  return { status: 'unavailable', detail: '未找到可用的 sendNotify.js，业务退出码保持不变' };
}

async function runAccount(cookie, accountNumber, dryRun) {
  const accountStartedAt = Date.now();
  console.log(`\n[${now()}] ===== 账号 ${accountNumber} 开始 =====`);

  let stageStartedAt = Date.now();
  const validationError = validateCookie(cookie);
  if (validationError) {
    logStage(accountNumber, 1, '参数校验', `❌ ${validationError}`, stageStartedAt);
    console.log(`[${now()}] [账号 ${accountNumber}] 结果：❌ 配置无效`);
    console.log(`[${now()}] [账号 ${accountNumber}] 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1，耗时 ${elapsed(accountStartedAt)}`);
    return {
      ok: false,
      stats: { total: 1, success: 0, alreadyComplete: 0, skipped: 0, failed: 1 },
      durationMs: Date.now() - accountStartedAt,
    };
  }
  logStage(accountNumber, 1, '参数校验', '✅ Cookie 结构有效（内容已隐藏）', stageStartedAt);

  if (dryRun) {
    stageStartedAt = Date.now();
    logStage(accountNumber, 2, '断网预演', `⏭️ 将向 ${SIGN_URL.hostname}${SIGN_URL.pathname} 发起空请求体 POST；未发起网络请求`, stageStartedAt);
    console.log(`[${now()}] [账号 ${accountNumber}] 结果：✅ 预演通过`);
    console.log(`[${now()}] [账号 ${accountNumber}] 统计：总任务 1，成功 0，已完成 0，跳过 1，失败 0，耗时 ${elapsed(accountStartedAt)}`);
    return {
      ok: true,
      stats: { total: 1, success: 0, alreadyComplete: 0, skipped: 1, failed: 0 },
      durationMs: Date.now() - accountStartedAt,
    };
  }

  stageStartedAt = Date.now();
  logStage(accountNumber, 2, '签到请求', '开始调用官方签到接口', undefined);
  let response;
  try {
    response = await requestSign(cookie);
    logStage(accountNumber, 2, '签到请求', `✅ 请求完成，HTTP ${response.statusCode}`, stageStartedAt);
  } catch (error) {
    const detail = error && error.message === '响应超过大小限制'
      ? '响应超过大小限制'
      : error && /超时/.test(error.message)
        ? error.message
        : '网络请求失败';
    logStage(accountNumber, 2, '签到请求', `❌ ${detail}`, stageStartedAt);
    console.log(`[${now()}] [账号 ${accountNumber}] 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1，耗时 ${elapsed(accountStartedAt)}`);
    return {
      ok: false,
      stats: { total: 1, success: 0, alreadyComplete: 0, skipped: 0, failed: 1 },
      durationMs: Date.now() - accountStartedAt,
    };
  }

  stageStartedAt = Date.now();
  const result = evaluateResponse(response);
  if (result.identity) {
    console.log(`[${now()}] [账号 ${accountNumber}] 官方账号身份（${result.identity.key}）：${result.identity.value}`);
  }
  const icon = result.ok ? (result.alreadyComplete ? '☑️' : '✅') : '❌';
  logStage(accountNumber, 3, '业务校验', `${icon} ${result.detail}`, stageStartedAt);

  const stats = {
    total: 1,
    success: result.ok && !result.alreadyComplete ? 1 : 0,
    alreadyComplete: result.alreadyComplete ? 1 : 0,
    skipped: 0,
    failed: result.ok ? 0 : 1,
  };
  console.log(`[${now()}] [账号 ${accountNumber}] 结果：${icon} ${result.ok ? '执行完成' : '执行失败'}`);
  console.log(`[${now()}] [账号 ${accountNumber}] 统计：总任务 1，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 0，失败 ${stats.failed}，耗时 ${elapsed(accountStartedAt)}`);
  return { ok: result.ok, stats, durationMs: Date.now() - accountStartedAt };
}

function addStats(target, source) {
  for (const key of ['total', 'success', 'alreadyComplete', 'skipped', 'failed']) {
    target[key] += source[key];
  }
}

async function main() {
  const taskStartedAt = Date.now();
  const startedAt = new Date().toISOString();
  const dryRun = isEnabled(process.env[DRY_RUN_ENV]);
  const accounts = parseAccounts(process.env[COOKIE_ENV]);
  const accountStats = { total: accounts.length, success: 0, failed: 0 };
  const taskStats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };

  console.log(`========== ${TASK_NAME} ==========`);
  console.log(`开始时间：${startedAt}`);
  console.log(`运行模式：${dryRun ? 'DRY_RUN（完全断网预演）' : 'LIVE（真实签到）'}`);
  console.log(`账号数量：${accounts.length}`);

  let configurationError = false;
  if (accounts.length === 0) {
    configurationError = true;
    console.log(`[${now()}] 阶段 1：配置检查 - ❌ 缺少必填环境变量 ${COOKIE_ENV}，每行应填写一个账号 Cookie`);
  } else {
    for (let index = 0; index < accounts.length; index += 1) {
      const result = await runAccount(accounts[index], index + 1, dryRun);
      addStats(taskStats, result.stats);
      if (result.ok) accountStats.success += 1;
      else accountStats.failed += 1;
    }
  }

  let finalStatus;
  if (configurationError) finalStatus = 'configuration-error';
  else if (dryRun && accountStats.failed === 0) finalStatus = 'dry-run';
  else if (accountStats.failed === 0) finalStatus = 'success';
  else if (accountStats.success > 0) finalStatus = 'partial-failure';
  else finalStatus = 'failure';

  const notificationBody = [
    `状态：${finalStatus}`,
    `账号总数：${accountStats.total}`,
    `成功账号：${accountStats.success}`,
    `失败账号：${accountStats.failed}`,
    `子任务成功：${taskStats.success + taskStats.alreadyComplete}`,
    `子任务失败：${taskStats.failed}`,
  ].join('\n');
  const notification = await sendSummaryNotification(notificationBody, dryRun);
  console.log(`[${now()}] 通知状态：${notification.status}（${notification.detail}）`);

  const finishedAt = new Date().toISOString();
  const durationMs = Date.now() - taskStartedAt;
  console.log('\n----------------------------------------');
  console.log(`账号统计：总数 ${accountStats.total}，成功 ${accountStats.success}，失败 ${accountStats.failed}`);
  console.log(`子任务统计：总数 ${taskStats.total}，成功 ${taskStats.success}，已完成 ${taskStats.alreadyComplete}，跳过 ${taskStats.skipped}，失败 ${taskStats.failed}`);
  console.log(`总耗时：${durationMs}ms`);
  console.log(`完成时间：${finishedAt}`);
  console.log(`通知状态：${notification.status}`);
  console.log(`最终状态：${finalStatus.toUpperCase()}`);

  const machineSummary = {
    task: 'znzmo',
    status: finalStatus,
    dryRun,
    accounts: accountStats,
    subtasks: taskStats,
    notification: notification.status,
    startedAt,
    finishedAt,
    durationMs,
  };
  console.log(`TASK_SUMMARY=${JSON.stringify(machineSummary)}`);
  process.exitCode = configurationError || accountStats.failed > 0 ? 1 : 0;
}

main().catch((error) => {
  const finishedAt = new Date().toISOString();
  console.error(`[${now()}] ❌ 未预期的内部错误：${error && error.name ? error.name : 'Error'}`);
  console.log(`完成时间：${finishedAt}`);
  console.log('最终状态：FAILURE');
  console.log(`TASK_SUMMARY=${JSON.stringify({
    task: 'znzmo',
    status: 'failure',
    dryRun: isEnabled(process.env[DRY_RUN_ENV]),
    accounts: { total: 0, success: 0, failed: 1 },
    subtasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 1 },
    notification: 'not-attempted',
    finishedAt,
  })}`);
  process.exitCode = 1;
});
