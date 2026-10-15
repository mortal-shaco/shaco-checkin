// name: 吾爱破解每日签到
// cron: 8 0 * * *
// SPDX-License-Identifier: GPL-3.0-only
// 原作者：NobyDa；HTTP 工具原始归属：https://github.com/Peng-YM/QuanX/tree/master/Tools/OpenAPI
// 维护版：Node.js 18+，无需第三方依赖。原始说明保留在文件末尾供归属参考。
// POJIE_COOKIE：每行一个账号的完整 Cookie；CookieWA 为可选兼容别名。
// 获取：浏览器登录 https://www.52pojie.cn/home.php，在开发者工具网络页复制该请求的 Cookie。
// 不需 MITM、不写入本地凭据。POJIE_DRY_RUN=1 完全断网预演。
// BARK_KEY（兼容 barkKey）可选；QINGLONG_NOTIFY=0 关闭所有通知。
'use strict';
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { TextDecoder } = require('node:util');
const TITLE = '吾爱破解每日签到';
const started = Date.now();
const dry = /^(1|true|yes|on)$/i.test(process.env.POJIE_DRY_RUN || '');
const enabled = !/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1');
const cookies = (process.env.POJIE_COOKIE || process.env.CookieWA || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const bark = process.env.BARK_KEY || process.env.barkKey || '';
const results = [];
function stamp() { return new Date().toLocaleTimeString('zh-CN', {hour12:false}); }
function log(msg) { console.log(`[${stamp()}] ${msg}`); }
function request(url, options = {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer;
    const finish = (err, data) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      err ? reject(err) : resolve(data);
    };
    const req = https.request(url, {method: options.method || 'GET', headers: options.headers || {}}, res => {
      const chunks = []; let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) { finish(new Error('response-limit')); res.destroy(); req.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('network')));
      res.on('aborted', () => finish(new Error('network')));
      res.on('end', () => finish(null, {status:res.statusCode, headers:res.headers, body:Buffer.concat(chunks)}));
    });
    timer = setTimeout(() => { finish(new Error('timeout')); req.destroy(); }, 15000);
    req.on('error', () => finish(new Error('network')));
    if (options.body) req.write(options.body);
    req.end();
  });
}
function decode(response) {
  const type = String(response.headers['content-type'] || '');
  const head = response.body.subarray(0, 4096).toString('ascii');
  const declared = (type + ' ' + head).match(/charset\s*=\s*["']?([\w-]+)/i);
  const encoding = declared && /^(gbk|gb2312|gb18030)$/i.test(declared[1]) ? 'gb18030' : 'utf-8';
  const utf = new TextDecoder(encoding).decode(response.body);
  return !declared && utf.includes('\uFFFD') ? new TextDecoder('gb18030').decode(response.body) : utf;
}
function classify(response) {
  if (response.status < 200 || response.status >= 300) return {status:'failed', message:`❌ HTTP ${response.status}，未验证签到成功`};
  const body = decode(response);
  if (/需要先登录|先登录|请先登录|登录后才能/.test(body)) return {status:'failed', message:'❌ 登录失效，请重新获取 Cookie'};
  if (/下期再来|您已(?:经)?(?:完成|领取|签|做过)/.test(body)) return {status:'alreadyComplete', message:'☑️ 已签到（服务端确认）'};
  if (/已完成|恭喜您/.test(body)) return {status:'success', message:'✅ 签到成功（服务端确认）'};
  return {status:'failed', message:'❌ 未识别到业务成功标志，需检查接口或 Cookie'};
}
function identity(response) {
  // 仅读取 Discuz 的官方用户名链接，不输出页面或 Cookie。
  const body = decode(response);
  const match = body.match(/<strong\b[^>]*class=["'][^"']*\bvwmy\b[^"']*["'][^>]*>\s*<a\b[^>]*href=["'][^"']*home\.php\?mod=space(?:&amp;|&)uid=\d+[^"']*["'][^>]*>([^<>]+)<\/a>/i);
  if (!match) return '';
  const name = match[1].replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'");
  if (/[\r\n\x00-\x1f]/.test(name) || /(?:cookie|token|session|_auth)\s*[=:]/i.test(name) || /\b1[3-9]\d{9}\b/.test(name) || cookies.some(c => c.includes(name))) return '';
  return name;
}
async function account(cookie, index) {
  const at = Date.now();
  let result;
  log(`账号 ${index} · 阶段 1/2：检查授权字段`);
  const auth = cookie.split(';').some(part => /^[^=;\s]*_auth\s*=\s*\S+/.test(part.trim()));
  if (!auth || /[\r\n\x00-\x1f\x7f]/.test(cookie)) {
    result = {status:'failed', message:'❌ Cookie 格式错误或缺少非空 _auth 字段'};
    log(`账号 ${index} · 阶段 1/2：${result.message}，耗时 ${Date.now()-at}ms`);
    log(`账号 ${index} · 阶段 2/2：⏭️ 跳过签到`);
  } else {
    log(`账号 ${index} · 阶段 1/2：✅ 参数检查通过，耗时 ${Date.now()-at}ms`);
    const step = Date.now();
    log(`账号 ${index} · 阶段 2/2：${dry ? '预演签到与响应校验' : '提交每日签到'}`);
    if (dry) result = {status:'dry-run', message:'✅ DRY_RUN_OK：参数检查通过；未执行请求、通知或文件写入'};
    else {
      try {
        const response = await request('https://www.52pojie.cn/home.php?mod=task&do=apply&id=2', {
          method:'PUT', headers:{Cookie:cookie, 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0'}
        });
        result = classify(response);
        const name = identity(response);
        if (name) log(`账号 ${index} · 官方用户名：${name}`);
      } catch (err) {
        const reason = err.message === 'timeout' ? '请求超时' : err.message === 'response-limit' ? '响应超过大小限制' : '网络请求失败';
        result = {status:'failed', message:`❌ ${reason}，未验证签到成功`};
      }
    }
    log(`账号 ${index} · 阶段 2/2：${result.message}，耗时 ${Date.now()-step}ms`);
  }
  const stats = {total:1, success:result.status==='success'?1:0, alreadyComplete:result.status==='alreadyComplete'?1:0, skipped:result.status==='dry-run'?1:0, failed:result.status==='failed'?1:0};
  log(`账号 ${index} 统计：总任务 1，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${Date.now()-at}ms`);
  results.push({account:index, status:result.status, ...stats, elapsedMs:Date.now()-at});
}
async function notify(body) {
  if (!enabled) { log('通知：⏭️ QINGLONG_NOTIFY 已关闭'); return 'disabled'; }
  if (dry) { log('通知：⏭️ 断网预演，仅模拟脱敏总结通知'); return 'dry-run'; }
  let ql = 'unavailable';
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js', path.join(__dirname,'sendNotify.js')].filter(Boolean);
  for (const file of [...new Set(locations)]) {
    if (!fs.existsSync(file)) continue;
    try {
      const module = require(file);
      if (typeof module.sendNotify !== 'function') continue;
      let timer;
      try {
        await Promise.race([Promise.resolve().then(() => module.sendNotify(TITLE, body)), new Promise((_,reject) => {timer=setTimeout(() => reject(new Error('notify-timeout')),20000);})]);
      } finally { clearTimeout(timer); }
      ql = 'sent'; break;
    } catch (_) { ql='failed'; }
  }
  log(`青龙通知：${ql === 'sent' ? '✅ 已发送' : '⚠️ 不可用或发送失败，保留业务退出码'}`);
  if (bark) {
    for (let attempt=1;attempt<=3;attempt++) {
      try {
        const r = await request('https://api.day.app/push', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title:TITLE, body, device_key:bark, ext_params:{group:TITLE}})});
        const data = JSON.parse(r.body.toString('utf8'));
        if (r.status===200 && data.code===200) { log('Bark 通知：✅ 已发送'); break; }
        log(`Bark 通知：⚠️ 第 ${attempt}/3 次未确认成功`);
      } catch (_) { log(`Bark 通知：⚠️ 第 ${attempt}/3 次发送失败`); }
    }
  }
  return ql;
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry?'断网预演':'正式执行'}；账号数：${cookies.length}`);
  if (!cookies.length) log('❌ 配置错误：请设置 POJIE_COOKIE（每行一个账号）');
  for (let i=0;i<cookies.length;i++) await account(cookies[i], i+1);
  const failed = results.filter(r=>r.status==='failed').length;
  const verified = results.filter(r=>['success','alreadyComplete'].includes(r.status)).length;
  const passed = results.length-failed;
  const status = !cookies.length ? 'configuration-error' : failed ? (passed?'partial-failure':'failure') : dry ? 'dry-run' : 'success';
  const code = !cookies.length || failed ? 1 : 0;
  const body = `状态：${status}；账号总数：${cookies.length}；成功数：${dry?passed:verified}；失败数：${failed}；预演通过：${dry?passed:0}。${dry?'未执行业务请求。':''}`;
  log('----------------------------------------');
  log(`账号统计：总数 ${cookies.length}，成功 ${dry?0:verified}，预演通过 ${dry?passed:0}，失败 ${failed}`);
  const tasks = results.reduce((sum,r)=>{for(const key of Object.keys(sum)) sum[key]+=r[key];return sum;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log(`子任务统计：总数 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  const notification = await notify(body);
  const summary = {task:TITLE, mode:dry?'dry-run':'live', status, accounts:cookies.length, success:verified, dryRunPassed:dry?passed:0, failed, tasks, results, notification, elapsedMs:Date.now()-started, finishedAt:new Date().toISOString(), exitCode:code};
  log(`总耗时：${summary.elapsedMs}ms；完成时间：${summary.finishedAt}；最终状态：${status}；通知状态：${notification}`);
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
  process.exitCode=code;
}
if (require.main === module) {
  main().catch(async () => {
    log('❌ 任务内部异常；未确认业务成功');
    const notification = await notify(`状态：failure；账号总数：${cookies.length}；成功数：0；失败数：${cookies.length}；任务内部异常。`).catch(()=>'failed');
    log(`完成时间：${new Date().toISOString()}；最终状态：failure；耗时 ${Date.now()-started}ms`);
    console.log('TASK_SUMMARY='+JSON.stringify({task:TITLE,status:'failure',accounts:cookies.length,success:0,failed:cookies.length,notification,exitCode:1}));
    process.exitCode=1;
  });
}
module.exports = {classify, decode};

/* 原始作者说明（历史配置；维护版以顶部环境变量说明为准）

吾爱破解签到脚本

更新时间: 2022.6.18
脚本兼容: QuantumultX, Surge, Loon, Node.js
电报频道: @NobyDa
问题反馈: @NobyDa_bot

************************
QX, Surge, Loon说明：
************************
手动登录 https://www.52pojie.cn/home.php 如通知成功获取cookie, 则可以使用此签到脚本.
获取Cookie后, 请将Cookie脚本禁用并移除主机名, 以免产生不必要的MITM.
脚本将在每天上午9点执行, 您可以修改执行时间.

************************
Node.js说明: 
************************
需自行安装"got"与"iconv-lite"模块. 例: npm install got iconv-lite -g

抓取Cookie说明:
浏览器打开 https://www.52pojie.cn/home.php 登录账号后, 开启抓包软件并刷新页面.
抓取该URL请求头下的Cookie字段, 填入以下CookieWA的单引号内即可. *
*/
