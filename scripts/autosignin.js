// name: 阿里云盘签到
// cron: 0 9 * * *
/*
name: 阿里云盘签到
cron: 0 9 * * *
来源：TangTang0812/aliyun，autoSignin.js
原始提交：fb6c6aa9c49c315f2e5c32949eef06689aa2ea7e
许可：MIT。上游文件未包含额外版权或许可声明。

MIT License
Copyright (c) TangTang0812/aliyun contributors
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

参数：ALIYUN_REFRESH_TOKEN，每行一个账号的 refresh_token；兼容 refreshToken。
获取：本人登录阿里云盘网页，在浏览器开发者工具的应用/本地存储中查找
refresh_token（或 token 对象中的 refresh_token）；也可从本人登录的令牌接口
响应取得。仅复制该字段，勿分享、勿粘贴整个对象或 access_token。
ALIYUN_DRY_RUN=1：完全断网，预演刷新、签到、领奖与通知，不验证实际业务。
QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭。QINGLONG_NOTIFY_DIR 可指定
青龙 sendNotify.js 所在目录。通知模块是可选集成，缺失不会改变业务退出码。
每天 09:00 执行；保留自动领取全部未领签到奖励。不修改青龙环境变量，
刷新令牌若发生轮换，请通过本人登录会话更新凭据，脚本不会输出新令牌。
*/
'use strict';

