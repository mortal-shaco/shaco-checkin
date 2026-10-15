// name: 蜜雪冰城每日签到
// cron: 22 1 * * *
/**
 * name: 蜜雪冰城每日签到
 * cron: 28 10 * * *
 * 蜜雪冰城小程序；原作者 Telegram@sudojia，https://blog.imzjw.cn
 * 来源 sudojia/AutoTaskScript，2024/07/27；保留 GPL-3.0 许可。
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * Node.js >= 18，无第三方业务依赖。
 * MXBC_TOKEN：在本人小程序登录后抓取 mxsa.mxbc.net 请求头 Access-Token，
 * 每个非空行一个账号；不支持 & 或 @ 分隔账号，不输出抓包内容。
 * MXBC_SIGNING_KEY：应用 RSA 签名私钥（非账号 Token），必须自行确认授权。
 * 原上游源码 privateKeyStr 是签名材料的来源；本版不再内置私钥。
 * 将授权的 PEM 完整文本（含 BEGIN/END 和换行）放入此环境变量，
 * 也可将完整 PEM 编码为 Base64 后填入。不要填写请求中的 sign 值。
 * MXBC_DRY_RUN=1：完全离线，模拟三个步骤，不读取私钥、不发送签到或通知。
 * QINGLONG_NOTIFY=0/false/no/off：关闭通知；默认开启。
 * QINGLONG_NOTIFY_DIR：可选，青龙 sendNotify.js 或 notify.py 所在目录。
 * 业务仅执行账号验证、每日签到、积分查询，不兑换、不改资料、不发布文字。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '蜜雪冰城每日签到';
const APP_ID = 'd82be6bbc1da11eb9dd000163e122ecb';
const BASE = 'https://mxsa.mxbc.net';
const TIMEOUT = 15000;
const MAX_BYTES = 262144;
const dryRun = process.env.MXBC_DRY_RUN === '1';
const started = Date.now();
const results = [];
let key;
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${stamp()}] ${text}`);
const seconds = ms => (ms / 1000).toFixed(2);
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const validNumber = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
class TaskError extends Error {}
function accountLines() {
  return (process.env.MXBC_TOKEN || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
}
function loadKey() {
  let pem = process.env.MXBC_SIGNING_KEY;
  if (!pem) throw new TaskError('缺少 MXBC_SIGNING_KEY；请配置授权的应用 RSA 签名私钥');
  if (!pem.includes('-----BEGIN')) pem = Buffer.from(pem.trim(), 'base64').toString('utf8');
  try {
    const parsed = crypto.createPrivateKey(pem);
    if (parsed.asymmetricKeyType !== 'rsa') throw new Error();
    return parsed;
  } catch { throw new TaskError('MXBC_SIGNING_KEY 格式错误；需要 RSA 私钥 PEM 或完整 PEM 的 Base64'); }
}
function signedUrl(endpoint) {
  const t = Date.now().toString();
  const content = `appId=${APP_ID}&t=${t}`;
  const sign = crypto.sign('RSA-SHA256', Buffer.from(content), key).toString('base64url');
  return `${BASE}${endpoint}?${content}&sign=${sign}`;
}
function request(endpoint, token) {
  if (dryRun) throw new TaskError('离线模式禁止网络请求');
  return new Promise((resolve, reject) => {
    let settled = false;
    let req;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(value);
    };
    const timer = setTimeout(() => {
      finish(new TaskError('请求超过 15 秒，结果未确认；请在小程序核对后再运行'));
      if (req) req.destroy();
    }, TIMEOUT);
    try {
      req = https.get(signedUrl(endpoint), { headers: {
        Host: 'mxsa.mxbc.net', app: 'mxbc', appchannel: 'xiaomi',
        'User-Agent': 'Mozilla/5.0 MicroMessenger/8.0.50',
        'Content-Type': 'application/json', Accept: '*/*',
        'Accept-Encoding': 'identity',
        Referer: 'https://servicewechat.com/wx7696c66d2245d107/123/page-frame.html',
        'Access-Token': token
      } }, res => {
        if (res.statusCode !== 200) {
          finish(new TaskError(`HTTP 状态 ${Number(res.statusCode) || 0}，请求未确认`));
          res.destroy(); return;
        }
        const chunks = []; let bytes = 0;
        res.on('data', chunk => {
          bytes += chunk.length;
          if (bytes > MAX_BYTES) {
            finish(new TaskError('响应超过大小限制')); res.destroy();
          } else chunks.push(chunk);
        });
        res.on('error', () => finish(new TaskError('读取响应失败')));
        res.on('aborted', () => finish(new TaskError('响应中断')));
        res.on('end', () => {
          if (settled) return;
          let data;
          try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
          catch { finish(new TaskError('响应不是有效 JSON')); return; }
          if (!isObject(data) || data.code !== 0 || !isObject(data.data)) {
            finish(new TaskError('业务未返回 code=0 和有效数据；请检查登录或接口变化')); return;
          }
          finish(null, data.data);
        });
      });
      req.on('error', () => finish(new TaskError('网络或请求失败，结果未确认')));
    } catch { finish(new TaskError('无法构造请求，请检查凭据格式与签名配置')); }
  });
}
function identity(data, token) {
  for (const field of ['nickname', 'nickName', 'username', 'displayName', 'uid']) {
    const value = data[field];
    if ((typeof value === 'string' || typeof value === 'number') && String(value).length) {
      const text = String(value);
      // 身份按官方值显示；疑似手机号、Token、控制字符不进入日志。
      if (text.includes(token) || /(?:\+?86[- ]?)?1[3-9]\d{9}/.test(text) || /[\r\n\x00-\x1f\x7f]/.test(text)) continue;
      return text;
    }
  }
  return null;
}
async function stage(result, n, name, action) {
  const start = Date.now();
  log(`账号 ${result.account} · 阶段 ${n}/3 ${name} 开始`);
  try {
    const detail = await action();
    result.tasks.success++;
    log(`✅ ${name}：${detail}；耗时 ${seconds(Date.now() - start)} 秒`);
    return true;
  } catch (error) {
    result.tasks.failed++;
    log(`❌ ${name}：${error instanceof TaskError ? error.message : '内部处理失败（已隐藏详细异常）'}；耗时 ${seconds(Date.now() - start)} 秒`);
    return false;
  }
}
async function runAccount(token, account) {
  const start = Date.now();
  const result = { account, status: 'failed', tasks: { total: 3, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 }, durationMs: 0 };
  log(`------ 账号 ${account} ------`);
  const login = await stage(result, 1, '验证账号', async () => {
    if (!token || /[\s&@\x00-\x1f\x7f]/.test(token)) throw new TaskError('Token 格式错误；每行一个完整 Access-Token，不使用 & 或 @ 分隔账号');
    if (dryRun) return '离线模拟账号验证成功';
    const data = await request('/api/v1/customer/info', token);
    const name = identity(data, token);
    return name ? `登录验证成功，用户：${name}` : '登录验证成功（接口未返回可显示的公开身份）';
  });
  if (login) {
    if (!dryRun) await new Promise(resolve => setTimeout(resolve, 1200));
    await stage(result, 2, '每日签到', async () => {
      if (dryRun) return '离线模拟签到成功，未发送签到请求';
      const data = await request('/api/v1/customer/signin', token);
      if (!validNumber(data.ruleValuePoint) || !validNumber(data.ruleValueGrowth)) throw new TaskError('签到返回数据不完整，无法验证成功；请在小程序核对');
      return `签到成功，雪王币+${data.ruleValuePoint}，已连续签到${data.ruleValueGrowth}天`;
    });
    if (!dryRun) await new Promise(resolve => setTimeout(resolve, 1200));
    await stage(result, 3, '查询雪王币', async () => {
      if (dryRun) return '离线模拟积分查询成功';
      const data = await request('/api/v1/customer/info', token);
      if (!validNumber(data.customerPoint)) throw new TaskError('积分字段缺失或格式异常，无法验证查询成功');
      return `当前雪王币：${data.customerPoint}`;
    });
  } else {
    result.tasks.skipped = 2;
    log('⏭️ 阶段 2/3 每日签到、阶段 3/3 查询雪王币：账号验证失败，跳过；耗时 0.00 秒');
  }
  result.status = result.tasks.failed === 0 ? 'success' : 'failed';
  result.durationMs = Date.now() - start;
  results.push(result);
  log(`账号 ${account} 统计：总任务 3，成功 ${result.tasks.success}，已完成 0，跳过 ${result.tasks.skipped}，失败 ${result.tasks.failed}；耗时 ${seconds(result.durationMs)} 秒`);
}
// 通知模块在独立子进程运行，屏蔽第三方模块 stdout/stderr，不泄漏配置或原始响应。
function notifyChild(executable, args, body) {
  return new Promise(resolve => {
    let child; let settled = false;
    const finish = ok => { if (!settled) { settled = true; clearTimeout(timer); resolve(ok); } };
    const timer = setTimeout(() => { if (child) child.kill('SIGKILL'); finish(false); }, 20000);
    try {
      child = spawn(executable, args, { stdio: ['pipe', 'ignore', 'ignore'] });
      child.on('error', () => finish(false));
      child.on('close', code => finish(code === 0));
      child.stdin.on('error', () => finish(false));
      child.stdin.end(JSON.stringify({ title: TITLE, body }));
    } catch { finish(false); }
  });
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dryRun) { log(`离线通知预演：${body}`); return '离线预演（为保证断网，未调用通知通道）'; }
  const dirs = [process.env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  for (const dir of dirs) {
    const js = path.join(dir, 'sendNotify.js');
    if (fs.existsSync(js)) {
      const code = "let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',async()=>{try{const p=JSON.parse(s);const n=require(process.argv[1]);await n.sendNotify(p.title,p.body);process.exit(0)}catch{process.exit(1)}})";
      if (await notifyChild(process.execPath, ['-e', code, path.resolve(js)], body)) return '已发送';
    }
  }
  const pyCode = "import sys,json,importlib.util\np=json.load(sys.stdin)\nif len(sys.argv)>1:\n s=importlib.util.spec_from_file_location('notify',sys.argv[1]);n=importlib.util.module_from_spec(s);s.loader.exec_module(n)\nelse:\n import notify as n\nn.send(p['title'],p['body'])";
  for (const dir of dirs) {
    const py = path.join(dir, 'notify.py');
    if (fs.existsSync(py) && await notifyChild('python3', ['-c', pyCode, py], body)) return '已发送';
  }
  if (await notifyChild('python3', ['-c', pyCode], body)) return '已发送';
  return '不可用或发送失败（业务退出码保持不变）';
}
async function main() {
  log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dryRun ? '离线预演' : '正式运行'}`);
  const accounts = accountLines();
  log(`账号总数：${accounts.length}`);
  let configurationError = false;
  try {
    if (!accounts.length) throw new TaskError('缺少 MXBC_TOKEN；请每行配置一个账号的 Access-Token');
    if (!dryRun) key = loadKey();
    for (let i = 0; i < accounts.length; i++) await runAccount(accounts[i], i + 1);
  } catch (error) {
    configurationError = true;
    log(`❌ 配置或任务错误：${error instanceof TaskError ? error.message : '内部处理异常（详情已隐藏）'}`);
  }
  const success = results.filter(r => r.status === 'success').length;
  const failed = accounts.length - success;
  const status = configurationError ? 'configuration-error' : failed ? (success ? 'partial-failure' : 'failure') : (dryRun ? 'dry-run' : 'success');
  const exitCode = configurationError || failed ? 1 : 0;
  const tasks = results.reduce((sum, r) => { for (const k of Object.keys(sum)) sum[k] += r.tasks[k]; return sum; }, { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0 });
  const body = `模式：${dryRun ? '离线预演' : '正式运行'}；状态：${status}；账号总数 ${accounts.length}，成功 ${success}，失败 ${failed}；子任务成功 ${tasks.success}，失败 ${tasks.failed}，跳过 ${tasks.skipped}`;
  let notification;
  try { notification = await notify(body); } catch { notification = '通知异常（业务退出码保持不变）'; }
  log('----------------------------------------');
  log(`任务统计：账号总数 ${accounts.length}，成功 ${success}，失败 ${failed}`);
  log(`子任务统计：总数 ${tasks.total}，成功 ${tasks.success}，已完成 ${tasks.alreadyComplete}，跳过 ${tasks.skipped}，失败 ${tasks.failed}`);
  log(`通知状态：${notification}`);
  const finished = new Date().toISOString();
  log(`完成时间：${finished}；总耗时 ${seconds(Date.now() - started)} 秒；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: TITLE, mode: dryRun ? 'dry-run' : 'live', status, accountCount: accounts.length, success, failed, tasks, accounts: results, notification, startedAt: new Date(started).toISOString(), finishedAt: finished, durationMs: Date.now() - started, exitCode }));
  process.exitCode = exitCode;
}
main();
