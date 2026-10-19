#!/usr/bin/env node
// name: 小牛电动社区任务（安全维护版）
// cron: 40 1 * * *
/**
 * 小牛电动 APP 社区任务（安全维护版）
 *
 * 必填：XNIU_TOKEN，每行一个账号，格式为“访问令牌#公开用户ID”。
 * 获取方法：登录小牛电动 APP，在本人设备抓取 app-api.niu.com 请求头中的 token，
 * 同时从本人资料接口确认公开 user_id。请勿填写手机号或密码。
 *
 * 可选开关（值为 1 时开启）：
 * XNIU_ENABLE_COMMENT  自动回答；默认关闭
 * XNIU_ENABLE_SHARE    分享文章；默认关闭
 * XNIU_ENABLE_FOLLOW 与 XNIU_ENABLE_UNFOLLOW 必须同时为 1，才执行可恢复的关注状态循环；默认关闭
 * XNIU_DRY_RUN         无网络预演；值为 1 时不发起任何网络请求
 *
 * 多账号仅使用换行分隔，不再接受 & 分隔，也不接受旧版手机号#密码参数。
 *
 * @author Telegram@sudojia
 * @site https://blog.imzjw.cn
 * @date 2024/08/26
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * Copyright and attribution notices from the upstream script are retained above.
 * This maintained derivative is distributed under GPL-3.0-only.
 */

'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["9ba3d61418ae2582", "scripts/sudojia_xniu.js", "sudojia_xniu.js", "sudojia_xniu"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const TASK_NAME = '小牛电动';
const CATALOG_ID = '9ba3d61418ae2582';
const BASE_URL = 'https://app-api.niu.com';
const TEXT_PROVIDER_URL = 'https://v1.hitokoto.cn/?encode=json';
const REQUEST_TIMEOUT_MS = 12_000;
const PROVIDER_TIMEOUT_MS = 8_000;
const MAX_API_BYTES = 1024 * 1024;
const MAX_PROVIDER_BYTES = 16_384;
const DEFAULT_FALLBACK_TEXT = '愿每一次出发都有收获，也愿每一段旅程平安顺利。';
const TRUE_VALUES = new Set(['1', 'true', 'yes', 'on']);
const FALSE_VALUES = new Set(['0', 'false', 'no', 'off']);
const CITY_CODES = [
  '110000', '120000', '310000', '440100', '440300', '320400',
  '441900', '442000', '441300', '440700', '431100', '371000',
];

const BASE_HEADERS = Object.freeze({
  'User-Agent': 'manager/5.7.4 (android; OPPO R9s 9);lang=zh-CN;clientIdentifier=Domestic;timezone=Asia/Shanghai;model=OPPO_OPPO R9s;deviceName=OPPO R9s;ostype=android',
  'Content-Type': 'application/json',
  'Accept-Encoding': 'gzip',
  Accept: 'application/json',
});

class TaskError extends Error {
  constructor(code, safeMessage) {
    super(safeMessage);
    this.name = 'TaskError';
    this.code = code;
  }
}

function nowTime() {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date());
}

function nowDateTime() {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date());
}

function elapsed(startedAt) {
  return `${Date.now() - startedAt}ms`;
}

function enabled(name) {
  return TRUE_VALUES.has(String(process.env[name] || '').trim().toLowerCase());
}

function safeError(error) {
  if (error instanceof TaskError) return error.message;
  if (error && error.name === 'AbortError') return '请求超时';
  return '请求或处理发生异常';
}

function parseAccounts() {
  const raw = process.env.XNIU_TOKEN || '';
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const delimiter = line.indexOf('#');
      if (delimiter <= 0 || delimiter === line.length - 1) {
        throw new TaskError('CONFIG_FORMAT', `第 ${index + 1} 行账号格式错误，应为“访问令牌#公开用户ID”`);
      }
      const token = line.slice(0, delimiter).trim();
      const userId = line.slice(delimiter + 1).trim();
      if (!token || !userId || /[\r\n]/.test(token) || /[\r\n]/.test(userId)) {
        throw new TaskError('CONFIG_FORMAT', `第 ${index + 1} 行账号格式错误，应为“访问令牌#公开用户ID”`);
      }
      return { token, userId };
    });
}

