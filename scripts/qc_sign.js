// name: 青瓷签到与会话保活
// cron: 25 * * * *
/*
 * name: 青瓷签到与会话保活
 * cron: 0 * * * *
 * 来源: justin0406/qc-checkin / scripts/qc_sign.js
 * 原始版本: 3ebc1cc03e91f21fcf526f31e43bd587b8dcdb67，许可证 MIT。
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
 *
 * Node.js >=18，无第三方业务依赖。每小时运行，超过约两小时未保活可能需要重抓。
 * 在微信打开已绑定角色的官方活动页面，抓取 api.qingcigame.com 请求 Cookie
 * （必须含 PHPSESSID）及 URL 的 app_id、page_id；通行证账号密码不能替代微信会话。
 * QC_ACCOUNTS: 每个非空行一个账号，可直接填完整 Cookie；或 app_id,page_id|完整Cookie。
 * 只拆分第一个 |，Cookie 内的 =、&、@、| 均原样保留，不用这些符号分隔账号。
 * 未指定游戏时 QC_APP_ID=39、QC_PAGE_ID=1；旧 qc_ck、qc_app=app_id|page_id 可兼容。
 * QC_ARGUMENT=app_id=58&page_id=8 覆盖游戏（对应上游 argument）；按账号前缀次优先。
 * 常见 app_id: 39 最强蜗牛、33 提灯与地下城、35 时光旅行社、58/69 仙剑、74 魔卡少女樱。
 * QC_ALLOW_BIND=1 才允许按官方 /game/my 中已有角色资料绑定；默认不修改绑定。
 * QC_DRY_RUN=1: 完全离线，不读写会话缓存、不加载通知模块，展示通知预览。
 * 缓存为本文件同目录 .qc-session-state.json（0600），可用 QC_STATE_FILE 设置绝对路径。
 * 缓存关联原始凭据摘要，更新环境 Cookie 后旧缓存自动失效；请保护缓存，勿上传仓库。
 * 每次从服务端验证签到状态；不以本地完成标记冒充成功。
 * QINGLONG_NOTIFY=auto|1|0；auto 默认选中本任务；QINGLONG_NOTIFY_SCRIPTS 可替换选择清单。
 * 通知仅调用青龙 sendNotify.js / notify.py，失败不影响业务退出码。
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
    const identities = ["17218a3f4a2a30a6", "scripts/qc_sign.js", "qc_sign.js", "qc_sign"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawn } = require('child_process');
const E = process.env;
const DRY = E.QC_DRY_RUN === '1';
const TITLE = '青瓷签到与会话保活';
const BASE = 'https://api.qingcigame.com';
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49(0x18003128) NetType/WIFI Language/zh_CN';
const stateFile = E.QC_STATE_FILE || path.join(__dirname, '.qc-session-state.json');
const started = Date.now();
const summary = { task: TITLE, mode: DRY ? 'dry-run' : 'live', accounts: 0, success: 0, failed: 0, alreadyComplete: 0, tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, results: [] };
let state = {};
const truthy = v => v === true || v === 1 || v === '1' || v === 'true';
const stamp = () => new Date().toTimeString().slice(0, 8);
const log = s => console.log(`[${stamp()}] ${s}`);
function fail(message) { throw new Error(message); }
function cookieMap(cookie) {
  const map = new Map();
  for (const part of cookie.split(';')) {
    const i = part.indexOf('=');
    if (i > 0) map.set(part.slice(0, i).trim(), part.slice(i + 1).trim());
  }
  return map;
}
function refreshCookie(cookie, headers) {
  const map = cookieMap(cookie);
  const values = headers['set-cookie'] || [];
  for (const item of (Array.isArray(values) ? values : [values])) {
    for (const seg of String(item).split(/,\s*(?=[A-Za-z0-9_.%-]+=)/)) {
      const pair = seg.split(';')[0];
      const i = pair.indexOf('=');
      if (i > 0) map.set(pair.slice(0, i).trim(), pair.slice(i + 1).trim());
    }
  }
  return [...map].map(([k, v]) => `${k}=${v}`).join('; ');
}
function loadState() {
  if (!path.isAbsolute(stateFile)) fail('会话缓存路径必须为绝对路径');
  if (DRY || !fs.existsSync(stateFile)) return;
  try {
    const st = fs.lstatSync(stateFile);
    if (!st.isFile() || st.isSymbolicLink() || (st.mode & 0o077)) fail('会话缓存必须为仅本人可读写的普通文件');
    const parsed = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') fail('缓存格式错误');
    state = parsed;
  } catch (_) { fail('会话缓存读取失败，请检查权限或移除旧缓存后重新抓取'); }
}
function saveCookie(account) {
  state[account.key] = { cookie: account.cookie };
  const tmp = `${stateFile}.${process.pid}.${crypto.randomBytes(6).toString('hex')}.tmp`;
  try {
    fs.writeFileSync(tmp, JSON.stringify(state), { mode: 0o600, flag: 'wx' });
    fs.renameSync(tmp, stateFile);
  } catch (_) {
    try { fs.unlinkSync(tmp); } catch (_) {}
    fail('续期会话保存失败，请检查缓存目录权限');
  }
}
function parseAccount(line) {
  let app = E.QC_APP_ID || '39', page = E.QC_PAGE_ID || '1';
  if (E.qc_app) [app, page] = E.qc_app.split('|');
  let cookie = line;
  const i = line.indexOf('|');
  if (i >= 0 && /^\d+,\d+$/.test(line.slice(0, i))) {
    [app, page] = line.slice(0, i).split(','); cookie = line.slice(i + 1).trim();
  }
  const args = new URLSearchParams(E.QC_ARGUMENT || '');
  app = args.get('app_id') || app; page = args.get('page_id') || page;
  if (!/^\d+$/.test(app) || !/^\d+$/.test(page)) fail('游戏参数必须是数字');
  if (/[\r\n\x00-\x1f\x7f]/.test(cookie) || !cookieMap(cookie).get('PHPSESSID')) fail('Cookie 格式错误或缺少 PHPSESSID，请重新从微信活动页获取');
  const key = crypto.createHash('sha256').update(`${app}\n${page}\n${cookie}`).digest('hex');
  const saved = state[key];
  if (!DRY && saved && typeof saved.cookie === 'string' && !/[\r\n\x00-\x1f\x7f]/.test(saved.cookie) && cookieMap(saved.cookie).get('PHPSESSID')) cookie = saved.cookie;
  return { app, page, cookie, key };
}
function request(account, method, endpoint, body) {
  if (DRY) return Promise.reject(new Error('离线模式禁止请求'));
  return new Promise((resolve, reject) => {
    let finished = false;
    const done = (err, data) => { if (finished) return; finished = true; clearTimeout(timer); err ? reject(err) : resolve(data); };
    const payload = body ? JSON.stringify(body) : null;
    const headers = {
      'User-Agent': UA, Accept: 'application/json, text/javascript, */*; q=0.01',
      'X-Requested-With': 'XMLHttpRequest', Origin: 'https://h5.qingcigame.com',
      Referer: `https://h5.qingcigame.com/package/template/enter1h15sds6myo?app_id=${account.app}`,
      Cookie: account.cookie,
    };
    if (payload) { headers['Content-Type'] = 'application/json'; headers['Content-Length'] = Buffer.byteLength(payload); }
    const timer = setTimeout(() => { done(new Error('请求超时')); req.destroy(); }, 15000);
    let req;
    try {
      req = https.request(BASE + endpoint, { method, headers }, res => {
        let size = 0; const chunks = [];
        res.on('data', chunk => {
          size += chunk.length;
          if (size > 1048576) { done(new Error('响应过大')); res.destroy(); } else chunks.push(chunk);
        });
        res.on('error', () => done(new Error('响应读取失败')));
        res.on('end', () => {
          if (finished) return;
          if (res.statusCode !== 200) return done(new Error('HTTP 状态异常（未输出响应）'));
          let json;
          try { json = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch (_) { return done(new Error('响应不是有效 JSON')); }
          if (!json || typeof json !== 'object') return done(new Error('响应结构异常'));
          try {
            const updated = refreshCookie(account.cookie, res.headers);
            if (updated !== account.cookie) { account.cookie = updated; saveCookie(account); }
          } catch (_) { return done(new Error('续期会话保存失败')); }
          done(null, json);
        });
      });
      req.on('error', () => done(new Error('网络连接失败')));
      if (payload) req.write(payload);
      req.end();
    } catch (_) { done(new Error('请求配置无效')); }
  });
}
function business(json, label) {
  if (json.code !== 200) fail(`${label}业务未成功，请检查会话或游戏参数（未输出响应）`);
  return json.data;
}
function getStatus(account, user) {
  const query = new URLSearchParams({ game_id: String(user.game_id || account.app), role_id: String(user.role_id || ''), app_id: account.app });
  return request(account, 'GET', '/game/sign/list?' + query).then(j => {
    const data = business(j, '签到查询');
    if (!data || ![true, false, 0, 1, '0', '1', 'true', 'false'].includes(data.is_get)) fail('签到状态字段异常，停止写入');
    return data;
  });
}
// 身份仅输出官方明确的非凭据字段；防止身份字段嵌入当前凭据、手机号或控制字符。
function identity(user, account) {
  const value = user.nickname || user.username || user.display_name || user.role_name || user.user_id;
  if (value === undefined || value === null) return '';
  let text = String(value).replace(/[\x00-\x1f\x7f]/g, ' ');
  for (const secret of cookieMap(account.cookie).values()) if (secret) text = text.split(secret).join('[已隐藏凭据]');
  return text.replace(/1[3-9]\d{9}/g, '[已隐藏手机号]');
}
async function runAccount(line, index) {
  const start = Date.now();
  const counts = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  let stageNumber = 0;
  async function stage(name, action) {
    counts.total++; const t = Date.now(); const n = ++stageNumber;
    log(`账号 ${index} · 阶段 ${n} ${name} 开始`);
    try { const result = await action(); counts.success++; log(`✅ 账号 ${index} · 阶段 ${n} ${name} 完成，耗时 ${Date.now() - t}ms`); return result; }
    catch (err) { counts.failed++; log(`❌ 账号 ${index} · 阶段 ${n} ${name} 失败，耗时 ${Date.now() - t}ms`); throw err; }
  }
  let status = 'failure';
  try {
    const account = await stage('校验账号配置', () => parseAccount(line));
    if (DRY) {
      await stage('离线预演', () => { log(`⏭️ 游戏 ${account.app}，页面 ${account.page}；计划保活、查询、按需签到及复查；绑定${E.QC_ALLOW_BIND === '1' ? '已启用' : '已禁用'}；未联网、未写缓存`); });
      counts.skipped += 4; counts.total += 4;
      status = 'dry-run';
    } else {
      const data = await stage('刷新微信会话', async () => business(await request(account, 'GET', `/game/my?game_id=${account.app}&page_id=${account.page}`), '会话刷新'));
      if (!data || !data.user_info || !data.user_info.user_id) fail('缺少活动用户身份，请重新在微信打开活动页');
      const user = data.user_info;
      log(`账号 ${index} 官方身份：${identity(user, account)}`);
      const before = await stage('查询今日签到', () => getStatus(account, user));
      if (truthy(before.is_get)) { status = 'already-complete'; counts.alreadyComplete++; counts.total++; log(`☑️ 账号 ${index} 今日已签到${/^\d+$/.test(String(before.sign_total)) ? '，累计签到 ' + before.sign_total + ' 天' : ''}`); }
      else {
        const payload = { app_id: account.app, page_id: account.page, game_id: user.game_id || account.app };
        await stage('提交签到', async () => {
          let response = await request(account, 'POST', '/game/sign/record', payload);
          if (String(response.message || '').includes('绑定角色')) {
            if (E.QC_ALLOW_BIND !== '1') fail('需要绑定角色：默认禁止自动修改，请在官方页面绑定后重试，或显式启用 QC_ALLOW_BIND');
            if (!user.account || !user.role_id || !user.server_id || !user.role_name) fail('角色资料不完整，禁止绑定');
            business(await request(account, 'POST', '/game/binds', {
              account: user.account, page_id: account.page, game_id: payload.game_id, role_id: user.role_id,
              role_name: user.role_name, server_id: user.server_id, server_name: user.server_name,
              type: 'android', platform: user.platform || 'android', extra: user.extra || '{}',
            }), '角色绑定');
            log(`账号 ${index} 已按显式开关完成角色绑定，正在重新提交签到`);
            response = await request(account, 'POST', '/game/sign/record', payload);
          }
          business(response, '签到提交');
        });
        await stage('复查签到结果', async () => {
          for (let i = 0; i < 2; i++) {
            if (i) await new Promise(resolve => setTimeout(resolve, 1200));
            const after = await getStatus(account, user);
            if (truthy(after.is_get)) { log(`✅ 账号 ${index} 签到成功，已由官方状态确认${/^\d+$/.test(String(after.sign_total)) ? '，累计签到 ' + after.sign_total + ' 天' : ''}`); return; }
          }
          fail('签到未生效，不能确认成功');
        });
        status = 'success';
      }
    }
    summary.success++;
    if (status === 'already-complete') summary.alreadyComplete++;
  } catch (err) {
    // 只展示脚本自有固定错误；不输出底层异常或服务端 message。
    const safe = /^(Cookie |游戏参数|签到|会话|缺少活动|需要绑定|角色资料|角色绑定|请求|网络|HTTP |响应|续期)/.test(err.message || '') ? err.message : '账号执行失败（详细异常已隐藏）';
    log(`❌ 账号 ${index}：${safe}`);
    summary.failed++;
    if (!counts.failed) { counts.total++; counts.failed++; }
  }
  for (const k of Object.keys(counts)) summary.tasks[k] += counts[k];
  summary.results.push({ account: index, status, ...counts, durationMs: Date.now() - start });
  log(`账号 ${index} 统计：总任务 ${counts.total}，成功 ${counts.success}，已完成 ${counts.alreadyComplete}，跳过 ${counts.skipped}，失败 ${counts.failed}，耗时 ${Date.now() - start}ms`);
}
function notifySelected() {
  const sw = (E.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0', 'false', 'no', 'off'].includes(sw)) return false;
  if (['1', 'true', 'yes', 'on'].includes(sw)) return true;
  if (E.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const names = ['17218a3f4a2a30a6', 'qc_sign.js', 'candidate.js', 'scripts/qc_sign.js', path.basename(__filename)];
  return E.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(pattern => {
    const regex = new RegExp('^' + pattern.split('*').map(p => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
    return names.some(n => regex.test(n));
  });
}
function childNotify(command, args, body) {
  return new Promise(resolve => {
    let child; let done = false;
    const finish = ok => { if (!done) { done = true; clearTimeout(timer); resolve(ok); } };
    const timer = setTimeout(() => { if (child) child.kill('SIGKILL'); finish(false); }, 20000);
    try {
      child = spawn(command, args, { stdio: ['pipe', 'ignore', 'ignore'], env: { PATH: E.PATH, HOME: E.HOME, ...Object.fromEntries(Object.entries(E).filter(([k]) => !/^QC_|^qc_/.test(k))) } });
      child.on('error', () => finish(false)); child.on('exit', code => finish(code === 0));
      child.stdin.on('error', () => {}); child.stdin.end(JSON.stringify({ title: TITLE, body }));
    } catch (_) { finish(false); }
  });
}
async function notify() {
  if (!notifySelected()) return 'disabled';
  if (DRY) { log(`通知预览：${TITLE}；账号 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；状态 ${summary.status}（离线不加载通知模块）`); return 'dry-run-preview'; }
  const body = `状态：${summary.status}；账号总数：${summary.accounts}；成功：${summary.success}；失败：${summary.failed}；子任务失败：${summary.tasks.failed}。请查看脱敏任务日志。`;
  const dirs = [E.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  for (const dir of dirs) {
    const js = path.join(dir, 'sendNotify.js');
    if (fs.existsSync(js) && await childNotify(process.execPath, ['-e', 'const fs=require("fs");const m=JSON.parse(fs.readFileSync(0,"utf8"));Promise.resolve().then(()=>require(process.argv[1]).sendNotify(m.title,m.body)).catch(()=>process.exitCode=1);', js], body)) return 'sent';
  }
  const py = 'import sys,json,importlib.util\nm=json.load(sys.stdin)\np=sys.argv[1]\nif p:\n s=importlib.util.spec_from_file_location("notify",p);n=importlib.util.module_from_spec(s);s.loader.exec_module(n)\nelse:\n import notify as n\nn.send(m["title"],m["body"])';
  for (const file of ['', ...dirs.map(dir => path.join(dir, 'notify.py')).filter(f => fs.existsSync(f))]) {
    if (await childNotify('python3', ['-c', py, file], body)) return 'sent';
  }
  log('⚠️ 青龙通知不可用或发送失败，保留业务退出码'); return 'unavailable-or-failed';
}
(async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${summary.mode}`);
  const lines = (E.QC_ACCOUNTS || E.qc_ck || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  summary.accounts = lines.length;
  log(`账号数量：${lines.length}`);
  try {
    if (!lines.length) fail('缺少 QC_ACCOUNTS，请从微信活动页获取会话');
    loadState();
    for (let i = 0; i < lines.length; i++) await runAccount(lines[i], i + 1);
    summary.status = summary.failed ? (summary.success ? 'partial-failure' : 'failure') : (DRY ? 'dry-run' : 'success');
  } catch (_) { summary.status = 'configuration-error'; log('❌ 配置错误：请检查 QC_ACCOUNTS、游戏参数及会话缓存权限；未输出配置值'); }
  const exitCode = summary.failed || summary.status === 'configuration-error' ? 1 : 0;
  try { summary.notification = await notify(); } catch (_) { summary.notification = 'failed'; log('⚠️ 通知失败，保留业务退出码'); }
  summary.durationMs = Date.now() - started; summary.finishedAt = new Date().toISOString();
  console.log('----------------------------------------');
  log(`任务统计：账号 ${summary.accounts}，成功 ${summary.success}，已签到 ${summary.alreadyComplete}，失败 ${summary.failed}；子任务 ${JSON.stringify(summary.tasks)}`);
  log(`总耗时 ${summary.durationMs}ms；完成时间 ${summary.finishedAt}；通知 ${summary.notification}；最终状态 ${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
})();
