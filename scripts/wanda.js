// name: 万达电影签到与能量查询
// cron: 52 1 * * *
/*
 * name: 万达电影
 * cron: 10 0 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * Derived from chavyleung/scripts wanda/wanda.js and wanda/wanda.cookie.js.
 * Original Env helper attribution: chavy (chavyleung); original task storage: senku_wanda_mi_.
 * 保留上游许可 GPL-3.0-only；源码归属原作者，本文件为独立 Node.js 维护版本。
 * 获取方式：登录万达电影，进入签到页面，读取本人请求 MX-API JSON 中的 _mi_。
 * 上游网页入口：https://act-m.wandacinemas.com/2005/17621a8caacc4d190dadd/
 * 上游捕获域名：user-api-prd-mx.wandafilm.com。旧入口可能失效，请以客户端实际请求为准。
 * WANDA_MI 每个非空行一个 _mi_，不使用 & 或 @ 分隔，不读取 box.dat。
 * 兼容环境变量 senku_wanda_mi_。抽奖会消耗能量，默认关闭；答题属于独立活动，默认关闭。
 * WANDA_LOTTERY=1 开启签到抽奖；WANDA_QUESTION=1 开启报名和答题；
 * WANDA_QUESTION_DRAWS=0|1|2 控制答题后抽奖次数（默认 0，须同时开启答题）。
 * 不发布文章、评论或分享，不需要随机文案服务。
 */
