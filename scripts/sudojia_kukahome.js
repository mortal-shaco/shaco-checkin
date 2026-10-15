// name: 顾家家居签到
// cron: 9 2 * * *
/**
 * name: 顾家家居签到
 * cron: 5 10 * * *
 * SPDX-License-Identifier: GPL-3.0
 * Derived from sudojia/AutoTaskScript src/wx_mini/sudojia_kukahome.js
 * Author: Telegram@sudojia · https://blog.imzjw.cn
 * 上游版本：4a55327baed0321bdf95802a75cc8363cae118b0；遵循 GPL-3.0。
 * Node.js >= 18，仅使用标准库。每天签到并查询昵称、连续签到天数及积分。
 * 顾家会员微信小程序，登录后在本人授权抓包中查看 mc.kukahome.com 请求头。
 * GU_HOME_TOKEN：每行 AccessToken#X-Customer，仅按首个 # 分割，后续内容保留。
 * GU_HOME_APP_SECRET：使用获授权的该应用 appid=667516 签名配置中的 appSecret；
 * 可从合法取得的上游脚本 appSecret 配置确认，不是 AccessToken，勿公开或打印。
 * GU_HOME_DRY_RUN=1：完全断网预演；QINGLONG_NOTIFY=0：关闭通知。
 * QINGLONG_NOTIFY_DIR：青龙 sendNotify.js 所在目录（可选）。
 * 安全变更：移除随机点赞/撤销、收藏/撤销及分享刷分；只保留明确的签到副作用。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const dry = process.env.GU_HOME_DRY_RUN === '1';
const started = Date.now();
const title = '顾家家居签到';
const lines = (process.env.GU_HOME_TOKEN || '').split(/\r?\n/).filter(x => x.trim());
const stats = { accounts: lines.length, success: 0, failed: 0, tasks: {total:0, success:0, alreadyComplete:0, skipped:0, failed:0}, dryRun: dry };
const log = msg => console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${msg}`);
const md5 = value => crypto.createHash('md5').update(value).digest('hex');
function account(line) {
  const split = line.indexOf('#');
  if (split < 1 || split === line.length - 1) throw new Error('账号格式错误，应为 AccessToken#X-Customer');
  const token = line.slice(0, split), customer = line.slice(split + 1);
  if (/[\r\n\x00-\x1f\x7f]/.test(token + customer)) throw new Error('凭据含非法控制字符');
  return { token, customer };
}
function request(auth, endpoint, method, body) {
  if (dry) throw new Error('预演禁止业务网络请求');
  const timestamp = String(Date.now());
  const headers = { 'User-Agent':'Mozilla/5.0', 'Content-Type':'application/json', brandCode:'K001', appid:'667516',
    Referer:'https://servicewechat.com/wx0770280d160f09fe/214/page-frame.html', 'Accept-Language':'zh-CN,zh;q=0.9',
    AccessToken:auth.token, 'X-Customer':auth.customer, timestamp,
    sign:md5('667516' + process.env.GU_HOME_APP_SECRET + timestamp) };
  let payload;
  if (body !== undefined) {
    const canonical = Object.keys(body).sort((a,b) => a.localeCompare(b)).map(key => `${key}=${typeof body[key] === 'object' ? JSON.stringify(body[key]) : body[key]}`).join('&');
    headers.parameterSign = md5(md5(canonical) + timestamp.substring(4,10));
    payload = JSON.stringify(body);
    headers['Content-Length'] = Buffer.byteLength(payload);
  }
  return new Promise((resolve,reject) => {
    let done = false;
    const finish = (err,value) => { if (done) return; done = true; clearTimeout(timer); err ? reject(err) : resolve(value); };
    const req = https.request({hostname:'mc.kukahome.com', path:endpoint, method, headers}, res => {
      let size = 0; const chunks = [];
      res.on('data', chunk => { size += chunk.length; if(size > 1024*1024) { finish(new Error('响应超过大小限制')); res.destroy(); req.destroy(); } else chunks.push(chunk); });
      res.on('error', () => finish(new Error('响应读取失败')));
      res.on('aborted', () => finish(new Error('响应中断')));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) return finish(new Error(`HTTP 状态异常（${res.statusCode}）`));
        let data; try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return finish(new Error('响应不是有效 JSON')); }
        if (!data || data.code !== 0) return finish(new Error('业务未确认成功（要求 code 为数字 0；请检查凭据或接口）'));
        finish(null,data.data);
      });
    });
    const timer = setTimeout(() => { finish(new Error('请求超时')); req.destroy(); },15000);
    req.on('error', () => finish(new Error('网络请求失败')));
    if(payload !== undefined) req.write(payload);
    req.end();
  });
}
function numeric(value) { return (typeof value === 'number' && Number.isFinite(value) && value >= 0) || (typeof value === 'string' && /^\d+(\.\d+)?$/.test(value)); }
async function notify(body) {
  if (['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase())) return '已关闭';
  // 预演绝不加载通知模块（模块可能自行联网）；仍生成相同的脱敏通知摘要。
  if (dry) { log(`通知预演：${body}`); return '预演已生成，未发送'; }
  const candidates = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  const modulePath = candidates.find(p => fs.existsSync(p));
  if (!modulePath) return '不可用（未发现 sendNotify.js，保留业务退出码）';
  return new Promise(resolve => {
    // 隔离通知模块的日志与异常，防止第三方模块输出凭据；超时不影响业务状态。
    const child = spawn(process.execPath, ['-e', 'Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))', modulePath,title,body], {stdio:'ignore'});
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve('通知超时'); },15000);
    child.on('error', () => { clearTimeout(timer); resolve('通知启动失败'); });
    child.on('close', code => { clearTimeout(timer); resolve(code === 0 ? '已发送' : '通知失败'); });
  });
}
async function main() {
  log(`========== ${title} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式'}；账号数：${lines.length}`);
  let configError = !lines.length || (!dry && !process.env.GU_HOME_APP_SECRET);
  if(configError) log('❌ 配置错误：需要 GU_HOME_TOKEN，正式模式还需要 GU_HOME_APP_SECRET');
  for(let i=0;i<lines.length;i++) {
    const start = Date.now(); const counts = {total:3, success:0, alreadyComplete:0, skipped:0, failed:0};
    let auth;
    try { auth = account(lines[i]); } catch { log(`账号 ${i+1}：❌ 凭据格式错误`); }
    const steps = [
      ['账号信息', async () => {
        const data = await request(auth,'/club-server/api/user/info','POST');
        if(!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('账号信息结构异常');
        if(typeof data.nickName === 'string' && data.nickName) log(`账号 ${i+1} 昵称：${data.nickName.replace(/[\r\n\x00-\x1f\x7f]/g,' ')}`);
        else log(`账号 ${i+1}：接口未返回昵称`);
      }],
      ['每日签到', async () => {
        const points = await request(auth,'/integral-server/scenePoint/scene/point','POST',{scene:'sign',brandCode:'K001'});
        if(!numeric(points)) throw new Error('签到返回积分结构异常，不能确认完成');
        log(`✅ 签到成功，积分+${points}`);
      }],
      ['积分查询', async () => {
        const data = await request(auth,'/club-server/front/member/userCenterScore','GET');
        if(!data || !numeric(data.signCount) || !numeric(data.point)) throw new Error('积分响应结构异常');
        log(`已连续签到${data.signCount}天；当前积分：${data.point}`);
      }]
    ];
    for(let j=0;j<steps.length;j++) {
      const stage = Date.now(); log(`账号 ${i+1} · 阶段 ${j+1}/3 ${steps[j][0]}`);
      if(!auth || configError || (j === 1 && counts.failed)) { counts.skipped++; log(`⏭️ 配置或身份校验未通过，跳过；耗时 ${Date.now()-stage}ms`); }
      else try {
        if(dry) log(`✅ 预演通过：已校验参数并模拟${steps[j][0]}，未发送请求`);
        else await steps[j][1]();
        counts.success++; log(`✅ 阶段完成，耗时 ${Date.now()-stage}ms`);
      } catch(e) { counts.failed++; log(`❌ ${e.message}；耗时 ${Date.now()-stage}ms`); }
    }
    const ok = counts.success === 3;
    stats[ok ? 'success' : 'failed']++;
    for(const key of Object.keys(counts)) stats.tasks[key] += counts[key];
    log(`账号 ${i+1} 统计：总任务 ${counts.total}，成功 ${counts.success}，已完成 ${counts.alreadyComplete}，跳过 ${counts.skipped}，失败 ${counts.failed}；${ok?'成功':'失败'}；耗时 ${Date.now()-start}ms`);
  }
  const exitCode = configError || stats.failed ? 1 : 0;
  stats.status = configError ? 'configuration-error' : stats.failed ? (stats.success ? 'partial-failure' : 'failure') : dry ? 'dry-run' : 'success';
  stats.notification = await notify(`模式：${dry?'断网预演':'正式'}；账号总数 ${stats.accounts}，成功 ${stats.success}，失败 ${stats.failed}；状态 ${stats.status}`);
  stats.durationMs = Date.now()-started;
  stats.finishedAt = new Date().toISOString();
  log('----------------------------------------');
  log(`账号统计：总数 ${stats.accounts}，成功 ${stats.success}，失败 ${stats.failed}`);
  log(`子任务统计：${JSON.stringify(stats.tasks)}`);
  log(`总耗时：${stats.durationMs}ms；完成时间：${stats.finishedAt}；通知：${stats.notification}；最终状态：${stats.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(stats));
  process.exitCode = exitCode;
}
main().catch(() => { console.error('任务内部异常（详情已抑制）'); process.exitCode = 1; });
