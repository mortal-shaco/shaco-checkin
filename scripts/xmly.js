#!/usr/bin/env node
// name: 喜马拉雅每日签到
// cron: 10 0 12 * * *
/*
 * name: 喜马拉雅每日签到
 * cron: 10 0 12 * * *
 * SPDX-License-Identifier: MIT
 *
 * 上游项目：ql_sign_script
 * 原始来源：https://github.com/unitaryhighs/ql_sign_script
 * 原始标识：ql_sign_script : https://github.com/unitaryhighs/ql_sign_script
 *
 * 环境变量：
 *   XMLY_LIST（必填）：每行一个账号。填写 Cookie；如接口要求 X-Xuid-Fp，
 *     可在同一行首个制表符后填写，即 Cookie<TAB>X-Xuid-Fp。
 *   XMLY_DRY_RUN=1：完全断网预演，不调用签到接口或通知脚本。
 *   XMLY_TIMEOUT_SECONDS：请求超时秒数，默认 12，范围 3～60。
 *   QINGLONG_NOTIFY：auto（默认）、1/true/yes/on 或 0/false/no/off。
 *   QINGLONG_NOTIFY_SCRIPTS：用逗号、分号或空白分隔脚本选择器；支持 *、
 *     catalogId、文件名、相对路径和 * 通配符。未设置时 auto 模式不通知。
 *
 * Cookie 获取：登录喜马拉雅网页或 App，在本人设备的开发者工具/抓包工具中，
 * 找到发往 ximalaya.com 的本人请求并复制完整 Cookie。请勿分享给他人。
 */

'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["44110e6cc005cbcd", "scripts/xmly.js", "xmly.js", "xmly"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const fs = require('fs');
const path = require('path');
const https = require('https');
const { spawnSync } = require('child_process');

const TASK_NAME = '喜马拉雅每日签到';
const CATALOG_ID = '44110e6cc005cbcd';
const ENDPOINT = 'https://hybrid.ximalaya.com/web-activity/signIn/v2/signIn';
const DEFAULT_TIMEOUT_SECONDS = 12;
const MAX_RESPONSE_BYTES = 64 * 1024;
const ENABLED = new Set(['1', 'true', 'yes', 'on']);
const DISABLED = new Set(['0', 'false', 'no', 'off']);

function now() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false });
}

function isoNow() {
  return new Date().toISOString();
}

function elapsed(startedAt) {
  return `${Date.now() - startedAt}ms`;
}

function log(message) {
  console.log(`[${now()}] ${message}`);
}

function cleanText(value, maxLength = 160) {
  if (value === undefined || value === null) return '';
  return String(value).replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, maxLength);
}

function envEnabled(name) {
  return ENABLED.has(String(process.env[name] || '').trim().toLowerCase());
}

function timeoutMilliseconds() {
  const raw = Number(process.env.XMLY_TIMEOUT_SECONDS || DEFAULT_TIMEOUT_SECONDS);
  if (!Number.isFinite(raw)) return DEFAULT_TIMEOUT_SECONDS * 1000;
  return Math.min(60, Math.max(3, raw)) * 1000;
}

function parseAccounts(raw) {
  return String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const tab = line.indexOf('\t');
      const cookie = (tab === -1 ? line : line.slice(0, tab)).trim();
      const xXuidFp = (tab === -1 ? '' : line.slice(tab + 1)).trim();
      return { index: index + 1, cookie, xXuidFp };
    });
}

function validateAccount(account) {
  if (!account.cookie) return 'Cookie 为空';
  if (/[\r\n]/.test(account.cookie) || /[\r\n]/.test(account.xXuidFp)) return '凭据包含非法换行符';
  return '';
}

function requestJson(urlString, payload, headers, timeoutMs) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlString);
    const body = Buffer.from(JSON.stringify(payload), 'utf8');
    let settled = false;

    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      if (error) reject(error);
      else resolve(value);
    };

    const request = https.request({
      protocol: url.protocol,
      hostname: url.hostname,
      port: url.port || 443,
      path: `${url.pathname}${url.search}`,
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'Content-Length': body.length,
        'User-Agent': 'Qinglong-Ximalaya-Checkin/1.0',
        ...headers,
      },
    }, (response) => {
      const chunks = [];
      let size = 0;

      response.on('data', (chunk) => {
        size += chunk.length;
        if (size > MAX_RESPONSE_BYTES) {
          response.destroy();
          finish(new Error('响应体超过 64 KiB 安全上限'));
          return;
        }
        chunks.push(chunk);
      });

      response.on('error', (error) => finish(new Error(`响应读取失败：${cleanText(error.message)}`)));
      response.on('end', () => {
        if (settled) return;
        const text = Buffer.concat(chunks).toString('utf8');
        let data;
        try {
          data = JSON.parse(text);
        } catch {
          finish(new Error(`接口返回非 JSON（HTTP ${response.statusCode || 0}）`));
          return;
        }
        finish(null, { statusCode: response.statusCode || 0, data });
      });
    });

    request.setTimeout(timeoutMs, () => request.destroy(new Error(`请求超过 ${Math.round(timeoutMs / 1000)} 秒`)));
    request.on('error', (error) => finish(new Error(cleanText(error.message) || '网络请求失败')));
    request.end(body);
  });
}