'use strict';
// qinglong-notification-policy: begin
(() => {
  const raw = process.env.QINGLONG_NOTIFY;
  if (raw !== undefined && String(raw).trim() !== '' && String(raw).trim().toLowerCase() !== 'auto') return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["8e3a583eb2a0dc24", "scripts/wanda.js", "wanda.js", "wanda"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const crypto = require('node:crypto');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const E = process.env;
const TITLE = '万达电影';
const started = Date.now();
const dry = E.WANDA_DRY_RUN === '1';
const accounts = (E.WANDA_MI || E.senku_wanda_mi_ || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const summary = { task: TITLE, mode: dry ? 'dry-run' : 'live', accounts: accounts.length, success: 0, failed: 0, status: '', results: [] };
function log(s) { console.log(`[${new Date().toLocaleTimeString('zh-CN', { hour12: false })}] ${s}`); }
function fail(s) { throw new Error(s); }
function flag(name) {
  const value = E[name] || '0';
  if (!['0', '1'].includes(value)) fail(`${name} 仅允许 0 或 1`);
  return value === '1';
}
function dateCN() {
  const p = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const get = t => p.find(x => x.type === t).value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}
// 保留上游签名规则：同一次请求的签名和请求头共用一个毫秒时间戳。
function request(mi, endpoint, body, signingBody = body) {
  if (dry) fail('断网预演禁止发起请求');
  const ts = Date.now();
  const key = `Wanda1_3B3AA12B0145E1982F282BEDD8A3305B89A9811280C0B8CC3A6A60D81022E4903${ts}`;
  const header = { ver: 'v1.0.0', sCode: 'Wanda', _mi_: mi, width: 1280, json: true, cCode: '1_3',
    check: crypto.createHash('md5').update(key + endpoint + signingBody).digest('hex'), ts, heigth: 720, appId: '3' };
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (err, data) => { if (done) return; done = true; clearTimeout(timer); err ? reject(err) : resolve(data); };
    const req = https.request({ hostname: 'activity-api-mx.wandafilm.com', path: endpoint, method: 'POST',
      headers: { 'MX-API': JSON.stringify(header), 'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': Buffer.byteLength(body) } }, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => { size += chunk.length; if (size > 1024 * 1024) { finish(new Error('响应超过大小限制')); res.destroy(); req.destroy(); } else chunks.push(chunk); });
      res.on('error', () => finish(new Error('响应中断')));
      res.on('aborted', () => finish(new Error('响应中断')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error('HTTP 状态异常（不跟随重定向）'));
        let data;
        try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return finish(new Error('响应不是有效 JSON')); }
        if (!data || typeof data !== 'object' || ![1, '1'].includes(data.code)) return finish(new Error('业务未确认成功（要求 code=1，请核查会话和活动）'));
        finish(null, data);
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超过 15 秒')); req.destroy(); }, 15000);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(body);
  });
}
function identity(data, mi) {
  // 仅显示官方明确给出的公开身份字段，避免误把会话、手机号或设备值当身份。
  const objects = [data, data?.user, data?.userInfo];
  for (const object of objects) {
    if (!object || typeof object !== 'object') continue;
    for (const field of ['nickname', 'nickName', 'username', 'displayName', 'publicUid', 'uid']) {
      const value = object[field];
      if (typeof value !== 'string' && typeof value !== 'number') continue;
      const text = String(value);
      if (!text || text.includes(mi) || /(?:1[3-9]\d{9}|[\r\n\x00-\x1f])/.test(text)) continue;
      log(`官方身份 ${field}: ${text}`);
    }
  }
}
async function runAccount(mi, index, cfg) {
  const begin = Date.now();
  const stats = { account: index, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let stage = 0;
  async function step(name, action, enabled = true) {
    const time = Date.now(); stats.total++; stage++;
    log(`账号 ${index} · 阶段 ${stage} ${name} 开始`);
    if (!enabled || dry) {
      stats.skipped++;
      log(`⏭️ 账号 ${index} · 阶段 ${stage} ${name}：${dry && enabled ? '断网预演，仅检查执行计划' : '未启用或不满足条件'}；耗时 ${Date.now() - time}ms`);
      return null;
    }
    try {
      const result = await action(); stats.success++;
      log(`✅ 账号 ${index} · 阶段 ${stage} ${name}：已验证成功；耗时 ${Date.now() - time}ms`);
      return result;
    } catch (err) {
      stats.failed++;
      log(`❌ 账号 ${index} · 阶段 ${stage} ${name}：${err.message}；耗时 ${Date.now() - time}ms`);
      return null;
    }
  }
  const api = async (endpoint, body, sign) => {
    const result = await request(mi, endpoint, body, sign); identity(result.data, mi); return result;
  };
  log(`账号 ${index} 开始`);
  const sign = `activityCode=${cfg.signCode}`;
  await step('每日签到', () => api('/activityWholeSign/wholeSignUp.api', `${sign}&signDate=${dateCN()}`));
  const record = await step('查询签到记录和能量', async () => {
    const result = await api('/activityWholeSign/getSignRecord.api', sign);
    const data = result.data;
    if (!data || !['totalMedal', 'remainMedal'].every(k => data[k] !== null && data[k] !== '' && ['number', 'string'].includes(typeof data[k]) && Number.isFinite(Number(data[k])) && Number(data[k]) >= 0)) fail('能量字段缺失或格式异常');
    log(`账号 ${index} 总计能量 ${Number(data.totalMedal)}，剩余能量 ${Number(data.remainMedal)}`);
    return result;
  });
  await step('签到能量抽奖（可能消耗 50 能量）', async () => {
    const result = await api('/activityWholeSign/prize/lottery.api', `${sign}&vcode=&requestId=`);
    if (!result.data?.prize || typeof result.data.prize.prizeName !== 'string') fail('抽奖结果缺少奖品字段，请人工核查，禁止自动重试');
    log(`账号 ${index} 抽奖结果已确认（奖品内容不输出）`);
  }, cfg.lottery && (dry || (record && Number(record.data.remainMedal) >= 50)));
  const q = `activityCode=${cfg.questionCode}`;
  const enrolled = await step('答题活动报名', () => api('/question/qustion/strength.api', q), cfg.question);
  const questions = await step('获取题目及电影答案', async () => {
    const result = await api('/question/question_list.api', q);
    if (typeof result.data?.questionList?.[0]?.movie?.nameCN !== 'string' || !result.data.questionList[0].movie.nameCN.trim()) fail('未找到可用的电影答案');
    return result;
  }, cfg.question && (dry || !!enrolled));
  const answered = await step('提交电影答案', async () => {
    const text = questions.data.questionList[0].movie.nameCN;
    // 原接口签名对答案采用 escape 编码并小写，正文采用 encodeURI；不能改为统一编码。
    const signature = `${q}&answer=%7b%221%22%3a%22${escape(text).toLowerCase()}%22%7d`;
    const result = await api('/question/qustion/answer.api', `${q}&answer=%7B%221%22%3A%22${encodeURI(text)}%22%7D`, signature);
    if (!Number.isInteger(Number(result.data?.remainChance)) || result.data?.remainChance == null || Number(result.data.remainChance) < 0) fail('答题剩余抽奖次数字段异常');
    return result;
  }, cfg.question && (dry || !!questions));
  let drawBlocked = false;
  for (let i = 0; i < cfg.draws; i++) {
    const failuresBefore = stats.failed;
    await step(`答题抽奖 ${i + 1}`, async () => {
      const result = await api('/question/prize/lottery.api', q);
      if (typeof result.data?.prize?.prizeName !== 'string') fail('答题抽奖结果缺少奖品字段，请人工核查');
    }, cfg.question && !drawBlocked && (dry || (answered && Number(answered.data.remainChance) > i)));
    if (stats.failed > failuresBefore) drawBlocked = true;
  }
  stats.elapsedMs = Date.now() - begin;
  stats.status = stats.failed ? 'failure' : dry ? 'dry-run' : 'success';
  log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.elapsedMs}ms`);
  summary.results.push(stats);
  if (stats.failed) summary.failed++; else summary.success++;
}
function selectedNotification() {
  const sw = (E.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(sw)) return false;
  if (['1', 'true', 'yes', 'on'].includes(sw)) return true;
  if (sw !== 'auto') return false;
  // listed-only：未配置选择列表时本任务不在默认通知列表。
  const selectors = (E.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const names = ['8e3a583eb2a0dc24', 'wanda/wanda.js', 'wanda.js', 'candidate.js', path.basename(__filename)];
  return selectors.some(pattern => {
    const re = new RegExp('^' + pattern.split('*').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(n => re.test(n));
  });
}
async function notify() {
  if (!selectedNotification()) return '未选中或已关闭';
  if (dry) { log('通知：断网预演，已生成脱敏通知，不调用外部通知渠道'); return '断网预演'; }
  const files = [E.QINGLONG_NOTIFY_DIR && path.join(E.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = files.find(f => fs.existsSync(f));
  if (!file) return '通知不可用（未找到 sendNotify.js）';
  // 隔离通知模块，屏蔽其日志，防止其输出通知配置或响应；超时不改变业务退出码。
  const body = `状态：${summary.status}；账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；不含凭据与原始响应。`;
  return new Promise(resolve => {
    let settled = false;
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>{process.exitCode=1})', file, TITLE, body], { stdio: 'ignore' });
    const finish = s => { if (settled) return; settled = true; clearTimeout(timer); resolve(s); };
    const timer = setTimeout(() => { child.kill('SIGKILL'); finish('通知超时'); }, 15000);
    child.on('error', () => finish('通知失败'));
    child.on('exit', code => finish(code === 0 ? '已发送' : '通知失败'));
  });
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间 ${new Date(started).toISOString()}；模式 ${summary.mode}；账号数 ${accounts.length}`);
  try {
    if (E.WANDA_DRY_RUN && !['0', '1'].includes(E.WANDA_DRY_RUN)) fail('WANDA_DRY_RUN 仅允许 0 或 1');
    if (!accounts.length) fail('缺少 WANDA_MI，每行填写一个账号的 _mi_');
    const cfg = { signCode: E.WANDA_SIGN_CODE || '134146532', questionCode: E.WANDA_QUESTION_CODE || '15884027', lottery: flag('WANDA_LOTTERY'), question: flag('WANDA_QUESTION'), draws: Number(E.WANDA_QUESTION_DRAWS || '0') };
    if (![cfg.signCode, cfg.questionCode].every(s => /^\d+$/.test(s))) fail('活动编号必须为数字');
    if (!/^[012]$/.test(E.WANDA_QUESTION_DRAWS || '0') || (!cfg.question && cfg.draws)) fail('答题抽奖次数须为 0 至 2，且必须启用答题');
    for (let i = 0; i < accounts.length; i++) {
      if (/[\x00-\x1f\x7f]/.test(accounts[i])) {
        summary.failed++; log(`❌ 账号 ${i + 1} 凭据包含控制字符，跳过该账号`); continue;
      }
      await runAccount(accounts[i], i + 1, cfg);
    }
    summary.status = summary.failed ? (summary.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  } catch (err) {
    summary.status = 'configuration-error'; log(`❌ 配置错误：${err.message}`);
  }
  process.exitCode = ['success', 'dry-run'].includes(summary.status) ? 0 : 1;
  try { summary.notification = await notify(); } catch { summary.notification = '通知失败'; }
  summary.elapsedMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  console.log('----------------------------------------');
  log(`任务统计：账号 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}`);
  const totals = summary.results.reduce((a, r) => { for (const k of ['total', 'success', 'alreadyComplete', 'skipped', 'failed']) a[k] += r[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  summary.steps = totals;
  log(`子任务统计：总计 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`通知状态：${summary.notification}；耗时 ${summary.elapsedMs}ms；完成时间 ${summary.finishedAt}；最终状态 ${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
}
main().catch(() => { process.exitCode = 1; console.error('任务执行异常，已安全终止'); });
