// name: 51CTO博客每日签到
// cron: 17 2 * * *
/**
 * name: 51CTO博客每日签到
 * cron: 0 8 * * *
 * 51CTO博客每日签到脚本（青龙面板专用）
 * 纯HTTP请求实现，无需Puppeteer/Chromium
 * 来源：huwangkeji/51cto_sign_authed，51cto_sign.js
 * 许可证：GPL-3.0（依据来源许可证，保留上游署名）。
 * Node.js >= 18，仅使用标准库。上游未声明计划，此处建议每日北京时间08:00。
 * ICTO_BLOG_ACCOUNTS（必填）：每个非空行一个账号，推荐 用户名|密码。
 * 从 https://home.51cto.com/ 注册或已有账号取得登录用户名和密码。
 * 兼容每行 用户名@密码；只在第一个分隔符拆分，密码中的后续分隔符保留。
 * 邮箱用户名必须使用 |；不再用 & 或 @ 分隔账号。密码不去除首尾空格。
 * ICTO_BLOG_DRY_RUN=1：完全断网预演，不登录、不签到、不调用通知模块。
 * QINGLONG_NOTIFY 默认1，0/false/no/off关闭；QINGLONG_NOTIFY_DIR可指定通知模块目录。
 * 仅登录和签到，不发布文章、评论、分享，不持久化凭据；验证码登录不能绕过。
 */
