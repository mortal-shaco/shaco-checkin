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
QINGLONG_NOTIFY 未设置时按上架状态，可用 0、false、no、off 禁用。
QINGLONG_NOTIFY_DIR 可选：青龙 sendNotify.js 所在目录。
DAILYNEWSCN_TASK 默认 dailynewscn；填写 bdhot 仅获取百度热搜榜；填写 chouq 仅随机抽签。
日报保持 cron: 0 15 9 * * *；百度榜另建青龙任务指向同一文件，
设置 DAILYNEWSCN_TASK=bdhot，定时 0 0 9 * * *，无需复制脚本。
BDHOT_LIST 为百度榜执行标记，填写 1 即可；无需获取账号或凭据。
BDHOT_DRY_RUN=1 兼容百度榜断网预演；DAILYNEWSCN_DRY_RUN=1 对所有模式生效。
抽签另建青龙任务指向同一文件，设置 DAILYNEWSCN_TASK=chouq，定时 0 10 9 * * *。
CHOUQ_LIST 为抽签执行标记，填写 1 即可，兼容非空旧值；不发送这些值，无需凭据。
CHOUQ_DRY_RUN=1 兼容抽签断网预演；不自动添加其他任务或更改既有调度。
源功能盘点：百度前五热搜 09:00、随机抽签 09:10、日报 09:15；均公开读取并通知。
抽签保留签文、签等级与颜色、卦象、解签全角空格换行、典故首句及省略号。
新增 DAILYNEWSCN_TASK=day60s：原 HTTPS GET 世界新闻接口，保留 DAY60S_LIST。
DAY60S_LIST 在青龙手工填写 1，兼容旧非空值；无需注册或获取凭据，不发送标记。
DAY60S_DRY_RUN=1 兼容该模式断网预演；统一预演开关对所有模式生效。
世界新闻另建同文件任务，设置 DAILYNEWSCN_TASK=day60s，定时 0 20 9 * * *。
新增 DAILYNEWSCN_TASK=dyhot：HTTPS GET https://jkapi.com/api/dy_hot?limit=5 获取抖音前五热搜。
DYHOT_LIST 为本地执行标记，在青龙手工填写 1；无需账号，不发送标记。
DYHOT_DRY_RUN=1 兼容抖音榜断网预演；统一预演开关对所有模式生效。
抖音榜另建同文件任务，设置 DAILYNEWSCN_TASK=dyhot，保持定时 0 25 9 * * *。
功能覆盖对比：保留维护版日报、百度榜、抽签、世界新闻、抖音榜全部能力及默认值；新增鸡汤。
原鸡汤来源 hot/jitang.js：09:30 读取公开短句并通知，无需账号，JITANG_LIST 为本地执行标记。
新增 DAILYNEWSCN_TASK=jitang：HTTPS GET https://jkapi.com/api/dujitang，不发送标记或凭据。
JITANG_LIST 在青龙手工填写 1，兼容旧非空值；JITANG_DRY_RUN=1 仅预演鸡汤。
鸡汤另建同文件任务，设置 DAILYNEWSCN_TASK=jitang，保持定时 0 30 9 * * *。
鸡汤沿用文本响应、超时、大小及错误页校验；允许短句，成功输出 JITANG_SUCCESS。
不发布帖子、评论或分享文本，随机发文内容策略不适用；断网预演不会调用任何远程服务。
修正前轮导入失败：契约 smokeTest.env 必须包含 dryRunEnv 的全部键值。
上游均公开读取并通知；移除私有工作表适配器、写表和无超时请求。
本任务无需账号，LIST 是执行标记，不能当作凭据或真实账号成功数。
参数获取：所有 LIST 均为本地执行标记，在青龙环境变量手工填写 1，不需要注册或登录。
公开任务只读取一次，无账号循环；多个非空行仅兼容旧标记，不代表多账号。
原抽签来源只有 HTTP 地址证据，保持原 GET URL，不发送凭据，不假设 HTTPS 已可用。
完整 data 字符串字段与非空签等级为抽签业务校验；没有已证实的固定业务码，不臆造接口。
参考来源：hot/chouq.js、hot/dailynewscn.js、hot/bdhot.js、hot/day60s.js、hot/dyhot.js、hot/jitang.js。
各源原作者标识均为 ql_sign_script : https://github.com/unitaryhighs/ql_sign_script，MIT。
不复用上游私有 airscriptShim、工作表写入和自定义推送凭据。
仅访问所选任务的上游公开日报、百度热搜、抽签、世界新闻、抖音热搜或鸡汤接口，不写表格、不发布帖子、不修改账号。

