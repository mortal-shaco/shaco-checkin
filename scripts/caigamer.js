// name: 菜玩社区每日签到
// cron: 0 20 11 * * *
/*
name: 菜玩社区每日签到
cron: 0 20 11 * * *
来源：unitaryhighs/ql_sign_script，sign/caigamer.js
https://github.com/unitaryhighs/ql_sign_script
许可证：MIT

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

参数：CAIGAMER_COOKIE_LIST，每个非空行一个账号，保留完整 Cookie；
登录 https://caigamer.cn 后，在浏览器开发者工具的网络面板中，
读取本站已登录请求的 Cookie 请求头，包含 bbs_sid 和 bbs_token。
CAIGAMER_DRY_RUN=1：完全断网预演，不签到、不向外发送通知。
QINGLONG_NOTIFY 未设置时按上架状态，0/false/no/off 关闭；QINGLONG_NOTIFY_DIR 可指定青龙通知目录。
仅自动签到，无发帖、评论、分享、账号资料修改；不重试状态变更请求。
*/
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["8bd252d858b7095c", "scripts/caigamer.js", "caigamer.js", "caigamer"];
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
const { fork } = require('node:child_process');
const title = '菜玩社区';
const disabled = value => /^(0|false|no|off)$/i.test(value || '');
const dry = /^(1|true|yes|on)$/i.test(process.env.CAIGAMER_DRY_RUN || '');
const cookies = (process.env.CAIGAMER_COOKIE_LIST || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const clock = () => new Date().toTimeString().slice(0, 8);
const log = text => console.log(`[${clock()}] ${text}`);
function redact(value) {
  let text = String(value);
  for (const cookie of cookies) {
    text = text.split(cookie).join('[凭据已隐藏]');
    for (const part of cookie.split(';')) {
      const at = part.indexOf('=');
      const secret = at >= 0 ? part.slice(at + 1).trim() : '';
      if (secret) text = text.split(secret).join('[凭据已隐藏]');
    }
  }
  return text.replace(/(?:cookie|token|session|bbs_sid|bbs_token|device[_-]?id)\s*[:=]\s*\S+/gi, '[敏感字段已隐藏]')
    .replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]').replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, '');
}
function validCookie(cookie) {
  if (/[\r\n\x00-\x1f\x7f]/.test(cookie)) return false;
  const fields = new Map(cookie.split(';').map(part => {
    const at = part.indexOf('=');
    return at < 0 ? ['', ''] : [part.slice(0, at).trim(), part.slice(at + 1).trim()];
  }));
  return Boolean(fields.get('bbs_sid') && fields.get('bbs_token'));
}
function sign(cookie) {
  return new Promise((resolve, reject) => {
    const req = https.request('https://caigamer.cn/my-sign.htm', {
      method: 'POST', headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        Cookie: cookie, Origin: 'https://caigamer.cn', Referer: 'https://caigamer.cn/',
        Accept: 'text/plain, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest', 'Content-Length': '0'
      }
    }, res => {
      let bytes = 0;
      const chunks = [];
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('aborted', () => reject(new Error('响应中断')));
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 65536) req.destroy(new Error('响应超过大小限制'));
        else chunks.push(chunk);
      });
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error(`HTTP 状态异常：${res.statusCode}`));
        try {
          const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error();
          resolve(body);
        } catch { reject(new Error('响应不是有效业务 JSON')); }
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时（15 秒）')), 15000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', error => reject(new Error(error.message === '请求超时（15 秒）' || error.message === '响应超过大小限制' ? error.message : '网络或 TLS 请求失败')));
    req.end();
  });
}
function interpret(body) {
  const message = typeof body.message === 'string' ? body.message.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '').trim() : '';
  // 只有明确的成功码可以证实本次签到；不把任意非登录错误当作成功。
  if (body.code === 0 || body.code === '0') return { status: 'success', message };
  if (/^(?:今天|今日|您今天|您今日)?(?:已经|已)签到(?:了)?[！!。.]?$/.test(message)) return { status: 'alreadyComplete', message: '今日已签到' };
  return { status: 'failure', message: /登录/.test(message) ? '登录状态无效，请重新获取 Cookie' : '业务未确认成功（未输出原始响应）' };
}
function identity(body) {
  const objects = [body, body.data, body.user, body.data && body.data.user].filter(x => x && typeof x === 'object');
  for (const obj of objects) {
    for (const key of ['nickname', 'username', 'display_name', 'displayName', 'uid']) {
      if (typeof obj[key] === 'string' || typeof obj[key] === 'number') log(`官方账号身份：${redact(obj[key])}`);
    }
  }
}
function rewards(message) {
  // 白名单提取名次和奖励，不输出可能包含会话或凭据的任意业务文本。
  const patterns = [/(?:签到排名|签到名次|排名|名次)\s*[:：]?\s*第?\s*\d+\s*名?/g,
    /第\s*\d+\s*(?:位|名)/g, /(?:连续签到|连签)\s*\d+\s*天/g,
    /(?:金币|积分|经验(?:值)?|奖励)\s*[:：]?\s*[+＋]?\s*\d+\s*(?:金币|积分|点|枚)?/g];
  for (const pattern of patterns) for (const value of message.match(pattern) || []) log(`签到详情：${redact(value)}`);
}
async function notification(body) {
  if (disabled(process.env.QINGLONG_NOTIFY)) return '已关闭';
  if (dry) {
    log(`通知预演（断网，不发送）：${body}`);
    return '断网预演';
  }
  return new Promise(resolve => {
    const child = fork(__filename, ['--notification-worker'], { silent: true });
    child.stdout.resume();
    child.stderr.resume();
    let done = false;
    const finish = status => {
      if (done) return;
      done = true; clearTimeout(timer); child.kill(); resolve(status);
    };
    const timer = setTimeout(() => finish('通知超时，保留业务退出码'), 10000);
    child.on('error', () => finish('通知不可用，保留业务退出码'));
    child.on('exit', () => finish('通知不可用，保留业务退出码'));
    child.on('message', status => finish(status === 'sent' ? '已发送' : '通知不可用，保留业务退出码'));
    child.send(body);
  });
}
async function main() {
  const started = Date.now();
  log(`========== ${title} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式签到'}；账号数：${cookies.length}`);
  const counts = { total: cookies.length, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
  const accounts = [];
  if (!cookies.length) log('❌ 配置错误：必须设置 CAIGAMER_COOKIE_LIST');
  for (const [index, cookie] of cookies.entries()) {
    const began = Date.now();
    const result = { account: index + 1, status: 'failure', total: 1, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
    log(`账号 ${index + 1} / 阶段 1：校验 Cookie`);
    log(`账号 ${index + 1} / 阶段 1：校验结束，耗时 ${Date.now() - began}ms`);
    if (!validCookie(cookie)) log('❌ Cookie 格式错误：须含非空 bbs_sid 和 bbs_token');
    else if (dry) {
      log(`账号 ${index + 1} / 阶段 2：DRY_RUN_OK，已校验空请求体 POST；未发起网络请求`);
      result.status = 'skipped';
    } else {
      log(`账号 ${index + 1} / 阶段 2：提交签到（15 秒超时，不自动重试）`);
      try {
        const body = await sign(cookie);
        identity(body);
        const outcome = interpret(body);
        result.status = outcome.status;
        log(`${outcome.status === 'failure' ? '❌ ' + outcome.message : outcome.status === 'alreadyComplete' ? '☑️ 今日已签到' : '✅ 签到成功'}`);
        if (outcome.status === 'success') rewards(outcome.message);
      } catch (error) { log(`❌ ${error.message}`); }
    }
    counts[result.status]++;
    log(`账号 ${index + 1} / 阶段 2：结束，耗时 ${Date.now() - began}ms`);
    result[result.status]++;
    result.durationMs = Date.now() - began;
    accounts.push(result);
    log(`账号 ${index + 1} / 阶段 3：统计；任务总数 1，成功 ${result.success}，已完成 ${result.alreadyComplete}，跳过 ${result.skipped}，失败 ${result.failure}；阶段及账号耗时 ${result.durationMs}ms`);
  }
  const failed = counts.failure > 0 || !cookies.length;
  const status = !cookies.length ? 'configuration-error' : failed ? (counts.success + counts.alreadyComplete > 0 ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  const body = `账号总数 ${counts.total}，成功 ${counts.success + counts.alreadyComplete}，失败 ${counts.failure}，预演跳过 ${counts.skipped}，最终状态 ${status}`;
  const notify = await notification(body);
  log('----------------------------------------');
  log(`任务统计：${body}；子任务成功 ${counts.success}，已完成 ${counts.alreadyComplete}，跳过 ${counts.skipped}，失败 ${counts.failure}`);
  const finishTime = new Date().toISOString();
  log(`完成时间：${finishTime}；总耗时 ${Date.now() - started}ms；通知状态：${notify}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: title, mode: dry ? 'dry-run' : 'live', status, ...counts, accounts, notification: notify, finishTime, durationMs: Date.now() - started }));
  process.exitCode = failed ? 1 : 0;
}
if (process.argv[2] === '--notification-worker') {
  process.once('message', async body => {
    const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
    let sent = false;
    for (const location of locations) {
      if (!fs.existsSync(location)) continue;
      try {
        const helper = require(location);
        if (typeof helper.sendNotify !== 'function') continue;
        await helper.sendNotify(title, body);
        sent = true;
        break;
      } catch { /* 通知错误及辅助库输出不泄漏到主进程。 */ }
    }
    if (process.send) process.send(sent ? 'sent' : 'unavailable');
  });
} else if (require.main === module) main();
module.exports = { interpret, validCookie, redact };