const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const TITLE = '阿里云盘签到';
const DRY = process.env.ALIYUN_DRY_RUN === '1';
const started = Date.now();
const endpoints = {
  token: 'https://auth.aliyundrive.com/v2/account/token',
  sign: 'https://member.aliyundrive.com/v1/activity/sign_in_list?_rx-s=mobile',
  reward: 'https://member.aliyundrive.com/v1/activity/sign_in_reward?_rx-s=mobile'
};
const secrets = new Set();
function safe(value) {
  let text = String(value).replace(/[\r\n\u0000-\u001f\u007f]/g, ' ');
  for (const secret of secrets) if (secret) text = text.split(secret).join('[凭据已隐藏]');
  return text.replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, '[手机号已隐藏]');
}
function log(message) {
  console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12: false})}] ${safe(message)}`);
}
function object(value) { return value && typeof value === 'object' && !Array.isArray(value); }
function post(url, body, token) {
  if (DRY) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const headers = {'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data)};
    if (token) headers.Authorization = token;
    let done = false;
    let timer;
    let req;
    const finish = (error, result) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      if (error) { if (req) req.destroy(); reject(error); }
      else resolve(result);
    };
    req = https.request(url, {method: 'POST', headers}, res => {
      let size = 0;
      const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) { finish(new Error('接口响应超过大小限制')); res.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('接口响应读取失败')));
      res.on('aborted', () => finish(new Error('接口响应中断')));
      res.on('end', () => {
        if (done) return;
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error(`接口 HTTP ${res.statusCode}`));
        try {
          const json = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!object(json)) throw new Error();
          finish(null, json);
        } catch (_) { finish(new Error('接口 JSON 格式无效')); }
      });
    });
    req.on('error', () => finish(new Error('接口网络请求失败')));
    timer = setTimeout(() => finish(new Error('接口请求超时（15秒）')), 15000);
    req.end(data);
  });
}
async function stage(account, number, title, action) {
  const begin = Date.now();
  log(`账号${account.index} 阶段${number} ${title}：开始`);
  account.total++;
  try {
    const result = await action();
    account.success++;
    log(`账号${account.index} 阶段${number} ✅ ${result || title + '成功'}；耗时 ${Date.now() - begin}ms`);
    return true;
  } catch (error) {
    account.failed++;
    // 仅内部固定错误文本；绝不输出响应中的 message 或异常堆栈。
    log(`账号${account.index} 阶段${number} ❌ ${error.message}；耗时 ${Date.now() - begin}ms`);
    return false;
  }
}
async function runAccount(refreshToken, index) {
  const begin = Date.now();
  const account = {index, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
  let token;
  let rewards = [];
  const refreshed = await stage(account, 1, '刷新令牌', async () => {
    if (DRY) return '预演刷新令牌（未请求接口）';
    const data = await post(endpoints.token, {grant_type: 'refresh_token', refresh_token: refreshToken});
    if (typeof data.refresh_token === 'string') secrets.add(data.refresh_token);
    if (typeof data.access_token === 'string') secrets.add(data.access_token);
    if ((data.code !== undefined && data.code !== null && data.code !== '') ||
        typeof data.access_token !== 'string' || !data.access_token.trim()) {
      throw new Error('刷新令牌失败：凭据无效或响应契约不符，请检查本人 refresh_token');
    }
    token = data.access_token;
    if (typeof data.nick_name === 'string' && data.nick_name) log(`账号${index} 昵称：${data.nick_name}`);
    return '刷新令牌成功';
  });
  let signed = false;
  if (refreshed) signed = await stage(account, 2, '每日签到', async () => {
    if (DRY) return '预演签到（未请求接口）';
    const data = await post(endpoints.sign, {isReward: false}, token);
    if (data.success !== true || !object(data.result)) throw new Error('签到失败：未取得明确业务成功响应');
    const {signInLogs, signInCount} = data.result;
    if (!Array.isArray(signInLogs) || !Number.isInteger(signInCount) || signInCount < 1 ||
        signInCount > signInLogs.length || !signInLogs.every(object)) throw new Error('签到响应字段异常');
    const pending = signInLogs.filter(item => item.status === 'normal' && !item.isReward);
    if (!pending.every(item => Number.isInteger(item.day) && item.day > 0 && item.day <= 31))
      throw new Error('未领奖励日期字段异常');
    rewards = pending;
    const current = signInLogs[signInCount - 1];
    if (current.isReward === true && object(current.reward)) {
      log(`账号${index} 今日奖励：${typeof current.reward.name === 'string' ? current.reward.name : ''} ${typeof current.reward.description === 'string' ? current.reward.description : ''}`);
    }
    return `签到成功，本月累计 ${signInCount} 天，未领奖励 ${rewards.length} 项`;
  });
  if (signed) {
    if (DRY || rewards.length === 0) {
      account.total++;
      account.skipped++;
      log(`账号${index} 阶段3 ⏭️ ${DRY ? '预演全部未领奖励（未请求接口）' : '无未领奖励'}；耗时 0ms`);
    } else {
      for (let i = 0; i < rewards.length; i++) {
        const day = rewards[i].day;
        await stage(account, i + 3, `领取第${day}天奖励`, async () => {
          const data = await post(endpoints.reward, {signInDay: day}, token);
          if (data.success !== true || !object(data.result)) throw new Error(`第${day}天奖励领取失败：未取得明确业务成功响应`);
          const reward = data.result;
          return `第${day}天奖励领取成功：${typeof reward.name === 'string' ? reward.name : ''} ${typeof reward.description === 'string' ? reward.description : ''}`;
        });
      }
    }
  } else {
    const missing = refreshed ? 1 : 2;
    account.total += missing;
    account.skipped += missing;
    log(`账号${index} 阶段${refreshed ? 3 : 2} ⏭️ 后续 ${missing} 项因前置失败跳过；耗时 0ms`);
  }
  account.durationMs = Date.now() - begin;
  account.status = account.failed ? 'failure' : DRY ? 'dry-run' : 'success';
  log(`账号${index} 统计：总任务 ${account.total}，成功 ${account.success}，已完成 ${account.alreadyComplete}，跳过 ${account.skipped}，失败 ${account.failed}；耗时 ${account.durationMs}ms；状态 ${account.status}`);
  return account;
}
async function notify(summary) {
  if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return 'disabled';
  if (DRY) { log('通知预演：脱敏摘要已生成；断网模式不加载或调用通知模块'); return 'dry-run'; }
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    path.join(__dirname, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const body = `账号总数 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${summary.failed}；状态 ${summary.status}；子任务成功 ${summary.steps.success}，跳过 ${summary.steps.skipped}，失败 ${summary.steps.failed}。`;
  for (const location of [...new Set(locations)]) {
    if (!fs.existsSync(location)) continue;
    let timer;
    try {
      const module = require(location);
      if (typeof module.sendNotify !== 'function') continue;
      await Promise.race([Promise.resolve().then(() => module.sendNotify(TITLE, body)),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('timeout')), 15000); })]);
      clearTimeout(timer);
      return 'sent';
    } catch (_) { clearTimeout(timer); log('⚠️ 通知发送失败；保留业务退出码'); return 'failed'; }
  }
  log('⚠️ 未找到可用 sendNotify.js；保留业务退出码');
  return 'unavailable';
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${DRY ? '断网预演' : '正式执行'}`);
  const canonical = process.env.ALIYUN_REFRESH_TOKEN;
  const raw = canonical && canonical.trim() ? canonical : process.env.refreshToken || '';
  const accounts = raw.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  accounts.forEach(value => secrets.add(value));
  log(`账号数量：${accounts.length}；阶段0 参数检查`);
  const results = [];
  if (!accounts.length) log('❌ 配置错误：请设置 ALIYUN_REFRESH_TOKEN，每个非空行一个账号');
  for (let i = 0; i < accounts.length; i++) results.push(await runAccount(accounts[i], i + 1));
  const failed = results.filter(account => account.failed > 0).length;
  const succeeded = results.length - failed;
  const status = !accounts.length ? 'configuration-error' : failed ? (succeeded ? 'partial-failure' : 'failure') : DRY ? 'dry-run' : 'success';
  const summary = {task: TITLE, mode: DRY ? 'dry-run' : 'live', status, accounts: accounts.length, succeeded, failed,
    verifiedAccounts: DRY ? 0 : succeeded, steps: {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0}, results};
  for (const result of results) for (const key of Object.keys(summary.steps)) summary.steps[key] += result[key];
  const exitCode = !accounts.length || failed ? 1 : 0;
  log('阶段4 发送脱敏任务通知：开始');
  const notificationStart = Date.now();
  summary.notification = await notify(summary);
  log(`阶段4 通知状态 ${summary.notification}；耗时 ${Date.now() - notificationStart}ms`);
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  console.log('----------------------------------------');
  log(`任务统计：账号 ${accounts.length}，成功 ${succeeded}，失败 ${failed}；子任务 ${JSON.stringify(summary.steps)}`);
  log(`完成时间：${summary.finishedAt}；总耗时 ${summary.durationMs}ms；最终状态 ${status}；通知 ${summary.notification}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exit(exitCode);
}
main();