function createStats() {
  return { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
}

function record(stats, status) {
  stats.total += 1;
  if (status === 'success') stats.success += 1;
  else if (status === 'alreadyComplete') stats.alreadyComplete += 1;
  else if (status === 'skipped') stats.skipped += 1;
  else stats.failed += 1;
}

function stageLog(accountIndex, stageIndex, stageName, status, message, startedAt) {
  const icons = {
    success: '✅',
    alreadyComplete: '☑️',
    skipped: '⏭️',
    warning: '⚠️',
    failure: '❌',
  };
  console.log(`[${nowTime()}] [账号 ${accountIndex}] [阶段 ${stageIndex}] ${stageName} ${icons[status] || icons.warning} ${message}（${elapsed(startedAt)}）`);
}

async function runStage(context, stageName, action, options = {}) {
  const stageIndex = ++context.stageIndex;
  const startedAt = Date.now();
  console.log(`[${nowTime()}] [账号 ${context.index}] [阶段 ${stageIndex}] 开始：${stageName}`);
  if (options.skip) {
    record(context.stats, 'skipped');
    stageLog(context.index, stageIndex, stageName, 'skipped', options.skip, startedAt);
    return null;
  }
  try {
    const result = await action();
    const status = result && result.alreadyComplete ? 'alreadyComplete' : 'success';
    const message = result && result.message ? result.message : '已通过业务成功校验';
    record(context.stats, status);
    stageLog(context.index, stageIndex, stageName, status, message, startedAt);
    return result;
  } catch (error) {
    record(context.stats, 'failure');
    stageLog(context.index, stageIndex, stageName, 'failure', safeError(error), startedAt);
    context.failed = true;
    return null;
  }
}

async function requestJson(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      method: options.method || 'GET',
      headers: options.headers || {},
      body: options.body,
      redirect: 'error',
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new TaskError('HTTP_STATUS', `服务返回 HTTP ${response.status}`);
    }
    const buffer = new Uint8Array(await response.arrayBuffer());
    const maxBytes = options.maxBytes || MAX_API_BYTES;
    if (buffer.byteLength > maxBytes) {
      throw new TaskError('OVERSIZED_RESPONSE', '服务响应超过允许大小');
    }
    try {
      return JSON.parse(new TextDecoder().decode(buffer));
    } catch {
      throw new TaskError('INVALID_JSON', '服务响应不是有效 JSON');
    }
  } catch (error) {
    if (error instanceof TaskError) throw error;
    if (error && error.name === 'AbortError') throw new TaskError('TIMEOUT', '请求超时');
    throw new TaskError('NETWORK_ERROR', '网络请求失败');
  } finally {
    clearTimeout(timeout);
  }
}

function accountHeaders(account) {
  return { ...BASE_HEADERS, token: account.token };
}

function requireStatusZero(data, operation) {
  if (!data || data.status !== 0) {
    throw new TaskError('BUSINESS_FAILURE', `${operation}未通过业务状态校验`);
  }
  return data.data;
}

function pickRandom(items, operation) {
  if (!Array.isArray(items) || items.length === 0) {
    throw new TaskError('EMPTY_RESULT', `${operation}未返回可用项目`);
  }
  return items[Math.floor(Math.random() * items.length)];
}

async function getProfile(account, userId = account.userId) {
  const url = `${BASE_URL}/community/api/user/profile?user_id=${encodeURIComponent(userId)}`;
  const data = await requestJson(url, { headers: accountHeaders(account) });
  return requireStatusZero(data, '资料查询');
}

async function queryOwnProfile(account) {
  const profile = await getProfile(account);
  const identity = profile && (profile.user_nick_name ?? profile.nick_name ?? profile.user_name);
  if (identity === undefined || identity === null || String(identity).length === 0) {
    throw new TaskError('IDENTITY_MISSING', '资料查询成功，但未返回可核对的公开身份');
  }
  console.log(`[${nowTime()}] 官方身份：${identity}`);
  return { message: `已核对官方返回身份：${identity}` };
}

async function readGuide(account) {
  const url = `${BASE_URL}/community/api/posts/detail?id=1940&version=2&_=${Date.now()}`;
  const data = await requestJson(url, { headers: accountHeaders(account) });
  requireStatusZero(data, '社区指引读取');
  return { message: '社区指引读取成功' };
}

async function queryPoints(account) {
  const data = await requestJson(`${BASE_URL}/v5/points/index`, { headers: accountHeaders(account) });
  const payload = requireStatusZero(data, '积分查询');
  if (!payload || payload.userPoints === undefined || payload.userPoints === null) {
    throw new TaskError('POINTS_MISSING', '积分查询成功，但未返回积分字段');
  }
  console.log(`[${nowTime()}] 当前积分：${payload.userPoints}`);
  return { message: `当前积分：${payload.userPoints}` };
}

