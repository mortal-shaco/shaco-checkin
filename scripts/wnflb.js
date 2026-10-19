#!/usr/bin/env node
// name: 万能福利吧每日签到
// cron: 0 45 11 * * *
// SPDX-License-Identifier: MIT
// 上游来源：ql_sign_script : https://github.com/unitaryhighs/ql_sign_script
// 原脚本名称：万能福利吧（sign/wnflb.js）

'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["0958709b5f55078a", "scripts/wnflb.js", "wnflb.js", "wnflb"];
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

const TASK_NAME = '万能福利吧签到';
const CATALOG_ID = '0958709b5f55078a';
const COOKIE_ENV = 'WNFLB_COOKIE_LIST';
const DRY_RUN_ENV = 'WNFLB_DRY_RUN';
const LIST_URL = 'https://www.wnflb2023.com/plugin.php?id=fx_checkin:list';
const CHECKIN_URL = 'https://www.wnflb2023.com/plugin.php?id=fx_checkin%3Acheckin&infloat=yes&handlekey=fx_checkin&inajax=1&ajaxtarget=fwin_content_fx_checkin';
const ALLOWED_HOST = 'www.wnflb2023.com';
const REQUEST_TIMEOUT_MS = 12_000;
const NOTIFY_TIMEOUT_MS = 15_000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const TRUE_VALUES = new Set(['1', 'true', 'yes', 'on']);
const FALSE_VALUES = new Set(['0', 'false', 'no', 'off']);
const SCRIPT_SELECTORS = [CATALOG_ID, 'wnflb.js', 'candidate.js', 'output/candidate.js'];

function nowText() {
  return new Date().toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
}

function timeText() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
}

function log(message) {
  console.log(`[${timeText()}] ${message}`);
}

function elapsed(startedAt) {
  return `${((Date.now() - startedAt) / 1000).toFixed(2)} 秒`;
}

function isEnabled(value) {
  return TRUE_VALUES.has(String(value || '').trim().toLowerCase());
}

