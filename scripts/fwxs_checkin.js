// name: 废文网签到
// cron: 5 8 * * *
/*
 * name: 废文网签到
 * cron: 5 8 * * *
 * 废文网(SosadFun) 自动签到脚本；来源 zhui-zi/fwcheckin / fwxs_checkin.js
 * 上游版本 7793a795d603df34f0ebdbc7d6810427f84f59c6，许可证 MIT。
 * 兼容青龙、Node.js >=18、GitHub Actions，无 npm 依赖。
 * fwxs：浏览器登录 https://xn--pxtr7m.net 后，在开发者工具 Network 中
 * 查看本站已登录请求的 Request Headers，复制完整 Cookie 值（不含 Cookie:）。
 * 每个非空行一个账号，禁止用 @ 或 & 分隔账号。兼容 Cookie#昵称备注；
 * 仅在首个 # 处分割，备注保留但不输出，官方公开 UID 用于核对账号。
 * FWXS_DRY_RUN=1：完全断网预演，包括通知；QINGLONG_NOTIFY=0：关闭通知。
 * 签到接口沿用 GET /qiandao，通过个人中心总签到天数增长核验签到。
 * 原脚本未声明 cron；默认北京时间每日 08:05，请将调度器设为 Asia/Shanghai。
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
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const BASE = 'https://xn--pxtr7m.net';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
const dry = process.env.FWXS_DRY_RUN === '1';
const started = Date.now();
const clock = () => new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
const log = s => console.log(`[${clock()}] ${s}`);
function stripTags(s) {
  return s.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
}
function parseState(html) {
  const t = stripTags(html);
  const number = re => { const m = t.match(re); return m ? Number(m[1]) : null; };
  const m = t.match(/最新签到\s*[：:]\s*(.*?)(?=连续|补签|盐度|总签到|答题|注册|$)/);
  return { total: number(/总签到\s*[：:]\s*(\d+)/), cont: number(/连续签到\s*[：:]\s*(\d+)/), latest: m ? m[1].trim() : '' };
}
function todayVerified(latest, now = new Date()) {
  const shifted = new Date(now.getTime() + 8 * 3600000);
  const today = shifted.toISOString().slice(0, 10);
  const date = latest.match(/^(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})(?:日|\b)/);
  if (date) return `${date[1]}-${date[2].padStart(2, '0')}-${date[3].padStart(2, '0')}` === today;
  // 相对时间有舍入误差，按完整时间区间的上界判断，跨午夜不误报。
  const relative = latest.match(/^(\d+)\s*(秒|分钟|分|小时|seconds?|minutes?|hours?)\s*(?:前|ago)$/i);
  if (!relative) return false;
  const unit = /秒|second/i.test(relative[2]) ? 1 : /小时|hour/i.test(relative[2]) ? 3600 : 60;
  const elapsed = shifted.getUTCHours() * 3600 + shifted.getUTCMinutes() * 60 + shifted.getUTCSeconds();
  return (Number(relative[1]) + 1) * unit <= elapsed;
}
async function reqText(route, cookie, checkin = false) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const resp = await fetch(BASE + route, { method: 'GET', headers: { Cookie: cookie, 'User-Agent': UA, Accept: 'text/html' }, redirect: 'manual', signal: controller.signal });
    if (!(resp.status >= 200 && resp.status < 300) && !(checkin && [301, 302, 303].includes(resp.status))) throw new Error(`HTTP ${resp.status}`);
    if (checkin && resp.status >= 300) {
      const target = new URL(resp.headers.get('location') || '/', BASE);
      if (target.origin !== BASE || /login|signin/i.test(target.pathname)) throw new Error('签到跳转异常');
    }
    let size = 0;
    const chunks = [];
    for await (const chunk of resp.body || []) {
      size += chunk.length;
      if (size > 1024 * 1024) { controller.abort(); throw new Error('响应过大'); }
      chunks.push(Buffer.from(chunk));
    }
    return Buffer.concat(chunks).toString('utf8');
  } catch (e) {
    if (/^(HTTP \d{3}|签到跳转异常|响应过大)$/.test(e.message)) throw e;
    throw new Error(controller.signal.aborted ? '请求超时或响应超限' : '网络请求失败');
  } finally { clearTimeout(timer); }
}
async function notify(body) {
  if (['0', 'false', 'no', 'off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  if (dry) return '断网预演：通知已模拟';
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts', __dirname].filter(Boolean);
  const file = dirs.map(dir => path.resolve(dir, 'sendNotify.js')).find(p => fs.existsSync(p));
  if (!file) return '通知不可用：未找到 sendNotify.js';
  // 独立子进程限制通知耗时，并抑制通知库可能输出的凭据或原始响应。
  return await new Promise(resolve => {
    const env = { ...process.env }; delete env.fwxs;
    const child = spawn(process.execPath, ['-e', 'const fs=require("node:fs"); const p=JSON.parse(fs.readFileSync(0,"utf8")); Promise.resolve().then(()=>require(p.file).sendNotify(p.title,p.body)).catch(()=>{process.exitCode=1});'], { env, stdio: ['pipe', 'ignore', 'ignore'] });
    let settled = false;
    const finish = value => { if (!settled) { settled = true; clearTimeout(timer); resolve(value); } };
    const timer = setTimeout(() => { child.kill('SIGKILL'); finish('通知超时'); }, 20000);
    child.on('error', () => finish('通知失败'));
    child.on('close', code => finish(code === 0 ? '通知已发送' : '通知失败'));
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify({ file, title: '废文网签到', body }));
  });
}
async function main() {
  log('========== 废文网签到 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式执行'}`);
  const accounts = (process.env.fwxs || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  log(`账号总数：${accounts.length}`);
  const results = [];
  for (let i = 0; i < accounts.length; i++) {
    const begun = Date.now();
    const item = { account: i + 1, status: 'failure', tasks: { total: 1, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 } };
    const stage = async (n, name, fn) => {
      const t = Date.now(); log(`账号${i + 1} 阶段${n}：${name}`);
      try { const value = await fn(); log(`账号${i + 1} 阶段${n}完成，耗时${Date.now() - t}毫秒`); return value; }
      catch (e) { log(`账号${i + 1} 阶段${n}失败：${e.message}，耗时${Date.now() - t}毫秒`); throw e; }
    };
    try {
      const delimiter = accounts[i].indexOf('#');
      const cookie = (delimiter < 0 ? accounts[i] : accounts[i].slice(0, delimiter)).trim();
      if (!cookie || /[\r\n\x00-\x1f\x7f]/.test(cookie) || !cookie.includes('=')) throw new Error('Cookie 配置格式错误');
      if (dry) {
        await stage(1, '参数检查', async () => {});
        await stage(2, '模拟登录及状态查询', async () => {});
        await stage(3, '模拟签到及结果核验（不发送请求）', async () => {});
        item.status = 'dry-run'; item.tasks.skipped = 1;
        log(`账号${i + 1} DRY_RUN_OK：参数解析通过，未访问网络`);
      } else {
        const uid = await stage(1, '验证登录', async () => {
          const home = await reqText('/', cookie);
          const m = home.match(/\/users\/(\d+)\/usercenter/);
          if (!m) throw new Error('未确认登录，请更新 Cookie');
          return m[1];
        });
        item.uid = uid; log(`账号${i + 1} 官方公开 UID：${uid}`);
        const route = `/users/${uid}/usercenter`;
        const before = await stage(2, '查询签到状态', async () => {
          const s = parseState(await reqText(route, cookie));
          if (s.total === null) throw new Error('个人中心签到字段缺失');
          log(`账号${i + 1} 总签到${s.total}天；连续签到${s.cont === null ? '未知' : s.cont}天`);
          return s;
        });
        if (todayVerified(before.latest)) { item.status = 'already-complete'; item.tasks.alreadyComplete = 1; }
        else {
          await stage(3, '执行签到', () => reqText('/qiandao', cookie, true));
          await stage(4, '核验签到结果', async () => {
            const after = parseState(await reqText(route, cookie));
            if (after.total !== null && after.total > before.total) { item.status = 'success'; item.tasks.success = 1; }
            else if (after.total === before.total && todayVerified(after.latest)) { item.status = 'already-complete'; item.tasks.alreadyComplete = 1; }
            else throw new Error('未确认签到成功：状态未增长且未确认今日签到');
            log(`账号${i + 1} 总签到${after.total}天；连续签到${after.cont === null ? '未知' : after.cont}天`);
          });
        }
        log(`账号${i + 1} ${item.status === 'success' ? '✅ 签到成功' : '☑️ 今日已签到'}`);
      }
    } catch (e) { item.tasks.failure = 1; log(`账号${i + 1} ❌ ${e.message}`); }
    item.durationMs = Date.now() - begun;
    log(`账号${i + 1}统计：总任务1，成功${item.tasks.success}，已完成${item.tasks.alreadyComplete}，跳过${item.tasks.skipped}，失败${item.tasks.failure}，耗时${item.durationMs}毫秒`);
    results.push(item);
  }
  const failed = results.filter(r => r.status === 'failure').length;
  const succeeded = results.filter(r => ['success', 'already-complete'].includes(r.status)).length;
  const status = !accounts.length ? 'configuration-error' : failed ? (failed === accounts.length ? 'failure' : 'partial-failure') : dry ? 'dry-run' : 'success';
  if (!accounts.length) log('❌ 配置错误：缺少必填变量 fwxs');
  const summary = { task: '废文网签到', mode: dry ? 'dry-run' : 'live', status, accounts: accounts.length, success: succeeded, failure: failed, dryRun: results.filter(r => r.status === 'dry-run').length, results };
  summary.notification = await notify(`状态：${status}；账号总数：${accounts.length}；成功：${succeeded}；失败：${failed}；预演：${summary.dryRun}`);
  summary.durationMs = Date.now() - started;
  log('----------------------------------------');
  log(`账号统计：总数${accounts.length}，成功${succeeded}，失败${failed}，预演${summary.dryRun}`);
  const totals = results.reduce((a, r) => { for (const key of Object.keys(a)) a[key] += r.tasks[key]; return a; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 });
  log(`子任务统计：总数${totals.total}，成功${totals.success}，已完成${totals.alreadyComplete}，跳过${totals.skipped}，失败${totals.failure}`);
  log(`总耗时：${summary.durationMs}毫秒；完成时间：${new Date().toISOString()}；通知状态：${summary.notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = !accounts.length || failed ? 1 : 0;
}
main();
