// name: 中国日报
// cron: 0 15 9 * * *
/*
name: 中国日报
cron: 0 15 9 * * *
原作者及来源：ql_sign_script : https://github.com/unitaryhighs/ql_sign_script
许可证：MIT
参数：DAILYNEWSCN_LIST 为必填执行标记，填写 1 即可，无需注册、Cookie 或 Token。
兼容旧变量中的非空值；按非空行读取，但公开日报只获取一次，不向接口发送这些值。
DAILYNEWSCN_DRY_RUN=1：完全断网预演，包括模拟通知，不加载通知模块。
QINGLONG_NOTIFY 默认 1，可用 0、false、no、off 禁用。
QINGLONG_NOTIFY_DIR 可选：青龙 sendNotify.js 所在目录。
仅访问上游公开日报接口，不写表格、不发布帖子、不修改账号。

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
*/
'use strict';
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const TITLE = '中国日报';
const URL = 'https://api.suyanw.cn/api/China_Daily_Highlights_of_the_day.php';
const dryRun = process.env.DAILYNEWSCN_DRY_RUN === '1';
const started = Date.now();
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${stamp()}] ${text}`);
const disabled = value => /^(0|false|no|off)$/i.test((value || '').trim());

function getReport() {
  if (dryRun) throw new Error('预演禁止网络');
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(value);
    };
    const request = https.get(URL, { headers: { Accept: 'text/plain', 'User-Agent': 'Qinglong-DailyNews/1.0' } }, response => {
      if (response.statusCode !== 200) {
        finish(new Error('日报接口 HTTP 状态异常'));
        response.destroy();
        return;
      }
      const type = String(response.headers['content-type'] || '');
      if (/html|json|image|octet-stream/i.test(type)) {
        finish(new Error('日报响应格式与上游文本契约不符'));
        response.destroy();
        return;
      }
      let size = 0;
      const chunks = [];
      response.on('data', chunk => {
        size += chunk.length;
        if (size > 128 * 1024) {
          finish(new Error('日报响应超过安全大小'));
          response.destroy();
        } else chunks.push(chunk);
      });
      response.on('error', () => finish(new Error('日报响应接收失败')));
      response.on('aborted', () => finish(new Error('日报响应中断')));
      response.on('end', () => finish(null, Buffer.concat(chunks).toString('utf8')));
    });
    const timer = setTimeout(() => {
      finish(new Error('日报请求超时'));
      request.destroy();
    }, 10000);
    request.on('error', () => finish(new Error('日报网络请求失败')));
  });
}

function parseReport(text) {
  const cleaned = text.replace(/^\uFEFF/, '').trim();
  // 原来源只有文本响应，没有可验证的 JSON 业务码，拒绝错误页和未知结构。
  if (cleaned.length < 20 || !/[\u3400-\u9fff]/u.test(cleaned) ||
      /^[\[{]/.test(cleaned) || /<\/?(?:html|body|script|head)\b/i.test(cleaned) ||
      /(?:接口|请求|服务|参数).{0,12}(?:失败|错误|异常|限流|无效|维护)|访问频繁|请求过多|额度不足|今日暂无|暂无数据|暂无新闻|access denied|unauthorized|rate limit|internal server error/i.test(cleaned)) {
    throw new Error('日报内容为空、错误提示或无法验证为新闻文本');
  }
  const lines = cleaned.split(/\r?\n/).map(line => line.replace(/[\u0000-\u001f\u007f-\u009f]/g, '').trim()).filter(Boolean);
  return lines.map(line => line
    .replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]')
    .replace(/\b(?:cookie|token|authorization|session|signature|device_?id)\s*[:=]\s*\S+/gi, '[敏感字段已隐藏]'));
}

async function notify(body) {
  if (disabled(process.env.QINGLONG_NOTIFY)) return '已禁用';
  if (dryRun) return '断网预演已模拟通知';
  const locations = [
    process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'
  ].filter(Boolean);
  const file = locations.find(location => fs.existsSync(location));
  if (!file) return '通知模块不可用（业务退出码保持不变）';
  // 隔离通知输出，限制通知耗时；通知不得输出模块中的凭据或改变业务结果。
  const runner = 'const m=require(process.argv[1]);Promise.resolve().then(()=>{if(typeof m.sendNotify!=="function")throw Error();return m.sendNotify(process.argv[2],process.argv[3]);}).then(()=>process.exit(0),()=>process.exit(1));';
  return new Promise(resolve => {
    let done = false;
    const child = spawn(process.execPath, ['-e', runner, file, TITLE, body], { stdio: 'ignore' });
    const complete = value => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      resolve(value);
    };
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      complete('通知超时（业务退出码保持不变）');
    }, 15000);
    child.on('error', () => complete('通知启动失败（业务退出码保持不变）'));
    child.on('close', code => complete(code === 0 ? '通知已发送' : '通知失败（业务退出码保持不变）'));
  });
}

async function main() {
  console.log('========== 中国日报 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dryRun ? '断网预演' : '正式运行'}`);
  log('账号总数：0（公开日报，无需账号）；任务总数：1');
  let status = 'configuration-error', success = 0, failure = 0, skipped = 0, report = [];
  const stageStart = Date.now();
  log('阶段 1/3：检查执行参数');
  const entries = (process.env.DAILYNEWSCN_LIST || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if (!entries.length) {
    failure = 1;
    log('❌ 缺少 DAILYNEWSCN_LIST；此免账号任务填写 1 即可，不需要凭据');
  } else {
    log(`✅ 执行标记检查通过；阶段耗时 ${Date.now() - stageStart} 毫秒`);
    const fetchStart = Date.now();
    log('阶段 2/3：获取并验证日报');
    try {
      if (dryRun) {
        report = parseReport('中国日报断网预演\n这是一条本地测试新闻，仅用于验证文本处理流程，不代表今日真实新闻。');
        skipped = 1;
        status = 'dry-run';
        log('✅ DRY_RUN_OK：本地日报解析通过，HTTP 请求已跳过');
      } else {
        report = parseReport(await getReport());
        success = 1;
        status = 'success';
        log(`✅ DAILYNEWSCN_SUCCESS：日报获取及文本检查通过，共 ${report.length} 行`);
        console.log('【中国日报】\n' + report.join('\n'));
      }
    } catch (error) {
      failure = 1;
      status = 'failure';
      log(`❌ ${error.message}`);
    }
    log(`日报任务统计：总任务 1，成功 ${success}，已完成 0，跳过 ${skipped}，失败 ${failure}；阶段耗时 ${Date.now() - fetchStart} 毫秒`);
  }
  log('阶段 3/3：发送任务总结');
  const body = `账号总数：0（无需账号）\n任务总数：1；成功：${success}；失败：${failure}；跳过：${skipped}\n状态：${status}` +
    (status === 'success' ? '\n【中国日报】\n' + report.join('\n') : '');
  const notification = await notify(body);
  const finishedAt = new Date().toISOString();
  console.log('--------------------------------');
  log(`账号统计：总数 0，成功 0，失败 0；子任务统计：总数 1，成功 ${success}，已完成 0，跳过 ${skipped}，失败 ${failure}`);
  log(`完成时间：${finishedAt}；总耗时：${Date.now() - started} 毫秒；通知状态：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task: 'dailynewscn', mode: dryRun ? 'dry-run' : 'live', status, accounts: { total: 0, success: 0, failure: 0 }, tasks: { total: 1, success, alreadyComplete: 0, skipped, failure }, notification, startedAt: new Date(started).toISOString(), finishedAt, elapsedMs: Date.now() - started }));
  process.exitCode = failure ? 1 : 0;
}
main();
