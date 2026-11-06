// name: 橙光每日任务
// cron: 20 10 * * *
/*
name: 橙光每日任务
cron: 20 10 * * *
来源：Wenmoux/checkbox scripts/rpg66.js
上游版本：a22d8650ae69224c18c4856afdf9fbdf8622c54f
许可：MIT（上游输入未附额外版权或许可声明，保留其来源署名）。
上游未声明 cron；此处提供每日 08:15 的默认维护计划。
Node.js >= 18，无第三方依赖。
RPG66_ACCOUNTS：每个非空行一个 JSON 对象，包含 uid、token，可选 skey，
以及原有 gameid、readGameId/read_gameid、flowerTarget/flower_target、
confessionGameId/confession_gameid、allowSendFlowers/allow_send_flowers/sendFlowers。
获取方法：自行登录橙光官方客户端，在本人授权的请求中查看 uid、token、skey；
不要提供给第三方，失效后重新登录获取。目标作品 ID 从官方作品页获取。
默认 tasks=balance,sign,claim-tree,claim-old，只执行查询、签到与已完成奖励领取。
RPG66_TASKS 为逗号分隔的任务开关（见 contract.json），不用于分隔账号。
互动、公开回帖/收藏夹、消费和时长上报均须主动开启；不再内置目标作品。
RPG66_DRY_RUN=1：完全断网，模拟配置与执行计划，不代表真实业务成功。
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
    const identities = ["38acc6660ed7ac1b", "scripts/rpg66.js", "rpg66.js", "rpg66"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
const https = require('node:https');
const crypto = require('node:crypto');
const path = require('node:path');
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const qs = { stringify: value => new URLSearchParams(Object.entries(value).map(([k,v]) => [k,String(v)])).toString() };
const md5 = text => crypto.createHash('md5').update(text).digest('hex');
const DRY = process.env.RPG66_DRY_RUN === '1';
const TITLE = '橙光每日任务';
const CATALOG = '38acc6660ed7ac1b';
const DEFAULT_TASKS = ['balance','sign','claim-tree','claim-old'];
const ACTION_NAMES = ['browse-channel','browse-share','dog-next','dog-favorite','like','favorite','share','flowers','reply','confession','collections'];
const ALL_TASKS = new Set([...DEFAULT_TASKS,'runtime',...ACTION_NAMES]);
const secrets = new Set();
function safe(value) {
  let text = String(value).replace(/[\r\n\x00-\x1f]/g,' ');
  for (const item of secrets) if (item) text = text.split(item).join('[凭据已隐藏]');
  return text.replace(/\b1[3-9]\d{9}\b/g,'[手机号已隐藏]');
}
function log(text) { console.log(`[${new Date().toTimeString().slice(0,8)}] ${safe(text)}`); }
function requireGame(account) {
  if (!account.gameid || !/^\d+$/.test(String(account.gameid))) throw new Error('该操作必须配置目标 gameid');
  return account.gameid;
}
function identify(data) {
  const objects = [data?.data?.user,data?.data?.userInfo,data?.data?.userinfo,data?.data,data?.user];
  for (const user of objects) {
    if (!user || typeof user !== 'object') continue;
    const key = ['nickname','username','display_name','uid'].find(k => typeof user[k] === 'string' || typeof user[k] === 'number');
    if (key) { log(`官方账号身份：${user[key]}`); return; }
  }
}
function http(url, {method='GET',headers={},body='',timeout=15000,maxBytes=1048576,json=true}={}) {
  if (DRY) return Promise.reject(new Error('断网预演禁止网络请求'));
  return new Promise((resolve,reject) => {
    const target = new URL(url);
    if (target.protocol !== 'https:') return reject(new Error('只允许 HTTPS'));
    let done=false, timer;
    const finish=(err,value)=>{ if(done)return;done=true;clearTimeout(timer);err?reject(err):resolve(value); };
    const req=https.request(target,{method,headers},res=>{
      let bytes=0;const chunks=[];
      res.on('data',chunk=>{bytes+=chunk.length;if(bytes>maxBytes){finish(new Error('响应超出大小限制'));res.destroy();req.destroy();}else chunks.push(chunk);});
      res.on('error',()=>finish(new Error('响应读取失败')));
      res.on('end',()=>{
        if(res.statusCode<200||res.statusCode>=300)return finish(new Error('HTTP 状态异常'));
        const text=Buffer.concat(chunks).toString('utf8');
        if(!json)return finish(null,text);
        try { finish(null,JSON.parse(text)); } catch { finish(new Error('响应不是有效 JSON')); }
      });
    });
    timer=setTimeout(()=>{finish(new Error('请求超时'));req.destroy();},timeout);
    req.on('error',()=>finish(new Error('网络请求失败')));
    if(body)req.write(body);req.end();
  });
}
async function request(method,url,body,options={}) {
  const target=new URL(url);
  for(const [key,value] of Object.entries(options.params||{}))target.searchParams.set(key,String(value));
  const html=target.hostname==='m.66rpg.com' && target.pathname==='/mini/home';
  const data=await http(target,{method,body,headers:options.headers,timeout:options.timeout,json:!html});
  if(!html && (!data || data.status!==1)) throw new Error('接口未明确返回业务成功 status=1');
  if(!html)identify(data);
  return {data};
}
const axios={get:(url,options)=>request('GET',url,'',options),post:(url,body,options)=>request('POST',url,body,options)};
const normalizeText=value=> typeof value==='string'?value.replace(/\s+/g,' ').trim():'';
async function publicText() {
  const local=normalizeText(process.env.RPG66_LOCAL_TEXT||'感谢分享，祝创作顺利。');
  const fallback=local && Array.from(local).length<=280?local:'感谢分享，祝创作顺利。';
  if(DRY)return fallback;
  try {
    const data=await http('https://v1.hitokoto.cn/?encode=json',{timeout:8000,maxBytes:16384});
    const text=normalizeText(data.hitokoto),author=normalizeText(data.from_who),source=normalizeText(data.from);
    if(!text)throw new Error('缺少文本');
    const result=text+(author&&source?` —— ${author}《${source}》`:source?` ——《${source}》`:author?` —— ${author}`:'');
    if(Array.from(result).length>280)throw new Error('文本过长');
    log('公开回帖文本：已取得一言内容及署名（不输出正文）');
    return result;
  } catch { log('一言获取失败，使用本地回帖文本'); return fallback; }
}
const WWW = "https://www.66rpg.com";
const IAPI = "https://iapi.66rpg.com";
const COLLECT = "https://c.66rpg.com/collect/v1/index/runtime";
const IAPI_SIGN_SALT = "a_bvvznajmyefox9ts";

const APP_PARAMS = {
  client: 2,
  platform: 2,
  android_cur_ver: "3.11.334.0424",
  channel: "vivoDYD",
};

const UA =
  "Mozilla/5.0 (Linux; Android 12; Redmi K30 Build/SKQ1.211006.001; wv) " +
  "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36";

const RUNTIME_PUBKEY =
  "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDtsvsk/MIEI9YXvHzLfg+eEJkY3d7RmVynKBZY35T0xg3WwZgmC6GSPZqrMMcht6aiZYPJywhm9JiE6kBo/0Mvxklm5Wd35wIKeDXcq8Aqb4aQXalcwsD3f829OR1P2AqGilr14Rftv4ixyQATG/BqP2/kgft2rcq4e/E7bDWNLQIDAQAB";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeAccount(name, value) {
  if (!value || !value.uid || !value.token) return null;
  return { name: value.name || name, ...value };
}

function collectAccounts(source, defaultName) {
  if (!source) return [];
  if (Array.isArray(source)) {
    return source
      .map((value, index) => normalizeAccount(`${defaultName}${index + 1}`, value))
      .filter(Boolean);
  }
  if (source.accounts) return collectAccounts(source.accounts, defaultName);
  if (source.users) return collectAccounts(source.users, defaultName);

  const direct = normalizeAccount(defaultName, source);
  if (direct) return [direct];

  return Object.entries(source)
    .map(([name, value]) => normalizeAccount(name, value))
    .filter(Boolean);
}

function loadAccounts() {
  return collectAccounts(globalThis.config?.rpg66, "rpg66");
}

function params(account, extra = {}) {
  return {
    uid: account.uid,
    token: account.token,
    ...APP_PARAMS,
    ...extra,
  };
}

function signedIapiParams(account, extra = {}) {
  return {
    uid: account.uid,
    token: account.token,
    skey: account.skey || "",
    client: 2,
    platform: 2,
    nt: "wifi",
    ...extra,
  };
}

function iapiSign(body) {
  const text = Object.keys(body)
    .sort()
    .map((key) => `${key}=${body[key]}`)
    .join("&");
  return md5(text + IAPI_SIGN_SALT).toString();
}

async function iapiGet(account, apiPath, extra = {}) {
  const body = signedIapiParams(account, extra);
  const res = await axios.get(IAPI + apiPath, {
    params: body,
    headers: {
      "user-agent": UA,
      "x-sign": iapiSign(body),
    },
    timeout: 20000,
    validateStatus: () => true,
  });
  return res.data;
}

async function iapiPost(account, apiPath, extra = {}) {
  const body = signedIapiParams(account, extra);
  const res = await axios.post(IAPI + apiPath, qs.stringify(body), {
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      "user-agent": UA,
      "x-sign": iapiSign(body),
    },
    timeout: 20000,
    validateStatus: () => true,
  });
  return res.data;
}

async function get(account, apiPath, extra = {}) {
  const res = await axios.get(WWW + apiPath, {
    params: params(account, extra),
    headers: {
      "user-agent": UA,
      referer: "https://m3.66rpg.com/mini/orgshop/orgfarm",
    },
    timeout: 15000,
    validateStatus: () => true,
  });
  return res.data;
}

async function postForm(account, apiPath, body = {}) {
  const res = await axios.post(WWW + apiPath, qs.stringify(params(account, body)), {
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      "user-agent": UA,
      referer: "https://m3.66rpg.com/mini/orgshop/orgfarm",
    },
    timeout: 15000,
    validateStatus: () => true,
  });
  return res.data;
}

function webCookie(account) {
  return [
    `userid=${account.uid}`,
    `token=${account.token}`,
    "isLogin=true",
    "loginStatus=1",
  ].join("; ");
}

async function webGet(account, url, extra = {}, referer = "https://m3.66rpg.com/mini/orgshop/orgfarm") {
  const res = await axios.get(url, {
    params: params(account, extra),
    headers: {
      "user-agent": UA,
      cookie: webCookie(account),
      referer,
    },
    timeout: 15000,
    validateStatus: () => true,
  });
  return res.data;
}

async function webPostForm(account, url, body = {}, referer = "https://m3.66rpg.com/mini/orgshop/orgfarm") {
  const res = await axios.post(url, qs.stringify(params(account, body)), {
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      "user-agent": UA,
      cookie: webCookie(account),
      referer,
    },
    timeout: 15000,
    validateStatus: () => true,
  });
  return res.data;
}

function flatTasks(treeTaskData) {
  const groups = ["day", "week", "timed", "growth"];
  return groups.flatMap((group) => {
    const list = treeTaskData?.[group]?.list || [];
    return list.map((task) => ({ ...task, group }));
  });
}

function taskLine(task) {
  return `${task.task_id} ${task.task_name} ${task.progress_bar_current}/${task.progress_bar_max} status=${task.task_status} claim=${task.claim_status}`;
}

function taskProgress(task) {
  return {
    current: Number(task.progress_bar_current || 0),
    max: Number(task.progress_bar_max || 0),
  };
}

function isTaskDone(task) {
  const progress = taskProgress(task);
  return progress.max > 0 && progress.current >= progress.max;
}

function isTaskReady(task) {
  return Number(task.task_status) === 1 && Number(task.claim_status) === 0;
}

function isTaskPending(task) {
  return !isTaskDone(task) && !isTaskReady(task);
}

function normalizeTaskText(value) {
  return String(value || "").replace(/\s+/g, "").toLowerCase();
}

function taskMatches(task, aliases) {
  const text = normalizeTaskText(`${task.task_name || ""} ${task.desc || ""} ${task.description || ""}`);
  return aliases.some((alias) => text.includes(normalizeTaskText(alias)));
}

async function getTreeTasks(account) {
  const data = await get(account, "/ActiveSystem/ptree/get_user_task_list");
  if (data.status !== 1) throw new Error(`tree task list failed: ${data.msg || data.status}`);
  const groups = data.data;
  if (!groups || typeof groups !== 'object' || !['day','week','timed','growth'].some(key => Array.isArray(groups[key]?.list))) throw new Error('橙树任务列表结构异常');
  for (const key of ['day','week','timed','growth']) if (groups[key] !== undefined && !Array.isArray(groups[key]?.list)) throw new Error('橙树任务分组结构异常');
  for (const task of flatTasks(groups)) {
    for (const key of ['task_id','task_status','claim_status','progress_bar_current','progress_bar_max']) {
      if (task[key] === undefined || task[key] === null || task[key] === '' || !Number.isFinite(Number(task[key]))) throw new Error('橙树任务字段不完整');
    }
  }
  return groups;
}

async function getTreeTask(account, taskId) {
  return flatTasks(await getTreeTasks(account)).find((task) => Number(task.task_id) === Number(taskId));
}

async function signIn(account) {
  const res = await axios.post(
    `${WWW}/Ajax/Home/new_sign_in.json`,
    qs.stringify({
      token: account.token,
      mobile_uid: "",
      client: 2,
      android_cur_ver: APP_PARAMS.android_cur_ver,
    }),
    {
      headers: {
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "user-agent": UA,
      },
      timeout: 15000,
      validateStatus: () => true,
    },
  );
  const data = res.data;
  if (data.status === 1) {
    const today = data.data?.today?.award_name || "ok";
    const fov = data.data?.today?.active_signin_award?.award_fov_name || "";
    return `sign ok: ${today}${fov ? `, ${fov}` : ""}`;
  }
  throw new Error("签到未通过业务核验");
}

async function uploadRuntime(account, minutes = 30) {
  const seconds = minutes * 60;
  const gameIds = Array.from(
    new Set([account.readGameId, account.read_gameid, account.gameid].filter(Boolean)),
  );
  if (!gameIds.length) throw new Error("阅读上报需要 readGameId 或 gameid");
  const logs = [];
  for (const gameId of gameIds) {
    const ts = Math.floor(Date.now() / 1000);
    const data = JSON.stringify({ run: { [gameId]: seconds } });
    const check = md5(data + account.uid + ts + RUNTIME_PUBKEY).toString();
    const body = qs.stringify({
      data,
      uid: account.uid,
      ts,
      check,
      platform: 3,
      channel_id: 0,
      online_plat: seconds,
      nonce: "b613b114-b3a8-4bb6-a444-7096b2abc5fe",
      timestamp: ts,
    });
    const res = await axios.post(COLLECT, body, {
      headers: {
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": UA,
      },
      timeout: 15000,
      validateStatus: () => true,
    });
    logs.push(`${gameId}:${res.data?.msg || res.data?.status}`);
    await sleep(300);
  }
  return `runtime ${minutes}min: ${logs.join(", ")}`;
}

async function fillRuntimeTasks(account, tasks) {
  const needMinutes = tasks
    .filter((task) => findPassiveTaskCoverage(task)?.handler === "fillRuntimeTasks")
    .map((task) => Math.max(0, Number(task.progress_bar_max) - Number(task.progress_bar_current)))
    .reduce((max, remain) => Math.max(max, remain), 0);

  if (!needMinutes) return "runtime tasks already done";
  return uploadRuntime(account, Math.max(30, needMinutes));
}

async function getRecommendedGame(account, action = "") {
  const data = await get(account, "/ActiveSystem/FeedDog/get_recommended_game_info", {
    c_action: action,
  });
  if (data.status !== 1 || !data.data?.gameInfo) {
    throw new Error(`recommended game failed: ${data.msg || data.status}`);
  }
  return data.data.gameInfo;
}

async function doDogNext(account, task) {
  const remain = Math.max(0, Number(task.progress_bar_max) - Number(task.progress_bar_current));
  if (!remain) return "dog next already done";

  for (let i = 0; i < remain; i++) {
    await getRecommendedGame(account, i === 0 && Number(task.progress_bar_current) === 0 ? "" : "next");
    await sleep(500);
  }
  return `dog next requested ${remain}`;
}

async function createFavorite(account, gindex, favSource) {
  const res = await axios.post(
    `${WWW}/ajax/favorite/create.json`,
    qs.stringify({
      gindex,
      android_uid: account.uid,
      platform: 2,
      fav_source: favSource,
      uid: account.uid,
      token: account.token,
      client: 2,
    }),
    {
      headers: {
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": UA,
        referer: "https://m3.66rpg.com/mini/orgshop/orgdog?share_mode=1",
      },
      timeout: 15000,
      validateStatus: () => true,
    },
  );
  return res.data;
}

async function doDogFavorite(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "dog favorite already done";
  }

  let last;
  for (let i = 0; i < 5; i++) {
    last = await getRecommendedGame(account, i === 0 ? "" : "next");
    if (!last.is_fav) break;
  }
  if (!last?.gindex) return "dog favorite no game";

  const data = await createFavorite(account, last.gindex, "1");
  return `dog favorite ${last.gindex}: ${data.msg || data.status}`;
}

async function doGenericFavorite(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "favorite already done";
  }
  const gindex = requireGame(account);
  const data = await createFavorite(account, gindex, "script");
  return `favorite ${gindex}: ${data.msg || data.status}`;
}

async function doDynamicLike(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "dynamic like already done";
  }

  let listRes;
  let list = [];
  for (let page = 1; page <= 3 && !list.length; page++) {
    listRes = await iapiGet(account, "/dynamic/v1/dynamic/get_dynamic", { page, type: 0 });
    list = listRes.data?.list || [];
  }
  const dynamic = list.find((item) => Number(item.star_status) === 0 && String(item.user?.uid) !== String(account.uid));
  if (!dynamic?.did) return `dynamic like no target: ${listRes?.msg || listRes?.status}`;

  const likeRes = await iapiPost(account, "/dynamic/v1/dynamic/star", { did: dynamic.did });
  return `dynamic like ${dynamic.did}: ${likeRes.msg || likeRes.status}`;
}

function appBackUrl() {
  return "https://m3.66rpg.com/mini/orgshop/orgfarm";
}

async function recordBoxRunTimes(account, extra = {}) {
  const data = await iapiGet(account, "/box/v1/index/record_box_run_times.json", {
    run_time: 15,
    count_timer: 15,
    ...extra,
  });
  return `record box run times: ${data.msg || data.status || JSON.stringify(data)}`;
}

async function doSharePageBrowse(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "share page browse already done";
  }

  const backUrl = appBackUrl();
  await webGet(
    account,
    "https://m.66rpg.com/mini/home",
    {
      box: "box_tab",
      pushvalue: 3,
      type: 1,
      count_timer: 15,
      count_timer_url: "box/v1/index/record_box_run_times.json",
      url: backUrl,
    },
    backUrl,
  );
  const recordResult = await recordBoxRunTimes(account, {
    box: "box_tab",
    pushvalue: 3,
    type: 1,
  });
  await iapiGet(account, "/dynamic/v1/dynamic/get_dynamic", { page: 1, type: 1 });
  await sleep(16000);

  const latest = await getTreeTask(account, task.task_id);
  return `share page browse attempted: ${latest?.progress_bar_current ?? "?"}/${latest?.progress_bar_max ?? "?"} status=${latest?.task_status ?? "?"}; ${recordResult}`;
}

async function doChannelPageBrowse(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "channel page browse already done";
  }

  const tid = Number(task.tid || 0);
  if (!tid) return `channel page browse no tid: ${taskLine(task)}`;

  const backUrl = appBackUrl();
  await webGet(
    account,
    "https://m.66rpg.com/mini/home",
    {
      box: "box_tid",
      pushvalue: tid,
      count_timer: 15,
      count_timer_url: "box/v1/index/record_box_run_times.json",
      url: backUrl,
    },
    backUrl,
  );
  const recordResult = await recordBoxRunTimes(account, {
    box: "box_tid",
    pushvalue: tid,
    tid,
  });
  await webPostForm(account, `${WWW}/ajax/index/statistics_first_screen_cat_content`, {
    position: tid,
    id: tid,
  }, "https://m.66rpg.com/mini/home");

  const channelParams = {
    tid,
    page: 1,
    pageNum: 1,
    works_pub_time: 0,
    flag: "orgbox",
  };
  const endpoints = [
    "/ajax/channel/tag_screen_list",
    "/ajax/channel/tag_screen",
    "/ajax/Channel/third_tag_screen_list",
    "/ajax/channel/third_tag_screen",
    "/cgMini/ajax/channel/tag_screen_list",
    "/cgMini/ajax/channel/tag_screen",
  ];
  for (const endpoint of endpoints) {
    try {
      await webGet(account, `${WWW}${endpoint}`, channelParams, "https://m.66rpg.com/mini/home");
    } catch (err) {
      // Some channel endpoints are only valid for specific tag families; try the next one.
    }
    await sleep(300);
  }
  await sleep(16000);

  const latest = await getTreeTask(account, task.task_id);
  return `channel page browse attempted tid=${tid}: ${latest?.progress_bar_current ?? "?"}/${latest?.progress_bar_max ?? "?"} status=${latest?.task_status ?? "?"}; ${recordResult}`;
}

async function tryShare(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "share already done";
  }
  const gindex = requireGame(account);
  const data = await iapiPost(account, "/share/v1/share/share_game", {
    gindex,
    share_msg_id: "",
    share_channel: 3,
  });
  return `share game ${gindex}: ${data.msg || data.status}`;
}

async function doSendFlowers(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "send flowers already done";
  }
  if (!account.allowSendFlowers && !account.allow_send_flowers && !account.sendFlowers) {
    return "send flowers skipped: set allowSendFlowers: true to enable";
  }
  const remain = Math.max(0, Number(task.progress_bar_max) - Number(task.progress_bar_current));
  const gindex = account.flowerTarget || account.flower_target || requireGame(account);
  const data = await iapiPost(account, "/game/v1/pay/send_flower", {
    gindex,
    num: remain,
    flower_place: 4,
    group_id: "",
  });
  return `send flowers ${gindex} x${remain}: ${data.msg || data.status}`;
}

async function doCreateCollections(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "collections already done";
  }
  const remain = Math.max(0, Number(task.progress_bar_max) - Number(task.progress_bar_current));
  const logs = [];
  for (let i = 0; i < remain; i++) {
    const data = await iapiPost(account, "/Favorite/v1/Favorite/create_edit_fav_folder", {
      folder_name: `每日任务${Date.now().toString().slice(-6)}${i}`,
      folder_id: 0,
      folder_cover: "",
      folder_desc: "",
      is_public: 1,
      source: 1,
    });
    logs.push(data.msg || data.status);
    await sleep(300);
  }
  return `create collections: ${logs.join(", ")}`;
}

async function doReplyBountyShare(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "bounty reply already done";
  }
  const list = await iapiGet(account, "/topicPlaza/v1/home/topic_list", {
    page: 1,
    limit: 10,
    type: 0,
  });
  const topic = (list.data?.list || []).find(
    (item) => Number(item.reward_status) === 1 && String(item.uid) !== String(account.uid),
  );
  if (!topic?.topic_id) return `bounty reply no target: ${list.msg || list.status}`;

  const data = await iapiPost(account, "/topicPlaza/v1/info/reply", {
    topic_id: topic.topic_id,
    content: await publicText(),
    reply_id: 0,
    parent_id: 0,
  });
  return `bounty reply ${topic.topic_id}: ${data.msg || data.status}`;
}

async function doConfession(account, task) {
  if (Number(task.progress_bar_current) >= Number(task.progress_bar_max) || task.task_status === 1) {
    return "confession already done";
  }
  const gindex = account.confessionGameId || account.confession_gameid || requireGame(account);
  const roles = await iapiGet(account, "/bestman/bestman/v2/role/bestman_all_role_list", {
    gindex,
    page: 1,
    limit: 10,
  });
  const role = roles.data?.role?.[0];
  if (!role?.role_id) return `confession no role: ${roles.msg || roles.status}`;

  const data = await iapiPost(account, "/bestman/bestman/v1/vote/bestman_express_words", {
    gindex,
    role_id: role.role_id,
    role_words: 1,
  });
  return `confession ${role.role_id}: ${data.msg || data.status}`;
}

const TASK_ACTIONS = [
  {
    ids: [3],
    aliases: ["浏览频道页15s", "频道页15s", "频道页"],
    action: doChannelPageBrowse,
    note: "best-effort app timer task",
  },
  {
    ids: [12],
    aliases: ["浏览share页面15s", "浏览share页面", "share页面15s", "share页面"],
    action: doSharePageBrowse,
    note: "best-effort app timer task",
  },
  {
    ids: [13],
    aliases: ["狗橙推荐模式点击下一个", "推荐模式点击下一个", "浏览3次"],
    action: doDogNext,
  },
  {
    ids: [14],
    aliases: ["狗橙推荐模式收藏", "推荐模式收藏"],
    action: doDogFavorite,
  },
  {
    ids: [2],
    aliases: ["浏览动态页面并点赞", "动态页面并点赞", "点赞1次"],
    action: doDynamicLike,
  },
  {
    ids: [6],
    aliases: ["收藏任意一部作品", "收藏任意作品"],
    action: doGenericFavorite,
  },
  {
    ids: [5],
    aliases: ["分享任意一部作品", "分享任意作品"],
    action: tryShare,
  },
  {
    ids: [4],
    aliases: ["为任意作品送鲜花", "送鲜花"],
    action: doSendFlowers,
    note: "will spend real flowers",
  },
  {
    ids: [10],
    aliases: ["悬赏", "回帖"],
    action: doReplyBountyShare,
  },
  {
    ids: [7],
    aliases: ["告白", "表白"],
    action: doConfession,
  },
  {
    ids: [101],
    aliases: ["创建收藏夹", "创建合集"],
    action: doCreateCollections,
  },
];

const PASSIVE_TASK_COVERAGE = [
  {
    key: "runtime_read",
    ids: [1, 100],
    aliases: [
      "阅读任意作品满10min",
      "阅读任意作品满10分钟",
      "阅读任意作品10min",
      "阅读任意作品10分钟",
      "阅读任意作品",
      "阅读作品10min",
      "阅读作品10分钟",
      "阅读10min",
      "阅读10分钟",
    ],
    handler: "fillRuntimeTasks",
    detail: "handled before action loop by fillRuntimeTasks",
  },
];

const MANUAL_TASK_GUIDES = [
  {
    aliases: ["获得1朵鲜花", "获得鲜花"],
    guide: "claim a real login/activity flower first; this task is updated by server-side flower income",
  },
];

function findTaskRule(task, rules) {
  const id = Number(task.task_id);
  return rules.find((item) => (item.ids || []).includes(id) || taskMatches(task, item.aliases || []));
}

function findTaskAction(task) {
  return findTaskRule(task, TASK_ACTIONS);
}

function findPassiveTaskCoverage(task) {
  return findTaskRule(task, PASSIVE_TASK_COVERAGE);
}

function findManualTaskGuide(task) {
  return findTaskRule(task, MANUAL_TASK_GUIDES);
}

async function claimTreeAwards(account) {
  const taskData = await getTreeTasks(account);
  const ready = flatTasks(taskData).filter(
    (task) => Number(task.task_status) === 1 && Number(task.claim_status) === 0,
  );
  const logs = [];
  for (const task of ready) {
    const data = await postForm(account, "/ActiveSystem/ptree/claim_task_award", {
      task_id: task.task_id,
      noVer: true,
    });
    log(`橙树任务 ${Number(task.task_id)}：奖励领取接口 status=1`);
    logs.push(`${task.task_id} ${task.task_name}: ${data.msg || data.status}`);
    await sleep(300);
  }
  if (!logs.length) log("橙树奖励：当前没有已完成且待领取的奖励");
  return logs.length ? logs : ["no tree award to claim"];
}

async function claimOldActiveAwards(account) {
  const oldParams = {
    jsonCallBack: "",
    uid: account.uid,
    token: account.token,
    client: 2,
    _: Date.now(),
  };
  const listRes = await axios.get(`${WWW}/ActiveSystem/api/v1/active/get_today_task_lists`, {
    params: oldParams,
    headers: { "user-agent": UA },
    timeout: 15000,
    validateStatus: () => true,
  });
  const list = listRes.data;
  if (list.status !== 1 || !Array.isArray(list.data)) throw new Error("旧版任务列表格式异常");

  const ready = list.data.filter((task) => Number(task.status) === 1 && Number(task.unclaimed) > 0);
  const logs = [];
  for (const task of ready) {
    const claimRes = await axios.get(`${WWW}/ActiveSystem/api/v1/active/claimReward`, {
      params: {
        uid: account.uid,
        token: account.token,
        client: 2,
        task_type: task.task_type,
        _: Date.now(),
      },
      headers: { "user-agent": UA },
      timeout: 15000,
      validateStatus: () => true,
    });
    const data = claimRes.data;
    log(`旧版任务 ${Number(task.task_type)}：奖励领取接口 status=1`);
    logs.push(`old ${task.task_type} ${task.task_name}: ${data.msg || data.status}`);
    await sleep(300);
  }
  if (!logs.length) log("旧版活跃奖励：当前没有已完成且待领取的奖励");
  return logs.length ? logs : ["no old active award to claim"];
}


function readAccounts() {
  if (process.env.RPG66_ACCOUNTS !== undefined) {
    return process.env.RPG66_ACCOUNTS.split(/\r?\n/).filter(line=>line.trim()).map(line=>{
      try { return {value:JSON.parse(line)}; } catch { return {error:'账号行不是有效 JSON'}; }
    });
  }
  // 兼容原调用方的全局注入，不读取任何私有文件。
  return collectAccounts(globalThis.config?.rpg66,'rpg66').map(value=>({value}));
}
function validateAccount(item) {
  if(item.error)throw new Error(item.error);
  const a=item.value;
  if(!a || typeof a!=='object' || Array.isArray(a))throw new Error('账号必须是 JSON 对象');
  if(!/^[0-9]+$/.test(String(a.uid||'')) || typeof a.token!=='string' || !a.token.trim() || /[\r\n;]/.test(a.token))throw new Error('uid 或 token 格式错误');
  if(a.skey!==undefined && typeof a.skey!=='string')throw new Error('skey 必须为字符串');
  for(const key of ['gameid','readGameId','read_gameid','flowerTarget','flower_target','confessionGameId','confession_gameid'])if(a[key]!==undefined && !/^[0-9]+$/.test(String(a[key])))throw new Error('目标 ID 必须为数字');
  for(const key of ['token','skey'])if(a[key])secrets.add(a[key]);
  return a;
}
function notificationSelected() {
  const toggle=(process.env.QINGLONG_NOTIFY||'auto').toLowerCase();
  if(['0','false','no','off'].includes(toggle))return false;
  const selection=process.env.QINGLONG_NOTIFY_SCRIPTS;
  if(selection!==undefined) {
    const names=[CATALOG,'scripts/rpg66.js','rpg66.js','candidate.js'];
    return selection.split(/[,;\s]+/).filter(Boolean).some(pattern=>{
      const escaped=pattern.replace(/[.+?^${}()|[\]\\]/g,'\\$&').replace(/\*/g,'.*');
      return names.some(name=>new RegExp(`^${escaped}$`).test(name));
    });
  }
  return ['1','true','yes','on'].includes(toggle); // listed-only：未列入且 auto 时不发送。
}
async function notify(summary) {
  if(!notificationSelected())return '未选中或已关闭';
  if(DRY){log('断网预演：模拟通知投递，不加载可能联网的通知模块');return '预演模拟';}
  const dirs=[process.env.QINGLONG_NOTIFY_DIR,'/ql/data/scripts','/ql/scripts'].filter(Boolean);
  const filename=dirs.map(dir=>path.join(dir,'sendNotify.js')).find(file=>fs.existsSync(file));
  if(!filename){log('⚠️ 未找到 sendNotify.js，保留业务退出码');return '不可用';}
  const body=`账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}；状态 ${summary.status}`;
  return new Promise(resolve=>{
    // 子进程隔离通知错误和日志，父进程保持业务退出码；标题正文不含账号凭据。
    const code='const n=require(process.argv[1]); Promise.resolve(n.sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exitCode=1)';
    const child=spawn(process.execPath,['-e',code,filename,TITLE,body],{stdio:'ignore'});
    const timer=setTimeout(()=>child.kill('SIGKILL'),15000);
    child.once('error',()=>{clearTimeout(timer);resolve('失败');});
    child.once('close',code=>{clearTimeout(timer);resolve(code===0?'已发送':'失败');});
  });
}
async function main() {
  const started=Date.now(),stats={accounts:0,success:0,failed:0,steps:{total:0,success:0,alreadyComplete:0,skipped:0,failed:0}};
  let configError=false;
  log(`========== ${TITLE} ==========`);log(`开始时间：${new Date(started).toISOString()}；模式：${DRY?'断网预演':'正式执行'}`);
  let items=[];let enabled=new Set();
  try {
    items=readAccounts();stats.accounts=items.length;
    for(const item of items)for(const key of ['token','skey'])if(typeof item.value?.[key]==='string'&&item.value[key])secrets.add(item.value[key]);
    const names=(process.env.RPG66_TASKS??DEFAULT_TASKS.join(',')).split(',').map(x=>x.trim()).filter(Boolean);
    if(!names.length||names.some(name=>!ALL_TASKS.has(name)))throw new Error('RPG66_TASKS 包含未知任务或为空');
    enabled=new Set(names);
    if(!items.length)throw new Error('缺少 RPG66_ACCOUNTS，每行一个账号 JSON');
  }catch{configError=true;log('❌ 配置错误：请检查账号变量和任务开关');}
  log(`账号数量：${items.length}`);
  for(let index=0;index<items.length;index++) {
    const begin=Date.now(),local={total:0,success:0,alreadyComplete:0,skipped:0,failed:0};let number=0;
    async function stage(name,fn) {
      const start=Date.now();number++;local.total++;log(`账号 ${index+1} 阶段 ${number}：${name}`);
      try {const result=await fn();const state=result==='skip'?'skipped':result==='already'?'alreadyComplete':'success';local[state]++;log(`${state==='skipped'?'⏭️':state==='alreadyComplete'?'☑️':'✅'} 阶段 ${number} ${name}：${DRY?'预演通过':state==='skipped'?'已跳过':state==='alreadyComplete'?'已完成':'核验通过'}，耗时 ${Date.now()-start}ms`);return true;}
      catch{local.failed++;log(`❌ 阶段 ${number} ${name}：未通过配置、接口或进度核验，耗时 ${Date.now()-start}ms`);return false;}
    }
    let account;
    const valid=await stage('账号配置',async()=>{account=validateAccount(items[index]);});
    if(valid && !configError) {
      if(DRY) {
        for(const name of enabled)await stage(`执行计划 ${name}`,async()=>{validateActionConfig(account,name);});
        await stage('公开内容预演',async()=>{await publicText();});
      } else {
        if(enabled.has('balance'))await stage('鲜橙余额查询',async()=>{const res=await get(account,'/ActiveSystem/PtreeShop/get_user_account_money');if(!['string','number'].includes(typeof res.data?.fov_value)||!Number.isFinite(Number(res.data.fov_value)))throw new Error('缺少有效余额');log(`鲜橙余额：${res.data.fov_value}`);});
        if(enabled.has('sign'))await stage('每日签到',()=>signIn(account));
        const actionsEnabled=ACTION_NAMES.some(name=>enabled.has(name))||enabled.has('runtime');
        if(actionsEnabled) {
          let tasks;
          const loaded=await stage('读取并盘点橙树任务',async()=>{
            const data=await getTreeTasks(account);tasks=flatTasks(data);
            if(!data || !['day','week','timed','growth'].some(k=>Array.isArray(data[k]?.list)))throw new Error('任务列表契约不匹配');
            for(const t of tasks)log(`任务 ${Number(t.task_id)}：进度 ${Number(t.progress_bar_current)}/${Number(t.progress_bar_max)}，领取状态 ${Number(t.claim_status)}`);
          });
          if(loaded) {
            if(enabled.has('runtime'))await stage('阅读时长上报',async()=>{
              validateActionConfig(account,'runtime');const pending=tasks.filter(t=>findPassiveTaskCoverage(t)&&isTaskPending(t));
              if(!pending.length)return 'already';await fillRuntimeTasks(account,pending);
              const current=flatTasks(await getTreeTasks(account));
              if(pending.some(t=>!current.some(n=>Number(n.task_id)===Number(t.task_id)&&!isTaskPending(n))))throw new Error('阅读进度未完成');
            });
            for(const task of tasks) {
              const rule=findTaskAction(task);if(!rule) {if(isTaskPending(task))log(`⏭️ 任务 ${Number(task.task_id)}：需手动完成或暂无适配规则`);continue;}
              const name=ACTION_NAMES[TASK_ACTIONS.indexOf(rule)];
              await stage(`橙树任务 ${Number(task.task_id)} ${name}`,async()=>{
                if(!isTaskPending(task))return 'already';if(!enabled.has(name))return 'skip';
                validateActionConfig(account,name);
                const latest=await getTreeTask(account,task.task_id);
                if(!latest)throw new Error('任务不存在');if(!isTaskPending(latest))return 'already';
                await rule.action(account,latest);
                const after=await getTreeTask(account,task.task_id);
                if(!after || isTaskPending(after))throw new Error('动作完成后任务进度尚未通过');
              });
            }
          }
        }
        if(enabled.has('claim-tree'))await stage('领取已完成橙树奖励',()=>claimTreeAwards(account));
        if(enabled.has('claim-old'))await stage('领取已完成旧版活跃奖励',()=>claimOldActiveAwards(account));
      }
    } else if(configError && valid) {local.failed++;local.total++;}
    if(local.failed)stats.failed++;else stats.success++;
    for(const key of Object.keys(local))stats.steps[key]+=local[key];
    log(`账号 ${index+1} 统计：总任务 ${local.total}，成功 ${local.success}，已完成 ${local.alreadyComplete}，跳过 ${local.skipped}，失败 ${local.failed}，耗时 ${Date.now()-begin}ms`);
  }
  const exitCode=configError||stats.failed?1:0;
  const status=configError?'configuration-error':stats.failed?(stats.success?'partial-failure':'failure'):DRY?'dry-run':'success';
  const summary={...stats,status,mode:DRY?'dry-run':'live',exitCode};
  let notification='失败';try{notification=await notify(summary);}catch{log('⚠️ 通知失败，保留业务退出码');}
  log('----------------------------------------');
  log(`最终统计：账号 ${stats.accounts}，成功 ${stats.success}，失败 ${stats.failed}；子任务 ${JSON.stringify(stats.steps)}；总耗时 ${Date.now()-started}ms`);
  log(`完成时间：${new Date().toISOString()}；最终状态：${status}；通知：${notification}`);
  console.log('TASK_SUMMARY='+JSON.stringify({...summary,notification,durationMs:Date.now()-started}));
  process.exitCode=exitCode;
  return summary;
}
function validateActionConfig(account,name) {
  if(['favorite','share'].includes(name))requireGame(account);
  if(name==='runtime' && ![account.readGameId,account.read_gameid,account.gameid].some(Boolean))throw new Error('需要阅读作品 ID');
  if(name==='flowers') {
    if(![account.allowSendFlowers,account.allow_send_flowers,account.sendFlowers].some(v=>v===true))throw new Error('送花须显式设置 true');
    if(!account.flowerTarget&&!account.flower_target)requireGame(account);
  }
  if(name==='confession'&&!account.confessionGameId&&!account.confession_gameid)requireGame(account);
}
if(require.main===module)main().catch(()=>{log('❌ 执行器异常');process.exitCode=1;});
module.exports=main;
