// name: 超星学习通巡课签到
// cron: */10 7-22 * * *
/**
 * 超星学习通（chaoxing）网课巡视签到 · 青龙独立维护版
 *
 * 上游：snomiao/chaoxing-assistant.js · chaoxing-assistant.js
 * 仓库：https://github.com/snomiao/chaoxing-assistant.js.git
 * 分支：master
 * 提交：ad5a1cde2a3805cbb9bfe6cad6caf6d9c1d791e8
 * 授权：GPL-3.0
 *
 * 功能盘点（主来源 chaoxing-assistant.js；maintainedFeatureCoverage 为空，无重复覆盖）：
 * - 账号密码登录 passport2.chaoxing.com/api/login，校验 Cookie 含 UID
 * - 访问应用中心校验登录有效；读取账号资料与课程表
 * - 轮询各课程可用签到活动，执行普通/手势签到并核对签到状态
 * - 检查待完成任务点与作业状态变化（只读提示，不自动提交作业）
 * - 可选报告地址（%s 占位）推送巡视摘要；默认关闭，不写本地缓存文件
 * - 上游 config.yaml / cache.yaml / node-fetch / yaml 依赖改为环境变量 + Node 内置 HTTP
 *
 * CHAOXING_ACCOUNTS（必填）：每行一个账号，格式「账号,密码」；只在第一个逗号处拆分，
 * 密码中后续逗号原样保留。可选备注：「备注|账号,密码」，只在首个 | 处拆分。
 * 不使用 & 或 @ 分隔账号。账号与密码为超星学习通本人登录凭据。
 * CHAOXING_SCHOOLID（可选）：单位账号学校 ID，默认空；个人账号通常不填。
 * CHAOXING_REPORT_URL（可选）：报告推送地址，可用 %s 占位巡视摘要；未设置则不推送。
 * CHAOXING_DRY_RUN=1：完全断网预演，只校验参数并模拟流程与通知摘要（不投递）。
 * CHAOXING_TIMEOUT_MS：请求超时毫秒，默认 20000（1000–60000）。
 * QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
 *
 * Copyright (C) 2020 snomiao
 * Copyright (C) 2026 Qinglong maintained adaptation
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
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
    const identities = ["413b9423260e2104", "scripts/chaoxing_assistant.js", "chaoxing_assistant.js", "chaoxing_assistant"];
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
const { URL } = require('node:url');
const { execFile } = require('node:child_process');

const TITLE = '超星学习通巡课签到';
const CATALOG_ID = '413b9423260e2104';
const CREDENTIAL_ENV = 'CHAOXING_ACCOUNTS';
const DRY_RUN_ENV = 'CHAOXING_DRY_RUN';
const UA =
  'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.100 Safari/537.36';
const DEFAULT_TIMEOUT_MS = 20000;
const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;
const ACCOUNT_GAP_MS = 2000;
const REQUEST_GAP_MS = 200;

const secrets = new Set();
const stamp = () =>
  new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
const nowText = () =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
    .format(new Date())
    .replace(/\//g, '-');
const log = (text) => console.log(`[${stamp()}] ${text}`);
const enabled = (value) => /^(1|true|yes|on)$/i.test(String(value || '').trim());
const disabled = (value) => /^(0|false|no|off)$/i.test(String(value || '').trim());

function remember(value) {
  if (typeof value === 'string' && value) secrets.add(value);
}

function redact(value) {
  let text = String(value == null ? '' : value).replace(
    /[\r\n\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    ' '
  );
  for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
    if (secret) text = text.split(secret).join('[已隐藏]');
  }
  text = text.replace(/(Cookie|cookie|token|Token|UID|puid)=([^;\s&]+)/gi, '$1=[已隐藏]');
  text = text.replace(/\+?\d[\d ()-]{8,}\d/g, '[号码已隐藏]');
  return text;
}

function timeoutMs() {
  const value = Number.parseInt(process.env.CHAOXING_TIMEOUT_MS || '', 10);
  return Number.isFinite(value) && value >= 1000 && value <= 60000 ? value : DEFAULT_TIMEOUT_MS;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function notificationSelected() {
  if (disabled(process.env.QINGLONG_NOTIFY)) return false;
  if (enabled(process.env.QINGLONG_NOTIFY)) return true;
  if (process.env.QINGLONG_NOTIFY_SCRIPTS === undefined) return false; /* listed-only default */
  const raw = process.env.QINGLONG_NOTIFY_SCRIPTS;
  if (String(raw).trim() === '') return false;
  const selectors = String(raw).split(/[,;\s]+/).filter(Boolean);
  if (selectors.includes('*')) return true;
  const filename = path.basename(process.argv[1] || 'candidate.js');
  const names = [
    CATALOG_ID,
    'scripts/chaoxing_assistant.js',
    'chaoxing_assistant.js',
    'chaoxing-assistant.js',
    'chaoxing',
    filename,
    'candidate.js',
  ];
  return selectors.some((selector) => {
    const pattern =
      '^' +
      selector
        .split('*')
        .map((part) =>
          part
            .split('?')
            .map((token) => token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
            .join('.')
        )
        .join('.*') +
      '$';
    return names.some((name) => new RegExp(pattern, 'i').test(name));
  });
}