function parseAccounts(raw) {
  return String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function validateCookie(cookie) {
  if (!cookie || !cookie.includes('=')) {
    throw new Error(`配置项 ${COOKIE_ENV} 中有账号不是有效的 Cookie 格式`);
  }
  if (/\r|\n/.test(cookie)) {
    throw new Error('单个账号 Cookie 不能包含换行符');
  }
}

function decodeEntities(text) {
  return String(text || '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)));
}

function cleanText(text, maxLength = 120) {
  return decodeEntities(text).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, maxLength);
}

function visibleIdentity(identity) {
  const cleaned = cleanText(identity, 80);
  if (!cleaned) return '';
  if (/^(?:\+?86[- ]?)?1\d{10}$/.test(cleaned.replace(/[- ]/g, ''))) {
    return '已获取（疑似手机号，按安全规则隐藏）';
  }
  return cleaned;
}

function matchFirst(html, patterns) {
  for (const pattern of patterns) {
    const matched = pattern.exec(html);
    if (matched && matched[1]) return cleanText(matched[1]);
  }
  return '';
}

function parsePage(html) {
  const formhash = matchFirst(html, [
    /(?:[?&]|\b)formhash=["']?([a-f0-9]{8})(?:[&"'\s<]|$)/i,
    /name=["']formhash["'][^>]*value=["']([a-f0-9]{8})["']/i,
  ]);
  const points = matchFirst(html, [
    /showmenu["'][^>]*>\s*积分\s*[:：]\s*([^<]+)<\/a>/i,
    /积分\s*[:：]\s*<[^>]*>\s*([^<]+)</i,
  ]);
  const totalDays = matchFirst(html, [/累计签到\s*[:：]\s*<i[^>]*>\s*([^<]+)<\/i>\s*天/i]);
  const continuousDays = matchFirst(html, [/已连续签到\s*[:：]\s*<i[^>]*>\s*([^<]+)<\/i>\s*天/i]);
  const identity = matchFirst(html, [
    /class=["'][^"']*vwmy[^"']*["'][^>]*>\s*<a[^>]*>([^<]+)<\/a>/i,
    /title=["']访问我的空间["'][^>]*>([^<]+)<\/a>/i,
  ]);
  return { formhash, points, totalDays, continuousDays, identity: visibleIdentity(identity) };
}

function decodeBody(buffer, contentType) {
  const charsetMatch = /charset\s*=\s*([\w-]+)/i.exec(contentType || '');
  const requested = charsetMatch ? charsetMatch[1].toLowerCase() : 'utf-8';
  const charset = requested === 'gb2312' ? 'gb18030' : requested;
  try {
    return new TextDecoder(charset).decode(buffer);
  } catch {
    return buffer.toString('utf8');
  }
}

function safeNetworkError(error) {
  const message = error && typeof error.message === 'string' ? error.message : '';
  const safeMessages = [
    '响应内容超过安全上限',
    '请求超时',
    '请求地址无效',
    '已阻止向非预期站点发送账号凭据',
    '重定向次数过多',
    '未取得 formhash，Cookie 可能已失效',
    '签到接口明确拒绝请求',
    '签到接口未返回可确认的成功状态',
    '签到页未返回累计或连续签到天数，无法验证结果',
    '签到页未返回当前积分，无法验证结果',
    '单个账号 Cookie 不能包含换行符',
  ];
  if (safeMessages.includes(message) || message.startsWith(`配置项 ${COOKIE_ENV} `)) return message;
  if (/^请求返回 HTTP \d{3}$/.test(message)) return message;
  const code = error && typeof error.code === 'string' ? error.code : 'NETWORK_ERROR';
  return `网络请求失败（${code}）`;
}

function requestGet(url, cookie, redirects = 0) {
  return new Promise((resolve, reject) => {
    let target;
    try {
      target = new URL(url);
    } catch {
      reject(new Error('请求地址无效'));
      return;
    }
    if (target.protocol !== 'https:' || target.hostname !== ALLOWED_HOST) {
      reject(new Error('已阻止向非预期站点发送账号凭据'));
      return;
    }

    const request = https.request(target, {
      method: 'GET',
      headers: {
        Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'identity',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        Cookie: cookie,
        Referer: 'https://www.wnflb2023.com/',
        'User-Agent': 'Mozilla/5.0 (Qinglong; WNFLB maintained script)',
        'X-Requested-With': 'XMLHttpRequest',
      },
    }, (response) => {
      const statusCode = response.statusCode || 0;
      if ([301, 302, 303, 307, 308].includes(statusCode) && response.headers.location) {
        response.resume();
        if (redirects >= 3) {
          reject(new Error('重定向次数过多'));
          return;
        }
        const redirected = new URL(response.headers.location, target);
        if (redirected.protocol !== 'https:' || redirected.hostname !== ALLOWED_HOST) {
          reject(new Error('已阻止向非预期站点发送账号凭据'));
          return;
        }
        requestGet(redirected.toString(), cookie, redirects + 1).then(resolve, reject);
        return;
      }
      if (statusCode < 200 || statusCode >= 300) {
        response.resume();
        reject(new Error(`请求返回 HTTP ${statusCode}`));
        return;
      }

      const chunks = [];
      let size = 0;
      response.on('data', (chunk) => {
        size += chunk.length;
        if (size > MAX_RESPONSE_BYTES) {
          response.destroy(new Error('响应内容超过安全上限'));
          return;
        }
        chunks.push(chunk);
      });
      response.on('end', () => {
        const body = Buffer.concat(chunks);
        resolve({ body: decodeBody(body, response.headers['content-type']), statusCode });
      });
      response.on('error', reject);
    });

    request.setTimeout(REQUEST_TIMEOUT_MS, () => request.destroy(new Error('请求超时')));
    request.on('error', reject);
    request.end();
  });
}

function classifyCheckin(body) {
  const message = cleanText(body, 500);
  if (/已经?签到|已签到|签到过|无需重复|重复签到|今日已(?:经)?签到/.test(message)) {
    return { ok: true, alreadyComplete: true, detail: '今日已签到' };
  }
  if (/签到成功|恭喜.{0,30}签到|成功.{0,20}(积分|金币)|获得.{0,20}(积分|金币)/.test(message)) {
    return { ok: true, alreadyComplete: false, detail: '签到接口确认成功' };
  }
  if (/请先登录|需要登录|登录后|无权|非法|过期|签到失败|操作失败|错误/.test(message)) {
    return { ok: false, alreadyComplete: false, detail: '签到接口明确拒绝请求' };
  }
  return { ok: false, alreadyComplete: false, detail: '签到接口未返回可确认的成功状态' };
}

async function runStage(accountLabel, number, name, action) {
  const startedAt = Date.now();
  log(`${accountLabel}｜阶段 ${number}：${name}`);
  try {
    const value = await action();
    log(`${accountLabel}｜✅ 阶段 ${number} 完成，耗时 ${elapsed(startedAt)}`);
    return value;
  } catch (error) {
    log(`${accountLabel}｜❌ 阶段 ${number} 失败：${safeNetworkError(error)}，耗时 ${elapsed(startedAt)}`);
    throw error;
  }
}

async function runDryAccount(index, cookie) {
  const label = `账号 ${index + 1}`;
  const startedAt = Date.now();
  const result = { total: 2, success: 0, already: 0, skipped: 0, failed: 0 };
  try {
    await runStage(label, 1, '校验账号配置', async () => {
      validateCookie(cookie);
      result.success += 1;
    });
    await runStage(label, 2, '检查离线执行计划', async () => {
      log(`${label}｜⏭️ dry-run 已验证三步签到流程，不发起网络请求，也不调用通知模块`);
      result.success += 1;
    });
    log(`${label}｜结果：✅ 预演通过`);
    return { ok: true, result, durationMs: Date.now() - startedAt };
  } catch {
    result.failed += 1;
    result.skipped = Math.max(0, result.total - result.success - result.already - result.failed);
    log(`${label}｜结果：❌ 预演失败`);
    return { ok: false, result, durationMs: Date.now() - startedAt };
  }
}

async function runLiveAccount(index, cookie) {
  const label = `账号 ${index + 1}`;
  const startedAt = Date.now();
  const result = { total: 3, success: 0, already: 0, skipped: 0, failed: 0 };
  try {
    validateCookie(cookie);
    const before = await runStage(label, 1, '读取 formhash 与签到前积分', async () => {
      const response = await requestGet(LIST_URL, cookie);
      const parsed = parsePage(response.body);
      if (!parsed.formhash) throw new Error('未取得 formhash，Cookie 可能已失效');
      if (parsed.identity) log(`${label}｜账号身份：${parsed.identity}`);
      log(`${label}｜签到前积分：${parsed.points || '页面未提供'}`);
      result.success += 1;
      return parsed;
    });

    const checkin = await runStage(label, 2, '提交每日签到', async () => {
      const url = `${CHECKIN_URL}&formhash=${encodeURIComponent(before.formhash)}&${encodeURIComponent(before.formhash)}`;
      const response = await requestGet(url, cookie);
      const checked = classifyCheckin(response.body);
      if (!checked.ok) throw new Error(checked.detail);
      if (checked.alreadyComplete) {
        result.already += 1;
        log(`${label}｜☑️ ${checked.detail}`);
      } else {
        result.success += 1;
        log(`${label}｜✅ ${checked.detail}`);
      }
      return checked;
    });

    const after = await runStage(label, 3, '回查签到结果', async () => {
      const response = await requestGet(LIST_URL, cookie);
      const parsed = parsePage(response.body);
      if (!parsed.totalDays && !parsed.continuousDays) {
        throw new Error('签到页未返回累计或连续签到天数，无法验证结果');
      }
      if (!parsed.points) throw new Error('签到页未返回当前积分，无法验证结果');
      log(`${label}｜累计签到：${parsed.totalDays || '页面未提供'} 天`);
      log(`${label}｜连续签到：${parsed.continuousDays || '页面未提供'} 天`);
      log(`${label}｜当前积分：${parsed.points}`);
      result.success += 1;
      return parsed;
    });

    const state = checkin.alreadyComplete ? '☑️ 今日已完成' : '✅ 签到成功';
    log(`${label}｜结果：${state}；积分 ${before.points || '未知'} → ${after.points}`);
    return { ok: true, result, durationMs: Date.now() - startedAt };
  } catch (error) {
    result.failed += 1;
    result.skipped = Math.max(0, result.total - result.success - result.already - result.failed);
    log(`${label}｜结果：❌ ${safeNetworkError(error)}`);
    return { ok: false, result, durationMs: Date.now() - startedAt };
  }
}

function wildcardMatches(pattern, value) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
  return new RegExp(`^${escaped}$`, 'i').test(value);
}

function notificationRequested() {
  const globalValue = String(process.env.QINGLONG_NOTIFY || 'auto').trim().toLowerCase();
  if (FALSE_VALUES.has(globalValue)) return false;
  const hasSelection = Object.prototype.hasOwnProperty.call(process.env, 'QINGLONG_NOTIFY_SCRIPTS');
  if (hasSelection) {
    const raw = String(process.env.QINGLONG_NOTIFY_SCRIPTS || '');
    if (!raw.trim()) return false;
    const selectors = raw.split(/[,;\s]+/).filter(Boolean);
    return selectors.some((selector) => selector === '*' || SCRIPT_SELECTORS.some((item) => wildcardMatches(selector, item)));
  }
  return TRUE_VALUES.has(globalValue);
}

function notifierCandidates() {
  const candidates = [];
  if (process.env.QINGLONG_NOTIFY_DIR) {
    candidates.push(path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'));
  }
  candidates.push('/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js');
  return [...new Set(candidates)];
}

async function sendNotification(body, dryRun) {
  if (dryRun) return 'skipped-dry-run-offline';
  if (!notificationRequested()) return 'disabled';
  for (const candidate of notifierCandidates()) {
    if (!fs.existsSync(candidate)) continue;
    try {
      const loaded = require(candidate);
      const sender = typeof loaded === 'function'
        ? loaded
        : loaded.sendNotify || loaded.default?.sendNotify || loaded.default;
      if (typeof sender !== 'function') continue;
      let timer;
      try {
        await Promise.race([
          Promise.resolve().then(() => sender(TASK_NAME, body)),
          new Promise((_, reject) => {
            timer = setTimeout(() => reject(new Error('通知超时')), NOTIFY_TIMEOUT_MS);
          }),
        ]);
      } finally {
        clearTimeout(timer);
      }
      return 'sent';
    } catch (error) {
      log(`⚠️ 通知发送失败（${path.basename(candidate)}），不改变业务退出码`);
      return 'failed';
    }
  }
  log('⚠️ 未找到可用的 sendNotify.js，不改变业务退出码');
  return 'unavailable';
}

function aggregate(results) {
  return results.reduce((all, item) => {
    all.totalTasks += item.result.total;
    all.succeededTasks += item.result.success;
    all.alreadyCompletedTasks += item.result.already;
    all.skippedTasks += item.result.skipped;
    all.failedTasks += item.result.failed;
    return all;
  }, { totalTasks: 0, succeededTasks: 0, alreadyCompletedTasks: 0, skippedTasks: 0, failedTasks: 0 });
}

async function main() {
  const taskStartedAt = Date.now();
  const dryRun = isEnabled(process.env[DRY_RUN_ENV]);
  const accounts = parseAccounts(process.env[COOKIE_ENV]);
  console.log('='.repeat(64));
  console.log(`【${TASK_NAME}】`);
  console.log(`开始时间：${nowText()}`);
  console.log(`运行模式：${dryRun ? 'dry-run（完全断网）' : 'live'}`);
  console.log(`账号数量：${accounts.length}`);
  console.log('='.repeat(64));

  const results = [];
  let configurationError = false;
  if (accounts.length === 0) {
    configurationError = true;
    log(`❌ 配置错误：缺少必填环境变量 ${COOKIE_ENV}；请按每行一个账号填写 Cookie`);
  } else {
    for (let index = 0; index < accounts.length; index += 1) {
      console.log('-'.repeat(64));
      results.push(dryRun
        ? await runDryAccount(index, accounts[index])
        : await runLiveAccount(index, accounts[index]));
      const account = results[results.length - 1];
      log(`账号 ${index + 1}｜统计：总任务 ${account.result.total}，成功 ${account.result.success}，已完成 ${account.result.already}，跳过 ${account.result.skipped}，失败 ${account.result.failed}，耗时 ${(account.durationMs / 1000).toFixed(2)} 秒`);
    }
  }

  const taskStats = aggregate(results);
  if (configurationError) {
    taskStats.totalTasks = 1;
    taskStats.failedTasks = 1;
  }
  const successAccounts = results.filter((item) => item.ok).length;
  const failedAccounts = configurationError ? 0 : results.length - successAccounts;
  let status;
  if (configurationError) status = 'configuration-error';
  else if (failedAccounts > 0 && successAccounts > 0) status = 'partial-failure';
  else if (failedAccounts > 0) status = 'failure';
  else status = dryRun ? 'dry-run-success' : 'success';

  const notificationBody = [
    `模式：${dryRun ? 'dry-run' : 'live'}`,
    `账号总数：${accounts.length}`,
    `成功账号：${successAccounts}`,
    `失败账号：${failedAccounts}`,
    `最终状态：${status}`,
  ].join('\n');
  const notification = await sendNotification(notificationBody, dryRun);
  const finishTime = nowText();
  const durationMs = Date.now() - taskStartedAt;
  const statusLabel = {
    success: '成功',
    'dry-run-success': '预演成功',
    'partial-failure': '部分失败',
    failure: '失败',
    'configuration-error': '配置错误',
  }[status];

  console.log('='.repeat(64));
  console.log('任务统计');
  console.log(`账号结果：总数 ${accounts.length}，成功 ${successAccounts}，失败 ${failedAccounts}`);
  console.log(`子任务结果：总数 ${taskStats.totalTasks}，成功 ${taskStats.succeededTasks}，已完成 ${taskStats.alreadyCompletedTasks}，跳过 ${taskStats.skippedTasks}，失败 ${taskStats.failedTasks}`);
  console.log(`总耗时：${(durationMs / 1000).toFixed(2)} 秒`);
  console.log(`完成时间：${finishTime}`);
  console.log(`通知状态：${notification}`);
  console.log(`最终状态：${statusLabel}`);
  console.log('='.repeat(64));

  const summary = {
    status,
    mode: dryRun ? 'dry-run' : 'live',
    accountCount: accounts.length,
    successAccounts,
    failedAccounts,
    ...taskStats,
    durationMs,
    notification,
    finishedAt: finishTime,
  };
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = status === 'success' || status === 'dry-run-success' ? 0 : 1;
}

main().catch((error) => {
  const finishTime = nowText();
  console.error(`[${timeText()}] ❌ 未预期的内部错误，凭据与原始响应已隐藏`);
  console.log(`完成时间：${finishTime}`);
  console.log('最终状态：失败');
  console.log(`TASK_SUMMARY=${JSON.stringify({
    status: 'failure',
    mode: isEnabled(process.env[DRY_RUN_ENV]) ? 'dry-run' : 'live',
    accountCount: 0,
    successAccounts: 0,
    failedAccounts: 0,
    totalTasks: 1,
    succeededTasks: 0,
    alreadyCompletedTasks: 0,
    skippedTasks: 0,
    failedTasks: 1,
    notification: 'not-attempted',
    finishedAt: finishTime,
  })}`);
  process.exitCode = 1;
});
