// name: 阿里云盘签到与奖励领取
// cron: 37 2 * * *
/*
name: 阿里云盘签到与奖励领取
cron: 37 2 * * *
发布文件名: aliyun_signin.js
发布路径: scripts/aliyun_signin.js（禁止沿用冲突路径 scripts/autosignin.js）
来源: wang-st/aliyunSignIn / autoSignin.js
上游提交: e81b2732652aadea5ee9920eb0d0adfe07dffa91
许可证: MIT（保留上游归属；源文件未包含单独版权声明）

MIT License
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

Node.js >= 18；无需安装依赖。
ALIYUN_REFRESH_TOKEN: 阿里云盘网页登录后，在开发者工具的应用/本地存储中
查找登录信息中的 refresh_token，仅复制该值；不同账号用换行分隔。
兼容旧变量 refreshToken（仅在规范变量未设置时使用），不再用 & 分隔账号。
ALIYUN_DRY_RUN=1: 完全断网预演，不刷新令牌、不签到、不领取、不发送外部通知。
QINGLONG_NOTIFY=0: 关闭通知；可用 QINGLONG_NOTIFY_DIR 指定青龙通知模块目录。
每行只填写一个 refresh_token，空行忽略；不需要 CLIENT_ID、CLIENT_SECRET 或 qlApi.js。
任务顺序：刷新令牌、签到、领取当天签到奖励和任务奖励；没有发布文本动作。
令牌刷新返回的新凭据只在内存使用，不修改环境变量，也不打印；凭据失效后手动重新获取。
*/
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["ee45e24a6845dbc0", "scripts/autosignin.js", "autosignin.js", "autosignin"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const TITLE = '阿里云盘签到';
const dry = process.env.ALIYUN_DRY_RUN === '1';
const start = Date.now();
const tokens = (process.env.ALIYUN_REFRESH_TOKEN ?? process.env.refreshToken ?? '')
  .split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const secrets = new Set(tokens);
const summary = { task: TITLE, mode: dry ? 'dry-run' : 'live', accounts: tokens.length,
  success: 0, failed: 0, tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, results: [] };
function safe(value) {
  let s = String(value).replace(/[\r\n\u0000-\u001f\u007f]/g, ' ');
  for (const secret of secrets) if (secret) s = s.split(secret).join('[凭据已隐藏]');
  return s.replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, '[手机号已隐藏]');
}
function log(message) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${safe(message)}`); }
// 不输出服务错误文本或原始响应，避免其回显凭据。
function post(url, body, token) {
  return new Promise((resolve, reject) => {
    if (dry) return reject(new Error('预演禁止网络请求'));
    const payload = JSON.stringify(body);
    const request = https.request(url, { method: 'POST', headers: {
      'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload),
      ...(token ? { Authorization: token } : {})
    } }, response => {
      const chunks = []; let size = 0;
      response.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) request.destroy(new Error('响应超过大小限制'));
        else chunks.push(chunk);
      });
      response.on('error', () => request.destroy(new Error('响应读取失败')));
      response.on('end', () => {
        clearTimeout(timer);
        if (response.statusCode < 200 || response.statusCode >= 300)
          return reject(new Error(`HTTP 状态异常 ${response.statusCode}`));
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error();
          resolve(data);
        } catch { reject(new Error('响应不是有效业务对象')); }
      });
    });
    const timer = setTimeout(() => request.destroy(new Error('请求超时')), 15000);
    request.on('error', error => {
      clearTimeout(timer);
      const allowed = ['请求超时', '响应读取失败', '响应超过大小限制'];
      reject(new Error(allowed.includes(error.message) ? error.message : '网络请求失败'));
    });
    request.end(payload);
  });
}
async function stage(result, name, action) {
  const since = Date.now();
  result.total++;
  log(`账号${result.account} 阶段${result.total} ${name} 开始`);
  try {
    const outcome = await action();
    const state = outcome.state || 'success';
    result[state]++;
    log(`账号${result.account} 阶段${result.total} ${name} ${state === 'failed' ? '❌' : state === 'skipped' ? '⏭️' : state === 'alreadyComplete' ? '☑️' : '✅'} ${outcome.message}；耗时 ${Date.now() - since} 毫秒`);
    return outcome.value;
  } catch (error) {
    result.failed++;
    log(`账号${result.account} 阶段${result.total} ${name} ❌ ${error.message}；耗时 ${Date.now() - since} 毫秒`);
    throw error;
  }
}
async function account(token, number) {
  const since = Date.now();
  const result = { account: number, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  try {
    if (dry) {
      for (const name of ['刷新登录令牌', '每日签到', '每日签到奖励领取', '每日任务奖励领取'])
        await stage(result, name, async () => ({ state: 'skipped', message: '断网预演：仅验证流程，不判定业务成功' }));
    } else {
      const login = await stage(result, '刷新登录令牌', async () => {
        const data = await post('https://auth.aliyundrive.com/v2/account/token', { grant_type: 'refresh_token', refresh_token: token });
        if (typeof data.access_token === 'string') secrets.add(data.access_token);
        if (typeof data.refresh_token === 'string') secrets.add(data.refresh_token);
        if (data.code || typeof data.access_token !== 'string' || !data.access_token.trim())
          throw new Error('刷新令牌失败：凭据无效或响应契约不匹配');
        const identity = data.nick_name || data.user_name || data.user_id;
        if (typeof identity === 'string' && identity) log(`账号${number} 官方身份：${safe(identity)}`);
        return { message: '登录令牌已验证', value: data.access_token };
      });
      const today = await stage(result, '每日签到', async () => {
        const data = await post('https://member.aliyundrive.com/v2/activity/sign_in_list?_rx-s=mobile', { isReward: false }, login);
        const r = data.result;
        if (data.success !== true || !r || !Number.isInteger(r.signInCount) || r.signInCount < 1 || !Array.isArray(r.signInInfos))
          throw new Error('签到失败：业务状态或签到记录无效');
        const info = r.signInInfos[r.signInCount - 1];
        if (!info || !Number.isInteger(info.day) || info.day < 1 || !Array.isArray(info.rewards))
          throw new Error('签到失败：当天奖励记录无效');
        return { message: `签到成功；本月累计签到 ${r.signInCount} 天`, value: info };
      });
      for (const reward of today.rewards) {
        // 未知奖励结构必须失败闭合，不能误报领取成功。
        try {
          await stage(result, '当天奖励处理', async () => {
            if (!reward || typeof reward !== 'object') throw new Error('奖励结构无效');
            if (reward.status === 'unfinished') return { state: 'skipped', message: '奖励任务尚未完成' };
            if (reward.status === 'end') return { state: 'skipped', message: '奖励活动已结束' };
            if (reward.status !== 'finished') throw new Error('未识别的奖励状态，未执行领取');
            const endpoint = reward.type === 'dailySignIn' ? 'v1/activity/sign_in_reward' : reward.type === 'dailyTask' ? 'v2/activity/sign_in_task_reward' : null;
            if (!endpoint) throw new Error('未识别的奖励类型，未执行领取');
            const data = await post(`https://member.aliyundrive.com/${endpoint}?_rx-s=mobile`, { signInDay: today.day }, login);
            if (data.success !== true || !data.result || typeof data.result !== 'object' || Array.isArray(data.result))
              throw new Error('奖励领取失败：业务状态或结果无效');
            const detail = [data.result.name, reward.type === 'dailyTask' ? data.result.notice : data.result.description]
              .filter(v => typeof v === 'string').map(v => safe(v).slice(0, 200)).join(' ');
            return { message: `第${today.day}天${reward.type === 'dailyTask' ? '任务' : '签到'}奖励领取成功${detail ? '：' + detail : ''}` };
          });
        } catch { /* 继续处理其他奖励，但保留失败计数 */ }
      }
    }
  } catch { /* 失败账号不阻塞其他账号 */ }
  result.durationMs = Date.now() - since;
  result.status = result.failed ? 'failure' : dry ? 'dry-run' : 'success';
  log(`账号${number} 统计：总任务 ${result.total}，成功 ${result.success}，已完成 ${result.alreadyComplete}，跳过 ${result.skipped}，失败 ${result.failed}，耗时 ${result.durationMs} 毫秒`);
  summary.results.push(result);
  if (result.failed) summary.failed++; else if (!dry) summary.success++;
  for (const key of Object.keys(summary.tasks)) summary.tasks[key] += result[key];
}
async function notify(body) {
  if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  if (dry) return '断网预演：通知内容已生成，外部投递跳过';
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = locations.find(p => fs.existsSync(p));
  if (!file) return '不可用：未发现青龙 sendNotify.js';
  return new Promise(resolve => {
    // 通知在独立进程执行，输出不转发，限时并保持业务退出码。
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).then(() => process.exit(0), () => process.exit(1));', file, TITLE, safe(body)], { stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('失败：通知超时'); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve('失败：通知进程无法启动'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '失败：通知模块执行失败'); });
  });
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(start).toISOString()}；模式：${dry ? '断网预演' : '正式运行'}；账号总数：${tokens.length}`);
  if (!tokens.length) log('❌ 配置错误：请设置 ALIYUN_REFRESH_TOKEN，每行一个账号');
  for (let i = 0; i < tokens.length; i++) await account(tokens[i], i + 1);
  summary.status = !tokens.length ? 'configuration-error' : summary.failed ? (summary.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  summary.exitCode = !tokens.length || summary.failed ? 1 : 0;
  const body = `状态：${summary.status}；账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；子任务成功 ${summary.tasks.success}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}${dry ? '；预演不代表业务成功' : ''}`;
  summary.notification = await notify(body);
  summary.durationMs = Date.now() - start;
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(body);
  log(`总耗时：${summary.durationMs} 毫秒；完成时间：${summary.finishedAt}；通知状态：${summary.notification}；最终状态：${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = summary.exitCode;
}
main().catch(() => {
  // 最终兜底同样走通知与单行汇总；不打印异常对象。
  summary.status = 'failure'; summary.exitCode = 1;
  notify(`状态：失败；账号总数 ${tokens.length}，成功 ${summary.success}，失败 ${Math.max(1, summary.failed)}；内部流程异常`).then(state => {
    summary.notification = state; summary.finishedAt = new Date().toISOString();
    summary.durationMs = Date.now() - start;
    log('----------------------------------------');
    log(`❌ 内部流程异常；账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；子任务成功 ${summary.tasks.success}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}`);
    log(`总耗时：${summary.durationMs} 毫秒；完成时间：${summary.finishedAt}；通知状态：${state}；最终状态：失败`);
    console.log('TASK_SUMMARY=' + JSON.stringify(summary)); process.exitCode = 1;
  });
});
