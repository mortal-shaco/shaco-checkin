// name: 阿里云社区
// cron: 36 7,13 * * *
/*
name: 阿里云社区
new Env('阿里云社区')
cron: 36 7,13 * * *
原作者：Leiyiyan。来源：https://github.com/leiyiyan/resource/blob/main/script/aliyun_web/aliyun_web.js
青龙适配修改：llle0x，2026-10-04。按现行任务列表更新执行流程。
依赖：cheerio@1.0.0；Node.js >= 18.17。变量：aliyunWeb_data。
任务包含签到、现行文章/回答互动、可选视频、积分领取及库存查询。
原脚本使用说明及声明见 UPSTREAM-ALIYUN.md；本适配不改变原作者声明。
*/
// SPDX-License-Identifier: GPL-3.0
// 有效许可证：GPL-3.0；保留原作者及适配者声明。
// 配置：登录 developer.aliyun.com，在网络面板 /developer/api/my/user/getUser
// 请求头复制完整 Cookie 到 aliyunWeb_data；每个非空行一个账号，保留所有等号。
// 兼容原 JSON 数组或每行 {"token": "完整 Cookie"}，不要用 @ 或 & 分隔账号。
// aliyunWeb_interact=true 显式开启随机公开互动；aliyunWeb_video/stock 默认 false。
// aliyunWeb_time 默认 12，时区默认 Asia/Shanghai；原场景参数仅提示手动完成。
// ALIYUN_WEB_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY 未设置时按上架状态，off 可关闭。
// 正式运行安装公共依赖 cheerio@1.0.0；业务实现均包含于本文件，无需私有仓库。
// 原声明引用文件未随输入提供；本文保留上游全部可见作者、来源和许可说明。
"use strict";
// qinglong-notification-policy: begin
(() => {
  if (process.env.QINGLONG_NOTIFY !== undefined) return;
  const selection = process.env.QINGLONG_NOTIFY_SCRIPTS;
  let enabled = false;
  if (selection !== undefined) {
    const selectors = selection.trim().toLowerCase().split(/[,;\s]+/).filter(Boolean);
    const identities = ["5c73bf2cb192e0d0", "scripts/aliyun_web.js", "aliyun_web.js", "aliyun_web"];
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
const crypto = require('node:crypto');
process.env.TZ = process.env.aliyunWeb_timezone || 'Asia/Shanghai';
const dry = process.env.ALIYUN_WEB_DRY_RUN === '1';
let secretValues = [], reports = [];
function redact(value) {
  let text = String(value);
  for (const secret of secretValues) if (secret) text = text.split(secret).join('[已隐藏]');
  return text.replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, '[手机号已隐藏]').replace(/[\r\n]+/g, ' ');
}
function log(text) { console.log(`[${new Date().toTimeString().slice(0,8)}] ${redact(text)}`); }
const $ = { log, wait: ms => new Promise(resolve => setTimeout(resolve, Math.max(1, ms))) };
const runtime = { apiSuccess, decodeJsonResponse };
function parseTaskCatalog(html, cheerio) {
  if (typeof html !== "string" || !html.trim())
    throw new Error("任务中心未返回 HTML");
  const script = cheerio.load(html)("#script-page-config").text();
  const start = script.indexOf("{"),
    end = script.lastIndexOf("}");
  let config;
  try {
    config = JSON.parse(script.slice(start, end + 1));
  } catch (_) {
    throw new Error("任务中心配置格式已变化，停止互动任务");
  }
  const module = config.modules?.find(
    (item) =>
      item.fullName === "@ali/hmod-ace-developer-new-score-get-integral",
  );
  const rows = module?.props?.getScore;
  if (!Array.isArray(rows))
    throw new Error("任务中心缺少现行任务列表，停止互动任务");
  return rows
    .filter((row) => row && typeof row.title === "string")
    .map((row) => ({
      title: row.title,
      chance: String(row.chance || ""),
      href: String(row.href || ""),
    }));
}
function apiSuccess(response) {
  if (response?.success === false) return false;
  return response?.success === true || String(response?.code) === "200";
}
function decodeJsonResponse(response) {
  if (response && typeof response === "object") return response;
  if (typeof response !== "string") return null;
  const start = response.indexOf("{"),
    end = response.lastIndexOf("}");
  if (start < 0 || end < start) return null;
  try {
    return JSON.parse(response.slice(start, end + 1));
  } catch (_) {
    return null;
  }
}
function taskPeriod(chance, now = Date.now()) {
  const date = new Date(now + 8 * 3600000);
  if (chance.includes("每周"))
    date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return date.toISOString().slice(0, 10);
}
function createTaskState(file) {
  const fs = require("node:fs"),
    path = require("node:path"),
    crypto = require("node:crypto");
  file ||= path.join(
    process.env.QL_DATA_DIR ||
      (fs.existsSync("/ql/data") ? "/ql/data" : path.resolve(__dirname, "..")),
    "config",
    "aliyun-community-state.json",
  );
  let data = {};
  try {
    const text = fs.readFileSync(file, "utf8");
    if (text.length <= 1024 * 1024) {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed))
        data = parsed;
    }
  } catch (_) {}
  const key = (account, title) =>
    crypto
      .createHash("sha256")
      .update(String(account.userId || account.token))
      .update("\0")
      .update(title)
      .digest("hex");
  return {
    has(account, task) {
      return data[key(account, task.title)] === taskPeriod(task.chance);
    },
    mark(account, task) {
      data[key(account, task.title)] = taskPeriod(task.chance);
      fs.mkdirSync(path.dirname(file), { recursive: true });
      const temp = `${file}.${process.pid}.tmp`;
      fs.writeFileSync(temp, JSON.stringify(data), { mode: 0o600 });
      fs.renameSync(temp, file);
    },
  };
}

