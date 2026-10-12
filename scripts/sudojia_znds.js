// name: 智能电视签到
// cron: 5 11 * * *
/**
 * name: 智能电视签到
 * cron: 5 11 * * *
 * 来源 sudojia/AutoTaskScript src/web/sudojia_znds.js
 * 作者 Telegram@sudojia https://blog.imzjw.cn （2024/5/31）
 * SPDX-License-Identifier: GPL-3.0-only
 * 本维护版本延续 GPL-3.0 许可：https://www.gnu.org/licenses/gpl-3.0.html
 * Node.js >=18；公开依赖：cheerio@1.0.0。
 * ZNDS_COOKIE：登录 https://www.znds.com 后，在浏览器开发者工具的网络面板
 * 复制本站已登录请求的 Cookie 请求头（含 auth、saltkey），不要复制 Set-Cookie。
 * 每个非空行一个账号，完整保留 Cookie 中的 &、= 等字符。
 * ZNDS_VISIT_UID：可选，自行从目标用户空间链接 uid 参数获取；不设置则不访问他人空间。
 * ZNDS_DRY_RUN=1：完全断网，仅验证配置和演练流程；通知也仅演练。
 * QINGLONG_NOTIFY=0 可关闭通知；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
 */
'use strict';
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const dry = process.env.ZNDS_DRY_RUN === '1';
const accounts = (process.env.ZNDS_COOKIE || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const visit = (process.env.ZNDS_VISIT_UID || '').trim();
const start = Date.now();
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const summary = { task: '智能电视签到', mode: dry ? 'dry-run' : 'live', accounts: accounts.length, success: 0, failed: 0, status: '', notification: '', steps: totals };
const log = s => console.log(`[${new Date().toTimeString().slice(0, 8)}] ${s}`);
function request(url, cookie) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const req = https.request(url, { method: 'POST', headers: { Cookie: cookie, 'User-Agent': 'Mozilla/5.0', Accept: 'text/html,application/xml', 'Accept-Encoding': 'identity', 'Content-Length': '0' } }, res => {
      let size = 0; const chunks = [];
      res.on('data', c => { size += c.length; if (size > 2 * 1024 * 1024) req.destroy(new Error('响应超限')); else chunks.push(c); });
      res.on('end', () => { if (res.statusCode !== 200) reject(new Error('HTTP状态异常')); else resolve(Buffer.concat(chunks).toString('utf8')); });
      res.on('error', () => reject(new Error('响应读取失败')));
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    req.end();
  });
}
function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) { log(`通知预演：${body}`); return '断网预演（未发送）'; }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  for (const dir of dirs) {
    const js = path.join(dir, 'sendNotify.js');
    const py = path.join(dir, 'notify.py');
    let result;
    if (fs.existsSync(js)) result = spawnSync(process.execPath, ['-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', js, summary.task, body], { timeout: 20000, stdio: 'ignore' });
    else if (fs.existsSync(py)) result = spawnSync('python3', ['-c', 'import sys;sys.path.insert(0,sys.argv[1]);import notify;notify.send(sys.argv[2],sys.argv[3])', dir, summary.task, body], { timeout: 20000, stdio: 'ignore' });
    if (result && result.status === 0) return '已发送';
  }
  const fallback = spawnSync('python3', ['-c', 'import notify,sys;notify.send(sys.argv[1],sys.argv[2])', summary.task, body], { timeout: 20000, stdio: 'ignore' });
  return fallback.status === 0 ? '已发送' : '不可用或发送失败（保留业务退出码）';
}
async function main() {
  log(`========== 智能电视签到 ==========\n开始时间：${new Date(start).toISOString()}\n模式：${summary.mode}\n账号数：${accounts.length}`);
  let configError = !accounts.length || (visit && !/^\d+$/.test(visit));
  let cheerio;
  if (!dry && !configError) { try { cheerio = require('cheerio'); } catch { configError = true; log('❌ 缺少公开依赖，请安装 cheerio@1.0.0'); } }
  if (configError) log('❌ 配置错误：需要非空 ZNDS_COOKIE，目标 UID 必须为数字');
  for (let i = 0; i < accounts.length && !configError; i++) {
    const begun = Date.now();
    const stats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let uid, hash;
    async function step(n, name, action) {
      const t = Date.now(); stats.total++; log(`账号 ${i + 1} 阶段 ${n}：${name}`);
      try { const result = await action(); const state = result || 'success'; stats[state]++; log(`${state === 'skipped' ? '⏭️' : state === 'alreadyComplete' ? '☑️' : '✅'} ${name}：${state}，耗时 ${Date.now() - t}ms`); }
      catch { stats.failed++; log(`❌ ${name}失败：配置、网络或业务响应未通过校验，耗时 ${Date.now() - t}ms`); }
    }
    await step(1, '验证登录身份', async () => {
      if (!/(?:^|;\s*)[^;=]*auth=[^;\s]+/.test(accounts[i]) || !/(?:^|;\s*)[^;=]*saltkey=[^;\s]+/.test(accounts[i]) || /[\r\n\x00]/.test(accounts[i])) throw Error();
      if (dry) { uid = 'dry'; return; }
      const $ = cheerio.load(await request('https://www.znds.com/', accounts[i]));
      uid = ($('a.avts').attr('href') || '').match(/[?&]uid=(\d+)/)?.[1];
      $('a[href*="mod=logging"]').each((_, a) => { const href = $(a).attr('href'); if (href.includes('action=logout')) hash = href.match(/[?&]formhash=([a-zA-Z0-9]+)/)?.[1]; });
      if (!uid || !hash) { uid = undefined; throw Error(); }
      log(`官方公开 UID：${uid}`);
    });
    await step(2, '每日签到', async () => {
      if (!uid) return 'skipped'; if (dry) return;
      const html = await request(`https://www.znds.com/plugin.php?id=ljdaka:daka&action=msg&formhash=${encodeURIComponent(hash)}&infloat=yes&handlekey=ljdaka&inajax=1&ajaxtarget=fwin_content_ljdaka`, accounts[i]);
      const $ = cheerio.load(html.replace(/^\s*<\?xml[^>]*>\s*<root><!\[CDATA\[([\s\S]*)\]\]><\/root>\s*$/, '$1'));
      const text = $('div.alert_info').first().text().trim();
      if (/今日已签到|今天已经签到|今日已经签到|今天已签到|今日已打卡|今天已经打卡/.test(text)) return 'alreadyComplete';
      if (!/签到成功|打卡成功/.test(text) || /失败|错误|未成功/.test(text)) throw Error();
    });
    await step(3, '可选访问空间', async () => {
      if (!uid || !visit) return 'skipped'; if (dry) return;
      if (visit === uid) throw Error();
      const $ = cheerio.load(await request(`https://www.znds.com/home.php?mod=space&uid=${visit}`, accounts[i]));
      if (!$('#uhd').length || !$('#statistic_content').length) throw Error();
      log('目标空间页面已验证；不推断访问奖励到账');
    });
    await step(4, '查询积分、威望、金币和Z币', async () => {
      if (!uid) return 'skipped'; if (dry) return;
      const $ = cheerio.load(await request(`https://www.znds.com/home.php?mod=space&uid=${uid}`, accounts[i]));
      const values = {};
      $('#statistic_content .xl li').each((_, el) => { const text = $(el).text().trim(); for (const label of ['积分', '威望', '金币', 'Z币']) if (text.includes(label)) { const value = $(el).find('a').text().trim(); if (/^-?\d+(?:\.\d+)?$/.test(value)) values[label] = value; } });
      if (Object.keys(values).length !== 4) throw Error();
      log(Object.entries(values).map(([k, v]) => `${k}：${v}`).join('，'));
    });
    for (const k of Object.keys(totals)) totals[k] += stats[k];
    if (stats.failed) summary.failed++; else summary.success++;
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now() - begun}ms`);
  }
  summary.status = configError ? 'configuration-error' : summary.failed ? (summary.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  process.exitCode = configError || summary.failed ? 1 : 0;
  if (configError) summary.failed = accounts.length;
}
main().catch(() => { summary.status = 'failure'; process.exitCode = 1; log('❌ 任务发生异常（详细信息已隐藏）'); }).finally(() => {
  const body = `状态：${summary.status}；账号总数：${summary.accounts}；成功：${summary.success}；失败：${summary.failed}；子任务成功：${totals.success}；已完成：${totals.alreadyComplete}；跳过：${totals.skipped}；失败：${totals.failed}`;
  try { summary.notification = notify(body); } catch { summary.notification = '通知异常（保留业务退出码）'; }
  summary.elapsedMs = Date.now() - start;
  log(`--------------------\n${body}\n总耗时：${summary.elapsedMs}ms\n完成时间：${new Date().toISOString()}\n通知状态：${summary.notification}\n最终状态：${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
});
