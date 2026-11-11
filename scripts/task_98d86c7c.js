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
// 原脚本未声明 cron，这里采用每天 08:00，可在青龙调整。

const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');

const TITLE = '百度贴吧关注吧签到';
const CATALOG_ID = '98d86c7c8da22e52';
const enabled = value => /^(1|true|yes|on)$/i.test(value || '');
const dryRun = enabled(process.env.TIEBA_DRY_RUN);
const started = Date.now();
const secrets = [];
let stageNumber = 0;

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
function requestJson(route, bduss, form) {
  if (dryRun) throw failure('断网演练禁止 HTTP 请求');
  return new Promise((resolve, reject) => {
    const body = form ? new URLSearchParams(form).toString() : null;
    const headers = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
      Cookie: `BDUSS=${bduss}`,
      Accept: 'application/json',
    };
    if (body) {
      headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
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
      hostname: 'tieba.baidu.com', path: route, method: body ? 'POST' : 'GET', headers,
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
  const name = user.user_name || user.username || user.name || user.nickname || response.user_name;
  const uid = user.user_id || user.uid;
  if (typeof name === 'string' && name.trim()) log(`官方账号身份 ${name}`);
  if (typeof uid === 'number' || typeof uid === 'string') log(`官方公开 UID ${uid}`);
}

async function runAccount(account, credential) {
  const accountStarted = Date.now();
  log(`账号 ${account.index} 开始`);
  try {
    await stage(account, '凭据检查', async () => {
      if (!/^[A-Za-z0-9._~+/=-]+$/.test(credential)) {
        throw failure('BDUSS 格式错误，请填写单独的字段值并用换行分隔账号');
      }
      return { message: '凭据格式通过' };
    });
    if (dryRun) {
      await stage(account, '断网演练', async () => ({ message: 'DRY_RUN_OK 流程计划为登录校验、关注吧读取、逐吧签到及验证码停止，实际请求 0 次' }));
      account.status = 'dry-run';
      return;
    }
    const { tbs } = await stage(account, '获取登录校验值', async () => {
      const data = await requestJson('/dc/common/tbs', credential);
      if (typeof data.tbs === 'string') secrets.push(data.tbs);
      if (String(data.is_login) !== '1' || typeof data.tbs !== 'string' || !data.tbs.trim()) {
        throw failure('登录校验失败，请重新获取 BDUSS');
      }
      publicIdentity(data);
      return { tbs: data.tbs, message: '已验证登录状态并获取校验值' };
    });
    const { forums } = await stage(account, '读取关注贴吧', async () => {
      const data = await requestJson('/mo/q/newmoindex', credential);
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
          await new Promise(resolve => setTimeout(resolve, 5000));
          const data = await requestJson('/sign/add', credential, { ie: 'utf-8', kw: forum.forum_name, tbs });
          const code = String(data.no);
          if (code === '0') return { message: '签到成功' };
          if (code === '1101') return { outcome: 'alreadyComplete', message: '已经签到过了' };
          if (code === '2150040') {
            const error = failure('需要验证码，停止当前账号后续签到');
            error.captcha = true;
            throw error;
          }
          throw failure(`签到业务失败（状态码 ${/^\d{1,10}$/.test(code) ? code : '缺失或无效'}）`);
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

async function notify(summary) {
  if (!notificationEnabled()) return '已通过通知开关关闭';
  const body = `${TITLE}\n模式 ${summary.mode}\n账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}\n状态 ${summary.status}\n子任务 ${summary.tasks.total}，成功 ${summary.tasks.success}，已完成 ${summary.tasks.alreadyComplete}，跳过 ${summary.tasks.skipped}，失败 ${summary.tasks.failed}`;
  // 演练优先保证完全断网，不调用可能联网的青龙通知器。
  if (dryRun) {
    log(`通知摘要（断网演练仅本地输出） ${body}`);
    return '断网演练已输出通知摘要';
  }
  const directories = [process.env.QINGLONG_NOTIFY_DIR, __dirname, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  const payload = { title: TITLE, body };
  const jsCode = `let input=''; process.stdin.on('data', c=>input+=c); process.stdin.on('end', async()=>{try { const p=JSON.parse(input); const m=require(process.argv[1]); await m.sendNotify(p.title,p.body); } catch { process.exitCode=1; }});`;
  for (const directory of [...new Set(directories)]) {
    const filename = path.join(directory, 'sendNotify.js');
    if (fs.existsSync(filename) && await runNotifier(process.execPath, ['-e', jsCode, filename], payload)) return '青龙通知已发送';
  }
  const pythonCode = `import sys,json\nsys.path[:0]=sys.argv[1:]\nfrom notify import send\np=json.load(sys.stdin)\nsend(p['title'],p['body'])`;
  if (await runNotifier('python3', ['-c', pythonCode, ...directories], payload)) return '青龙通知已发送';
  log('⚠️ 青龙通知不可用或发送失败，保留业务退出码');
  return '通知不可用或发送失败';
}

async function main() {
  const credentials = (process.env.BDUSS || '').split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  secrets.push(...credentials);
  log(`========== ${TITLE} ==========`);
  log(`开始时间 ${new Date(started).toISOString()}，模式 ${dryRun ? '断网演练' : '正式执行'}，账号数 ${credentials.length}`);
  const accounts = [];
  if (!credentials.length) log('❌ 配置错误，必须设置 BDUSS，每个非空行一个账号');
  for (let index = 0; index < credentials.length; index++) {
    const account = { index: index + 1, tasks: stats(), failed: false, status: 'failure' };
    accounts.push(account);
    await runAccount(account, credentials[index]);
  }
  const failed = accounts.filter(account => account.failed).length;
  const tasks = stats();
  for (const account of accounts) {
    for (const key of Object.keys(tasks)) tasks[key] += account.tasks[key];
  }
  const status = !credentials.length ? 'configuration-error' : failed ? (failed === accounts.length ? 'failure' : 'partial-failure') : dryRun ? 'dry-run' : 'success';
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
  summary.exitCode = !credentials.length || failed ? 1 : 0;
  log('----------------------------------------');
  log(`账号总数 ${summary.accounts}，成功 ${summary.success}，演练 ${summary.dryRunAccounts}，失败 ${failed}`);
  log(`子任务 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`总耗时 ${summary.elapsedMs}ms，完成时间 ${summary.finishedAt}，通知状态 ${summary.notification}，最终状态 ${status}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(summary)}`);
  process.exitCode = summary.exitCode;
}

main();
