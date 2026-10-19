// name: Pixiv 收藏图片下载
// cron: 48 1 * * *
/*
name: Pixiv 收藏图片下载
cron: 48 1 * * *
来源：cloudcranes/some_scripts / Download_pixiv/index.js
上游提交：f62b50fe0a961ea8a8707682723b080c0a5d1142；许可：MIT。
合并参考：qluser-alan/some_scripts / Download_pixiv/index.js
参考提交：f62b50fe0a961ea8a8707682723b080c0a5d1142；参考许可：MIT。
维护目标：b4b3175bb52c98a5，保留规范脚本身份、参数和保存路径。
原始源码未附版权声明；保留上游归属，按 MIT 许可维护。
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
需要 Node.js >= 18；运行依赖 axios（公开 npm 包）。
PIXIV_ACCOUNTS：每行 用户公开UID|完整Cookie；UID留空时从收藏页面重定向获取。
Cookie 从本人登录 Pixiv 后浏览器开发者工具中 www.pixiv.net 请求的 Cookie 获取。
PIXIV_OUTPUT：明确指定图片保存目录；旧版当前目录 config.json 的 cookie/output/proxy 仍兼容。
PIXIV_DRY_RUN=1 完全断网且不写图片；QINGLONG_NOTIFY=0 关闭通知。
上游无定时声明；此 cron 为每天 03:00 的维护默认值，可在青龙调整。
*/
'use strict';
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["b4b3175bb52c98a5", "scripts/index.js", "index.js", "index"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const fs = require('node:fs');
const path = require('node:path');
const { pipeline } = require('node:stream/promises');
const { Transform } = require('node:stream');
const { fork } = require('node:child_process');
const started = Date.now();
const dry = process.env.PIXIV_DRY_RUN === '1';
const stats = { accounts: 0, success: 0, failed: 0, tasks: 0, downloaded: 0, skipped: 0, taskFailed: 0 };
function log(message) { console.log(`[${new Date().toTimeString().slice(0, 8)}] ${message}`); }
function safeTitle(value) { return String(value || '未命名').replace(/[\x00-\x1f\x7f/\\?%*:|"<>]/g, '_').replace(/^\.+$/, '_').slice(0, 100).trim() || '未命名'; }
// 两个独立阶段各最多三个并发任务，不依赖 p-queue 的模块版本。
function concurrencyQueue(limit) {
  const pending = []; let active = 0;
  function pump() {
    while (active < limit && pending.length) {
      const { task, resolve, reject } = pending.shift(); active++;
      Promise.resolve().then(task).then(resolve, reject).finally(() => { active--; pump(); });
    }
  }
  return task => new Promise((resolve, reject) => { pending.push({ task, resolve, reject }); pump(); });
}
function imageHeader(buffer) {
  return (buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) ||
    buffer.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10])) ||
    ['GIF87a', 'GIF89a'].includes(buffer.subarray(0, 6).toString()) ||
    (buffer.subarray(0, 4).toString() === 'RIFF' && buffer.subarray(8, 12).toString() === 'WEBP');
}
async function validFile(file) {
  let handle;
  try { handle = await fs.promises.open(file, 'r'); const info = await handle.stat(); const b = Buffer.alloc(12); await handle.read(b, 0, 12, 0); return info.isFile() && info.size >= 12 && imageHeader(b); }
  catch { return false; } finally { if (handle) await handle.close(); }
}
// 通知隔离到子进程，防止通知组件改变业务退出码或留下定时器。
// 预演仍调用青龙通知入口，但阻断子进程全部网络与派生进程。
function notificationWorker() {
  if (dry) {
    const deny = () => { throw new Error('断网预演禁止外部通信'); };
    for (const [moduleName, names] of [
      ['node:http', ['request', 'get']], ['node:https', ['request', 'get']],
      ['node:http2', ['connect']], ['node:net', ['connect', 'createConnection']],
      ['node:tls', ['connect']], ['node:dgram', ['createSocket']],
      ['node:dns', ['lookup', 'resolve', 'resolve4', 'resolve6']],
      ['node:child_process', ['spawn', 'fork', 'exec', 'execFile', 'spawnSync', 'execSync', 'execFileSync']]
    ]) {
      const module = require(moduleName); for (const name of names) module[name] = deny;
    }
    require('node:net').Socket.prototype.connect = deny;
    const dnsPromises = require('node:dns').promises;
    for (const name of Object.keys(dnsPromises)) if (typeof dnsPromises[name] === 'function') dnsPromises[name] = deny;
    globalThis.fetch = deny;
    if (globalThis.WebSocket) globalThis.WebSocket = deny;
    require('node:module').syncBuiltinESMExports();
  }
  process.once('message', async ({ file, body }) => {
    let result = '通知模块不可用';
    try {
      const module = require(file);
      if (typeof module.sendNotify === 'function') {
        await module.sendNotify('Pixiv 收藏图片下载', body);
        result = dry ? '预演通知入口已调用（网络已阻断）' : '已发送';
      }
    } catch { result = dry ? '预演通知入口已调用，外部投递被阻断或组件失败' : '投递失败'; }
    if (process.send) process.send(result, () => process.exit(0)); else process.exit(0);
  });
}
async function notify(body) {
  if (/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY || '1')) return '已关闭';
  if (dry) log(`预演本地通知：${body}`);
  const locations = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  for (const file of locations) {
    if (!fs.existsSync(file)) continue;
    const result = await new Promise(resolve => {
      let worker, timer, finished = false;
      const finish = value => { if (finished) return; finished = true; clearTimeout(timer); if (worker) worker.kill(); resolve(value); };
      try {
        // 账号凭据无须传入通知组件。
        const env = { ...process.env }; delete env.PIXIV_ACCOUNTS;
        delete env.NODE_OPTIONS;
        worker = fork(__filename, ['--notification-worker'], { env, stdio: ['ignore', 'ignore', 'ignore', 'ipc'], execArgv: [] });
        worker.on('message', finish);
        worker.on('error', () => finish('投递失败'));
        worker.on('exit', () => finish('投递失败'));
        timer = setTimeout(() => finish('通知超时'), 10000);
        worker.send({ file: path.resolve(file), body });
      } catch { finish('投递失败'); }
    });
    if (result === '通知模块不可用') continue;
    log(`通知状态：${result}`); return result;
  }
  log('⚠️ 未找到青龙 sendNotify.js；保留业务退出码'); return '通知模块不可用';
}
async function run() {
  log('========== Pixiv 收藏图片下载 ==========');
  log(`开始时间：${new Date(started).toISOString()}；模式：${dry ? '断网预演' : '正式下载'}`);
  let status = 'failure';
  try {
    log('阶段 1：参数检查');
    let config = {};
    if (fs.existsSync('config.json')) { try { config = JSON.parse(fs.readFileSync('config.json', 'utf8')); } catch { throw new Error('旧版 config.json 无法解析'); } }
    const raw = process.env.PIXIV_ACCOUNTS || (config.cookie ? `|${config.cookie}` : '');
    const accounts = raw.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => {
      const i = line.indexOf('|');
      if (i < 0) return { uid: '', cookie: '', invalid: true };
      const uid = line.slice(0, i).trim(); const cookie = line.slice(i + 1).trim();
      return { uid, cookie };
    });
    stats.accounts = accounts.length;
    log(`账号数量：${stats.accounts}；阶段 1 耗时：${Date.now() - started}ms`);
    if (!accounts.length) throw new Error('请配置 PIXIV_ACCOUNTS');
    const destination = process.env.PIXIV_OUTPUT || config.output;
    if (!destination && !dry) throw new Error('请明确配置 PIXIV_OUTPUT 或旧版 output');
    const root = path.resolve(destination || 'pixiv-dry-run');
    const proxy = config.proxy?.host ? config.proxy : false;
    let axios;
    if (!dry) { try { axios = require('axios'); } catch { throw new Error('缺少公开依赖 axios，请通过青龙依赖管理安装'); } }
    for (let index = 0; index < accounts.length; index++) {
      const accountStarted = Date.now(); const local = { tasks: 0, success: 0, skipped: 0, failed: 0 }; const account = accounts[index];
      log(`账号 ${index + 1} / 阶段 2：收藏读取`);
      try {
        if (account.invalid || (account.uid && !/^\d+$/.test(account.uid)) || !account.cookie || /[\r\n\x00]/.test(account.cookie)) throw new Error('账号 UID 或 Cookie 格式无效');
        if (dry) {
          log(`账号 ${index + 1}：参数有效；将分页读取公开收藏、以两个并发数为 3 的阶段获取全部图片页并校验下载；未发起网络请求或文件写入`);
          log(`账号 ${index + 1} / 阶段 3：下载流程预演通过；耗时 ${Date.now() - accountStarted}ms`);
        } else {
          const api = axios.create({ timeout: 20000, maxRedirects: 0, proxy, maxContentLength: 8 * 1024 * 1024, headers: { Cookie: account.cookie, Referer: 'https://www.pixiv.net/', 'User-Agent': 'Mozilla/5.0' }, validateStatus: () => true });
          async function request(url, extra = {}) { const r = await api.get(url, { ...extra, signal: AbortSignal.timeout(25000) }); return r; }
          let uid = account.uid;
          if (!uid) {
            const r = await request('https://www.pixiv.net/bookmark.php');
            if (![301, 302, 303, 307, 308].includes(r.status) || !r.headers.location) throw new Error('收藏身份重定向无效，请提供公开 UID');
            const target = new URL(r.headers.location, 'https://www.pixiv.net/');
            const match = target.pathname.match(/^\/users\/(\d+)(?:\/|$)/);
            if (target.origin !== 'https://www.pixiv.net' || !match) throw new Error('收藏身份无法核验，请提供公开 UID');
            uid = match[1]; log(`官方收藏重定向返回公开 UID：${uid}`);
          }
          const seen = new Set(); let offset = 0; let expectedTotal;
          const queuePages = concurrencyQueue(3); const queueDownloads = concurrencyQueue(3);
          const collectionStarted = Date.now();
          while (true) {
            const response = await request(`https://www.pixiv.net/ajax/user/${uid}/illusts/bookmarks`, { params: { tag: '', offset, limit: 100, rest: 'show', lang: 'zh' } });
            const data = response.data;
            if (response.status !== 200 || data?.error !== false || !Array.isArray(data.body?.works) || !Number.isSafeInteger(data.body.total) || data.body.total < 0) throw new Error('收藏接口未返回明确业务成功');
            const works = data.body.works;
            if (expectedTotal === undefined) expectedTotal = data.body.total;
            if (data.body.total !== expectedTotal || works.length > 100 || offset + works.length > expectedTotal) throw new Error('收藏分页总数变化或超出声明范围，请重试');
            log(`账号 ${index + 1} / 阶段 2：偏移 ${offset}，获取 ${works.length} 条；耗时 ${Date.now() - accountStarted}ms`);
            // 先验证整个分页，避免抛错后遗留仍在写入的队列任务。
            for (const work of works) {
              const id = String(work.id);
              if (!/^\d+$/.test(id) || seen.has(id)) throw new Error('收藏分页返回无效或重复作品');
              seen.add(id);
            }
            await Promise.all(works.map(work => queuePages(async () => {
              const id = String(work.id);
              const workStarted = Date.now();
              try {
                const pagesResponse = await request(`https://www.pixiv.net/ajax/illust/${id}/pages?lang=zh`);
                if (pagesResponse.status !== 200 || pagesResponse.data?.error !== false || !Array.isArray(pagesResponse.data.body) || !pagesResponse.data.body.length) throw new Error('图片页接口业务失败');
                const title = safeTitle(work.title); const folder = path.join(root, `${title}_${id}`);
                log(`账号 ${index + 1} / 阶段 3：作品 ${id}，${pagesResponse.data.body.length} 页`);
                await Promise.all(pagesResponse.data.body.map((page, pageIndex) => queueDownloads(async () => {
                  local.tasks++; stats.tasks++;
                  try {
                    const url = new URL(page.urls.original);
                    if (url.protocol !== 'https:' || !(url.hostname === 'pximg.net' || url.hostname.endsWith('.pximg.net')) || url.port || url.username || url.password) throw new Error('不允许的图片地址');
                    const extension = path.extname(url.pathname).toLowerCase();
                    if (!['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(extension)) throw new Error('不支持的图片类型');
                    const file = path.join(folder, `${title}_${pageIndex + 1}${extension}`);
                    const legacy = path.join(root, title, `${title}_${pageIndex + 1}${extension}`);
                    if (await validFile(file) || await validFile(legacy)) { local.skipped++; stats.skipped++; log(`账号 ${index + 1}：作品 ${id} 第 ${pageIndex + 1} 页已有有效图片，跳过；阶段 3 耗时 ${Date.now() - workStarted}ms`); return; }
                    await fs.promises.mkdir(folder, { recursive: true });
                    if ((await fs.promises.lstat(folder)).isSymbolicLink()) throw new Error('图片目录不能是符号链接');
                    const temp = `${file}.${process.pid}.part`;
                    try {
                      // 图片域不携带账户 Cookie，且禁止重定向。
                      const r = await axios.get(url.href, { responseType: 'stream', timeout: 20000, signal: AbortSignal.timeout(120000), maxRedirects: 0, proxy, headers: { Referer: 'https://www.pixiv.net/', 'User-Agent': 'Mozilla/5.0' }, validateStatus: () => true });
                      if (r.status !== 200 || !/^image\//i.test(r.headers['content-type'] || '')) { r.data.destroy(); throw new Error('图片 HTTP 状态或类型无效'); }
                      let size = 0;
                      const limiter = new Transform({ transform(chunk, encoding, callback) { size += chunk.length; callback(size > 100 * 1024 * 1024 ? new Error('图片超过大小限制') : null, chunk); } });
                      await pipeline(r.data, limiter, fs.createWriteStream(temp, { flags: 'wx' }));
                      const expected = r.headers['content-length'];
                      if ((expected !== undefined && Number(expected) !== size) || !await validFile(temp)) throw new Error('图片内容校验失败');
                      // 原子创建最终文件，避免与另一运行实例竞争时覆盖有效文件。
                      // 无效既有图片继续保持原来的修复能力；符号链接不能跟随写入。
                      try {
                        const existing = await fs.promises.lstat(file);
                        if (existing.isSymbolicLink() || !existing.isFile()) throw new Error('目标不是普通图片文件');
                        if (await validFile(file)) {
                          local.skipped++; stats.skipped++; log(`账号 ${index + 1}：作品 ${id} 第 ${pageIndex + 1} 页另一任务已完成，跳过`); return;
                        }
                        await fs.promises.unlink(file);
                      } catch (error) { if (error.code !== 'ENOENT') throw error; }
                      await fs.promises.link(temp, file);
                      local.success++; stats.downloaded++; log(`账号 ${index + 1}：作品 ${id} 第 ${pageIndex + 1} 页下载校验成功；阶段 3 耗时 ${Date.now() - workStarted}ms`);
                    } finally { await fs.promises.rm(temp, { force: true }); }
                  } catch { local.failed++; stats.taskFailed++; log(`❌ 账号 ${index + 1}：作品 ${id} 第 ${pageIndex + 1} 页下载失败（已脱敏）`); }
                })));
              } catch { local.tasks++; stats.tasks++; local.failed++; stats.taskFailed++; log(`❌ 账号 ${index + 1}：作品 ${id} 图片页读取失败（已脱敏）`); }
            })));
            offset += works.length;
            if (offset >= data.body.total) break;
            if (!works.length) throw new Error('收藏分页提前结束');
          }
          log(`账号 ${index + 1} / 阶段 2、3 完成；总耗时 ${Date.now() - collectionStarted}ms`);
          if (seen.size !== expectedTotal) throw new Error('收藏分页不完整');
          if (local.failed) throw new Error('存在失败子任务');
          log(`获取收藏成功，共 ${seen.size} 条；所有图片下载已完成或已存在有效文件`);
        }
        stats.success++;
      } catch { stats.failed++; log(`❌ 账号 ${index + 1} 失败：参数、依赖或业务检查未通过（详细响应不输出）`); }
      log(`账号 ${index + 1} 统计：总任务 ${local.tasks}，成功 ${local.success}，已完成 0，跳过 ${local.skipped}，失败 ${local.failed}；耗时 ${Date.now() - accountStarted}ms`);
    }
    status = stats.failed ? (stats.success ? 'partial-failure' : 'failure') : (dry ? 'dry-run' : 'success');
    process.exitCode = stats.failed ? 1 : 0;
  } catch (error) {
    status = 'configuration-error'; process.exitCode = 1;
    // 仅输出由本脚本构造的配置提示，不输出第三方异常。
    log(`❌ 配置检查失败：${error.message}`);
  }
  const body = `模式：${dry ? '断网预演' : '正式'}；状态：${status}；账号总数 ${stats.accounts}，成功 ${stats.success}，失败 ${stats.failed}；下载 ${stats.downloaded}，跳过 ${stats.skipped}，失败子任务 ${stats.taskFailed}`;
  const businessExitCode = process.exitCode || 0;
  const notification = await notify(body);
  log('----------------------------------------'); log(body);
  log(`完成时间：${new Date().toISOString()}；总耗时：${Date.now() - started}ms；通知：${notification}；最终状态：${status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify({ ...stats, mode: dry ? 'dry-run' : 'live', status, notification, durationMs: Date.now() - started }));
  // 通知模块不得改变业务退出码；也避免其遗留定时器使任务挂起。
  process.exit(businessExitCode);
}
if (process.argv.includes('--notification-worker')) notificationWorker();
else run().catch(() => { log('❌ 未预期运行错误（已脱敏）'); process.exit(1); });
