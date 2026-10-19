#!/usr/bin/env node
// name: 词霸每日一句
// cron: 0 25 11 * * *
/**
 * name: 词霸每日一句
 * cron: 0 25 11 * * *
 *
 * 原项目：ql_sign_script
 * 原项目地址：https://github.com/unitaryhighs/ql_sign_script
 * 原脚本路径：sign/ciba.js
 * SPDX-License-Identifier: MIT
 *
 * CIBA_LIST（必填，非凭据）：每行一项显示配置。
 * 推荐格式：配置名称|中文开关|英文开关，例如“每日一句|是|是”。
 * 为兼容旧配置，单个非空值默认同时显示中文和英文；字段分隔符也兼容 @。
 * 账号之间不得使用字段分隔符；本服务本身无需账号，多个非空行仅表示多项显示配置。
 *
 * CIBA_DRY_RUN=1 时完全断网，只验证配置、流程、日志和汇总。
 */

'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["5901669d3162577e", "scripts/ciba.js", "ciba.js", "ciba"];
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

const TASK_NAME = '词霸每日一句';
const CATALOG_ID = '5901669d3162577e';
const API_URL = 'https://open.iciba.com/dsapi/';
const REQUEST_TIMEOUT_MS = 10_000;
const MAX_RESPONSE_BYTES = 64 * 1024;
const DRY_RUN_ENV = 'CIBA_DRY_RUN';
const TRUTHY = new Set(['1', 'true', 'yes', 'on', '是', '启用']);
const FALSEY = new Set(['0', 'false', 'no', 'off', '否', '禁用']);

function nowParts() {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date());
  return Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]));
}

function dateTime() {
  const value = nowParts();
  return `${value.year}-${value.month}-${value.day} ${value.hour}:${value.minute}:${value.second}`;
}

function clock() {
  const value = nowParts();
  return `${value.hour}:${value.minute}:${value.second}`;
}

function elapsedMs(startedAt) {
  return Number(process.hrtime.bigint() - startedAt) / 1e6;
}

function logStage(configIndex, stageIndex, stageTotal, name, message, startedAt, icon = '') {
  const scope = configIndex == null ? '任务' : `配置 ${configIndex}`;
  const duration = startedAt == null ? '' : `，耗时 ${elapsedMs(startedAt).toFixed(0)}ms`;
  console.log(`[${clock()}] [${scope}] [${stageIndex}/${stageTotal}] ${name}：${icon}${message}${duration}`);
}

function isEnabled(value) {
  return TRUTHY.has(String(value || '').trim().toLowerCase());
}

function parseSwitch(value, defaultValue) {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return defaultValue;
  if (TRUTHY.has(normalized)) return true;
  if (FALSEY.has(normalized)) return false;
  throw new Error('显示开关只能填写“是/否、1/0、true/false、on/off”');
}

function parseConfigurations(rawValue) {
  if (!rawValue || !rawValue.trim()) {
    throw new Error('缺少必填环境变量 CIBA_LIST');
  }

  return rawValue
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const delimiter = line.includes('|') ? '|' : line.includes('@') ? '@' : null;
      const fields = delimiter ? line.split(delimiter) : [line];
      const showChinese = parseSwitch(fields[1], true);
      const showEnglish = parseSwitch(fields[2], true);
      if (!showChinese && !showEnglish) {
        throw new Error(`第 ${index + 1} 行至少需要启用中文或英文中的一项`);
      }
      return { index: index + 1, showChinese, showEnglish };
    });
}

function normalizedText(value) {
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
}

function validateBusinessResponse(payload, config) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('接口返回的 JSON 不是对象');
  }

  const chinese = normalizedText(payload.note);
  const english = normalizedText(payload.content);
  if (config.showChinese && !chinese) throw new Error('接口响应缺少中文释义 note');
  if (config.showEnglish && !english) throw new Error('接口响应缺少英文原文 content');
  return { chinese, english };
}

function requestDailySentence() {
  return new Promise((resolve, reject) => {
    const target = new URL(API_URL);
    if (target.protocol !== 'https:') {
      reject(new Error('拒绝访问非 HTTPS 接口'));
      return;
    }

    const request = https.get(target, {
      headers: {
        Accept: 'application/json',
        'User-Agent': 'Qinglong-Ciba-Maintained/1.0',
      },
    }, (response) => {
      let receivedBytes = 0;
      const chunks = [];

      response.on('data', (chunk) => {
        receivedBytes += chunk.length;
        if (receivedBytes > MAX_RESPONSE_BYTES) {
          response.destroy(new Error('接口响应超过 64 KiB 安全上限'));
          return;
        }
        chunks.push(chunk);
      });

      response.on('end', () => {
        if (response.statusCode !== 200) {
          reject(new Error(`接口 HTTP 状态码为 ${response.statusCode || '未知'}`));
          return;
        }
        try {
          resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));
        } catch {
          reject(new Error('接口返回的内容不是有效 JSON'));
        }
      });

      response.on('error', reject);
    });

    request.setTimeout(REQUEST_TIMEOUT_MS, () => {
      request.destroy(new Error(`接口请求超过 ${REQUEST_TIMEOUT_MS / 1000} 秒`));
    });
    request.on('error', reject);
  });
}