function normalizedText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function localFallbackText() {
  const configured = normalizedText(process.env.XNIU_FALLBACK_TEXT);
  if (configured && configured.length <= 280) return configured;
  return DEFAULT_FALLBACK_TEXT;
}

async function getPublicText() {
  try {
    // 此请求有意不复用账号请求头，确保 token 不会发送给第三方文案服务。
    const data = await requestJson(TEXT_PROVIDER_URL, {
      headers: { Accept: 'application/json', 'User-Agent': 'Qinglong-XNIU/1.0' },
      timeoutMs: PROVIDER_TIMEOUT_MS,
      maxBytes: MAX_PROVIDER_BYTES,
    });
    const text = normalizedText(data && data.hitokoto);
    const author = normalizedText(data && data.from_who);
    const source = normalizedText(data && data.from);
    if (!text) throw new TaskError('MISSING_TEXT', '随机文案缺少正文');
    let formatted = text;
    if (author && source) formatted = `${text} —— ${author}《${source}》`;
    else if (source) formatted = `${text} ——《${source}》`;
    else if (author) formatted = `${text} —— ${author}`;
    formatted = normalizedText(formatted);
    if (formatted.length > 280) throw new TaskError('OVERLONG_TEXT', '随机文案超过 280 字');
    console.log(`[${nowTime()}] 随机文案来源：一言（未发送账号凭据）`);
    return formatted;
  } catch (error) {
    console.log(`[${nowTime()}] ⚠️ 随机文案不可用（${safeError(error)}），已改用本地文案`);
    return localFallbackText();
  }
}

async function postAnswer(account) {
  const listUrl = `${BASE_URL}/community/api/qa/list?type=2&category_id=&page=1&page_size=30&_=${Date.now()}`;
  const listData = await requestJson(listUrl, { headers: accountHeaders(account) });
  const list = requireStatusZero(listData, '问题列表查询');
  const question = pickRandom(list && list.items, '问题列表查询');
  if (question.id === undefined || question.id === null) {
    throw new TaskError('QUESTION_ID_MISSING', '问题列表未返回问题 ID');
  }
  const content = await getPublicText();
  const result = await requestJson(`${BASE_URL}/community/api/posts/comments`, {
    method: 'POST',
    headers: accountHeaders(account),
    body: JSON.stringify({ content, object: 2, parent_id: question.id }),
  });
  requireStatusZero(result, '自动回答');
  return { message: '回答已发布，文案来自一言或本地安全回退' };
}

async function getRecommendation(account) {
  const city = CITY_CODES[Math.floor(Math.random() * CITY_CODES.length)];
  const url = `${BASE_URL}/community/api/group/city/recommend_list?city_code=${city}&last_score=0&page_size=20&_=${Date.now()}`;
  const data = await requestJson(url, { headers: accountHeaders(account) });
  const payload = requireStatusZero(data, '推荐列表查询');
  const item = pickRandom(payload && payload.items, '推荐列表查询');
  if (item.id === undefined || item.user_id === undefined) {
    throw new TaskError('RECOMMENDATION_FIELDS_MISSING', '推荐项目缺少文章或用户标识');
  }
  return item;
}

async function sharePosts(account) {
  for (let index = 0; index < 2; index += 1) {
    const item = await getRecommendation(account);
    const data = await requestJson(`${BASE_URL}/community/api/posts/shares`, {
      method: 'POST',
      headers: accountHeaders(account),
      body: JSON.stringify({ id: item.id }),
    });
    requireStatusZero(data, `第 ${index + 1} 次分享`);
  }
  return { message: '2 次分享均通过业务成功校验' };
}

function decodeFollowState(profile) {
  const candidates = [
    ['is_follow', profile && profile.is_follow],
    ['isFollow', profile && profile.isFollow],
    ['followed', profile && profile.followed],
    ['follow_type', profile && profile.follow_type],
    ['followType', profile && profile.followType],
    ['is_follow', profile && profile.user && profile.user.is_follow],
    ['isFollow', profile && profile.user && profile.user.isFollow],
    ['followType', profile && profile.user && profile.user.followType],
  ];
  for (const [key, value] of candidates) {
    if (typeof value === 'boolean') return value;
    if (value === 'true') return true;
    if (value === 'false') return false;
    if (typeof value === 'number' || /^\d+$/.test(String(value || ''))) {
      const number = Number(value);
      if (key.toLowerCase().includes('type')) {
        if (number === 2) return true;
        if (number === 0 || number === 1) return false;
      } else if (number === 0 || number === 1) {
        return number === 1;
      }
    }
  }
  return null;
}

