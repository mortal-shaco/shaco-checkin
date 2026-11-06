// name: 快看漫画签到
// cron: 19 10 * * *
/*
 * name: 快看漫画签到
 * cron: 0 9 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 上游：NobyDa/Script — KuaiKan-DailyBonus/KKMH.js，更新时间 2022.06.18
 * 原作者电报频道：@NobyDa；问题反馈：@NobyDa_bot
 * 原兼容层署名：Compatible code from https://github.com/chavyleung/scripts/blob/master/Env.min.js
 * 本维护版使用 Node.js 内置 HTTPS 实现请求，不再使用上述兼容层。
 * 本脚本依 GPL-3.0-only 分发：https://www.gnu.org/licenses/gpl-3.0.html
 *
 * 功能盘点：每日签到；今日可领时领取连签礼包；显示积分、KK 币与礼包奖励；可选 Bark 通知。
 * 原移动代理抓取 Cookie 功能改为配置说明，不在定时任务中安装抓包规则或写入明文凭据文件。
 * 当前任务 maintainedFeatureCoverage 为空，无相关脚本或维护目标，不存在重复覆盖。
 * 保持原 GET 地址、请求头、业务码 200 与每日 9:00 计划；未联网确认服务现状。
 *
 * 参数获取：在自己设备上抓取快看漫画 App（中国区）“我的”页面请求，
 * 查找 api.kkmh.com 下的 passport/user 请求，复制请求头 Cookie 的完整值。
 * 在青龙环境变量 KKMH_COOKIE 中填写，每个非空行一个账号，包含 session= 字段。
 * 不要按 &、@ 或分号分割账号；分号属于 Cookie，值内的等号按原样保留。
 * 抓取完成后关闭抓包并移除 MITM 主机名。不要分享 Cookie 或写入脚本。
 * KKMH_DRY_RUN=1：完全离线，验证配置并模拟签到、礼包与通知，不代表实际业务成功。
 * KKMH_GIFT_PACK=0 可关闭礼包领取，默认 1，保持原签到后自动领取行为。
 * BARK_KEY：可选 Bark 推送密钥，留空不发送；仅发送脱敏统计，无原始响应。
 * QINGLONG_NOTIFY=auto|1|0：青龙通知开关，默认 auto，对本脚本默认启用。
 * QINGLONG_NOTIFY_SCRIPTS：设置后替换默认选择，逗号、分号或空白分隔，空值禁用全部。
 * 支持目录、文件名、文件名通配符、catalogId 或 *；QINGLONG_NOTIFY_DIR 可指定通知目录。
 * 通知缺失或发送失败不改变业务退出码；离线预演仅模拟通知，不加载外部通知代码。
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
    const identities = ["6240bc42b411cdf6", "scripts/kkmh.js", "kkmh.js", "kkmh"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const NAME = '快看漫画签到';
const CATALOG = '6240bc42b411cdf6';
const ROOT = 'https://h5.kuaikanmanhua.com';
const CHECKIN = '/v2/checkin/task_center/checkin';
const GIFT = '/v1/checkin/api/check/open_gift_bag';
const started = Date.now();
const dryRun = process.env.KKMH_DRY_RUN === '1';
const lines = (process.env.KKMH_COOKIE || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const secrets = lines.flatMap(x => [x, ...x.split(';').map(p => p.slice(p.indexOf('=') + 1).trim())])
  .concat(process.env.BARK_KEY || '').filter(x => x.length >= 4);
const accounts = [];
let stageNumber = 0;

function clean(value) {
  let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const secret of secrets) s = s.split(secret).join('[已隐藏]');
  return s.replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, '[手机号已隐藏]');
}
function log(text) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${clean(text)}`); }
function fail(message) { return new Error(message); }
function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function numeric(value) { return (typeof value === 'number' || typeof value === 'string') && String(value).trim() !== '' && Number.isFinite(Number(value)); }
function amount(value) { return numeric(value) ? String(value) : '未返回'; }
function validateCookie(cookie) {
  if (/[\x00-\x1f\x7f]/.test(cookie) || !/(?:^|;)\s*session=[^;\s]+/.test(cookie)) {
    throw fail('配置错误：Cookie 需包含非空 session 字段且不得包含控制字符');
  }
}
function business(json, needsHome) {
  if (!object(json) || ![200, '200'].includes(json.code)) {
    throw fail(json && [401, '401'].includes(json.code) ? 'Cookie 已失效（业务码 401）' : '接口未确认业务成功');
  }
  if (!object(json.data) || (needsHome && !object(json.data.check_in_home_info))) {
    throw fail('响应结构变化：缺少业务数据');
  }
  return json.data;
}

// 固定目标，不自动跳转，不自动重试有状态请求；总时限覆盖 DNS、连接和响应读取。
function request(url, headers, body) {
  if (dryRun) return Promise.reject(fail('离线保护：禁止网络请求'));
  return new Promise((resolve, reject) => {
    let done = false;
    let req;
    const finish = (error, result) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(result);
    };
    const timer = setTimeout(() => { finish(fail('请求超时')); if (req) req.destroy(); }, 15000);
    try {
      req = https.request(url, { method: body ? 'POST' : 'GET', headers }, res => {
        const chunks = [];
        let size = 0;
        res.on('error', () => finish(fail('响应读取失败')));
        res.on('aborted', () => finish(fail('响应中断')));
        res.on('data', chunk => {
          size += chunk.length;
          if (size > 262144) { finish(fail('响应超过大小限制')); res.destroy(); req.destroy(); }
          else chunks.push(chunk);
        });
        res.on('end', () => {
          if (res.statusCode < 200 || res.statusCode >= 300) return finish(fail('HTTP 状态异常'));
          try { finish(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
          catch { finish(fail('响应不是有效 JSON')); }
        });
      });
      req.on('error', () => finish(fail('网络连接失败')));
      req.end(body);
    } catch { finish(fail('请求配置无效')); if (req) req.destroy(); }
  });
}
function api(endpoint, cookie) {
  return request(ROOT + endpoint, {
    Cookie: cookie,
    'User-Agent': 'Kuaikan/5.75.0/575000(iPhone;Scale/3.00) (iPhone; CPU)',
    'X-Device': '0'
  });
}
function showIdentity(data, index) {
  // 仅使用官方返回的公开身份；不从 Cookie 的 uid 或 session 推断身份。
  for (const user of [data.user, data.user_info, data.userInfo, data, data.check_in_home_info]) {
    if (!object(user)) continue;
    for (const key of ['nickname', 'username', 'display_name', 'displayName', 'public_uid', 'uid']) {
      if ((typeof user[key] === 'string' || typeof user[key] === 'number') && String(user[key]).trim()) {
        log(`账号 ${index} 官方身份：${user[key]}`);
        return;
      }
    }
  }
}
async function stage(account, title, action) {
  const now = Date.now();
  const number = ++stageNumber;
  log(`账号 ${account.index} · 阶段 ${number} ${title} 开始`);
  account.total++;
  try {
    const result = await action();
    if (result === 'skipped') account.skipped++; else account.success++;
    log(`账号 ${account.index} · 阶段 ${number} ${result === 'skipped' ? '⏭️ 跳过' : dryRun ? '✅ 模拟通过' : '✅ 成功'} · ${Date.now() - now} 毫秒`);
    return result;
  } catch (error) {
    account.failed++;
    log(`账号 ${account.index} · 阶段 ${number} ❌ ${error.message} · ${Date.now() - now} 毫秒`);
    throw error;
  }
}
async function runAccount(cookie, index, giftEnabled) {
  const now = Date.now();
  const a = { index, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, status: 'failure' };
  accounts.push(a);
  try {
    await stage(a, '参数检查', async () => validateCookie(cookie));
    const data = await stage(a, '每日签到', async () => {
      const json = dryRun ? { code: 200, data: { check_in_home_info: {
        check_in_title: '今日可领', user_score: 0, user_kkb: 0
      } } } : await api(CHECKIN, cookie);
      const result = business(json, true);
      if (typeof result.check_in_home_info.check_in_title !== 'string') throw fail('响应结构变化：缺少签到标题');
      showIdentity(result, index);
      for (const key of ['pop_title', 'check_in_bubble_text', 'check_in_title']) {
        if (typeof result.check_in_home_info[key] === 'string') log(`账号 ${index} 签到提示：${result.check_in_home_info[key]}`);
      }
      log(`账号 ${index} ${dryRun ? '预演余额' : '签到确认，余额'}：${amount(result.check_in_home_info.user_score)}积分，${amount(result.check_in_home_info.user_kkb)} KK币`);
      return result;
    });
    await stage(a, '连签礼包', async () => {
      if (!giftEnabled || !/今(日|天)可领/.test(data.check_in_home_info.check_in_title)) {
        log(`账号 ${index} ${giftEnabled ? '今日没有可领取礼包' : '已显式关闭礼包领取'}`);
        return 'skipped';
      }
      const result = business(dryRun ? { code: 200, data: { score: 0, kkb: 0, giftBagScore: 0, giftBagKkb: 0 } } : await api(GIFT, cookie), false);
      if (!numeric(result.score) || !numeric(result.kkb)) throw fail('响应结构变化：礼包未返回有效余额');
      const kkb = Number(result.kkb) + (numeric(result.giftBagKkb) ? Number(result.giftBagKkb) : 0);
      log(`账号 ${index} ${dryRun ? '礼包预演' : '领取连签礼包成功'}：现有${amount(result.score)}积分，${kkb} KK币；奖励积分 ${amount(result.giftBagScore)}，KK币 ${amount(result.giftBagKkb)}`);
      if (result.giftBagSupplement) log(`账号 ${index} 奖励：补签胶囊`);
      if (result.giftBagCardCoupon) log(`账号 ${index} 奖励：卡券${object(result.cardCoupon) && typeof result.cardCoupon.title === 'string' ? ' ' + result.cardCoupon.title : ''}`);
      if (result.giftBagYouzanCoupon) log(`账号 ${index} 奖励：有赞优惠券${object(result.youzanCoupon) && typeof result.youzanCoupon.title === 'string' ? ' ' + result.youzanCoupon.title : ''}`);
    });
    a.status = dryRun ? 'dry-run' : 'success';
  } catch { /* 单个账号失败后继续处理后续账号；阶段已记录安全错误。 */ }
  a.durationMs = Date.now() - now;
  log(`账号 ${index} 统计：总任务 ${a.total}，成功 ${a.success}，已完成 ${a.alreadyComplete}，跳过 ${a.skipped}，失败 ${a.failed}，耗时 ${a.durationMs} 毫秒，状态 ${a.status}`);
}

