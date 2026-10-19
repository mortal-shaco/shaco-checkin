#!/usr/bin/env node
// name: 夸父资源社签到
// cron: 0 40 11 * * *
/*
 * 夸父资源社签到（独立维护版）
 * 上游来源：unitaryhighs/ql_sign_script/sign/kfzy.js
 * 上游项目标识：ql_sign_script : https://github.com/unitaryhighs/ql_sign_script
 * 许可证：MIT（保留上游署名与许可信息）
 *
 * 必需环境变量：
 *   KFZY_COOKIE_LIST  每行一个账号 Cookie，必须同时包含 bbs_sid 与 bbs_token。
 * 可选环境变量：
 *   KFZY_DRY_RUN=1    完全断网预演，仅校验配置，不执行签到。
 *   QINGLONG_NOTIFY   auto/1/0，默认 auto；设为 0 可关闭通知。
 *   QINGLONG_NOTIFY_SCRIPTS  通知脚本选择器；支持逗号、分号、空白分隔，* 表示全部。
 */

'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["ec84855cfbf1a288", "scripts/kfzy.js", "kfzy.js", "kfzy"];
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

const TASK_NAME = '夸父资源社签到';
const CATALOG_ID = 'ec84855cfbf1a288';
const DRY_RUN_ENV = 'KFZY_DRY_RUN';
const REQUEST_TIMEOUT_MS = 15000;
const MAX_RESPONSE_BYTES = 64 * 1024;
const ENDPOINT = 'https://www.kfzy.net/my-sign.htm';
const startedAt = Date.now();

function now() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false });
}

function isoNow() {
  return new Date().toISOString();
}

function elapsedText(start) {
  return `${Date.now() - start}ms`;
}

function isEnabled(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase());
}

function redactText(value) {
  return String(value == null ? '' : value)
    .replace(/(bbs_sid|bbs_token|cookie|token|session|authorization)\s*[=:]\s*[^\s;,]+/gi, '$1=[已隐藏]')
    .replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 240);
}

function safeIdentity(value, allowNumericUid = false) {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  const text = String(value).replace(/[\r\n\t]/g, ' ').trim().slice(0, 80);
  if (!text || /@/.test(text)) return '';
  if (!allowNumericUid && /^1[3-9]\d{9}$/.test(text)) return '';
  return text;
}

function findIdentity(payload) {
  const containers = [payload, payload && payload.data, payload && payload.user].filter(Boolean);
  const names = ['nickname', 'nickName', 'username', 'userName', 'displayName'];
  for (const container of containers) {
    if (typeof container !== 'object') continue;
    for (const key of names) {
      const identity = safeIdentity(container[key]);
      if (identity) return identity;
    }
  }
  const uidKeys = ['uid', 'userId', 'user_id'];
  for (const container of containers) {
    if (typeof container !== 'object') continue;
    for (const key of uidKeys) {
      const identity = safeIdentity(container[key], true);
      if (identity) return identity;
    }
  }
  return '';
}

function validCookie(cookie) {
  const fields = new Map();
  for (const part of cookie.split(';')) {
    const index = part.indexOf('=');
    if (index <= 0) continue;
    fields.set(part.slice(0, index).trim(), part.slice(index + 1).trim());
  }
  return Boolean(fields.get('bbs_sid') && fields.get('bbs_token'));
}

function requestSign(cookie) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finishReject = (error) => {
      if (settled) return;
      settled = true;
      reject(error);
    };
    const request = https.request(ENDPOINT, {
      method: 'POST',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        Cookie: cookie,
        Origin: 'https://www.kfzy.net',
        Referer: 'https://www.kfzy.net/',
        Accept: 'text/plain, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Length': '0'
      }
    }, (response) => {
      const chunks = [];
      let size = 0;
      response.on('data', (chunk) => {
        size += chunk.length;
        if (size > MAX_RESPONSE_BYTES) {
          response.destroy(new Error('响应体超过安全上限'));
          return;
        }
        chunks.push(chunk);
      });
      response.on('error', finishReject);
      response.on('end', () => {
        if (settled) return;
        settled = true;
        resolve({ statusCode: response.statusCode || 0, body: Buffer.concat(chunks).toString('utf8') });
      });
    });
    request.setTimeout(REQUEST_TIMEOUT_MS, () => request.destroy(new Error('请求超时')));
    request.on('error', finishReject);
    request.end();
  });
}

