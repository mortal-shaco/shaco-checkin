// name: 王者营地每日签到
// cron: 59 15 8 * * *
/*
name: 王者营地每日签到
cron: 59 15 8 * * *
SPDX-License-Identifier: GPL-3.0
原作者与来源：NaroisCool/naro-scripts，王者营地.js
来源版本：c2ffa8af2089bd98e1ed623c7a25d49b60ca0fdd
维护版本：独立 Node.js 实现，保留原签到接口、请求参数和定时。

参数获取：在本人已授权的设备上登录王者营地，抓取每日签到时发往
https://kohcamp.qq.com/operation/action/signin 的 POST 请求。
将请求头中的 appid/openid/msdkEncodeParam/sig/userId/source/encode/timestamp/
algorithm/version 等认证字段原样存入 headers，将完整请求体存入 body。
不要粘贴整段 HTTP 报文，不要共享凭据；签名或会话过期后重新抓取，本脚本不生成签名。
WZYD_ACCOUNTS：每个非空行一个 JSON 对象 {"headers":{...},"body":{...}}。
body 保留 cSystem、h5Get、roleId 及实际请求的其他字段；同一行两部分必须属于同一账号。
兼容 WZYD_TOKEN + WZYD_BODY（旧注释中的 WZYY_BODY 也接受）：两个变量的每行
分别为请求头 JSON 和请求体 JSON，按行一一对应；还接受原来的分号分隔格式。
新配置使用换行，禁止用 & 或 @ 分隔账号。WZYD_ACCOUNTS 设置后优先使用。
WZYD_DRY_RUN=1：仅离线校验配置、演示请求阶段与通知摘要，不签到、不发送网络通知。
QINGLONG_NOTIFY=auto|1|0；auto 仅在 QINGLONG_NOTIFY_SCRIPTS 选择本脚本时通知。
选择器支持目录路径、文件名及文件名通配符，逗号、分号或空白分隔，* 表示全部。
通知通过 QINGLONG_NOTIFY_DIR 或青龙标准路径的 sendNotify.js，失败不改变业务退出码。
签到只接受明确数值业务成功码；未识别响应失败退出，不将 HTTP 200 当作签到成功。
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
    const identities = ["e7937ed1d56e881d", "scripts/task_e7937ed1.js", "task_e7937ed1.js", "task_e7937ed1"];
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
const { spawn } = require('node:child_process');
const TITLE = '王者营地每日签到';
const CATALOG = 'e7937ed1d56e881d';
const START = Date.now();
const DRY = /^(1|true|yes|on)$/i.test(process.env.WZYD_DRY_RUN || '');
const ENDPOINT = 'https://kohcamp.qq.com/operation/action/signin';
const secrets = new Set();
function hide(value) {
  let text = String(value);
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
    if (secret) text = text.split(secret).join('[已隐藏]');
  }
  return text.replace(/[\r\n\x00-\x1f\x7f]/g, ' ').replace(/1[3-9]\d{9}/g, '[手机号已隐藏]');
}
function log(text) { console.log(`[${new Date().toLocaleTimeString('zh-CN', { hour12: false })}] ${hide(text)}`); }
function object(value) { return value && typeof value === 'object' && !Array.isArray(value); }
function remember(value, key = '') {
  if (object(value)) for (const [k, v] of Object.entries(value)) remember(v, k);
  else if (/token|cookie|sig|openid|msdk|userId|roleId|timestamp|device|session|phone/i.test(key)) {
    if (value != null) secrets.add(String(value));
  }
}
function rows(raw) {
  // 原变量的历史分号格式仅作兼容；规范变量始终按行解析。
  return String(raw || '').split(/[\r\n;]+/).map(s => s.trim()).filter(Boolean);
}
function accounts() {
  if (process.env.WZYD_ACCOUNTS !== undefined) {
    const lines = process.env.WZYD_ACCOUNTS.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
    if (!lines.length) throw Error('WZYD_ACCOUNTS 为空，请配置账号');
    return lines.map(line => () => JSON.parse(line));
  }
  const headers = rows(process.env.WZYD_TOKEN);
  const bodies = rows(process.env.WZYD_BODY ?? process.env.WZYY_BODY);
  if (!headers.length && !bodies.length) throw Error('缺少 WZYD_ACCOUNTS 或旧版配套凭据变量');
  return Array.from({ length: Math.max(headers.length, bodies.length) }, (_, i) => () => {
    if (!headers[i] || !bodies[i]) throw Error('旧版请求头和请求体账号数量不匹配');
    return { headers: JSON.parse(headers[i]), body: JSON.parse(bodies[i]) };
  });
}
function validate(account) {
  if (!object(account) || !object(account.headers) || !object(account.body)) throw Error('账号必须包含 headers 和 body 两个 JSON 对象');
  remember(account);
  const headers = {};
  for (const [key, value] of Object.entries(account.headers)) {
    if (!/^[!#$%&'*+.^_`|~0-9a-z-]+$/i.test(key) || !['string', 'number'].includes(typeof value) || /[\r\n]/.test(String(value))) throw Error('请求头格式无效');
    const lower = key.toLowerCase();
    if (Object.hasOwn(headers, lower)) throw Error('请求头存在重复字段');
    // 传输层字段由 HTTP 客户端生成，避免错误主机、长度和压缩设置。
    if (!['host', 'content-length', 'connection', 'transfer-encoding', 'accept-encoding'].includes(lower)) headers[lower] = String(value);
  }
  for (const key of ['appid', 'openid', 'msdkencodeparam', 'sig', 'userid', 'timestamp']) {
    if (!headers[key]?.trim()) throw Error('请求头缺少必要认证字段，请重新抓取完整签到请求');
  }
  if (!['string', 'number'].includes(typeof account.body.roleId) || !String(account.body.roleId).trim()) throw Error('请求体缺少 roleId');
  if (!['string'].includes(typeof account.body.cSystem) || !Object.hasOwn(account.body, 'h5Get')) throw Error('请求体缺少 cSystem 或 h5Get');
  headers['content-type'] = 'application/json';
  headers.accept = 'application/json';
  headers['accept-encoding'] = 'identity';
  return { headers, body: account.body };
}
function request(account) {
  return new Promise((resolve, reject) => {
    const data = Buffer.from(JSON.stringify(account.body));
    let settled = false;
    let timer;
    const done = (error, result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(result);
    };
    const req = https.request(ENDPOINT, { method: 'POST', headers: { ...account.headers, 'content-length': data.length } }, res => {
      const chunks = [];
      let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 262144) { done(Error('响应超过大小限制')); res.destroy(); req.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => done(Error('响应读取失败')));
      res.on('aborted', () => done(Error('响应中断')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return done(Error('HTTP 请求失败'));
        try { done(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch { done(Error('响应不是有效 JSON')); }
      });
    });
    req.on('error', () => done(Error('网络请求失败')));
    timer = setTimeout(() => { done(Error('请求超时（15秒）')); req.destroy(); }, 15000);
    req.end(data);
  });
}
function verify(response) {
  if (!object(response)) throw Error('响应结构无法确认签到成功');
  // 原源码没有响应样例或业务码定义；只接受显式的零值业务码，拒绝冲突及未知值。
  const keys = ['returnCode', 'code', 'ret', 'result'];
  const codes = keys.filter(k => Object.hasOwn(response, k));
  if (!codes.length || codes.some(k => response[k] !== 0)) throw Error('业务码未明确成功，请核对凭据或接口契约');
  if (response.success === false || response.data?.success === false) throw Error('接口明确报告失败');
  return true;
}
function identity(response) {
  const scopes = [response, response.data, response.data?.user, response.data?.userInfo];
  for (const scope of scopes) {
    if (!object(scope)) continue;
    for (const key of ['nickname', 'nickName', 'username', 'displayName', 'publicUid']) {
      if (typeof scope[key] === 'string' && scope[key].trim()) return hide(scope[key]);
    }
  }
  return '';
}
function selected() {
  const control = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(control)) return false;
  if (['1', 'true', 'yes', 'on'].includes(control)) return true;
  const selectors = (process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const names = [CATALOG, '王者营地.js', path.basename(__filename), __filename.replace(/\\/g, '/')];
  return selectors.some(selector => {
    const escaped = selector.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.');
    const re = new RegExp(`^${escaped}$`);
    return names.some(name => re.test(name) || name.endsWith('/' + selector));
  });
}
async function notify(body) {
  if (DRY) { log(`⏭️ 离线通知摘要：${body}`); return 'dry-run'; }
  if (!selected()) { log('⏭️ 通知未启用或本脚本未被选择'); return 'disabled'; }
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const helper = candidates.find(file => fs.existsSync(file));
  if (!helper) { log('⚠️ 未找到青龙 sendNotify.js，保留业务退出码'); return 'unavailable'; }
  // 子进程隔离通知模块的日志、异常和超时，凭据不进入通知子进程环境。
  const worker = `let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',async()=>{try{const p=JSON.parse(s);const n=require(process.argv[1]);if(typeof n.sendNotify!=='function')throw Error();await n.sendNotify(p.title,p.body);process.exit(0)}catch{process.exit(1)}});`;
  return new Promise(resolve => {
    const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !/^WZYD_|^WZYY_/.test(k)));
    const child = spawn(process.execPath, ['-e', worker, helper], { env, stdio: ['pipe', 'ignore', 'ignore'] });
    let finished = false;
    let timer;
    const done = ok => {
      if (finished) return;
      finished = true; clearTimeout(timer);
      log(ok ? '✅ 青龙通知已发送' : '⚠️ 青龙通知失败，保留业务退出码');
      resolve(ok ? 'sent' : 'failed');
    };
    child.on('error', () => done(false));
    child.on('close', code => done(code === 0));
    child.stdin.on('error', () => {});
    timer = setTimeout(() => { child.kill('SIGKILL'); done(false); }, 20000);
    child.stdin.end(JSON.stringify({ title: TITLE, body }));
  });
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(START).toISOString()}；模式：${DRY ? '离线预演' : '正式签到'}`);
  log('工具余量未知，无法自动保证 5% 保护');
  log('阶段 0：读取账号配置');
  const results = [];
  let configError = false;
  let loaders = [];
  try { loaders = accounts(); } catch { configError = true; log('❌ 配置错误：请填写规范账号变量或完整的旧版配套变量'); }
  log(`账号数：${loaders.length}`);
  for (const [index, load] of loaders.entries()) {
    const begin = Date.now();
    const stats = { account: index + 1, total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    let stageStart = Date.now();
    let stage = 1;
    try {
      log(`账号 ${index + 1} / 阶段 1：校验账号配置`);
      let account;
      try { account = validate(load()); } catch { throw Error('账号 JSON、配套字段或认证请求头无效，请核对配置说明'); }
      stats.success++;
      log(`✅ 阶段 1 完成，耗时 ${Date.now() - stageStart}ms`);
      stage = 2; stageStart = Date.now();
      log(`账号 ${index + 1} / 阶段 2：${DRY ? '离线演示签到' : '提交每日签到'}`);
      if (DRY) {
        stats.skipped++;
        log('⏭️ DRY_RUN_OK：配置有效；跳过签到请求与网络通知，未验证真实业务结果');
      } else {
        const response = await request(account);
        const name = identity(response);
        if (name) log(`官方账号身份：${name}`);
        verify(response);
        stats.success++;
        log('✅ 签到成功：业务码已校验');
      }
      log(`阶段 2 完成，耗时 ${Date.now() - stageStart}ms`);
    } catch (error) {
      stats.failed++;
      if (stage === 1) { configError = true; stats.skipped++; }
      log(`❌ 阶段 ${stage} 失败：${error.message}；耗时 ${Date.now() - stageStart}ms`);
    }
    stats.elapsedMs = Date.now() - begin;
    results.push(stats);
    log(`账号 ${index + 1} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.elapsedMs}ms`);
  }
  const failed = results.filter(r => r.failed).length;
  const success = results.length - failed;
  const exitCode = configError || failed ? 1 : 0;
  const status = configError ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : DRY ? 'dry-run' : 'success';
  const body = `状态：${status}；账号总数 ${results.length}，${DRY ? '预演通过' : '成功'} ${success}，失败 ${failed}；配置错误 ${configError ? '有' : '无'}。`;
  log('阶段 3：通知与任务汇总');
  let notification;
  try { notification = await notify(body); } catch { notification = 'failed'; log('⚠️ 通知不可用，保留业务退出码'); }
  const totals = results.reduce((a, r) => { for (const k of Object.keys(a)) a[k] += r[k]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  console.log('----------------------------------------');
  log(`任务统计：${body}`);
  log(`子任务统计：总数 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now() - START}ms；通知状态 ${notification}；最终状态 ${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, mode: DRY ? 'dry-run' : 'live', status, accounts: results.length, success, failed, configurationError: configError, totals, results, notification, elapsedMs: Date.now() - START, exitCode }));
  process.exitCode = exitCode;
}
main().catch(() => { console.error('任务发生未预期错误，未输出敏感详情'); process.exitCode = 1; });