function notificationEnabled() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(mode)) return false;
  if (['1', 'true', 'yes', 'on'].includes(mode)) return true;
  if (!Object.hasOwn(process.env, 'QINGLONG_NOTIFY_SCRIPTS')) return true;
  const full = __filename.replace(/\\/g, '/');
  const targets = [CATALOG, 'KKMH.js', path.basename(__filename), full, full.split('/scripts/').pop()];
  return process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(selector => {
    const escaped = selector.split('*').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    const pattern = new RegExp(`^${escaped}$`);
    return targets.some(t => pattern.test(t));
  });
}
async function notify(body) {
  if (!notificationEnabled()) { log('青龙通知：已关闭'); return 'disabled'; }
  if (dryRun) { log('青龙通知：已离线模拟脱敏汇总，未调用外部模块'); return 'dry-run'; }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const file = dirs.map(d => path.join(d, 'sendNotify.js')).find(f => fs.existsSync(f));
  if (!file) { log('⚠️ 青龙通知：未找到 sendNotify.js，保留业务退出码'); return 'unavailable'; }
  // 隔离通知模块，禁止把模块输出（可能含推送密钥）写入任务日志；超时不影响业务结果。
  const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))';
  return new Promise(resolve => {
    let child;
    let settled = false;
    const finish = ok => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      log(ok ? '青龙通知：已发送' : '⚠️ 青龙通知：发送失败或超时，保留业务退出码');
      resolve(ok ? 'sent' : 'failed');
    };
    const timer = setTimeout(() => { if (child) child.kill('SIGKILL'); finish(false); }, 15000);
    try {
      child = spawn(process.execPath, ['-e', code, file, NAME, body], { stdio: 'ignore' });
      child.on('error', () => finish(false));
      child.on('exit', exitCode => finish(exitCode === 0));
    } catch { finish(false); }
  });
}
async function main() {
  log(`========== ${NAME} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dryRun ? '完全离线预演' : '正式运行'}；账号数：${lines.length}`);
  const giftSetting = process.env.KKMH_GIFT_PACK || '1';
  let configurationError = false;
  if (!lines.length || !['0', '1'].includes(giftSetting) || !['auto', '1', 'true', 'yes', 'on', '0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || 'auto').toLowerCase()) || !['0', '1'].includes(process.env.KKMH_DRY_RUN || '0')) {
    log('❌ 配置错误：必须设置 KKMH_COOKIE；预演和礼包开关仅允许 0 或 1，通知开关需使用文档列出的值');
    configurationError = true;
  } else {
    for (const [i, cookie] of lines.entries()) await runAccount(cookie, i + 1, giftSetting === '1');
  }
  const failed = configurationError ? lines.length : accounts.filter(a => a.status === 'failure').length;
  const success = accounts.length - accounts.filter(a => a.status === 'failure').length;
  const exitCode = configurationError || failed ? 1 : 0;
  const status = configurationError ? 'configuration-error' : failed ? success ? 'partial-failure' : 'failure' : dryRun ? 'dry-run' : 'success';
  const body = `${NAME}\n模式：${dryRun ? '离线预演（非业务成功）' : '正式运行'}\n账号总数 ${lines.length}，成功 ${success}，失败 ${failed}，状态 ${status}`;
  const notification = await notify(body);
  let bark = 'disabled';
  if (process.env.BARK_KEY) {
    if (dryRun) { bark = 'dry-run'; log('Bark 通知：已离线模拟'); }
    else {
      try {
        const result = await request('https://api.day.app/push', { 'Content-Type': 'application/json' }, JSON.stringify({ title: NAME, body, device_key: process.env.BARK_KEY, ext_params: { group: NAME } }));
        if (!result || ![200, '200'].includes(result.code)) throw fail('Bark 未确认成功');
        bark = 'sent'; log('Bark 通知：已发送');
      } catch { bark = 'failed'; log('⚠️ Bark 通知失败，保留业务退出码'); }
    }
  }
  const tasks = accounts.reduce((s, a) => {
    for (const k of ['total', 'success', 'alreadyComplete', 'skipped', 'failed']) s[k] += a[k];
    return s;
  }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  log('----------------------------------------');
  log(`任务统计：账号总数 ${lines.length}，成功 ${success}，失败 ${failed}；子任务总数 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now() - started} 毫秒；通知 ${notification}；Bark ${bark}；最终状态 ${status}`);
  if (!exitCode) log(dryRun ? 'DRY_RUN_OK：仅确认离线预演通过' : 'KKMH_SUCCESS：全部账号签到与启用的礼包任务已验证成功');
  console.log('TASK_SUMMARY=' + JSON.stringify({ schemaVersion: 1, name: NAME, mode: dryRun ? 'dry-run' : 'live', status, verified: !dryRun && exitCode === 0, accountCount: lines.length, success, failed, tasks, accounts, notification, bark, durationMs: Date.now() - started, exitCode }));
  process.exitCode = exitCode;
}
main().catch(async () => {
  log('❌ 任务内部错误，未确认业务成功');
  let notification = 'failed';
  try { notification = await notify(`${NAME}：账号总数 ${lines.length}，成功 0，失败 ${lines.length}，任务内部错误`); } catch { log('⚠️ 青龙通知不可用'); }
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now() - started} 毫秒；最终状态 failure`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ schemaVersion: 1, name: NAME, mode: dryRun ? 'dry-run' : 'live', status: 'failure', verified: false, accountCount: lines.length, success: 0, failed: lines.length, accounts, notification, durationMs: Date.now() - started, exitCode: 1 }));
  process.exitCode = 1;
});
