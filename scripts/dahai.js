// name: 大海资源站每日签到
// cron: 0 30 11 * * *
/*
name: 大海资源站每日签到
cron: 0 30 11 * * *
原始来源：unitaryhighs/ql_sign_script，sign/dahai.js
ql_sign_script : https://github.com/unitaryhighs/ql_sign_script
许可证：MIT（保留上游归属；输入源码无其他版权或许可正文）
环境变量 DAHAI_COOKIE_LIST：登录 https://vip.lzzcc.cn 后，在浏览器开发者工具
网络面板查看本站请求的 Cookie 请求头，复制完整值。每个非空行一个账号，
不要用 & 或 @ 分隔账号。Cookie 内的分号和等号原样保留。
DAHAI_DRY_RUN=1：完全断网预演；QINGLONG_NOTIFY=0：关闭青龙通知。
通知目录可通过 QINGLONG_NOTIFY_DIR 指定。需要 Node.js 18 或更新版本。
*/
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["a5b99fb59f74d208", "scripts/dahai.js", "dahai.js", "dahai"];
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
const TITLE = '大海资源站每日签到';
const cookies = (process.env.DAHAI_COOKIE_LIST || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const dryRun = /^(1|true|yes|on)$/i.test(process.env.DAHAI_DRY_RUN || '');
const start = Date.now();
function safe(value) {
  let s = String(value).replace(/<[^>]*>/g, '').replace(/[\r\n\t]/g, ' ');
  for (const cookie of cookies) {
    s = s.split(cookie).join('[凭据已隐藏]');
    for (const part of cookie.split(';')) {
      const at = part.indexOf('=');
      const v = part.slice(at + 1).trim();
      if (at >= 0 && v) s = s.split(v).join('[凭据已隐藏]');
    }
  }
  return s.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]').replace(/(?:cookie|token|session|authorization|device[_-]?id)\s*[:=]\s*\S+/gi, '[敏感字段已隐藏]');
}
function log(s) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${safe(s)}`); }
function checkin(cookie) {
  return new Promise((resolve, reject) => {
    const body = 'action=user_checkin';
    const req = https.request('https://vip.lzzcc.cn/wp-admin/admin-ajax.php', {
      method: 'POST', headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        Cookie: cookie, 'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(body), 'X-Requested-With': 'XMLHttpRequest',
        Origin: 'https://vip.lzzcc.cn', Referer: 'https://vip.lzzcc.cn/'
      }
    }, res => {
      let chunks = [], bytes = 0;
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 65536) { req.destroy(); reject(new Error('响应超过大小限制')); }
        else chunks.push(chunk);
      });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error(`HTTP 状态 ${res.statusCode}，签到未确认`));
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error();
          resolve(data);
        } catch { reject(new Error('响应不是有效的业务对象')); }
      });
    });
    // 整体截止时间包括 DNS、连接及响应，避免慢速响应无限等待。
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', error => reject(new Error(error.message === '请求超时' ? '请求超时' : '网络请求失败')));
    req.end(body);
  });
}
function classify(data) {
  const msg = typeof data.msg === 'string' ? data.msg.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim() : '';
  if (data.error === false) return 'success';
  if (data.error === true && /^(?:您|你)?(?:今天|今日|当天)?(?:已经|已)签到(?:[！!。.,，\s]|$)/.test(msg)) return 'alreadyComplete';
  throw new Error('业务未确认成功（未返回明确成功或已签到状态）');
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dryRun) { log('通知：断网预演，已生成脱敏通知摘要，未调用通知模块'); return '预演'; }
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  for (const file of locations) {
    if (!fs.existsSync(file)) continue;
    try {
      const module = require(file);
      if (typeof module.sendNotify !== 'function') throw new Error();
      let timer;
      try { await Promise.race([Promise.resolve().then(() => module.sendNotify(TITLE, body)), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error()), 10000); })]); }
      finally { clearTimeout(timer); }
      return '已发送';
    } catch { log('⚠️ 通知投递失败，保留业务退出码'); return '失败'; }
  }
  log('⚠️ 未找到青龙 sendNotify.js，保留业务退出码');
  return '不可用';
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(start).toISOString()}；模式：${dryRun ? '断网预演' : '正式'}；账号数：${cookies.length}`);
  const results = [];
  let configurationError = cookies.length === 0;
  if (configurationError) log('❌ 阶段 1 参数检查：DAHAI_COOKIE_LIST 缺失或为空');
  for (let i = 0; i < cookies.length; i++) {
    const t = Date.now();
    const stats = {account: i + 1, total: 1, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
    log(`账号 ${i + 1} 阶段 1 参数检查：已读取完整 Cookie`);
    try {
      if (/[\x00-\x1f\x7f]/.test(cookies[i])) throw new Error('Cookie 包含非法控制字符');
      log(`账号 ${i + 1} 阶段 1 完成，耗时 ${Date.now() - t}ms`);
      const stageStart = Date.now();
      log(`账号 ${i + 1} 阶段 2 每日签到：${dryRun ? '预演 POST action=user_checkin，不发出请求' : '提交签到请求'}`);
      if (dryRun) {
        stats.skipped = 1;
        log(`账号 ${i + 1} ⏭️ DRY_RUN_OK：参数及请求构造验证通过，未验证业务成功`);
      } else {
        const data = await checkin(cookies[i]);
        const status = classify(data);
        for (const key of ['nickname', 'username', 'display_name', 'uid']) {
          if (typeof data[key] === 'string' || typeof data[key] === 'number') log(`账号 ${i + 1} 官方身份 ${key}：${data[key]}`);
        }
        stats[status] = 1;
        // 不打印服务端任意消息，避免响应中回显凭据。
        log(`账号 ${i + 1} ${status === 'success' ? '✅ 签到成功' : '☑️ 今日已签到'}`);
        if (/^\d{1,6}$/.test(String(data.continuous_day))) log(`账号 ${i + 1} 连续签到 ${data.continuous_day} 天`);
      }
      log(`账号 ${i + 1} 阶段 2 完成，耗时 ${Date.now() - stageStart}ms`);
    } catch (error) { stats.failed = 1; log(`账号 ${i + 1} ❌ 阶段失败：${error.message}；耗时 ${Date.now() - t}ms`); }
    stats.durationMs = Date.now() - t;
    results.push(stats);
    log(`账号 ${i + 1} 统计：总任务 1，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs}ms`);
  }
  const failed = results.filter(x => x.failed).length;
  const good = results.length - failed;
  const status = configurationError ? 'configuration-error' : failed ? (good ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
  const exitCode = configurationError || failed ? 1 : 0;
  const body = `${TITLE}：状态 ${status}；账号总数 ${cookies.length}，${dryRun ? '预演通过' : '成功'} ${good}，失败 ${failed}；${configurationError ? '缺少账号配置' : dryRun ? '未发送业务请求' : '签到结果已核验'}`;
  log(`阶段 3 通知：${body}`);
  const notification = await notify(body);
  console.log('----------------------------------------');
  const totals = Object.fromEntries(['total', 'success', 'alreadyComplete', 'skipped', 'failed'].map(k => [k, results.reduce((sum, r) => sum + r[k], 0)]));
  const summary = {task: TITLE, mode: dryRun ? 'dry-run' : 'live', status, accounts: cookies.length, passedAccounts: good, failedAccounts: failed, configurationError, tasks: totals, results, notification, durationMs: Date.now() - start, finishedAt: new Date().toISOString(), exitCode};
  log(`最终统计：账号 ${cookies.length}，通过 ${good}，失败 ${failed}；子任务 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}；总耗时 ${summary.durationMs}ms`);
  log(`结束时间：${summary.finishedAt}；通知：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
}
main().catch(() => { console.error('❌ 任务内部错误'); process.exitCode = 1; });
