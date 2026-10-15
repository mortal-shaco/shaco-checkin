// name: 好游快爆游戏签到
// cron: 50 1 * * *
/*
 * name: 好游快爆游戏签到
 * cron: 15 8 * * *
 * 上游：qidouhai/checkbox，scripts/hykb_gamesign.js，MIT。
 * 同功能参考：catalogId c6a5976b8d9283cf，MIT。
 * 原始代码出处：https://res.onebiji.com/kuaibao/n/hykb/signcard/js/user.js?v_6_v43
 * 原文件没有定时信息；维护版建议每日北京时间 08:15 执行。
 *
 * HYKB_SCOOKIE：在自己的好游快爆账号登录后，打开游戏签到活动，
 * 使用本地抓包工具读取 signcard/ajax.php 请求表单中的 scookie 值。
 * 每个账号占一行；保留值内部的 |、&、@，不要用这些字符分隔账号。
 * 支持原始值或已百分号编码的值；不需要 Cookie 请求头或 QQ。
 * HYKB_ALLOW_EXPERIENCE=1：允许记录试玩并等待 65 秒后再次核验签到。
 * HYKB_ALLOW_SHARE=1：允许记录分享并再次签到，不发布任何公开文本。
 * 两项默认关闭，避免未经选择的试玩/分享记录；签到仍默认执行。
 * HYKB_DRY_RUN=1：完全断网，使用本地响应演练，不载入通知模块。
 * QINGLONG_NOTIFY=0 可关闭通知；真实模式自动发现青龙 sendNotify.js。
 * Node.js >=18；仅使用标准库，无私有配置、远程代码或安装引导。
 *
 * MIT License
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
'use strict';
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const TITLE = '好游快爆游戏签到';
const BASE = 'https://huodong3.3839.com/n/hykb/';
const UA = 'Mozilla/5.0 (Linux; Android 8.0.0; FRD-AL10 Build/HUAWEIFRD-AL10; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/77.0.3865.120 MQQBrowser/6.2 TBS/045224 Mobile Safari/537.36 V1_AND_SQ_7.1.0_0_TIM_D TIM/3.0.0.2860 QQ/6.5.5 NetType/WIFI WebP/0.3.0 Pixel/1080';
const started = Date.now();
const secrets = [];
let dry = false;
let stageNumber = 0;
function clock() { return new Date().toLocaleTimeString('zh-CN', { hour12: false }); }
function safe(value) {
  let text = String(value).replace(/[\r\n\x00-\x1f\x7f]/g, ' ');
  for (const secret of secrets) {
    if (secret) text = text.split(secret).join('[凭据已隐藏]');
  }
  return text.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function log(text) { console.log(`[${clock()}] ${safe(text)}`); }
function switchValue(name, defaultValue = false) {
  const value = process.env[name];
  if (value === undefined) return defaultValue;
  if (/^(1|true|yes|on)$/i.test(value)) return true;
  if (/^(0|false|no|off)$/i.test(value)) return false;
  throw new Error(`${name} 必须是 1 或 0`);
}
async function stage(stats, title, fn) {
  const begin = Date.now();
  log(`${stats.label} 阶段 ${++stageNumber}：${title}`);
  try {
    const result = await fn();
    stats[result === 'already' ? 'alreadyComplete' : result === 'skipped' ? 'skipped' : 'success']++;
    log(`${stats.label} ${result === 'already' ? '☑️ 已完成' : result === 'skipped' ? '⏭️ 跳过' : '✅ 成功'}：${title}，耗时 ${Date.now() - begin} 毫秒`);
    return result;
  } catch (error) {
    stats.failed++;
    log(`${stats.label} ❌ ${title}：${error.message}，耗时 ${Date.now() - begin} 毫秒`);
    throw error;
  }
}
function request(url, body) {
  if (dry) throw new Error('断网预演禁止 HTTP 请求');
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer;
    const finish = (error, data) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(data);
    };
    const req = https.request(url, {
      method: body === undefined ? 'GET' : 'POST',
      headers: {
        'User-Agent': UA,
        ...(body === undefined ? {} : {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Content-Length': Buffer.byteLength(body)
        })
      }
    }, res => {
      if (res.statusCode !== 200) {
        res.resume();
        finish(new Error(`HTTP 状态异常（${res.statusCode}），不跟随跳转`));
        return;
      }
      const chunks = [];
      let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 2 * 1024 * 1024) {
          finish(new Error('响应超过大小限制'));
          res.destroy(); req.destroy();
        } else chunks.push(chunk);
      });
      res.on('end', () => finish(null, Buffer.concat(chunks).toString('utf8')));
      res.on('error', () => finish(new Error('响应传输失败')));
      res.on('aborted', () => finish(new Error('响应提前中断')));
    });
    req.on('error', () => finish(new Error('网络请求失败，检查网络或服务状态')));
    timer = setTimeout(() => {
      finish(new Error('请求超时（15 秒）')); req.destroy();
    }, 15000);
    req.end(body);
  });
}
function entities(text) {
  return text.replace(/&(#x[\da-f]+|#\d+|quot|apos|amp|lt|gt);/gi, (match, key) => {
    if (key[0] === '#') {
      const number = key[1].toLowerCase() === 'x' ? parseInt(key.slice(2), 16) : Number(key.slice(1));
      return number > 0 && number <= 0x10ffff ? String.fromCodePoint(number) : '';
    }
    return {quot: '"', apos: "'", amp: '&', lt: '<', gt: '>'}[key.toLowerCase()];
  });
}
// 只读取 .glist 中 li 的 .btn onclick，不执行网页 JavaScript。
function parseActivities(html) {
  const stack = [];
  const items = new Map();
  let foundList = false;
  let ended = 0;
  let malformed = 0;
  const cleaned = html.replace(/<!--[\s\S]*?-->/g, '').replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '');
  const tags = cleaned.match(/<\/?[a-zA-Z](?:"[^"]*"|'[^']*'|[^'">])*>/g) || [];
  for (const token of tags) {
    const tag = /^<\/?([\w-]+)/.exec(token)[1].toLowerCase();
    if (/^<\//.test(token)) {
      const index = stack.map(item => item.tag).lastIndexOf(tag);
      if (index >= 0) stack.length = index;
      continue;
    }
    const attrs = {};
    for (const attr of token.matchAll(/([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)) {
      attrs[attr[1].toLowerCase()] = entities(attr[2] ?? attr[3] ?? attr[4]);
    }
    const classes = (attrs.class || '').split(/\s+/);
    const inList = classes.includes('glist') || stack.some(item => item.list);
    if (classes.includes('glist')) foundList = true;
    const li = stack.slice().reverse().find(item => item.tag === 'li');
    if (inList && li && classes.includes('btn')) {
      const onclick = attrs.onclick || '';
      if (onclick.includes('已结束')) ended++;
      else {
        const args = [...onclick.matchAll(/(['"])(.*?)\1/g)].map(match => match[2]);
        const target = args.find(arg => /[?&]hd_id=/.test(arg));
        let id;
        try { if (target) id = new URL(target, BASE).searchParams.get('hd_id'); } catch (_) { /* 下方闭合失败 */ }
        if (!id || !/^\d+$/.test(id)) malformed++;
        else items.set(id, { id, title: (args[1] || `活动 ${id}`).replace(/每日签到领/g, '') });
      }
    }
    if (!/\/$/.test(token.slice(0, -1)) && !['br', 'img', 'input', 'meta', 'link', 'hr', 'source', 'area', 'wbr', 'embed', 'param', 'col', 'base'].includes(tag)) {
      stack.push({tag, list: inList});
    }
  }
  if (!foundList || malformed || (!items.size && !ended)) throw new Error('活动列表结构不符合本地参考，不能确认活动状态');
  return [...items.values()];
}
function verifyObject(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('业务响应结构异常');
  if (String(data.key) === 'no_login') throw new Error('登录凭据失效，请重新获取 HYKB_SCOOKIE');
  return data;
}
function showIdentity(data, label) {
  for (const object of [data, data.config]) {
    if (!object || typeof object !== 'object') continue;
    for (const key of ['nickname', 'username', 'display_name', 'name', 'uid']) {
      if (typeof object[key] === 'string' || typeof object[key] === 'number') {
        log(`${label} 官方身份 ${key}：${object[key]}`);
      }
    }
  }
}
function makeAPI(credential) {
  const calls = new Map();
  return async (action, id) => {
    if (dry) {
      const count = (calls.get(id) || 0) + (action === 'signToday' ? 1 : 0);
      calls.set(id, count);
      if (action === 'login') return {key: '200', config: {name: '断网演练账号'}};
      if (action !== 'signToday') return {key: '200'};
      if (id === '102') return {key: '-1002'};
      if (id === '103' && count === 1) return {key: '-1005'};
      if (id === '104' && count === 1) return {key: '-1007'};
      return {key: '200', signnum: 1};
    }
    const body = new URLSearchParams({ac: action, t: new Date().toISOString().replace('T', ' ').slice(0, 19), r: String(Math.random()), hd_id: id, hd_id2: id, scookie: credential}).toString();
    const text = await request(`${BASE}signcard/ajax.php`, body);
    let data;
    try { data = JSON.parse(text); } catch (_) { throw new Error('业务接口未返回有效 JSON'); }
    return verifyObject(data);
  };
}
async function runAccount(credential, index, options) {
  const begin = Date.now();
  const stats = {label: `账号 ${index + 1}`, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, verifiedGames: 0};
  stageNumber = 0;
  let api;
  let activities;
  try {
    await stage(stats, '账号参数检查', async () => {
      let decoded = credential;
      if (!credential.includes('|') && /%[\da-f]{2}/i.test(credential)) {
        try { decoded = decodeURIComponent(credential); } catch (_) { throw new Error('HYKB_SCOOKIE 百分号编码格式无效'); }
      }
      if (/[\x00-\x1f\x7f]/.test(decoded)) throw new Error('HYKB_SCOOKIE 包含非法控制字符');
      secrets.push(decoded, encodeURIComponent(decoded));
      api = makeAPI(decoded);
    });
    await stage(stats, '获取未结束的游戏签到活动', async () => {
      const html = dry ? '<ul class="glist">' + ['101', '102', '103', '104'].map(id => `<li><a class="btn" onclick="open(\'index.php?hd_id=${id}\',\'本地测试活动${id}\')"></a></li>`).join('') + '</ul>' : await request(`${BASE}qdjh/index.php`);
      activities = parseActivities(html);
      log(`${stats.label} 发现 ${activities.length} 个有效活动${dry ? '（本地样例）' : ''}`);
      return activities.length ? 'success' : 'skipped';
    });
    for (const item of activities) {
      let credentialInvalid = false;
      try {
        await stage(stats, `${item.title} 登录核验`, async () => {
          const data = verifyObject(await api('login', item.id));
          showIdentity(data, stats.label);
          if (!['200', 'ok'].includes(String(data.key)) && !(data.config && typeof data.config === 'object' && !Array.isArray(data.config))) throw new Error('登录响应缺少可核验的成功标志');
        });
        await stage(stats, `${item.title} 每日签到`, async () => {
          let data = verifyObject(await api('signToday', item.id));
          if (String(data.key) === '-1005' || String(data.key) === '-1007') {
            const experience = String(data.key) === '-1005';
            if (!(experience ? options.experience : options.share)) {
              log(`${stats.label} ⏭️ 未启用${experience ? '试玩' : '分享'}记录：${experience ? 'HYKB_ALLOW_EXPERIENCE' : 'HYKB_ALLOW_SHARE'}=0`);
              stats.skipped++;
              throw new Error(`签到需要${experience ? '试玩' : '分享'}条件，未满足，不能报告签到成功`);
            }
            const action = experience ? 'tiyan' : 'sharelimit';
            log(`${stats.label} 已明确启用${experience ? '试玩' : '分享'}记录，执行 ${action}`);
            const actionData = verifyObject(await api(action, item.id));
            if (!['200', 'ok'].includes(String(actionData.key))) throw new Error('条件动作缺少明确业务成功标志');
            if (experience && !dry) await new Promise(resolve => setTimeout(resolve, 65000));
            if (experience) log(`${stats.label} ${dry ? '断网模拟等待，不休眠' : '已等待 65 秒'}，再次核验签到`);
            const login = verifyObject(await api('login', item.id));
            if (!['200', 'ok'].includes(String(login.key)) && !(login.config && typeof login.config === 'object' && !Array.isArray(login.config))) throw new Error('再次登录未通过核验');
            data = verifyObject(await api('signToday', item.id));
          }
          if (String(data.key) === '-1002') { stats.verifiedGames++; return 'already'; }
          if (String(data.key) !== '200') throw new Error('签到未返回成功或今日已签标志');
          stats.verifiedGames++;
          log(`${stats.label} 签到成功${Number.isInteger(Number(data.signnum)) && Number(data.signnum) >= 0 ? `，累计签到 ${Number(data.signnum)} 天` : ''}${dry ? '（模拟）' : ''}`);
        });
      } catch (error) {
        credentialInvalid = error.message.includes('登录凭据失效');
      }
      if (credentialInvalid) break;
    }
  } catch (_) { /* 已由阶段输出脱敏错误，继续处理其他账号 */ }
  stats.total = stats.success + stats.alreadyComplete + stats.skipped + stats.failed;
  stats.durationMs = Date.now() - begin;
  stats.status = stats.failed ? 'failure' : 'success';
  log(`${stats.label} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs} 毫秒`);
  return stats;
}
async function notify(summary, enabled) {
  const body = `${TITLE}\n状态：${summary.status}\n账号总数：${summary.accountCount}\n成功数：${summary.successAccounts}\n失败数：${summary.failedAccounts}\n子任务成功：${summary.tasks.success}，已完成：${summary.tasks.alreadyComplete}，跳过：${summary.tasks.skipped}，失败：${summary.tasks.failed}\n${summary.configurationError ? '参数配置错误，请查看脱敏日志。' : ''}`;
  if (!enabled) { log('通知状态：全局关闭'); return 'disabled'; }
  if (dry) { log(`通知状态：断网预演，仅展示脱敏通知：${body}`); return 'dry-run'; }
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const file = candidates.find(candidate => fs.existsSync(candidate));
  if (!file) { log('⚠️ 通知模块不可用，保留业务退出码'); return 'unavailable'; }
  let timer;
  try {
    const module = require(file);
    if (typeof module.sendNotify !== 'function') throw new Error('通知模块接口不兼容');
    await Promise.race([module.sendNotify(TITLE, body), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('通知超时')), 10000); })]);
    log('通知状态：已发送脱敏汇总'); return 'sent';
  } catch (_) { log('⚠️ 通知失败或超时，保留业务退出码'); return 'failed'; }
  finally { clearTimeout(timer); }
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}`);
  const results = [];
  let configurationError = false;
  let enabled = !/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1');
  let accounts = [];
  try {
    // 即便其他参数错误，明确指定 dry-run 也不能进入通知网络。
    dry = /^(1|true|yes|on)$/i.test(process.env.HYKB_DRY_RUN || '0');
    dry = switchValue('HYKB_DRY_RUN');
    enabled = switchValue('QINGLONG_NOTIFY', true);
    const options = {experience: switchValue('HYKB_ALLOW_EXPERIENCE'), share: switchValue('HYKB_ALLOW_SHARE')};
    accounts = (process.env.HYKB_SCOOKIE || '').split(/\r?\n/).map(value => value.trim()).filter(Boolean);
    for (const value of accounts) {
      secrets.push(value, encodeURIComponent(value));
    }
    if (!accounts.length) throw new Error('缺少必填 HYKB_SCOOKIE，每行配置一个账号的 scookie');
    log(`运行模式：${dry ? '断网预演' : '真实执行'}；账号数：${accounts.length}`);
    log(`可选动作：试玩记录${options.experience ? '开启' : '关闭'}，分享记录${options.share ? '开启' : '关闭'}`);
    for (let index = 0; index < accounts.length; index++) results.push(await runAccount(accounts[index], index, options));
  } catch (error) {
    configurationError = true;
    log(`运行模式：${dry ? '断网预演' : '真实执行'}；账号数：${accounts.length}`);
    log(`阶段 1：参数检查 ❌ ${error.message}`);
  }
  const failedAccounts = results.filter(result => result.failed).length;
  const summary = {
    name: TITLE, mode: dry ? 'dry-run' : 'live', accountCount: accounts.length,
    successAccounts: results.length - failedAccounts, failedAccounts,
    configurationError,
    status: configurationError ? 'configuration-error' : failedAccounts ? (failedAccounts < results.length ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success',
    tasks: results.reduce((total, item) => {
      for (const key of Object.keys(total)) total[key] += item[key];
      return total;
    }, {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0, verifiedGames: 0}),
    accounts: results
  };
  const exitCode = configurationError || failedAccounts ? 1 : 0;
  log('----------------------------------------');
  log(`任务统计：账号 ${summary.accountCount}，成功 ${summary.successAccounts}，失败 ${summary.failedAccounts}；子任务成功 ${summary.tasks.success}，已完成 ${summary.tasks.alreadyComplete}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}`);
  summary.notification = await notify(summary, enabled);
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  summary.exitCode = exitCode;
  // 保留上游最后输出签到活动计数的格式，只计入核验通过的活动。
  console.log(summary.tasks.verifiedGames);
  log(`完成时间：${summary.finishedAt}；总耗时 ${summary.durationMs} 毫秒；最终状态：${summary.status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  // 通知模块可能遗留连接；汇总写完后仍按业务结果退出。
  process.exitCode = exitCode;
  setImmediate(() => process.exit(exitCode));
}
main();