function firstValue(object, paths) {
  for (const keys of paths) {
    let value = object;
    for (const key of keys) value = value && typeof value === 'object' ? value[key] : undefined;
    if (value !== undefined && value !== null) return value;
  }
  return undefined;
}

function extractIdentity(body) {
  const value = firstValue(body, [
    ['data', 'nickname'], ['data', 'nickName'], ['data', 'username'], ['data', 'userName'],
    ['data', 'displayName'], ['data', 'uid'], ['data', 'userId'],
    ['nickname'], ['username'], ['displayName'], ['uid'],
  ]);
  return cleanText(value, 80);
}

function classifyBusinessResult(statusCode, body) {
  if (statusCode < 200 || statusCode >= 300) {
    return { ok: false, status: 'failed', detail: `HTTP 状态码 ${statusCode}` };
  }
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, status: 'failed', detail: '响应不是有效业务对象' };
  }

  const message = cleanText(firstValue(body, [
    ['data', 'msg'], ['data', 'message'], ['msg'], ['message'],
  ]));
  const code = firstValue(body, [
    ['ret'], ['code'], ['status'], ['data', 'code'], ['data', 'status'],
  ]);
  const successFlag = firstValue(body, [['success'], ['data', 'success']]);
  const already = /已签到|已经签到|重复签到|今日.*签/.test(message);
  const failedMessage = /失败|错误|无效|过期|未登录|请登录|异常|拒绝|风控/.test(message);
  const successfulMessage = /签到成功|成功签到|success/i.test(message);
  const normalizedCode = typeof code === 'string' ? code.trim().toLowerCase() : code;
  const successfulCode = [0, 200, true, '0', '200', 'success', 'ok'].includes(normalizedCode);
  const hasCode = code !== undefined;

  if (already) return { ok: true, status: 'already_complete', detail: message || '今日已签到' };
  if (successFlag === false || failedMessage) {
    return { ok: false, status: 'failed', detail: message || '接口明确返回失败' };
  }
  if (hasCode && !successfulCode) {
    return { ok: false, status: 'failed', detail: `业务码 ${cleanText(code, 32)} 未被识别为成功` };
  }
  if (successFlag === true || successfulCode || successfulMessage) {
    return { ok: true, status: 'success', detail: message || '接口业务成功标识校验通过' };
  }
  return { ok: false, status: 'failed', detail: '响应缺少可验证的成功业务码或成功信息' };
}

async function runAccount(account, dryRun, timeoutMs) {
  const startedAt = Date.now();
  const label = `账号 ${account.index}`;
  log(`── ${label} ──`);
  log(`[1/2] ${label} 参数检查`);
  const invalidReason = validateAccount(account);
  if (invalidReason) {
    log(`❌ ${label} 参数无效：${invalidReason}`);
    return { account: account.index, status: 'failed', tasks: 1, success: 0, already: 0, skipped: 0, failed: 1, durationMs: Date.now() - startedAt };
  }
  log(`✅ ${label} 已读取 Cookie${account.xXuidFp ? '及同账号 X-Xuid-Fp' : ''}（内容已隐藏）`);

  log(`[2/2] ${label} ${dryRun ? '断网预演' : '执行签到'}`);
  if (dryRun) {
    log(`⏭️ ${label} 预演成功：请求参数有效，未调用签到接口或通知脚本`);
    return { account: account.index, status: 'dry_run', tasks: 1, success: 0, already: 0, skipped: 1, failed: 0, durationMs: Date.now() - startedAt };
  }

  try {
    const headers = { Cookie: account.cookie };
    if (account.xXuidFp) headers['X-Xuid-Fp'] = account.xXuidFp;
    const response = await requestJson(ENDPOINT, { aid: 87 }, headers, timeoutMs);
    const identity = extractIdentity(response.data);
    if (identity) log(`👤 ${label} 官方身份：${identity}`);
    const result = classifyBusinessResult(response.statusCode, response.data);
    if (!result.ok) {
      log(`❌ ${label} 签到失败：${result.detail}`);
      return { account: account.index, identity, status: 'failed', tasks: 1, success: 0, already: 0, skipped: 0, failed: 1, durationMs: Date.now() - startedAt };
    }
    const icon = result.status === 'already_complete' ? '☑️' : '✅';
    log(`${icon} ${label} ${result.detail}`);
    return {
      account: account.index, identity, status: result.status, tasks: 1,
      success: result.status === 'success' ? 1 : 0,
      already: result.status === 'already_complete' ? 1 : 0,
      skipped: 0, failed: 0, durationMs: Date.now() - startedAt,
    };
  } catch (error) {
    log(`❌ ${label} 请求失败：${cleanText(error.message)}`);
    return { account: account.index, status: 'failed', tasks: 1, success: 0, already: 0, skipped: 0, failed: 1, durationMs: Date.now() - startedAt };
  }
}