function parseAccounts(raw) {
  const schoolidDefault = String(process.env.CHAOXING_SCHOOLID || '').trim();
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line, index) => {
    remember(line);
    let label = '';
    let credential = line;
    const pipe = line.indexOf('|');
    if (pipe > 0) {
      label = line.slice(0, pipe).trim();
      credential = line.slice(pipe + 1).trim();
    }
    const comma = credential.indexOf(',');
    const account = comma < 0 ? '' : credential.slice(0, comma).trim();
    const password = comma < 0 ? '' : credential.slice(comma + 1);
    remember(account);
    remember(password);
    const accountOk = account.length > 0 && !/[\r\n]/.test(account);
    const passwordOk = password.length > 0 && !/[\r\n]/.test(password);
    return {
      index: index + 1,
      label,
      account,
      password,
      schoolid: schoolidDefault,
      valid: accountOk && passwordOk,
    };
  });
}

function allMatches(str, reg) {
  if (!reg.global) return [];
  const coll = [];
  let match;
  while ((match = reg.exec(str))) coll.push(match);
  return coll;
}

function extractMap(html, regex, mapper) {
  const out = {};
  for (const match of allMatches(html, regex)) {
    const [key, value] = mapper(match);
    if (key != null) out[key] = value;
  }
  return out;
}

function loginUrl({ account, password, schoolid = '', verify = 0 }) {
  return (
    'https://passport2.chaoxing.com/api/login?name=' +
    encodeURIComponent(account) +
    '&pwd=' +
    encodeURIComponent(password) +
    '&schoolid=' +
    encodeURIComponent(schoolid || '') +
    '&verify=' +
    encodeURIComponent(String(verify))
  );
}

const URLS = {
  apps: () => 'https://i.mooc.chaoxing.com/app/myapps.shtml',
  profile: () => `https://i.mooc.chaoxing.com/settings/info?t=${Date.now()}`,
  courses: () => `https://mooc1-1.chaoxing.com/visit/interaction?t=${Date.now()}`,
  courseHome: ({ courseId, classId, enc }) =>
    `https://mooc1-1.chaoxing.com/mycourse/studentcourse?courseId=${courseId}&vc=1&clazzid=${classId}&enc=${enc}`,
  courseTasks: ({ courseId, classId }) =>
    `https://mobilelearn.chaoxing.com/widget/pcpick/stu/index?courseId=${courseId}&jclassId=${classId}`,
  normalSign: ({ courseId, classId, activeId, fid = '' }) =>
    `https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/preSign?activeId=${activeId}&classId=${classId}&fid=${fid}&courseId=${courseId}`,
  gestureSign: ({ courseId, classId, activeId }) =>
    `https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/signIn?&courseId=${courseId}&classId=${classId}&activeId=${activeId}`,
  homework: ({ courseId, classId, enc, cpi, openc }) =>
    `https://mooc1-1.chaoxing.com/work/getAllWork?classId=${classId}&courseId=${courseId}&isdisplaytable=2&mooc=1&ut=s&enc=${enc}&cpi=${cpi}&openc=${openc}`,
};