function evaluateResponse(response) {
  if (response.statusCode !== 200) {
    return { ok: false, state: 'failure', detail: `HTTP ${response.statusCode}` };
  }
  let payload;
  try {
    payload = JSON.parse(response.body);
  } catch (_error) {
    return { ok: false, state: 'failure', detail: '接口返回的不是有效 JSON' };
  }
  const code = payload && payload.code;
  const message = redactText(payload && (payload.message || payload.msg)) || '接口未返回说明';
  const identity = findIdentity(payload);
  if (String(code) === '0') {
    return { ok: true, state: 'success', detail: message, identity };
  }
  if (/(?:已|已经|今日).*签到|签到.*(?:已完成|完成过|重复)/.test(message)) {
    return { ok: true, state: 'alreadyComplete', detail: message, identity };
  }
  return { ok: false, state: 'failure', detail: `业务码 ${redactText(code)}：${message}`, identity };
}

function wildcardMatch(pattern, value) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
  return new RegExp(`^${escaped}$`, 'i').test(value);
}

function notificationEnabled() {
  const switchValue = String(process.env.QINGLONG_NOTIFY || 'auto').trim().toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(switchValue)) return { enabled: false, reason: '全局开关关闭' };
  if (switchValue !== 'auto' && !['1', 'true', 'yes', 'on'].includes(switchValue)) {
    console.log(`[${now()}] ⚠️ 未识别的 QINGLONG_NOTIFY 值，按 auto 处理`);
  }
  if (Object.prototype.hasOwnProperty.call(process.env, 'QINGLONG_NOTIFY_SCRIPTS')) {
    const raw = String(process.env.QINGLONG_NOTIFY_SCRIPTS || '').trim();
    if (!raw) return { enabled: false, reason: '脚本选择器为空' };
    const selectors = raw.split(/[,;\s]+/).filter(Boolean);
    const identities = [CATALOG_ID, 'sign/kfzy.js', 'kfzy.js', path.basename(__filename)];
    const matched = selectors.some((selector) => selector === '*' || identities.some((id) => wildcardMatch(selector, id)));
    if (!matched) return { enabled: false, reason: '脚本未被通知选择器选中' };
  }
  return { enabled: true, reason: '' };
}

