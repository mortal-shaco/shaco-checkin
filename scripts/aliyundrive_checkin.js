// name: 阿里云盘每日签到
// cron: 0 8 * * *
/**
 * 阿里云盘每日签到 - 青龙面板脚本
 * name: 阿里云盘每日签到
 * cron: 0 8 * * *
 * 原作者/来源：huwangkeji/aliyundrive_checkin，aliyundrive_checkin.js
 * 上游提交：267ee025840c5b55dce5b5e1e365fb52ac500fce
 * SPDX-License-Identifier: GPL-3.0
 * 本维护版本按 GPL-3.0 分发，保留上游署名。
 *
 * Node.js >= 16，无第三方业务依赖。refreshToken：每行一个账号的 refresh_token。
 * 获取方法：登录 https://www.aliyundrive.com/，在浏览器开发者工具控制台读取
 * JSON.parse(localStorage.token).refresh_token；仅复制到青龙私密环境变量，不分享或写入日志。
 * ALIYUN_PUSH_PLUS：可选，PushPlus 官网账户中的推送令牌；仅通过 HTTPS 发送总结。
 * ALIYUNDRIVE_DRY_RUN=1：完全断网预演（通知也模拟），不验证真实凭据或业务成功。
 * QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭全部通知。
 * QINGLONG_NOTIFY_DIR：可选，青龙 sendNotify.js 所在目录。
 * 默认签到并领取当日奖励、展示签到日历和奖励概览，不执行其他账号修改。
 */