function extractCourses(html) {
  return extractMap(
    html,
    /<a .*?courseId=(\d+).*?clazzid=(\d+).*?enc=(\w+).*?title="(.*?)"[\s\S]*?<p title="(.*?)">/g,
    ([, courseId, classId, enc, title, teacher]) => [
      classId,
      { courseId, enc, classId, name: title, teacher },
    ]
  );
}

function extractCourseToken(html) {
  return extractMap(
    html,
    /clazzId.*?'(\w+?)'[\s\S]*?courseId.*?'(\w+?)'[\s\S]*?cpi.*?'(\w+?)'[\s\S]*?openc.*?'(\w+?)'[\s\S]*?(?:(待完成任务点))?/g,
    ([, classId, courseId, cpi, openc, pending]) => [
      classId,
      {
        classId,
        courseId,
        cpi,
        openc,
        pendingTasks: !!pending,
      },
    ]
  );
}

function extractActiveSigns(html) {
  return extractMap(
    html,
    /activeDetail\((\d+),2,null\)[\s\S]*?<dd class="green">(.*?)<[\s\S]*?<a.*?>(.*?)</g,
    ([, activeId, type, title]) => [activeId, { activeId, type, title }]
  );
}

function extractHomework(html) {
  return extractMap(
    html,
    /<a.*?courseId=(\d+).*?classId=(\d+).*?workId=(\d+)(?:.*?workAnswerId=(\d+))?.*?title="(.*?)"[\s\S]*?开始时间.*>(.*?)<[\s\S]*?截止时间.*?>(.*?)<[\s\S]*?作业状态[\s\S]*?<strong>\s*(.*?)\s*?</g,
    ([, courseId, classId, workId, workAnswerId, title, startAt, endAt, status]) => [
      workId,
      { courseId, classId, workId, workAnswerId, title, startAt, endAt, status },
    ]
  );
}

function extractSignStatus(html) {
  return extractMap(
    html,
    /id="activeId".*?"(.*?)"[\s\S]*?id="activeStatus".*?"(.*?)"[\s\S]*?id="courseId".*?"(.*?)"[\s\S]*?id="classId".*?"(.*?)"[\s\S]*?id="puid".*?"(.*?)"[\s\S]*?id="createUid".*?"(.*?)"[\s\S]*?id="fid".*?"(.*?)"[\s\S]*?<em id="st">(.*?)</g,
    ([, activeId, activeStatus, courseId, classId, puid, createUid, fid, succTimeRaw]) => [
      activeId,
      { activeId, activeStatus, courseId, classId, puid, createUid, fid, succTimeRaw },
    ]
  );
}

function extractProfile(html) {
  const map = extractMap(
    html,
    /\$\("#(.*?male)"\)\.attr\("checked","checked"\)[\s\S]*?id="resetIDspac" title="(.*?)"/g,
    ([, gender, studentNo]) => [
      'profile',
      { gender: gender === 'female' ? '女' : '男', studentNo },
    ]
  );
  return map.profile || null;
}

function parseSetCookie(headerValue) {
  const values = Array.isArray(headerValue) ? headerValue : headerValue ? [headerValue] : [];
  const parts = [];
  for (const item of values) {
    const match = String(item).match(/(.*?)=(.*?)(?=;|$)/);
    if (match) {
      parts.push(match[0]);
      remember(match[2]);
    }
  }
  return parts.join('; ');
}

function commonHeaders(cookie) {
  const headers = {
    'User-Agent': UA,
    Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
  };
  if (cookie) headers.Cookie = cookie;
  return headers;
}

