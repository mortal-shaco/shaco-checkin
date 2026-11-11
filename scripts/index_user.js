// name: 微博超话自动签到
// cron: 5 11 * * *
// ==UserScript==
// @name       微博超话自动签到
// @description  用户登录后进入微博主页，获取超级话题并自动签到
// @homepageURL  https://github.com/Deuscx/WB_SIGN_EXT
// @supportURL   https://github.com/Deuscx/WB_SIGN_EXT/issues
// @grant       none
// @version     2.0.3
// @author       deus
// @match        https://weibo.com/*
// @match        https://www.weibo.com/*
// @require     https://cdn.jsdelivr.net/npm/@violentmonkey/dom@1
// @require     https://cdn.jsdelivr.net/npm/@violentmonkey/ui@0.4
// @require    https://cdn.jsdelivr.net/npm/axios@0.21.0/dist/axios.min.js
// ==/UserScript==
// 上述元数据保留上游署名；本维护版运行于 Node.js，不加载浏览器依赖。
// 上游及本维护版采用 MIT 许可。
/*
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
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
    const identities = ["3e7e9390a09ade1f", "scripts/index_user.js", "index_user.js", "index_user"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
/*
功能清单：分页获取关注超话、串行签到、识别重复签到、单项失败继续、每日定时执行。
原脚本仅在打开网页时执行，无固定 cron；这里建议北京时间每天 08:15，青龙时区应设为亚洲/上海。
账号：登录 https://weibo.com/，开发者工具的网络面板选择本人已登录的同站请求，
复制请求头 Cookie 的值到 WB_COOKIE，每行一个账号；不要复制整段请求头，不使用 & 或 @ 分账号。
WB_AUTO_SIGN=0 可关闭签到并只读取列表；默认开启，唯一业务写操作为已关注超话签到。
WB_INTERVAL_MS 控制签到间隔，默认并至少 500 毫秒。WB_DRY_RUN=1 完全断网预演。
气泡提示改为终端日志和可选青龙通知；不读取或写入浏览器存储，不使用私有仓库或本地应用。
成功仅根据原接口 ok=1、签到 code=100000 或已签到 code=382004 判定；不输出服务器原始消息。
通知：QINGLONG_NOTIFY=1 开启，=0 关闭；auto 仅通知 QINGLONG_NOTIFY_SCRIPTS 匹配的脚本。
选择器支持目录相对路径、文件名、文件名通配符、catalogId、*，以逗号/分号/空白分隔。
可用 QINGLONG_NOTIFY_DIR 指定青龙 sendNotify.js 目录；dry-run 仅模拟通知，防止网络副作用。
*/
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const TITLE = '微博超话自动签到';
const CATALOG = '3e7e9390a09ade1f';
const enabled = v => /^(1|true|yes|on)$/i.test(v || '');
const disabled = v => /^(0|false|no|off)$/i.test(v || '');
const dry = enabled(process.env.WB_DRY_RUN);
const started = Date.now();
const accounts = (process.env.WB_COOKIE || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const log = s => console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${s}`);
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
// 唯一 HTTP 实现：固定同站 HTTPS、禁止重定向、绝对超时、限制响应体、不输出凭据或响应。
function request(url, cookie) {
  if (dry) throw new Error('预演禁止网络请求');
  if (url.origin !== 'https://weibo.com') throw new Error('拒绝非微博地址');
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer;
    const finish = (err, data) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      err ? reject(err) : resolve(data);
    };
    const req = https.request(url, {method:'GET', headers: {
      Cookie:cookie, Referer:'https://weibo.com/', Accept:'application/json',
      'User-Agent':'Mozilla/5.0 QinglongWeiboCheckin/1.0'
    }}, res => {
      if (res.statusCode !== 200) {
        finish(new Error(`HTTP 状态异常（${res.statusCode}）`));
        res.destroy(); return;
      }
      const chunks = [];
      let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 2 * 1024 * 1024) {
          finish(new Error('响应超过大小限制')); res.destroy(); req.destroy();
        } else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应传输失败')));
      res.on('aborted', () => finish(new Error('响应传输中断')));
      res.on('end', () => {
        try { finish(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch { finish(new Error('响应不是有效 JSON，可能登录失效')); }
      });
    });
    timer = setTimeout(() => {finish(new Error('请求超时')); req.destroy();}, 5000);
    req.on('error', () => finish(new Error('网络请求失败')));
    req.end();
  });
}
function cookieValid(cookie) {
  return !/[\x00-\x1f\x7f]/.test(cookie) && cookie.split(';').every(p => /^\s*[^=;\s]+=[^;]*$/.test(p));
}
function printIdentity(data, cookie) {
  const user = data && (data.user || (data.data && data.data.user));
  const value = user && (user.screen_name || user.nickname || user.username || user.display_name);
  if (typeof value !== 'string' || !value.trim()) return;
  // 昵称按官方值显示，但保护异常响应中的凭据、手机号及日志控制字符。
  const secrets = cookie.split(';').map(p => p.slice(p.indexOf('=') + 1).trim()).filter(Boolean);
  if (/[\x00-\x1f\x7f]|1[3-9]\d{9}|cookie|token|session/i.test(value) || secrets.some(s => value.includes(s))) return;
  log(`账号身份：${value}`);
}
async function topics(cookie) {
  const result = new Map();
  let maxPage;
  for (let page = 1; page <= (maxPage || 1); page++) {
    const url = new URL('https://weibo.com/ajax/profile/topicContent');
    url.search = new URLSearchParams({tabid:'231093_-_chaohua', page:String(page)}).toString();
    const body = await request(url, cookie);
    if (!body || body.ok !== 1 || !body.data || !Array.isArray(body.data.list))
      throw new Error('关注超话列表业务校验失败，请检查登录状态或接口变化');
    if (page === 1) printIdentity(body, cookie);
    const currentMax = Number(body.data.max_page);
    if (!Number.isInteger(currentMax) || currentMax < 0 || currentMax > 1000)
      throw new Error('分页字段异常，停止操作');
    if (maxPage === undefined) maxPage = Math.max(1, currentMax);
    else if (Math.max(1, currentMax) !== maxPage) throw new Error('分页总数变化，请稍后重试');
    for (const item of body.data.list) {
      if (!item || typeof item.oid !== 'string' || !/^1022:[a-zA-Z0-9_-]+$/.test(item.oid))
        throw new Error('超话标识格式异常，停止操作');
      result.set(item.oid.slice(5), {id:item.oid.slice(5)});
    }
    log(`阶段 1 获取第 ${page}/${maxPage} 页成功，本页 ${body.data.list.length} 项`);
  }
  return [...result.values()];
}
async function sign(cookie, id) {
  const url = new URL('https://weibo.com/p/aj/general/button');
  // api 是微博代理接口所需的上游参数，不直接访问该 HTTP 地址。
  url.search = new URLSearchParams({ajwvr:'6', api:'http://i.huati.weibo.com/aj/super/checkin',
    texta:encodeURI('签到'), textb:encodeURI('已签到'), status:'0', id, __rnd:String(Date.now())}).toString();
  const body = await request(url, cookie);
  if (body && String(body.code) === '100000') return 'success';
  if (body && String(body.code) === '382004') return 'alreadyComplete';
  throw new Error('签到业务校验失败，请检查登录状态、风控或接口变化');
}
function selectedForNotification() {
  const mode = process.env.QINGLONG_NOTIFY || 'auto';
  if (disabled(mode)) return false;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (selection === undefined) return enabled(mode);
  const filename = path.basename(__filename);
  const relative = path.relative(process.env.QL_DIR ? path.join(process.env.QL_DIR, 'scripts') : '/ql/data/scripts', __filename).split(path.sep).join('/');
  return selection.split(/[,;\s]+/).filter(Boolean).some(pattern => {
    const escaped = pattern.split('*').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    const re = new RegExp(`^${escaped}$`);
    return [CATALOG, filename, relative].some(v => re.test(v));
  });
}
async function notify(message) {
  if (!selectedForNotification()) {log('通知：未启用或未被选择'); return 'disabled';}
  if (dry) {log('通知：断网预演，仅模拟脱敏总结投递'); return 'dry-run';}
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const helper = candidates.find(p => fs.existsSync(p));
  if (!helper) {log('⚠️ 通知：未找到青龙 sendNotify.js，保留业务退出码'); return 'unavailable';}
  return new Promise(resolve => {
    // 子进程隔离通知模块，丢弃其日志，防止通知配置及返回体泄漏。
    const code = 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))';
    const child = spawn(process.execPath, ['-e', code, helper, TITLE, message], {stdio:'ignore'});
    const timer = setTimeout(() => child.kill('SIGKILL'), 15000);
    let done = false;
    const finish = ok => {
      if (done) return; done = true; clearTimeout(timer);
      log(ok ? '通知：已发送脱敏总结' : '⚠️ 通知：投递失败，保留业务退出码');
      resolve(ok ? 'sent' : 'failed');
    };
    child.on('error', () => finish(false)); child.on('close', code => finish(code === 0));
  });
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}；账号数：${accounts.length}`);
  const stats = {success:0, alreadyComplete:0, skipped:0, failed:0};
  const accountResults = [];
  let configurationError = false;
  let interval = 500;
  const auto = process.env.WB_AUTO_SIGN === undefined ? true : enabled(process.env.WB_AUTO_SIGN);
  if (!accounts.length) {log('❌ 配置错误：必须设置 WB_COOKIE，每行一个账号'); configurationError = true;}
  if (process.env.WB_AUTO_SIGN !== undefined && !enabled(process.env.WB_AUTO_SIGN) && !disabled(process.env.WB_AUTO_SIGN)) {
    log('❌ 配置错误：WB_AUTO_SIGN 必须为布尔开关'); configurationError = true;
  }
  if (process.env.WB_INTERVAL_MS !== undefined) {
    interval = Number(process.env.WB_INTERVAL_MS);
    if (!Number.isInteger(interval) || interval < 500 || interval > 60000) {
      log('❌ 配置错误：WB_INTERVAL_MS 须为 500 至 60000 的整数'); configurationError = true;
    }
  }
  if (process.env.WB_DRY_RUN !== undefined && !enabled(process.env.WB_DRY_RUN) && !disabled(process.env.WB_DRY_RUN)) {
    log('❌ 配置错误：WB_DRY_RUN 必须为布尔开关'); configurationError = true;
  }
  const globalConfigurationError = configurationError;
  for (let i = 0; i < accounts.length; i++) {
    const begin = Date.now();
    const item = {account:i+1, success:0, alreadyComplete:0, skipped:0, failed:0, total:0};
    log(`账号 ${i+1} / ${accounts.length} 开始`);
    try {
      if (globalConfigurationError) throw new Error('全局配置错误，未执行网络请求');
      if (!cookieValid(accounts[i])) {configurationError = true; throw new Error('账号 Cookie 格式无效，未执行网络请求');}
      log(`账号 ${i+1} 阶段 1：获取关注超话`);
      let phase = Date.now();
      const list = dry ? [{id:'dry_run_placeholder'}] : await topics(accounts[i]);
      log(`账号 ${i+1} 阶段 1 完成，${list.length} 项，耗时 ${Date.now()-phase} 毫秒${dry ? '（模拟数据）' : ''}`);
      item.total = list.length;
      log(`账号 ${i+1} 阶段 2：${auto ? '逐项签到' : '只读模式，跳过签到'}`);
      phase = Date.now();
      for (let j = 0; j < list.length; j++) {
        if (dry || !auto) {
          item.skipped++; log(`账号 ${i+1} 第 ${j+1} 项 ⏭️ ${dry ? 'DRY_RUN_OK：已模拟分页与签到流程，未请求网络' : '自动签到已关闭'}`); continue;
        }
        if (j) await pause(interval);
        try {
          const state = await sign(accounts[i], list[j].id);
          item[state]++;
          log(`账号 ${i+1} 第 ${j+1} 项 ${state === 'success' ? '✅ 签到成功' : '☑️ 已签到'}`);
        } catch (error) {item.failed++; log(`账号 ${i+1} 第 ${j+1} 项 ❌ ${error.message}`);}
      }
      log(`账号 ${i+1} 阶段 2 完成，耗时 ${Date.now()-phase} 毫秒`);
    } catch (error) {
      item.failed++; item.total++; log(`账号 ${i+1} ❌ ${error.message}`);
    }
    item.elapsedMs = Date.now()-begin;
    for (const key of Object.keys(stats)) stats[key] += item[key];
    accountResults.push(item);
    log(`账号 ${i+1} 统计：总任务 ${item.total}，成功 ${item.success}，已完成 ${item.alreadyComplete}，跳过 ${item.skipped}，失败 ${item.failed}，耗时 ${item.elapsedMs} 毫秒`);
  }
  const failed = accountResults.filter(r => r.failed > 0).length;
  const succeeded = accountResults.length - failed;
  const exitCode = configurationError || failed ? 1 : 0;
  const status = configurationError ? 'configuration-error' : failed ? (succeeded ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const message = `模式：${dry ? '断网预演' : '正式执行'}；账号总数 ${accounts.length}，成功 ${succeeded}，失败 ${failed}；子任务成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；状态 ${status}`;
  let notification;
  try {notification = await notify(message);} catch {notification = 'failed'; log('⚠️ 通知失败，保留业务退出码');}
  console.log('----------------------------------------');
  log(message);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now()-started} 毫秒；通知 ${notification}；最终状态 ${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({task:TITLE, mode:dry?'dry-run':'live', status, accounts:accounts.length,
    succeeded, failed, tasks:stats, accountResults, notification, elapsedMs:Date.now()-started, exitCode}));
  process.exitCode = exitCode;
}
main().catch(() => {process.exitCode = 1; console.error('任务执行器异常，未确认业务成功');});