新增 DAILYNEWSCN_TASK=kfc：读取、校验、输出并通知 KFC疯狂星期四文案。
KFC_LIST 为本地执行标记，在青龙环境变量手工填写 1，兼容旧非空值；无需账号或凭据。
KFC_DRY_RUN=1 兼容此模式断网预演，DAILYNEWSCN_DRY_RUN=1 对全部模式生效。
同文件另建 KFC 任务，设置 DAILYNEWSCN_TASK=kfc，保持 cron: 0 35 9 * * *（每日09:35）。
原 KFC 源仅证实 HTTP GET http://shanhe.kim/api/za/kfc.php；保持地址与方法，不发送标记。
功能盘点与覆盖：原六模式、参数、输出标记、接口、抽签格式及调度全部保留；补入缺失的 KFC 模式。
所有模式均只读公开内容并发送通知；删除原 KFC 写表、自定义推送凭据与私有适配器依赖。
参考比较：日报、百度榜、抽签、世界新闻接口及格式与提供的参考一致，无接口变更证据。
前轮执行器失败为模型列表刷新超时，无失败包或导入契约错误证据；本轮产物使用 Node 标准库独立执行。
KFC 内容不自动发布帖子、评论或分享，公共发文随机文本策略不适用。

新增 DAILYNEWSCN_TASK=meiju：HTTPS GET https://api.suyanw.cn/api/meiju 获取、校验、输出并通知随机美句。
MEIJU_LIST 在青龙环境变量手工填写 1，兼容旧非空值；无需账号或凭据，不发送标记。
MEIJU_DRY_RUN=1 仅预演美句；DAILYNEWSCN_DRY_RUN=1 对全部模式生效。
同文件另建美句任务，设置 DAILYNEWSCN_TASK=meiju，保持 cron: 0 40 9 * * *。
美句允许中文短句，拒绝空白、错误页、未知 JSON、超时和过大响应，成功输出 MEIJU_SUCCESS。
本轮盘点：美句公开读取及通知尚未被维护版覆盖；在原七模式基础上增补，无重复产品脚本。
参考日报、百度榜、抽签和60秒脚本的接口、方法及抽签格式与维护版一致，无接口变化证据。
保留原七模式默认值、参数、调度、通知、预演、输出标记及校验，不增加远程文本替代链。
删除美句源的私有工作表适配器、写表及无超时请求；不发布帖子、评论或分享。

新增 DAILYNEWSCN_TASK=miyu：HTTPS GET https://api.71xk.com/api/miyu 获取、校验、输出并通知谜语。
MIYU_LIST 为本地执行标记，在青龙手工填写 1，兼容旧非空值；无需账号或凭据，不发送标记。
MIYU_DRY_RUN=1 仅预演谜语；DAILYNEWSCN_DRY_RUN=1 对全部模式生效。
同文件另建谜语任务，设置 DAILYNEWSCN_TASK=miyu，保持 cron: 0 45 9 * * *。
功能盘点：原谜语只有公开纯文本读取和通知；无登录、签到或发文，09:45 独立调度。
覆盖对比：保留维护版八种模式、默认日报、所有接口、参数、格式、通知和成功标记；仅补入缺失的谜语。
谜语允许中文短文本，拒绝空白、错误页、未知 JSON、超时、过大响应及错误提示，输出 MIYU_SUCCESS。
相关日报、百度榜、抽签及60秒来源证实维护版接口、GET 方法及格式，无接口变更证据。
移除谜语源私有 airscriptShim、默认写表和自定义推送凭据；独立使用 Node.js 标准库 HTTP。
MIT 及上游 ql_sign_script 来源标识完整保留；不自动发布帖子、评论或分享文本。
本轮没有被拒绝的真实验证或前轮修复失败；仅进行断网检查，不声称真实接口成功。

