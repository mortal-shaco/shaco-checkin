// name: 网易蜗牛读书
// cron: 52 9 * * *
/*
 * name: 网易蜗牛读书
 * cron: 52 9 * * *
 * 上游：OreosLab/checkinpanel，ck_du163.js
 * 原始提交：911402e4b2e559ffd62c4949a971ddd6834edd7d
 * SPDX-License-Identifier: MIT
 *
 * MIT License
 * Copyright (c) original contributors to OreosLab/checkinpanel
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 * 参数：DU163_COOKIE，每个非空行一个账号：完整 Cookie|可选 User-Agent。
 * 仅在第一个 | 处分割；Cookie 的分号分隔保持原样。兼容 DU163 同格式输入。
 * 获取：登录网易蜗牛读书官方网站，在浏览器开发者工具网络面板找到
 * sign.json 请求，复制请求 Cookie（必须含 _xsrf）及可选 User-Agent。
 * 不要分享 Cookie。旧 utils/getData 私有配置无需保留。
 * DU163_DRY_RUN=1 完全断网：校验参数并模拟响应与通知，不验证真实账号。
 * QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭通知。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录。
 */
'use strict';
const https = require('https');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const TITLE = '网易蜗牛读书';
const ENDPOINT = 'https://du.163.com/activity/201907/activityCenter/sign.json';
const dry = /^(1|true|yes|on)$/i.test(process.env.DU163_DRY_RUN || '');
const now = () => new Date().toISOString();
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = (message) => console.log(`[${stamp()}] ${message}`);

function parseAccount(line) {
  const split = line.indexOf('|');
  const cookie = (split < 0 ? line : line.slice(0, split)).trim();
  const userAgent = split < 0 ? '' : line.slice(split + 1).trim();
  if (/[\r\n\x00-\x1f\x7f]/.test(cookie + userAgent)) throw new Error('凭据含不合法控制字符');
  const csrf = cookie.split(';').map(s => s.trim()).find(s => s.startsWith('_xsrf='));
  if (!csrf || !csrf.slice(6).trim()) throw new Error('Cookie 缺少非空 _xsrf 字段');
  return { cookie, userAgent, csrf: csrf.slice(6).trim() };
}

function sign(account) {
  const body = new URLSearchParams({ csrfToken: account.csrf }).toString();
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(value);
    };
    const headers = { Cookie: account.cookie, 'Content-Type': 'application/x-www-form-urlencoded',
      'Content-Length': Buffer.byteLength(body) };
    if (account.userAgent) headers['User-Agent'] = account.userAgent;
    const req = https.request(ENDPOINT, { method: 'POST', headers }, res => {
      if (res.statusCode < 200 || res.statusCode >= 300) {
        res.resume();
        finish(new Error(`HTTP ${res.statusCode}，签到未确认`));
        return;
      }
      let size = 0;
      const chunks = [];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 65536) {
          finish(new Error('响应过大，签到未确认'));
          res.destroy();
          req.destroy();
        } else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应被中断')));
      res.on('end', () => {
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error();
          finish(null, data);
        } catch (_) { finish(new Error('响应 JSON 无效')); }
      });
    });
    timer = setTimeout(() => {
      finish(new Error('请求超过 15 秒，签到未确认'));
      req.destroy();
    }, 15000);
    req.on('error', () => finish(new Error('网络请求失败，签到未确认')));
    req.end(body);
  });
}

function identity(data, account) {
  for (const key of ['nickname', 'username', 'displayName', 'uid']) {
    const value = data[key];
    if (typeof value !== 'string' && typeof value !== 'number') continue;
    const text = String(value);
    if (!text || /[\x00-\x1f\x7f]|1[3-9]\d{9}/.test(text)) continue;
    if ([account.cookie, account.csrf, account.userAgent].some(s => s && text.includes(s))) continue;
    log(`官方账号身份（${key}）：${text}`);
  }
}

async function notify(summary) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) {
    log(`⏭️ 断网预演通知：${summary}`);
    return '断网模拟';
  }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const modulePath = dirs.map(dir => path.join(dir, 'sendNotify.js')).find(p => fs.existsSync(p));
  if (!modulePath) return '不可用（未找到 sendNotify.js）';
  // 独立进程限制通知时间，抑制通知库可能输出的配置或响应。
  return new Promise(resolve => {
    const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))';
    const child = spawn(process.execPath, ['-e', code, modulePath, TITLE, summary], { stdio: 'ignore' });
    const timer = setTimeout(() => child.kill('SIGKILL'), 15000);
    child.on('error', () => { clearTimeout(timer); resolve('发送失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '发送失败或超时'); });
  });
}

