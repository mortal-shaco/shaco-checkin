// name: 芬享汇每日签到
// cron: 0 8 * * *
// @Time    : 2024-05-12 01:10
// @Author  : Sirius
// 上游：xingly-cn/QLPanelScript，fxh.js，version = 1.0.0
// wx小程序：芬享汇；每天签到积分，可换取5元jd E卡（兑换需自行操作）。
// fxhOpenId：打开芬享汇小程序，用自己的合法抓包工具读取
// scrm.ocheng.me/v2/api/member/info 请求中的 miniProgramOpenId，或签到路径中的 OpenId。
// 每个非空行一个账号，不使用 @ 或 & 分隔。不要提供 Cookie、手机号或整个请求 URL。
// FXH_DRY_RUN=1：完全断网预演；QINGLONG_NOTIFY=0：关闭通知。
// Node.js >= 16，无第三方业务依赖；通知可使用青龙 sendNotify.js 或 notify.py。
/*
MIT License (上游许可由任务元数据声明；保留上游作者署名)
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
const https = require('https');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const title = '芬享汇每日签到';
const started = Date.now();
const dry = process.env.FXH_DRY_RUN === '1';
const headers = {
  'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 16_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.48(0x18003030) NetType/WIFI Language/zh_CN miniProgram/',
  'X-Channel-Type': '1', 'X-Channel': '40'
};
function log(message) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${message}`); }
function request(url, method) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    let settled = false;
    let req;
    const timer = setTimeout(() => { finish(new Error('请求超时')); if (req) req.destroy(); }, 15000);
    function finish(error, value) {
      if (settled) return;
      settled = true; clearTimeout(timer);
      if (error) reject(error); else resolve(value);
    }
    const body = method === 'POST' ? '{}' : null;
    req = https.request(url, { method, headers: { ...headers, ...(body ? {
      'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body)
    } : {}) } }, res => {
      const chunks = []; let bytes = 0;
      res.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > 262144) { finish(new Error('响应超过大小限制')); res.destroy(); }
        else chunks.push(chunk);
      });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应中断')));
      res.on('end', () => {
        const status = res.statusCode;
        if (status !== 200 && !(method === 'POST' && status === 400)) {
          finish(new Error(`HTTP ${status}，未验证业务成功`)); return;
        }
        try { finish(null, { status, data: JSON.parse(Buffer.concat(chunks).toString('utf8')) }); }
        catch { finish(new Error('响应不是有效 JSON')); }
      });
    });
    req.on('error', () => finish(new Error('网络请求失败')));
    if (body) req.write(body);
    req.end();
  });
}
// 只展示官方非敏感身份；拒绝控制字符、凭据片段及手机号，绝不输出原始响应。
function identity(member, secret) {
  for (const key of ['nickname', 'nickName', 'username', 'displayName', 'publicUid']) {
    const value = member && member[key];
    if ((typeof value === 'string' || typeof value === 'number') && String(value) &&
        !/[\r\n\x00-\x1f\x7f]/.test(String(value)) && !String(value).includes(secret) &&
        !/(?:token|cookie|session|1\d{10})/i.test(String(value))) log(`官方身份：${value}`);
  }
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) return '预演模拟发送（断网）';
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  let file, python = false;
  for (const dir of dirs) {
    for (const name of ['sendNotify.js', 'notify.py']) {
      const candidate = path.resolve(dir, name);
      if (fs.existsSync(candidate)) { file = candidate; python = name === 'notify.py'; break; }
    }
    if (file) break;
  }
  if (!file) return '不可用：未找到青龙通知模块';
  // 子进程隔离通知模块输出，避免模块报错输出凭据；通知失败不改业务退出码。
  return new Promise(resolve => {
    const js = "console.log=console.error=console.warn=()=>{}; Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1));";
    const py = 'import importlib.util,sys\ns=importlib.util.spec_from_file_location("notify",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[2],sys.argv[3])';
    let child;
    try { child = spawn(python ? 'python3' : process.execPath, [python ? '-c' : '-e', python ? py : js, file, title, body], { stdio: 'ignore' }); }
    catch { resolve('发送失败'); return; }
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('发送超时'); }, 20000);
    child.on('error', () => { clearTimeout(timer); resolve('发送失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '发送失败'); });
  });
}
async function main() {
  const accounts = (process.env.fxhOpenId || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean);
  const results = [];
  log(`========== ${title} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '实际执行'}；账号数：${accounts.length}`);
  let configError = accounts.length === 0;
  if (configError) log('❌ 配置错误：请配置 fxhOpenId，每行一个账号');
  for (let i = 0; i < accounts.length; i++) {
    const secret = accounts[i];
    const accountStart = Date.now();
    const stats = { account: i + 1, total: 2, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
    log(`账号 ${i + 1} 开始`);
    let stage = 1;
    let stageStart = Date.now();
    try {
      if (!/^[A-Za-z0-9_-]+$/.test(secret)) throw new Error('账号参数格式错误：只接受单个 OpenId，每行一个账号');
      log('阶段 1/2：查询当前积分');
      const info = dry ? { status: 200, data: { success: true, data: { memberMultiBrandDO: { memberPoints: 0, nickname: '预演账号' } } } } :
        await request(`https://scrm.ocheng.me/v2/api/member/info?miniProgramOpenId=${encodeURIComponent(secret)}`, 'GET');
      const member = info.data && info.data.data && info.data.data.memberMultiBrandDO;
      const points = member && member.memberPoints;
      if (info.status !== 200 || info.data.success !== true || !member ||
          !['string', 'number'].includes(typeof points) || !/^\d+(?:\.\d+)?$/.test(String(points)))
        throw new Error('积分查询业务失败或响应契约不匹配');
      identity(member, secret);
      log(`✅ 当前积分：${points}；阶段 1 耗时 ${Date.now() - stageStart}ms${dry ? '（模拟）' : ''}`);
      stats.success++;
      stage = 2; stageStart = Date.now();
      log('阶段 2/2：每日签到（会改变签到状态并发放积分）');
      const attendance = dry ? { status: 200, data: { success: true, data: { awardInfo: 1 } } } :
        await request(`https://scrm.ocheng.me/v2/api/marketing/attendance/68/${encodeURIComponent(secret)}?openIdType=2`, 'POST');
      const data = attendance.data;
      if (data && data.code === 0x2693d) {
        stats.alreadyComplete++; log(`☑️ 今日已签到！；阶段 2 耗时 ${Date.now() - stageStart}ms`);
      } else if (attendance.status === 200 && data && data.success === true) {
        stats.success++; log(`✅ 签到成功！；阶段 2 耗时 ${Date.now() - stageStart}ms${dry ? '（模拟）' : ''}`);
        const award = data.data && data.data.awardInfo;
        if (['number', 'string'].includes(typeof award) && /^\d+(?:\.\d+)?$/.test(String(award))) log(`获得${award}积分`);
      } else throw new Error('签到业务失败：未返回明确成功或已签到代码');
    } catch (error) {
      // 本文件仅抛出固定脱敏错误，不将网络异常或业务响应拼入日志。
      stats.failed++; stats.skipped = stage === 1 ? 1 : 0;
      log(`❌ 阶段 ${stage}：${['账号参数格式错误：只接受单个 OpenId，每行一个账号', '积分查询业务失败或响应契约不匹配', '签到业务失败：未返回明确成功或已签到代码', '请求超时', '响应超过大小限制', '响应读取失败', '响应中断', '响应不是有效 JSON', '网络请求失败'].includes(error.message) || /^HTTP \d{3}，未验证业务成功$/.test(error.message) ? error.message : '请求或内部处理失败'}；耗时 ${Date.now() - stageStart}ms`);
      if (stats.skipped) log('⏭️ 阶段 2/2：积分查询未通过，跳过签到');
    }
    stats.durationMs = Date.now() - accountStart;
    stats.status = stats.failed ? 'failure' : (dry ? 'dry-run' : 'success');
    results.push(stats);
    log(`账号 ${i + 1}：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}；耗时 ${stats.durationMs}ms`);
  }
  const failed = results.filter(r => r.failed).length;
  const successful = results.length - failed;
  const status = configError ? 'configuration-error' : failed ? (successful ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  process.exitCode = configError || failed ? 1 : 0;
  const subTasks = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 };
  for (const r of results) for (const k of Object.keys(subTasks)) subTasks[k] += r[k];
  const notification = await notify(`模式：${dry ? '断网预演' : '实际执行'}；账号总数 ${accounts.length}，成功 ${successful}，失败 ${failed}；状态 ${status}；子任务成功 ${subTasks.success}，已完成 ${subTasks.alreadyComplete}，跳过 ${subTasks.skipped}，失败 ${subTasks.failed}`).catch(() => '发送失败');
  log('----------------------------------------');
  log(`账号总数 ${accounts.length}；成功 ${successful}；失败 ${failed}；子任务 ${JSON.stringify(subTasks)}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now() - started}ms；通知：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: title, mode: dry ? 'dry-run' : 'live', status, accounts: accounts.length, successful, failed, subTasks, results, notification, durationMs: Date.now() - started, exitCode: process.exitCode }));
}
main().catch(() => { process.exitCode = 1; log('❌ 内部执行异常，未验证业务成功'); });