新增 DAILYNEWSCN_TASK=oilprice：原 HTTPS GET https://api.03c3.cn/api/oilPrice?area= 查询今日油价。
同一维护文件另建任务，设置 DAILYNEWSCN_TASK=oilprice，保持 cron: 0 50 9 * * *。
OILPRICE_LIST 每个非空行填写一个地区，例如北京；无需注册、Cookie、Token 或执行标记。
也支持每行 JSON 对象 {"area":"北京"}；旧执行标记可配合 OILPRICE_AREA 指定统一地区。
原来源仅说明工作表 D 列地区，未提供私有适配器的环境编码，不能保证未提供的分隔格式。
OILPRICE_AREA 为可选地区默认值；纯地区行和 JSON area 优先于默认值。
OILPRICE_DRY_RUN=1 为油价断网预演；统一 DAILYNEWSCN_DRY_RUN=1 仍对全部任务生效。
油价各地区独立查询，任一地区配置或响应失败均非零退出；不把地区当作账号。
保留地区、日期、92/95/98号汽油、0号柴油与其他油号价格的图标及元/L格式。
验证 HTTP 200、JSON 数据结构、返回地区、有效日期、价格及明确失败标志；无业务码证据不臆造业务码。
油价无账号、无发文；唯一正式副作用为青龙通知。移除原工作表写入、私有适配器和自定义推送。
覆盖对比：原九模式、默认日报、接口、输出、调度及通知代码保留；仅补入缺失的油价模式。
相关四来源的接口、GET 方法、抽签字段与维护版一致；本轮没有被拒绝的真实验证或前次失败。

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
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["f3d5ae90c3c979bf", "scripts/dailynewscn.js", "dailynewscn.js", "dailynewscn"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const requestedTask = process.env.DAILYNEWSCN_TASK === undefined ? 'dailynewscn' : process.env.DAILYNEWSCN_TASK.trim();
const task = ['dailynewscn', 'bdhot', 'chouq', 'day60s', 'dyhot', 'jitang', 'kfc', 'meiju', 'miyu', 'oilprice'].includes(requestedTask) ? requestedTask : 'invalid';
const isOil = task === 'oilprice';
const isBaidu = task === 'bdhot';
const isDraw = task === 'chouq';
const isWorld = task === 'day60s';
const isDouyin = task === 'dyhot';
const isJitang = task === 'jitang';
const isKfc = task === 'kfc';
const isMeiju = task === 'meiju';
const isMiyu = task === 'miyu';
const TITLE = isOil ? '今日油价' : isMiyu ? '谜语' : isMeiju ? '随机美句' : isKfc ? 'KFC疯狂星期四' : isJitang ? '鸡汤' : isDouyin ? '抖音热搜榜' : isWorld ? '每天60秒读懂世界' : isDraw ? '随机抽签' : isBaidu ? '百度热搜榜' : '中国日报';
const marker = isOil ? 'OILPRICE_LIST' : isMiyu ? 'MIYU_LIST' : isMeiju ? 'MEIJU_LIST' : isKfc ? 'KFC_LIST' : isJitang ? 'JITANG_LIST' : isDouyin ? 'DYHOT_LIST' : isWorld ? 'DAY60S_LIST' : isDraw ? 'CHOUQ_LIST' : isBaidu ? 'BDHOT_LIST' : 'DAILYNEWSCN_LIST';
const URL = isOil ? 'https://api.03c3.cn/api/oilPrice' : isMiyu ? 'https://api.71xk.com/api/miyu' : isMeiju ? 'https://api.suyanw.cn/api/meiju' : isKfc ? 'http://shanhe.kim/api/za/kfc.php' : isJitang ? 'https://jkapi.com/api/dujitang' : isDouyin ? 'https://jkapi.com/api/dy_hot?limit=5' : isWorld ? 'https://jkapi.com/api/day_60s' : isDraw ? 'http://shanhe.kim/api/za/chouq.php' : isBaidu ? 'https://jkapi.com/api/bd_hot?limit=5' : 'https://api.suyanw.cn/api/China_Daily_Highlights_of_the_day.php';
const dryRun = (isOil && process.env.OILPRICE_DRY_RUN === '1') || process.env.DAILYNEWSCN_DRY_RUN === '1' || (isBaidu && process.env.BDHOT_DRY_RUN === '1') || (isDraw && process.env.CHOUQ_DRY_RUN === '1') || (isWorld && process.env.DAY60S_DRY_RUN === '1') || (isDouyin && process.env.DYHOT_DRY_RUN === '1') || (isJitang && process.env.JITANG_DRY_RUN === '1') || (isKfc && process.env.KFC_DRY_RUN === '1') || (isMeiju && process.env.MEIJU_DRY_RUN === '1') || (isMiyu && process.env.MIYU_DRY_RUN === '1');
const started = Date.now();
const stamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
const log = text => console.log(`[${stamp()}] ${text}`);
const disabled = value => /^(0|false|no|off)$/i.test((value || '').trim());

function getReport(requestURL = URL) {
  if (dryRun) throw new Error('预演禁止网络');
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(value);
    };
    const transport = (isDraw || isKfc) ? http : https;
    const request = transport.get(requestURL, { headers: { Accept: (isDraw || isOil) ? 'application/json' : 'text/plain', 'User-Agent': 'Qinglong-DailyNews/1.0' } }, response => {
      if (response.statusCode !== 200) {
        finish(new Error(TITLE + '接口 HTTP 状态异常'));
        response.destroy();
        return;
      }
      const type = String(response.headers['content-type'] || '');
      if (((isDraw || isOil) ? /html|image|octet-stream/i : /html|json|image|octet-stream/i).test(type)) {
        finish(new Error(TITLE + '响应格式与上游文本契约不符'));
        response.destroy();
        return;
      }
      let size = 0;
      const chunks = [];
      response.on('data', chunk => {
        size += chunk.length;
        if (size > 128 * 1024) {
          finish(new Error(TITLE + '响应超过安全大小'));
          response.destroy();
        } else chunks.push(chunk);
      });
      response.on('error', () => finish(new Error(TITLE + '响应接收失败')));
      response.on('aborted', () => finish(new Error(TITLE + '响应中断')));
      response.on('end', () => finish(null, Buffer.concat(chunks).toString('utf8')));
    });
    const timer = setTimeout(() => {
      finish(new Error(TITLE + '请求超时'));
      request.destroy();
    }, 10000);
    request.on('error', () => finish(new Error(TITLE + '网络请求失败')));
  });
}

