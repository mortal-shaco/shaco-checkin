// name: 三国杀社区签到
// cron: 4 * * * *
/*
name: 三国杀社区签到
cron: 4 * * * *
SPDX-License-Identifier: GPL-3.0
来源：NaroisCool/naro-scripts，原文件：三国杀社区.js（三国社区签到）。
保留原项目 GPL-3.0 许可与来源署名；原文件无其他版权声明。

功能盘点：原脚本每小时第 9 分钟以 Cookie 调用社区签到接口并通知。
原脚本无环境参数说明，含固定 Cookie、固定请求体及远程声明下载；这些已移除。
无相关来源、无已维护功能覆盖，保留同一任务和时间安排。
SGS_COOKIE（必填）：浏览器登录 https://club.sanguosha.com 后，打开开发者工具
网络面板，刷新签到页，复制该站已登录请求的 Cookie 请求头完整值（不含 Cookie:）。
每个非空行一个账号，保留 Cookie 内分号及等号；不要使用 & 或 @ 分隔账号。
SGS_DRY_RUN=1：只验证配置和模拟阶段，不执行 HTTP 或通知模块。
QINGLONG_NOTIFY=auto|1|0；QINGLONG_NOTIFY_SCRIPTS 支持目录路径、文件名、
catalogId、通配符，逗号/分号/空白分隔；显式空值关闭全部。
QINGLONG_NOTIFY_DIR：可选，青龙 sendNotify.js 所在目录。
签到使用页面实际表单字段，禁用自由文本提交；不能确定表单时失败闭合。
无发帖、评论、分享、花费或资料修改功能。仅签到产生状态变化。
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
    const identities = ["4c3629330ab7d6a1", "scripts/task_4c362933.js", "task_4c362933.js", "task_4c362933"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { performance } = require('node:perf_hooks');
const TITLE = '三国杀社区签到';
const ID = '4c3629330ab7d6a1';
const ORIGIN = 'https://club.sanguosha.com';
const PAGE = '/plugin.php?id=dsu_paulsign:sign';
const ACTION = PAGE + '&operation=qiandao&infloat=1&inajax=1';
const dry = process.env.SGS_DRY_RUN === '1';
const start = new Date();
const started = performance.now();
const results = [];
const secrets = [];
const clock = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${clock()}] ${text}`);
const seconds = t => Number(((performance.now() - t) / 1000).toFixed(3));
function safeIdentity(value) {
  let s = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const secret of secrets) if (secret) s = s.split(secret).join('[凭据已隐藏]');
  return s.replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, '[手机号已隐藏]');
}
function decode(text) {
  return text.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&amp;/gi, '&').replace(/&quot;/gi, '"').replace(/&#39;|&apos;/gi, "'")
    .replace(/&lt;/gi, '<').replace(/&gt;/gi, '>').replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Math.min(Number(n), 0x10ffff)));
}
function attrs(tag) {
  const a = {};
  const re = /([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g;
  let m;
  while ((m = re.exec(tag))) a[m[1].toLowerCase()] = decode(m[2] ?? m[3] ?? m[4]);
  return a;
}
function plain(html) {
  return decode(html).replace(/<script\b[\s\S]*?<\/script>/gi, '')
    .replace(/<style\b[\s\S]*?<\/style>/gi, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}
function request(urlPath, jar, body) {
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (error, value) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(value);
    };
    const headers = {
      Cookie: [...jar].map(([k, v]) => `${k}=${v}`).join('; '),
      'User-Agent': 'Mozilla/5.0 Qinglong-SGS/1.0',
      Accept: 'text/html,application/xml;q=0.9,*/*;q=0.8',
      Referer: ORIGIN + PAGE,
      'Accept-Encoding': 'identity'
    };
    if (body !== undefined) {
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
      headers['Content-Length'] = Buffer.byteLength(body);
    }
    const req = https.request(ORIGIN + urlPath, { method: body === undefined ? 'GET' : 'POST', headers }, res => {
      if (res.statusCode !== 200) {
        res.resume();
        finish(new Error(`HTTP 状态异常（${res.statusCode}），未跟随重定向`));
        return;
      }
      for (const item of res.headers['set-cookie'] || []) {
        const pair = item.split(';', 1)[0];
        const split = pair.indexOf('=');
        if (split > 0) {
          const value = pair.slice(split + 1);
          if (value) secrets.push(value);
          jar.set(pair.slice(0, split), value);
        }
      }
      const chunks = [];
      let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) {
          finish(new Error('响应超过大小限制'));
          res.destroy();
        } else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应中断')));
      res.on('end', () => {
        try {
          const buffer = Buffer.concat(chunks);
          const type = String(res.headers['content-type'] || '');
          const prefix = buffer.subarray(0, 2048).toString('ascii');
          const charset = /charset\s*=\s*["']?([\w-]+)/i.exec(type + ' ' + prefix)?.[1] || 'utf-8';
          finish(null, new TextDecoder(charset).decode(buffer));
        } catch { finish(new Error('无法解码社区响应')); }
      });
    });
    const timer = setTimeout(() => {
      finish(new Error('请求超时（15 秒）'));
      req.destroy();
    }, 15000);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end(body);
  });
}
const already = text => /(?:您|你)(?:今天|今日)已经签到|(?:今天|今日)(?:已|已经)签到|不能重复签到/.test(text);
function signForm(html) {
  const forms = html.match(/<form\b[^>]*>[\s\S]*?<\/form>/gi) || [];
  const form = forms.find(f => /(?:operation=qiandao|id=["']qiandao|id=["']signform)/i.test(decode(f)));
  if (!form) throw new Error('未找到可核验的签到表单，未提交');
  const fields = new URLSearchParams();
  const inputs = (form.match(/<input\b[^>]*>/gi) || []).map(attrs);
  const hash = inputs.find(a => a.name === 'formhash')?.value;
  if (!hash || !/^[a-zA-Z0-9]+$/.test(hash)) throw new Error('页面缺少有效 formhash，未提交');
  secrets.push(hash);
  // 仅复制签到所需字段，绝不提交页面中未知的附加操作。
  fields.set('formhash', hash);
  const moods = inputs.filter(a => a.name === 'qdxq');
  const mood = moods.find(a => a.value === 'kx')?.value || moods.find(a => a.value)?.value
    || (moods.length && /\bid\s*=\s*["']kx["']/i.test(form) ? 'kx' : null);
  if (!mood) throw new Error('页面缺少可用签到心情字段，未提交');
  fields.set('qdxq', mood);
  // 按页面标签选择“不填写”模式，不能把快速选择文本误认为无文本模式。
  const options = [...form.matchAll(/<select\b([^>]*)>([\s\S]*?)<\/select>/gi)]
    .filter(m => attrs(m[1]).name === 'qdmode')
    .flatMap(m => [...m[2].matchAll(/<option\b([^>]*)>([\s\S]*?)(?:<\/option>|(?=<option)|$)/gi)]
      .map(o => ({ ...attrs(o[1]), label: plain(o[2]) })));
  const noText = options.find(a => a.value && /不想填写|不填写|不想说|无需填写/.test(a.label));
  if (!noText) throw new Error('页面未提供无自由文本签到模式，未提交');
  fields.set('qdmode', noText.value);
  fields.set('todaysay', '');
  return fields.toString();
}
async function stage(account, number, name, action) {
  const t = performance.now();
  log(`账号 ${account.index} · ${number}. ${name} 开始`);
  try {
    const value = await action();
    log(`账号 ${account.index} · ${number}. ${name} ✅（${seconds(t)} 秒）`);
    return value;
  } catch (e) {
    log(`账号 ${account.index} · ${number}. ${name} ❌ ${e.message}（${seconds(t)} 秒）`);
    throw e;
  }
}
async function runAccount(line, index) {
  const t = performance.now();
  const result = { index, total: 1, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  try {
    const jar = await stage(result, 1, '验证账号配置', async () => {
      if (/[\x00-\x1f\x7f]/.test(line) || /^Cookie\s*:/i.test(line)) throw new Error('Cookie 格式错误，请仅填写请求头的值');
      const pairs = line.split(';').map(s => s.trim()).filter(Boolean);
      const jar = new Map();
      for (const pair of pairs) {
        const split = pair.indexOf('=');
        if (split <= 0 || !/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(pair.slice(0, split))) throw new Error('Cookie 字段格式错误');
        const value = pair.slice(split + 1);
        jar.set(pair.slice(0, split), value);
      }
      if (![...jar].some(([k, v]) => /_auth$/.test(k) && v && jar.get(k.slice(0, -5) + '_saltkey'))) throw new Error('Cookie 缺少同一前缀的 auth 或 saltkey');
      return jar;
    });
    if (dry) {
      await stage(result, 2, '预演读取签到页和身份核验', async () => {});
      await stage(result, 3, '预演动态表单签到及结果核验', async () => {});
      result.skipped = 1;
      result.status = 'dry-run';
      log(`账号 ${index} ⏭️ DRY_RUN_OK 配置有效，未执行网络与签到`);
    } else {
      const html = await stage(result, 2, '读取签到页和核验登录身份', async () => {
        const html = await request(PAGE, jar);
        const uid = /\bdiscuz_uid\s*=\s*["']?([1-9]\d*)/.exec(html)?.[1];
        if (!uid && !/member\.php\?[^"'<>]*action=logout/i.test(decode(html))) throw new Error('未核验到登录身份，请重新获取 Cookie');
        if (uid) log(`账号 ${index} · 官方公开 UID：${safeIdentity(uid)}`);
        const username = /<strong[^>]*>\s*<a\b[^>]*href=["'][^"']*(?:space-uid-|mod=space[^"']*uid=)[^"']*["'][^>]*>([\s\S]*?)<\/a>/i.exec(html)?.[1];
        if (username) log(`账号 ${index} · 官方昵称：${safeIdentity(plain(username))}`);
        return html;
      });
      if (already(plain(html))) {
        result.alreadyComplete = 1;
        log(`账号 ${index} ☑️ 今日已签到，未重复提交`);
      } else {
        await stage(result, 3, '提交签到并核验业务结果', async () => {
          const body = signForm(html);
          const response = plain(await request(ACTION, jar, body));
          if (already(response)) result.alreadyComplete = 1;
          else if (/签到成功|恭喜[\s\S]{0,80}签到/.test(response) && !/签到失败|签到未成功|签到不成功/.test(response)) result.success = 1;
          else throw new Error('接口未返回明确签到成功或今日已签到标志，请在社区核对；未自动重试');
        });
      }
      result.status = 'success';
      log(`账号 ${index} ✅ SIGN_IN_OK ${result.alreadyComplete ? '今日已签到' : '签到成功'}`);
    }
  } catch (e) {
    result.failed = 1;
    result.status = 'failure';
    log(`账号 ${index} ❌ ${e.message}`);
  }
  result.seconds = seconds(t);
  log(`账号 ${index} 统计：任务 ${result.total}，成功 ${result.success}，已完成 ${result.alreadyComplete}，跳过 ${result.skipped}，失败 ${result.failed}，耗时 ${result.seconds} 秒`);
  results.push(result);
}
function notificationEnabled() {
  const mode = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(mode)) return false;
  if (['1', 'true', 'yes', 'on'].includes(mode)) return true;
  if (mode !== 'auto') return false;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const names = [ID, '三国杀社区.js', 'candidate.js', path.basename(__filename), 'checkin/三国杀社区.js'];
  return process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(pattern => {
    const re = new RegExp('^' + pattern.split('*').map(p => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(name => re.test(name));
  });
}
async function notify(summary) {
  if (!notificationEnabled()) return '已关闭';
  if (dry) return '预演通知（断网模式未加载通知模块）';
  const files = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = files.find(f => fs.existsSync(f));
  if (!file) { log('⚠️ 未发现青龙 sendNotify.js，保留业务退出码'); return '不可用'; }
  // 隔离通知执行并限制时长，不让通知故障覆盖业务结果。
  const { spawn } = require('node:child_process');
  const body = `状态：${summary.status}\n账号总数：${summary.accounts}，成功：${summary.succeeded}，失败：${summary.failed}\n子任务：成功 ${summary.tasks.success}，已完成 ${summary.tasks.alreadyComplete}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}`;
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>{process.exitCode=1})', file, TITLE, body], { stdio: 'ignore', env: { ...process.env, SGS_COOKIE: '' } });
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('通知超时'); }, 20000);
    child.on('error', () => { clearTimeout(timer); resolve('通知失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '通知失败'); });
  });
}
async function main() {
  const lines = (process.env.SGS_COOKIE || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  for (const line of lines) {
    secrets.push(line);
    for (const pair of line.split(';')) {
      const split = pair.indexOf('=');
      if (split >= 0 && pair.slice(split + 1).trim()) secrets.push(pair.slice(split + 1).trim());
    }
  }
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${start.toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${lines.length}`);
  if (!lines.length) log('❌ 配置错误：缺少 SGS_COOKIE，请每行填写一个已登录账号的完整 Cookie');
  for (let i = 0; i < lines.length; i++) await runAccount(lines[i], i + 1);
  const failed = results.filter(r => r.failed).length;
  const succeeded = results.filter(r => r.status === 'success').length;
  const tasks = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  for (const r of results) for (const k of Object.keys(tasks)) tasks[k] += r[k];
  const status = !lines.length ? 'configuration-error' : failed ? (failed < lines.length ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const summary = { status, mode: dry ? 'dry-run' : 'live', accounts: lines.length, succeeded, failed, tasks, results };
  const notification = await notify(summary);
  summary.notification = notification;
  summary.seconds = seconds(started);
  summary.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`最终状态：${status}；账号总数 ${lines.length}，成功 ${succeeded}，预演 ${results.filter(r => r.status === 'dry-run').length}，失败 ${failed}`);
  log(`子任务统计：总数 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`完成时间：${summary.finishedAt}；总耗时 ${summary.seconds} 秒；通知：${notification}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = !lines.length || failed ? 1 : 0;
}
main().catch(() => {
  // 不记录异常对象，以免第三方错误包含请求头或凭据。
  log('❌ 任务执行出现内部错误');
  process.exitCode = 1;
});