function httpRequest(urlString, { method = 'GET', headers = {}, body = null, redirect = 'manual' } = {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const deadline = Date.now() + timeoutMs();
    const fail = (code) => {
      if (settled) return;
      settled = true;
      reject(new Error(code));
    };
    let parsed;
    try {
      parsed = new URL(urlString);
    } catch {
      return fail('invalid-url');
    }
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return fail('invalid-url');
    const remaining = deadline - Date.now();
    if (remaining <= 0) return fail('timeout');
    const lib = parsed.protocol === 'https:' ? https : http;
    const payload = body == null ? null : Buffer.from(String(body), 'utf8');
    const reqHeaders = { ...headers };
    if (payload) reqHeaders['Content-Length'] = String(payload.length);
    const req = lib.request(
      {
        protocol: parsed.protocol,
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
        path: parsed.pathname + parsed.search,
        method,
        headers: reqHeaders,
        timeout: remaining,
      },
      (res) => {
        if (
          redirect === 'follow' &&
          res.statusCode >= 300 &&
          res.statusCode < 400 &&
          res.headers.location
        ) {
          const next = new URL(res.headers.location, parsed).toString();
          res.resume();
          settled = true;
          httpRequest(next, { method, headers, body: null, redirect })
            .then(resolve)
            .catch(reject);
          return;
        }
        const parts = [];
        let size = 0;
        res.on('data', (chunk) => {
          size += chunk.length;
          if (size > MAX_RESPONSE_BYTES) {
            fail('response-too-large');
            res.destroy();
            req.destroy();
            return;
          }
          parts.push(chunk);
        });
        res.on('error', () => fail('response-error'));
        res.on('aborted', () => fail('response-aborted'));
        res.on('end', () => {
          if (settled) return;
          settled = true;
          resolve({
            statusCode: res.statusCode || 0,
            headers: res.headers,
            text: Buffer.concat(parts).toString('utf8'),
          });
        });
      }
    );
    req.on('timeout', () => {
      fail('timeout');
      req.destroy();
    });
    req.on('error', () => fail('network-error'));
    if (payload) req.write(payload);
    req.end();
  });
}

async function studentGet(cookie, url) {
  await sleep(REQUEST_GAP_MS);
  const response = await httpRequest(url, {
    method: 'GET',
    headers: commonHeaders(cookie),
    redirect: 'manual',
  });
  if (response.statusCode >= 300 && response.statusCode < 400) {
    throw new Error('unexpected-redirect');
  }
  if (response.statusCode < 200 || response.statusCode >= 400) {
    throw new Error(`http-${response.statusCode}`);
  }
  return response;
}

function showIdentity(payload, accountIndex) {
  if (!payload || typeof payload !== 'object') return;
  const fields = ['realname', 'nickname', 'username', 'name', 'uid', 'puid'];
  for (const field of fields) {
    const value = payload[field];
    if ((typeof value === 'string' && value) || typeof value === 'number') {
      log(`账号 ${accountIndex} 官方身份（${field}）：${redact(String(value))}`);
      return;
    }
  }
}

async function login(account) {
  const response = await httpRequest(loginUrl(account), {
    method: 'GET',
    headers: commonHeaders(),
  });
  const cookie = parseSetCookie(response.headers['set-cookie']);
  let payload = {};
  try {
    payload = JSON.parse(response.text);
  } catch {
    throw new Error('login-non-json');
  }
  if (!/UID=/i.test(cookie)) {
    const msg =
      (payload && (payload.errorMessage || payload.msg || payload.message)) || '未检测到 UID Cookie';
    throw new Error(`login-business:${msg}`);
  }
  remember(cookie);
  showIdentity(payload, account.index);
  return {
    cookie,
    realname: typeof payload.realname === 'string' ? payload.realname : '',
    uid: payload.uid != null ? String(payload.uid) : '',
  };
}

async function loginValid(cookie) {
  try {
    const response = await httpRequest(URLS.apps(), {
      method: 'GET',
      headers: commonHeaders(cookie),
      redirect: 'manual',
    });
    return response.statusCode === 200;
  } catch {
    return false;
  }
}

