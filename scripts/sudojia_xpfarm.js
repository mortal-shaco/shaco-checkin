// name: 兴攀农场
// cron: 50 11,18 * * *
/**
 * name: 兴攀农场
 * cron: 50 11,18 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Derived from sudojia/AutoTaskScript, src/wx_mini/sudojia_xpfarm.js
 * Original author: Telegram@sudojia — https://blog.imzjw.cn (2024/08/21)
 * 小程序：兴攀农场。抓取 https://p.xpfarm.cn 请求头 authorization 原值，
 * 设置 XPFARM_TOKEN，每个非空行一个账号，不使用 & 或 @ 分隔。
 * 默认仅签到及查询。XPFARM_TASK_IDS 可填经小程序确认的任务编号（1–16，逗号分隔）；
 * XPFARM_FERTILIZER_LIMIT、XPFARM_WATER_LIMIT 为本次最多消耗操作次数，默认 0。
 * 请确认具体任务含义和资源消耗后启用；不会自动遍历未知任务。
 * XPFARM_DRY_RUN=1 完全断网（含通知）；QINGLONG_NOTIFY=0 关闭通知。
 * Node.js >=18，无第三方业务依赖，无自动更新、下载或安装。
 */
'use strict';
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const started = Date.now();
const dry = process.env.XPFARM_DRY_RUN === '1';
const accounts = (process.env.XPFARM_TOKEN || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const totals = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
const summary = { task: '兴攀农场', mode: dry ? 'dry-run' : 'live', accounts: accounts.length, success: 0, failed: 0, configurationError: false, steps: totals };
const stamp = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = text => console.log(`[${stamp()}] ${text}`);
const pause = () => new Promise(resolve => setTimeout(resolve, 1500));
function numeric(data, key) {
  const v = data && data[key];
  if ((typeof v !== 'number' && typeof v !== 'string') || String(v).trim() === '' || !Number.isFinite(Number(v)) || Number(v) < 0) throw new Error('响应字段无效');
  return Number(v);
}
function request(token, endpoint, body) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const payload = body === undefined ? '' : JSON.stringify(body);
    let done = false;
    const finish = (error, result) => { if (done) return; done = true; clearTimeout(timer); error ? reject(error) : resolve(result); };
    const req = https.request({hostname:'p.xpfarm.cn', path:'/treemp/' + endpoint, method:'POST', headers:{
      authorization:token, 'Content-Type':'application/json', 'Content-Length':Buffer.byteLength(payload),
      'User-Agent':'Mozilla/5.0', xweb_xhr:'1', Accept:'*/*',
      Referer:'https://servicewechat.com/wx27e219ff3142b7c8/63/page-frame.html'
    }}, res => {
      let bytes = 0; const chunks = [];
      res.on('data', chunk => { bytes += chunk.length; if (bytes > 262144) { finish(new Error('响应过大')); res.destroy(); req.destroy(); } else chunks.push(chunk); });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应中断')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error('HTTP 请求失败'));
        try {
          const json = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!json || json.code !== 1000) return finish(new Error('业务未确认成功'));
          finish(null, json.data);
        } catch { finish(new Error('响应格式无效')); }
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超时')); req.destroy(); }, 15000);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(payload);
  });
}
function limit(name) {
  const v = process.env[name] || '0';
  if (!/^\d+$/.test(v) || Number(v) > 100) throw new Error('操作上限必须为 0–100 整数');
  return Number(v);
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) return '预演：已生成脱敏通知，未发送（断网）';
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(dir => path.join(dir, 'sendNotify.js')).find(p => fs.existsSync(p));
  if (!file) return '不可用：未找到 sendNotify.js';
  // 子进程隔离通知模块日志和异常，且不传入业务凭据。
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify("兴攀农场",process.argv[2])).then(()=>process.exit(0),()=>process.exit(1))', file, body], {
      stdio:'ignore', env:Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('XPFARM_')))
    });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('发送超时'); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve('发送失败'); });
    child.on('exit', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '发送失败'); });
  });
}
async function runAccount(token, index, config) {
  const begin = Date.now();
  const stats = { total:0, success:0, alreadyComplete:0, skipped:0, failed:0 };
  let stage = 0;
  async function step(title, action, enabled = true) {
    const t = Date.now(); stage++; stats.total++;
    log(`账号 ${index} 阶段 ${stage}：${title}`);
    try {
      let status;
      if (!enabled) { status = 'skipped'; log('⏭️ 未配置此操作'); }
      else if (dry) { status = 'skipped'; log('⏭️ DRY_RUN_OK：仅检查流程，不发送请求'); }
      else { status = await action() || 'success'; log(status === 'alreadyComplete' ? '☑️ 已完成' : '✅ 已验证成功'); }
      stats[status]++;
      return status === 'success' || status === 'alreadyComplete';
    } catch (error) { stats.failed++; log(`❌ ${error.message}`); return false; }
    finally { log(`账号 ${index} 阶段 ${stage} 耗时 ${Date.now()-t}ms`); if (!dry && enabled) await pause(); }
  }
  const api = (name, body) => request(token, name, body);
  const identified = await step('账号信息', async () => {
    const data = await api('user.PersonalCenter/getInfo');
    if (!data || typeof data !== 'object') throw new Error('账号信息缺失');
    // 仅展示官方非凭据昵称，不输出手机号或服务器消息。
    if (typeof data.nickname === 'string' && data.nickname) {
      if (!accounts.some(secret => data.nickname.includes(secret)) && !/[\r\n\x00-\x1f]|1[3-9]\d{9}/.test(data.nickname)) log(`昵称：${data.nickname}`);
    }
  });
  if (identified || dry) {
    await step('每日签到', async () => {
      const info = await api('user.PersonalCenter/getSigninInfo');
      if (!info || ![0, 1].includes(info.isSignInToday)) throw new Error('签到状态无效');
      if (info.isSignInToday === 1) return 'alreadyComplete';
      await pause(); await api('user.PersonalCenter/addSignIn');
    });
    if (!config.ids.length) await step('任务完成及领奖', async () => {}, false);
    for (const id of config.ids) {
      const completed = await step(`完成任务 ${id}`, () => api('tree.Tasks/completeTask', {task_id:id}).then(() => undefined));
      await step(`领取任务 ${id} 奖励`, async () => { await api('tree.Tasks/receiveTaskReward', {task_id:id}); }, completed || dry);
    }
    await step('积分查询', async () => log(`当前积分：${numeric(await api('user.PersonalCenter/getInfo'), 'integral')}`));
    for (const [title, endpoint, field, cap, body, threshold] of [
      ['施肥','addFertilizer','fertilizer_value',config.fertilizer,{type:0},0],
      ['浇水','addWater','water_value',config.water,undefined,10]
    ]) {
      await step(title, async () => {
        let previous = Infinity;
        for (let n=0;n<cap;n++) {
          const data = await api('tree.Tasks/' + endpoint, body);
          const remaining = numeric(data, field);
          log(`${title}第 ${n+1} 次成功，剩余资源：${remaining}，肥力：${numeric(data,'fertilizer')}`);
          if (remaining <= threshold) break;
          if (remaining >= previous) throw new Error('资源未递减，停止重复操作');
          previous = remaining;
          if (n+1<cap) await pause();
        }
      }, cap > 0);
    }
    await step('种树进度查询', async () => {
      const data = await api('tree.Tasks/getHomePage');
      const typeName = typeof data.type_name === 'string' && !/[\r\n\x00-\x1f]|1[3-9]\d{9}/.test(data.type_name) && !accounts.some(secret => data.type_name.includes(secret)) ? data.type_name : '种树';
      log(`当前进度：${typeName} ${numeric(data,'growth_level')}%，剩余水滴：${numeric(data,'water_value')}，剩余肥力：${numeric(data,'fertilizer')}`);
    });
  }
  for (const key of Object.keys(totals)) totals[key] += stats[key];
  summary[stats.failed ? 'failed' : 'success']++;
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now()-begin}ms`);
}
async function main() {
  log('========== 兴攀农场 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${summary.mode}；账号数：${accounts.length}`);
  try {
    if (!accounts.length) throw new Error('缺少 XPFARM_TOKEN，每行填写一个账号');
    if (accounts.some(x => /[\x00-\x1f\x7f-\uffff]/.test(x))) throw new Error('凭据包含无效请求头字符');
    const rawIds = process.env.XPFARM_TASK_IDS || '';
    if (rawIds && !/^(?:[1-9]|1[0-6])(?:,(?:[1-9]|1[0-6]))*$/.test(rawIds)) throw new Error('任务编号须为逗号分隔的 1–16 整数');
    const config = {ids:[...new Set(rawIds ? rawIds.split(',').map(Number) : [])], fertilizer:limit('XPFARM_FERTILIZER_LIMIT'), water:limit('XPFARM_WATER_LIMIT')};
    for (let i=0;i<accounts.length;i++) await runAccount(accounts[i], i+1, config);
  } catch (error) { summary.configurationError = true; log(`❌ 配置错误：${error.message}`); }
  const code = summary.failed || summary.configurationError ? 1 : 0;
  summary.status = code ? 'failure' : dry ? 'dry-run' : 'success';
  const body = `模式：${summary.mode}；账号总数：${summary.accounts}；成功数：${summary.success}；失败数：${summary.failed}；配置错误：${summary.configurationError ? '是' : '否'}；状态：${summary.status}。`;
  summary.notification = await notify(body);
  summary.durationMs = Date.now()-started;
  summary.finishedAt = new Date().toISOString();
  log('--------------------------------');
  log(body);
  log(`子任务总数：${totals.total}；成功：${totals.success}；已完成：${totals.alreadyComplete}；跳过：${totals.skipped}；失败：${totals.failed}`);
  log(`总耗时：${summary.durationMs}ms；完成时间：${summary.finishedAt}；通知：${summary.notification}；最终状态：${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = code;
}
main().catch(() => { log('❌ 任务内部异常'); process.exitCode=1; });
