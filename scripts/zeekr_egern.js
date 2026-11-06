// name: 极氪每日签到与奖励领取
// cron: 14 0 * * *
/**
 * name: 极氪每日签到与奖励领取
 * cron: 1 0 * * *
 * SPDX-License-Identifier: Apache-2.0
 * 来源 m20104600/zeekr-checkin，保留原核心实现与注释。
 * 上游 dist/zeekr.egern.js，参考 dist/zeekr.qinglong.js 和 dist/zeekr.js。
 * 许可 https://www.apache.org/licenses/LICENSE-2.0
 * 修改说明：独立 Node.js 执行、多账号换行、安全开关、断网预演、失败闭合、通知与统计。
 * 获取凭据：在本人极氪 App 或官网登录后，抓取发往 api-gw-toc.zeekrlife.com
 * 的 Authorization 请求头；可同时保存 device_id。请勿公开抓包或凭据。
 * ZEEKR_TOKEN 每个非空行填一个 Bearer JWT，或单行 JSON
 * {"authorization":"本人凭据","device_id":"同账号抓取值"}。只按换行分账号。
 * 兼容 TOKEN、ZEEKR_VAL、zeekr_val 及 ZEEKR_TOKEN_n / ZEEKR_VAL_n。
 * 编号变量从 ZEEKR_TOKEN_1 或 ZEEKR_VAL_1 开始，逐号增加。
 * 默认 all；sign 只签到做任务，claim 只领取，可在 00:10 配置 claim 补领。
 * 默认关闭步数上报与点赞。STEPS 明确指定实际步数或范围才会上报，LIKE=1 才点赞。
 * 参数支持 ZEEKR_ 前缀及原无前缀别名，大小写不敏感，详见配套契约。
 * ZEEKR_DRY_RUN=1 完全断网，仅检查配置与动作计划，通知采用本地预演。
 * QINGLONG_NOTIFY 控制通知；auto 仅发送列入 QINGLONG_NOTIFY_SCRIPTS 的脚本。
 * 参考构建入口的六场次可手动配置同一文件，保留各自 all/claim 与场次标签。
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
    const identities = ["a5b6bae676d9ef43", "scripts/zeekr_egern.js", "zeekr_egern.js", "zeekr_egern"];
    enabled = selectors.some((selector) => {
      const pattern = '^' + selector.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$';
      return identities.some((identity) => new RegExp(pattern).test(identity));
    });
  }
  process.env.QINGLONG_NOTIFY = enabled ? '1' : '0';
})();
// qinglong-notification-policy: end
var ZEEKR_PORT_VERSION = "3.3.4";
/* 签名密钥由 build.py 从本地 checkin.mjs 抽取后注入（避免密钥出现在源码/终端里被安全屏蔽器打码） */
var ZEEKR_SECRET = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCz09z6e9WOcNq+nUMX8Vq1Xe2EmJxuR3XbturefioF)E(Fl";
var ZEEKR_BASE = "https://api-gw-toc.zeekrlife.com";
var ZEEKR_API = {
  signIn: "/zeekrlife-mp-val/toc/v1/zgreen/center",
  taskMsg: "/zeekrlife-mp-mkt/open/v1/taskProgress/taskMsg",
  walkData: "/zeekrlife-mp-val/v1/walkData/initDayWalkData",
  articleDetail: "/zeekrlife-bbs-theme/v1/invitation/pub/detail",
  squareList: "/zeekrlife-bbs-theme/v1/invitation/pub/list",
  fabulous: "/zeekrlife-bbs-theme/v1/clicks/fabulous",
  uncollected: "/zeekrlife-mp-val/v1/carEnergy/getUncollectedBallsPageNew",
  claimDebris: "/zeekrlife-mp-mkt/toc/v1/apply/batchApply",
  claimSevenDayLottery: "/zeekrlife-mp-mkt/toc/v1/applyV2/apply",
  claimWalk: "/zeekrlife-mp-val/v1/carEnergy/collectedAllEnergy",
  claimIntegral: "/zeekrlife-mp-val/v1/carEnergy/collectIntegralZeekrBalls",
  festival: "/zeekrlife-mp-sic/v1/feign/signincalendar/festival",
  taskGet: "/zeekrlife-mp-sic/v1/signinzgreen/toc/taskGet",
  behaviorTrack: "/zeekrlife-search-api/search/open/api/new/behaviorTrack",
  commentList: "/zeekrlife-bbs-theme/v1/comment/pub/list",
  recommend: "/zeekrlife-bbs-theme/v1/invitation/pub/recommend",
};
var ZEEKR_VAL_DEBRIS = "DEBRIS";
var ZEEKR_VAL_WALK = "CARBON_VALUE";
var ZEEKR_VAL_INTEGRAL = "ZEEKR_VALUE";
var ZEEKR_SCENE_SEVEN_DAY_LOTTERY = "SIGN_CONTINUOUS_7_LOTTERY";
var ZEEKR_RECORD_SEVEN_DAY_LOTTERY = "zgreen_7day_activity";
var ZEEKR_TASK_ARTICLE = "阅读文章";
var ZEEKR_TASK_WALK = "步行3000步";
var ZEEKR_TASK_PRAISE = "每周点赞帖子";

/* ---------------- 基础工具（纯 JS，不依赖任何客户端 API） ---------------- */

var ZEEKR__B64C =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

function zeekrUtf8Bytes(str) {
  var out = [];
  for (var i = 0; i < str.length; i++) {
    var c = str.charCodeAt(i);
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
    else if (c >= 0xd800 && c <= 0xdbff) {
      var c2 = str.charCodeAt(++i);
      var cp = 0x10000 + ((c - 0xd800) << 10) + (c2 - 0xdc00);
      out.push(
        0xf0 | (cp >> 18),
        0x80 | ((cp >> 12) & 63),
        0x80 | ((cp >> 6) & 63),
        0x80 | (cp & 63)
      );
    } else out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
  }
  return out;
}

function zeekrUtf8Decode(bytes) {
  var s = "";
  for (var i = 0; i < bytes.length; ) {
    var c = bytes[i++];
    if (c < 0x80) s += String.fromCharCode(c);
    else if (c < 0xe0)
      s += String.fromCharCode(((c & 31) << 6) | (bytes[i++] & 63));
    else if (c < 0xf0)
      s += String.fromCharCode(
        ((c & 15) << 12) | ((bytes[i++] & 63) << 6) | (bytes[i++] & 63)
      );
    else {
      var cp =
        ((c & 7) << 18) |
        ((bytes[i++] & 63) << 12) |
        ((bytes[i++] & 63) << 6) |
        (bytes[i++] & 63);
      cp -= 0x10000;
      s += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 1023));
    }
  }
  return s;
}

/** base64 编码（标准字母表 + 补 =，与 Node Buffer.toString("base64") 一致） */
function zeekrB64Encode(str) {
  var b = zeekrUtf8Bytes(str);
  var out = "";
  for (var i = 0; i < b.length; i += 3) {
    var n = b[i] << 16;
    var rem = b.length - i - 1;
    if (rem >= 1) n |= b[i + 1] << 8;
    if (rem >= 2) n |= b[i + 2];
    out += ZEEKR__B64C.charAt((n >> 18) & 63);
    out += ZEEKR__B64C.charAt((n >> 12) & 63);
    out += rem >= 1 ? ZEEKR__B64C.charAt((n >> 6) & 63) : "=";
    out += rem >= 2 ? ZEEKR__B64C.charAt(n & 63) : "=";
  }
  return out;
}

/** base64 解码为 UTF-8 字符串，兼容 JWT 的 base64url 与缺失补位 */
function zeekrB64Decode(str) {
  str = String(str)
    .replace(/-/g, "+")
    .replace(/_/g, "/")
    .replace(/[^A-Za-z0-9+/=]/g, "");
  var out = [];
  var buf = 0;
  var bits = 0;
  for (var i = 0; i < str.length; i++) {
    if (str.charAt(i) === "=") break;
    var idx = ZEEKR__B64C.indexOf(str.charAt(i));
    if (idx < 0) continue;
    buf = (buf << 6) | idx;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out.push((buf >> bits) & 255);
    }
  }
  return zeekrUtf8Decode(out);
}

/** SHA1（hex），与 Node crypto.createHash("sha1") 等价 —— 各客户端没有 crypto */
function zeekrSha1Hex(str) {
  var bytes = zeekrUtf8Bytes(str);
  var bitLen = bytes.length * 8;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  bytes.push(0, 0, 0, 0);
  bytes.push(
    (bitLen >>> 24) & 255,
    (bitLen >>> 16) & 255,
    (bitLen >>> 8) & 255,
    bitLen & 255
  );

  var h0 = 0x67452301,
    h1 = 0xefcdab89,
    h2 = 0x98badcfe,
    h3 = 0x10325476,
    h4 = 0xc3d2e1f0;
  var w = new Array(80);

  for (var i = 0; i < bytes.length; i += 64) {
    for (var j = 0; j < 16; j++) {
      w[j] =
        (bytes[i + 4 * j] << 24) |
        (bytes[i + 4 * j + 1] << 16) |
        (bytes[i + 4 * j + 2] << 8) |
        bytes[i + 4 * j + 3];
    }
    for (var j2 = 16; j2 < 80; j2++) {
      var n = w[j2 - 3] ^ w[j2 - 8] ^ w[j2 - 14] ^ w[j2 - 16];
      w[j2] = ((n << 1) | (n >>> 31)) >>> 0;
    }
    var a = h0,
      b = h1,
      c = h2,
      d = h3,
      e = h4;
    for (var k = 0; k < 80; k++) {
      var f, kk;
      if (k < 20) {
        f = (b & c) | (~b & d);
        kk = 0x5a827999;
      } else if (k < 40) {
        f = b ^ c ^ d;
        kk = 0x6ed9eba1;
      } else if (k < 60) {
        f = (b & c) | (b & d) | (c & d);
        kk = 0x8f1bbcdc;
      } else {
        f = b ^ c ^ d;
        kk = 0xca62c1d6;
      }
      var t =
        ((((a << 5) | (a >>> 27)) >>> 0) + (f >>> 0) + e + kk + (w[k] >>> 0)) >>>
        0;
      e = d;
      d = c;
      c = ((b << 30) | (b >>> 2)) >>> 0;
      b = a;
      a = t;
    }
    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
  }
  var hex = function (x) {
    var s = x.toString(16);
    while (s.length < 8) s = "0" + s;
    return s;
  };
  return hex(h0) + hex(h1) + hex(h2) + hex(h3) + hex(h4);
}

