// name: 水费易签到
// cron: 4 0 * * *
/**
 * name: 水费易签到
 * cron: 3 9 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 原作者 Telegram@sudojia，https://blog.imzjw.cn
 * 来源 sudojia/AutoTaskScript src/public/sudojia_shuifei.js
 * SHUI_FEI_COOKIE：水费易公众号中打开个人中心，抓取 https://m.ipaiyun.cn
 * 请求头 Cookie 和请求正文 memberId，每行 Cookie#memberId；仅在首个 # 处分割。
 * SHUI_FEI_DRY_RUN=1：断网校验配置与流程，通知仅模拟，不代表业务成功。
 * QINGLONG_NOTIFY=0：关闭通知；QINGLONG_NOTIFY_DIR：可选青龙通知模块目录。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const started = Date.now();
const dry = process.env.SHUI_FEI_DRY_RUN === '1';
const lines = (process.env.SHUI_FEI_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const secrets = lines.flatMap(x => { const i = x.indexOf('#'); return [x, x.slice(0, i), x.slice(i + 1), ...x.slice(0, i).split(';').map(v => v.slice(v.indexOf('=') + 1).trim())]; }).filter(Boolean);
const safe = value => { let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' '); for (const secret of secrets) s = s.split(secret).join('[凭据已隐藏]'); return s.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]'); };
const log = text => console.log(`[${new Date().toTimeString().slice(0, 8)}] ${text}`);
function request(action, account) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams({ memberId: account.memberId }).toString();
    const req = https.request({ hostname: 'm.ipaiyun.cn', path: `/PersonalCenter/PersonalCenter/${action}`, method: 'POST', headers: {
      'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      Accept: 'application/json', Origin: 'https://m.ipaiyun.cn', Referer: 'https://m.ipaiyun.cn/Ipai/Home/Index',
      Cookie: account.cookie, 'Content-Length': Buffer.byteLength(body)
    } }, res => {
      const chunks = []; let size = 0;
      res.on('data', chunk => { size += chunk.length; if (size > 1048576) res.destroy(new Error('响应过大')); else chunks.push(chunk); });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error('HTTP 状态异常'));
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (data.code !== 0) throw new Error('业务状态未确认成功');
          if (!data.resultJson || typeof data.resultJson !== 'object') throw new Error('业务数据缺失');
          resolve(data.resultJson);
        } catch (_) { reject(new Error('业务状态或响应结构异常')); }
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    req.end(body);
  });
}
const number = x => typeof x === 'number' && Number.isFinite(x) && x >= 0;
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) return '断网预演：已模拟通知';
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(d => path.join(d, 'sendNotify.js')).find(f => fs.existsSync(f));
  if (!file) return '通知不可用（未找到 sendNotify.js）';
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', 'Promise.resolve(require(process.argv[1]).sendNotify("水费易签到",process.argv[2])).then(()=>process.exit(0)).catch(()=>process.exit(1))', file, body], { stdio: 'ignore' });
    const timer = setTimeout(() => { child.kill('SIGKILL'); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve('通知发送失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '通知已发送' : '通知发送失败或超时'); });
  });
}
async function main() {
  log('========== 水费易签到 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${lines.length}`);
  const results = [];
  for (let i = 0; i < lines.length; i++) {
    const begin = Date.now(); const stats = { account: i + 1, total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let stage = 0;
    async function step(name, fn) { stage++; const t = Date.now(); log(`账号 ${i + 1} 阶段 ${stage}/3 ${name} 开始`); try { const value = await fn(); log(`账号 ${i + 1} 阶段 ${stage}/3 ${name} 完成，耗时 ${Date.now() - t}ms`); return value; } catch (e) { log(`❌ 账号 ${i + 1} 阶段 ${stage}/3 ${name} 失败：${e.message}，耗时 ${Date.now() - t}ms`); throw e; } }
    try {
      const pos = lines[i].indexOf('#');
      const account = { cookie: lines[i].slice(0, pos).trim(), memberId: lines[i].slice(pos + 1).trim() };
      if (pos < 1 || !account.cookie || !account.memberId || /[\x00-\x1f\x7f]/.test(lines[i])) throw new Error('配置错误：需要 Cookie#memberId');
      if (dry) {
        for (const name of ['用户信息查询', '按剩余次数签到', '积分查询']) await step(name, async () => { log('⏭️ DRY_RUN_OK：流程校验通过，未发送请求'); stats.skipped++; });
      } else {
        const detail = await step('用户信息查询', async () => {
          const d = await request('GetShopMemberDetail', account);
          if (!d.userMember || !number(d.signNum) || !Number.isInteger(d.signNum)) throw new Error('用户信息或剩余签到次数结构异常');
          if (typeof d.userMember.nickName === 'string') log(`账号昵称：${safe(d.userMember.nickName)}`);
          log(`剩余签到次数：${d.signNum}`); return d;
        }); stats.success++;
        await step('签到', async () => {
          if (detail.signNum === 0) { stats.alreadyComplete++; log('☑️ 今日已签到'); return; }
          const d = await request('ShopMemberSign', account);
          if (!number(d.signdays) || !Number.isInteger(d.signdays) || d.signdays < 1) throw new Error('连续签到天数结构异常');
          stats.success++; log(`✅ 签到成功，已连续签到${d.signdays}天`);
        });
        await step('积分查询', async () => {
          const d = await request('GetShopMemberDetail', account);
          if (!d.meberinfo || !number(d.meberinfo.totalIntegral)) throw new Error('积分结构异常');
          log(`当前积分：${d.meberinfo.totalIntegral}`); stats.success++;
        });
      }
    } catch (e) { stats.failed++; stats.skipped = stats.total - stats.success - stats.alreadyComplete - stats.failed; log(`❌ 账号 ${i + 1}：${e.message}`); }
    stats.durationMs = Date.now() - begin; results.push(stats);
    log(`账号 ${i + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs}ms`);
  }
  if (!lines.length) log('❌ 配置错误：SHUI_FEI_COOKIE 未设置');
  const failed = results.filter(r => r.failed).length;
  const status = !lines.length ? 'configuration-error' : failed ? (failed === lines.length ? 'failure' : 'partial-failure') : dry ? 'dry-run' : 'success';
  process.exitCode = failed || !lines.length ? 1 : 0;
  const summary = { status, mode: dry ? 'dry-run' : 'live', accounts: lines.length, success: dry ? 0 : lines.length - failed, failed, rehearsed: dry ? lines.length - failed : 0, results };
  const body = `账号总数：${summary.accounts}，成功：${summary.success}，失败：${failed}，预演通过：${summary.rehearsed}；状态：${status}`;
  const notification = await notify(body);
  log('----------------------------------------'); log(body);
  log(`子任务统计：成功 ${results.reduce((n,r)=>n+r.success,0)}，已完成 ${results.reduce((n,r)=>n+r.alreadyComplete,0)}，跳过 ${results.reduce((n,r)=>n+r.skipped,0)}，失败 ${results.reduce((n,r)=>n+r.failed,0)}`);
  log(`通知状态：${notification}；总耗时：${Date.now()-started}ms；完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ ...summary, notification }));
}
main().catch(() => { process.exitCode = 1; console.error('任务发生未预期错误'); });