async function queryFollowState(account, targetUserId) {
  const profile = await getProfile(account, targetUserId);
  const state = decodeFollowState(profile);
  if (state === null) {
    throw new TaskError('FOLLOW_STATE_UNKNOWN', '服务未返回可识别的关注状态，安全策略已阻止切换');
  }
  return state;
}

async function toggleFollow(account, targetUserId) {
  const data = await requestJson(`${BASE_URL}/community/api/user/follow/create`, {
    method: 'POST',
    headers: accountHeaders(account),
    body: JSON.stringify({ follow_user_id: targetUserId }),
  });
  requireStatusZero(data, '关注状态切换');
}

async function pollFollowState(account, targetUserId, attempts = 3) {
  let lastError;
  for (let index = 0; index < attempts; index += 1) {
    try {
      return await queryFollowState(account, targetUserId);
    } catch (error) {
      lastError = error;
      if (index + 1 < attempts) await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  throw lastError || new TaskError('FOLLOW_STATE_UNKNOWN', '无法核验关注状态');
}

async function restoreFollowState(account, targetUserId, originalState) {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const current = await pollFollowState(account, targetUserId);
    if (current === originalState) return;
    try {
      await toggleFollow(account, targetUserId);
    } catch {
      // 切换请求结果不确定时，不假设失败；下一轮先重新读取状态。
    }
  }
  const finalState = await pollFollowState(account, targetUserId);
  if (finalState !== originalState) {
    throw new TaskError('FOLLOW_RESTORE_FAILED', '关注状态未恢复，账号任务判定失败，请人工核对');
  }
}

async function runRestoredFollowCycle(account) {
  const item = await getRecommendation(account);
  const targetUserId = item.user_id;
  const originalState = await queryFollowState(account, targetUserId);
  let mutationAttempted = false;
  try {
    // 请求即使超时，也可能已经在服务端生效，因此在发送前就进入强制恢复路径。
    mutationAttempted = true;
    await toggleFollow(account, targetUserId);
    const changedState = await pollFollowState(account, targetUserId);
    if (changedState === originalState) {
      throw new TaskError('FOLLOW_NOT_CHANGED', '关注状态未发生预期变化');
    }
  } finally {
    if (mutationAttempted) await restoreFollowState(account, targetUserId, originalState);
  }
  const verifiedState = await queryFollowState(account, targetUserId);
  if (verifiedState !== originalState) {
    throw new TaskError('FOLLOW_RESTORE_FAILED', '最终关注状态核验不一致');
  }
  return { message: '临时关注状态已恢复并通过最终核验' };
}

async function runAccount(account, index, flags) {
  const startedAt = Date.now();
  const context = { index, stageIndex: 0, stats: createStats(), failed: false };
  console.log(`\n[${nowTime()}] ===== 账号 ${index} 开始 =====`);

  if (flags.dryRun) {
    const dryStages = [
      ['校验令牌参数', '占位令牌格式有效；未发起网络请求'],
      ['查询公开身份', '预演查询；未发起网络请求'],
      ['读取社区指引', '预演读取；未发起网络请求'],
      ['查询积分', '预演查询；未发起网络请求'],
      ['自动回答', flags.comment ? '预演发布与本地文案回退；未发起网络请求' : '开关默认关闭'],
      ['分享文章', flags.share ? '预演分享；未发起网络请求' : '开关默认关闭'],
      ['关注状态恢复循环', flags.followCycle ? '预演状态读取、切换、恢复和复核；未发起网络请求' : '关注与取关开关默认关闭'],
    ];
    for (const [name, message] of dryStages) {
      await runStage(context, name, async () => ({ message }), {
        skip: message.includes('默认关闭') ? message : undefined,
      });
    }
  } else {
    await runStage(context, '查询公开身份', () => queryOwnProfile(account));
    await runStage(context, '读取社区指引', () => readGuide(account));
    await runStage(context, '查询积分', () => queryPoints(account));
    await runStage(context, '自动回答', () => postAnswer(account), {
      skip: flags.comment ? undefined : 'XNIU_ENABLE_COMMENT 未开启',
    });
    await runStage(context, '分享文章', () => sharePosts(account), {
      skip: flags.share ? undefined : 'XNIU_ENABLE_SHARE 未开启',
    });
    await runStage(context, '关注状态恢复循环', () => runRestoredFollowCycle(account), {
      skip: flags.followCycle ? undefined : 'XNIU_ENABLE_FOLLOW 与 XNIU_ENABLE_UNFOLLOW 未同时开启',
    });
  }

  console.log(`[${nowTime()}] 账号 ${index} 统计：总任务 ${context.stats.total}，成功 ${context.stats.success}，已完成 ${context.stats.alreadyComplete}，跳过 ${context.stats.skipped}，失败 ${context.stats.failed}，耗时 ${elapsed(startedAt)}`);
  console.log(`[${nowTime()}] ===== 账号 ${index} ${context.failed ? '失败' : '成功'} =====`);
  return { ok: !context.failed, stats: context.stats, durationMs: Date.now() - startedAt };
}

function wildcardMatch(pattern, value) {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.');
  return new RegExp(`^${escaped}$`).test(value);
}

function notificationEnabled() {
  const switchValue = String(process.env.QINGLONG_NOTIFY || 'auto').trim().toLowerCase();
  if (FALSE_VALUES.has(switchValue)) return false;
  if (TRUE_VALUES.has(switchValue)) return true;
  if (Object.prototype.hasOwnProperty.call(process.env, 'QINGLONG_NOTIFY_SCRIPTS')) {
    const raw = process.env.QINGLONG_NOTIFY_SCRIPTS || '';
    if (!raw.trim()) return false;
    const selectors = raw.split(/[,;\s]+/).filter(Boolean);
    const values = [CATALOG_ID, 'candidate.js', 'output/candidate.js'];
    return selectors.includes('*') || selectors.some((selector) => values.some((value) => wildcardMatch(selector, value)));
  }
  return true;
}

function notifyCandidates() {
  const candidates = [];
  if (process.env.QINGLONG_NOTIFY_DIR) {
    candidates.push(path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'));
  }
  candidates.push('/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js');
  return [...new Set(candidates)];
}

async function sendNodeNotification(title, body) {
  for (const candidate of notifyCandidates()) {
    if (!fs.existsSync(candidate)) continue;
    try {
      const moduleValue = require(candidate);
      const sender = typeof moduleValue === 'function'
        ? moduleValue
        : moduleValue.sendNotify || (moduleValue.default && moduleValue.default.sendNotify);
      if (typeof sender !== 'function') continue;
      await sender(title, body);
      return true;
    } catch {
      // 继续尝试其他通知实现，且不改变业务退出码。
    }
  }
  return false;
}

function sendPythonNotification(title, body) {
  const pythonCode = [
    'import importlib.util, os, sys',
    'title=os.environ["QL_SAFE_NOTIFY_TITLE"]',
    'body=os.environ["QL_SAFE_NOTIFY_BODY"]',
    'candidate=os.environ.get("QL_SAFE_NOTIFY_FILE", "")',
    'if candidate:',
    ' spec=importlib.util.spec_from_file_location("ql_notify", candidate)',
    ' module=importlib.util.module_from_spec(spec)',
    ' spec.loader.exec_module(module)',
    'else:',
    ' import notify as module',
    'module.send(title, body)',
  ].join('\n');
  const files = [];
  if (process.env.QINGLONG_NOTIFY_DIR) files.push(path.join(process.env.QINGLONG_NOTIFY_DIR, 'notify.py'));
  files.push('/ql/data/scripts/notify.py', '/ql/scripts/notify.py');
  for (const file of [...new Set(files)]) {
    if (!fs.existsSync(file)) continue;
    const result = spawnSync('python3', ['-c', pythonCode], {
      env: { ...process.env, QL_SAFE_NOTIFY_TITLE: title, QL_SAFE_NOTIFY_BODY: body, QL_SAFE_NOTIFY_FILE: file },
      stdio: 'ignore',
      timeout: 15_000,
      shell: false,
    });
    if (result.status === 0) return true;
  }
  const imported = spawnSync('python3', ['-c', pythonCode], {
    env: { ...process.env, QL_SAFE_NOTIFY_TITLE: title, QL_SAFE_NOTIFY_BODY: body, QL_SAFE_NOTIFY_FILE: '' },
    stdio: 'ignore',
    timeout: 15_000,
    shell: false,
  });
  return imported.status === 0;
}

async function sendNotification(summary) {
  if (!notificationEnabled()) return '已关闭';
  const title = `「${TASK_NAME}」`;
  const body = `任务状态：${summary.status}\n账号总数：${summary.accounts}\n成功：${summary.succeeded}\n失败：${summary.failed}\n模式：${summary.mode}`;
  if (await sendNodeNotification(title, body)) return '发送成功';
  if (sendPythonNotification(title, body)) return '发送成功';
  console.log(`[${nowTime()}] ⚠️ 未找到可用通知组件或通知发送失败；业务退出码保持不变`);
  return '不可用';
}

async function main() {
  const taskStartedAt = Date.now();
  const flags = {
    dryRun: enabled('XNIU_DRY_RUN'),
    comment: enabled('XNIU_ENABLE_COMMENT'),
    share: enabled('XNIU_ENABLE_SHARE'),
    follow: enabled('XNIU_ENABLE_FOLLOW'),
    unfollow: enabled('XNIU_ENABLE_UNFOLLOW'),
  };
  flags.followCycle = flags.follow && flags.unfollow;
  let accounts = [];
  let configurationError = null;
  try {
    accounts = parseAccounts();
    if (accounts.length === 0) throw new TaskError('CONFIG_MISSING', '未配置 XNIU_TOKEN');
    if (flags.follow !== flags.unfollow) {
      throw new TaskError('UNSAFE_FOLLOW_CONFIG', '关注与取关必须同时明确开启，否则不会执行状态切换');
    }
  } catch (error) {
    configurationError = safeError(error);
  }

  console.log(`========== ${TASK_NAME} ==========`);
  console.log(`开始时间：${nowDateTime()}`);
  console.log(`运行模式：${flags.dryRun ? '无网络预演' : '正式运行'}`);
  console.log(`账号数量：${accounts.length}`);
  console.log(`社区变更：回答=${flags.comment ? '开启' : '关闭'}，分享=${flags.share ? '开启' : '关闭'}，关注=${flags.follow ? '开启' : '关闭'}，取关=${flags.unfollow ? '开启' : '关闭'}`);

  const results = [];
  if (configurationError) {
    console.log(`[${nowTime()}] ❌ 配置错误：${configurationError}`);
  } else {
    for (let index = 0; index < accounts.length; index += 1) {
      // 账号相互隔离；单账号失败不会阻止后续账号。
      results.push(await runAccount(accounts[index], index + 1, flags));
    }
  }

  const succeeded = results.filter((result) => result.ok).length;
  const failed = configurationError ? Math.max(1, accounts.length) : results.filter((result) => !result.ok).length;
  const childStats = results.reduce((total, result) => {
    for (const key of Object.keys(total)) total[key] += result.stats[key];
    return total;
  }, createStats());
  const businessOk = !configurationError && accounts.length > 0 && failed === 0;
  const status = flags.dryRun
    ? (businessOk ? '预演成功' : '预演失败')
    : (businessOk ? '成功' : succeeded > 0 ? '部分失败' : '失败');
  const summary = {
    status,
    mode: flags.dryRun ? 'dry-run' : 'live',
    accounts: accounts.length,
    succeeded,
    failed,
  };
  const notification = await sendNotification(summary);

  console.log('\n----------------------------------------');
  console.log(`任务统计：账号 ${accounts.length}，成功 ${succeeded}，失败 ${failed}`);
  console.log(`子任务统计：总计 ${childStats.total}，成功 ${childStats.success}，已完成 ${childStats.alreadyComplete}，跳过 ${childStats.skipped}，失败 ${childStats.failed}`);
  console.log(`总耗时：${elapsed(taskStartedAt)}`);
  console.log(`完成时间：${nowDateTime()}`);
  console.log(`通知状态：${notification}`);
  console.log(`最终状态：${status}`);
  console.log('----------------------------------------');
  console.log(`TASK_SUMMARY=${JSON.stringify({ ...summary, tasks: childStats, notification, durationMs: Date.now() - taskStartedAt })}`);
  process.exitCode = businessOk ? 0 : 1;
}

main().catch(async () => {
  const summary = { status: '失败', mode: enabled('XNIU_DRY_RUN') ? 'dry-run' : 'live', accounts: 0, succeeded: 0, failed: 1 };
  const notification = await sendNotification(summary);
  console.log(`[${nowTime()}] ❌ 任务发生未处理异常`);
  console.log(`完成时间：${nowDateTime()}`);
  console.log('最终状态：失败');
  console.log(`TASK_SUMMARY=${JSON.stringify({ ...summary, notification })}`);
  process.exitCode = 1;
});