// 官网积分明细记录的是领取时间，不等同于任务完成时间。
const rewardContents = {
  点赞任一文章: ["完成每周点赞文章", "完成点赞任一文章"],
  收藏任一文章: ["完成每周收藏文章", "完成收藏任一文章"],
  分享任一文章: ["完成每周分享文章", "完成分享社区文章"],
  点赞任一回答: ["完成每周点赞回答", "完成点赞任一回答"],
};
async function readReceivedRewards(fetchPage, now = Date.now()) {
  const week = taskPeriod("每周", now);
  const months = [
    ...new Set([week.slice(0, 7), taskPeriod("每日", now).slice(0, 7)]),
  ];
  const rows = [];
  for (const month of months) {
    let loaded = 0;
    for (let pageNum = 1; pageNum <= 100; pageNum++) {
      const response = await fetchPage({
        appCode: "developer",
        source: "receive",
        month,
        pageNum,
        pageSize: 10,
      });
      const data = response?.data;
      if (
        !apiSuccess(response) ||
        !Array.isArray(data?.list) ||
        !Number.isSafeInteger(data.total) ||
        data.total < 0 ||
        data.list.some(
          (row) =>
            !row ||
            typeof row.content !== "string" ||
            !Number.isFinite(Number(row.gmtCreate)) ||
            Number(row.gmtCreate) <= 0 ||
            !Number.isFinite(Number(row.score)) ||
            ![1, 2].includes(Number(row.operateType)),
        )
      )
        throw new Error("积分领取明细查询失败或格式变化，跳过本次互动任务");
      rows.push(...data.list);
      loaded += data.list.length;
      if (loaded >= data.total) break;
      if (!data.list.length || pageNum === 100)
        throw new Error("积分领取明细未完整读取，跳过本次互动任务");
    }
  }
  return rows;
}
function hasReceivedReward(rows, task, now = Date.now()) {
  const names = rewardContents[task.title];
  if (!names) return false; // 未核对的名称不能模糊匹配。
  return rows.some(
    (row) =>
      Number(row.operateType) === 1 &&
      Number(row.score) > 0 &&
      names.includes(row.content.trim()) &&
      Number(row.gmtCreate) <= now &&
      taskPeriod(task.chance, Number(row.gmtCreate)) ===
        taskPeriod(task.chance, now),
  );
}