function signSucceeded(html, signMap) {
  const text = String(html || '');
  if (/签到成功|已签到|success/i.test(text) && !/签到失败|请先登录/i.test(text)) {
    return true;
  }
  for (const item of Object.values(signMap || {})) {
    if (item && (item.succTimeRaw || String(item.activeStatus) === '1' || String(item.activeStatus) === '2')) {
      return true;
    }
  }
  return false;
}

async function signActivity(cookie, course, activity) {
  const gestureHtml = (await studentGet(cookie, URLS.gestureSign({ ...course, ...activity }))).text;
  let signMap = extractSignStatus(gestureHtml);
  if (signSucceeded(gestureHtml, signMap)) {
    return { state: 'success', message: `${activity.title || activity.activeId} 签到成功` };
  }
  const normalHtml = (
    await studentGet(cookie, URLS.normalSign({ ...course, ...activity, fid: '' }))
  ).text;
  signMap = { ...signMap, ...extractSignStatus(normalHtml) };
  if (signSucceeded(normalHtml, signMap)) {
    return { state: 'success', message: `${activity.title || activity.activeId} 签到成功` };
  }
  if (/已签到|重复签到|你已签过到/i.test(gestureHtml + normalHtml)) {
    return { state: 'alreadyComplete', message: `${activity.title || activity.activeId} 已签到` };
  }
  throw new Error(`sign-business:${activity.title || activity.activeId} 未确认签到成功`);
}

async function patrolCourse(cookie, course) {
  const notes = [];
  const taskStats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };

  const taskPage = (await studentGet(cookie, URLS.courseTasks(course))).text;
  const activities = extractActiveSigns(taskPage);
  const activityList = Object.values(activities);
  if (!activityList.length) {
    taskStats.total += 1;
    taskStats.skipped += 1;
    notes.push('无进行中签到');
  } else {
    for (const activity of activityList) {
      taskStats.total += 1;
      try {
        const result = await signActivity(cookie, course, activity);
        if (result.state === 'success') {
          taskStats.success += 1;
          notes.push(result.message);
        } else if (result.state === 'alreadyComplete') {
          taskStats.alreadyComplete += 1;
          notes.push(result.message);
        }
      } catch (err) {
        taskStats.failure += 1;
        notes.push(redact(err && err.message));
      }
    }
  }

  try {
    const homeHtml = (await studentGet(cookie, URLS.courseHome(course))).text;
    const tokenMap = extractCourseToken(homeHtml);
    const token = tokenMap[course.classId] || Object.values(tokenMap)[0];
    if (token) {
      Object.assign(course, token);
      if (token.pendingTasks) notes.push('有待完成任务点');
      if (course.openc) {
        const hwHtml = (await studentGet(cookie, URLS.homework(course))).text;
        const homework = extractHomework(hwHtml);
        const pending = Object.values(homework).filter((item) => item.status && item.status !== '已完成');
        if (pending.length) {
          notes.push(
            pending
              .slice(0, 5)
              .map((item) => `${item.title}${item.status}`)
              .join('、')
          );
        }
      }
    }
  } catch {
    notes.push('任务/作业只读检查跳过');
  }

  return { notes, taskStats, failed: taskStats.failure > 0 };
}

