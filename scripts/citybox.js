// name: 魔盒 CityBox 签到
// cron: 15 0 * * *
/*
 * name: 魔盒 CityBox 签到
 * cron: 10 0 * * *
 * SPDX-License-Identifier: GPL-3.0-only
 * 来源：chavyleung/scripts，citybox/citybox.js、citybox/citybox.cookie.js。
 * 保留上游作者归属，维护版本遵循 GPL-3.0-only。
 *
 * CITYBOX_ACCOUNTS：每个非空行一个 JSON 对象，格式 {"headers":{请求头字段:值}}。
 * 打开 CityBox 小程序签到页，使用自己授权的抓包工具取得
 * https://api.icitybox.cn/api/user/get_user_info 的请求头；保留认证和签名字段。
 * 可把旧 BoxJS 的 boxapp_citybox_har 值作为一行，或用同名环境变量兼容输入。
 * 不再读写 box.dat，不需要抓包脚本或其他仓库。不要公开请求头。
 * CITYBOX_DRAW=1 显式开启消耗活动机会的抽奖；只在原活动截止日 2026-09-20 前执行。
 * 不延长活动期限；未知剩余次数时不抽奖。每日签到默认执行。
 * CITYBOX_DRY_RUN=1 完全断网预演（含通知），不验证凭据或业务成功。
 * QINGLONG_NOTIFY=auto 默认仅通知 QINGLONG_NOTIFY_SCRIPTS 显式选中的脚本；
 * 设为 1 强制启用、0 关闭。选择器支持目录路径、文件名、catalogId 和文件名通配符。
 * QINGLONG_NOTIFY_DIR 可指定青龙 sendNotify.js 所在目录；失败不改变业务退出码。
 * 仅使用 Node.js 内置模块，建议 Node.js 18 或以上。
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
    const identities = ["08faf258eda0d905", "scripts/citybox.js", "citybox.js", "citybox"];
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
const { execFile } = require('node:child_process');
const TITLE = '魔盒 CityBox 签到';
const ID = '08faf258eda0d905';
const START = Date.now();
const DRY = process.env.CITYBOX_DRY_RUN === '1';
const END = '2026-09-20';
const log = text => console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${text}`);
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const secrets = [];
function safe(value) {
  let text = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const secret of secrets) if (secret.length > 2) text = text.split(secret).join('[凭据已隐藏]');
  return text.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function parseAccount(line) {
  let data;
  try { data = JSON.parse(line); } catch { throw new Error('账号必须是单行 JSON 请求头对象'); }
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('账号结构错误');
  const raw = data.headers;
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('账号缺少 headers 对象');
  const headers = {};
  // 不转发传输层字段、代理头或抓包工具头，不改变其余认证/签名字段。
  const removed = /^(content-length|host|connection|transfer-encoding|accept-encoding|proxy-.*|:.*|x-surge-.*)$/i;
  for (const [key, value] of Object.entries(raw)) {
    if (typeof value !== 'string') throw new Error('请求头的值必须为字符串');
    if (value) secrets.push(value);
    if (removed.test(key)) continue;
    if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(key) || /[\r\n\x00]/.test(value)) throw new Error('请求头格式不合法');
    headers[key.toLowerCase()] = value;
  }
  if (!Object.values(headers).some(Boolean)) throw new Error('账号请求头不能为空');
  return headers;
}
function request(endpoint, method, headers) {
  if (DRY) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (error, value) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(value);
    };
    const req = https.request({hostname:'api.icitybox.cn', path:`/api${endpoint}`, method, headers}, res => {
      const chunks = []; let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 262144) { finish(new Error('响应超过大小限制')); res.destroy(); req.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应中断')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error(`HTTP 状态异常 ${res.statusCode}`));
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error();
          finish(null, data);
        } catch { finish(new Error('响应不是有效业务对象')); }
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超时')); req.destroy(); }, 15000);
    req.on('error', () => finish(new Error('网络请求失败')));
    // 不重定向、不自动重试状态改变请求，防止跨域泄露凭据和重复消耗。
    req.end();
  });
}
function identity(data) {
  for (const obj of [data, data.user, data.data, data.data?.user]) {
    if (!obj || typeof obj !== 'object') continue;
    for (const field of ['nickname','username','display_name','uid']) {
      if (typeof obj[field] === 'string' || typeof obj[field] === 'number') {
        log(`官方账号身份：${safe(obj[field])}`);
        return;
      }
    }
  }
}
function notifySelected() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0','false','no','off'].includes(mode)) return false;
  if (['1','true','yes','on'].includes(mode)) return true;
  const selectors = (process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const names = [ID, 'citybox.js', 'citybox/citybox.js', 'candidate.js', path.basename(__filename)];
  return selectors.some(pattern => {
    const regex = new RegExp('^' + pattern.split('*').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(name => regex.test(name));
  });
}
async function notify(body) {
  if (!notifySelected()) return '未选中或已关闭';
  if (DRY) return '预演已模拟通知（未联网）';
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'];
  const file = locations.find(p => p && fs.existsSync(p));
  if (!file) return '通知模块不可用，保留业务退出码';
  return new Promise(resolve => {
    execFile(process.execPath, ['-e',
      'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0)).catch(()=>process.exit(1))',
      file, TITLE, body], {timeout:15000, maxBuffer:4096}, error => resolve(error ? '通知失败，保留业务退出码' : '通知已发送'));
  });
}
async function run() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(START).toISOString()}；模式：${DRY ? '断网预演' : '正式执行'}`);
  const lines = (process.env.CITYBOX_ACCOUNTS ?? process.env.boxapp_citybox_har ?? '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  log(`账号总数：${lines.length}`);
  const accounts = []; let configError = false;
  const drawOption = process.env.CITYBOX_DRAW || '0';
  if (!['0','1'].includes(drawOption)) { configError = true; log('❌ 配置错误：CITYBOX_DRAW 只能为 0 或 1'); }
  if (!lines.length) { configError = true; log('❌ 配置错误：请设置 CITYBOX_ACCOUNTS，每行一个账号 JSON'); }
  const globalConfigError = configError;
  for (let i = 0; i < lines.length; i++) {
    const started = Date.now();
    const stats = {account:i+1,total:0,success:0,alreadyComplete:0,skipped:0,failed:0,durationMs:0};
    accounts.push(stats);
    async function stage(number, name, action) {
      const at = Date.now(); stats.total++;
      log(`账号 ${i+1} [${number}] ${name} 开始`);
      try {
        const result = await action();
        stats[result || 'success']++;
        log(`账号 ${i+1} [${number}] ${name} ${result === 'skipped' ? '⏭️ 跳过' : result === 'alreadyComplete' ? '☑️ 已完成' : '✅ 成功'}；耗时 ${Date.now()-at}ms`);
        return true;
      } catch (error) {
        stats.failed++;
        log(`账号 ${i+1} [${number}] ${name} ❌ ${safe(error.message)}；耗时 ${Date.now()-at}ms`);
        return false;
      }
    }
    let headers;
    const valid = await stage(1, '参数检查', () => { headers = parseAccount(lines[i]); if (globalConfigError) throw new Error('全局配置错误'); });
    if (!valid) configError = true;
    if (valid) {
      const signed = await stage(2, '每日签到', async () => {
        if (DRY) { log('预演：将 GET /api/user/up_sign，不发送请求'); return 'skipped'; }
        const data = await request('/user/up_sign', 'GET', headers);
        identity(data);
        if (data.status !== false && Number.isInteger(Number(data.signnum)) && Number(data.signnum) > 0) {
          log(`签到成功，累计 ${Number(data.signnum)} 天`); return;
        }
        if (/^(今日已签到|今天已签到|您今天已签到|已经签到|已签到)[！!。.]?$/.test(data.message || '')) return 'alreadyComplete';
        throw new Error('签到未通过业务校验（未返回有效 signnum 或明确的已签到结果），请更新抓包凭据');
      });
      await stage(3, '活动查询及抽奖', async () => {
        const today = new Date().toLocaleDateString('sv-SE', {timeZone:'Asia/Shanghai'});
        if (drawOption !== '1' || today > END || !signed) {
          log(`活动跳过：${!signed ? '签到失败' : today > END ? '原活动已于 2026-09-20 结束' : '未显式开启 CITYBOX_DRAW'}`);
          return 'skipped';
        }
        if (DRY) { log('预演：将查询活动剩余次数并按限流退避抽奖，不发送请求'); return 'skipped'; }
        await wait(800);
        const active = await request('/active/trigger_active_list', 'GET', headers);
        identity(active);
        const total = typeof active.gift_num === 'number' ? active.gift_num :
          typeof active.gift_num === 'string' && /^\d+$/.test(active.gift_num) ? Number(active.gift_num) : NaN;
        if (active.status === false || !Number.isSafeInteger(total) || total < 0) throw new Error('活动剩余次数无法确认，已停止抽奖');
        if (!total) { log('活动剩余次数为 0'); return 'alreadyComplete'; }
        for (let drawn = 0; drawn < total; drawn++) {
          let success = false;
          for (let retry = 0; retry <= 4; retry++) {
            await wait(retry ? Math.min(800 * 2 ** (retry-1), 6400) : 800);
            const data = await request('/active/trigger_draw', 'POST', headers);
            identity(data);
            if (data.status === false) {
              if (/重复提交|频繁|稍后|请稍候|超时/.test(data.message || '') && retry < 4) { log(`抽奖限流，第 ${retry+1}/4 次退避`); continue; }
              throw new Error('抽奖被业务接口拒绝或限流重试耗尽');
            }
            // 上游把任何非 false 都当成功；这里必须有明确结果字段。
            if (data.status !== true || ![true,false,0,1].includes(data.is_win)) throw new Error('抽奖响应缺少明确成功状态或中奖结果，停止重试避免重复消耗');
            log(`抽奖 ${drawn+1}/${total}：${data.is_win ? '中奖' : '未中奖'}`);
            const detail = data.reward?.detail;
            const prize = detail?.open_door_remarks || detail?.card_name || data.reward?.name;
            if (typeof prize === 'string') log(`奖品：${safe(prize)}`);
            success = true; break;
          }
          if (!success) throw new Error('抽奖未确认完成');
        }
      });
    }
    stats.durationMs = Date.now()-started;
    log(`账号 ${i+1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${stats.durationMs}ms`);
  }
  const failed = accounts.filter(a => a.failed).length;
  const ok = accounts.length - failed;
  const exitCode = configError || failed ? 1 : 0;
  const status = configError ? 'configuration-error' : failed ? (ok ? 'partial-failure' : 'failure') : DRY ? 'dry-run' : 'success';
  const body = `状态：${status}；账号总数 ${lines.length}，成功 ${ok}，失败 ${failed}。${DRY ? '断网预演，不代表真实业务成功。' : ''}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '通知失败，保留业务退出码'; }
  log('----------------------------------------');
  log(body);
  const totals = accounts.reduce((sum,a) => { for (const k of ['total','success','alreadyComplete','skipped','failed']) sum[k] += a[k]; return sum; }, {total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log(`子任务统计：总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`通知状态：${notification}；总耗时 ${Date.now()-START}ms；完成时间：${new Date().toISOString()}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({task:TITLE,mode:DRY?'dry-run':'live',status,accountCount:lines.length,success:ok,failed,accounts,totals,notification,durationMs:Date.now()-START,exitCode}));
  process.exitCode = exitCode;
}
run().catch(async () => {
  log('❌ 任务内部异常（详情已隐藏）');
  const count = (process.env.CITYBOX_ACCOUNTS ?? process.env.boxapp_citybox_har ?? '').split(/\r?\n/).filter(s => s.trim()).length;
  let notification = '通知失败，保留业务退出码';
  try { notification = await notify(`状态：failure；账号总数 ${count}，成功 0，失败 ${count}；任务内部异常，未确认完成。`); } catch {}
  log('----------------------------------------');
  log(`任务统计：账号总数 ${count}，成功 0，失败 ${count}；通知状态：${notification}`);
  log(`总耗时 ${Date.now()-START}ms；完成时间：${new Date().toISOString()}；最终状态：failure`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:TITLE,status:'failure',accountCount:count,success:0,failed:count,notification,exitCode:1}));
  process.exitCode = 1;
});