function dryRunPayload() {
  return {
    note: '预演中文释义',
    content: 'Dry-run English sentence.',
  };
}

function wildcardMatches(pattern, value) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
  return new RegExp(`^${escaped}$`, 'i').test(value);
}

function notificationEnabled() {
  const globalSwitch = String(process.env.QINGLONG_NOTIFY || 'auto').trim().toLowerCase();
  if (FALSEY.has(globalSwitch)) return { enabled: false, reason: '已由 QINGLONG_NOTIFY 关闭' };
  if (globalSwitch !== 'auto' && !TRUTHY.has(globalSwitch)) {
    console.log(`[${clock()}] ⚠️ QINGLONG_NOTIFY 值无法识别，按 auto 处理`);
  }

  if (Object.prototype.hasOwnProperty.call(process.env, 'QINGLONG_NOTIFY_SCRIPTS')) {
    const rawSelection = process.env.QINGLONG_NOTIFY_SCRIPTS.trim();
    if (!rawSelection) return { enabled: false, reason: 'QINGLONG_NOTIFY_SCRIPTS 为空' };
    const selectors = rawSelection.split(/[,;\s]+/).filter(Boolean);
    const identities = [CATALOG_ID, 'output/candidate.js', 'candidate.js'];
    const selected = selectors.some((selector) => selector === '*' || identities.some((identity) => wildcardMatches(selector, identity)));
    return selected
      ? { enabled: true, reason: '已被 QINGLONG_NOTIFY_SCRIPTS 选中' }
      : { enabled: false, reason: '未被 QINGLONG_NOTIFY_SCRIPTS 选中' };
  }

  return { enabled: true, reason: '计划任务默认启用' };
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
  const selection = notificationEnabled();
  if (!selection.enabled) {
    console.log(`[${clock()}] ⏭️ 通知：${selection.reason}`);
    return 'disabled';
  }
  if (dryRun) {
    console.log(`[${clock()}] ⏭️ 通知：断网预演不调用外部通知通道`);
    return 'dry-run-skipped';
  }

  for (const candidate of notifierCandidates()) {
    if (!fs.existsSync(candidate)) continue;
    try {
      const loaded = require(candidate);
      const send = typeof loaded === 'function'
        ? loaded
        : typeof loaded.sendNotify === 'function'
          ? loaded.sendNotify
          : typeof loaded.default === 'function'
            ? loaded.default
            : null;
      if (!send) continue;
      await Promise.resolve(send(TASK_NAME, body));
      console.log(`[${clock()}] ✅ 通知：已通过 sendNotify.js 提交`);
      return 'sent';
    } catch (error) {
      console.log(`[${clock()}] ⚠️ 通知失败：${error instanceof Error ? error.message : '未知错误'}`);
      return 'failed';
    }
  }

  console.log(`[${clock()}] ⚠️ 通知不可用：未找到 sendNotify.js，业务退出码保持不变`);
  return 'unavailable';
}

async function runConfiguration(config, dryRun) {
  const configStartedAt = process.hrtime.bigint();
  const stats = { total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };

  let stageStartedAt = process.hrtime.bigint();
  logStage(config.index, 1, 2, '检查显示配置', `中文=${config.showChinese ? '是' : '否'}，英文=${config.showEnglish ? '是' : '否'}`, stageStartedAt, '✅ ');
  stats.success += 1;

  stageStartedAt = process.hrtime.bigint();
  try {
    const payload = dryRun ? dryRunPayload() : await requestDailySentence();
    const result = validateBusinessResponse(payload, config);
    logStage(config.index, 2, 2, dryRun ? '验证模拟响应' : '请求词霸接口', dryRun ? '断网模拟响应通过业务校验' : 'HTTP 200 且业务字段完整', stageStartedAt, '✅ ');
    if (config.showEnglish) console.log(`[${clock()}] [配置 ${config.index}] 英文：${result.english}`);
    if (config.showChinese) console.log(`[${clock()}] [配置 ${config.index}] 中文：${result.chinese}`);
    stats.success += 1;
    console.log(`[${clock()}] [配置 ${config.index}] 结果：✅ 词霸每日一句获取成功`);
  } catch (error) {
    stats.failed += 1;
    logStage(config.index, 2, 2, dryRun ? '验证模拟响应' : '请求词霸接口', error instanceof Error ? error.message : '未知错误', stageStartedAt, '❌ ');
    console.log(`[${clock()}] [配置 ${config.index}] 结果：❌ 失败`);
  }

  console.log(`[${clock()}] [配置 ${config.index}] 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${elapsedMs(configStartedAt).toFixed(0)}ms`);
  return stats;
}