async function sendNotification(body) {
  const policy = notificationEnabled();
  if (!policy.enabled) return { status: 'skipped', detail: policy.reason };
  const candidates = [];
  if (process.env.QINGLONG_NOTIFY_DIR) {
    candidates.push(path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'));
  }
  candidates.push('/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js');
  for (const candidate of [...new Set(candidates)]) {
    if (!fs.existsSync(candidate)) continue;
    try {
      const moduleValue = require(candidate);
      const sender = typeof moduleValue === 'function'
        ? moduleValue
        : moduleValue.sendNotify || moduleValue.default;
      if (typeof sender !== 'function') continue;
      await sender(TASK_NAME, body);
      return { status: 'sent', detail: '通知已发送' };
    } catch (error) {
      return { status: 'failed', detail: `通知发送失败：${redactText(error.message)}` };
    }
  }
  return { status: 'unavailable', detail: '未发现 Qinglong sendNotify.js，业务退出码保持不变' };
}

function printAccountStats(index, stats, accountStart) {
  console.log(`[${now()}] 账号 ${index} 统计：总任务=${stats.total}，成功=${stats.success}，已完成=${stats.alreadyComplete}，跳过=${stats.skipped}，失败=${stats.failure}，耗时=${elapsedText(accountStart)}`);
}

async function main() {
  const dryRun = isEnabled(process.env[DRY_RUN_ENV]);
  const rawAccounts = String(process.env.KFZY_COOKIE_LIST || '');
  const accounts = rawAccounts.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const totals = { accounts: accounts.length, accountSuccess: 0, accountFailure: 0, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };

  console.log('========================================');
  console.log(`【${TASK_NAME}】`);
  console.log(`开始时间：${isoNow()}`);
  console.log(`运行模式：${dryRun ? 'DRY-RUN（完全断网）' : 'LIVE'}`);
  console.log(`账号数量：${accounts.length}`);
  console.log('========================================');

  if (accounts.length === 0) {
    console.log(`[${now()}] ❌ 配置错误：缺少 KFZY_COOKIE_LIST，每行应填写一个账号 Cookie`);
    totals.accountFailure = 1;
    totals.failure = 1;
  } else {
    for (let offset = 0; offset < accounts.length; offset += 1) {
      const index = offset + 1;
      const accountStart = Date.now();
      const stats = { total: 1, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
      totals.total += 1;
      console.log(`\n[${now()}] —— 账号 ${index}/${accounts.length} ——`);
      const stageStart = Date.now();
      console.log(`[${now()}] [1/2] 校验账号参数`);
      if (!validCookie(accounts[offset])) {
        stats.failure = 1;
        totals.failure += 1;
        totals.accountFailure += 1;
        console.log(`[${now()}] ❌ 参数无效：Cookie 必须包含非空的 bbs_sid 和 bbs_token（耗时 ${elapsedText(stageStart)}）`);
        console.log(`[${now()}] [2/2] ⏭️ 跳过签到请求`);
        printAccountStats(index, stats, accountStart);
        continue;
      }
      console.log(`[${now()}] ✅ 参数格式有效（耗时 ${elapsedText(stageStart)}）`);
      const requestStart = Date.now();
      console.log(`[${now()}] [2/2] ${dryRun ? '预演签到' : '执行签到请求'}`);
      if (dryRun) {
        stats.skipped = 1;
        totals.skipped += 1;
        totals.accountSuccess += 1;
        console.log(`[${now()}] ⏭️ DRY-RUN 校验通过，未发起任何网络请求或签到（耗时 ${elapsedText(requestStart)}）`);
        printAccountStats(index, stats, accountStart);
        continue;
      }
      try {
        const response = await requestSign(accounts[offset]);
        const result = evaluateResponse(response);
        const label = result.identity ? `（官方身份：${result.identity}）` : '';
        if (result.ok && result.state === 'success') {
          stats.success = 1;
          totals.success += 1;
          totals.accountSuccess += 1;
          console.log(`[${now()}] ✅ 签到成功${label}：${result.detail}（耗时 ${elapsedText(requestStart)}）`);
        } else if (result.ok) {
          stats.alreadyComplete = 1;
          totals.alreadyComplete += 1;
          totals.accountSuccess += 1;
          console.log(`[${now()}] ☑️ 今日已完成${label}：${result.detail}（耗时 ${elapsedText(requestStart)}）`);
        } else {
          stats.failure = 1;
          totals.failure += 1;
          totals.accountFailure += 1;
          console.log(`[${now()}] ❌ 签到失败${label}：${result.detail}（耗时 ${elapsedText(requestStart)}）`);
        }
      } catch (error) {
        stats.failure = 1;
        totals.failure += 1;
        totals.accountFailure += 1;
        console.log(`[${now()}] ❌ 请求失败：${redactText(error.message)}（耗时 ${elapsedText(requestStart)}）`);
      }
      printAccountStats(index, stats, accountStart);
    }
  }

  const businessExitCode = totals.accountFailure > 0 ? 1 : 0;
  const modeLabel = dryRun ? 'DRY-RUN' : 'LIVE';
  const notificationBody = `${modeLabel}：账号总数 ${totals.accounts}，成功 ${totals.accountSuccess}，失败 ${totals.accountFailure}；子任务成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failure}。`;
  console.log(`\n[${now()}] [通知] 发送脱敏任务总结`);
  const notification = await sendNotification(notificationBody);
  const notifyIcon = notification.status === 'sent' ? '✅' : notification.status === 'skipped' ? '⏭️' : '⚠️';
  console.log(`[${now()}] ${notifyIcon} ${notification.detail}`);

  const finalStatus = businessExitCode === 0 ? (dryRun ? 'dry-run-success' : 'success') : (totals.accountSuccess > 0 ? 'partial-failure' : 'failure');
  const summary = {
    task: TASK_NAME,
    mode: modeLabel,
    accounts: totals.accounts,
    accountSuccess: totals.accountSuccess,
    accountFailure: totals.accountFailure,
    tasks: { total: totals.total, success: totals.success, alreadyComplete: totals.alreadyComplete, skipped: totals.skipped, failure: totals.failure },
    notification: notification.status,
    status: finalStatus,
    exitCode: businessExitCode,
    durationMs: Date.now() - startedAt,
    finishedAt: isoNow()
  };
  console.log('\n========================================');
  console.log(`账号结果：总数=${totals.accounts}，成功=${totals.accountSuccess}，失败=${totals.accountFailure}`);
  console.log(`子任务结果：总数=${totals.total}，成功=${totals.success}，已完成=${totals.alreadyComplete}，跳过=${totals.skipped}，失败=${totals.failure}`);
  console.log(`总耗时：${summary.durationMs}ms`);
  console.log(`完成时间：${summary.finishedAt}`);
  console.log(`通知状态：${notification.status}`);
  console.log(`最终状态：${finalStatus}`);
  console.log('========================================');
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = businessExitCode;
}

main().catch(async (error) => {
  const detail = redactText(error && error.message) || '未知异常';
  console.error(`[${now()}] ❌ 未处理异常：${detail}`);
  const notification = await sendNotification('任务异常终止：账号总数 0，成功 0，失败 1。');
  const summary = {
    task: TASK_NAME,
    mode: isEnabled(process.env[DRY_RUN_ENV]) ? 'DRY-RUN' : 'LIVE',
    accounts: 0,
    accountSuccess: 0,
    accountFailure: 1,
    tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 1 },
    notification: notification.status,
    status: 'failure',
    exitCode: 1,
    durationMs: Date.now() - startedAt,
    finishedAt: isoNow()
  };
  console.log(`完成时间：${summary.finishedAt}`);
  console.log('最终状态：failure');
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = 1;
});