async function optionalReport(content) {
  const urlTemplate = String(process.env.CHAOXING_REPORT_URL || '').trim();
  if (!urlTemplate) return '未配置报告地址';
  if (!/^https:\/\//i.test(urlTemplate)) throw new Error('report-url-insecure');
  const target = urlTemplate.replace(/%s/g, encodeURIComponent(content));
  await httpRequest(target, { method: 'GET', headers: commonHeaders(), redirect: 'follow' });
  return '报告已请求';
}

async function sendNotify(body, dryRun) {
  if (!notificationSelected()) return '已关闭';
  if (dryRun) return '通知预演已跳过真实投递（断网）';

  const jsCandidates = [
    process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'),
    '/ql/data/scripts/sendNotify.js',
    '/ql/scripts/sendNotify.js',
  ].filter(Boolean);
  const jsFile = jsCandidates.find((file) => fs.existsSync(file));
  if (jsFile) {
    const code = `
      Promise.resolve()
        .then(() => require(process.argv[1]).sendNotify(process.argv[2], process.argv[3]))
        .catch(() => { process.exitCode = 1; });
    `;
    const env = { ...process.env };
    delete env.CHAOXING_ACCOUNTS;
    delete env.CHAOXING_REPORT_URL;
    return new Promise((resolve) => {
      execFile(
        process.execPath,
        ['-e', code, jsFile, TITLE, body],
        { env, timeout: 10000, maxBuffer: 65536 },
        (err) => resolve(err ? '通知失败（保留业务退出码）' : '通知已发送')
      );
    });
  }

  const pyCandidates = [
    process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR, 'notify.py'),
    '/ql/data/scripts/notify.py',
    '/ql/scripts/notify.py',
  ].filter(Boolean);
  const pyFile = pyCandidates.find((file) => fs.existsSync(file));
  if (pyFile) {
    const env = { ...process.env };
    delete env.CHAOXING_ACCOUNTS;
    delete env.CHAOXING_REPORT_URL;
    const script = `
import importlib.util, sys
spec = importlib.util.spec_from_file_location('ql_notify', sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
send = getattr(mod, 'send', None) or getattr(mod, 'notify', None)
if callable(send):
    send(sys.argv[2], sys.argv[3])
else:
    sys.exit(1)
`;
    return new Promise((resolve) => {
      execFile(
        'python3',
        ['-c', script, pyFile, TITLE, body],
        { env, timeout: 10000, maxBuffer: 65536 },
        (err) => resolve(err ? '通知失败（保留业务退出码）' : '通知已发送')
      );
    });
  }
  return '通知不可用（未找到青龙 notify）';
}

function reasonText(code) {
  const map = {
    timeout: '请求超时',
    'response-too-large': '响应过大',
    'network-error': '网络请求失败',
    'response-error': '响应读取失败',
    'response-aborted': '响应中断',
    'invalid-url': '地址无效',
    'login-non-json': '登录接口返回非 JSON',
    'unexpected-redirect': '会话失效或被重定向',
    'report-url-insecure': '报告地址必须使用 HTTPS',
  };
  if (map[code]) return map[code];
  if (String(code).startsWith('login-business:')) {
    return `登录失败：${redact(String(code).slice('login-business:'.length))}`;
  }
  if (String(code).startsWith('sign-business:')) {
    return `签到失败：${redact(String(code).slice('sign-business:'.length))}`;
  }
  if (String(code).startsWith('http-')) return `HTTP 状态异常：${String(code).slice(5)}`;
  return redact(code || '请求失败');
}

function mergeStats(target, part) {
  target.total += part.total;
  target.success += part.success;
  target.alreadyComplete += part.alreadyComplete;
  target.skipped += part.skipped;
  target.failure += part.failure;
}