async function main() {
  const runStartedAt = process.hrtime.bigint();
  const startTime = dateTime();
  const dryRun = isEnabled(process.env[DRY_RUN_ENV]);
  let configurations = [];
  let configurationError = null;

  try {
    configurations = parseConfigurations(process.env.CIBA_LIST || '');
  } catch (error) {
    configurationError = error instanceof Error ? error.message : '配置解析失败';
  }

  console.log('========================================');
  console.log(`任务名称: ${TASK_NAME}`);
  console.log(`开始时间: ${startTime}`);
  console.log(`运行模式: ${dryRun ? 'DRY-RUN（完全断网）' : 'LIVE'}`);
  console.log('账号数量: 0（词霸公开接口无需账号）');
  console.log(`配置数量: ${configurations.length}`);
  console.log('========================================');

  const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let succeededConfigurations = 0;
  let failedConfigurations = 0;

  if (configurationError) {
    logStage(null, 1, 1, '检查任务配置', configurationError, runStartedAt, '❌ ');
    failedConfigurations = 1;
    totals.total = 1;
    totals.failed = 1;
  } else {
    for (const config of configurations) {
      const stats = await runConfiguration(config, dryRun);
      totals.total += stats.total;
      totals.success += stats.success;
      totals.alreadyComplete += stats.alreadyComplete;
      totals.skipped += stats.skipped;
      totals.failed += stats.failed;
      if (stats.failed > 0) failedConfigurations += 1;
      else succeededConfigurations += 1;
    }
  }

  const businessSucceeded = !configurationError && failedConfigurations === 0 && succeededConfigurations === configurations.length;
  const preliminaryStatus = businessSucceeded ? '成功' : succeededConfigurations > 0 ? '部分失败' : '失败';
  const notificationBody = `状态：${preliminaryStatus}\n账号总数：0（无需账号）\n配置总数：${configurations.length}\n成功配置：${succeededConfigurations}\n失败配置：${failedConfigurations}`;
  const notification = await sendNotification(notificationBody, dryRun);
  const finishTime = dateTime();
  const duration = elapsedMs(runStartedAt);

  console.log('----------------------------------------');
  console.log('账号结果: 本任务无需账号');
  console.log(`配置结果: 总数 ${configurations.length}，成功 ${succeededConfigurations}，失败 ${failedConfigurations}`);
  console.log(`子任务结果: 总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  console.log(`总耗时: ${duration.toFixed(0)}ms`);
  console.log(`完成时间: ${finishTime}`);
  console.log(`通知状态: ${notification}`);
  console.log(`最终状态: ${businessSucceeded ? '✅ 成功' : succeededConfigurations > 0 ? '⚠️ 部分失败' : '❌ 失败'}`);
  console.log('----------------------------------------');

  const summary = {
    task: TASK_NAME,
    catalogId: CATALOG_ID,
    mode: dryRun ? 'dry-run' : 'live',
    accountTotal: 0,
    configurationTotal: configurations.length,
    configurationSucceeded: succeededConfigurations,
    configurationFailed: failedConfigurations,
    subtaskTotal: totals.total,
    subtaskSucceeded: totals.success,
    subtaskAlreadyComplete: totals.alreadyComplete,
    subtaskSkipped: totals.skipped,
    subtaskFailed: totals.failed,
    notification,
    durationMs: Math.round(duration),
    finishTime,
    status: businessSucceeded ? 'success' : succeededConfigurations > 0 ? 'partial-failure' : configurationError ? 'configuration-error' : 'failure',
  };
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = businessSucceeded ? 0 : 1;
}

main().catch(async (error) => {
  const message = error instanceof Error ? error.message : '未知致命错误';
  const finishTime = dateTime();
  console.log(`[${clock()}] ❌ 致命错误：${message}`);
  const notification = await sendNotification('状态：失败\n账号总数：0（无需账号）\n成功配置：0\n失败配置：1', isEnabled(process.env[DRY_RUN_ENV]));
  console.log(`最终状态: ❌ 失败`);
  console.log(`TASK_SUMMARY=${JSON.stringify({ task: TASK_NAME, catalogId: CATALOG_ID, mode: isEnabled(process.env[DRY_RUN_ENV]) ? 'dry-run' : 'live', accountTotal: 0, configurationTotal: 0, configurationSucceeded: 0, configurationFailed: 1, notification, finishTime, status: 'failure' })}`);
  process.exitCode = 1;
});