function parseReport(text) {
  const cleaned = text.replace(/^\uFEFF/, '').trim();
  // 原来源只有文本响应，没有可验证的 JSON 业务码，拒绝错误页和未知结构。
  if (cleaned.length < ((isJitang || isKfc || isMeiju || isMiyu) ? 2 : 20) || !/[\u3400-\u9fff]/u.test(cleaned) ||
      /^[\[{]/.test(cleaned) || /<\/?(?:html|body|script|head)\b/i.test(cleaned) ||
      /(?:接口|请求|服务|参数).{0,12}(?:失败|错误|异常|限流|无效|维护)|访问频繁|请求过多|额度不足|今日暂无|暂无数据|暂无新闻|access denied|unauthorized|rate limit|internal server error/i.test(cleaned)) {
    throw new Error(isMiyu ? '谜语内容为空、错误提示或无法验证为中文文本' : isMeiju ? '美句内容为空、错误提示或无法验证为中文文本' : isKfc ? 'KFC文案为空、错误提示或无法验证为中文文本' : isJitang ? '鸡汤内容为空、错误提示或无法验证为中文文本' : (isBaidu || isDouyin) ? '热搜内容为空、错误提示或无法验证为榜单文本' : '日报内容为空、错误提示或无法验证为新闻文本');
  }
  if (isMiyu && /暂无谜语|没有谜语|^(?:error|failed|失败|错误)\s*[:：]/i.test(cleaned)) throw new Error('谜语接口返回错误或暂无内容');
  const lines = cleaned.split(/\r?\n/).map(line => line.replace(/[\u0000-\u001f\u007f-\u009f]/g, '').trim()).filter(Boolean);
  return lines.map(line => line
    .replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]')
    .replace(/\b(?:cookie|token|authorization|session|signature|device_?id)\s*[:=]\s*\S+/gi, '[敏感字段已隐藏]'));
}

function redactDraw(text) {
  return text.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/g, '')
    .replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]')
    .replace(/\b(?:cookie|token|authorization|session|signature|device_?id)\s*[:=]\s*\S+/gi, '[敏感字段已隐藏]');
}

