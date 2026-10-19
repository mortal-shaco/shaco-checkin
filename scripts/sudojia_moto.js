// name: 摩托范每日签到
// cron: 26 0 * * *
/**
 * name: 摩托范每日签到
 * cron: 33 3 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Based on sudojia/AutoTaskScript src/client/sudojia_moto.js
 * Author: Telegram@sudojia — https://blog.imzjw.cn (2024/08/27)
 * Maintained standalone edition; retains upstream GPL-3.0 licensing.
 *
 * Node.js >= 18，无第三方业务依赖。
 * 按维护任务要求暂停签到状态查询，直接提交每日签到；仅数字业务码 0 确认成功。
 * 不自动重试签到，不修改资料，不安装或下载外部程序。
 * MOTO_TOKEN：登录摩托范 App，在本人授权的抓包环境中获取
 * https://api.58moto.com 请求头 token 和对应 uid，组合为 token#uid。
 * 每个非空行一个账号，仅在第一个 # 处分隔；不使用 & 或 @ 分隔账号。
 * MOTO_DRY_RUN=1：只检查配置和模拟流程，禁止所有网络与外部通知调用。
 * QINGLONG_NOTIFY=0/false/no/off 关闭通知，未设置时按上架状态。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = true;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["2e1e25aaedb9b2c3", "scripts/sudojia_moto.js", "sudojia_moto.js", "sudojia_moto"];
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
const { fork } = require('node:child_process');
const TITLE = '摩托范每日签到';
const dry = process.env.MOTO_DRY_RUN === '1';
const started = Date.now();
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = s => console.log(`[${stamp()}] ${s}`);
const pause = ms => new Promise(r => setTimeout(r, ms));
const fail = label => { throw new Error(label); };

// 在有时限的独立进程中运行青龙通知，避免通知挂起改变业务结果。
if (process.argv[2] === '--notification-worker') {
  process.once('message', async ({ modulePath, title, body }) => {
    try {
      const notifier = require(modulePath);
      if (typeof notifier.sendNotify !== 'function') throw new Error();
      await notifier.sendNotify(title, body);
      process.exit(0);
    } catch { process.exit(1); }
  });
} else {
  main().catch(() => { log('❌ 未预期的内部错误'); process.exitCode = 1; });
}

function request(account, route, method = 'GET', fields, requireData = true) {
  if (dry) return Promise.reject(new Error('预演禁止网络'));
  const requestStarted = Date.now();
  const endpoint = route.split('?')[0];
  log(`请求 ${method} ${endpoint}`);
  const body = fields ? new URLSearchParams(fields).toString() : '';
  const headers = {
    'User-Agent': 'okhttp/4.11.0', 'Content-Type': 'application/x-www-form-urlencoded',
    'Accept-Encoding': 'identity', os: 'OPPO:OPPO+R9s', osversion: '28',
    referer: 'api.58moto.com', version: '3.57.63', timestamp: String(Date.now()), token: account.token
  };
  if (body) headers['Content-Length'] = Buffer.byteLength(body);
  return new Promise((resolve, reject) => {
    let finished = false;
    const settle = (err, value) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      log(`${err ? '❌ 请求失败' : '✅ 请求业务码 0'}：${method} ${endpoint}；耗时 ${Date.now() - requestStarted}ms`);
      err ? reject(err) : resolve(value);
    };
    let req;
    const timer = setTimeout(() => {
      settle(new Error('网络请求失败或超时：timeout'));
      if (req) req.destroy();
    }, 15000);
    try {
    req = https.request(new URL(route, 'https://api.58moto.com'), { method, headers }, res => {
      const parts = []; let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) {
          settle(new Error('响应格式错误：响应过大'));
          req.destroy();
        }
        else parts.push(chunk);
      });
      res.on('aborted', () => settle(new Error('响应读取失败：连接中断')));
      res.on('error', () => settle(new Error('响应读取失败')));
      res.on('end', () => {
        if (finished) return;
        log(`HTTP ${method} ${endpoint}；状态 ${res.statusCode}`);
        if (res.statusCode !== 200) return settle(new Error(`HTTP 状态异常：${res.statusCode}`));
        try {
          const data = JSON.parse(Buffer.concat(parts).toString('utf8'));
          if (!data || data.code !== 0) {
            // 只显示短数字业务码和固定分类；不输出服务端消息或原始响应。
            const code = data && Number.isSafeInteger(data.code) && Math.abs(data.code) <= 999999
              ? String(data.code) : (data && typeof data.code === 'string' && /^-?\d{1,6}$/.test(data.code)
                ? `字符串(${data.code})` : '缺失或类型异常');
            const msg = data && typeof data.msg === 'string' ? data.msg : '';
            const category = /登录|登陆|token|凭证|认证|授权|过期/i.test(msg) ? '凭据或登录状态异常'
              : /参数|签名|版本/.test(msg) ? '参数或客户端校验异常'
              : /已签到|已经签到|重复签到/.test(msg) ? '重复签到提示（未确认成功业务码）'
              : /维护|停服|下线/.test(msg) ? '服务不可用提示'
              : /频繁|限流|稍后/.test(msg) ? '请求限制'
              : '未分类业务错误';
            return settle(new Error(`业务状态未成功：code=${code}；分类=${category}`));
          }
          if (requireData && (!data.data || typeof data.data !== 'object' || Array.isArray(data.data))) return settle(new Error('业务数据缺失'));
          settle(null, data.data);
        } catch { settle(new Error('响应格式错误')); }
      });
    });
    req.on('error', error => {
      const codes = ['ENOTFOUND', 'EAI_AGAIN', 'ECONNRESET', 'ECONNREFUSED', 'ETIMEDOUT', 'CERT_HAS_EXPIRED', 'UNABLE_TO_VERIFY_LEAF_SIGNATURE'];
      settle(new Error(`网络请求失败或超时：${codes.includes(error.code) ? error.code : '连接失败'}`));
    });
    req.end(body);
    } catch {
      settle(new Error('网络请求失败或超时：请求构建失败'));
      if (req) req.destroy();
    }
  });
}

function parse(line) {
  const at = line.indexOf('#');
  if (at <= 0) fail('配置格式错误，应为 token#uid');
  const token = line.slice(0, at).trim();
  const uid = line.slice(at + 1).trim();
  if (!token || /[\s\x00-\x1f\x7f]/.test(token) || !/^\d+$/.test(uid)) fail('配置格式错误，token 不得含空白且 uid 应为数字');
  return { token, uid };
}
function dateCode() {
  const d = new Date();
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
}
async function accountRun(line, index) {
  const t = Date.now();
  const stats = { total: 4, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let account;
  let previousFailed = false;
  const steps = [
    ['参数检查', async () => { account = parse(line); return '参数结构有效'; }],
    ['账号信息', async () => {
      const data = await request(account, '/user/center/info/v2/principal', 'POST', { uid: account.uid });
      if (typeof data.nickname === 'string' && data.nickname.trim()) {
        // 仅输出接口明确标记为昵称的身份字段，不输出手机号或原始响应。
        log(`账号 ${index} 昵称：${data.nickname.replace(/[\r\n\x00-\x1f\x7f]/g, ' ')}`);
      }
      if (typeof data.token !== 'string' || !data.token || /[\s\x00-\x1f\x7f]/.test(data.token)) fail('刷新凭据字段异常');
      account.token = data.token;
      return '账号信息及会话刷新成功';
    }],
    ['每日签到', async () => {
      // 按任务明确要求停用签到状态查询。成功依据沿用上游 dailyCheckIn 的数字 code === 0。
      // 不重试有副作用的提交；非零业务码（包括未经证实的重复签到码）仍按失败处理。
      await request(account, '/coins/task/dailyCheckIn', 'POST', { uid: account.uid, weekDate: dateCode() }, false);
      return '签到成功（签到提交业务码 0；按要求未查询签到状态）';
    }],
    ['能量查询', async () => {
      const data = await request(account, `/coins/account/energy?${new URLSearchParams({ uid: account.uid })}`);
      if (!['number', 'string'].includes(typeof data.available) || !/^\d+(\.\d+)?$/.test(String(data.available))) fail('能量字段异常');
      return `当前能量：${data.available}`;
    }]
  ];
  for (let n = 0; n < steps.length; n++) {
    const [name, action] = steps[n]; const st = Date.now();
    log(`账号 ${index} 阶段 ${n + 1}/4：${name}`);
    if (previousFailed && (n !== 3 || !account || stats.success < 2)) {
      stats.skipped++; log(`⏭️ 前置步骤失败，跳过；耗时 ${Date.now() - st}ms`); continue;
    }
    try {
      const result = dry && n > 0 ? '预演：已检查流程，未请求接口、未执行签到' : await action();
      if (dry && n > 0) stats.skipped++;
      else if (result.already) stats.alreadyComplete++;
      else stats.success++;
      log(`${dry && n > 0 ? '⏭️' : result.already ? '☑️' : '✅'} ${result.text || result}；耗时 ${Date.now() - st}ms`);
    } catch (error) {
      stats.failed++; previousFailed = true;
      // 错误仅来自本脚本固定文案，不透传 HTTP、依赖或服务端错误内容。
      const allowed = /^(配置格式错误|业务状态未成功|业务数据缺失|响应格式错误|HTTP 状态异常|网络请求失败或超时|响应读取失败|刷新凭据字段异常|签到状态字段异常|签到后状态未确认|能量字段异常)/;
      log(`❌ ${allowed.test(error.message) ? error.message : '步骤失败'}；耗时 ${Date.now() - st}ms`);
    }
    if (!dry && n > 0 && n < 3) await pause(1000);
  }
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${Date.now() - t}ms`);
  return stats;
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) return '预演：通知摘要已生成，禁止外部发送';
  const paths = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const modulePath = paths.find(p => fs.existsSync(p));
  if (!modulePath) return '不可用：未找到青龙 sendNotify.js';
  return new Promise(resolve => {
    const child = fork(__filename, ['--notification-worker'], { stdio: ['ignore', 'ignore', 'ignore', 'ipc'] });
    let settled = false;
    const finish = value => { if (!settled) { settled = true; clearTimeout(timer); resolve(value); } };
    const timer = setTimeout(() => { child.kill('SIGKILL'); finish('通知超时'); }, 20000);
    child.on('error', () => finish('通知失败'));
    child.on('exit', code => finish(code === 0 ? '已发送' : '通知失败'));
    child.send({ modulePath, title: TITLE, body }, error => { if (error) { child.kill(); finish('通知失败'); } });
  });
}
async function main() {
  const lines = (process.env.MOTO_TOKEN || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean);
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '无网络预演' : '正式运行'}；账号数：${lines.length}`);
  const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let successful = 0; let failed = 0;
  if (!lines.length) log('❌ 配置错误：请设置 MOTO_TOKEN，每行 token#uid');
  for (let i = 0; i < lines.length; i++) {
    const stats = await accountRun(lines[i], i + 1);
    for (const key of Object.keys(totals)) totals[key] += stats[key];
    if (stats.failed) failed++; else successful++;
  }
  const exitCode = failed || !lines.length ? 1 : 0;
  const status = !lines.length ? 'configuration-error' : failed ? (successful ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `${TITLE}：${status}；账号总数 ${lines.length}，成功数 ${successful}，失败数 ${failed}；子任务成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '通知失败'; }
  log('----------------------------------------');
  log(body);
  log(`通知状态：${notification}；总耗时 ${Date.now() - started}ms；完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify({ task: TITLE, mode: dry ? 'dry-run' : 'live', status, accounts: { total: lines.length, success: successful, failed }, tasks: totals, notification, durationMs: Date.now() - started, exitCode })}`);
  process.exitCode = exitCode;
}