function zeekrSleep(ms) {
  return new Promise(function (r) {
    setTimeout(r, ms);
  });
}
function zeekrResolveStepCounts(value, rng) {
  var text = String(value == null ? "" : value).trim();
  var pick = rng || zeekrRand;
  if (/^(off|0|no|false)$/i.test(text)) return 0;
  var range = text.match(/^(\d+)\s*-\s*(\d+)$/);
  if (range) {
    var min = Number(range[1]), max = Number(range[2]);
    if (min > 0 && max >= min && max <= 9007199254740991) return pick(min, max);
  } else if (/^\d+$/.test(text)) {
    var fixed = Number(text);
    if (fixed > 0 && fixed <= 9007199254740991) return fixed;
  }
  return pick(15000, 25000);
}
function zeekrRand(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}
// Opt-in time settings: strict integer/range, finite before sampling, bounded.
function zeekrResolveSeconds(value, cap) {
  var text = String(value == null ? "" : value).trim();
  var range = text.match(/^(\d+)\s*-\s*(\d+)$/), min, max;
  if (range) { min = Number(range[1]); max = Number(range[2]); }
  else if (/^\d+$/.test(text)) { min = max = Number(text); }
  else return 0;
  if (min < 0 || max < min || max > 9007199254740991) return 0;
  return zeekrRand(Math.min(min, cap), Math.min(max, cap));
}
function zeekrDailyRng(accountId) {
  var day = zeekrCSTDate(Date.now());
  return function (min, max) {
    var hash = parseInt(zeekrSha1Hex("zeekr-steps:" + day + ":" + (accountId || "")).slice(0, 12), 16);
    return min + (hash % (max - min + 1));
  };
}
function zeekrRandomString(len) {
  var chars = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz1234567890";
  var s = "";
  for (var i = 0; i < len; i++)
    s += chars.charAt(Math.floor(Math.random() * chars.length));
  return s;
}
function zeekrPad2(n) {
  return n < 10 ? "0" + n : String(n);
}
/** 北京时间字符串，不依赖 Intl / 时区设置 */
function zeekrNowCST() {
  var d = new Date(Date.now() + 8 * 3600 * 1000);
  return (
    d.getUTCFullYear() +
    "/" +
    (d.getUTCMonth() + 1) +
    "/" +
    d.getUTCDate() +
    " " +
    zeekrPad2(d.getUTCHours()) +
    ":" +
    zeekrPad2(d.getUTCMinutes()) +
    ":" +
    zeekrPad2(d.getUTCSeconds())
  );
}
function zeekrCSTDate(ms) {
  var d = new Date(ms + 8 * 3600 * 1000);
  return (
    d.getUTCFullYear() + "/" + (d.getUTCMonth() + 1) + "/" + d.getUTCDate()
  );
}

/* ---------------- 参数读取 ---------------- */

/**
 * 清洗 Token：用户到处复制粘贴，常见带单/双引号、首尾空格、零宽字符
 * （零宽空格 U+200B、BOM U+FEFF、双向标记 U+200E/F 等），
 * 青龙环境变量里还经常写 ZEEKR_TOKEN="Bearer ..."，这里统一收拾干净。
 * 顺带：只粘了裸 JWT（没带 Bearer 前缀）也自动补上。
 */