function getCallback(time = Date.now()) { return `jsonp_${time}_${Math.ceil(Math.random()*100000)}`; }
function getSessionId(cookie, id) {
  const field = cookie.split(';').find(x => x.trim().startsWith('cna='));
  const cna = field ? field.slice(field.indexOf('=')+1) : '';
  return crypto.createHash('md5').update(cna + id + Date.now()).digest('hex');
}
async function request(options) {
  if (dry) throw new Error('预演禁止网络请求');
  const url = new URL(options.url);
  if (url.protocol !== 'https:' || !['developer.aliyun.com','ucc.aliyun.com'].includes(url.hostname)) throw new Error('拒绝非阿里云任务地址');
  for (const [k,v] of Object.entries(options.params || {})) {
    if (v !== undefined && v !== null) url.searchParams.set(k, typeof v === 'object' ? JSON.stringify(v) : String(v));
  }
  const method = (options.type || 'get').toUpperCase();
  const headers = {...options.headers};
  let body;
  if (options.body !== undefined && method !== 'GET') {
    body = new URLSearchParams(Object.entries(options.body).map(([k,v]) => [k, typeof v === 'object' ? JSON.stringify(v) : String(v)])).toString();
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
  }
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(url, {method, headers, body, signal:controller.signal, redirect:'manual'});
    if (!response.ok) throw new Error(`接口 HTTP ${response.status}`);
    let size = 0, chunks = [];
    for await (const chunk of response.body) {
      size += chunk.length;
      if (size > 5*1024*1024) { controller.abort(); throw new Error('接口响应过大'); }
      chunks.push(Buffer.from(chunk));
    }
    const text = Buffer.concat(chunks).toString('utf8');
    try { return JSON.parse(text); } catch (_) { return text; }
  } catch(error) {
    if (/^接口 HTTP \d+$|^接口响应过大$/.test(error.message)) throw error;
    throw new Error('接口网络请求失败或超时');
  } finally { clearTimeout(timer); }
}
class UserInfo {
  constructor(data, index) {
    this.index = index; this.token = data.token; this.userId = data.userId; this.ckStatus = true;
    this.headers = {Cookie: data.token, 'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36', Referer:'https://developer.aliyun.com/'};
    this.fetch = async options => {
      if (options.url.startsWith('/')) options = {...options, url:'https://developer.aliyun.com/developer/api'+options.url};
      try {
        const response = await request({...options, headers:options.headers || this.headers});
        const decoded = decodeJsonResponse(response);
        if (decoded && (decoded.code !== undefined || decoded.success !== undefined) && !apiSuccess(decoded)) throw new Error('接口业务状态未成功');
        log(`账号 ${this.index} 请求完成：${new URL(options.url).pathname}`);
        return response;
      } catch (error) { this.ckStatus = false; throw error; }
    };
  }
  async api(url, params, body) {
    const response = await this.fetch({url, params, body, type:body === undefined ? 'get':'post'});
    if (!apiSuccess(response)) throw new Error('接口未返回明确业务成功状态');
    return response.data;
  }
  async getUccCsrfToken() {
    const response = decodeJsonResponse(await this.fetch({url:'https://ucc.aliyun.com/uccPagingComponent/getUser', params:{uccCsrfToken:'', callback:getCallback()}}));
    if (!apiSuccess(response) || typeof response.data?.uccCsrfToken !== 'string' || !response.data.uccCsrfToken) throw new Error('未取得有效互动校验令牌');
    secretValues.push(response.data.uccCsrfToken);
    return response.data.uccCsrfToken;
  }
  async ["getArticles"]() {
    const html = await this.fetch({
      url: "https://developer.aliyun.com/indexFeed/",
      type: "get",
    });
    if (typeof html !== "string") return null;
    const dom = $.Cheerio.load(html);
    const ids = [
      ...new Set(
        dom("a[href]")
          .toArray()
          .map(
            (link) =>
              dom(link)
                .attr("href")
                ?.match(
                  /^(?:https:\/\/developer\.aliyun\.com)?\/article\/(\d+)(?:[?#]|$)/,
                )?.[1],
          )
          .filter(Boolean),
      ),
    ];
    if (!ids.length) {
      $.log("⛔️ 当前文章列表未取得可用文章");
      return null;
    }
    return ids[Math.floor(Math.random() * ids.length)];
  }
  async ["getAsks"]() {
    const _0x2a639b = null,
      _0x2d934c = {
        idPFR: function (_0x781559, _0x189325) {
          return _0x781559(_0x189325);
        },
        wifgB: function (_0x5f4b30, _0x82768c) {
          return _0x5f4b30(_0x82768c);
        },
        vCapZ: ".askProduct-item-title-text h3",
        UkTaX: function (_0x5f4213, _0x5e64d9) {
          return _0x5f4213(_0x5e64d9);
        },
        twSUE: ".askProduct-item-info-answer",
        LXbVE: function (_0x5fea47, _0x5d8160) {
          return _0x5fea47 + _0x5d8160;
        },
        qDgPA: function (_0x40cb4e, _0x5a357c) {
          return _0x40cb4e * _0x5a357c;
        },
        BhNap: "get",
        MDVED: ".askProduct-list",
        WYycT: ".askProduct-item",
      };
    try {
      const _0x21f883 = _0x2d934c["LXbVE"](
          Math["floor"](_0x2d934c["qDgPA"](Math["random"](), 0x1f)),
          0x1,
        ),
        _0x35d953 = {
          url: "https://developer.aliyun.com/ask/?pageNum=" + _0x21f883,
          type: _0x2d934c["BhNap"],
        };
      let _0x21a196 = await this["fetch"](_0x35d953);
      if (typeof _0x21a196 !== "string" || !_0x21a196.trim()) {
        $["log"]("⛔️ 获取问答列表失败：未取得 HTML，跳过本次问答");
        return null;
      }
      const _0x3f3437 = $["Cheerio"]["load"](_0x21a196),
        _0x5341fa = _0x2d934c["wifgB"](_0x3f3437, _0x2d934c["MDVED"]),
        _0x1772a5 = _0x5341fa["find"](_0x2d934c["WYycT"])
          ["map"]((_0x3bf0f7, _0x580a7c) => {
            const _0x22342a = null;
            return {
              id:
                _0x2d934c["idPFR"](_0x3f3437, _0x580a7c)["attr"]("data-id") ||
                "",
              name:
                _0x2d934c["wifgB"](_0x3f3437, _0x580a7c)
                  ["find"](_0x2d934c["vCapZ"])
                  ["text"]() || "",
              answer:
                parseInt(
                  _0x2d934c["UkTaX"](_0x3f3437, _0x580a7c)
                    ["find"](_0x2d934c["twSUE"])
                    ["text"](),
                ) || "",
            };
          })
          ["filter"]((_0xfd811d, _0x3ac6dc) => _0x3ac6dc["answer"] > 0x0)
          ["get"](),
        _0x27367d =
          _0x1772a5[Math["floor"](Math["random"]() * _0x1772a5["length"])];
      if (_0x27367d?.["id"] && _0x27367d?.["name"]) {
        const { id: _0x14c0c6, name: _0x34c830 } = _0x27367d;
        return (
          $["log"]("✅ 随机获取问答id: " + _0x14c0c6 + ", 标题: " + _0x34c830),
          _0x27367d
        );
      }
      return null;
    } catch (_0x2c7844) {
      ((this["ckStatus"] = ![]),
        $["log"]("⛔️ 获取问答列表失败! " + _0x2c7844));
    }
  }
  async ["getAskDetail"](_0x3c853b) {
    const _0x133191 = null,
      _0x1108c9 = {
        WFMNv: function (_0x20483a, _0x54875b) {
          return _0x20483a(_0x54875b);
        },
        JWibK: "data-id",
        iXboJ: function (_0x4f3ff8, _0x14d57e) {
          return _0x4f3ff8(_0x14d57e);
        },
        YWzNW: ".answer-list",
        NUXGX: ".answer-item",
        pOoay: function (_0x58639d, _0x3e11d8) {
          return _0x58639d * _0x3e11d8;
        },
      };
    try {
      const _0x4d9fd4 = {
        url: "https://developer.aliyun.com/ask/" + _0x3c853b["id"],
        type: "get",
      };
      let _0x4a8d4d = await this["fetch"](_0x4d9fd4);
      if (typeof _0x4a8d4d !== "string") return null;
      const _0x197405 = $["Cheerio"]["load"](_0x4a8d4d),
        _0x95c7bb = _0x1108c9["iXboJ"](_0x197405, _0x1108c9["YWzNW"]),
        _0x496a64 = _0x95c7bb["find"](_0x1108c9["NUXGX"])
          ["map"]((_0x290648, _0x492ae4) => {
            const _0x2ecb22 = null;
            return {
              id:
                _0x1108c9["WFMNv"](_0x197405, _0x492ae4)["attr"](
                  _0x1108c9["JWibK"],
                ) || "",
            };
          })
          ["get"](),
        _0x777a55 =
          _0x496a64[
            Math["floor"](
              _0x1108c9["pOoay"](Math["random"](), _0x496a64.length),
            )
          ];
      if (_0x777a55) {
        const { id: _0x2a3950 } = _0x777a55;
        return (
          $["log"]("✅\x20随机获取问题问答id:\x20" + _0x2a3950),
          _0x2a3950
        );
      }
      return null;
    } catch (_0x49424e) {
      ((this["ckStatus"] = ![]),
        $["log"]("⛔️ 随机获取问题问答失败! " + _0x49424e));
    }
  }
  async ["likeOrNotLike"](_0x5af432, _0x2ed0dc, _0x3541c6) {
    const _0x10ed7c = null,
      _0x1e0e13 = {
        Pffrn: "https://ucc.aliyun.com/uccPagingComponent/likeOrNotLike",
        nGUEP: "get",
        sTsDx: "yq-article",
        pvSTb: function (_0x571a67) {
          return _0x571a67();
        },
        cLyIc: function (_0x593c61, _0x15d89b) {
          return _0x593c61 + _0x15d89b;
        },
        pIRta: function (_0x3c3e5f, _0x202dfc) {
          return _0x3c3e5f === _0x202dfc;
        },
        keamp: "aliyun-public-like",
        cdZJP: "aliyun-public-favorite",
        gXewl: "aliyun-public-share",
      };
    try {
      const _0x4af17a = {
        url: _0x1e0e13["Pffrn"],
        type: _0x1e0e13["nGUEP"],
        params: {
          bizCategory: _0x1e0e13["sTsDx"],
          actionCode: _0x2ed0dc,
          objectId: _0x5af432,
          status: _0x3541c6,
          uccCsrfToken: await this["getUccCsrfToken"](),
          callback: _0x1e0e13["pvSTb"](getCallback),
        },
      };
      const response = runtime.decodeJsonResponse(
        await this["fetch"](_0x4af17a),
      );
      if (!runtime.apiSuccess(response)) {
        $.log("⛔️ 文章互动接口未返回成功");
        return false;
      }
      let _0x33d148 = _0x1e0e13["cLyIc"](
        "文章",
        _0x1e0e13["pIRta"](_0x3541c6, 0x1) ? "取消" : "",
      );
      if (_0x1e0e13["pIRta"](_0x2ed0dc, _0x1e0e13["keamp"]))
        _0x33d148 += "点赞";
      else {
        if (_0x2ed0dc === _0x1e0e13["cdZJP"]) _0x33d148 += "收藏";
        else _0x2ed0dc === _0x1e0e13["gXewl"] && (_0x33d148 += "分享");
      }
      $["log"]("✅\x20" + _0x33d148 + "请求成功: " + _0x5af432);
      return true;
    } catch (_0x56df3a) {
      ((this["ckStatus"] = ![]), $["log"]("⛔️ 文章互动失败!\x20" + _0x56df3a));
    }
  }
  async ["getCsrfToken"](_0x3f985f, _0x20ff73) {
    const _0x17a058 = null,
      _0x488cb4 = {
        vfSSx: "get",
        ITMUJ:
          "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 AliApp(Aliyun/6.7.1) WindVane/8.7.2 1170x2532 WK",
      };
    try {
      const _0x4b9efd = {
          url: "https://developer.aliyun.com/csrfToken",
          type: _0x488cb4["vfSSx"],
          headers: {
            Cookie: this["token"],
            "User-Agent": _0x488cb4["ITMUJ"],
            Referer:
              "https://developer.aliyun.com/" + _0x20ff73 + "/" + _0x3f985f,
          },
        },
        _0x4948f3 = await this["fetch"](_0x4b9efd);
      return _0x4948f3?.["token"];
    } catch (_0x12b621) {
      ((this["ckStatus"] = ![]),
        $["log"]("⛔️\x20获取\x20csrf\x20失败!\x20" + _0x12b621));
    }
  }
  async ["voteAnswer"](_0x41d7ed, _0x29baf3, _0x2dc533, _0x750f28) {
    const _0xe6da6e = null,
      _0x4e5cc0 = {
        jZCPX: "post",
        VggLf:
          "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 AliApp(Aliyun/6.7.1) WindVane/8.7.2 1170x2532 WK",
      };
    try {
      const _0x1383be = {
        url: "https://developer.aliyun.com/developer/api/my/ask/voteAnswer",
        type: _0x4e5cc0["jZCPX"],
        dataType: "form",
        headers: {
          Cookie: this["token"],
          "User-Agent": _0x4e5cc0["VggLf"],
          Referer: "https://developer.aliyun.com/ask/" + _0x41d7ed,
        },
        params: { p_csrf: _0x2dc533 },
        body: { id: _0x29baf3, votes: _0x750f28 },
      };
      const response = runtime.decodeJsonResponse(await this.fetch(_0x1383be));
      const success = runtime.apiSuccess(response);
      $.log(
        `${success ? "✅" : "⛔️"} 回答点赞接口：${success ? "请求成功" : "未返回成功"}`,
      );
      return success;
    } catch (_0x194e66) {
      ((this["ckStatus"] = ![]), $["log"]("⛔️ 回答点赞失败! " + _0x194e66));
    }
  }
  async ["getVideoDetail"](_0x5f3fc1) {
    const _0x1d0cb7 = null,
      _0x2cfaae = {
        fUbAN: function (_0x219fdf, _0x3bbc06) {
          return _0x219fdf(_0x3bbc06);
        },
        oWklG: "get",
        XAIhx: "1.1.23",
        LVwix:
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        AfHQa: function (_0xbd63fe, _0xd265df) {
          return _0xbd63fe(_0xd265df);
        },
      };
    try {
      const _0x38c61b = Date["now"](),
        _0x451b2e = _0x2cfaae["fUbAN"](getCallback, _0x38c61b),
        _0x58f751 = {
          url: "https://ucc.aliyun.com/api/ucc/live/open/detail",
          type: _0x2cfaae["oWklG"],
          params: {
            _: _0x38c61b,
            callback: _0x451b2e,
            version: _0x2cfaae["XAIhx"],
            id: _0x5f3fc1,
          },
          headers: {
            "User-Agent": _0x2cfaae["LVwix"],
            Cookie: this["token"],
            Referer: "https://developer.aliyun.com/live/" + _0x5f3fc1,
          },
        },
        _0x46c6d5 = await this["fetch"](_0x58f751),
        _0x4202fd = runtime.decodeJsonResponse(_0x46c6d5),
        _0x1ef603 = _0x4202fd?.["data"]?.["live"]?.["name"],
        _0x3e391f = _0x4202fd?.["data"]?.["live"]?.["duration"];
      if (
        !runtime.apiSuccess(_0x4202fd) ||
        !_0x1ef603 ||
        !Number.isFinite(Number(_0x3e391f))
      )
        return null;
      return (
        $.log(
          "✅ 获取视频信息成功: " +
            _0x1ef603 +
            ", 时长: " +
            _0x3e391f +
            "\x20秒",
        ),
        { videoName: _0x1ef603, videoTime: _0x3e391f }
      );
    } catch (_0x17a3fe) {
      return (
        (this["ckStatus"] = ![]),
        $["log"]("⛔️ 获取视频信息失败! " + _0x17a3fe),
        null
      );
    }
  }
  async ["getVideoView"](_0x1e1e24, _0x174a43) {
    const _0xd702cc = null,
      _0x56e011 = { TSRsa: "get" };
    try {
      const _0x17cdc8 = Date["now"](),
        _0x475c76 = getCallback(_0x17cdc8),
        _0x83fe0e = {
          url: "https://ucc.aliyun.com/api/ucc/live/open/view",
          type: _0x56e011["TSRsa"],
          params: {
            _: _0x17cdc8,
            callback: _0x475c76,
            version: "1.1.23",
            id: _0x1e1e24,
            sessionId: _0x174a43,
          },
          headers: {
            "User-Agent":
              "Mozilla/5.0\x20(Macintosh;\x20Intel\x20Mac\x20OS\x20X\x2010_15_7)\x20AppleWebKit/537.36\x20(KHTML,\x20like\x20Gecko)\x20Chrome/125.0.0.0\x20Safari/537.36",
            Cookie: this["token"],
            Referer: "https://developer.aliyun.com/live/" + _0x1e1e24,
          },
        };
      return runtime.apiSuccess(
        runtime.decodeJsonResponse(await this.fetch(_0x83fe0e)),
      );
    } catch (_0xf47ac) {
      ((this["ckStatus"] = ![]), $["log"]("⛔️ 获取视频视图失败! " + _0xf47ac));
    }
  }
  async ["play"](_0x19cac2, _0x4aa617, _0x3f5f00) {
    const _0x4e11d7 = null,
      _0x194151 = {
        XxmSN: function (_0x4e8ce5, _0x1b60c6) {
          return _0x4e8ce5(_0x1b60c6);
        },
        shDrW: "get",
        hLfat: "1.1.23",
      };
    try {
      const _0x2ba447 = Date["now"](),
        _0x23605f = _0x194151["XxmSN"](getCallback, _0x2ba447),
        _0xb88426 = {
          url: "https://ucc.aliyun.com/api/ucc/live/open/play",
          type: _0x194151["shDrW"],
          params: {
            _: _0x2ba447,
            callback: _0x23605f,
            version: _0x194151["hLfat"],
            id: _0x4aa617,
            sessionId: _0x3f5f00,
          },
          headers: {
            "User-Agent":
              "Mozilla/5.0\x20(Macintosh;\x20Intel\x20Mac\x20OS\x20X\x2010_15_7)\x20AppleWebKit/537.36\x20(KHTML,\x20like\x20Gecko)\x20Chrome/125.0.0.0\x20Safari/537.36",
            Cookie: this["token"],
            Referer: "https://developer.aliyun.com/live/" + _0x4aa617,
          },
        };
      const success = runtime.apiSuccess(
        runtime.decodeJsonResponse(await this.fetch(_0xb88426)),
      );
      $.log(
        `${success ? "✅" : "⛔️"} 视频播放接口：${success ? "请求成功" : "未返回成功"}`,
      );
      return success;
    } catch (_0x3d7d6d) {
      ((this["ckStatus"] = ![]), $["log"]("⛔️ 播放视频失败! " + _0x3d7d6d));
    }
  }
  async ["danmu"](_0x4538f3, _0x3917d4) {
    const _0x244625 = null,
      _0x53b51d = {
        kuTmH: function (_0x18b28a, _0xf2a664) {
          return _0x18b28a(_0xf2a664);
        },
        dnaov: "1.1.23",
        qHiNf:
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        eFisk: function (_0xcb18e6, _0x1ea933) {
          return _0xcb18e6(_0x1ea933);
        },
      };
    try {
      const _0x21aff2 = Date["now"](),
        _0xfaf2fc = _0x53b51d["kuTmH"](getCallback, _0x21aff2),
        _0x32e09c = {
          url: "https://ucc.aliyun.com/api/ucc/live/open/danmu",
          type: "get",
          params: {
            _: _0x21aff2,
            callback: _0xfaf2fc,
            version: _0x53b51d["dnaov"],
            id: _0x4538f3,
            seek: _0x3917d4,
          },
          headers: {
            "User-Agent": _0x53b51d["qHiNf"],
            Cookie: this["token"],
            Referer: "https://developer.aliyun.com/live/" + _0x4538f3,
          },
        },
        _0x436c79 = await this["fetch"](_0x32e09c);
      const success = runtime.apiSuccess(runtime.decodeJsonResponse(_0x436c79));
      if (!success) $.log("⛔️ 视频弹幕接口未返回成功，停止视频流程");
      return success;
    } catch (_0x1899b3) {
      ((this["ckStatus"] = ![]), $["log"]("⛔️ 获取弹幕失败! " + _0x1899b3));
    }
  }
  async ["online"](_0xf9cc65, _0x4b080b, quiet = false) {
    const _0x5e4348 = null,
      _0x3dddd = {
        VdfAt: function (_0x1f8f9b, _0x591380) {
          return _0x1f8f9b(_0x591380);
        },
        KLykr: "get",
        rqQAT: "1.1.23",
      };
    try {
      const _0x418c19 = Date["now"](),
        _0x369e23 = _0x3dddd["VdfAt"](getCallback, _0x418c19),
        _0x54fd5b = {
          url: "https://ucc.aliyun.com/api/ucc/live/open/online",
          type: _0x3dddd["KLykr"],
          params: {
            _: _0x418c19,
            callback: _0x369e23,
            version: _0x3dddd["rqQAT"],
            id: _0xf9cc65,
            sessionId: _0x4b080b,
          },
          headers: {
            "User-Agent":
              "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            Cookie: this["token"],
            Referer: "https://developer.aliyun.com/live/" + _0xf9cc65,
          },
        };
      const success = runtime.apiSuccess(
        runtime.decodeJsonResponse(await this.fetch(_0x54fd5b)),
      );
      if (!quiet || !success)
        $.log(
          `${success ? "✅" : "⛔️"} 在线心跳接口：${success ? "请求成功" : "未返回成功"}`,
        );
      return success;
    } catch (_0x1be8cf) {
      ((this["ckStatus"] = ![]), $["log"]("⛔️ 在线心跳确认! " + _0x1be8cf));
    }
  }
  async ["playVideo"]() {
    const html = await this.fetch({
      url: "https://developer.aliyun.com/live/",
      type: "get",
    });
    if (typeof html !== "string") return false;
    const dom = $.Cheerio.load(html);
    const ids = [
      ...new Set(
        dom("a[href]")
          .toArray()
          .map(
            (link) =>
              dom(link)
                .attr("href")
                ?.match(
                  /^(?:https:\/\/developer\.aliyun\.com)?\/live\/(\d+)(?:[?#]|$)/,
                )?.[1],
          )
          .filter(Boolean),
      ),
    ];
    // 只从当前列表选择可用视频，最多检查三个；不再使用固定的旧视频 ID。
    for (const id of ids.slice(0, 3)) {
      const detail = await this.getVideoDetail(id);
      const seconds = Number(detail?.videoTime);
      if (
        !detail?.videoName ||
        !Number.isFinite(seconds) ||
        seconds <= 0 ||
        seconds > 1800
      )
        continue;
      const session = getSessionId(this.token, id);
      if (
        !(await this.getVideoView(id, session)) ||
        !(await this.play(detail.videoName, id, session))
      )
        return false;
      const started = Date.now(),
        deadline = started + seconds * 1000;
      let nextReport = 60;
      $.log(
        `视频等待开始：约 ${Math.ceil(seconds / 60)} 分钟，每分钟报告一次进度`,
      );
      // 同时限制真实经过时间与轮数，接口耗时计入等待，失败立即结束。
      for (
        let tick = 0;
        tick < Math.ceil(seconds / 3) && Date.now() < deadline;
        tick++
      ) {
        await $.wait(Math.min(3000, deadline - Date.now()));
        const elapsed = Math.min(
          Math.floor((Date.now() - started) / 1000),
          Math.ceil(seconds),
        );
        if (Date.now() >= deadline) break;
        if (!(await this.danmu(id, elapsed))) return false;
        if (elapsed >= nextReport) {
          if (!(await this.online(id, session, true))) return false;
          $.log(
            `视频进度：${Math.min(100, Math.floor((elapsed / seconds) * 100))}%（${elapsed}/${Math.ceil(seconds)} 秒）`,
          );
          nextReport = (Math.floor(elapsed / 60) + 1) * 60;
        }
      }
      if (Date.now() < deadline) {
        $.log("⛔️ 视频计时异常，停止本次视频流程");
        return false;
      }
      if (!(await this.online(id, session, true))) return false;
      $.log(`✅ 视频播放请求结束：${detail.videoName}；奖励以积分记录为准`);
      return true;
    }
    $.log("⏭️ 当前视频列表未找到 30 分钟以内的有效视频，请手动观看");
    return false;
  }
}
function accounts(value) {
  const text = String(value || '').trim();
  if (!text) throw new Error('请配置必填变量 aliyunWeb_data');
  let rows;
  if (text.startsWith('[')) {
    try { rows = JSON.parse(text); } catch (_) { throw new Error('aliyunWeb_data JSON 数组格式错误'); }
    if (!Array.isArray(rows)) throw new Error('aliyunWeb_data 应为账号数组');
  } else rows = text.split(/\r?\n/).filter(x => x.trim()).map(line => {
    if (line.trim().startsWith('{')) { try { return JSON.parse(line); } catch (_) { return {invalid:true}; } }
    return {token:line.trim()};
  });
  return rows.map(row => {
    if (typeof row === 'string') row = {token:row};
    if (!row || typeof row.token !== 'string' || !row.token.trim() || /[\r\n\x00]/.test(row.token)) return {invalid:true};
    const token = row.token.trim();
    secretValues.push(token, ...token.split(';').map(x => x.slice(x.indexOf('=')+1).trim()).filter(x => x.length >= 4));
    return {...row, token};
  });
}
function settings() {
  const hour = process.env.aliyunWeb_time || '12';
  if (!/^\d+$/.test(hour) || +hour < 1 || +hour > 23) throw new Error('aliyunWeb_time 必须是 1 至 23 的整数');
  for (const name of ['aliyunWeb_scene','aliyunWeb_video','aliyunWeb_stock','aliyunWeb_dedupe','aliyunWeb_reward_check','aliyunWeb_interact']) {
    if (process.env[name] && !['true','false'].includes(process.env[name])) throw new Error(`${name} 必须为 true 或 false`);
  }
  if (process.env.ALIYUN_WEB_DRY_RUN && !['0','1'].includes(process.env.ALIYUN_WEB_DRY_RUN)) throw new Error('ALIYUN_WEB_DRY_RUN 必须为 0 或 1');
  try { new Intl.DateTimeFormat('zh-CN',{timeZone:process.env.aliyunWeb_timezone || 'Asia/Shanghai'}); } catch (_) { throw new Error('aliyunWeb_timezone 时区无效'); }
  return +hour;
}
const skip = reason => ({skip:reason});
async function stage(stats, title, action) {
  const start = Date.now(), num = ++stats.total;
  log(`账号 ${stats.index} 阶段 ${num}：${title}`);
  try {
    const result = await action();
    if (result?.skip) { stats.skipped++; log(`⏭️ ${title}：${result.skip}`); }
    else { stats.success++; log(`✅ ${title}：${dry ? '预演通过，未发出请求' : '已核验接口业务成功'}`); }
    return result;
  } catch (_) { stats.failed++; log(`❌ ${title}：接口失败、超时或响应契约不符；不输出原始响应`); return undefined; }
  finally { log(`阶段 ${num} 耗时 ${Date.now()-start} 毫秒`); }
}
function numberData(value) {
  if (!['number','string'].includes(typeof value) || value === '' || !Number.isFinite(Number(value)) || Number(value) < 0) throw new Error('积分数据格式变化');
  return Number(value);
}
async function accountRun(data, index, hour, state) {
  const started = Date.now(), stats = {index,total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
  const morning = new Date().getHours() < hour;
  try {
    if (data.invalid) { await stage(stats,'账号参数检查',async () => {throw new Error();}); return; }
    if (dry) {
      for (const name of ['账号参数检查','身份与积分查询','社区签到及奖励资格核对','现行任务目录及周期去重','文章与回答互动','视频观看','待领取积分及领取','库存查询']) {
        await stage(stats,name,async () => undefined);
      }
      log(`账号 ${index} DRY_RUN_OK：仅检查执行计划，不验证真实账号或业务`);
      return;
    }
    const account = new UserInfo(data,index);
    const user = await stage(stats,'身份与积分查询',async () => {
      const info = await account.api('/my/user/getUser');
      if (!info || typeof info !== 'object') throw new Error();
      for (const key of ['nickname','userName','username','displayName','userId','uid']) {
        const value = info[key];
        if (typeof value === 'string' || typeof value === 'number') log(`账号 ${index} 官方身份 ${key}：${value}`);
      }
      account.userId = info.userId || info.uid || account.userId;
      log(`当前积分：${numberData(await account.api('/my/score/getUserScore',{appCode:'developer'}))}`);
      return info;
    });
    if (!user) return;
    await stage(stats,'社区签到及签到奖励',async () => {
      const detail = await account.api('/sign/getUserSpaceSignInDetail',{excode:''});
      const groupId = detail?.taskGroupId;
      if (!groupId) return skip('官网未提供签到任务组');
      if (morning) {
        const group = await account.api('/task/getTaskGroup',{groupId});
        if (!Array.isArray(group?.taskList)) throw new Error();
        let selected;
        for (const task of group.taskList) {
          const now = Date.now();
          if (!task || (task.gmtEnableStart != null && now < Number(task.gmtEnableStart)) || (task.gmtEnableEnd != null && now > Number(task.gmtEnableEnd))) continue;
          let rule;
          try {rule = typeof task.finishRule === 'string' ? JSON.parse(task.finishRule.replace(/&quot;/g,'"')) : task.finishRule;} catch (_) {continue;}
          const a = rule?.actions?.[0];
          if (a?.actionCode && a.objectId != null) {selected={actionCode:a.actionCode,activityCode:a.activityCode || a.actionCode,objectId:a.objectId};break;}
        }
        if (selected) {await account.api('/task/actionLog',undefined,selected);log('社区签到请求已核验');}
        else log('⏭️ 官网没有可执行的签到动作');
      } else log('⏭️ 当前为下午积分领取时段');
      const qualified = await account.api('/sign/assessSignInBonusQualification',{taskGroupId:groupId});
      if (typeof qualified !== 'boolean') throw new Error();
      if (qualified) {numberData(await account.api('/sign/receiveSignInBonus',undefined,{taskGroupId:groupId}));log('签到奖励已领取');}
      else log('⏭️ 暂无可领取签到奖励');
    });
    if (morning) {
      let catalog, rewards = [];
      catalog = await stage(stats,'读取现行任务与奖励记录',async () => {
        const rows = parseTaskCatalog(await account.fetch({url:'https://developer.aliyun.com/mission/daily'}), $.Cheerio);
        if (process.env.aliyunWeb_reward_check !== 'false' && rows.length) rewards = await readReceivedRewards(params => account.fetch({url:'/my/score/listScoreLogByPage',params}));
        log(`官网现行任务 ${rows.length} 项`);
        return rows;
      });
      if (catalog) {
        for (const [title,action] of [['点赞任一文章','aliyun-public-like'],['收藏任一文章','aliyun-public-favorite'],['分享任一文章','aliyun-public-share'],['点赞任一回答','answer'],['观看视频','video']]) {
          await stage(stats,title,async () => {
            const task = catalog.find(x => x.title === title);
            if (!task) return skip('现行任务列表没有此任务');
            if (hasReceivedReward(rewards,task)) {stats.alreadyComplete++;return skip('官网已有本周期奖励领取记录');}
            if (process.env.aliyunWeb_dedupe !== 'false' && state.has(account,task)) return skip('本周期已核验成功请求；奖励以官网记录为准');
            if (action === 'video' ? process.env.aliyunWeb_video !== 'true' : process.env.aliyunWeb_interact !== 'true') return skip('未显式开启此互动开关');
            let ok;
            if (action === 'video') ok = await account.playVideo();
            else if (action === 'answer') {
              const ask = await account.getAsks(), answer = ask && await account.getAskDetail(ask), csrf = answer && await account.getCsrfToken(ask.id,'ask');
              if (csrf) secretValues.push(csrf);
              ok = csrf && await account.voteAnswer(ask.id,answer,csrf,1);
            } else {
              const article = await account.getArticles();
              ok = article && await account.likeOrNotLike(article,action,0);
            }
            if (!ok) throw new Error();
            state.mark(account,task);
            log('任务接口已接受；积分奖励以领取记录为准');
          });
        }
        const manual = catalog.filter(x => !['点赞任一文章','收藏任一文章','分享任一文章','点赞任一回答','观看视频'].includes(x.title));
        if (manual.length) log(`需手动完成：${manual.map(x => x.title).join('、')}`);
      }
    } else await stage(stats,'领取全部待领取积分',async () => {
      const before = numberData(await account.api('/score/pending/getUserTotalPendingScore',{appCode:'developer'}));
      const amount = numberData(await account.api('/score/pending/receiveAllPendingScore',{appCode:'developer'}));
      log(`领取前待领取 ${before}；本次接口确认领取 ${amount}`);
    });
    if (process.env.aliyunWeb_scene === 'true') log('⏭️ 场景实验已退出积分任务，不自动创建、关闭或部署云资源');
    await stage(stats,'库存查询',async () => {
      if (process.env.aliyunWeb_stock !== 'true') return skip('库存查询未开启');
      const items = await account.api('/lm/getGroupItems',{pageNum:1,pageSize:50});
      if (!Array.isArray(items?.list)) throw new Error();
      for (const item of items.list) log(`库存：${item.itemTitle}；${item.points} 分；${item.statusStr}`);
    });
    await stage(stats,'最终积分查询',async () => {
      log(`当前积分：${numberData(await account.api('/my/score/getUserScore',{appCode:'developer'}))}；待领取：${numberData(await account.api('/score/pending/getUserTotalPendingScore',{appCode:'developer'}))}`);
    });
    if (!account.ckStatus && stats.failed === 0) stats.failed++;
  } finally {
    stats.durationMs=Date.now()-started; stats.status=stats.failed ? 'failure' : dry ? 'dry-run':'success'; reports.push(stats);
    log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${stats.durationMs} 毫秒`);
  }
}
async function notify(body) {
  if (['0','false','no','off'].includes((process.env.QINGLONG_NOTIFY || '1').toLowerCase()) || process.env.aliyunWeb_notify === 'off') return 'disabled';
  if (dry) {log('通知预演：已生成脱敏汇总；断网模式不加载通知模块');return 'dry-run';}
  const paths = [process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js',path.join(__dirname,'sendNotify.js')].filter(Boolean);
  const helper = paths.find(p => fs.existsSync(p));
  if (!helper) {log('⚠️ 未找到 sendNotify.js，保留业务退出码');return 'unavailable';}
  // 通知在有超时的独立进程中执行，渠道故障不影响业务退出码。
  const {spawn} = require('node:child_process');
  return new Promise(resolve => {
    const child = spawn(process.execPath,['-e',"const p=JSON.parse(process.argv[1]);Promise.resolve(require(p.path).sendNotify(p.title,p.body)).then(()=>process.exit(0)).catch(()=>process.exit(1));",JSON.stringify({path:helper,title:'阿里云社区',body:redact(body)})],{stdio:'ignore',env:process.env});
    const timer=setTimeout(()=>{child.kill('SIGKILL');},15000);
    child.on('error',()=>{clearTimeout(timer);resolve('failure');});
    child.on('close',code=>{clearTimeout(timer);resolve(code===0?'sent':'failure');});
  });
}
async function run() {
  const started=Date.now();let count=0, configError=false;
  log('========== 阿里云社区 ==========' );
  log(`开始时间：${new Date().toISOString()}；模式：${dry?'断网预演':'正式执行'}`);
  try {
    const rows=accounts(process.env.aliyunWeb_data);count=rows.length;
    log(`账号数量：${count}`);
    if (!count) throw new Error('aliyunWeb_data 没有非空账号');
    const hour=settings();
    if (!dry) {try {$.Cheerio=require('cheerio');} catch (_) {throw new Error('请通过青龙依赖管理安装 cheerio@1.0.0');}}
    const state=dry ? null : createTaskState(path.join(process.env.QL_DATA_DIR || __dirname,'config','aliyun-community-state.json'));
    for (let i=0;i<rows.length;i++) await accountRun(rows[i],i+1,hour,state);
  } catch (error) {configError=true;log(`❌ 配置错误：${error.message}`);}
  const success=reports.filter(x=>!x.failed).length, failed=reports.filter(x=>x.failed).length;
  const status=configError?'configuration-error':failed?(success?'partial-failure':'failure'):dry?'dry-run':'success';
  const exitCode=configError || failed ? 1:0;
  const body=`状态：${status}；账号总数 ${count}，成功 ${success}，失败 ${failed}；配置错误 ${configError?'是':'否'}。`;
  let notification;
  try {notification=await notify(body);} catch (_) {notification='failure';}
  log('--------------------------------');log(body);
  const tasks=reports.reduce((a,x)=>{for (const k of ['total','success','alreadyComplete','skipped','failed']) a[k]+=x[k];return a;},{total:0,success:0,alreadyComplete:0,skipped:0,failed:0});
  log(`子任务统计：总数 ${tasks.total}；成功 ${tasks.success}；已完成 ${tasks.alreadyComplete}；跳过 ${tasks.skipped}；失败 ${tasks.failed}`);
  log(`完成时间：${new Date().toISOString()}；总耗时 ${Date.now()-started} 毫秒；通知状态 ${notification}；最终状态 ${status}`);
  if (!exitCode) log(dry?'DRY_RUN_OK':'TASK_SUCCESS');
  console.log('TASK_SUMMARY='+JSON.stringify({status,mode:dry?'dry-run':'live',accounts:{total:count,success,failed},configError,tasks,results:reports,notification,durationMs:Date.now()-started,exitCode}));
  process.exitCode=exitCode;
}
module.exports={run,UserInfo,request,accounts};
if (require.main===module) run().catch(()=>{console.error('不可恢复的任务执行错误');process.exitCode=1;});