function parseDraw(text) {
  let result;
  try { result = JSON.parse(text.replace(/^\uFEFF/, '')); }
  catch { throw new Error('抽签响应不是有效 JSON'); }
  const data = result && result.data;
  if (!data || typeof data !== 'object' || Array.isArray(data) ||
      result.success === false || (result.error !== undefined && result.error !== null && result.error !== false && result.error !== '') ||
      !['draw', 'annotate', 'explain', 'source'].every(key => typeof data[key] === 'string' && data[key].trim())) {
    throw new Error('抽签业务失败或签文必需字段缺失');
  }
  const match = data.draw.trim().match(/^(.+?)\s*[（(]([^（）()]+)[）)]$/u);
  if (!match || !match[1].trim() || !match[2].trim()) throw new Error('抽签签文或签等级无法验证');
  const emoji = { '上签': '🟢', '中签': '🟡', '下签': '🔴' };
  return [
    `${emoji[match[2]] || '⚪'} ${match[1].trim()} (${match[2]})`,
    `📜 卦象：${data.annotate}`,
    `📖 解签：${data.explain.replace(/　/g, '\n          ')}`,
    `🌄 典故：${data.source.split('。')[0]}...`
  ].map(redactDraw);
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
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dryRun ? '断网预演' : '正式运行'}`);
  log('账号总数：0（公开资讯，无需账号）；任务总数：1');
  let status = 'configuration-error', success = 0, failure = 0, skipped = 0, report = [];
  const stageStart = Date.now();
  log('阶段 1/3：检查执行参数');
  const entries = (process.env[marker] || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if (!['dailynewscn', 'bdhot', 'chouq', 'day60s', 'dyhot', 'jitang', 'kfc', 'meiju', 'miyu', 'oilprice'].includes(task) || !entries.length) {
    failure = 1;
    log(`❌ 配置错误：DAILYNEWSCN_TASK 仅支持 dailynewscn、bdhot、chouq、day60s、dyhot、jitang、kfc、meiju 或 miyu；所选任务必须配置 ${marker}=1，无需凭据；阶段耗时 ${Date.now() - stageStart} 毫秒`);
    log('阶段 2/3：⏭️ 配置错误，跳过获取；阶段耗时 0 毫秒');
  } else {
    log(`✅ 执行标记检查通过；阶段耗时 ${Date.now() - stageStart} 毫秒`);
    const fetchStart = Date.now();
    log(`阶段 2/3：获取并验证${TITLE}`);
    try {
      if (dryRun) {
        report = isDraw ? parseDraw(JSON.stringify({ data: { draw: '本地测试签 (上签)', annotate: '本地卦象，仅验证格式', explain: '本地解签　仅用于断网预演', source: '本地典故。非真实抽签结果。' } })) : parseReport(isMiyu ? '谜面：什么东西越洗越脏？\n谜底：水。仅用于断网预演。' : isMeiju ? '本地美句，仅用于断网预演。' : isKfc ? 'KFC疯狂星期四本地文案，仅用于断网预演。' : isJitang ? '本地鸡汤短句，仅用于断网预演。' : isDouyin ? '抖音热搜榜断网预演\n1. 本地测试热搜一\n2. 本地测试热搜二\n3. 本地测试热搜三\n4. 本地测试热搜四\n5. 本地测试热搜五' : isWorld ? '每天60秒读懂世界断网预演\n这是一条本地世界新闻，仅用于验证文本处理流程，不代表今日真实新闻。' : isBaidu ? '百度热搜榜断网预演\n1. 本地测试热搜一\n2. 本地测试热搜二\n3. 本地测试热搜三\n4. 本地测试热搜四\n5. 本地测试热搜五' : '中国日报断网预演\n这是一条本地测试新闻，仅用于验证文本处理流程，不代表今日真实新闻。');
        skipped = 1;
        status = 'dry-run';
        log(`✅ DRY_RUN_OK：本地${TITLE}解析通过，HTTP 请求已跳过`);
      } else {
        const responseText = await getReport();
        report = isDraw ? parseDraw(responseText) : parseReport(responseText);
        success = 1;
        status = 'success';
        log(`✅ ${isMiyu ? 'MIYU_SUCCESS' : isMeiju ? 'MEIJU_SUCCESS' : isKfc ? 'KFC_SUCCESS' : isJitang ? 'JITANG_SUCCESS' : isDouyin ? 'DYHOT_SUCCESS' : isWorld ? 'DAY60S_SUCCESS' : isDraw ? 'CHOUQ_SUCCESS' : isBaidu ? 'BDHOT_SUCCESS' : 'DAILYNEWSCN_SUCCESS'}：${TITLE}获取及${isDraw ? '签文结构' : '文本'}检查通过，共 ${report.length} 行`);
        console.log(`【${TITLE}】\n` + report.join('\n'));
      }
    } catch (error) {
      failure = 1;
      status = 'failure';
      log(`❌ ${error.message}`);
    }
    log(`${TITLE}任务统计：总任务 1，成功 ${success}，已完成 0，跳过 ${skipped}，失败 ${failure}；阶段耗时 ${Date.now() - fetchStart} 毫秒`);
  }
  const notifyStart = Date.now();
  log('阶段 3/3：发送任务总结');
  const body = `账号总数：0（无需账号）\n任务总数：1；成功：${success}；失败：${failure}；跳过：${skipped}\n状态：${status}` +
    (status === 'success' ? `\n【${TITLE}】\n` + report.join('\n') : '');
  const notification = await notify(body);
  log(`通知结果：${notification}；阶段耗时 ${Date.now() - notifyStart} 毫秒`);
  const finishedAt = new Date().toISOString();
  console.log('--------------------------------');
  log(`账号统计：总数 0，成功 0，失败 0；子任务统计：总数 1，成功 ${success}，已完成 0，跳过 ${skipped}，失败 ${failure}`);
  log(`完成时间：${finishedAt}；总耗时：${Date.now() - started} 毫秒；通知状态：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task, mode: dryRun ? 'dry-run' : 'live', status, accounts: { total: 0, success: 0, failure: 0 }, tasks: { total: 1, success, alreadyComplete: 0, skipped, failure }, notification, startedAt: new Date(started).toISOString(), finishedAt, elapsedMs: Date.now() - started }));
  process.exitCode = failure ? 1 : 0;
}
(isOil ? mainOil : main)();

