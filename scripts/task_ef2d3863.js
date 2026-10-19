// name: 阿里云盘签到
// cron: 7 9,22 * * *
/*
name: 阿里云盘签到
cron: 7 9,22 * * *
阿里云盘签到
项目地址：https://github.com/mrabit/aliyundriveDailyCheck
上游来源：yunzimo/APChinkin，autoSignin.js
SPDX-License-Identifier: Apache-2.0
本维护版本沿用上游 Apache-2.0 许可；保留上游署名。
许可全文：https://www.apache.org/licenses/LICENSE-2.0

参数：refreshToken 为必填凭据，每个非空行填写一个账号的 refresh_token。
获取：在阿里云盘网页版登录自己的账号，用浏览器开发者工具检查
本地存储中的 token 对象或本人登录刷新请求，提取 refresh_token（不是 access_token）。
不要将凭据截图、日志或浏览器存储内容公开。旧变量名 refreshToken 保持兼容。
不再读取青龙管理 API 或自动改写凭据；服务端轮换后须自行更新凭据。
ALIYUNDRIVE_DRY_RUN=1：完全断网预演（含通知预演），不验证真实账号。
QINGLONG_NOTIFY 未设置时按上架状态；0/false/no/off 关闭。QINGLONG_NOTIFY_DIR 指向
公开青龙通知模块 sendNotify.js 所在目录；通知失败不改变业务退出码。
*/
'use strict';

// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["ef2d3863a5184a74", "scripts/task_ef2d3863.js", "task_ef2d3863.js", "task_ef2d3863"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');

const TITLE = '阿里云盘签到';
const TOKEN_URL = 'https://auth.aliyundrive.com/v2/account/token';
const SIGN_URL = 'https://member.aliyundrive.com/v1/activity/sign_in_list?_rx-s=mobile';
const REWARD_URL = 'https://member.aliyundrive.com/v1/activity/sign_in_reward?_rx-s=mobile';
const DRY = process.env.ALIYUNDRIVE_DRY_RUN === '1';
const started = Date.now();
let stageNumber = 0;
const secrets = [];

function clean(value) {
  let text = String(value).replace(/[\r\n\u0000-\u001f\u007f]/g, ' ');
  for (const secret of secrets) if (secret) text = text.split(secret).join('[凭据已隐藏]');
  return text.replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, '[手机号已隐藏]');
}
function log(message) {
  console.log(`[${new Date().toTimeString().slice(0, 8)}] ${clean(message)}`);
}
function fail(message) { throw new Error(message); }
function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }

// 固定服务端地址；不跟随重定向、不输出请求/响应原文或底层错误。
function post(url, data, accessToken) {
  if (DRY) return Promise.reject(new Error('断网预演禁止 HTTP 请求'));
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(data);
    let settled = false;
    let req;
    const done = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(value);
    };
    const timer = setTimeout(() => {
      done(new Error('请求超时（15 秒）'));
      if (req) req.destroy();
    }, 15000);
    try {
      req = https.request(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body),
          ...(accessToken ? { Authorization: accessToken } : {}) }
      }, response => {
        let bytes = 0;
        const chunks = [];
        response.on('data', chunk => {
          bytes += chunk.length;
          if (bytes > 1024 * 1024) {
            done(new Error('响应超过大小限制')); response.destroy(); req.destroy();
          } else chunks.push(chunk);
        });
        response.on('error', () => done(new Error('响应读取失败')));
        response.on('aborted', () => done(new Error('响应被中断')));
        response.on('end', () => {
          if (response.statusCode < 200 || response.statusCode >= 300)
            return done(new Error(`HTTP 状态异常：${response.statusCode}`));
          try {
            const json = JSON.parse(Buffer.concat(chunks).toString('utf8'));
            if (!object(json)) return done(new Error('响应结构无效'));
            done(null, json);
          } catch (_) { done(new Error('响应不是有效 JSON')); }
        });
      });
      req.on('error', () => done(new Error('网络请求失败')));
      req.end(body);
    } catch (_) { done(new Error('请求初始化失败')); }
  });
}

