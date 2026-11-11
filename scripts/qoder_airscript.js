// name: Qoder每日签到
// cron: 17 8 * * *
// Qoder 每日自动签到 · 金山文档 AirScript 版（修复版）
// 独立 Node.js 维护版本；上游：wallechfox/qoder-checkin
// 合并来源：spirodelazz/ide-daily-checkin/scripts/qoder_checkin.py，MIT 授权。
// 合并来源：L0NE-6/Qoder-Daily/qoder_daily.py，MIT 授权。
// 合并来源：sunp-1/qoder-checkin/qoder_claim.py，MIT 授权。
// 合并来源：wzhu22750-lang/qoder_checkin/qoder_checkin_local.py，MIT 授权。
// 与 Python 版 qoder_core.py 对齐：优先用 accessToken，查活动 401 时才用
// refreshToken 续期，不再一上来就强制刷新。
// 上游授权：MIT。原文件没有单独的版权声明。
// MIT License
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.
/*
Node.js >=18，无第三方业务依赖。每天一次，沿用上游建议避开整点。
QODER_ACCOUNTS：每个非空行一个 JSON 对象，不用 & 或 @ 分隔账号。
字段：accessToken/access_token、refreshToken/refresh_token（至少一项），
device 的 clientType、machineOS、machineHostname、machineId、machineToken、
machineCode、machineType、version 八项均必填。原账号 name、uid 保留。
取得参数：在本人已登录的 Qoder 客户端查看本人授权请求的 Authorization
及 Cosy-* 头；按上述八项与对应头名称复制。刷新令牌从本人客户端登录凭据
中取得；不要上传给第三方。原 qoder_gettoken.py 导出的整行 JSON 也兼容，
本脚本不依赖该工具。中国区默认，国际区 QODER_REGION=global。
签到开关：账号 enabled=true 或 qiandao="是" 才领取，默认跳过（对应原 B 列）。
每账号可选 serverchan、pushplus、qywx 对应原 C/D/E 列；填本人通道令牌。
QODER_ACCOUNTS_FILE：可选显式指定的私有 JSONL 文件，优先于环境变量；
令牌刷新后原子写回此文件（权限 0600），相当于原 A 列写回。
仅使用环境变量时不写凭据，刷新令牌轮换后可能需要重新取得账号参数。
结果以日志及 TASK_SUMMARY 输出，代替原 F 列；不依赖金山文档应用。
QODER_DRY_RUN=1 完全断网且不写回：校验参数并模拟流程及通知。
QODER_ACTION=checkin（默认）或 refresh；也支持 --refresh-only。
QODER_ONLY 或 --only 指定从 1 开始的账号序号；--no-notify 关闭全部通知。
账号 region 可为 cn/global，未填沿用 QODER_REGION；不改变默认 cron。
国际区活动窗口北京时间 10:00 开启，可自行调整任务时间，不自动改动计划。
不查找本机组件、不下载软件、不自动生成设备身份；device 必须由本人取得。
功能清单与覆盖核对：原维护能力全部保留；强制刷新列表、仅刷新令牌、
指定账号、混合区域、通知链及幂等识别不变，仍逐项领取全部 CLAIM_BENEFIT。
本次来源核对：AirScript/core 使用同一活动及领取接口、设备头和刷新接口；
当前 qoder_daily.py 新增 403/业务码 105、10019901001 续期，中国区成功空表
用四个最小鉴权头复取一次，Pro /reward 只读查面值及 /api/v2/quota/usage
额度前后回读。本脚本保留既有 forceRefresh=true，合并这些兼容改进；
奖励面值和额度差额仅辅助核验，不能代替明确 CLAIMED 领取结果。
QODER_PRO_VERIFY=1 默认启用只读核验，可设 0 关闭；不减少既有领取能力。
QODER_PRO_UPGRADE=1 才额外领取列表中非 CLAIM_BENEFIT 的明确 Pro 活动，
默认 0 不扩大原候选的领取边界。不猜活动 ID，不打印兑换券或服务端原文。
QODER_WINDOW_RETRY=1 可启用北京时间 10:00-10:30 暂无活动时刷新列表，
默认 0 保持原候选单轮查询；QODER_WINDOW_RETRY_MAX 默认16、范围1至16，
QODER_WINDOW_RETRY_GAP 默认90秒、范围1至300秒，不重试领取请求。
兼容 QODER_TOKENS（中国区）和 QODER_GLOBAL_TOKENS（国际区），仅在未设
QODER_ACCOUNTS/私有文件时使用，每行 access 或 access|refresh 或
备注|access|refresh 或 备注|access|refresh|uid，绝不用 & 分账号。
拆分首个字段分隔符后保留剩余字段；含 | 的令牌请用规范 JSON 行避免歧义。
旧变量需 QODER_ENABLED=1 显式启用；device 从 QODER_COSY_CLIENT_TYPE、
QODER_COSY_MACHINE_OS/HOSTNAME/ID/TOKEN/CODE/TYPE、QODER_COSY_VERSION
取得，三项风控头还兼容 QODER_MACHINE_TOKEN/CODE/TYPE；不生成设备参数。
可选 PUSHPLUS_TOKEN、BARK_URL、WECOM_WEBHOOK、DINGTALK_WEBHOOK/SECRET
用于全局汇总通知，保留逐账号原有三种通知，全部服从总开关。
不将任意 409 当作成功，仅接受可核验 ALREADY_CLAIMED/replayed 业务结果。
取号脚本是 Windows 参数获取工具，02_checkin 是依赖入口，不另行发布。
QINGLONG_NOTIFY 默认 auto，本维护任务默认在通知名单内；1/true/yes/on
强制开启，0/false/no/off 关闭所有通知。auto 下 QINGLONG_NOTIFY_SCRIPTS
设置后替换默认名单，支持目录相对路径、文件名、catalogId、文件名通配符，
逗号、分号或空白分隔，* 全选，空值全关；dry-run 只模拟通知以保证断网。
QINGLONG_NOTIFY_DIR 可指定含 sendNotify.js 的青龙通知目录。
本轮功能盘点及来源差异核对（仅使用随任务提供的离线源码）：
qoder_claim.py 为每日活动任务，无内置 cron；提供只读 --status、领取全部奖励、
窗口内已领识别、最多20次间隔60秒重试、--once、--json；访问令牌来自
QODER_CLAIM_TOKEN/--token/--from-file 或 Windows 登录态。副作用为领取与续期。
其活动及刷新 URL、方法和 Cosy-ClientType 头与维护版相同，未发现需更换接口
的证据。维护版已覆盖领取、续期、窗口识别、混合地区及有界等待；合并缺少的
只读入口和参数兼容，默认单轮及原 cron 保留。只读模式不刷新、不领取、不写回。
QODER_ACTION=status 或 --status 查询已验证的活动状态、奖励及窗口，成功仅代表
查询完成。该模式需要有效访问令牌，忽略签到开关但保留 --only 账号选择。
--once 禁用可选开窗重试；--dry-run 等同 QODER_DRY_RUN=1，完全断网。
--json 额外保留原 verdict/detail/date/endpoint/campaigns 脱敏 JSON 字段，
日志及唯一 TASK_SUMMARY 仍输出；新增查询返回值不暴露原始响应。
QODER_CLAIM_TOKEN 可作为旧访问令牌变量，每非空行一个账号；配套设备参数
用 QODER_COSY_*，领取仍须 QODER_ENABLED=1。规范 QODER_ACCOUNTS 优先。
--token 显式提供单账号令牌；--from-file 显式读取本人导出的 JSON
{token,refreshToken,device,enabled,region}，token 兼容 accessToken；仅读不回写。
--base-url 仅接受两个官方 HTTPS 根地址并转换为地区，未指定时沿用维护版
中国区默认，不自动向另一地区转发凭据。Windows 解密/组件调用不适用于
独立维护脚本，凭据及设备头改为本人从已授权请求手工取得。
相关 local 脚本是10:05运行的 PAT 换 job token 后领取；本轮合入独立 PAT 凭据入口，
沿用现有账号的设备令牌链，PAT 账号仅在中国区使用来源中的最小鉴权头。daily 是同一每日领取/Pro 工作流，维护版已有
完整兼容功能及通知链，保留原开关。AirScript 是每日表格领取，原 A/B/C/D/E/F
行为已有 JSON 行、启用开关、三通知及结果输出替代。gettoken 是 Windows
参数获取工具，会打印并写 tokens.txt，不作为计划任务引入。
保留维护版 cron 17 8 * * *；活动开窗说明不自动变更现有计划。
本轮主来源功能：从 QODER_PAT 或隐式 qoder_pat.txt 取得 PAT，POST
/api/v1/jobToken/exchange 换任务令牌，兼容 personal_token/personal_access_token；
GET 活动、按有效窗口选择 CLAIM_BENEFIT、POST 领取、识别 replayed/CLAIMED；
建议北京时间每天10:05，暂未下发最多三轮等待。副作用为换令牌及领取。
维护版已有每日领取、窗口识别、显式有界等待，缺少 PAT 换令牌能力，故合入原任务。
参数：在 https://qoder.cn/account/integrations 创建本人 PAT（pt- 前缀），
规范 QODER_ACCOUNTS 每行可写 {"personalToken":"本人PAT","enabled":true,"region":"cn"}，
同一行可用 pat 或 personal_token 别名；无需设备头，不读取应用文件、不执行组件。
兼容 QODER_PAT：每非空行一个 PAT；仅在其他账号入口均未配置时使用，
须 QODER_ENABLED=1 授权兑换及领取。不要与同账号访问令牌重复配置。
不再隐式读取 qoder_pat.txt，私有文件请显式使用 QODER_ACCOUNTS_FILE 的 JSON 行。
PAT 模式只支持签到，status/refresh 请改用现有访问/刷新令牌模式，避免只读时兑换。
PAT 的第二字段仅在 HTTP 400/422 时尝试；鉴权拒绝及瞬时故障不反复提交 PAT。
PAT 领取只接受明确 CLAIMED、明确幂等结果或含正数 benefit.amount 的成功收据；
未知响应不再打印 OK。主来源原 OK claimed/OK already-claimed 标记保留。
默认计划仍为17 8 * * *，PAT 活动可将同一任务手动改至北京时间5 10 * * *；
--once 及 QODER_WINDOW_RETRY 的原语义不变，不静默增加等待或改动计划。
所有业务请求均自行通过 Node.js HTTPS 发出，凭据不发往其他地区或文本服务。
上次准备失败为引用不存在的私有上游路径；本次仅用提供的 input 源码，运行不依赖该路径。
*/
/*
本轮离线盘点：qoder_checkin.py 与 incoming_candidate.py 均查询全部普通活动、
领取 Credits、续期、空表最多3轮间隔20秒重查；支持 expiresAt 秒/毫秒/ISO、
JSON 账号及设备配置、企业微信/PushPlus/Webhook、silent/poll/silent-poll。
主来源本身无 cron；主控建议10:20主跑、15:00及20:30兜底，incoming 为11:06。
本规范脚本保留17 8 * * *，额外兜底可复用同一文件设置独立计划，不另发产品脚本。
同任务接口比对：活动 GET /sash/api/v1/me/campaigns、领取 POST .../{id}/claim、
刷新 POST /api/v1/deviceToken/refresh 与规范版相同，无更换接口的证据。
extract 只获取凭据并依赖 Windows 组件，不合入；signin/probe 为 WorkBuddy，
run_all 为跨应用调度，不合入。维护版原 PAT、双区、Pro、通知链、命令行全部保留。
QODER_EMPTY_RETRY/WAIT 显式配置才启用空表重查，默认保持规范版单轮；
次数至少1、等待至少0，非法整数使用来源默认3/20；--once 禁用所有等待重查。
QODER_CONFIG_FILE 显式指定 JSON 可含 device、refreshMarginH、notify，
不隐式读取本机文件。device 优先账号字段，其次环境变量，再其次显式配置。
QODER_ACCOUNTS 支持旧 JSON 数组、accounts 包装及 token/expires_at 别名；
显式账号文件继续优先并安全写回（兼容数组/包装），不自动写缓存或设备文件。
QODER_REFRESH_MARGIN_H 或显式配置 refreshMarginH 可开启临期刷新；
未配置时保持规范版优先访问令牌、鉴权失效才刷新的默认，失败可沿用未过期令牌。
QODER_LOG_FILE 显式指定时追加脱敏机器记录，不默认写文件；预演不写。
QYWX_TOKEN、PLUSPLUS_TOKEN、QODER_WEBHOOK 兼容新来源全局通知；
全局开关及断网预演始终生效。自定义通知仅接受 HTTPS，无重定向。
基址覆盖 QODER_BASE_URL/配置 baseUrls 仅允许同区域官方根地址，拒绝任意
凭据转发；保留原 --base-url 和逐账号区域，无客户端依赖或下载引导。
QODER_CACHE_FILE 不合入：规范版已有显式账号文件原子写回，避免并行持久化
覆盖轮换令牌；使用 QODER_ACCOUNTS_FILE 保存同账号全部配套参数。
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
    const identities = ["e034e75509550071", "scripts/qoder_airscript.js", "qoder_airscript.js", "qoder_airscript"];
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
const https = require('node:https');
const crypto = require('node:crypto');
const {spawn} = require('node:child_process');
const dry = process.argv.includes('--dry-run') || /^(1|true|yes|on)$/i.test(process.env.QODER_DRY_RUN || '');
const enabled = x => /^(1|true|yes|on)$/i.test(x || '');
const disabled = x => /^(0|false|no|off)$/i.test(x || '');
function notificationSelected() {
  if (process.argv.includes('--no-notify') || disabled(process.env.QINGLONG_NOTIFY)) return false;
  if (enabled(process.env.QINGLONG_NOTIFY)) return true;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return true;
  const names=['9cceef808f4e3500','scripts/qoder_checkin.py','qoder_checkin.py','2303ec2803cf2832','e034e75509550071','7dae37fb02629e65','d94f5f76e5dd357b','scripts/qoder_airscript.js','qoder_airscript.js',path.basename(__filename)];
  return process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(s=>{
    const pattern='^'+s.split('*').map(p=>p.split('?').map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('.')).join('.*')+'$';
    return names.some(n=>new RegExp(pattern).test(n));
  });
}
const notifyEnabled = notificationSelected();
let action='checkin', only=0, tokenArg, inputFile='', regionArg='', onceOnly=false;
const started = Date.now();
const fields = ['clientType','machineOS','machineHostname','machineId','machineToken','machineCode','machineType','version'];
const results = [];
let accounts = [], lines = [], file = '', base, configFailure = false;
let retryMax=16, retryGap=90, emptyTimes=1, emptyWait=20, refreshMargin=null;
let importedConfig={}, accountFileShape='lines';
const accountBase = a => a.region==='global' ? 'https://openapi.qoder.sh' : a.region==='cn' ? 'https://openapi.qoder.com.cn' : base;
const payload = d => d && typeof d.data==='object' && d.data && !Array.isArray(d.data) ? d.data : d;
const now = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
const log = s => console.log(`[${now()}] ${s}`);
const stamp = () => new Date().toISOString();
const nonempty = x => typeof x === 'string' && x.trim() && !/[\x00-\x1f\x7f]/.test(x);
function request(url, method, headers, body, allowSchemaError=false) {
  if (dry) throw new Error('预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const bytes = body === undefined ? null : Buffer.from(JSON.stringify(body));
    const req = https.request(url, {method, headers: {...headers, ...(bytes ? {'Content-Length':bytes.length} : {})}}, res => {
      let size=0, chunks=[];
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 1048576) { req.destroy(); reject(new Error('响应超出大小限制')); }
        else chunks.push(chunk);
      });
      res.on('error', () => reject(new Error('响应读取失败')));
      res.on('end', () => {
        let data;
        try { data=JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch {
          if ([401,403].includes(res.statusCode) || allowSchemaError && [400,422].includes(res.statusCode)) { resolve({status:res.statusCode,data:null}); return; }
          reject(new Error(`HTTP ${res.statusCode}：响应不是有效 JSON`)); return;
        }
        resolve({status:res.statusCode, data});
      });
    });
    const timer = setTimeout(() => {req.destroy(); reject(new Error('请求超时'));},30000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败')));
    if (bytes) req.write(bytes);
    req.end();
  });
}
const patOf = a => a.personalToken || a.pat || a.personal_token;
function headers(a, token) {
  if (patOf(a)) return {'Accept':'application/json','Cosy-ClientType':'10','User-Agent':'Qoder',...(token ? {Authorization:`Bearer ${token}`} : {})};
  const h = {'Accept':'application/json','Content-Type':'application/json','User-Agent':'Qoder/claim'};
  for (const f of fields) h[`Cosy-${f[0].toUpperCase()}${f.slice(1)}`] = a.device[f];
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}
function businessOK(d) {
  return d && typeof d === 'object' && !Array.isArray(d) &&
    ['code','Code'].every(k=>!Object.hasOwn(d,k) || [0,200,'0','200'].includes(d[k])) && d.success !== false;
}
function identity(d, a) {
  const objects = [d, d && d.user, d && d.account];
  const secrets = [a,...accounts].filter(x=>x && typeof x==='object').flatMap(x=>
    [x.token,x.personalToken,x.pat,x.personal_token,x.accessToken,x.access_token,x.refreshToken,x.refresh_token,x.device?.machineToken,x.device?.machineCode,x.device?.machineId,x.device?.machineHostname,x.serverchan,x.pushplus,x.qywx]);
  secrets.push(...['PUSHPLUS_TOKEN','BARK_URL','WECOM_WEBHOOK','DINGTALK_WEBHOOK','DINGTALK_SECRET','QYWX_TOKEN','PLUSPLUS_TOKEN','QODER_WEBHOOK'].map(k=>process.env[k]));
  secrets.push(...Object.values(importedConfig.device || {}),...Object.values(importedConfig.notify || {}));
  const protectedValues=secrets.filter(nonempty);
  for (const obj of objects) {
    if (!obj || typeof obj !== 'object') continue;
    for (const key of ['nickname','username','displayName','uid']) {
      if (obj[key] == null || typeof obj[key] === 'object') continue;
      const v=String(obj[key]);
      // 官方非敏感身份原样显示；疑似手机号或凭据、控制字符不进入日志。
      if (v && !/[\x00-\x1f\x7f]/.test(v) && (key==='uid' || !/\+?\d{11,}/.test(v)) && !protectedValues.some(s=>v.includes(s))) log(`官方${key}：${v}`);
    }
  }
}
async function stage(r, title, action) {
  const t=Date.now(); r.total++;
  log(`账号${r.account} 阶段${r.total} ${title} 开始`);
  try { const value=await action(); r.success++; log(`✅ 账号${r.account} ${title} 完成，耗时${Date.now()-t}毫秒`); return value; }
  catch (e) {r.failed++; log(`❌ 账号${r.account} ${title}：${e.message}，耗时${Date.now()-t}毫秒`); throw e;}
}
function persist(index,a) {
  if (!file) {log('⚠️ 刷新令牌仅在本次内存中使用；未配置账号文件写回'); return;}
  const updated=lines.slice(); updated[index]=JSON.stringify(a);
  const temp=`${file}.${process.pid}.tmp`;
  const doc=accountFileShape==='array' ? updated.map(JSON.parse) : accountFileShape==='wrapped' ? {...importedConfig.accountDocument,accounts:updated.map(JSON.parse)} : null;
  try {fs.writeFileSync(temp,doc ? JSON.stringify(doc)+'\n' : updated.join('\n')+'\n',{mode:0o600,flag:'wx'}); fs.renameSync(temp,file); lines=updated;}
  catch {try {fs.unlinkSync(temp);} catch {} throw new Error('私有账号文件写回失败');}
  log('刷新令牌已写回指定私有账号文件');
}
async function exchangePat(a) {
  // 仅依据提供的主来源兼容两种字段，不把网络或鉴权错误当字段错误重试。
  const pat=patOf(a);
  for (const field of ['personal_token','personal_access_token']) {
    const q=await request(accountBase(a)+'/api/v1/jobToken/exchange','POST',
      {'Content-Type':'application/json','Accept':'application/json','User-Agent':'qoder/1.1.47'}, {[field]:pat},true);
    log(`PAT 兑换任务令牌 HTTP ${q.status}`);
    if ([400,422].includes(q.status) && field==='personal_token') continue;
    const d=payload(q.data);
    if (q.status!==200 || !businessOK(q.data) || !businessOK(d)) throw new Error(`PAT 兑换失败：HTTP ${q.status} 或业务拒绝；请在官方集成页面检查本人 PAT`);
    const token=d.token || d.job_token || d.jobToken;
    if (!nonempty(token) || token===pat || [q.data,d].some(b=>b.failureCode || b.errorCode)) throw new Error('PAT 兑换响应缺少有效任务令牌或业务拒绝');
    a.accessToken=token; // 短期令牌仅在内存中使用，不写回 PAT 文件。
    identity(q.data,a); if (d!==q.data) identity(d,a);
    return token;
  }
  throw new Error('PAT 兑换字段不被接口接受');
}
function epochSeconds(v) {
  if (typeof v==='boolean') return null;
  if (v==null || v==='') return null;
  const n=typeof v==='number' || /^\d+(?:\.\d+)?$/.test(v) ? Number(v) : Date.parse(v)/1000;
  if (!Number.isFinite(n) || n<0) return null;
  return n>=1e12 ? n/1000 : n;
}
function tokenExpiry(token) {
  try {return epochSeconds(JSON.parse(Buffer.from(String(token).split('.')[1],'base64url').toString()).exp);} catch {return null;}
}
function parseAccounts(raw) {
  raw=raw.replace(/^\uFEFF/,'').trim();
  let doc; try {doc=JSON.parse(raw);} catch {}
  if (Array.isArray(doc)) {accountFileShape='array'; return doc;}
  if (doc && Array.isArray(doc.accounts)) {accountFileShape='wrapped'; importedConfig.accountDocument=doc; return doc.accounts;}
  return raw.split(/\r?\n/).filter(x=>x.trim()).map(line=>{try{return JSON.parse(line);}catch{return null;}});
}
function normalizeAccount(a) {
  if (!a || typeof a!=='object' || Array.isArray(a)) return a;
  return {...a,accessToken:a.accessToken || a.access_token || a.token,
    refreshToken:a.refreshToken || a.refresh_token,expiresAt:a.expiresAt ?? a.expires_at,
    device:{...legacyDevice(),...(a.device || {})}};
}
function retryInteger(name,fallback,min) {
  const raw=process.env[name];
  return Math.max(min,/^[+-]?\d+$/.test(raw || '') && Number.isSafeInteger(Number(raw)) ? Number(raw) : fallback);
}
function normalizePatCampaign(c) {
  if (!c || typeof c!=='object' || Array.isArray(c)) throw new Error('PAT 活动项目契约不符');
  const start=epochSeconds(c.startAt ?? c.beginAt), end=epochSeconds(c.endAt);
  const active=(start===null || start<=Date.now()/1000) && (end===null || Date.now()/1000<=end);
  const invalid=[c.startAt ?? c.beginAt,c.endAt].some(v=>v!=null && epochSeconds(v)===null);
  return {...c, startAt:start, endAt:end,
    claimStatus:!active || invalid ? 'EXPIRED' : c.claimStatus || (c.actionType==='CLAIM_BENEFIT' ? 'CLAIMABLE' : 'UNKNOWN')};
}
async function refresh(a,index) {
  const rt=a.refreshToken || a.refresh_token;
  if (!rt) throw new Error('缺少刷新令牌，请重新登录取得参数');
  const ep=rt.startsWith('jrt-') ? '/api/v1/jobToken/refresh' : '/api/v1/deviceToken/refresh';
  const q=await request(accountBase(a)+ep,'POST',headers(a,''),{refresh_token:rt});
  if (q.status!==200 || !businessOK(q.data)) throw new Error(`刷新失败：HTTP ${q.status} 或业务拒绝`);
  const d=payload(q.data);
  if (!businessOK(d)) throw new Error('刷新业务拒绝');
  const token=d.token || d.accessToken || d.access_token || d.device_token || d.deviceToken;
  if (!nonempty(token)) throw new Error('刷新响应缺少有效访问令牌');
  const rtNew=d.refreshToken || d.refresh_token || rt;
  if (!nonempty(rtNew)) throw new Error('刷新响应令牌格式无效');
  a.expiresAt=epochSeconds(d.expiresAt ?? d.expires_at) || tokenExpiry(token);
  a.accessToken=token; a.refreshToken=rtNew; delete a.access_token; delete a.refresh_token;
  identity(q.data,a); if (d!==q.data) identity(d,a);
  persist(index,a); return token;
}
const campaignId = c => c.campaignId || c.id || c.campaignKey;
function campaignBody(q) {
  if (q.status!==200 || !businessOK(q.data) || !businessOK(payload(q.data))) return null;
  // 已有标准及 data 包装均兼容；不把未知响应形状当作成功空表。
  for (const d of [payload(q.data),q.data]) {
    if (Array.isArray(d?.campaigns)) return {...d,campaigns:d.campaigns};
    if (d?.showCampaign===false && d.campaigns==null) return {...d,campaigns:[]};
  }
  return null;
}
function authDead(q) {
  return [401,403].includes(q.status) || [q.data,payload(q.data)].some(d=>
    d && [d.code,d.Code].some(code=>['105','10019901001'].includes(String(code))));
}
function minimalHeaders(a,token) {
  if (patOf(a)) return {...headers(a,token),'Content-Type':'application/json'};
  return {'Authorization':`Bearer ${token}`,'Cosy-ClientType':a.device.clientType,'User-Agent':'Qoder','Content-Type':'application/json'};
}
async function queryCampaigns(a,index,r,allowRefresh=true) {
  let token=a.accessToken || a.access_token;
  const once=async()=>{
    const q=await request(accountBase(a)+'/sash/api/v1/me/campaigns'+(patOf(a)?'':'?forceRefresh=true'),'GET',headers(a,token));
    log(`账号${r.account} 活动查询 HTTP ${q.status}`);
    const d=campaignBody(q);
    if (!patOf(a) && accountBase(a)==='https://openapi.qoder.com.cn' && d && !d.campaigns.length) {
      log(`账号${r.account} 中国区明确空列表，按上游四头协议只读重查一次`);
      // 原强制刷新请求保留，补取沿用当前主来源不带 forceRefresh 的四头请求。
      const retry=await request(accountBase(a)+'/sash/api/v1/me/campaigns','GET',minimalHeaders(a,token));
      log(`账号${r.account} 中国区补取 HTTP ${retry.status}`);
      if (campaignBody(retry)?.campaigns.length===0) return q;
      return retry;
    }
    return q;
  };
  let q=await once();
  if (allowRefresh && !patOf(a) && authDead(q) && (a.refreshToken || a.refresh_token)) {
    log(`账号${r.account} HTTP 或已知业务码表示鉴权失效，续期后仅重试一次`);
    token=await refresh(a,index); q=await once();
  }
  const d=campaignBody(q);
  if (!d) throw new Error(`活动查询失败或响应契约不符（HTTP ${q.status}）`);
  identity(q.data,a); if(d!==q.data) identity(d,a);
  log(`账号${r.account} 返回活动${d.campaigns.length}项`);
  return {...q,data:patOf(a) ? {...d,campaigns:d.campaigns.map(normalizePatCampaign)} : d};
}
function windowActive() {
  const d=new Date(Date.now()+8*3600000);
  return d.getUTCHours()===10 && d.getUTCMinutes()<30;
}
const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));
function looksPro(c) {
  return ['campaignKey','actionType','title','name','campaignName'].some(k=>/pro|upgrade/i.test(String(c[k] || ''))) ||
    (String(c.benefit?.kind).toUpperCase()==='CREDITS' && Number(c.benefit.amount)>=1000);
}
async function diagnostic(r,title,fn) {
  const t=Date.now(); r.total++;
  log(`账号${r.account} 阶段${r.total} ${title} 开始`);
  try {const value=await fn(); r.success++; log(`✅ 账号${r.account} ${title} 完成，耗时${Date.now()-t}毫秒`); return value;}
  catch {r.skipped++; log(`⚠️ 账号${r.account} ${title} 不可用，不改变领取判定，耗时${Date.now()-t}毫秒`); return null;}
}
async function rewardOf(a,c,token) {
  const id=campaignId(c);
  if (!['string','number'].includes(typeof id) || !String(id)) throw new Error('缺少活动标识');
  // 奖励页只读接口按来源仅用鉴权及客户端头，不发送设备身份。
  const q=await request(accountBase(a)+'/sash/api/v1/me/campaigns/'+encodeURIComponent(String(id))+'/reward','GET',
    {...minimalHeaders(a,token),Accept:'application/json','Accept-Language':'zh-CN',Origin:accountBase(a)});
  const d=payload(q.data);
  if (q.status!==200 || !businessOK(q.data) || !businessOK(d)) throw new Error('奖励查询失败');
  identity(q.data,a); if(d!==q.data) identity(d,a);
  const b=d.benefit && typeof d.benefit==='object' ? d.benefit : d;
  const amount=Number(b.amount);
  if (b.amount==null || !Number.isFinite(amount) || amount<0) throw new Error('奖励面值未知');
  return {kind:String(d.kind || b.kind || '').toUpperCase(),amount};
}
async function quotaRemaining(a,token) {
  const q=await request(accountBase(a)+'/api/v2/quota/usage','GET',headers(a,token));
  const d=payload(q.data);
  if (q.status!==200 || !businessOK(q.data) || !businessOK(d)) throw new Error('额度查询失败');
  identity(q.data,a); if(d!==q.data) identity(d,a);
  const pools=[d.userQuota,d.addOnQuota,d.orgResourcePackage,...(Array.isArray(d.dedicatedResourcePackages)?d.dedicatedResourcePackages:[])];
  const values=pools.filter(p=>p && p.remaining!=null).map(p=>Number(p.remaining));
  if (!values.length || values.some(n=>!Number.isFinite(n))) throw new Error('额度响应契约不符');
  return values.reduce((n,v)=>n+v,0);
}
const claimFailures={
  REDEMPTION_CODE_OUT_OF_STOCK:'今日名额已发完', SAME_PERSON_ALREADY_CLAIMED:'同一设备身份下其他账号已领取',
  CAMPAIGN_NOT_ACTIVE:'活动尚未开放或已结束', ACHIEVEMENT_NOT_COMPLETED:'活动条件尚未完成',
  RISK_BLOCKED:'设备风控未通过，请更新本人设备头', RISK_DEPENDENCY_UNAVAILABLE:'设备风控依赖暂不可用'
};
function claimVerdict(q, patMode=false) {
  const d=payload(q.data);
  const bodies=[d,q.data].filter(x=>x && typeof x==='object');
  const replay=bodies.some(b=>b.replayed===true || ['ALREADY_CLAIMED','REPLAYED'].includes(b.result) ||
    ['ALREADY_CLAIMED','REPLAYED'].includes(b.failureCode) || ['ALREADY_CLAIMED','REPLAYED'].includes(b.errorCode));
  if ([200,201,409].includes(q.status) && replay && (q.status===409 || businessOK(q.data) && businessOK(d))) return 'already';
  const failure=bodies.some(b=>b.failureCode || b.errorCode);
  const reason=bodies.map(b=>claimFailures[b.failureCode] || claimFailures[b.errorCode]).find(Boolean);
  if (failure) throw new Error(reason || `领取业务拒绝：HTTP ${q.status}`);
  if ([200,201].includes(q.status) && businessOK(q.data) && businessOK(d) && (d.status==='CLAIMED' || patMode && d.status==null && d.benefit && Number.isFinite(Number(d.benefit.amount)) && Number(d.benefit.amount)>0)) return 'claimed';
  throw new Error(reason || `领取未确认：HTTP ${q.status}`);
}
function legacyDevice() {
  const suffix={clientType:'CLIENT_TYPE',machineOS:'MACHINE_OS',machineHostname:'MACHINE_HOSTNAME',machineId:'MACHINE_ID',machineToken:'MACHINE_TOKEN',machineCode:'MACHINE_CODE',machineType:'MACHINE_TYPE',version:'VERSION'};
  return Object.fromEntries(fields.map(f=>[f,process.env['QODER_COSY_'+suffix[f]] ||
    (['machineToken','machineCode','machineType'].includes(f) ? process.env['QODER_'+suffix[f]] : '') || importedConfig.device?.[f] || (f==='clientType'?'10':'')]));
}
function legacyAccounts(raw,region) {
  const first=s=>{const i=s.indexOf('|'); return i<0?[s,'',false]:[s.slice(0,i),s.slice(i+1),true];};
  const isToken=s=>/^(dt-|drt-|jt-|jrt-|eyJ)/.test(s) || s.length>80 || s.split('.').length>=3;
  return (raw || '').split(/\r?\n/).map(s=>s.trim()).filter(s=>s && !s.startsWith('#')).map(line=>{
    let [head,tail,has]=first(line), name='', accessToken=head, refreshToken='', uid='';
    if (has) {
      if (isToken(head) || !tail.includes('|') && !isToken(tail)) refreshToken=tail;
      else {name=head; const parts=first(tail); accessToken=parts[0]; refreshToken=parts[1];
        // 旧四字段格式明确规定最后一项为公开 UID；含分隔符凭据请改用 JSON。
        if (parts[2] && refreshToken.includes('|')) [refreshToken,uid]=first(refreshToken);
      }
    }
    return {name,accessToken,refreshToken,uid,region,device:legacyDevice(),enabled:enabled(process.env.QODER_ENABLED)};
  });
}
async function one(a,index) {
  const t=Date.now(); const r={account:index+1,total:0,success:0,alreadyComplete:0,skipped:0,failed:0,status:'failure',credits:0}; results.push(r);
  try {
    await stage(r,'参数校验',async()=>{
      if (!a || typeof a!=='object' || Array.isArray(a)) throw new Error('账号行必须是 JSON 对象');
      if (a.region!==undefined && !['cn','global'].includes(a.region)) throw new Error('账号区域必须为 cn 或 global');
      if (patOf(a) && accountBase(a)!=='https://openapi.qoder.com.cn') throw new Error('PAT 来源仅支持中国区，不向国际区转发');
      if (!patOf(a) && (!a.device || fields.some(f=>!nonempty(a.device[f])))) throw new Error('device 八项参数必须为非空单行字符串');
      if (!nonempty(patOf(a)) && !nonempty(a.accessToken || a.access_token) && !nonempty(a.refreshToken || a.refresh_token)) throw new Error('至少提供一项有效访问或刷新令牌');
      for (const k of ['personalToken','pat','personal_token','accessToken','access_token','refreshToken','refresh_token','serverchan','pushplus','qywx']) if (a[k]!==undefined && a[k]!=='' && !nonempty(a[k])) throw new Error('凭据必须为单行字符串');
    });
    if (only && index+1!==only) {r.skipped++; r.status='skipped'; log(`⏭️ 账号${index+1} 不在指定执行范围`); return;}
    if (action!=='status' && a.enabled!==true && a.qiandao!=='是') {r.skipped++; r.status='skipped'; log(`⏭️ 账号${index+1} 签到未启用`); return;}
    if (patOf(a) && action!=='checkin') await stage(r,'PAT 动作校验',async()=>{throw new Error('PAT 仅支持签到；只读或仅刷新请使用访问或刷新令牌账号');});
    if (action==='refresh' && !nonempty(a.refreshToken || a.refresh_token)) {await stage(r,'刷新参数校验',async()=>{throw new Error('仅刷新模式必须提供刷新令牌');});}
    if (action==='status' && !nonempty(a.accessToken || a.access_token)) {await stage(r,'只读参数校验',async()=>{throw new Error('只读模式必须提供有效访问令牌，不执行刷新');});}
    if (dry) {await stage(r,'断网流程预演',async()=>log(patOf(a) ? '将用 PAT 兑换任务令牌并领取中国区活动；本次未发请求、未读取隐式凭据文件、未写回' : action==='status' ? '将只读查询活动状态、奖励和窗口；本次未发请求、未刷新、未领取、未写回' : action==='refresh' ? '将仅刷新令牌；本次未发请求、未写回' : '将优先使用访问令牌，必要时刷新，强制刷新活动；中国区空表补取，逐项领取，Pro 只读核验；本次未发请求、未写回')); r.status='dry-run'; return;}
    if (action==='status') {
      const q=await stage(r,'只读查询活动',()=>queryCampaigns(a,index,r,false));
      await stage(r,'整理活动状态',async()=>{
        r.campaigns=q.data.campaigns.map((c,i)=>{
          if (!c || typeof c!=='object') throw new Error('活动项目契约不符');
          const status=['CLAIMABLE','CLAIMED','PENDING','EXPIRED'].includes(c.claimStatus) ? c.claimStatus : 'UNKNOWN';
          const amount=Number(c.benefit?.amount);
          const time=v=>{const n=epochSeconds(v);return n!==null && n>0 && n<8640000000000 ? new Date(n*1000).toISOString() : null;};
          return {index:i+1,status,amount:c.benefit?.amount!=null && Number.isFinite(amount) && amount>=0 ? amount : null,startAt:time(c.startAt),endAt:time(c.endAt)};
        });
        for (const c of r.campaigns) log(`账号${r.account} 活动${c.index} 状态${c.status} 奖励${c.amount ?? '未知'} Credits 窗口${c.startAt || '未知'} 至 ${c.endAt || '未知'}`);
      });
      r.status='success'; return;
    }
    if (action==='refresh') {await stage(r,'仅刷新令牌',()=>refresh(a,index)); r.status='success'; return;}
    let token=a.accessToken || a.access_token;
    if (patOf(a)) token=await stage(r,'PAT 兑换任务令牌',()=>exchangePat(a));
    else if (!token) token=await stage(r,'获取访问令牌',()=>refresh(a,index));
    else if (refreshMargin!==null && (a.refreshToken || a.refresh_token)) {
      const expires=epochSeconds(a.expiresAt) || tokenExpiry(token);
      if (expires && expires-Date.now()/1000<=refreshMargin*3600) {
        const refreshed=await diagnostic(r,'临期续期',()=>refresh(a,index));
        if (refreshed) token=refreshed;
        else if (expires<=Date.now()/1000) await stage(r,'过期令牌检查',async()=>{throw new Error('访问令牌过期且刷新失败，请重新获取本人凭据');});
        else log(`账号${r.account} 刷新失败，沿用未过期访问令牌`);
      }
    }
    let q=await stage(r,'查询活动',()=>queryCampaigns(a,index,r));
    for (let attempt=1; !onceOnly && attempt<emptyTimes && !q.data.campaigns.some(c=>c?.actionType==='CLAIM_BENEFIT'); attempt++) {
      await stage(r,'空活动等待',async()=>{log(`账号${r.account} 无普通活动，第${attempt+1}/${emptyTimes}轮，等待${emptyWait}秒`); await sleep(emptyWait*1000);});
      q=await stage(r,'空活动重新查询',()=>queryCampaigns(a,index,r));
    }
    const eligible=c=>c && (c.actionType==='CLAIM_BENEFIT' || accountBase(a)==='https://openapi.qoder.com.cn' && enabled(process.env.QODER_PRO_UPGRADE) && looksPro(c));
    for (let attempt=0; !onceOnly && enabled(process.env.QODER_WINDOW_RETRY) && attempt<retryMax && windowActive() &&
      !q.data.campaigns.some(c=>eligible(c) && ['CLAIMABLE','CLAIMED'].includes(c.claimStatus)); attempt++) {
      await stage(r,'等待活动开窗',async()=>{
        // 不跨越北京时间 10:30 继续派发重试。
        const bj=new Date(Date.now()+8*3600000);
        const remaining=(30-bj.getUTCMinutes())*60000-bj.getUTCSeconds()*1000-bj.getUTCMilliseconds();
        const delay=Math.min(retryGap*1000,Math.max(0,remaining));
        log(`账号${r.account} 暂未下发，等待${Math.ceil(delay/1000)}秒`); await sleep(delay);
      });
      if (!windowActive()) break;
      q=await stage(r,'开窗重新查询',()=>queryCampaigns(a,index,r));
    }
    token=a.accessToken || a.access_token;
    const benefits=q.data.campaigns.filter(eligible);
    const claimable=benefits.filter(c=>c.claimStatus==='CLAIMABLE');
    const verify=!disabled(process.env.QODER_PRO_VERIFY) && accountBase(a)==='https://openapi.qoder.com.cn';
    let probes=0;
    for (const c of claimable) {
      try {await stage(r,'领取活动',async()=>{
        const cid=campaignId(c);
        if (!['string','number'].includes(typeof cid) || !String(cid)) throw new Error('活动缺少标识');
        let pro=looksPro(c);
        if (verify && (pro || probes<5)) {
          probes++;
          const reward=await diagnostic(r,'只读核验奖励面值',()=>rewardOf(a,c,token));
          if (reward) {pro=pro || reward.kind==='CREDITS' && reward.amount>=1000; log(`账号${r.account} 奖励面值${reward.amount}，${pro?'识别为 Pro 升级候选':'普通活动'}`);}
        }
        const before=verify && pro ? await diagnostic(r,'领取前回读总剩余额度',()=>quotaRemaining(a,token)) : null;
        const cr=await request(accountBase(a)+'/sash/api/v1/me/campaigns/'+encodeURIComponent(String(cid))+'/claim','POST',{...headers(a,token),Origin:accountBase(a)},patOf(a) ? undefined : {});
        log(`账号${r.account} 领取 HTTP ${cr.status}`);
        const verdict=claimVerdict(cr,!!patOf(a));
        const d=payload(cr.data);
        identity(cr.data,a); if(d!==cr.data) identity(d,a);
        if (verdict==='already') {if(patOf(a)) log('OK already-claimed'); r.alreadyComplete++; log('☑️ 服务端确认活动已领取，未重复计入 Credits'); return;}
        if (verify && pro) {
          const after=await diagnostic(r,'领取后回读总剩余额度',async()=>{await sleep(2000); return quotaRemaining(a,token);});
          if (before!==null && after!==null) {const delta=after-before; log(delta>0 ? `账号${r.account} Pro 额度回读增加 ${delta}` : `账号${r.account} Pro 领取已确认，额度暂未增加，待到账核验`);}
          else log(`账号${r.account} Pro 领取已确认，额度回读不可用，到账待核验`);
        }
        const amount=Number(d.benefit?.amount ?? c.benefit?.amount ?? 0);
        if (Number.isFinite(amount)) r.credits+=amount;
        if (patOf(a)) log(`OK claimed +${Number.isFinite(amount) ? amount : 0} credits`);
        log(`领取已确认，累计 ${r.credits.toLocaleString('en-US')} Credits`);
        const days=Number(d.benefit?.validity?.days);
        if(Number.isFinite(days) && days>0) log(`奖励有效期 ${days} 天`);
      });} catch {} // 各活动独立执行，保留失败计数。
    }
    if (r.failed) r.status='failure';
    else if (claimable.length) r.status='success';
    else {
      const seconds=Date.now()/1000;
      if (benefits.some(b=>b.claimStatus==='CLAIMED' && (epochSeconds(b.startAt) ?? 0)<=seconds && (patOf(a) && b.endAt===null || seconds<(epochSeconds(b.endAt) ?? 0)))) {r.alreadyComplete++; r.status='already-complete'; if(patOf(a)) log('OK already-claimed'); log('☑️ 今日已领取');}
      else {r.skipped++; r.status='unavailable'; if ((a.region || process.env.QODER_REGION)==='global') log('国际区活动窗口北京时间 10:00 开启，暂未下发不视为领取成功'); log(benefits.length ? '⏭️ 活动待下发，等下轮' : '⏭️ 活动未开放');}
    }
  } catch {r.status='failure';}
  finally {r.elapsedMs=Date.now()-t; log(`账号${r.account} 统计：总任务${r.total} 成功${r.success} 已完成${r.alreadyComplete} 跳过${r.skipped} 失败${r.failed} 耗时${r.elapsedMs}毫秒 状态${r.status}`);}
}
function sendQinglong(modulePath,title,body) {
  if (dry) throw new Error('预演禁止调用通知模块');
  // 使用同一 Node.js 运行时隔离可选青龙模块的输出，防止它打印配置或响应。
  const program=`let raw='';process.stdin.setEncoding('utf8');process.stdin.on('data',c=>raw+=c);process.stdin.on('end',async()=>{try{const p=JSON.parse(raw),m=require(process.argv[1]);if(typeof m.sendNotify!=='function')throw Error();const r=await m.sendNotify(p.title,p.body);process.exit(r===false?1:0);}catch{process.exit(1);}});`;
  return new Promise((resolve,reject)=>{
    const child=spawn(process.execPath,['-e',program,path.resolve(modulePath)],{stdio:['pipe','ignore','ignore']});
    const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('通知超时'));},30000);
    child.on('error',()=>{clearTimeout(timer);reject(new Error('通知执行失败'));});
    child.on('close',code=>{clearTimeout(timer);if(code===0) resolve();else reject(new Error('通知发送失败'));});
    child.stdin.on('error',()=>{});
    child.stdin.end(JSON.stringify({title,body}));
  });
}
async function notifications(summary) {
  if (!notifyEnabled) {log('⏭️ 通知已关闭'); return 'disabled';}
  if (dry) {log(`⏭️ 断网预演：青龙及账号通知仅模拟；账号总数${summary.accounts} 成功${summary.succeeded} 失败${summary.failed} 状态${summary.status}`); return 'dry-run';}
  const title='Qoder每日签到';
  const body=`账号总数 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${summary.failed}，跳过 ${summary.skipped}，未确认领取 ${summary.unverified}；状态 ${summary.status}`;
  let delivered=false, failure=false;
  for (let i=0;i<accounts.length;i++) {
    const a=accounts[i]; if (!a || typeof a!=='object' || (a.enabled!==true && a.qiandao!=='是') || (only && i+1!==only)) continue;
    const text=`${body}\n账号${i+1}：${results[i]?.status || 'failure'}；Credits ${results[i]?.credits || 0}`;
    const channels=[];
    if (nonempty(a.serverchan)) channels.push(['Server酱',`https://sctapi.ftqq.com/${encodeURIComponent(a.serverchan)}.send`,{title,desp:text},d=>d.code===0]);
    if (nonempty(a.pushplus)) channels.push(['PushPlus','https://www.pushplus.plus/send',{token:a.pushplus,title,content:text,channel:'wechat',template:'txt'},d=>d.code===200]);
    if (nonempty(a.qywx)) {const key=a.qywx.includes('key=') ? a.qywx.split('key=').pop() : a.qywx; channels.push(['企业微信',`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=${encodeURIComponent(key)}`,{msgtype:'text',text:{content:text}},d=>d.errcode===0]);}
    for (const [name,url,payload,ok] of channels) {
      try {const q=await request(url,'POST',{'Content-Type':'application/json'},payload); if(q.status!==200 || !ok(q.data)) throw new Error(); log(`账号${i+1} ${name}通知成功`);}
      catch {failure=true; log(`⚠️ 账号${i+1} ${name}通知失败`);}
    }
  }
  const globalChannels=[];
  const incomingNotify=importedConfig.notify || {};
  const plus=process.env.PLUSPLUS_TOKEN || incomingNotify.plusplusToken;
  const wecom=process.env.QYWX_TOKEN || incomingNotify.qywxToken;
  const hook=process.env.QODER_WEBHOOK || incomingNotify.webhook;
  if (nonempty(plus)) globalChannels.push(['兼容 PushPlus','https://www.pushplus.plus/send',{token:plus,title,content:body,template:'txt'},d=>d.code===200]);
  if (nonempty(wecom)) globalChannels.push(['兼容企业微信','https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key='+encodeURIComponent(wecom.split('key=').pop()),{msgtype:'text',text:{content:body}},d=>d.errcode===0]);
  if (nonempty(hook)) globalChannels.push(['兼容 Webhook',hook,{title,content:body},d=>d.success===true || d.code===0 || d.code===200]);
  if (nonempty(process.env.PUSHPLUS_TOKEN)) globalChannels.push(['全局 PushPlus','https://www.pushplus.plus/send',
    {token:process.env.PUSHPLUS_TOKEN,title,content:body,template:'txt'},d=>d.code===200]);
  if (nonempty(process.env.BARK_URL)) globalChannels.push(['Bark',process.env.BARK_URL.replace(/\/+$/,''),{title,body,group:'Qoder'},d=>d.code===200]);
  if (nonempty(process.env.WECOM_WEBHOOK)) {
    const value=process.env.WECOM_WEBHOOK;
    const url=value.startsWith('https://') ? value : 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key='+encodeURIComponent(value);
    globalChannels.push(['全局企业微信',url,{msgtype:'text',text:{content:`${title}\n${body}`}},d=>d.errcode===0]);
  }
  if (nonempty(process.env.DINGTALK_WEBHOOK)) {
    try {
      const url=new URL(process.env.DINGTALK_WEBHOOK), secret=process.env.DINGTALK_SECRET;
      if (secret) {const timestamp=String(Date.now()); url.searchParams.set('timestamp',timestamp);
        url.searchParams.set('sign',crypto.createHmac('sha256',secret).update(`${timestamp}\n${secret}`).digest('base64'));}
      globalChannels.push(['钉钉',url.toString(),{msgtype:'text',text:{content:`${title}\n${body}`}},d=>d.errcode===0]);
    } catch {failure=true; log('⚠️ 钉钉通知地址配置无效');}
  }
  for (const [name,url,data,ok] of globalChannels) {
    try {const target=new URL(url); if (target.protocol!=='https:' || target.username || target.password) throw new Error();
      const q=await request(target,'POST',{'Content-Type':'application/json'},data);
      if (q.status!==200 || !ok(q.data)) throw new Error(); log(`✅ ${name}汇总通知成功`);
    } catch {failure=true; log(`⚠️ ${name}汇总通知失败`);}
  }
  const paths=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  for (const found of [...new Set(paths)].filter(p=>fs.existsSync(p))) {
    try {await sendQinglong(found,title,body); delivered=true;} catch {}
    if (delivered) break;
  }
  if (!delivered) failure=true;
  log(delivered ? '✅ 青龙通知已发送' : '⚠️ 青龙通知不可用或发送失败，保留业务退出码');
  return failure ? 'unavailable-or-failed' : 'sent';
}
async function main() {
  log('========== Qoder每日签到 =========='); log(`开始时间 ${stamp()}；模式 ${dry?'断网预演':'正式运行'}`);
  try {
    if (process.env.QODER_CONFIG_FILE) {
      importedConfig=JSON.parse(fs.readFileSync(process.env.QODER_CONFIG_FILE,'utf8').replace(/^\uFEFF/,''));
      if (!importedConfig || typeof importedConfig!=='object' || Array.isArray(importedConfig)) throw new Error();
    }
    const margin=process.env.QODER_REFRESH_MARGIN_H ?? importedConfig.refreshMarginH;
    if (margin!==undefined) {if(!/^\d+$/.test(String(margin)) || !Number.isSafeInteger(Number(margin))) throw new Error(); refreshMargin=Number(margin);}
    if (process.env.QODER_EMPTY_RETRY!==undefined || process.env.QODER_EMPTY_WAIT!==undefined) {
      emptyTimes=retryInteger('QODER_EMPTY_RETRY',3,1); emptyWait=retryInteger('QODER_EMPTY_WAIT',20,0);
    }
    const args=process.argv.slice(2);
    for(let j=0;j<args.length;j++) {
      if(args[j]==='--only') {if(!args[j+1] || !/^[1-9]\d*$/.test(args[j+1])) throw new Error(); only=Number(args[++j]);}
      else if (['--token','--from-file','--base-url'].includes(args[j])) {
        const flag=args[j], value=args[++j];
        if (!nonempty(value)) throw new Error();
        if (flag==='--token') tokenArg=value;
        if (flag==='--from-file') inputFile=value;
        if (flag==='--base-url') {
          const regions={'https://openapi.qoder.sh':'global','https://openapi.qoder.com.cn':'cn'};
          regionArg=regions[value.replace(/\/+$/,'')]; if (!regionArg) throw new Error();
        }
      }
      else if(!['--refresh-only','--no-notify','--status','--once','--dry-run','--json','silent','poll','silent-poll'].includes(args[j])) throw new Error();
    }
    if(!only && process.env.QODER_ONLY) {if(!/^[1-9]\d*$/.test(process.env.QODER_ONLY)) throw new Error(); only=Number(process.env.QODER_ONLY);}
    if (args.includes('--status') && args.includes('--refresh-only')) throw new Error();
    action=args.includes('--status') ? 'status' : args.includes('--refresh-only') ? 'refresh' : process.env.QODER_ACTION || 'checkin';
    if(!['checkin','refresh','status'].includes(action)) throw new Error();
    onceOnly=args.includes('--once');
    for (const [key,min,max] of [['QODER_WINDOW_RETRY_MAX',1,16],['QODER_WINDOW_RETRY_GAP',1,300]]) {
      if (process.env[key]!==undefined && (!/^\d+$/.test(process.env[key]) || Number(process.env[key])<min || Number(process.env[key])>max)) throw new Error();
    }
    retryMax=Number(process.env.QODER_WINDOW_RETRY_MAX || 16); retryGap=Number(process.env.QODER_WINDOW_RETRY_GAP || 90);
    const region=regionArg || process.env.QODER_REGION || 'cn';
    if (!['cn','global'].includes(region)) throw new Error();
    base=region==='global' ? 'https://openapi.qoder.sh' : 'https://openapi.qoder.com.cn';
    file=process.env.QODER_ACCOUNTS_FILE || '';
    if (tokenArg!==undefined || inputFile) {
      const imported=tokenArg!==undefined ? {accessToken:tokenArg} : JSON.parse(fs.readFileSync(inputFile,'utf8'));
      if (!imported || typeof imported!=='object' || Array.isArray(imported)) throw new Error();
      accounts=[{...imported,accessToken:imported.accessToken || imported.access_token || imported.token,
        device:imported.device || legacyDevice(),region:regionArg || imported.region || region,
        enabled:imported.enabled===true || enabled(process.env.QODER_ENABLED)}];
      file='';
    } else if (file || process.env.QODER_ACCOUNTS!==undefined) {
      const raw=file ? fs.readFileSync(file,'utf8') : process.env.QODER_ACCOUNTS;
      accounts=parseAccounts(raw); lines=accounts.map(a=>JSON.stringify(a));
    } else {
      accounts=[...legacyAccounts(process.env.QODER_TOKENS,'cn'),...legacyAccounts(process.env.QODER_GLOBAL_TOKENS,'global')];
      if (!accounts.length && process.env.QODER_CLAIM_TOKEN) accounts=process.env.QODER_CLAIM_TOKEN.split(/\r?\n/).map(s=>s.trim()).filter(Boolean).map(accessToken=>({accessToken,region,device:legacyDevice(),enabled:enabled(process.env.QODER_ENABLED)}));
    }
    if (!accounts.length && !file && process.env.QODER_ACCOUNTS===undefined && tokenArg===undefined && !inputFile && process.env.QODER_PAT) accounts=process.env.QODER_PAT.split(/\r?\n/).map(s=>s.trim()).filter(Boolean).map(personalToken=>({personalToken,region,enabled:enabled(process.env.QODER_ENABLED)}));
    accounts=accounts.map(normalizeAccount);
    const configuredBases=process.env.QODER_BASE_URL ? process.env.QODER_BASE_URL.split(',') : importedConfig.baseUrls;
    if (configuredBases!==undefined) {
      if (!Array.isArray(configuredBases) || !configuredBases.length || configuredBases.some(u=>typeof u!=='string' || u.trim().replace(/\/+$/,'')!==base)) throw new Error();
    }
    if (!accounts.length) throw new Error();
    if(only>accounts.length || !Number.isSafeInteger(only)) throw new Error();
  } catch {configFailure=true; log('❌ 阶段1 配置错误：请检查账号变量、私有文件及区域设置');}
  log(`账号数量 ${accounts.length}`);
  log(`任务动作 ${action==='status'?'只读活动查询':action==='refresh'?'仅刷新令牌':'签到'}；范围 ${only ? '账号'+only : '全部账号'}`);
  if(!configFailure) for(let i=0;i<accounts.length;i++) await one(accounts[i],i);
  const failed=results.filter(r=>r.status==='failure').length;
  const skipped=results.filter(r=>['skipped','unavailable'].includes(r.status)).length;
  const succeeded=results.filter(r=>['success','already-complete','dry-run'].includes(r.status)).length;
  // 活动未开放/关闭账号不是签到成功，不将它们当成成功退出。
  const unverified=results.filter(r=>r.status==='unavailable').length;
  const exitCode=configFailure || failed || unverified || !succeeded ? 1 : 0;
  const summary={task:'Qoder每日签到',mode:dry?'dry-run':'live',action,accounts:accounts.length,succeeded,failed,skipped,unverified,status:configFailure?'configuration-error':failed || unverified?(succeeded?'partial-failure':'failure'):exitCode?'no-verified-success':dry?'dry-run':'success',exitCode,results};
  try {summary.notification=await notifications(summary);} catch {summary.notification='unavailable-or-failed'; log('⚠️ 通知处理失败，保留业务退出码');}
  if (!dry && process.env.QODER_LOG_FILE) {
    try {
      const rec={time:stamp(),script:'qoder_checkin',trigger:process.argv.some(x=>x==='poll' || x==='silent-poll')?'poll':'checkin',
        result:summary.status,summary:{claimed:results.filter(r=>r.status==='success').length,already:results.filter(r=>r.status==='already-complete').length,pending:unverified,failed},results};
      fs.appendFileSync(process.env.QODER_LOG_FILE,JSON.stringify(rec)+'\n',{mode:0o600});
    } catch {log('⚠️ 脱敏日志写入失败，保留业务退出码');}
  }
  summary.elapsedMs=Date.now()-started; summary.finishedAt=stamp();
  log('--------------------------------');
  log(`任务统计：账号${summary.accounts} 成功${succeeded} 失败${failed} 跳过${skipped}；子任务成功${results.reduce((n,r)=>n+r.success,0)} 失败${results.reduce((n,r)=>n+r.failed,0)}；总耗时${summary.elapsedMs}毫秒`);
  log(`完成时间 ${summary.finishedAt}；最终状态 ${summary.status}；通知 ${summary.notification}`);
  console.log('全部处理完成');
  if (process.argv.includes('--json')) {
    for (const r of results) console.log(JSON.stringify({account:r.account,verdict:r.status==='dry-run'?'done':r.status==='success'?(action==='status' || action==='refresh'?'done':'claimed'):r.status==='already-complete'?'done':r.status==='unavailable'?'pending':'error',detail:action==='status'?(r.status==='success'?'只读查询完成，未执行领取或续期':r.status==='dry-run'?'只读查询断网预演':'只读查询未成功'):r.status,date:new Date(Date.now()+8*3600000).toISOString().slice(0,10),endpoint:accountBase(accounts[r.account-1]),...(r.campaigns?{http:200,campaigns:r.campaigns}:{})}));
    if (configFailure) console.log(JSON.stringify({verdict:'error',detail:'配置错误',date:new Date(Date.now()+8*3600000).toISOString().slice(0,10),endpoint:null}));
  }
  console.log('TASK_SUMMARY='+JSON.stringify(summary));
  process.exitCode=exitCode;
}
main().then(()=>{process.exit(process.exitCode || 0);}).catch(()=>{log('❌ 任务内部错误');process.exit(1);});