'use strict';
const https = require('https');
const path = require('path');
const fs = require('fs');
const TITLE = '阿里云盘每日签到';
const dry = process.env.ALIYUNDRIVE_DRY_RUN === '1';
const accounts = (process.env.refreshToken || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const secrets = [...accounts, process.env.ALIYUN_PUSH_PLUS].filter(Boolean);
const start = Date.now();
const timestamp = () => new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
function safe(value) {
  let text = String(value == null ? '' : value);
  for (const secret of secrets) text = text.split(secret).join('[凭据已隐藏]');
  return text.replace(/(?:Bearer\s+\S+|(?:access_token|refresh_token|cookie|session|token)\s*[:=]\s*\S+)/gi, '[凭据已隐藏]')
    .replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]').replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
}
function log(text) { console.log(`[${timestamp()}] ${safe(text)}`); }
function fault(message) { const e = new Error(message); e.safe = true; return e; }
function request(url, body, headers = {}) {
  if (dry) throw fault('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = https.request(url, { method: 'POST', headers: {
      'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json', Accept: 'application/json',
      'Content-Length': Buffer.byteLength(data), ...headers
    } }, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) { req.destroy(fault('响应超过大小限制')); return; }
        chunks.push(chunk);
      });
      res.on('error', () => reject(fault('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return reject(fault(`HTTP 状态 ${res.statusCode}`));
        try {
          const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error();
          resolve(parsed);
        } catch (_) { reject(fault('响应不是有效 JSON 对象')); }
      });
    });
    const timer = setTimeout(() => req.destroy(fault('请求超时（15 秒）')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', error => reject(error.safe ? error : fault('网络或 TLS 请求失败')));
    req.end(data);
  });
}
const member = (route, token, body) => request(`https://member.aliyundrive.com/${route}?_rx-s=mobile`, body, { Authorization: `Bearer ${token}` });
function validCount(value) { return Number.isInteger(value) && value >= 1 && value <= 31; }
async function runAccount(token, index) {
  const begun = Date.now();
  const result = { account: index + 1, name: '', success: false, signInCount: 0, reward: '', rewardNotice: '', error: '', tasks: { total: 4, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 } };
  let accessToken, count;
  async function stage(number, title, action) {
    const at = Date.now(); log(`账号 ${index + 1} 阶段 ${number}/4 ${title} 开始`);
    try {
      const outcome = await action();
      result.tasks[outcome === 'alreadyComplete' ? 'alreadyComplete' : 'success']++;
      log(`账号 ${index + 1} 阶段 ${number}/4 ${title} ${outcome === 'alreadyComplete' ? '☑️ 已完成' : '✅ 成功'}，耗时 ${Date.now() - at}ms`);
      return true;
    } catch (e) {
      result.tasks.failed++; const message = e.safe ? e.message : '处理响应失败';
      result.error = [result.error, `${title}：${message}`].filter(Boolean).join('；');
      log(`账号 ${index + 1} 阶段 ${number}/4 ❌ ${title}：${message}，耗时 ${Date.now() - at}ms`);
      return false;
    }
  }
  if (dry) {
    for (const [i, name] of ['令牌刷新', '每日签到', '当日奖励领取', '签到详情和奖励概览'].entries()) {
      log(`账号 ${index + 1} 阶段 ${i + 1}/4 ⏭️ ${name}：预演，未发送请求，耗时 0ms`);
      result.tasks.skipped++;
    }
    result.success = true;
  } else {
    const authenticated = await stage(1, '令牌刷新', async () => {
      const data = await request('https://auth.aliyundrive.com/v2/account/token', { grant_type: 'refresh_token', refresh_token: token });
      if (data.code || typeof data.access_token !== 'string' || !data.access_token.trim()) throw fault('未取得有效访问令牌，请检查 refreshToken');
      accessToken = data.access_token; secrets.push(accessToken);
      const identity = data.nick_name || data.user_name || data.user_id;
      if (typeof identity === 'string' || typeof identity === 'number') result.name = safe(identity);
      log(`账号 ${index + 1} 身份：${result.name || '接口未返回身份'}`);
    });
    if (authenticated) {
      const signed = await stage(2, '每日签到', async () => {
        const data = await member('v1/activity/sign_in_list', accessToken, { isReward: false });
        if (data.success !== true || !validCount(data.result?.signInCount)) throw fault('签到接口未确认成功或签到天数无效');
        count = data.result.signInCount; result.signInCount = count;
        log(`账号 ${index + 1} 签到成功！本月累计签到 ${count} 天`);
      });
      if (signed) await stage(3, '当日奖励领取', async () => {
        const data = await member('v1/activity/sign_in_reward', accessToken, { signInDay: count });
        if (data.success === true) {
          result.rewardNotice = safe(data.result?.notice || '当日奖励领取成功'); result.reward = result.rewardNotice;
          log(`账号 ${index + 1} 奖励：${result.rewardNotice}`);
        } else if (typeof data.message === 'string' && data.message.includes('已领取')) {
          result.reward = '奖励已领取过'; log(`账号 ${index + 1} 奖励已领取过`); return 'alreadyComplete';
        } else throw fault('奖励接口未确认成功');
      });
      else { result.tasks.skipped++; log(`账号 ${index + 1} 阶段 3/4 ⏭️ 签到失败，跳过奖励领取，耗时 0ms`); }
      await stage(4, '签到详情和奖励概览', async () => {
        const data = await member('v2/activity/sign_in_list', accessToken, {});
        if (data.success !== true || !data.result || !Array.isArray(data.result.signInLogs) || !Array.isArray(data.result.signInInfos)) throw fault('签到详情未确认成功或列表格式无效');
        const days = new Set(data.result.signInLogs.map(x => Number(x.day)));
        const day = Number(new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Shanghai', day: 'numeric' }).format(new Date()));
        log(`账号 ${index + 1} 本月签到：${Array.from({ length: day }, (_, i) => days.has(i + 1) ? '✅' : '⬜').join('')}`);
        const info = data.result.signInInfos.find(x => Number(x.day) === count && x.signed);
        if (info && Array.isArray(info.rewards)) for (const reward of info.rewards) {
          log(`账号 ${index + 1} ${{ dailySignIn: '签到奖励', dailyTask: '任务奖励' }[reward.type] || '奖励'}：${safe(reward.name)} - ${safe(reward.remind)}`);
        }
      });
    } else {
      result.tasks.skipped += 3;
      for (let n = 2; n <= 4; n++) log(`账号 ${index + 1} 阶段 ${n}/4 ⏭️ 令牌刷新失败，跳过依赖步骤，耗时 0ms`);
    }
    result.success = result.tasks.failed === 0;
  }
  result.durationMs = Date.now() - begun;
  log(`账号 ${index + 1} 统计：总任务 4，成功 ${result.tasks.success}，已完成 ${result.tasks.alreadyComplete}，跳过 ${result.tasks.skipped}，失败 ${result.tasks.failed}，耗时 ${result.durationMs}ms`);
  return result;
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) { log('⏭️ 通知已关闭'); return 'disabled'; }
  if (dry) { log('⏭️ 预演通知已模拟，未加载通知模块或发送请求'); return 'simulated'; }
  let delivered = false;
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js', path.join(__dirname, 'sendNotify.js')].filter(Boolean);
  const file = locations.find(x => fs.existsSync(x));
  if (file) {
    let timer;
    try {
      const module = require(file);
      if (typeof module.sendNotify !== 'function') throw new Error();
      await Promise.race([Promise.resolve(module.sendNotify(TITLE, body)), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error()), 20000); })]);
      delivered = true; log('✅ 青龙通知已发送');
    } catch (_) { log('⚠️ 青龙通知不可用或发送失败，保留业务退出码'); }
    finally { clearTimeout(timer); }
  } else log('⚠️ 未发现青龙 sendNotify.js，保留业务退出码');
  if (process.env.ALIYUN_PUSH_PLUS) {
    try {
      const data = await request('https://www.pushplus.plus/send', { token: process.env.ALIYUN_PUSH_PLUS, title: TITLE, content: body, template: 'txt' });
      if (data.code !== 200) throw fault('PushPlus 未确认成功');
      log('✅ PushPlus 推送成功');
    } catch (_) { log('⚠️ PushPlus 推送失败，保留业务退出码'); }
  }
  return delivered ? 'sent' : 'unavailable-or-failed';
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date().toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${accounts.length}`);
  const results = []; let configError = '';
  if (!accounts.length) configError = '未配置 refreshToken，请每行填写一个账号的刷新令牌';
  if (configError) log(`❌ 配置错误：${configError}`);
  for (let i = 0; i < accounts.length; i++) results.push(await runAccount(accounts[i], i));
  const success = results.filter(x => x.success).length, failed = results.length - success;
  const status = configError ? 'configuration-error' : dry ? 'dry-run' : failed ? (success ? 'partial-failure' : 'failure') : 'success';
  const tasks = results.reduce((a, r) => { for (const key of Object.keys(a)) a[key] += r.tasks[key]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  const exitCode = configError || failed ? 1 : 0;
  process.exitCode = exitCode;
  const body = `${TITLE}：${status}；账号总数 ${accounts.length}，成功 ${success}，失败 ${failed}${configError ? '；' + configError : ''}\n${results.map(r => `账号 ${r.account} ${r.name}：${r.success ? (dry ? '预演通过（未验证业务）' : '成功') : '失败'}；签到 ${r.signInCount} 天；${r.reward}；${r.error}`).join('\n')}`;
  const notification = await notify(safe(body));
  const finishedAt = new Date().toISOString();
  log('--------------------------------------------------');
  log(`账号结果：总数 ${accounts.length}，成功 ${success}，失败 ${failed}`);
  log(`子任务结果：总数 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`总耗时 ${Date.now() - start}ms；完成时间 ${finishedAt}；通知状态 ${notification}；最终状态 ${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, mode: dry ? 'dry-run' : 'live', status, accounts: accounts.length, success, failed, tasks, results, notification, finishedAt, durationMs: Date.now() - start, exitCode }));
  // 第三方通知模块可能保留计时器；明确保留业务退出码并结束进程。
  process.exit(exitCode);
}
if (require.main === module) main().catch(() => { log('❌ 任务内部异常'); process.exit(1); });
