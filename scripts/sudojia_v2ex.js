// name: V2EX每日签到
// cron: 0 9 * * *
/**
 * name: V2EX每日签到
 * cron: 0 9 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 基于 sudojia/AutoTaskScript src/web/sudojia_v2ex.js
 * 原作者 Telegram@sudojia https://blog.imzjw.cn，2024/5/22
 * V2EX_COOKIE：登录 https://www.v2ex.com 后，在开发者工具网络面板复制
 * 发往该站点的请求 Cookie 请求头值；每个非空行一个账号，不使用 & 分隔。
 * V2EX_DRY_RUN=1：完全断网预演（通知也仅模拟）；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方依赖；仅领取每日奖励，不更新脚本或发布内容。
 */
'use strict';
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const dry = process.env.V2EX_DRY_RUN === '1';
const started = Date.now();
const accounts = (process.env.V2EX_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const results = [];
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const stamp = () => new Date().toTimeString().slice(0, 8);
const log = text => console.log(`[${stamp()}] ${text}`);
function decode(s) {
  return s.replace(/&#(x[0-9a-f]+|\d+);/gi, (_, n) => {
    const c = n[0].toLowerCase() === 'x' ? parseInt(n.slice(1), 16) : Number(n);
    return c <= 0x10ffff ? String.fromCodePoint(c) : '';
  }).replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&');
}
const plain = s => decode(s.replace(/<[^>]*>/g, '')).replace(/[\r\n\t]/g, ' ').trim();
function request(route, cookie, depth = 0) {
  if (dry) throw Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const url = new URL(route, 'https://www.v2ex.com');
    if (url.origin !== 'https://www.v2ex.com') return reject(Error('拒绝跨站跳转'));
    const req = https.get(url, { headers: { Cookie: cookie, Accept: 'text/html', 'Accept-Encoding': 'identity', 'User-Agent': 'Mozilla/5.0 V2EXDaily/1.0' } }, res => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode)) {
        res.resume();
        if (depth >= 3 || !res.headers.location) return reject(Error('跳转异常'));
        let next;
        try { next = new URL(res.headers.location, url); } catch { return reject(Error('跳转异常')); }
        return resolve(request(next.href, cookie, depth + 1));
      }
      if (res.statusCode !== 200) { res.resume(); return reject(Error(`HTTP ${res.statusCode}`)); }
      let size = 0; const chunks = [];
      res.on('data', b => { size += b.length; if (size > 2 * 1024 * 1024) req.destroy(Error('响应超限')); else chunks.push(b); });
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
      res.on('error', () => reject(Error('响应读取失败')));
    });
    const timer = setTimeout(() => req.destroy(Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(Error('网络请求失败或超时')));
  });
}
function loggedIn(html) { if (!html.includes('登出')) throw Error('登录状态未验证，请重新获取 Cookie'); }
function identity(html) {
  for (const m of html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)) {
    if (/class\s*=\s*["'][^"']*\btop\b/.test(m[1]) && /href\s*=\s*["']\/member\//.test(m[1])) return plain(m[2]);
  }
  return '';
}
function balance(html) {
  const m = html.match(/<(?:a|div|span)\b[^>]*class=["'][^"']*\bbalance_area\b[^"']*["'][^>]*>([\s\S]*?)<\/(?:a|div|span)>/i);
  if (!m) throw Error('余额区域缺失');
  const nums = plain(m[1]).match(/\d+/g);
  if (!nums || nums.length > 3) throw Error('余额格式无法确认');
  const values = nums.map(Number); while (values.length < 3) values.unshift(0);
  return `${values[0]}金币 ${values[1]}银币 ${values[2]}铜币`;
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) { log('通知预演：' + body); return '预演模拟，未发送'; }
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = files.find(x => fs.existsSync(x));
  if (!file) return '不可用：未找到 sendNotify.js';
  return new Promise(resolve => {
    const env = { ...process.env }; delete env.V2EX_COOKIE;
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', file, 'V2EX每日签到', body], { env, stdio: 'ignore' });
    const timer = setTimeout(() => child.kill('SIGKILL'), 20000);
    child.on('error', () => { clearTimeout(timer); resolve('发送失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '发送失败'); });
  });
}
async function main() {
  console.log('========== V2EX每日签到 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式'}；账号数：${accounts.length}`);
  if (!accounts.length) log('❌ 配置错误：V2EX_COOKIE 未提供非空账号行');
  for (let i = 0; i < accounts.length; i++) {
    const begin = Date.now(); const stats = { total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let html = ''; let failed = false;
    const stages = ['登录校验及用户名', '每日奖励及连续天数', '账户余额'];
    for (let n = 0; n < 3; n++) {
      const tick = Date.now(); log(`账号[${i + 1}] 阶段 ${n + 1}/3 ${stages[n]} 开始`);
      let outcome = 'success';
      try {
        if (dry) { outcome = 'skipped'; log('⏭️ 仅验证流程，不请求站点、不领取奖励'); }
        else if (failed && n < 2) { outcome = 'skipped'; log('⏭️ 前置阶段失败'); }
        else if (n === 0) {
          if (!accounts[i].includes('=') || /[\x00-\x1f\x7f]/.test(accounts[i])) throw Error('Cookie 格式错误');
          html = await request('/mission/daily', accounts[i]); loggedIn(html);
          const name = identity(html); log(name ? `✅ 用户名称：${name}` : '✅ 登录有效；未返回用户名');
        } else if (n === 1) {
          if (html.includes('每日登录奖励已领取')) { outcome = 'alreadyComplete'; log('☑️ 已经签到过了'); }
          else {
            const once = html.match(/\/mission\/daily\/redeem\?once=(\d+)/);
            if (!once) throw Error('领取入口缺失或响应已变化');
            await new Promise(r => setTimeout(r, 2000));
            html = await request(`/mission/daily/redeem?once=${once[1]}`, accounts[i]);
            loggedIn(html);
            if (!html.includes('每日登录奖励已领取')) throw Error('未验证到奖励领取成功');
            log('✅ 签到成功');
          }
          const days = plain(html).match(/已连续登录\s*(\d+)\s*天/);
          log(days ? `连续签到：${days[1]}天` : '连续签到天数：页面未提供');
        } else {
          const data = await request('/balance', accounts[i]); loggedIn(data); log('✅ 账户余额：' + balance(data));
        }
      } catch (e) { outcome = 'failed'; failed = true; log('❌ ' + e.message); }
      stats[outcome]++; log(`账号[${i + 1}] 阶段 ${n + 1}/3 耗时 ${Date.now() - tick}ms`);
    }
    for (const k of Object.keys(totals)) totals[k] += stats[k];
    results.push({ account: i + 1, status: failed ? 'failure' : dry ? 'dry-run' : 'success', ...stats });
    log(`账号[${i + 1}] 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${Date.now() - begin}ms`);
  }
  const failures = results.filter(x => x.status === 'failure').length;
  const successes = dry ? 0 : results.length - failures;
  const code = !accounts.length || failures ? 1 : 0;
  const status = !accounts.length ? 'configuration-error' : failures ? successes ? 'partial-failure' : 'failure' : dry ? 'dry-run' : 'success';
  const body = `状态：${status}；账号总数：${accounts.length}；成功：${successes}；失败：${failures}；预演：${dry ? accounts.length : 0}`;
  const notification = await notify(body);
  console.log('----------------------------------------');
  log(body); log(`子任务统计：${JSON.stringify(totals)}`);
  log(`通知：${notification}；总耗时：${Date.now() - started}ms；完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ status, accounts: accounts.length, success: successes, failed: failures, dryRun: dry, tasks: totals, results, notification }));
  process.exitCode = code;
}
main();
