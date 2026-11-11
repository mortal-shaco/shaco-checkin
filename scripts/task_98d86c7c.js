// name: 百度贴吧关注吧签到
// cron: 48 10 * * *
// 来源 https://github.com/xdmjun/tbautosign ，原文件 index.js
// 上游提交 fec5a92235b2e12799ea539808851c83cfce634f ，有效许可证 MIT。
/*
MIT License
Upstream attribution: xdmjun/tbautosign contributors.

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
// 合并来源：wangyw15/tieba-signin index.py (MIT)，提交 fb036f4caf6385dece9b2b315911231a580d79f0。
// 保留原来源归属：wangyw15/tieba-signin contributors。
// 原功能：config.json 的 accounts(enable/name/bduss/stoken/push)、push 分组，
// 关注吧签到、已签跳过、排名/累计天数、Server酱及PushDeer；原入口无内置计划。
// TIEBA_CONFIG 可直接填写原 config.json 的 JSON 内容，避免依赖配置文件或仓库。
// 优先使用 BDUSS；TIEBA_CONFIG 账号仅作旧配置迁移，显式 enable=false 的账号不运行。
// 原账号 name 仅作本地配置标记，不打印；官方返回的公开身份正常显示。
// TIEBA_SERVERCHAN_KEY/TIEBA_PUSHDEER_KEY 为独立可选全局通知密钥。
'use strict';

// qinglong-notification-policy: begin
(() => {
  const raw = process.env.QINGLONG_NOTIFY;
  if (raw !== undefined && String(raw).trim() !== '' && String(raw).trim().toLowerCase() !== 'auto') return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["98d86c7c8da22e52", "scripts/task_98d86c7c.js", "task_98d86c7c.js", "task_98d86c7c"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
// Node.js >= 18。BDUSS 每个非空行一个账号，填写 Cookie 中 BDUSS 字段的值。
// 获取方式：在浏览器登录 tieba.baidu.com，通过开发者工具的 Cookie 存储查看。
// 请仅在青龙环境变量中保存，勿粘贴到日志。旧版 && 多账号分隔已改为换行。
// TIEBA_DRY_RUN=1 完全断网，仅演练解析、阶段、统计及通知摘要。
// 沿用维护版发布计划：每天 10:48。
// 合并来源：asc00001/TiebaSignIn-Auto run.py (MIT)，关联 run.py (MIT)，
// 关联 scripts/forum/tieba_checkin.py (MIT)。保留上述 MIT 许可及原维护版归属。
// 功能清单：原入口登录/关注吧/五轮重试/STOKEN网页兜底/PushPlus；
// 关联客户端签名、完整分页、排名；关联循环启动器无新增业务，不合并常驻循环。
// 保留维护版默认网页签到、五秒间隔、验证码停止、通知选择器及逐账号统计。
// BDUSS 每行 BDUSS原值 或 BDUSS原值|STOKEN原值；仅在第一个 | 处分割。
// STOKEN 是同账号 Cookie 的 STOKEN 字段；兼容单账号 STOKEN 与 --bduss/--stoken。
// 凭据从登录后的贴吧 Cookie 存储获取，不应通过日志或公开文件传递。
// TIEBA_SIGN_MODE=client 显式启用关联源码支持的签名客户端接口，默认 web。
// TIEBA_MAX_ROUNDS=1..5，默认1保持原维护行为；5启用原入口多轮能力。
// 重试前刷新TBS并休息60..90秒，仅重试网络错误和无明确业务码的响应。
// SCKEY / PUSHPLUS_TOKEN：可选 PushPlus 控制台令牌，通知受全局开关约束。
// 关联源码未给出凭据获取教程；以上补充浏览器获取说明。无发帖、评论或关注副作用。

const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { createHash } = require('node:crypto');
const { spawn } = require('node:child_process');

const TITLE = '百度贴吧关注吧签到';
const CATALOG_ID = '98d86c7c8da22e52';
const enabled = value => /^(1|true|yes|on)$/i.test(value || '');
const dryRun = enabled(process.env.TIEBA_DRY_RUN);
const started = Date.now();
const secrets = [];
let stageNumber = 0;
let signMode = 'web';
let maxRounds = 1;
let legacyConfig = { accounts: [], push: [] };
let accountConfigs = [];
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const randomWait = (min, max) => sleep((min + Math.random() * (max - min)) * 1000);

function clean(value) {
  let text = String(value).replace(/[\x00-\x1f\x7f]/g, ' ');
  for (const secret of secrets) {
    if (secret) text = text.split(secret).join('[已隐藏]');
  }
  return text.replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, '[手机号已隐藏]');
}

function log(message) {
  console.log(`[${new Date().toTimeString().slice(0, 8)}] ${clean(message)}`);
}

function failure(message) {
  const error = new Error(message);
  error.safeMessage = message;
  return error;
}

function safeError(error) {
  return error.safeMessage || '操作异常，已隐藏底层错误信息';
}

function stats() {
  return { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
}

async function stage(account, name, operation) {
  const number = ++stageNumber;
  const start = Date.now();
  account.tasks.total++;
  log(`账号 ${account.index} · 阶段 ${number} ${name} 开始`);
  try {
    const result = await operation();
    const outcome = result.outcome || 'success';
    account.tasks[outcome]++;
    log(`${outcome === 'alreadyComplete' ? '☑️' : '✅'} 账号 ${account.index} · 阶段 ${number} ${name} ${result.message}，耗时 ${Date.now() - start}ms`);
    return result;
  } catch (error) {
    account.tasks.failed++;
    account.failed = true;
    log(`❌ 账号 ${account.index} · 阶段 ${number} ${name} ${safeError(error)}，耗时 ${Date.now() - start}ms`);
    throw error;
  }
}

// 每次独立构造请求头，禁止跟随重定向，凭据仅发送到固定贴吧 HTTPS 主机。
function requestJson(route, bduss, form, options = {}) {
  if (dryRun) throw failure('断网演练禁止 HTTP 请求');
  return new Promise((resolve, reject) => {
    const body = form ? (options.json ? JSON.stringify(form) : new URLSearchParams(form).toString()) : null;
    const headers = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
      ...(bduss ? { Cookie: `BDUSS=${bduss}${options.stoken ? '; STOKEN=' + options.stoken : ''}` } : {}),
      Accept: 'application/json',
    };
    if (body) {
      headers['Content-Type'] = options.json ? 'application/json' : 'application/x-www-form-urlencoded; charset=UTF-8';
      headers['Content-Length'] = Buffer.byteLength(body);
    }
    let settled = false;
    let timer;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolve(value);
    };
    const req = https.request({
      hostname: options.hostname || 'tieba.baidu.com', path: route, method: body ? 'POST' : 'GET', headers,
    }, response => {
      if (response.statusCode !== 200) {
        finish(failure(`HTTP 状态异常（${response.statusCode}）`));
        response.destroy();
        return;
      }
      const chunks = [];
      let bytes = 0;
      response.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 2 * 1024 * 1024) {
          finish(failure('接口响应超过大小限制'));
          response.destroy();
          return;
        }
        chunks.push(chunk);
      });
      response.on('error', () => finish(failure('读取接口响应失败')));
      response.on('aborted', () => finish(failure('接口响应中断')));
      response.on('end', () => {
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error();
          finish(null, data);
        } catch {
          finish(failure('接口返回无效 JSON 对象'));
        }
      });
    });
    timer = setTimeout(() => {
      finish(failure('接口请求超时（15 秒）'));
      req.destroy();
    }, 15000);
    req.on('error', () => finish(failure('网络请求失败')));
    req.end(body);
  });
}

function publicIdentity(response) {
  const data = response.data || {};
  const user = data.user_info || data.user || response.user_info || {};
  const name = user.user_name || user.username || user.name || user.nickname || user.display_name || data.display_name || response.nickname || response.username || response.display_name || response.user_name;
  const uid = user.user_id || user.uid || data.uid || response.uid;
  if (typeof name === 'string' && name.trim()) log(`官方账号身份 ${name}`);
  if (typeof uid === 'number' || typeof uid === 'string') log(`官方公开 UID ${uid}`);
}

function signed(data) {
  const text = Object.keys(data).sort().map(key => `${key}=${data[key]}`).join('');
  return { ...data, sign: createHash('md5').update(text + 'tiebaclient!!!').digest('hex').toUpperCase() };
}

async function getTbs(credential) {
  const data = await requestJson('/dc/common/tbs', credential);
  if (typeof data.tbs === 'string') secrets.push(data.tbs);
  if (String(data.is_login) !== '1' || typeof data.tbs !== 'string' || !data.tbs.trim()) {
    const error = failure('登录校验失败，请重新获取 BDUSS'); error.retryable = false; throw error;
  }
  publicIdentity(data);
  return data.tbs;
}

async function clientForums(credential) {
  const forums = [], seen = new Set();
  for (let page = 1; page <= 1000; page++) {
    const data = await requestJson('/c/f/forum/like', credential, signed({
      BDUSS: credential, _client_type: '2', _client_id: 'wappc_1534235498291_488',
      _client_version: '9.7.8.0', _phone_imei: '000000000000000', from: '1008621y',
      page_no: String(page), page_size: '200', model: 'MI+5', net_type: '1',
      timestamp: String(Math.floor(Date.now() / 1000)), vcode_tag: '11',
    }), { hostname: 'c.tieba.baidu.com' });
    // 关联源码未要求列表成功码必须存在；有返回时必须明确成功。
    if ((data.error_code !== undefined && String(data.error_code) !== '0') ||
        !data.forum_list || typeof data.forum_list !== 'object' || Array.isArray(data.forum_list) ||
        !['0', '1'].includes(String(data.has_more))) throw failure('客户端关注列表业务失败或响应结构变化');
    let added = 0;
    for (const type of ['non-gconforum', 'gconforum']) {
      const group = data.forum_list[type];
      if (group === undefined) continue;
      const items = Array.isArray(group) ? group : [group];
      for (const item of items) {
        if (!item || typeof item.name !== 'string' || !item.name.trim() || !item.id) throw failure('客户端关注条目不完整');
        const key = String(item.id);
        if (!seen.has(key)) { seen.add(key); forums.push({ forum_name: item.name, id: key }); added++; }
      }
    }
    publicIdentity(data);
    log(`客户端关注列表第 ${page} 页验证通过，新增 ${added} 个`);
    if (String(data.has_more) === '0') return forums;
    if (!added) throw failure('客户端分页没有进展，停止以避免遗漏或循环');
    await randomWait(1, 2);
  }
  throw failure('客户端关注列表超过分页安全上限，未执行签到');
}

function signResult(data, client) {
  const code = String(client ? data.error_code : data.no);
  if (code === '0') {
    const info = data.data?.uinfo || data.user_info || {};
    const rank = info.user_sign_rank;
    const days = info.total_sign_num;
    return { message: '签到成功' + (/^\d+$/.test(String(rank)) ? `，第 ${rank} 个签到` : '') +
      (/^\d+$/.test(String(days)) ? `，共签到 ${days} 天` : '') };
  }
  if (code === (client ? '160002' : '1101')) return { outcome: 'alreadyComplete', message: '已经签到过了' };
  const error = failure(code === '2150040' ? '需要验证码，停止当前账号后续签到' :
    `签到业务失败（状态码 ${/^\d{1,10}$/.test(code) ? code : '缺失或无效'}）`);
  error.captcha = code === '2150040';
  error.retryable = !/^\d{1,10}$/.test(code);
  throw error;
}

async function submitSign(forum, credential, stoken, tbs) {
  const web = () => requestJson('/sign/add', credential, { ie: 'utf-8', kw: forum.forum_name, tbs }, { stoken });
  if (signMode === 'web') return signResult(await web(), false);
  try {
    return signResult(await requestJson('/c/c/forum/sign', credential, signed({
      BDUSS: credential, _client_type: '2', _client_version: '9.7.8.0',
      _phone_imei: '000000000000000', model: 'MI+5', net_type: '1',
      fid: forum.id, kw: forum.forum_name, tbs, timestamp: String(Math.floor(Date.now() / 1000)),
    }), { hostname: 'c.tieba.baidu.com' }), true);
  } catch (error) {
    if (error.captcha || !stoken) throw error;
    log('客户端未确认成功，使用同账号 STOKEN 尝试网页兜底');
    await sleep(5000);
    return signResult(await web(), false);
  }
}

async function signWithRetries(forum, credential, stoken, initialTbs) {
  let tbs = initialTbs;
  for (let round = 1; round <= maxRounds; round++) {
    try {
      if (round > 1) {
        log(`签到重试 ${round}/${maxRounds}，刷新校验值并进行轮间节流`);
        tbs = await getTbs(credential);
        await randomWait(60, 90);
      }
      await sleep(5000); // 所有模式保留原维护版每次签到前五秒间隔。
      return await submitSign(forum, credential, stoken, tbs);
    } catch (error) {
      if (error.captcha || error.retryable === false || round === maxRounds) throw error;
      log(`第 ${round} 次未确认成功，安排安全重试；凭据和原始响应已隐藏`);
    }
  }
}

async function runAccount(account, accountLine) {
  const split = accountLine.indexOf('|');
  const credential = split < 0 ? accountLine : accountLine.slice(0, split).trim();
  const stoken = split < 0 ? (process.env.STOKEN || '').trim() : accountLine.slice(split + 1).trim();
  secrets.push(credential, stoken);
  const accountStarted = Date.now();
  log(`账号 ${account.index} 开始`);
  try {
    await stage(account, '凭据检查', async () => {
      if (!/^[A-Za-z0-9._~+/=-]+$/.test(credential) || (stoken && !/^[A-Za-z0-9._~+/=|%-]+$/.test(stoken))) {
        throw failure('BDUSS 格式错误，请填写单独的字段值并用换行分隔账号');
      }
      return { message: `凭据格式通过，签到模式 ${signMode}，最多 ${maxRounds} 轮，网页兜底 ${stoken ? '已配置' : '未配置'}` };
    });
    if (dryRun) {
      await stage(account, '断网演练', async () => ({ message: 'DRY_RUN_OK 流程计划为登录校验、关注吧读取、逐吧签到及验证码停止，实际请求 0 次' }));
      account.status = 'dry-run';
      return;
    }
    const { tbs } = await stage(account, '获取登录校验值', async () => {
      return { tbs: await getTbs(credential), message: '已验证登录状态并获取校验值' };
    });
    const { forums } = await stage(account, '读取关注贴吧', async () => {
      if (signMode === 'client') { const forums = await clientForums(credential); return { forums, message: `完整分页读取 ${forums.length} 个关注贴吧` }; }
      const data = await requestJson('/mo/q/newmoindex', credential, null, { stoken });
      if (String(data.no) !== '0' || !Array.isArray(data.data?.like_forum)) {
        throw failure('关注吧接口业务失败或响应结构变化');
      }
      const forums = data.data.like_forum;
      if (forums.some(forum => !forum || typeof forum.forum_name !== 'string' || !forum.forum_name.trim())) {
        throw failure('关注吧列表包含无效贴吧名称');
      }
      publicIdentity(data);
      return { forums, message: `已验证关注吧列表，共 ${forums.length} 个` };
    });
    for (let index = 0; index < forums.length; index++) {
      const forum = forums[index];
      try {
        await stage(account, `签到 ${forum.forum_name}吧`, async () => {
          if (String(forum.is_sign) === '1') return { outcome: 'alreadyComplete', message: '关注列表确认今日已签到' };
          return await signWithRetries(forum, credential, stoken, tbs);
        });
      } catch (error) {
        if (error.captcha) {
          const remaining = forums.length - index - 1;
          account.tasks.total += remaining;
          account.tasks.skipped += remaining;
          log(`⏭️ 账号 ${account.index} 需要验证码，剩余 ${remaining} 个贴吧已跳过`);
          break;
        }
      }
    }
    account.status = account.failed ? 'failure' : 'success';
  } catch {
    account.failed = true;
    account.status = 'failure';
  } finally {
    account.elapsedMs = Date.now() - accountStarted;
    const tasks = account.tasks;
    log(`账号 ${account.index} 结束，总任务 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}，耗时 ${account.elapsedMs}ms，状态 ${account.status}`);
  }
}

function notificationEnabled() {
  const value = (process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (/^(0|false|no|off)$/.test(value)) return false;
  if (enabled(value)) return true;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const selectors = process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean);
  const scriptPath = __filename.replace(/\\/g, '/').split('/scripts/').pop();
  const names = [CATALOG_ID, path.basename(__filename), scriptPath];
  return selectors.some(selector => {
    const pattern = selector.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    return names.some(name => new RegExp(`^${pattern}$`).test(name));
  });
}

// 通知在有超时的子进程中执行，屏蔽通知器输出，保持业务退出码。
function runNotifier(command, args, payload) {
  return new Promise(resolve => {
    let child;
    try {
      child = spawn(command, args, { stdio: ['pipe', 'ignore', 'ignore'] });
    } catch {
      resolve(false);
      return;
    }
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve(false); }, 15000);
    child.on('error', () => { clearTimeout(timer); resolve(false); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0); });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(payload));
  });
}

async function sendPushplus(body) {
  const token = process.env.PUSHPLUS_TOKEN || process.env.SCKEY;
  if (!token) return '未配置 PushPlus';
  secrets.push(token);
  try {
    const data = await requestJson('/send', null, { token, title: TITLE, content: body, template: 'txt', channel: 'wechat' },
      { hostname: 'www.pushplus.plus', json: true });
    if (data.code !== 200) throw failure('PushPlus 未明确受理');
    return 'PushPlus 请求已受理';
  } catch { return 'PushPlus 发送失败，保留业务退出码'; }
}

async function sendAdditionalNotifications(summary) {
  const routes = [];
  if (process.env.TIEBA_SERVERCHAN_KEY) routes.push({ type: 'serverchan', key: process.env.TIEBA_SERVERCHAN_KEY });
  if (process.env.TIEBA_PUSHDEER_KEY) routes.push({ type: 'pushdeer', key: process.env.TIEBA_PUSHDEER_KEY });
  for (const route of legacyConfig.push) {
    const indices = accountConfigs.flatMap((account, index) =>
      Array.isArray(account.push) && account.push.includes(route.name) ? [index + 1] : []);
    if (indices.length) routes.push({ ...route, indices });
  }
  const results = [];
  for (const route of routes) {
    const accounts = route.indices ? summary.accountResults.filter(a => route.indices.includes(a.index)) : summary.accountResults;
    const body = `${TITLE}\n状态 ${summary.status}\n账号总数 ${accounts.length}，成功 ${accounts.filter(a => a.status === 'success').length}，失败 ${accounts.filter(a => a.failed).length}\n` +
      accounts.map(a => `账号 ${a.index}：成功 ${a.tasks.success}，已完成 ${a.tasks.alreadyComplete}，失败 ${a.tasks.failed}`).join('\n');
    try {
      if (route.type === 'serverchan') {
        if (!/^[A-Za-z0-9_-]+$/.test(route.key)) throw failure('通知密钥格式无效');
        const data = await requestJson('/' + encodeURIComponent(route.key) + '.send', null,
          { title: TITLE, desp: body }, { hostname: 'sctapi.ftqq.com' });
        if (String(data.data?.errno) !== '0') throw failure('Server酱未明确受理');
        results.push('Server酱请求已受理');
      } else if (route.type === 'pushdeer') {
        const data = await requestJson('/message/push', null,
          { pushkey: route.key, text: TITLE, desp: body, type: 'markdown' }, { hostname: 'api2.pushdeer.com' });
        if (String(data.code) !== '0') throw failure('PushDeer未明确受理');
        results.push('PushDeer请求已受理');
      }
    } catch { results.push('附加通知发送失败，保留业务退出码'); }
  }
  return results.length ? results.join('；') : '未配置附加通知';
}

async function notify(summary) {
  if (!notificationEnabled()) return '已通过通知开关关闭';
  const body = `${TITLE}\n模式 ${summary.mode}\n账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}\n状态 ${summary.status}\n子任务 ${summary.tasks.total}，成功 ${summary.tasks.success}，已完成 ${summary.tasks.alreadyComplete}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}`;
  // 演练优先保证完全断网，不调用可能联网的青龙通知器。
  if (dryRun) {
    log(`通知摘要（断网演练仅本地输出） ${body}`);
    return '断网演练已输出通知摘要';
  }
  const pushStatus = (await sendPushplus(body)) + '；' + (await sendAdditionalNotifications(summary));
  const directories = [process.env.QINGLONG_NOTIFY_DIR, __dirname, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const payload = { title: TITLE, body };
  const jsCode = `let input=''; process.stdin.on('data', c=>input+=c); process.stdin.on('end', async()=>{try { const p=JSON.parse(input); const m=require(process.argv[1]); await m.sendNotify(p.title,p.body); } catch { process.exitCode=1; }});`;
  for (const directory of [...new Set(directories)]) {
    const filename = path.join(directory, 'sendNotify.js');
    if (fs.existsSync(filename) && await runNotifier(process.execPath, ['-e', jsCode, filename], payload)) return `青龙通知已发送；${pushStatus}`;
  }
  const pythonCode = `import sys,json\nsys.path[:0]=sys.argv[1:]\nfrom notify import send\np=json.load(sys.stdin)\nsend(p['title'],p['body'])`;
  if (await runNotifier('python3', ['-c', pythonCode, ...directories], payload)) return `青龙通知已发送；${pushStatus}`;
  log('⚠️ 青龙通知不可用或发送失败，保留业务退出码');
  return `通知不可用或发送失败；${pushStatus}`;
}

async function main() {
  let configError = '';
  let bdussInput = process.env.BDUSS || '';
  const args = process.argv.slice(2);
  for (let i = 0; i < args.length; i++) {
    const key = args[i];
    if (!['--bduss', '--stoken'].includes(key) || i + 1 >= args.length) { configError = '命令行仅支持 --bduss 和 --stoken 且必须提供值'; break; }
    const value = args[++i];
    secrets.push(value);
    if (key === '--bduss') bdussInput = value;
    else process.env.STOKEN = value;
  }
  signMode = process.env.TIEBA_SIGN_MODE || 'web';
  const rounds = process.env.TIEBA_MAX_ROUNDS || '1';
  if (!['web', 'client'].includes(signMode) || !/^[1-5]$/.test(rounds)) configError = '签到模式必须为 web/client，重试轮数必须为1至5';
  maxRounds = Number(rounds);
  let credentials = bdussInput.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  // 原文件配置通过环境 JSON 迁移；不读取旧绝对路径、工作流模块或 config.json。
  if (process.env.TIEBA_CONFIG) {
    secrets.push(process.env.TIEBA_CONFIG);
    try {
      const config = JSON.parse(process.env.TIEBA_CONFIG);
      if (!config || !Array.isArray(config.accounts) || !Array.isArray(config.push)) throw new Error();
      for (const a of config.accounts) {
        if (!a || typeof a.bduss !== 'string' || (a.stoken !== undefined && typeof a.stoken !== 'string') ||
            (a.push !== undefined && !Array.isArray(a.push)) || typeof a.enable !== 'boolean') throw new Error();
        secrets.push(a.bduss, a.stoken);
      }
      for (const route of config.push) {
        if (!route || !['serverchan', 'pushdeer'].includes(route.type) || typeof route.name !== 'string' ||
            typeof route.key !== 'string' || !route.key.trim()) throw new Error();
        secrets.push(route.key);
      }
      if (new Set(config.push.map(r => r.name)).size !== config.push.length ||
          config.accounts.some(a => a.push?.some(name => !config.push.some(r => r.name === name)))) throw new Error();
      legacyConfig = config;
      if (credentials.length) {
        // 同时给出两套账号容易将通知发给错误分组，显式拒绝歧义。
        configError = 'BDUSS 与 TIEBA_CONFIG 账号不能同时配置，请选择一种账号来源';
      } else {
        accountConfigs = config.accounts.filter(a => a.enable);
        credentials = accountConfigs.map(a => a.bduss + (a.stoken ? '|' + a.stoken : ''));
        if (credentials.some(line => /[\r\n]/.test(line))) throw new Error();
      }
    } catch { configError = 'TIEBA_CONFIG 格式错误，请使用原 accounts/push 结构和有效通知分组'; }
  }
  secrets.push(...credentials, process.env.STOKEN, process.env.SCKEY, process.env.PUSHPLUS_TOKEN,
    process.env.TIEBA_SERVERCHAN_KEY, process.env.TIEBA_PUSHDEER_KEY);
  if (credentials.length > 1 && process.env.STOKEN) configError = '多账号必须将 STOKEN 与对应 BDUSS 合并到每行，不支持共享 STOKEN';
  log(`========== ${TITLE} ==========`);
  log(`开始时间 ${new Date(started).toISOString()}，模式 ${dryRun ? '断网演练' : '正式执行'}，账号数 ${credentials.length}`);
  const accounts = [];
  if (!credentials.length) log('❌ 配置错误，必须设置 BDUSS，每个非空行一个账号');
  if (configError) log(`❌ 配置错误：${configError}`);
  for (let index = 0; !configError && index < credentials.length; index++) {
    const account = { index: index + 1, tasks: stats(), failed: false, status: 'failure' };
    accounts.push(account);
    await runAccount(account, credentials[index]);
  }
  const failed = accounts.filter(account => account.failed).length;
  const tasks = stats();
  for (const account of accounts) {
    for (const key of Object.keys(tasks)) tasks[key] += account.tasks[key];
  }
  const status = (!credentials.length || configError) ? 'configuration-error' : failed ? (failed === accounts.length ? 'failure' : 'partial-failure') : dryRun ? 'dry-run' : 'success';
  const summary = {
    mode: dryRun ? 'dry-run' : 'live', status, accounts: accounts.length,
    success: accounts.filter(account => account.status === 'success').length,
    dryRunAccounts: accounts.filter(account => account.status === 'dry-run').length,
    failed, tasks, accountResults: accounts,
  };
  try {
    summary.notification = await notify(summary);
  } catch {
    log('⚠️ 通知模块异常，保留业务退出码');
    summary.notification = '通知模块异常';
  }
  summary.elapsedMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  summary.exitCode = !credentials.length || configError || failed ? 1 : 0;
  log('----------------------------------------');
  log(`账号总数 ${summary.accounts}，成功 ${summary.success}，演练 ${summary.dryRunAccounts}，失败 ${failed}`);
  log(`子任务 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`总耗时 ${summary.elapsedMs}ms，完成时间 ${summary.finishedAt}，通知状态 ${summary.notification}，最终状态 ${status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = summary.exitCode;
}

main();