async function processAccount(account, dryRun, summary) {
  const began = Date.now();
  const who = account.label ? `（${account.label}）` : '';
  const accountStats = { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 };
  let identity = account.label || `账号${account.index}`;
  let failed = false;
  const notes = [];

  log(`账号 ${account.index}${who} | 子阶段 1/4：登录`);
  accountStats.total += 1;
  let session = null;
  if (dryRun) {
    accountStats.skipped += 1;
    log('⏭️ DRY_RUN_OK：凭据格式通过；未请求登录接口');
  } else {
    try {
      session = await login(account);
      if (!(await loginValid(session.cookie))) {
        throw new Error('login-business:登录后会话无效');
      }
      if (session.realname) identity = session.realname;
      else if (session.uid) identity = `UID:${session.uid}`;
      accountStats.success += 1;
      log(`✅ 登录成功（身份：${redact(identity)}）`);
    } catch (err) {
      accountStats.failure += 1;
      failed = true;
      log(`❌ ${reasonText(err && err.message)}；未确认登录成功`);
    }
  }

  log(`账号 ${account.index}${who} | 子阶段 2/4：课程表`);
  accountStats.total += 1;
  let courses = {};
  if (dryRun) {
    accountStats.skipped += 1;
    log('⏭️ DRY_RUN_OK：未请求课程表');
  } else if (!session) {
    accountStats.skipped += 1;
    log('⏭️ 因登录失败跳过课程表');
  } else {
    try {
      try {
        const profileHtml = (await studentGet(session.cookie, URLS.profile())).text;
        const profile = extractProfile(profileHtml);
        if (profile && session.realname) {
          /* 学号不输出；仅用 realname 作为身份 */
        }
      } catch {
        /* 资料页失败不阻断签到 */
      }
      const courseHtml = (await studentGet(session.cookie, URLS.courses())).text;
      courses = extractCourses(courseHtml);
      const count = Object.keys(courses).length;
      if (!count) throw new Error('未解析到课程');
      accountStats.success += 1;
      log(`✅ 课程表刷新：${count} 门课`);
    } catch (err) {
      accountStats.failure += 1;
      failed = true;
      log(`❌ 课程表失败：${reasonText(err && err.message)}`);
    }
  }

  log(`账号 ${account.index}${who} | 子阶段 3/4：巡课签到与作业检查`);
  if (dryRun) {
    accountStats.total += 1;
    accountStats.skipped += 1;
    log('⏭️ DRY_RUN_OK：未请求签到/作业接口，未验证真实业务');
  } else if (!session || !Object.keys(courses).length) {
    accountStats.total += 1;
    accountStats.skipped += 1;
    log('⏭️ 因前置失败跳过巡课');
  } else {
    for (const course of Object.values(courses)) {
      log(`### ${redact(course.name || course.courseId)}`);
      try {
        const result = await patrolCourse(session.cookie, course);
        mergeStats(accountStats, result.taskStats);
        if (result.notes.length) notes.push(`${course.name}：${result.notes.join('，')}`);
        if (result.failed) failed = true;
        if (result.taskStats.failure) {
          log(`❌ ${redact(course.name)} 存在签到失败`);
        } else if (result.taskStats.success || result.taskStats.alreadyComplete) {
          log(`✅ ${redact(course.name)}：${result.notes.join('，') || '巡视完成'}`);
        } else {
          log(`☑️ ${redact(course.name)}：${result.notes.join('，') || '无待办签到'}`);
        }
      } catch (err) {
        accountStats.total += 1;
        accountStats.failure += 1;
        failed = true;
        log(`❌ ${redact(course.name)} 巡视失败：${reasonText(err && err.message)}`);
      }
    }
  }

  log(`账号 ${account.index}${who} | 子阶段 4/4：可选报告`);
  accountStats.total += 1;
  if (dryRun) {
    accountStats.skipped += 1;
    log('⏭️ DRY_RUN_OK：未请求报告地址');
  } else if (failed || !session) {
    accountStats.skipped += 1;
    log('⏭️ 因账号失败跳过报告');
  } else if (!String(process.env.CHAOXING_REPORT_URL || '').trim()) {
    accountStats.skipped += 1;
    log('⏭️ 未配置 CHAOXING_REPORT_URL，跳过报告');
  } else {
    try {
      const content = `${identity}：${notes.join('；') || '巡视完成'}。`;
      const reportResult = await optionalReport(content);
      accountStats.success += 1;
      log(`✅ ${reportResult}`);
    } catch (err) {
      accountStats.failure += 1;
      failed = true;
      log(`❌ 报告失败：${reasonText(err && err.message)}`);
    }
  }

  mergeStats(summary.tasks, accountStats);
  if (failed) summary.failedAccounts += 1;
  else summary.successfulAccounts += 1;

  log(
    `账号 ${account.index}（${redact(identity)}）统计：总任务 ${accountStats.total} | 成功 ${accountStats.success} | 已完成 ${accountStats.alreadyComplete} | 跳过 ${accountStats.skipped} | 失败 ${accountStats.failure} | 耗时 ${Date.now() - began}ms`
  );
}