'use strict';
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const DRY = process.env.ICTO_BLOG_DRY_RUN === '1';
const LOGIN = 'https://home.51cto.com/index';
const PAGE = 'https://blog.51cto.com/user/sign';
const API = 'https://api-blog.51cto.com/sign/run';
const TITLE = '51CTO博客每日签到';
const started = Date.now();
const secrets = [];
const results = [];
const clock = () => new Date().toLocaleTimeString('zh-CN', {hour12:false});
function redact(value) {
  let text = String(value).replace(/[\r\n\u0000-\u001f\u007f]/g, ' ');
  for (const secret of [...secrets].sort((a,b)=>b.length-a.length)) {
    if (secret) text = text.split(secret).join('[已隐藏]');
  }
  return text.replace(/\b1[3-9]\d{9}\b/g, '[手机号已隐藏]');
}
function log(text) { console.log(`[${clock()}] ${redact(text)}`); }
function fail(message) { throw new Error(message); }
function parseAccount(line) {
  const delimiter = line.includes('|') ? '|' : '@';
  const at = line.indexOf(delimiter);
  if (at < 1 || !line.slice(at+1)) fail('账号格式错误：每行使用 用户名|密码');
  const username = line.slice(0, at).trim();
  const password = line.slice(at+1);
  if (!username || /[\r\n\u0000]/.test(password)) fail('账号格式错误');
  secrets.push(password);
  return {username, password};
}
// 按域、路径和安全属性保存会话，禁止向其他站点泄漏凭据。
class CookieJar {
  constructor() { this.items = new Map(); }
  add(headers, url) {
    const u = new URL(url);
    for (const header of headers || []) {
      const parts = header.split(';');
      const at = parts[0].indexOf('=');
      if (at < 1) continue;
      const name = parts[0].slice(0, at).trim(), value = parts[0].slice(at+1);
      const attrs = {};
      for (const p of parts.slice(1)) {
        const n = p.indexOf('=');
        attrs[(n<0?p:p.slice(0,n)).trim().toLowerCase()] = n<0?true:p.slice(n+1).trim();
      }
      const domain = String(attrs.domain || u.hostname).replace(/^\./,'').toLowerCase();
      if (!(u.hostname === domain || u.hostname.endsWith('.'+domain)) || !(domain === '51cto.com' || domain.endsWith('.51cto.com'))) continue;
      const cookiePath = typeof attrs.path === 'string' && attrs.path.startsWith('/') ? attrs.path : u.pathname.slice(0,u.pathname.lastIndexOf('/')+1) || '/';
      let expires = attrs.expires ? Date.parse(attrs.expires) : Infinity;
      if ('max-age' in attrs && /^-?\d+$/.test(attrs['max-age'])) expires = Date.now()+Number(attrs['max-age'])*1000;
      const key = `${domain}|${cookiePath}|${name}`;
      if (value === 'deleted' || expires <= Date.now()) this.items.delete(key);
      else {
        this.items.set(key, {name,value,domain,path:cookiePath,hostOnly:!attrs.domain,secure:!!attrs.secure,expires});
        secrets.push(value);
      }
    }
  }
  header(url) {
    const u = new URL(url);
    return [...this.items.values()].filter(c => c.expires > Date.now() &&
      (c.hostOnly ? c.domain === u.hostname : u.hostname === c.domain || u.hostname.endsWith('.'+c.domain)) &&
      (u.pathname === c.path || u.pathname.startsWith(c.path.endsWith('/')?c.path:c.path+'/')) &&
      (!c.secure || u.protocol === 'https:')).sort((a,b)=>b.path.length-a.path.length).map(c=>`${c.name}=${c.value}`).join('; ');
  }
}
async function request(url, jar, opts={}, redirects=0) {
  if (DRY) fail('断网预演禁止HTTP请求');
  const u = new URL(url);
  if (u.protocol !== 'https:' || !['home.51cto.com','blog.51cto.com','api-blog.51cto.com'].includes(u.hostname) || (u.port && u.port !== '443') || u.username || u.password) fail('拒绝非白名单请求');
  const response = await new Promise((resolve,reject)=> {
    const req = https.request(u, {method:opts.method || 'GET', headers:{
      'User-Agent':'Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36',
      'Accept':'application/json, text/html;q=0.9, */*;q=0.8',
      'Accept-Encoding':'identity', 'Cookie':jar.header(u),
      'Referer':opts.referer || PAGE,
      ...(opts.body ? {'Content-Type':opts.type || 'application/json','Origin':'https://blog.51cto.com'} : {})
    }}, res=> {
      const chunks=[]; let size=0;
      res.on('data',chunk=> {size+=chunk.length; if(size>2097152) req.destroy(new Error('响应超过大小限制')); else chunks.push(chunk);});
      res.on('end',()=>resolve({status:res.statusCode, headers:res.headers,body:Buffer.concat(chunks).toString('utf8')}));
      res.on('error',()=>reject(new Error('响应接收失败')));
      res.on('aborted',()=>reject(new Error('响应中断')));
    });
    const timer=setTimeout(()=>req.destroy(new Error('请求超时')),15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',()=>reject(new Error('网络请求失败或超时')));
    if(opts.body) req.write(opts.body);
    req.end();
  });
  jar.add(response.headers['set-cookie'],u);
  if(response.status>=300 && response.status<400) {
    if(!response.headers.location || redirects>=5) fail('重定向异常或次数超限');
    const next=new URL(response.headers.location,u);
    // 永不把登录表单重发给不同源。
    if(opts.body && next.origin !== u.origin && ![301,302,303].includes(response.status)) fail('拒绝跨源转发登录数据');
    const switchGet=response.status===303 || ([301,302].includes(response.status) && opts.method==='POST');
    return request(next,jar,switchGet?{referer:opts.referer}:opts,redirects+1);
  }
  if(response.status<200 || response.status>=300) fail(`HTTP请求失败（状态${response.status}）`);
  return response.body;
}
const md5 = x=>crypto.createHash('md5').update(String(x)).digest('hex');
function signed(token) {
  const timestamp=Math.floor(Date.now()/1000);
  const sign=md5(md5('sign/run')+md5('token,timestamp,sign'+md5(token)+md5(timestamp)));
  secrets.push(sign);
  return {token,timestamp,sign};
}
function decodeHTML(s) {
  return s.replace(/&quot;/g,'"').replace(/&#39;|&apos;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
}
function csrfFrom(html) {
  const tags=html.match(/<input\b[^>]*>/gi)||[];
  for(const tag of tags) {
    const attrs={};
    for(const m of tag.matchAll(/([\w-]+)\s*=\s*(["'])(.*?)\2/g)) attrs[m[1].toLowerCase()]=decodeHTML(m[3]);
    if(attrs.name==='_csrf' && attrs.value) return attrs.value;
  }
  fail('登录页缺少CSRF；可能需要人工处理验证码或接口已变化');
}
async function api(jar,token,post=false) {
  const data=signed(token);
  const body=await request(post?API:API+'?'+new URLSearchParams(data),jar,post?{method:'POST',body:JSON.stringify(data)}:{});
  let json; try {json=JSON.parse(body);} catch {fail('签到接口不是有效JSON');}
  if(!json || json.code!==0 || !json.data || ![0,1].includes(json.data.alert)) fail('签到业务状态不明确或失败；请检查凭据及接口');
  // 只采用官方非秘密身份字段，不输出原始响应或业务错误文本。
  for(const key of ['nickname','username','displayName','uid']) {
    const value=json.data[key];
    if((typeof value==='string'||typeof value==='number') && String(value).trim()) log(`官方账号${key}：${value}`);
  }
  return json.data.alert;
}
async function stage(record,number,name,fn) {
  const begin=Date.now(); log(`账号${record.account} 阶段${number} ${name} 开始`);
  try {
    const value=await fn();
    const state=value==='already'?'alreadyComplete':value==='skipped'?'skipped':'success';
    record[state]++; log(`账号${record.account} 阶段${number} ${name} ${state==='alreadyComplete'?'☑️ 已完成':state==='skipped'?'⏭️ 预演跳过网络':'✅ 成功'} 耗时${Date.now()-begin}ms`);
    return value;
  } catch(e) {
    record.failure++; log(`账号${record.account} 阶段${number} ${name} ❌ ${e.message} 耗时${Date.now()-begin}ms`); throw e;
  }
}
async function accountTask(account,record) {
  if(DRY) {
    for(const [i,name] of ['登录及会话同步','获取签到Token','查询签到状态','按需签到并复查'].entries()) await stage(record,i+2,name,async()=> 'skipped');
    log(`账号${record.account} DRY_RUN_OK 参数有效，未进行业务请求`); return;
  }
  const jar=new CookieJar();
  await stage(record,2,'登录及会话同步',async()=> {
    const url=LOGIN+'?reback='+encodeURIComponent(PAGE);
    const csrf=csrfFrom(await request(url,jar)); secrets.push(csrf);
    const body=new URLSearchParams({'_csrf':csrf,'LoginForm[username]':account.username,'LoginForm[password]':account.password,agree:'1'}).toString();
    const html=await request(url,jar,{method:'POST',body,type:'application/x-www-form-urlencoded',referer:LOGIN});
    if(/id=["']errorMsg["'][^>]*>\s*[^<\s]/.test(html)) fail('登录失败；请检查密码或人工处理验证码');
    await request('https://blog.51cto.com/',jar);
  });
  let token;
  await stage(record,3,'获取签到Token',async()=> {
    const html=await request(PAGE,jar);
    const nuxt=html.match(/window\.__NUXT__\s*=\s*(.+?);?\s*<\/script>/s);
    const match=nuxt && nuxt[1].match(/token["']?\s*[:=]\s*["']([^"']+)/);
    if(!match) fail('未取得签到Token；登录未验证或页面接口已变化');
    token=match[1]; secrets.push(token);
  });
  let already=false;
  await stage(record,4,'查询签到状态',async()=> { already=(await api(jar,token))===1; return already?'already':undefined; });
  await stage(record,5,'按需签到并复查',async()=> {
    if(already) {log('今日已签到，无需重复签到'); return 'already';}
    await api(jar,token,true);
    if(await api(jar,token)!==1) fail('签到后复查未确认完成，不标记业务成功');
    log('签到成功（已复查）');
  });
}
async function notify(body) {
  if(/^(0|false|no|off)$/i.test(process.env.QINGLONG_NOTIFY||'1')) {log('通知已关闭'); return 'disabled';}
  if(DRY) {log(`通知预演（未联网）：${body}`); return 'dry-run';}
  const paths=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js',path.join(__dirname,'sendNotify.js')].filter(Boolean);
  const modulePath=paths.find(p=>fs.existsSync(p));
  if(!modulePath) {log('⚠️ 未找到青龙sendNotify.js，保留业务退出码'); return 'unavailable';}
  let timer;
  try {
    await Promise.race([Promise.resolve().then(()=> {
      const mod=require(modulePath);
      if(typeof mod.sendNotify!=='function') fail('通知模块契约错误');
      return mod.sendNotify(TITLE,redact(body));
    }),new Promise((_,reject)=> {timer=setTimeout(()=>reject(new Error('通知超时')),15000);})]);
    log('通知发送成功'); return 'sent';
  } catch {log('⚠️ 通知失败，保留业务退出码'); return 'failed';}
  finally {clearTimeout(timer);}
}
async function main() {
  console.log(`========== ${TITLE} ==========`);
  log(`开始时间：${new Date(started).toISOString()}；模式：${DRY?'断网预演':'真实签到'}`);
  const lines=(process.env.ICTO_BLOG_ACCOUNTS||'').split(/\r?\n/).filter(s=>s.trim());
  log(`账号数量：${lines.length}`);
  if(!lines.length) log('❌ 配置错误：缺少必填ICTO_BLOG_ACCOUNTS');
  for(const [index,line] of lines.entries()) {
    const begin=Date.now();
    const record={account:index+1,success:0,alreadyComplete:0,skipped:0,failure:0,status:'success'};
    results.push(record);
    try {
      const account=await stage(record,1,'校验账号参数',async()=>parseAccount(line));
      await accountTask(account,record);
    } catch {record.status='failure';}
    record.durationMs=Date.now()-begin;
    log(`账号${record.account}统计：总任务${record.success+record.alreadyComplete+record.skipped+record.failure}，成功${record.success}，已完成${record.alreadyComplete}，跳过${record.skipped}，失败${record.failure}，耗时${record.durationMs}ms`);
  }
  const failed=results.filter(r=>r.status==='failure').length;
  const succeeded=results.length-failed;
  const exitCode=!lines.length||failed?1:0;
  const status=!lines.length?'configuration-error':failed?(succeeded?'partial-failure':'failure'):DRY?'dry-run':'success';
  const body=`模式${DRY?'断网预演':'真实签到'}；账号总数${lines.length}，成功${succeeded}，失败${failed}；状态${status}`;
  const notification=await notify(body);
  const totals={success:0,alreadyComplete:0,skipped:0,failure:0};
  for(const r of results) for(const key of Object.keys(totals)) totals[key]+=r[key];
  log('----------------------------------------');
  log(`最终统计：${body}；子任务成功${totals.success}，已完成${totals.alreadyComplete}，跳过${totals.skipped}，失败${totals.failure}`);
  log(`完成时间：${new Date().toISOString()}；总耗时${Date.now()-started}ms；通知状态${notification}；最终状态${status}`);
  console.log('TASK_SUMMARY='+JSON.stringify({task:TITLE,mode:DRY?'dry-run':'live',status,accounts:lines.length,succeeded,failed,totals,results,notification,durationMs:Date.now()-started,exitCode}));
  // 通知扩展可能保留连接：业务结束后按原脚本语义退出。
  process.exit(exitCode);
}
if(require.main===module) main().catch(()=> {log('❌ 运行器异常'); process.exit(1);});
module.exports={parseAccount,signed,CookieJar,csrfFrom};