async function stage(stats, label, action) {
  const number = ++stageNumber;
  const begin = Date.now();
  stats.total++;
  log(`阶段 ${number} ${label}：开始`);
  try {
    const result = await action();
    if (DRY) stats.skipped++; else stats.success++;
    log(`${DRY ? '⏭️ 预演' : '✅ 成功'} 阶段 ${number} ${label}，耗时 ${Date.now() - begin} ms`);
    return result;
  } catch (error) {
    stats.failed++;
    log(`❌ 阶段 ${number} ${label}：${error.message}，耗时 ${Date.now() - begin} ms`);
    throw error;
  }
}

async function account(token, index) {
  const begin = Date.now();
  const stats = { account: index, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  log(`账号 ${index}：开始`);
  try {
    const auth = await stage(stats, '刷新访问令牌', async () => {
      if (DRY) return { access_token: 'dry-run-access-token' };
      const json = await post(TOKEN_URL, { grant_type: 'refresh_token', refresh_token: token });
      if (json.code) {
        if (json.code === 'RefreshTokenExpired' || json.code === 'InvalidParameter.RefreshToken')
          fail('refresh_token 已过期或无效，请重新获取');
        fail('令牌接口返回业务错误');
      }
      if (typeof json.access_token !== 'string' || !json.access_token.trim()) fail('缺少有效访问令牌');
      secrets.push(json.access_token);
      if (typeof json.refresh_token === 'string') secrets.push(json.refresh_token);
      for (const field of ['nick_name', 'nickname', 'user_name', 'display_name', 'user_id']) {
        if ((typeof json[field] === 'string' && json[field]) ||
            (field === 'user_id' && Number.isSafeInteger(json[field])))
          log(`账号 ${index} 官方身份 ${field}：${json[field]}`);
      }
      if (json.refresh_token && json.refresh_token !== token)
        log('⚠️ 服务端已轮换刷新令牌，请通过本人官方登录流程更新环境变量；未自动改写凭据');
      return json;
    });
    const result = await stage(stats, '每日签到与检查奖励列表', async () => {
      if (DRY) return { signInCount: 1, signInLogs: [{ day: 1, status: 'normal', isReward: false }] };
      const json = await post(SIGN_URL, { isReward: false }, auth.access_token);
      if (json.success !== true) fail('签到接口未明确返回成功');
      const result = json.result;
      if (!object(result) || !Number.isInteger(result.signInCount) || result.signInCount < 1 ||
          !Array.isArray(result.signInLogs) || result.signInCount > result.signInLogs.length)
        fail('签到结果结构无效');
      const days = new Set();
      for (const entry of result.signInLogs) {
        if (!object(entry) || !Number.isInteger(entry.day) || entry.day < 1 || entry.day > 31 ||
            typeof entry.status !== 'string' || typeof entry.isReward !== 'boolean' || days.has(entry.day))
          fail('奖励列表结构无效');
        days.add(entry.day);
      }
      if (result.signInLogs[result.signInCount - 1].status !== 'normal') fail('当天签到状态未确认');
      log(`账号 ${index} 签到成功，本月累计签到 ${result.signInCount} 天`);
      return result;
    });
    const rewards = result.signInLogs.filter(entry => entry.status === 'normal' && !entry.isReward);
    for (const entry of rewards) {
      try {
        await stage(stats, `领取第 ${entry.day} 天奖励`, async () => {
          if (DRY) return;
          const json = await post(REWARD_URL, { signInDay: entry.day }, auth.access_token);
          if (json.success !== true || !object(json.result)) fail('奖励接口未明确返回成功或结果结构无效');
          // 只展示已知公开奖励描述，不打印服务端错误、未知字段或原始响应。
          const name = typeof json.result.name === 'string' ? json.result.name : '';
          const description = typeof json.result.description === 'string' ? json.result.description : '';
          log(`第 ${entry.day} 天奖励领取成功：${name}${description}`);
        });
      } catch (_) { /* 单次领奖失败后继续其他奖励；失败计数保留。 */ }
    }
    if (!rewards.length) {
      stats.total++; stats.alreadyComplete++;
      log('☑️ 奖励检查：没有待领取奖励');
      const current = result.signInLogs[result.signInCount - 1];
      if (current.isReward && object(current.reward)) {
        log(`今日签到获得${typeof current.reward.name === 'string' ? current.reward.name : ''}${
          typeof current.reward.description === 'string' ? current.reward.description : ''}`);
      }
    }
  } catch (_) { /* 已在对应阶段输出脱敏错误。 */ }
  stats.durationMs = Date.now() - begin;
  stats.status = stats.failed ? 'failure' : DRY ? 'dry-run' : 'success';
  log(`账号 ${index} 统计：任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs} ms`);
  return stats;
}

async function notify(summary) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (DRY) { log('⏭️ 通知预演：已生成脱敏总结，断网模式不加载通知模块'); return '断网预演'; }
  const locations = [
    ...(process.env.QINGLONG_NOTIFY_DIR ? [path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js')] : []),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'
  ];
  const location = locations.find(file => fs.existsSync(file));
  if (!location) return '通知模块不可用';
  let timer;
  try {
    const module = require(location);
    if (typeof module.sendNotify !== 'function') return '通知模块接口无效';
    const body = `状态：${summary.status}\n账号总数：${summary.accountCount}\n成功数：${summary.succeeded}\n失败数：${summary.failed}\n预演数：${summary.dryRunAccounts}\n子任务失败：${summary.tasks.failed}`;
    await Promise.race([
      module.sendNotify(TITLE, body),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('通知超时')), 15000); })
    ]);
    return '已发送';
  } catch (_) { return '通知失败或超时（业务退出码保留）'; }
  finally { clearTimeout(timer); }
}