async function main() {
  const started = Date.now();
  const dryRun = enabled(process.env[DRY_RUN_ENV]);
  const accounts = parseAccounts(process.env[CREDENTIAL_ENV]);
  const summary = {
    task: TITLE,
    catalogId: CATALOG_ID,
    mode: dryRun ? 'dry-run' : 'live',
    accounts: accounts.length,
    successfulAccounts: 0,
    failedAccounts: 0,
    tasks: { total: 0, success: 0, alreadyComplete: 0, skipped: 0, failure: 0 },
    status: '',
    notification: '',
  };

  console.log('========================================');
  console.log(`【${TITLE}】`);
  console.log(`开始时间：${nowText()}`);
  console.log(`运行模式：${dryRun ? 'DRY_RUN（完全断网）' : 'LIVE'}`);
  console.log(`账号数量：${accounts.length}`);
  console.log('========================================');

  log('阶段 1/3：配置检查');
  const configStarted = Date.now();
  let configurationError = false;
  if (!accounts.length) {
    configurationError = true;
    log(`❌ 配置错误：缺少 ${CREDENTIAL_ENV} 的非空账号行`);
  } else {
    for (const account of accounts) {
      if (!account.valid) {
        configurationError = true;
        log(`❌ 配置错误：账号 ${account.index} 格式无效，应为「账号,密码」或「备注|账号,密码」`);
      }
    }
  }
  const reportUrl = String(process.env.CHAOXING_REPORT_URL || '').trim();
  if (reportUrl && !/^https:\/\//i.test(reportUrl)) {
    configurationError = true;
    log('❌ 配置错误：CHAOXING_REPORT_URL 必须是 https:// 开头');
  }
  log(
    `阶段 1 完成：${configurationError ? '❌ 配置未通过' : '✅ 账号行已读取'} | 耗时 ${Date.now() - configStarted}ms`
  );

  if (!configurationError) {
    log('阶段 2/3：账号巡课签到');
    for (let i = 0; i < accounts.length; i++) {
      await processAccount(accounts[i], dryRun, summary);
      if (!dryRun && i < accounts.length - 1) await sleep(ACCOUNT_GAP_MS);
    }
  }

  const exitCode = configurationError || summary.failedAccounts ? 1 : 0;
  summary.status = configurationError
    ? 'configuration-error'
    : summary.failedAccounts
      ? summary.successfulAccounts
        ? 'partial-failure'
        : 'failure'
      : dryRun
        ? 'dry-run'
        : 'success';

  const body =
    `状态：${summary.status}；账号总数：${summary.accounts}；成功数：${summary.successfulAccounts}；` +
    `失败数：${summary.failedAccounts}；签到成功：${summary.tasks.success}；已完成：${summary.tasks.alreadyComplete}；` +
    `预演跳过：${summary.tasks.skipped}`;

  log('阶段 3/3：脱敏总结通知');
  const notifyStarted = Date.now();
  summary.notification = await sendNotify(body, dryRun);
  log(`阶段 3 完成：${summary.notification} | 耗时 ${Date.now() - notifyStarted}ms`);

  summary.durationMs = Date.now() - started;
  summary.finishedAt = nowText();
  console.log('----------------------------------------');
  log(body);
  log(
    `子任务统计：总数 ${summary.tasks.total} | 成功 ${summary.tasks.success} | 已完成 ${summary.tasks.alreadyComplete} | 跳过 ${summary.tasks.skipped} | 失败 ${summary.tasks.failure}`
  );
  log(
    `总耗时：${summary.durationMs}ms | 完成时间：${summary.finishedAt} | 通知状态：${summary.notification} | 最终状态：${summary.status}`
  );
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
}

if (require.main === module) {
  main().catch(() => {
    process.exitCode = 1;
    console.error('任务执行异常（已脱敏）');
  });
}

module.exports = {
  parseAccounts,
  extractCourses,
  extractActiveSigns,
  extractSignStatus,
  signSucceeded,
  loginUrl,
};