function wildcardMatches(pattern, value) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
  return new RegExp(`^${escaped}$`, 'i').test(value);
}

function notificationSelected() {
  const mode = String(process.env.QINGLONG_NOTIFY || 'auto').trim().toLowerCase();
  if (DISABLED.has(mode)) return false;

  const hasSelection = Object.prototype.hasOwnProperty.call(process.env, 'QINGLONG_NOTIFY_SCRIPTS');
  if (hasSelection) {
    const selectors = String(process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
    if (!selectors.length) return false;
    const filename = path.basename(__filename);
    const normalizedPath = __filename.replace(/\\/g, '/');
    const matched = selectors.some((selector) => {
      if (selector === '*') return true;
      return wildcardMatches(selector, CATALOG_ID)
        || wildcardMatches(selector, filename)
        || wildcardMatches(selector.replace(/\\/g, '/'), normalizedPath)
        || normalizedPath.endsWith(`/${selector.replace(/\\/g, '/')}`);
    });
    if (!matched) return false;
  }

  if (ENABLED.has(mode)) return true;
  return hasSelection;
}

function notifyPython(title, body) {
  const directories = [];
  if (process.env.QINGLONG_NOTIFY_DIR) directories.push(process.env.QINGLONG_NOTIFY_DIR);
  directories.push('/ql/data/scripts', '/ql/scripts');
  const files = directories.map((directory) => path.join(directory, 'notify.py')).filter((file) => fs.existsSync(file));
  const attempts = [
    'from notify import send; import os; send(os.environ["QL_SAFE_NOTIFY_TITLE"], os.environ["QL_SAFE_NOTIFY_BODY"])',
    ...files.map((file) => `import importlib.util,os; s=importlib.util.spec_from_file_location("ql_notify",${JSON.stringify(file)}); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(os.environ["QL_SAFE_NOTIFY_TITLE"],os.environ["QL_SAFE_NOTIFY_BODY"])`),
  ];
  for (const command of ['python3', 'python']) {
    for (const code of attempts) {
      const result = spawnSync(command, ['-c', code], {
        env: { ...process.env, QL_SAFE_NOTIFY_TITLE: title, QL_SAFE_NOTIFY_BODY: body },
        stdio: 'ignore', timeout: 15000,
      });
      if (!result.error && result.status === 0) return true;
    }
  }
  return false;
}

async function sendNotification(title, body, dryRun) {
  if (dryRun) return 'dry-run-skipped';
  if (!notificationSelected()) return 'not-selected';

  const candidates = [];
  if (process.env.QINGLONG_NOTIFY_DIR) candidates.push(path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'));
  candidates.push('/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js');
  for (const file of candidates) {
    if (!fs.existsSync(file)) continue;
    try {
      const moduleValue = require(file);
      const sender = typeof moduleValue === 'function' ? moduleValue : moduleValue.sendNotify || moduleValue.default;
      if (typeof sender !== 'function') continue;
      await Promise.resolve(sender(title, body));
      return 'sent';
    } catch (error) {
      log(`⚠️ JavaScript 通知组件不可用：${cleanText(error.message)}`);
    }
  }

  if (notifyPython(title, body)) return 'sent';
  return 'unavailable';
}

function printAccountStats(result) {
  const identity = result.identity ? `，身份：${result.identity}` : '';
  log(`账号 ${result.account} 统计：总任务 ${result.tasks}，成功 ${result.success}，已完成 ${result.already}，跳过 ${result.skipped}，失败 ${result.failed}，耗时 ${result.durationMs}ms${identity}`);
}

async function main() {
  const taskStartedAt = Date.now();
  const startedAt = isoNow();
  const dryRun = envEnabled('XMLY_DRY_RUN');
  const accounts = parseAccounts(process.env.XMLY_LIST);
  const results = [];

  console.log('========================================');
  console.log(`【${TASK_NAME}】`);
  console.log(`开始时间：${startedAt}`);
  console.log(`运行模式：${dryRun ? '断网预演' : '正式执行'}`);
  console.log(`账号数量：${accounts.length}`);
  console.log('========================================');

  log('[1/3] 读取并检查任务配置');
  let configurationError = '';
  if (!accounts.length) {
    configurationError = '缺少必填环境变量 XMLY_LIST，或变量中没有非空账号行';
    log(`❌ 配置错误：${configurationError}`);
  } else {
    log(`✅ 已读取 ${accounts.length} 个账号；账号按行独立处理`);
  }

  log('[2/3] 处理账号任务');
  for (const account of accounts) {
    const result = await runAccount(account, dryRun, timeoutMilliseconds());
    results.push(result);
    printAccountStats(result);
  }

  const accountFailed = results.filter((item) => item.failed > 0).length;
  const accountSuccess = results.length - accountFailed;
  const totals = results.reduce((sum, item) => ({
    tasks: sum.tasks + item.tasks,
    success: sum.success + item.success,
    already: sum.already + item.already,
    skipped: sum.skipped + item.skipped,
    failed: sum.failed + item.failed,
  }), { tasks: 0, success: 0, already: 0, skipped: 0, failed: 0 });

  let finalStatus;
  let exitCode;
  if (configurationError) {
    finalStatus = 'configuration_error';
    exitCode = 2;
  } else if (accountFailed > 0) {
    finalStatus = accountSuccess > 0 ? 'partial_failure' : 'failure';
    exitCode = 1;
  } else if (dryRun) {
    finalStatus = 'dry_run';
    exitCode = 0;
  } else {
    finalStatus = 'success';
    exitCode = 0;
  }

  log('[3/3] 处理青龙通知');
  const notifyBody = `账号总数：${accounts.length}\n成功账号：${accountSuccess}\n失败账号：${accountFailed}\n任务状态：${finalStatus}`;
  const notification = await sendNotification(TASK_NAME, notifyBody, dryRun);
  if (notification === 'sent') log('✅ 青龙通知已发送');
  else if (notification === 'dry-run-skipped') log('⏭️ 断网预演：通知摘要已生成，但未调用通知脚本');
  else if (notification === 'not-selected') log('⏭️ 当前脚本未被通知策略选中');
  else log('⚠️ 未找到可用通知组件；业务退出码保持不变');

  const finishedAt = isoNow();
  const durationMs = Date.now() - taskStartedAt;
  console.log('========================================');
  console.log(`账号统计：总数 ${accounts.length}，成功 ${accountSuccess}，失败 ${accountFailed}`);
  console.log(`子任务统计：总数 ${totals.tasks}，成功 ${totals.success}，已完成 ${totals.already}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  console.log(`总耗时：${elapsed(taskStartedAt)}`);
  console.log(`完成时间：${finishedAt}`);
  console.log(`通知状态：${notification}`);
  console.log(`最终状态：${finalStatus}`);
  console.log('========================================');
  console.log(`TASK_SUMMARY=${JSON.stringify({
    task: TASK_NAME,
    catalogId: CATALOG_ID,
    mode: dryRun ? 'dry-run' : 'live',
    status: finalStatus,
    accounts: { total: accounts.length, success: accountSuccess, failed: accountFailed },
    subtasks: totals,
    notification,
    startedAt,
    finishedAt,
    durationMs,
  })}`);

  process.exitCode = exitCode;
}

main().catch((error) => {
  const finishedAt = isoNow();
  log(`❌ 未处理异常：${cleanText(error.message)}`);
  console.log(`TASK_SUMMARY=${JSON.stringify({
    task: TASK_NAME,
    catalogId: CATALOG_ID,
    mode: envEnabled('XMLY_DRY_RUN') ? 'dry-run' : 'live',
    status: 'failure',
    accounts: { total: 0, success: 0, failed: 0 },
    subtasks: { tasks: 0, success: 0, already: 0, skipped: 0, failed: 1 },
    notification: 'not-attempted',
    finishedAt,
  })}`);
  process.exitCode = 1;
});