async function main() {
  const started = Date.now();
  const startTime = now();
  const lines = (process.env.DU163_COOKIE || process.env.DU163 || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const results = [];
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${startTime}；模式：${dry ? '断网预演' : '真实签到'}；账号数：${lines.length}`);
  if (!lines.length) log('❌ 配置错误：请设置 DU163_COOKIE，每行一个账号，Cookie 必须含 _xsrf');
  for (let i = 0; i < lines.length; i++) {
    const t = Date.now();
    let stage = Date.now();
    const item = { account: i + 1, total: 1, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    log(`账号 ${i + 1} / 阶段 1：校验 Cookie 与可选 User-Agent`);
    try {
      const account = parseAccount(lines[i]);
      log(`✅ 参数校验通过；阶段 1 耗时 ${Date.now() - stage} 毫秒`);
      stage = Date.now();
      log(`账号 ${i + 1} / 阶段 2：${dry ? '模拟每日签到（无网络）' : '提交每日签到'}`);
      if (dry) {
        item.success = 1;
        log('✅ DRY_RUN_OK：签到请求构造通过；真实业务未验证');
      } else {
        const data = await sign(account);
        identity(data, account);
        if (data.code === 0 || data.code === '0') {
          item.success = 1;
          const days = Number(data.continuousSignedDays);
          log(`✅ 签到成功${Number.isInteger(days) && days >= 0 ? `，连签 ${days} 天` : ''}`);
        } else if (data.code === -1104 || data.code === '-1104') {
          // 上游单独展示此码，但未证明其代表成功；禁止据此误报已签到。
          throw new Error('业务码 -1104，签到状态未确认，请在官方页面核对');
        } else throw new Error('业务响应未确认签到成功，请检查凭据或接口状态');
      }
      log(`阶段 2 耗时 ${Date.now() - stage} 毫秒`);
    } catch (error) {
      item.failed = 1;
      // 错误仅来自本文件固定文案；不输出网络库错误或响应正文。
      log(`❌ ${error.message}；当前阶段耗时 ${Date.now() - stage} 毫秒`);
    }
    item.durationMs = Date.now() - t;
    results.push(item);
    log(`账号 ${i + 1} 统计：总任务 ${item.total}，成功 ${item.success}，已完成 ${item.alreadyComplete}，跳过 ${item.skipped}，失败 ${item.failed}；耗时 ${item.durationMs} 毫秒`);
  }
  const failed = results.filter(r => r.failed).length;
  const successful = results.length - failed;
  const status = !lines.length ? 'configuration-error' : failed ? successful ? 'partial-failure' : 'failure' : dry ? 'dry-run' : 'success';
  const exitCode = !lines.length || failed ? 1 : 0;
  const body = `${TITLE}：模式 ${dry ? '断网预演，未验证真实业务' : '真实签到'}；账号总数 ${lines.length}，成功 ${successful}，失败 ${failed}；状态 ${status}`;
  log('阶段 3：发送脱敏任务通知');
  const notificationStart = Date.now();
  const notification = await notify(body);
  log(`通知状态：${notification}；阶段 3 耗时 ${Date.now() - notificationStart} 毫秒`);
  const summary = { task: TITLE, mode: dry ? 'dry-run' : 'live', status, accounts: lines.length,
    successful, failed, tasks: results.reduce((a, r) => a + r.total, 0),
    success: results.reduce((a, r) => a + r.success, 0),
    alreadyComplete: results.reduce((a, r) => a + r.alreadyComplete, 0),
    skipped: 0, failedTasks: failed, results, startTime, finishTime: now(), durationMs: Date.now() - started,
    notification, exitCode };
  log('----------------------------------------');
  log(body);
  log(`子任务：总数 ${summary.tasks}，成功 ${summary.success}，已完成 ${summary.alreadyComplete}，跳过 0，失败 ${summary.failedTasks}`);
  log(`完成时间：${summary.finishTime}；总耗时 ${summary.durationMs} 毫秒；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
  return summary;
}

if (require.main === module) main().catch(() => { log('❌ 任务执行器异常'); process.exitCode = 1; });
module.exports = main;