function zeekrCleanToken(t) {
  var s = String(t == null ? "" : t);
  s = s.replace(/[\u200b-\u200f\ufeff\u2060\u00a0\t\r\n]/g, " ");
  s = s.replace(/^[\s"']+|[\s"']+$/g, "");
  var i = s.search(/Bearer\s/i);
  if (i > 0) s = s.slice(i);
  s = s.replace(/\s+/g, " ").trim();
  if (s && !/^Bearer\s/i.test(s) && /^eyJ[\w-]+\.[\w-]+\./.test(s))
    s = "Bearer " + s;
  // 极氪的 Token 一定是 JWT（脚本要用里面的 accountId / deviceId）。
  // 这里做一次校验，好处是：插件/配置里没替换掉的占位符（如 ${TOKEN}、<粘贴你的Token>）
  // 会被当成"没配 Token"，走自动抓取的兜底，而不是发一个假 Token 出去变成"登录已失效"。
  if (s && !/^Bearer\s+[\w-]+\.[\w-]+\.[\w-]*$/.test(s)) return "";
  return s;
}

/**
 * 从「存量字符串」里取出 Token。兼容常见极氪脚本（如 wf021325/qx）的存储格式：
 *   {"authorization":"Bearer eyJ..."}（键名 zeekr_val / ZEEKR_VAL）
 *   Bearer eyJ...
 *   authorization=Bearer%20eyJ...
 *   裸的 eyJ...
 * 抓取规则写进客户端的值就是这个格式，所以两边可以互通。
 */
function zeekrTokenFromStore(raw) {
  if (!raw) return "";
  var s = String(raw).trim();
  if (s.charAt(0) === "{") {
    try {
      var o = JSON.parse(s) || {};
      return zeekrCleanToken(
        o.authorization ||
          o.Authorization ||
          o.token ||
          o.TOKEN ||
          o.ZEEKR_TOKEN ||
          ""
      );
    } catch (e) {
      return "";
    }
  }
  var m = s.match(/authorization=([^&\n]+)/i);
  if (m) {
    s = m[1];
    try {
      s = decodeURIComponent(s);
    } catch (e2) {}
  }
  return zeekrCleanToken(s);
}

/**
 * 支持的参数（大小写不敏感，前缀 ZEEKR_ 可有可无）：
 *   TOKEN      必填，Bearer eyJ...
 *   MODE       all（默认，签到+步数+任务+领取）/ sign（只签到做任务）/ claim（只领取）
 *   TAG        场次标签，只影响通知标题，例如 凌晨场 / 早间场 / 晚间场
 *   STEPS      上报步数，数字；off 表示跳过上报
 *   POLL       1 = 领取阶段做长时间复查轮询（需要客户端超时 ≥ ZEEKR_MAX，默认 0 只查一轮）
 *   WAITS      复查间隔（秒，逗号分隔，默认 45,60,75）
 *   SETTLE     距最后一次成功领取至少观察多少秒（默认 180）
 *   MAX        领取阶段上限（秒，默认 600）
 *   APPVER     App 版本号，跳过 iTunes 查询，例如 4.9.33
 *   LIKE       1 = 不管本周是否已完成都点一次赞（排查用）
 *   NATIVE     1 + APP_SECRET + 非零 JWT 设备 ID 才为文章/点赞启用原生头；默认仍 H5
 *   NATIVE_REQUESTS  1 = 另启用原生阅读页行为/评论/推荐（仍需 NATIVE）
 *   PAGE_CONTEXT    1 = 可选 festival/taskGet 预请求（网络错误软失败；认证错误立即退出）
 *   UA / PHONE_MODEL / IOS_VERSION  可选覆盖 H5 UA / 原生机型 / 系统版本
 *   READWAIT / DELAY  阅读停留 / 启动延迟秒数或范围，默认 0，每项最多 120 秒
 *   DAILYSTEPS 1 = 按北京时间日期+账号固定范围步数；默认每次运行重新随机
 *   附加请求和等待共享预算：QX 5秒（不发附加请求）、其它手机15秒、Node/青龙120秒。
 *   NOTIFY     0 = 不发通知
 *   CAPSHOW    1(默认) = 抓到 Token 时在通知里显示完整 Token（方便复制到青龙）；
 *              0 = 只显示账号/有效期（Token 仍会存进客户端持久化存储）
 *              —— **仅 QX / Loon / Stash 版实现**，Egern 版恒显示完整 Token
 *   VERBOSE    1 = 打印明细
 */
function zeekrNormKey(k) {
  return String(k)
    .replace(/^ZEEKR[-_]/i, "")
    .replace(/[-_]/g, "")
    .toUpperCase();
}

function zeekrDeviceIdFromStore(raw) {
  if (!raw) return "";
  try {
    var o = typeof raw === "string" && raw.charAt(0) === "{" ? JSON.parse(raw) : null;
    return o && o.device_id ? String(o.device_id) : "";
  } catch (e) {
    return "";
  }
}

/** Select usable explicit credentials first; placeholders must not shadow storage.
 * Return metadata only: neither credential nor device ID belongs in diagnostics.
 */
function zeekrSelectStoredConfig(env, storedRaw) {
  var explicit = "";
  var hasDevice = false;
  for (var k in env) {
    if (!Object.prototype.hasOwnProperty.call(env, k)) continue;
    var name = zeekrNormKey(k);
    if (name === "DEVICEID" && env[k] != null && String(env[k]).trim() !== "") hasDevice = true;
    if (name !== "TOKEN") continue;
    var cleaned = String(env[k] == null ? "" : env[k]).split(/\r?\n/).map(zeekrCleanToken).filter(function (value) { return !!value; }).join("\n");
    if (cleaned) explicit = cleaned;
    delete env[k];
  }
  var selected = explicit || zeekrTokenFromStore(storedRaw);
  if (selected) env.ZEEKR_TOKEN = selected;
  // A captured device belongs to the captured credential, never to an explicit one.
  if (!explicit && selected && !hasDevice) env.ZEEKR_DEVICE_ID = zeekrDeviceIdFromStore(storedRaw);
  return explicit ? "env" : selected ? "storage" : "missing";
}

function zeekrLoadConfig(RT) {
  var raw = RT.env || {};
  var v = {};
  for (var k in raw) {
    if (!Object.prototype.hasOwnProperty.call(raw, k)) continue;
    var val = raw[k];
    if (val === null || val === undefined) continue;
    v[zeekrNormKey(k)] = val;
  }
  var str = function (name, def) {
    var x = v[name];
    if (x === undefined || x === null || x === "") return def;
    return String(x).trim();
  };
  var cfg = {
    token: str("TOKEN", ""),
    deviceId: str("DEVICEID", ""),
    appSecret: str("APPSECRET", ""),
    native: str("NATIVE", "0") === "1",
    nativeRequests: str("NATIVEREQUESTS", "0") === "1",
    pageContext: str("PAGECONTEXT", "0") === "1",
    phoneModel: str("PHONEMODEL", "iPhone17,1"),
    iosVersion: str("IOSVERSION", "26.0"),
    ua: str("UA", ""),
    readWait: str("READWAIT", ""),
    delay: str("DELAY", ""),
    dailySteps: str("DAILYSTEPS", "0") === "1",
    mode: str("MODE", "all").toLowerCase(),
    tag: str("TAG", ""),
    stepsRaw: str("STEPS", "off"),
    poll: str("POLL", "0") === "1",
    waits: str("WAITS", "45,60,75"),
    settle: parseInt(str("SETTLE", "180"), 10) || 180,
    max: parseInt(str("MAX", "600"), 10) || 600,
    appver: str("APPVER", ""),
    forceLike: str("LIKE", "0") === "1",
    notify: str("NOTIFY", "1") !== "0",
    verbose: str("VERBOSE", "0") === "1",
  };
  var toks = [];
  if (cfg.token) {
    toks = String(cfg.token)
      .split(/\r?\n/)
      .map(function (t) {
        return zeekrCleanToken(t);
      })
      .filter(function (t) {
        return t && t.charAt(0) !== "#";
      });
  } else if (v["VAL"]) {
    // 兼容常见极氪脚本的 zeekr_val / ZEEKR_VAL（值是 {"authorization":"Bearer ..."}）
    var one = zeekrTokenFromStore(v["VAL"]);
    if (one) toks = [one];
    if (!cfg.deviceId) cfg.deviceId = zeekrDeviceIdFromStore(v["VAL"]);
  }
  cfg.tokens = toks.length ? toks : [];
  cfg.token = cfg.tokens[0] || "";
  if (cfg.mode !== "sign" && cfg.mode !== "claim") cfg.mode = "all";
  return cfg;
}

// Protect integer lexemes only (not JSON strings) before native JSON parsing.
function zeekrParseJsonExact(raw) {
  return JSON.parse(raw.replace(
    /"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
    function (value) { return /^-?\d{16,}$/.test(value) ? '"' + value + '"' : value; }
  ));
}

function zeekrParseToken(token) {
  var part = String(token).replace(/^Bearer\s+/i, "").split(".")[1] || "";
  var payload = {};
  try {
    payload = zeekrParseJsonExact(zeekrB64Decode(part));
  } catch (e) {
    payload = {};
  }
  var subRaw =
    typeof payload.sub === "string"
      ? payload.sub
      : JSON.stringify(payload.sub || {});
  var sub = {};
  try {
    sub = zeekrParseJsonExact(subRaw);
  } catch (e2) {
    sub = {};
  }
  var mAcc = subRaw.match(/"accountId"\s*:\s*"?(\d{10,})/);
  var accountId =
    (mAcc && mAcc[1]) ||
    String(
      (sub.accountInfoDTO && sub.accountInfoDTO.accountId) || ""
    );
  var mDev = subRaw.match(/"lastLoginDeviceId"\s*:\s*"([^"]+)"/);
  var deviceId =
    (mDev && mDev[1]) ||
    (sub.accountLoginInfoDTO && sub.accountLoginInfoDTO.lastLoginDeviceId) ||
    "";
  var exp = (payload.exp || 0) * 1000;
  var daysLeft = exp ? Math.floor((exp - Date.now()) / 86400000) : 999;
  var sourcePlatform = (sub.accountLoginInfoDTO && sub.accountLoginInfoDTO.platform) || "";
  return { accountId: accountId, deviceId: String(deviceId), sourcePlatform: sourcePlatform, exp: exp, daysLeft: daysLeft };
}

/* ---------------- 请求层 ---------------- */

function zeekrHeaders(token, appVersion, deviceId, sourcePlatform) {
  var timestamp = Date.now();
  var nonce = zeekrRandomString(15);
  return {
    "Content-Type": "application/json",
    Accept: "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    Authorization: token,
    x_ca_key: "H5-SIGN-SECRET-KEY",
    x_ca_nonce: nonce,
    x_ca_timestamp: String(timestamp),
    x_ca_sign: zeekrSha1Hex(
      [ZEEKR_SECRET, nonce, String(timestamp)].sort().join("")
    ),
    WorkspaceId: "prod",
    Version: "2",
    app_type: "h5",
    app_code: "toc_h5_green_zeekrapp",
    platform: sourcePlatform === "WEB_PC" ? "WEB_PC" : "",
    platform_h5: "IOS",
    risk_platform: "h5",
    riskTimeStamp: String(timestamp),
    riskVersion: "1",
    "device_id": deviceId || "",
    x_gray_code: "gray45",
    AppId: "ONEX97FB91F061405",
    "X-CORS-ONEX97FB91F061405-prod": "1",
    "Eagleeye-Sessionid": "",
    "Eagleeye-Traceid": "",
    Origin: "https://activity-h5.zeekrlife.com",
    Referer: "https://activity-h5.zeekrlife.com/",
    "User-Agent":
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) zeekr_iOS_v" +
      appVersion,
  };
}

// Keep the legacy four-argument H5 helper for Issue #6 consumers; endpoint
// selection belongs here, not in JWT parsing or runtime-specific wrappers.
function zeekrPathIn(list, path) {
  return list.indexOf(String(path).split("?")[0]) >= 0;
}
function zeekrH5Headers(ctx, path, method) {
  var h = zeekrHeaders(ctx.token, ctx.appVersion, ctx.deviceId, ctx.sourcePlatform);
  if (ctx.ua) h["User-Agent"] = ctx.ua;
  if (method === "GET") delete h["Content-Type"];
  if (!zeekrPathIn([ZEEKR_API.walkData, ZEEKR_API.uncollected], path)) delete h.x_gray_code;
  if (!zeekrPathIn([ZEEKR_API.claimDebris], path)) delete h.riskVersion;
  return h;
}
function zeekrNativeHeaders(ctx, method) {
  var timestamp = String(Date.now()), nonce = "";
  for (var i = 0; i < 8; i++) nonce += String(zeekrRand(0, 9));
  var h = {
    "User-Agent": "ZeekrLife/" + ctx.appVersion + " (iPhone; iOS " + ctx.iosVersion + "; Scale/3.00)" + ctx.nativeDeviceId,
    x_ca_sign: zeekrSha1Hex([ctx.appSecret, nonce, timestamp].sort().join("")),
    app_code: "toc_ios_zeekrapp", app_version: ctx.appVersion,
    device_id: ctx.nativeDeviceId, phone_version: ctx.iosVersion,
    x_ca_nonce: nonce, x_ca_key: "APP-SIGN-SECRET-KEY", Version: "2",
    x_ca_timestamp: timestamp, "request-original": "zeekr-app",
    WorkspaceId: "prod", riskVersion: "1", Authorization: ctx.token,
    "Accept-Language": "zh-Hans-CN;q=1", app_type: "IOS",
    phone_model: ctx.phoneModel, x_ca_secret: ctx.appSecret, Accept: "*/*",
  };
  if (method !== "GET") h["Content-Type"] = "application/json";
  return h;
}
function zeekrBuildHeaders(ctx, path, method) {
  if (ctx.nativeEnabled && zeekrPathIn([
    ZEEKR_API.articleDetail, ZEEKR_API.fabulous, ZEEKR_API.squareList,
    ZEEKR_API.behaviorTrack, ZEEKR_API.commentList, ZEEKR_API.recommend,
  ], path)) return zeekrNativeHeaders(ctx, method);
  return zeekrH5Headers(ctx, path, method);
}

// Optional page context/telemetry must never block the actual business action.
// Authentication exceptions deliberately escape to the main abort boundary.
async function zeekrOptionalRequest(ctx, path, method, body) {
  if (ctx.authDead) throw zeekrAuthError(ctx);
  // The existing QX adapter has no cancellation/deadline support. Exclude added
  // context HTTP there rather than promise a timeout it cannot actually enforce.
  if (ctx.RT.platform === "Quantumult X") return null;
  if (ctx.optionalRemainingMs <= 0) return null;
  var startedAt = Date.now();
  try {
    return await zeekrRequest(ctx, path, method, body, Math.min(5000, ctx.optionalRemainingMs));
  } catch (err) {
    if (err && err.zeekrAuth) throw err;
    ctx.vlog("可选页面请求失败，跳过");
    return null;
  } finally {
    ctx.optionalRemainingMs = Math.max(0, ctx.optionalRemainingMs - Math.max(0, Date.now() - startedAt));
  }
}
async function zeekrOptionalPause(ctx, value) {
  if (ctx.authDead) throw zeekrAuthError(ctx);
  var ms = Math.min(zeekrResolveSeconds(value, 120) * 1000, ctx.optionalRemainingMs);
  if (ms > 0) {
    ctx.optionalRemainingMs -= ms;
    await zeekrSleep(ms);
  }
}

// Authentication rejection is not necessarily expiration. Do not classify a
// temporary login-service outage merely because its message contains 登录.
function zeekrIsAuthDead(status, data) {
  if (Number(status) === 401 || Number(status) === 403) return true;
  if (!data || data.code === "000000") return false;
  if (String(data.code) === "000009") return true;
  return /认证失败|未授权|授权失败|登录(?:已)?(?:失效|过期)|未登录|请重新登录|请先登录|token\s*(?:失效|过期|无效|invalid|expired)/i.test(String(data.msg || data.message || ""));
}

function zeekrAuthError(ctx) {
  ctx.authDead = true;
  var err = new Error("认证失败，已停止本次后续请求；请检查或重新抓取 Token（不一定是过期）");
  err.zeekrAuth = true;
  return err;
}

async function zeekrRequest(ctx, path, method, body, timeoutMs) {
  if (ctx.authDead) throw zeekrAuthError(ctx);
  var res = await ctx.RT.http({
    method: method,
    url: ZEEKR_BASE + path,
    headers: zeekrBuildHeaders(ctx, path, method),
    body: method === "GET" ? null : JSON.stringify(body === undefined ? {} : body),
    timeoutMs: timeoutMs || 20000,
  });
  var text = res && res.body !== undefined && res.body !== null ? res.body : "";
  if (typeof text !== "string") {
    try {
      text = JSON.stringify(text);
    } catch (e) {
      text = String(text);
    }
  }
  var data;
  try {
    data = zeekrParseJsonExact(text);
  } catch (e2) {
    data = { code: "PARSE_ERROR", msg: "响应不是有效 JSON" };
  }
  if (zeekrIsAuthDead(res && res.status, data)) throw zeekrAuthError(ctx);
  // batchApply may report a successful outer envelope while an individual
  // command is rejected for authentication. Inspect before retry or any sleep.
  if (path === ZEEKR_API.claimDebris && data && Object.prototype.toString.call(data.data) === "[object Array]") {
    for (var authIndex = 0; authIndex < data.data.length; authIndex++) {
      if (zeekrIsAuthDead(200, data.data[authIndex])) throw zeekrAuthError(ctx);
    }
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("响应结构异常");
  if (data.code === "000000") {
    if (path === ZEEKR_API.taskMsg && !Array.isArray(data.data && data.data.taskReachMsgList)) throw new Error("任务列表响应结构异常");
    if (path === ZEEKR_API.uncollected && !Array.isArray(data.data && data.data.uncollectedVal)) throw new Error("奖励列表响应结构异常");
  }
  if (ctx.identity) ctx.identity(data.data);
  return data;
}

function zeekrGet(ctx, path) {
  return zeekrRequest(ctx, path, "GET", null);
}
function zeekrPost(ctx, path, body) {
  return zeekrRequest(ctx, path, "POST", body);
}

/** Encode the step field six times, matching the decoded phone request. */
function zeekrEncodeStepSecret(stepCounts, layers) {
  var out = stepCounts + "_salt";
  for (var i = 0; i < (layers || 6); i++) out = zeekrB64Encode(out);
  return out;
}

/* ---------------- 各业务动作 ---------------- */

async function zeekrSignIn(ctx) {
  if (ctx.pageContext) await zeekrOptionalRequest(ctx, ZEEKR_API.festival, "POST", {});
  var data = await zeekrPost(ctx, ZEEKR_API.signIn, {});
  if (data.code === "000000") {
    var info = (data.data && data.data.signInZgreenInfo) || [];
    var today = null,
      streak = null;
    for (var i = 0; i < info.length; i++) {
      var t = info[i] || {};
      if (t.taskName === "每日签到") today = t;
      if (t.taskName && String(t.taskName).indexOf("连续签到") === 0) streak = t;
    }
    ctx.out("✅ 签到成功" + (today && today.taskStatus ? "（今日已签到）" : ""));
    if (streak) ctx.out("🔥 " + streak.taskName);
    return true;
  }
  ctx.out("❌ 签到失败: " + (data.msg || JSON.stringify(data)));
  return false;
}

async function zeekrSyncWalk(ctx, steps, sourceType) {
  var base = {
    stepCounts: steps,
    stepCountsSecret: zeekrEncodeStepSecret(steps),
    sourceType: sourceType || 20,
  };
  var body = {};
  for (var k in base) body[k] = base[k];
  if (ctx.accountId) body.accountId = ctx.accountId;
  var data = await zeekrPost(ctx, ZEEKR_API.walkData, body);
  if (data.code !== "000000" && ctx.accountId) {
    ctx.out(
      "⚠️ 步数上报带 accountId 失败（" +
        data.code +
        " " +
        (data.msg || "") +
        "），改用不带 accountId 重试"
    );
    data = await zeekrPost(ctx, ZEEKR_API.walkData, base);
  }
  if (data.code === "000000") {
    ctx.out("🚶 步数上报成功: " + steps + " 步");
    return true;
  }
  ctx.out("❌ 步数上报失败: " + (data.msg || JSON.stringify(data)));
  return false;
}

async function zeekrGetTasks(ctx) {
  if (ctx.pageContext) await zeekrOptionalRequest(ctx, ZEEKR_API.taskGet, "GET");
  var data = await zeekrPost(ctx, ZEEKR_API.taskMsg, {
    activityRecord: "medal_compose_task_manage",
    optional: { fetchTaskTakeAndReachTimesInfo: true },
  });
  if (data.code !== "000000") {
    ctx.out("❌ 查询任务列表失败: " + (data.msg || JSON.stringify(data)));
    return [];
  }
  return (data.data && data.data.taskReachMsgList) || [];
}

async function zeekrReadArticle(ctx, tasks) {
  var task = null;
  for (var i = 0; i < tasks.length; i++)
    if (tasks[i].name === ZEEKR_TASK_ARTICLE) task = tasks[i];
  if (!task) return null;
  if (zeekrTaskDone(task)) {
    ctx.out("📖 阅读文章: 今日已完成，跳过");
    return null;
  }
  var url = (task.doc && task.doc.path) || "";
  var m = url.match(/acticleId=([^&]+)/);
  if (!m) {
    ctx.out("❌ 阅读文章: 任务里没拿到文章 ID");
    return null;
  }
  if (ctx.nativeRequests) await zeekrOptionalRequest(ctx, ZEEKR_API.behaviorTrack, "POST", {
    mobileType: "iOS", deviceId: ctx.nativeDeviceId, accountId: ctx.accountId,
    appVersion: ctx.appVersion, type: 1, businessId: m[1],
  });
  var data = await zeekrGet(ctx, ZEEKR_API.articleDetail + "?id=" + m[1]);
  if (data.code === "000000") {
    ctx.out(
      "📖 阅读文章成功: " + ((data.data && data.data.title) || m[1])
    );
    if (ctx.nativeRequests) {
      await zeekrOptionalRequest(ctx, ZEEKR_API.commentList + "?moduleId=" + m[1] + "&moduleType=1&pageNo=1&pageSize=15", "GET");
      await zeekrOptionalRequest(ctx, ZEEKR_API.recommend, "POST", { id: m[1] });
    }
    await zeekrOptionalPause(ctx, ctx.readWait);
    return data.data || { id: m[1] };
  }
  ctx.out("❌ 阅读文章失败: " + (data.msg || JSON.stringify(data)));
  return null;
}

async function zeekrLikeSquarePost(ctx) {
  var target = null;
  var pages = [1, 2, 3];
  for (var p = 0; p < pages.length; p++) {
    var list = await zeekrGet(
      ctx,
      ZEEKR_API.squareList +
        "?pageNo=" +
        pages[p] +
        "&pageSize=20&sort=0"
    );
    if (!list || list.code !== "000000" || !Array.isArray(list.data && list.data.list)) throw new Error("广场列表查询失败或结构异常");
    var items = list.data.list;
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      if (it && it.isFabulous === 0 && it.id && it.accountId) {
        target = it;
        break;
      }
    }
    if (target || !items.length) break;
  }
  if (!target) {
    ctx.out("⚠️ 广场列表里没有可点赞的帖子（前三页都点过了）");
    return null;
  }
  return zeekrLikePost(ctx, target);
}

async function zeekrLikePost(ctx, target) {
  var data = await zeekrPost(ctx, ZEEKR_API.fabulous, {
    moduleId: String(target.id),
    accountId: ctx.accountId,
    fabulousState: 1,
    moduleType: 1,
    toAccountId: String(target.accountId),
    invitationType: 2,
  });
  if (data.code === "000000") {
    var label = target.title
      ? "《" + String(target.title).slice(0, 18) + "》"
      : "帖子 " + String(target.id).slice(-6);
    ctx.out("👍 社区点赞成功: " + label);
    return true;
  }
  ctx.out("❌ 社区点赞失败: " + (data.msg || JSON.stringify(data)));
  return null;
}

function zeekrTaskDone(t) {
  if (!t) return true;
  var dto = t.taskTakeDTO || {};
  return (dto.currentComplete || 0) >= (dto.maxCompleteLimit || 1);
}
function zeekrTaskLine(t) {
  return (zeekrTaskDone(t) ? "✅" : "⏳") + " " + t.name;
}

async function zeekrDoTasks(ctx, forceLike) {
  var tasks = await zeekrGetTasks(ctx);
  if (!tasks.length) {
    ctx.out("⚠️ 未取到任务列表（跳过做任务）");
    return { tasks: tasks };
  }
  var article = await zeekrReadArticle(ctx, tasks);
  var weekly = null;
  for (var i = 0; i < tasks.length; i++)
    if (tasks[i].name === ZEEKR_TASK_PRAISE) weekly = tasks[i];
  if (!forceLike && zeekrTaskDone(weekly)) {
    ctx.out("👍 每周点赞帖子: 本周已完成，跳过");
  } else {
    if (article && article.isFabulous === 0 && article.id && article.accountId) await zeekrLikePost(ctx, article);
    else await zeekrLikeSquarePost(ctx);
  }
  return { tasks: tasks };
}

async function zeekrGetUncollected(ctx) {
  var data = await zeekrPost(ctx, ZEEKR_API.uncollected, {
    accountId: ctx.accountId,
  });
  if (data.code !== "000000") {
    ctx.out("❌ 查询可领取奖品失败: " + (data.msg || JSON.stringify(data)));
    throw new Error("查询可领取奖品失败，无法确认是否还有奖励");
  }
  var items = (data.data && data.data.uncollectedVal) || [];
  var debrisList = [],
    walkList = [],
    integralList = [],
    lotteryList = [];
  for (var i = 0; i < items.length; i++) {
    var it = items[i] || {};
    if (it.sceneCode === ZEEKR_SCENE_SEVEN_DAY_LOTTERY) lotteryList.push(it);
    else if (it.valDefineCode === ZEEKR_VAL_DEBRIS) debrisList.push(it);
    else if (it.valDefineCode === ZEEKR_VAL_WALK) walkList.push(it);
    else if (it.valDefineCode === ZEEKR_VAL_INTEGRAL) integralList.push(it);
  }
  var summary =
    debrisList.length +
    " 个碎片, " +
    lotteryList.length +
    " 个七日抽奖球, " +
    walkList.length +
    " 个能量球, " +
    integralList.length +
    " 个极值";
  if (debrisList.length || lotteryList.length || walkList.length || integralList.length)
    ctx.out("📦 可领取: " + summary);
  else ctx.vlog("📦 可领取: " + summary);
  return { debrisList: debrisList, walkList: walkList, integralList: integralList, lotteryList: lotteryList };
}

/* 2026-09-21 加：把服务端返回的失败原因取出来（字段名不固定，都试一遍）——
   旧版把原因整个丢掉，导致「通知说领完了、App 里还在」查不出原因。 */
function zeekrFailReason(rec, fallback) {
  if (!rec || typeof rec !== "object") return (fallback || "") + "";
  var keys = ["msg", "message", "errorMsg", "remark"];
  for (var i = 0; i < keys.length; i++) {
    if (rec[keys[i]]) return String(rec[keys[i]]);
  }
  if (typeof rec.code === "string" && rec.code) return rec.code;
  return (fallback || JSON.stringify(rec).slice(0, 160)) + "";
}

function zeekrCountKeys(obj) {
  var n = 0;
  for (var k in obj) if (Object.prototype.hasOwnProperty.call(obj, k)) n++;
  return n;
}

function zeekrFailedList(obj) {
  var out = [];
  for (var k in obj) if (Object.prototype.hasOwnProperty.call(obj, k)) out.push(obj[k]);
  return out;
}

function zeekrMergeFailed(target, list) {
  for (var i = 0; i < (list || []).length; i++) target[list[i].id] = list[i];
}

function zeekrDebrisName(r) {
  var snap = r && r.invoice && r.invoice.materialSnapshot;
  var name = (snap && snap.name) || "碎片";
  var fragment = (snap && snap.medalTemplateSnapshot && snap.medalTemplateSnapshot.name) || "";
  return fragment ? name + "(" + fragment + ")" : name;
}

/**
 * 批量领取碎片（与 App 一致：一次 batchApply 提交全部）；失败则**真的**逐个重试。
 *
 * ⚠️ 2026-09-21 修（真事故）：旧版遇到「批量里有 1 个失败」时只打了一句「逐个重试」
 * 的日志、**实际没有重试**，失败原因还被整个丢掉 —— 于是通知写「可取皆已领完」，
 * App 里那张碎片还在，只能手动领。现在返回 { claimed: [], failed: [{id,label,reason}] }，
 * 由 zeekrClaimAll 决定「下一轮再试」还是「进通知」。
 */
async function zeekrClaimDebris(ctx, debrisList) {
  if (!debrisList.length) return { claimed: [], failed: [] };
  var toCmd = function (item) {
    return {
      record: item.eventCode,
      payContent: { bubbleAssetsId: item.id },
      applyExt: { origin: item.sourceId },
    };
  };
  var labelOf = function (item) {
    return String(item.sourceId || item.sceneRemark || item.id);
  };

  var claimed = [];
  var pending = [];
  var data = await zeekrPost(ctx, ZEEKR_API.claimDebris, {
    applyCmdList: debrisList.map(toCmd),
  });
  if (data.code === "000000" && Object.prototype.toString.call(data.data) === "[object Array]") {
    for (var i = 0; i < debrisList.length; i++) {
      var r = data.data[i];
      var item = debrisList[i] || {};
      if (r && r.success === true) claimed.push(zeekrDebrisName(r));
      else pending.push({ item: item, reason: zeekrFailReason(r, data.msg || "") });
    }
    if (pending.length)
      ctx.out("⚠️ 批量领取有 " + pending.length + " 个失败，改为逐个重试");
  } else {
    ctx.out(
      "⚠️ 批量领取碎片失败（" +
        (data.msg || JSON.stringify(data)) +
        "），改为逐个领取"
    );
    for (var k = 0; k < debrisList.length; k++)
      pending.push({ item: debrisList[k], reason: (data.msg || "批量接口返回异常") + "" });
  }

  var failed = [];
  for (var p = 0; p < pending.length; p++) {
    var it = pending[p].item;
    var one = await zeekrPost(ctx, ZEEKR_API.claimDebris, {
      applyCmdList: [toCmd(it)],
    });
    var arr = one.data;
    var isArr = Object.prototype.toString.call(arr) === "[object Array]";
    var anyOk = false;
    if (one.code === "000000" && isArr) {
      for (var q = 0; q < arr.length; q++) {
        if (arr[q] && arr[q].success === true) {
          anyOk = true;
          claimed.push(zeekrDebrisName(arr[q]));
        }
      }
    }
    if (!anyOk) {
      var why = zeekrFailReason(
        isArr && arr.length ? arr[0] : null,
        one.msg || pending[p].reason
      );
      ctx.out("❌ 碎片领取失败（" + labelOf(it) + "）: " + why);
      failed.push({ id: it.id, label: labelOf(it), reason: why });
    }
    await zeekrSleep(zeekrRand(800, 1500));
  }
  if (claimed.length) ctx.out("🧩 碎片奖励: " + claimed.join("、"));
  return { claimed: claimed, failed: failed };
}

/* 领取能量球。返回 { val, failed }（失败要能被重试/上报，不能再静默吞掉）。 */
async function zeekrClaimSevenDayLottery(ctx, lotteryList) {
  if (!lotteryList.length) return { claimed: [], failed: [] };
  var claimed = [];
  var failed = [];
  for (var i = 0; i < lotteryList.length; i++) {
    var item = lotteryList[i];
    var label = String(item.sourceId || item.sceneRemark || "七日连签抽奖球");
    var data = await zeekrPost(ctx, ZEEKR_API.claimSevenDayLottery, {
      record: ZEEKR_RECORD_SEVEN_DAY_LOTTERY,
      fixedZgreenAssetId: item.id,
      optional: { mappingMsg: true },
    });
    var ok = data.code === "000000" && data.data && data.data.success === true;
    if (ok) {
      var prize =
        (data.data.invoice &&
          data.data.invoice.materialSnapshot &&
          data.data.invoice.materialSnapshot.name) ||
        "七日连签奖励";
      claimed.push(prize);
      ctx.out("🎁 七日连签奖励已领: " + prize);
    } else {
      var why = zeekrFailReason(data.data, data.msg || "七日连签领取失败");
      ctx.out("❌ 七日连签奖励领取失败（" + label + "）: " + why);
      failed.push({ id: item.id, label: label, reason: why });
    }
    await zeekrSleep(zeekrRand(1000, 2000));
  }
  return { claimed: claimed, failed: failed };
}

async function zeekrClaimWalk(ctx, walkList) {
  if (!walkList.length) return { val: 0, failed: [] };
  var total = 0;
  var failed = [];
  for (var i = 0; i < walkList.length; i++) {
    var it = walkList[i];
    var val = it.val || 0;
    var data = await zeekrPost(ctx, ZEEKR_API.claimWalk, { energyIds: [it.id] });
    if (data.code === "000000") {
      total += val;
      ctx.out("♻️ 能量球已领: +" + val);
    } else {
      var why = (data.msg || JSON.stringify(data)) + "";
      ctx.out("❌ 能量球领取失败（" + val + "g）: " + why);
      failed.push({ id: it.id, label: val + "g 能量球", reason: why.slice(0, 160) });
    }
    await zeekrSleep(zeekrRand(800, 1500));
  }
  return { val: total, failed: failed };
}

/* 领取极值。返回 { val, failed }。 */
async function zeekrClaimIntegral(ctx, integralList) {
  if (!integralList.length) return { val: 0, failed: [] };
  var total = 0;
  var failed = [];
  for (var i = 0; i < integralList.length; i++) {
    var it = integralList[i];
    var val = it.val || 0;
    var data = await zeekrPost(ctx, ZEEKR_API.claimIntegral, {
      energyIds: [it.id],
    });
    if (data.code === "000000") {
      total += val;
      ctx.out("🏆 极值已领: +" + val);
    } else {
      var why = (data.msg || JSON.stringify(data)) + "";
      ctx.out("❌ 极值领取失败（" + val + "）: " + why);
      failed.push({ id: it.id, label: val + " 极值", reason: why.slice(0, 160) });
    }
    await zeekrSleep(zeekrRand(800, 1500));
  }
  return { val: total, failed: failed };
}

function zeekrParseWaits(str) {
  var parts = String(str || "").split(",");
  var out = [];
  for (var i = 0; i < parts.length; i++) {
    var n = parseFloat(parts[i]);
    if (!isNaN(n) && n > 0) out.push(Math.round(n * 1000));
  }
  return out.length ? out : [45000, 60000, 75000, 60000];
}

/**
 * 领取循环：先领能量球 → 领极值 → 批量领碎片 → 复查。
 * 顺序不能反：能量球入账会让「减碳2000g」任务达标，进而生成新碎片。
 * 奖励是异步入账的（1~3 分钟），所以：
 *   poll=0（默认）：只查一轮，把「延迟入账的补领」交给 10 分钟后的第二条 cron（ZEEKR_MODE=claim）
 *   poll=1        ：按 WAITS / SETTLE / MAX 做时间窗口轮询（客户端超时必须放宽到 ≥ MAX）
 */
async function zeekrClaimAll(ctx, cfg) {
  var waits = zeekrParseWaits(cfg.waits);
  var silentRounds = 3;
  var minSettleMs = cfg.settle * 1000;
  var maxMs = cfg.max * 1000;
  var startedAt = Date.now();
  var claimed = {};
  var attempts = {}; /* id → 已尝试次数：失败项下一轮再试，不再"领之前就记成已领" */
  var failedMap = {}; /* id → { id, label, reason }：领失败且还没领到的项 */
  var maxAttempts = 3;
  var debrisCount = 0,
    lotteryCount = 0,
    walkVal = 0,
    integralVal = 0,
    emptyStreak = 0,
    round = 0,
    lastClaimAt = 0;
  var conclusion = "";
  var fresh = function (list) {
    var out = [];
    for (var i = 0; i < list.length; i++)
      if (!Object.prototype.hasOwnProperty.call(claimed, list[i].id))
        out.push(list[i]);
    return out;
  };
  /* 本轮还能尝试的项（每项最多 maxAttempts 次） */
  var bump = function (list) {
    var todo = [];
    for (var i = 0; i < list.length; i++) {
      var key = list[i].id;
      var n = (attempts[key] || 0) + 1;
      attempts[key] = n;
      if (n <= maxAttempts) todo.push(list[i]);
    }
    return todo;
  };
  /* 只有**确实领到**的项才记成已领（旧版领之前就记，失败后永不重试） */
  var settle = function (list, failList) {
    for (var i = 0; i < list.length; i++) {
      var bad = false;
      for (var j = 0; j < (failList || []).length; j++) {
        if (failList[j].id === list[i].id) {
          bad = true;
          break;
        }
      }
      if (!bad) {
        claimed[list[i].id] = 1;
        delete failedMap[list[i].id];
      }
    }
  };

  while (true) {
    round++;
    var got = await zeekrGetUncollected(ctx);
    var d = fresh(got.debrisList);
    var w = fresh(got.walkList);
    var g = fresh(got.integralList);
    var l = fresh(got.lotteryList);
    var elapsed = Date.now() - startedAt;

    var wTry = bump(w),
      gTry = bump(g),
      dTry = bump(d),
      lTry = bump(l);

    if (!wTry.length && !gTry.length && !dTry.length && !lTry.length) {
      if (d.length || w.length || g.length || l.length) {
        /* 列表里还有东西，但都重试到上限了 —— 绝不能报「已领完」 */
        var left = d.concat(w).concat(g).concat(l);
        for (var a1 = 0; a1 < left.length; a1++) {
          if (!failedMap[left[a1].id]) {
            failedMap[left[a1].id] = {
              id: left[a1].id,
              label: String(left[a1].sourceId || left[a1].sceneRemark || left[a1].id),
              reason: "重试 " + maxAttempts + " 次仍未领到",
            };
          }
        }
        conclusion =
          "⚠️ 仍有 " +
          zeekrCountKeys(failedMap) +
          " 项未领到（每项已重试 " +
          maxAttempts +
          " 次）";
        break;
      }
      emptyStreak++;
      var sinceClaim = Date.now() - (lastClaimAt || startedAt);
      if (!cfg.poll || (emptyStreak >= silentRounds && sinceClaim >= minSettleMs)) {
        if (zeekrCountKeys(failedMap)) {
          var fparts = [];
          var flist = zeekrFailedList(failedMap);
          for (var f1 = 0; f1 < flist.length; f1++)
            fparts.push(flist[f1].label + "(" + flist[f1].reason + ")");
          conclusion =
            "⚠️ 复查结束，但仍有 " + flist.length + " 项领取失败：" + fparts.join("、");
        } else {
          conclusion = cfg.poll
            ? "✅ 复查确认：可取皆已领完（共 " +
              round +
              " 轮 / " +
              Math.round(elapsed / 1000) +
              "s）"
            : "✅ 本次查询无待领取奖励";
        }
        break;
      }
      var waitTry =
        waits[Math.max(0, Math.min(emptyStreak - 1, waits.length - 1))];
      if (elapsed + waitTry > maxMs) {
        conclusion =
          "⏰ 观察到 " + Math.round(elapsed / 1000) + "s，到领取窗口上限，结束复查";
        break;
      }
      ctx.vlog("第 " + round + " 轮暂无可领（已观察 " + Math.round(elapsed / 1000) + "s）...");
    } else {
      /* ⚠️ 2026-09-21 修：旧版在**领取之前**就把 id 记进 claimed，一次失败就永不重试，
         列表还会被过滤成空 → 打出「✅ 可取皆已领完」而东西仍在。 */
      var rw = await zeekrClaimWalk(ctx, wTry);
      walkVal += rw.val || 0;
      settle(wTry, rw.failed);
      zeekrMergeFailed(failedMap, rw.failed);

      var rg = await zeekrClaimIntegral(ctx, gTry);
      integralVal += rg.val || 0;
      settle(gTry, rg.failed);
      zeekrMergeFailed(failedMap, rg.failed);

      var rd = await zeekrClaimDebris(ctx, dTry);
      debrisCount += (rd.claimed || []).length;
      settle(dTry, rd.failed);
      zeekrMergeFailed(failedMap, rd.failed);

      var rl = await zeekrClaimSevenDayLottery(ctx, lTry);
      lotteryCount += (rl.claimed || []).length;
      settle(lTry, rl.failed);
      zeekrMergeFailed(failedMap, rl.failed);

      emptyStreak = 0;
      lastClaimAt = Date.now();
    }

    if (!cfg.poll) {
      var nfail = zeekrCountKeys(failedMap);
      conclusion = nfail
        ? "⚠️ 未领净 " + nfail + " 项（稍后的「只领取」任务会再试）"
        : "✅ 已领取一轮（延迟入账的奖励由稍后的「只领取」任务补上）";
      break;
    }

    var wait = waits[Math.max(0, Math.min(emptyStreak - 1, waits.length - 1))];
    if (Date.now() - startedAt + wait > maxMs) {
      conclusion = "⏰ 到领取窗口上限，结束复查";
      break;
    }
    ctx.vlog(Math.round(wait / 1000) + "s 后复查（新奖励可能还在入账路上）...");
    await zeekrSleep(wait);
  }

  if (conclusion) ctx.out(conclusion);
  return {
    debrisCount: debrisCount,
    lotteryCount: lotteryCount,
    walkVal: walkVal,
    integralVal: integralVal,
    rounds: round,
    failed: zeekrFailedList(failedMap),
  };
}


const https = require('node:https');
const fs = require('node:fs');
const pathModule = require('node:path');
const started = Date.now();
const dryRun = process.env.ZEEKR_DRY_RUN === '1';
const title = '极氪每日签到与奖励领取';
const secrets = new Set();
function safe(text) {
  let result = String(text);
  for (const secret of secrets) if (secret) result = result.split(secret).join('[已隐藏]');
  return result.replace(/Bearer\s+\S+/gi, '[凭据已隐藏]')
    .replace(/[\w-]+\.[\w-]+\.[\w-]+/g, '[凭据已隐藏]')
    .replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, '[手机号已隐藏]')
    .replace(/[\x00-\x1f\x7f]/g, ' ');
}
function log(text) {
  console.log(`[${new Date().toTimeString().slice(0, 8)}] ${safe(text)}`);
}
function request(options) {
  if (dryRun) throw new Error('断网预演禁止网络请求');
  return new Promise((resolve, reject) => {
    const url = new URL(options.url);
    if (url.protocol !== 'https:' || url.username || url.password ||
        !['api-gw-toc.zeekrlife.com', 'itunes.apple.com'].includes(url.hostname)) {
      reject(new Error('请求地址不受支持'));
      return;
    }
    const req = https.request(url, {method: options.method, headers: options.headers}, response => {
      let length = 0;
      const chunks = [];
      response.on('data', chunk => {
        length += chunk.length;
        if (length > 2 * 1024 * 1024) req.destroy(new Error('响应过大'));
        else chunks.push(chunk);
      });
      response.on('error', () => reject(new Error('响应读取失败')));
      response.on('end', () => {
        if ((response.statusCode < 200 || response.statusCode >= 300) && ![401, 403].includes(response.statusCode)) {
          reject(new Error(`HTTP ${response.statusCode}`));
          return;
        }
        resolve({status: response.statusCode, body: Buffer.concat(chunks).toString('utf8')});
      });
    });
    const timer = setTimeout(() => req.destroy(new Error('请求超时')), options.timeoutMs || 20000);
    req.on('close', () => clearTimeout(timer));
    req.on('error', () => reject(new Error('网络请求失败或超时')));
    if (options.body != null) req.write(options.body);
    req.end();
  });
}
function normalizedEnvironment() {
  const env = {};
  // Keep legacy unprefixed keys without copying unrelated host configuration.
  const names = new Set(['TOKEN','VAL','MODE','TAG','STEPS','POLL','WAITS','SETTLE','MAX',
    'APPVER','LIKE','NOTIFY','VERBOSE','DEVICEID','APPSECRET','NATIVE','NATIVEREQUESTS',
    'PAGECONTEXT','UA','PHONEMODEL','IOSVERSION','READWAIT','DELAY','DAILYSTEPS']);
  for (const [key, value] of Object.entries(process.env)) {
    if (names.has(zeekrNormKey(key))) env[zeekrNormKey(key)] = value;
  }
  // Explicit supported canonical names keep the import contract and runtime configuration aligned.
  const canonicalKeys = ["ZEEKR_TOKEN", "ZEEKR_VAL", "ZEEKR_MODE", "ZEEKR_TAG", "ZEEKR_STEPS", "ZEEKR_LIKE", "ZEEKR_POLL", "ZEEKR_WAITS", "ZEEKR_SETTLE", "ZEEKR_MAX", "ZEEKR_APPVER", "ZEEKR_NATIVE", "ZEEKR_NATIVE_REQUESTS", "ZEEKR_PAGE_CONTEXT", "ZEEKR_UA", "ZEEKR_PHONE_MODEL", "ZEEKR_IOS_VERSION", "ZEEKR_READWAIT", "ZEEKR_DELAY", "ZEEKR_DAILYSTEPS", "ZEEKR_NOTIFY", "ZEEKR_VERBOSE", "ZEEKR_DEVICE_ID", "ZEEKR_APP_SECRET"];
  for (const key of canonicalKeys) {
    if (process.env[key] !== undefined) env[zeekrNormKey(key)] = process.env[key];
  }
  // Canonical names win when both aliases exist. Explicit TAG access fixes the previous contract failure.
  for (const [key, value] of Object.entries(process.env)) {
    if (/^ZEEKR_/i.test(key) && names.has(zeekrNormKey(key))) env[zeekrNormKey(key)] = value;
  }
  if (process.env.ZEEKR_TAG !== undefined) env.TAG = process.env.ZEEKR_TAG;
  return env;
}
function accountsFrom(env) {
  const accounts = [];
  const tokenKeys = Object.keys(process.env).filter(k => /^ZEEKR_TOKEN_\d+$/i.test(k)).sort();
  const valKeys = Object.keys(process.env).filter(k => /^ZEEKR_VAL_\d+$/i.test(k)).sort();
  const inputs = env.TOKEN ? [env.TOKEN] : tokenKeys.length ? tokenKeys.map(k => process.env[k]) :
    env.VAL ? [env.VAL] : valKeys.map(k => process.env[k]);
  for (const input of inputs) {
    for (const line of String(input).split(/\r?\n/)) {
      if (!line.trim()) continue;
      const raw = line.trim();
      secrets.add(raw);
      let token = raw;
      let device = '';
      let appSecret = '';
      if (raw.startsWith('{')) {
        try {
          const value = JSON.parse(raw);
          token = value.authorization || value.Authorization || value.token || value.TOKEN || value.ZEEKR_TOKEN || '';
          device = String(value.device_id || '');
          appSecret = String(value.app_secret || '');
        } catch { token = ''; }
      }
      secrets.add(token);
      secrets.add(token.replace(/^Bearer\s+/i, ''));
      secrets.add(device);
      secrets.add(appSecret);
      accounts.push({token, device, appSecret});
    }
  }
  return accounts;
}
function validateConfig(env) {
  if (env.MODE && !['all','sign','claim'].includes(env.MODE.toLowerCase())) throw new Error('MODE 必须为 all、sign 或 claim');
  if (env.STEPS && !/^(off|0|no|false|\d+|\d+\s*-\s*\d+)$/i.test(env.STEPS)) throw new Error('STEPS 格式无效');
  if (env.STEPS && !/^(off|0|no|false)$/i.test(env.STEPS)) {
    const values = env.STEPS.split('-').map(Number);
    if (values.some(v => !Number.isSafeInteger(v) || v < 1 || v > 100000) || values[0] > (values[1] || values[0])) throw new Error('STEPS 范围无效');
  }
  for (const key of ['SETTLE','MAX']) {
    if (env[key] !== undefined && (!/^\d+$/.test(env[key]) || Number(env[key]) < 1 || Number(env[key]) > 3600)) throw new Error(`${key} 应为 1 至 3600 秒`);
  }
  if (env.WAITS && !/^\d+(,\d+)*$/.test(env.WAITS)) throw new Error('WAITS 应为逗号分隔的秒数');
  if (env.WAITS && env.WAITS.split(',').some(v => Number(v) < 1 || Number(v) > 600)) throw new Error('WAITS 间隔应为 1 至 600 秒');
}
async function runAccount(account, index, base) {
  const stats = {account: index, total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0};
  const begin = Date.now();
  const env = {...base, TOKEN: account.token, DEVICEID: account.device || base.DEVICEID || '', APPSECRET: account.appSecret || base.APPSECRET || ''};
  delete env.VAL;
  const cfg = zeekrLoadConfig({env});
  const info = zeekrParseToken(cfg.token);
  secrets.add(info.deviceId);
  secrets.add(env.DEVICEID);
  secrets.add(env.APPSECRET);
  const ctx = {
    RT: {platform: '青龙', http: request}, token: cfg.token, accountId: info.accountId,
    deviceId: cfg.deviceId, nativeDeviceId: info.deviceId, sourcePlatform: info.sourcePlatform,
    appVersion: cfg.appver, nativeEnabled: !!(cfg.native && cfg.appSecret && info.deviceId && info.deviceId !== '0' && info.sourcePlatform !== 'WEB_PC'),
    appSecret: cfg.appSecret, phoneModel: cfg.phoneModel, iosVersion: cfg.iosVersion, ua: cfg.ua,
    pageContext: cfg.pageContext, readWait: cfg.readWait, optionalRemainingMs: 120000,
    // Upstream strings may embed raw business responses. Only report controlled stage results below.
    out: () => {}, vlog: () => {},
    identity: data => {
      if (!data || typeof data !== 'object') return;
      const profile = data.accountInfoDTO || data.userInfo || data;
      for (const key of ['nickname', 'userName', 'displayName', 'uid']) {
        if (typeof profile[key] === 'string' || typeof profile[key] === 'number') log(`账号 ${index} ${key} ${profile[key]}`);
      }
    },
  };
  ctx.nativeRequests = ctx.nativeEnabled && cfg.nativeRequests;
  async function stage(name, action) {
    const time = Date.now();
    stats.total++;
    log(`账号 ${index} 阶段 ${stats.total} ${name} 开始`);
    try {
      const state = await action();
      if (!['success','alreadyComplete','skipped'].includes(state)) throw new Error('未确认业务成功');
      stats[state]++;
      const labels = {success: '✅ 成功', alreadyComplete: '☑️ 已完成', skipped: '⏭️ 跳过'};
      log(`账号 ${index} 阶段 ${stats.total} ${name} ${labels[state]}，耗时 ${Date.now() - time} 毫秒`);
    } catch (error) {
      stats.failed++;
      // All thrown diagnostics below and in the transport are fixed local text.
      log(`账号 ${index} 阶段 ${stats.total} ${name} ❌ 失败，${error.message}，耗时 ${Date.now() - time} 毫秒`);
    }
  }
  await stage('配置检查', async () => {
    validateConfig(env);
    if (!dryRun && (!cfg.token || !info.deviceId || !info.accountId || (info.exp && info.exp <= Date.now()))) throw new Error('凭据格式无效、缺少账号或设备字段，或已过期');
    if (dryRun && !account.token.trim()) throw new Error('缺少预演凭据');
    return 'success';
  });
  if (!stats.failed) {
    // JWT contains the official account identity. Never print phone/device/session fields.
    if (!dryRun) {
      const payload = zeekrParseJsonExact(zeekrB64Decode(cfg.token.replace(/^Bearer\s+/i, '').split('.')[1]));
      const sub = typeof payload.sub === 'string' ? zeekrParseJsonExact(payload.sub) : payload.sub;
      const identity = sub && sub.accountInfoDTO || {};
      if (info.accountId) log(`账号 ${index} 公开 UID ${info.accountId}`);
      for (const key of ['nickname','userName','displayName']) if (typeof identity[key] === 'string') log(`账号 ${index} ${key} ${identity[key]}`);
    }
    if (dryRun) {
      await stage('断网动作计划', async () => {
        log(`账号 ${index} 模式 ${cfg.mode}，签到阅读 ${cfg.mode !== 'claim'}，步数上报 ${cfg.stepsRaw !== 'off' && cfg.mode !== 'claim'}，点赞 ${cfg.forceLike && cfg.mode !== 'claim'}，奖励领取 ${cfg.mode !== 'sign'}，轮询 ${cfg.poll}`);
        return 'skipped';
      });
    } else {
      await stage('客户端版本', async () => {
        if (!ctx.appVersion) {
          try {
            const response = await request({url: 'https://itunes.apple.com/cn/lookup?id=1570277888', method: 'GET', timeoutMs: 8000});
            const data = JSON.parse(response.body);
            ctx.appVersion = data.results && data.results[0] && data.results[0].version;
          } catch { /* Upstream documented fallback. */ }
          ctx.appVersion = ctx.appVersion || '4.9.33';
        }
        await zeekrOptionalPause(ctx, cfg.delay);
        return 'success';
      });
      if (cfg.mode !== 'claim') {
        await stage('每日签到', async () => await zeekrSignIn(ctx) ? 'success' : 'failure');
        if (!ctx.authDead) {
          await stage('步数上报', async () => {
            const steps = zeekrResolveStepCounts(cfg.stepsRaw, cfg.dailySteps ? zeekrDailyRng(ctx.accountId) : undefined);
            if (!steps) return 'skipped';
            return await zeekrSyncWalk(ctx, steps, 20) ? 'success' : 'failure';
          });
          let tasks;
          await stage('查询任务', async () => { tasks = await zeekrGetTasks(ctx); return 'success'; });
          if (tasks && !ctx.authDead) {
            await stage('阅读文章', async () => {
              const task = tasks.find(t => t.name === ZEEKR_TASK_ARTICLE);
              if (!task) return 'skipped';
              if (zeekrTaskDone(task)) return 'alreadyComplete';
              return await zeekrReadArticle(ctx, tasks) ? 'success' : 'failure';
            });
            await stage('社区点赞', async () => {
              if (!cfg.forceLike) return 'skipped';
              return await zeekrLikeSquarePost(ctx) ? 'success' : 'failure';
            });
          }
        }
      }
      if (cfg.mode !== 'claim' && !ctx.authDead) {
        await stage('任务状态复查', async () => {
          let tasks = await zeekrGetTasks(ctx);
          const walk = tasks.find(t => t.name === ZEEKR_TASK_WALK);
          const steps = zeekrResolveStepCounts(cfg.stepsRaw, cfg.dailySteps ? zeekrDailyRng(ctx.accountId) : undefined);
          if (steps && walk && !zeekrTaskDone(walk) && cfg.mode === 'all') {
            if (!await zeekrSyncWalk(ctx, steps, 20)) return 'failure';
            tasks = await zeekrGetTasks(ctx);
          }
          const selected = tasks.filter(t => t.name === ZEEKR_TASK_ARTICLE || (steps && t.name === ZEEKR_TASK_WALK) || (cfg.forceLike && t.name === ZEEKR_TASK_PRAISE));
          log(`账号 ${index} 复查任务 ${selected.length}，已完成 ${selected.filter(zeekrTaskDone).length}`);
          return selected.every(zeekrTaskDone) ? 'success' : 'failure';
        });
      }
      if (cfg.mode !== 'sign' && !ctx.authDead) {
        await stage('领取碎片、七日奖励、能量球及极值', async () => {
          const result = await zeekrClaimAll(ctx, cfg);
          log(`账号 ${index} 碎片 ${result.debrisCount}，七日奖励 ${result.lotteryCount}，能量 ${result.walkVal}，极值 ${result.integralVal}，轮次 ${result.rounds}，未领 ${result.failed.length}`);
          return result.failed.length ? 'failure' : 'success';
        });
      }
    }
  }
  stats.durationMs = Date.now() - begin;
  stats.ok = stats.failed === 0;
  log(`账号 ${index} 统计 ${JSON.stringify(stats)}`);
  return stats;
}
function notificationSelected() {
  const setting = String(process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
  if (['0','false','no','off'].includes(setting) || process.env.ZEEKR_NOTIFY === '0') return false;
  if (['1','true','yes','on'].includes(setting)) return true;
  const selectors = String(process.env.QINGLONG_NOTIFY_SCRIPTS || '').split(/[,;\s]+/).filter(Boolean);
  const filename = pathModule.basename(__filename);
  const relative = __filename.includes('/scripts/') ? __filename.split('/scripts/').slice(1).join('/scripts/') : filename;
  return selectors.some(selector => {
    const pattern = '^' + selector.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$';
    return ['a5b6bae676d9ef43', filename, relative, `scripts/${relative}`].some(value => new RegExp(pattern).test(value));
  });
}
async function notify(summary, tag) {
  if (!notificationSelected()) return '已关闭或未列入通知';
  if (dryRun) return '断网预演，已生成本地通知摘要';
  const locations = [process.env.QINGLONG_NOTIFY_DIR && pathModule.join(process.env.QINGLONG_NOTIFY_DIR, 'sendNotify.js'), '/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'].filter(Boolean);
  for (const location of locations) {
    if (!fs.existsSync(location)) continue;
    try {
      const notifier = require(location);
      if (typeof notifier.sendNotify !== 'function') continue;
      let timer;
      try {
        await Promise.race([
          Promise.resolve().then(() => notifier.sendNotify(safe(title + (tag ? `（${tag}）` : '')), safe(`账号总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}，状态 ${summary.status}`))),
          new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('通知超时')), 15000); }),
        ]);
      } finally { clearTimeout(timer); }
      return '已发送';
    } catch { return '通知失败，保留业务退出码'; }
  }
  return '通知模块不可用，保留业务退出码';
}
async function main() {
  const env = normalizedEnvironment();
  const accounts = accountsFrom(env);
  for (const key of ['DEVICEID','APPSECRET']) secrets.add(env[key]);
  log(`========== ${title} ==========`);
  log(`开始时间 ${new Date(started).toISOString()}，模式 ${dryRun ? '断网预演' : '正式执行'}，账号数 ${accounts.length}`);
  if (env.TAG) log(`场次 ${env.TAG}`);
  const results = [];
  for (let i = 0; i < accounts.length; i++) {
    try { results.push(await runAccount(accounts[i], i + 1, env)); }
    catch { results.push({account: i + 1, ok: false, total: 1, success: 0, failed: 1, skipped: 0, alreadyComplete: 0}); log(`账号 ${i + 1} 执行异常，继续处理其他账号`); }
  }
  const failed = results.filter(r => !r.ok).length;
  const summary = {accounts: accounts.length, success: results.length - failed, failed,
    status: !accounts.length ? 'configuration-error' : failed ? (failed < accounts.length ? 'partial-failure' : 'failure') : dryRun ? 'dry-run' : 'success',
    tasks: {total: 0, success: 0, alreadyComplete: 0, skipped: 0, failed: 0}};
  for (const result of results) for (const key of Object.keys(summary.tasks)) summary.tasks[key] += result[key];
  const exitCode = !accounts.length || failed ? 1 : 0;
  if (!accounts.length) log('❌ 配置错误，请设置 ZEEKR_TOKEN，每行一个账号');
  summary.notification = await notify(summary, env.TAG || '');
  summary.durationMs = Date.now() - started;
  summary.finishedAt = new Date().toISOString();
  summary.exitCode = exitCode;
  log('----------------------------------------');
  log(`账号统计 总数 ${summary.accounts}，成功 ${summary.success}，失败 ${summary.failed}`);
  log(`子任务统计 ${JSON.stringify(summary.tasks)}`);
  log(`通知 ${summary.notification}，总耗时 ${summary.durationMs} 毫秒`);
  log(`完成时间 ${summary.finishedAt}，最终状态 ${summary.status}`);
  console.log('TASK_SUMMARY=' + JSON.stringify(summary));
  process.exitCode = exitCode;
  // A timed-out notification module can retain open sockets. Preserve the business exit code.
  if (summary.notification === '通知失败，保留业务退出码') process.exit(exitCode);
}
if (require.main === module) main().catch(() => {
  log('❌ 执行器异常');
  process.exitCode = 1;
});