async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}，模式：${DRY ? '断网预演' : '正式运行'}`);
  const tokens = (process.env.refreshToken || '').split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  secrets.push(...tokens);
  log(`账号总数：${tokens.length}`);
  // 禁用旧的 & 分隔以免把两个账号当作单一凭据发送给服务端。
  const invalid = !tokens.length || tokens.some(token => /[&@\s]/.test(token));
  const results = [];
  if (invalid) log('❌ 阶段 1 配置检查：refreshToken 必填，每行一个账号；不支持 &、@ 或空白字符分隔');
  else for (let index = 0; index < tokens.length; index++) results.push(await account(tokens[index], index + 1));
  const failed = invalid ? tokens.length : results.filter(item => item.failed).length;
  const tasks = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  for (const result of results) for (const key of Object.keys(tasks)) tasks[key] += result[key];
  const summary = {
    task: TITLE, mode: DRY ? 'dry-run' : 'live', accountCount: tokens.length,
    succeeded: results.filter(item => item.status === 'success').length, failed,
    dryRunAccounts: results.filter(item => item.status === 'dry-run').length,
    status: invalid ? 'configuration-error' : failed ? (failed === tokens.length ? 'failure' : 'partial-failure') : DRY ? 'dry-run' : 'success',
    tasks, accounts: results, exitCode: invalid || failed ? 1 : 0
  };
  summary.notification = await notify(summary);
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`任务统计：账号 ${summary.accountCount}，成功 ${summary.succeeded}，失败 ${summary.failed}，预演 ${summary.dryRunAccounts}`);
  log(`子任务统计：总数 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`总耗时 ${summary.durationMs} ms，完成时间 ${summary.finishedAt}，通知状态：${summary.notification}`);
  log(`最终状态：${summary.status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  // 通知模块可能遗留连接；完成总结后强制按原业务结果退出。
  process.stdout.write('', () => process.exit(summary.exitCode));
}

main().catch(() => {
  log('❌ 任务内部异常（错误详情已隐藏）');
  process.exitCode = 1;
});
