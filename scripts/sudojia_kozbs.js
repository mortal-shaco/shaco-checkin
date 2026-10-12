// name: 植白说官方商城
// cron: 18 9 * * *
/**
 * name: 植白说官方商城
 * cron: 18 9 * * *
 * SPDX-License-Identifier: GPL-3.0
 * 基于 sudojia/AutoTaskScript，作者 Telegram@sudojia
 * https://blog.imzjw.cn；原文件 src/wx_mini/sudojia_kozbs.js
 * KOZBS_TOKEN：登录植白说官方商城微信小程序，在本人授权的抓包环境中，
 * 查找 https://www.kozbs.com 请求头 x-dts-token，仅复制其值；每行一个账号。
 * KOZBS_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方业务依赖；仅执行积分查询、状态检查及必要的签到。
 */
'use strict';
const https = require('node:https');
const {fork} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const TITLE = '植白说官方商城';
const dry = process.env.KOZBS_DRY_RUN === '1';
const tokens = (process.env.KOZBS_TOKEN || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const stamp = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = s => console.log(`[${stamp()}] ${s}`);
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
function request(endpoint, token) {
  if (dry) return Promise.reject(new Error('预演禁止网络请求'));
  return new Promise((resolve,reject) => {
    const req = https.get(`https://www.kozbs.com/demo/wx/${endpoint}`, {headers: {
      'x-dts-token': token, xweb_xhr:'1',
      'User-Agent':'Mozilla/5.0', 'Content-Type':'application/json', Accept:'*/*',
      Referer:'https://servicewechat.com/wx6b6c5243359fe265/153/page-frame.html',
      'Accept-Language':'zh-CN,zh;q=0.9'
    }}, res => {
      let chunks = [], size = 0;
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('data', c => {
        size += c.length;
        if (size > 1024*1024) req.destroy(new Error('响应超过大小限制'));
        else chunks.push(c);
      });
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error(`HTTP 状态异常 ${res.statusCode}`));
        try {
          const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!value || value.errno !== 0) return reject(new Error('业务响应未明确成功，请检查登录凭据或接口'));
          resolve(value.data);
        } catch { reject(new Error('响应格式异常')); }
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时（详细错误已脱敏）')));
  });
}
// 通知在有时限的独立进程执行，异常不能改变业务退出码。
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) { log('⏭️ 断网预演：通知内容已生成，跳过外部投递'); return '预演未投递'; }
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = locations.find(p => fs.existsSync(p));
  if (!file) return '不可用（未找到 sendNotify.js）';
  return new Promise(resolve => {
    const child = fork(__filename, ['--notification-worker'], {stdio:['ignore','ignore','ignore','ipc'], env: {...process.env, KOZBS_TOKEN:''}});
    const timer = setTimeout(() => {child.kill(); resolve('投递超时');}, 20000);
    child.on('error', () => { clearTimeout(timer); resolve('投递失败'); });
    child.on('exit', code => {clearTimeout(timer); resolve(code === 0 ? '已投递' : '投递失败');});
    child.send({file,body});
  });
}
async function main() {
  const started = Date.now();
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date().toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${tokens.length}`);
  const results = [];
  let configError = tokens.length === 0;
  if (configError) log('❌ 配置错误：KOZBS_TOKEN 未配置非空账号');
  for (let i=0;i<tokens.length;i++) {
    const begin = Date.now();
    const stats = {account:i+1,total:3,success:0,alreadyComplete:0,skipped:0,failed:0};
    let stopped = false;
    const actions = [
      ['查询昵称与积分', async () => {
        const d = await request('user/getUserIntegral',tokens[i]);
        if (!d || !(typeof d.integer === 'number' || typeof d.integer === 'string' && /^\d+(\.\d+)?$/.test(d.integer))) throw new Error('积分字段缺失或异常');
        const name = d.list?.[0]?.userName;
        if (typeof name === 'string' && name) {
          // 仅公开身份可显示；凭据或手机号不能作为身份输出。
          if (!tokens.some(t => name.includes(t)) && !/\d{11}/.test(name) && !/[\r\n\x00-\x1f]/.test(name)) log(`账号 ${i+1} 昵称：${name}`);
          else log(`账号 ${i+1} 身份字段含敏感内容，已抑制`);
        }
        log(`当前积分：${d.integer}`);
      }],
      ['检查签到状态', async () => {
        const d = await request('home/signDay',tokens[i]);
        if (!d || ![0,1].includes(d.isSign)) throw new Error('签到状态字段异常');
        stats.signed = d.isSign === 1;
        log(stats.signed ? '☑️ 今天已经签到过了' : '尚未签到');
      }],
      ['每日签到', async () => {
        if (stats.signed) return 'already';
        await request('home/sign',tokens[i]);
        log('✅ 签到成功（errno=0）');
      }]
    ];
    for (let j=0;j<actions.length;j++) {
      const at = Date.now();
      log(`账号 ${i+1} · 阶段 ${j+1}/3：${actions[j][0]}`);
      if (stopped || dry) {
        stats.skipped++;
        log(`⏭️ ${dry ? '预演：参数已读取，不发请求、不签到' : '前置阶段失败，跳过'}；耗时 ${Date.now()-at}ms`);
        continue;
      }
      try {
        const outcome = await actions[j][1]();
        if (outcome === 'already') stats.alreadyComplete++; else stats.success++;
        log(`✅ 阶段完成；耗时 ${Date.now()-at}ms`);
      } catch (e) {
        stats.failed++; stopped = true;
        log(`❌ ${e.message}；耗时 ${Date.now()-at}ms`);
      }
      if (!stopped && j < 2) await wait(2000);
    }
    delete stats.signed;
    stats.ok = stats.failed === 0;
    stats.elapsedMs = Date.now()-begin;
    results.push(stats);
    log(`账号 ${i+1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${stats.elapsedMs}ms`);
  }
  const failed = results.filter(r=>!r.ok).length;
  const success = dry ? 0 : results.length-failed;
  const status = configError ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  process.exitCode = configError || failed ? 1 : 0;
  const body = `${TITLE}：${status}；账号总数 ${tokens.length}，成功 ${success}，失败 ${failed}，预演 ${dry ? results.length : 0}。${configError ? '请配置 KOZBS_TOKEN。' : ''}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '通知异常'; }
  console.log('----------------------------------------');
  log(body);
  const tasks = {total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  for (const r of results) for (const k of Object.keys(tasks)) tasks[k] += r[k];
  log(`子任务统计：${JSON.stringify(tasks)}；总耗时 ${Date.now()-started}ms；通知状态：${notification}`);
  log(`完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({status,accounts:tokens.length,success,failed,dryRun:dry,tasks,results,notification,elapsedMs:Date.now()-started}));
}
if (process.argv.includes('--notification-worker')) {
  process.once('message', async ({file,body}) => {
    try {await require(file).sendNotify(TITLE,body); process.exit(0);} catch {process.exit(1);}
  });
} else { main().catch(() => {console.error('任务内部异常（已脱敏）');process.exitCode=1;}); }