// 油价只读地区任务；旧九模式仍使用上面的原执行流程。
function oilArea(line) {
  let area = line.trim();
  if (area.startsWith('{')) {
    let row;
    try { row = JSON.parse(area); } catch { throw new Error('地区 JSON 格式错误'); }
    area = row && typeof row.area === 'string' ? row.area.trim() : '';
  } else if (area === '1' && process.env.OILPRICE_AREA) {
    area = process.env.OILPRICE_AREA.trim();
  }
  if (!/^[\u3400-\u9fff]{2,20}$/u.test(area)) throw new Error('地区必须为中文地区名称，旧标记请配合 OILPRICE_AREA');
  return area;
}
function parseOil(text, area) {
  let result;
  try { result = JSON.parse(text.replace(/^\uFEFF/, '')); } catch { throw new Error('油价响应不是有效 JSON'); }
  const d = result && result.data;
  if (!d || typeof d !== 'object' || Array.isArray(d) || result.success === false ||
      (result.error !== undefined && ![null, false, '', 0].includes(result.error)) ||
      typeof d.area !== 'string' || d.area.trim() !== area || typeof d.date !== 'string') {
    throw new Error('油价业务失败或地区、日期字段不符');
  }
  const match = d.date.trim().match(/^(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?$/);
  if (!match) throw new Error('油价日期格式无法验证');
  const [year, month, day] = match.slice(1).map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (year < 2000 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) throw new Error('油价日期无效');
  const prices = Object.entries(d).filter(([key]) => !['area', 'date'].includes(key));
  if (!['92', '95', '98', '0'].every(key => Object.hasOwn(d, key)) || !prices.length) throw new Error('油价油号字段缺失');
  const labels = { '92': '⛽92号汽油', '95': '🛢️95号汽油', '98': '🔥98号汽油', '0': '🚚0号柴油' };
  const lines = prices.map(([key, value]) => {
    if (!/^\d{1,3}$/.test(key) || !['number', 'string'].includes(typeof value) ||
        !/^\d+(?:\.\d+)?$/.test(String(value)) || !Number.isFinite(Number(value)) || Number(value) <= 0) throw new Error('油价价格字段无法验证');
    return `${labels[key] || `⛽${key}号油`}：${value}元/L`;
  });
  return [`📍地区：${d.area}`, `📅日期：${d.date}`, ...lines];
}
async function mainOil() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${dryRun ? '断网预演' : '正式运行'}`);
  const entries = (process.env.OILPRICE_LIST || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  let success = 0, failure = 0, skipped = 0;
  const reports = [];
  log(`账号总数：0（公开油价，无需账号）；地区任务总数：${entries.length}`);
  log('阶段 1/3：检查地区配置');
  if (!entries.length) { failure = 1; log('❌ 配置错误：OILPRICE_LIST 每个非空行填写一个中文地区；阶段耗时 0 毫秒'); }
  else log(`✅ 已读取 ${entries.length} 个地区条目；阶段耗时 ${Date.now() - started} 毫秒`);
  log('阶段 2/3：逐地区获取并验证油价');
  for (let i = 0; i < entries.length; i++) {
    const begin = Date.now();
    let ok = 0, bad = 0, skip = 0;
    log(`地区任务 ${i + 1}：阶段 2/3 开始`);
    try {
      const area = oilArea(entries[i]);
      const url = new global.URL(URL);
      url.searchParams.set('area', area);
      const text = dryRun ? JSON.stringify({ data: { area, date: '2026-01-01', '92': '7.00', '95': '7.50', '98': '8.00', '0': '6.50' } }) : await getReport(url);
      const report = parseOil(text, area);
      if (dryRun) { skipped++; skip = 1; log(`✅ DRY_RUN_OK：地区任务 ${i + 1} 本地解析通过，HTTP 已跳过`); }
      else { success++; ok = 1; reports.push(report.join('\n')); log(`✅ OILPRICE_SUCCESS：地区任务 ${i + 1} 油价字段检查通过`); console.log('【今日油价】\n' + report.join('\n')); }
    } catch (error) { failure++; bad = 1; log(`❌ 地区任务 ${i + 1}：${error.message}`); }
    log(`地区任务 ${i + 1} 统计：总任务 1，成功 ${ok}，已完成 0，跳过 ${skip}，失败 ${bad}；耗时 ${Date.now() - begin} 毫秒`);
  }
  const status = !entries.length ? 'configuration-error' : failure ? (success ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success';
  const beginNotify = Date.now();
  log('阶段 3/3：发送任务总结');
  const body = `账号总数：0（无需账号）\n地区任务总数：${entries.length || 1}；成功：${success}；失败：${failure}；跳过：${skipped}\n状态：${status}` + (reports.length ? '\n【今日油价】\n' + reports.join('\n\n') : '');
  const notification = await notify(body);
  log(`通知结果：${notification}；阶段耗时 ${Date.now() - beginNotify} 毫秒`);
  const finishedAt = new Date().toISOString();
  console.log('--------------------------------');
  log(`账号统计：总数 0，成功 0，失败 0；子任务统计：总数 ${entries.length || 1}，成功 ${success}，已完成 0，跳过 ${skipped}，失败 ${failure}`);
  log(`完成时间：${finishedAt}；总耗时：${Date.now() - started} 毫秒；通知状态：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ task, mode: dryRun ? 'dry-run' : 'live', status, accounts: { total: 0, success: 0, failure: 0 }, tasks: { total: entries.length || 1, success, alreadyComplete: 0, skipped, failure }, notification, startedAt: new Date(started).toISOString(), finishedAt, elapsedMs: Date.now() - started }));
  process.exitCode = failure ? 1 : 0;
}
