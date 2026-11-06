// name: 酷狗概念版 VIP 签到
// cron: 1 1 * * *
// ==UserScript==
// @name         酷狗概念版 VIP 自动签到（ScriptCat 定时版）
// @namespace    https://github.com/yimu56
// @version      1.0.3
// @description  每天自动领取酷狗概念版 VIP：支持扫码 / 手机号 / 手动三种登录，启动后随机延迟签到，支持系统通知与多渠道推送，零外部依赖
// @author       yimu56
// @license      MIT
// @homepageURL  https://github.com/yimu56/kgcheckin_ScriptCat
// @supportURL   https://github.com/yimu56/kgcheckin_ScriptCat/issues
// @crontab      * 1-6 once * *
// @grant        GM_xmlhttpRequest
// @grant        GM_notification
// @grant        GM_log
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM_openInTab
// @connect      kugou.com
// @connect      kugou.com.cn
// @connect      api.qrserver.com
// @connect      qq.com
// @connect      feishu.cn
// @connect      dingtalk.com
// @connect      yhchat.com
// @connect      jwzhd.com
// @connect      ftqq.com
// @connect      pushplus.plus
// @connect      telegram.org
// @connect      day.app
// @connect      discord.com
// @connect      discordapp.com
// @connect      *
// ==/UserScript==
// 独立 Node.js 18+ 维护版；原作者 yimu56，MIT。
/*
使用：KG_ACCOUNTS 每行 userid#token（仅在第一个 # 分割）；兼容 USERINFO JSON 数组。
凭据获取：在原作者 ScriptCat 脚本扫码/短信登录后，从其账号配置读取 userid、token；
也可用本脚本 KG_ACTION=qr / sms / phone 登录。登录结果仅写入显式 KG_ACCOUNT_FILE，权限 0600。
qr 还须设置 KG_QR_FILE（本地 SVG）；用酷狗音乐 APP 扫描该本地文件，不输出登录链接。
KG_QR_ONLINE 不允许开启，避免第三方接收登录凭据。sms / phone 使用 KG_LOGIN_ACCOUNT=手机号#验证码；兼容 KG_PHONE / KG_CODE。
安全默认：只查询 VIP。领取需显式 KG_TASKS=listen,ad,vip；listen/ad 会上报听歌/广告活动，
请确认真实完成对应活动再启用。周续期默认关闭，KG_REFRESH_WEEKDAY=0..6 且须配置账号文件。
KG_ACTION=sign 默认每日 01:00 触发，沿用 1..60 分钟随机延迟；now 立即执行。
KG_ACTION=list / clear 仅列出账号数 / 清空显式账号文件；不修改青龙环境配置。
KG_DRY_RUN=1 完全断网，不等待、不读写账号文件、不加载通知模块，只校验并预演。
通知：支持青龙 sendNotify.js 与原有各渠道；QINGLONG_NOTIFY=0 禁用；通知失败不覆盖业务退出码。
本脚本不发布评论、帖子或分享文案。所有身份只采用官方响应，凭据及原始响应不输出。
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
    const identities = ["59cfee057c900f01", "scripts/kgcheckin_user.js", "kgcheckin_user.js", "kgcheckin_user"];
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
const {execFile} = require('node:child_process');
const DRY = /^(1|true|yes|on)$/i.test(process.env.KG_DRY_RUN || '');
const started = Date.now();
function log(msg) { console.log(`[${new Date().toLocaleTimeString('zh-CN', {hour12:false})}] ${msg}`); }
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
function safeError(e) { return e && e.safeMessage || '请求或数据处理失败（详细响应已隐藏）'; }
function fault(message) { const e = new Error(message); e.safeMessage=message; return e; }
  function buildGfTables(poly) {
    var exp = new Uint8Array(512);
    var log = new Uint8Array(256);
    var x = 1;
    for (var i = 0; i < 255; i++) {
      exp[i] = x;
      log[x] = i;
      x <<= 1;
      if (x & 0x100) x ^= poly;
    }
    for (var j = 255; j < 512; j++) exp[j] = exp[j - 255];
    return { exp: exp, log: log };
  }

  var QR_GF = buildGfTables(0x11d);

  function gfMul(a, b) {
    if (a === 0 || b === 0) return 0;
    return QR_GF.exp[QR_GF.log[a] + QR_GF.log[b]];
  }

  function aesMul(a, b) {
    var r = 0;
    var x = a & 0xff;
    var y = b & 0xff;
    while (y) {
      if (y & 1) r ^= x;
      x <<= 1;
      if (x & 0x100) x ^= 0x11b;
      y >>= 1;
    }
    return r & 0xff;
  }

  // 自检：FIPS-197 里的经典例子 0x57 • 0x13 = 0xfe；QR 域 0x80 • 0x02 = 0x1d
  if (aesMul(0x57, 2) !== 0xae || aesMul(0x57, 0x13) !== 0xfe || gfMul(0x80, 2) !== 0x1d) {
    throw new Error('有限域乘法表自检失败');
  }

  /* ---------------- MD5 ---------------- */

  var MD5_S = [
    7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
    5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
    4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
    6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
  ];
  var MD5_K = (function () {
    var k = new Uint32Array(64);
    for (var i = 0; i < 64; i++) k[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 4294967296);
    return k;
  })();

  function utf8Bytes(str) {
    if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(str);
    var bytes = [];
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      if (c < 0x80) bytes.push(c);
      else if (c < 0x800) bytes.push(0xc0 | (c >> 6), 0x80 | (c & 63));
      else bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
    return new Uint8Array(bytes);
  }

  function bytesToHex(bytes) {
    var out = '';
    for (var i = 0; i < bytes.length; i++) out += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16);
    return out;
  }

  function hexToBytes(hex) {
    var out = new Uint8Array(hex.length >> 1);
    for (var i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
    return out;
  }

  function utf8ToBytes(value) {
    if (typeof value === 'string') return utf8Bytes(value);
    // ArrayBuffer.isView 是跨 realm 可靠的（instanceof 在沙箱里会失效）
    if (value && typeof value === 'object' && (ArrayBuffer.isView(value) || value instanceof Uint8Array)) {
      return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    }
    if (Array.isArray(value)) return new Uint8Array(value);
    return utf8Bytes(value && typeof value === 'object' ? JSON.stringify(value) : String(value));
  }

  function md5(data) {
    var bytes = utf8ToBytes(data);
    var len = bytes.length;
    var total = (((len + 8) >> 6) + 1) * 64;
    var buf = new Uint8Array(total);
    buf.set(bytes);
    buf[len] = 0x80;
    var view = new DataView(buf.buffer);
    var bitLen = len * 8;
    view.setUint32(total - 8, bitLen >>> 0, true);
    view.setUint32(total - 4, Math.floor(bitLen / 4294967296), true);

    var a0 = 0x67452301, b0 = 0xefcdab89, c0 = 0x98badcfe, d0 = 0x10325476;
    var M = new Uint32Array(16);

    for (var off = 0; off < total; off += 64) {
      for (var i = 0; i < 16; i++) M[i] = view.getUint32(off + i * 4, true);
      var A = a0, B = b0, C = c0, D = d0;
      for (var r = 0; r < 64; r++) {
        var F, g;
        if (r < 16) { F = (B & C) | (~B & D); g = r; }
        else if (r < 32) { F = (D & B) | (~D & C); g = (5 * r + 1) % 16; }
        else if (r < 48) { F = B ^ C ^ D; g = (3 * r + 5) % 16; }
        else { F = C ^ (B | ~D); g = (7 * r) % 16; }
        F = (F + A + MD5_K[r] + M[g]) >>> 0;
        A = D; D = C; C = B;
        B = (B + ((F << MD5_S[r]) | (F >>> (32 - MD5_S[r])))) >>> 0;
      }
      a0 = (a0 + A) >>> 0; b0 = (b0 + B) >>> 0; c0 = (c0 + C) >>> 0; d0 = (d0 + D) >>> 0;
    }

    var out = new Uint8Array(16);
    var ov = new DataView(out.buffer);
    ov.setUint32(0, a0, true);
    ov.setUint32(4, b0, true);
    ov.setUint32(8, c0, true);
    ov.setUint32(12, d0, true);
    return bytesToHex(out);
  }

  /* ---------------- SHA-256 + HMAC（钉钉加签用） ---------------- */

  var SHA256_K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ]);

  function sha256(data) {
    var bytes = utf8ToBytes(data);
    var len = bytes.length;
    var total = (((len + 8) >> 6) + 1) * 64;
    var buf = new Uint8Array(total);
    buf.set(bytes);
    buf[len] = 0x80;
    var view = new DataView(buf.buffer);
    var bitLen = len * 8;
    view.setUint32(total - 8, Math.floor(bitLen / 4294967296), false);
    view.setUint32(total - 4, bitLen >>> 0, false);

    var h = new Uint32Array([
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ]);
    var w = new Uint32Array(64);

    function rotr(x, n) { return (x >>> n) | (x << (32 - n)); }

    for (var off = 0; off < total; off += 64) {
      for (var i = 0; i < 16; i++) w[i] = view.getUint32(off + i * 4, false);
      for (var j = 16; j < 64; j++) {
        var s0 = rotr(w[j - 15], 7) ^ rotr(w[j - 15], 18) ^ (w[j - 15] >>> 3);
        var s1 = rotr(w[j - 2], 17) ^ rotr(w[j - 2], 19) ^ (w[j - 2] >>> 10);
        w[j] = (w[j - 16] + s0 + w[j - 7] + s1) >>> 0;
      }
      var a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
      for (var t = 0; t < 64; t++) {
        var S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        var ch = (e & f) ^ (~e & g);
        var temp1 = (hh + S1 + ch + SHA256_K[t] + w[t]) >>> 0;
        var S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        var maj = (a & b) ^ (a & c) ^ (b & c);
        var temp2 = (S0 + maj) >>> 0;
        hh = g; g = f; f = e; e = (d + temp1) >>> 0;
        d = c; c = b; b = a; a = (temp1 + temp2) >>> 0;
      }
      h[0] = (h[0] + a) >>> 0; h[1] = (h[1] + b) >>> 0;
      h[2] = (h[2] + c) >>> 0; h[3] = (h[3] + d) >>> 0;
      h[4] = (h[4] + e) >>> 0; h[5] = (h[5] + f) >>> 0;
      h[6] = (h[6] + g) >>> 0; h[7] = (h[7] + hh) >>> 0;
    }

    var out = new Uint8Array(32);
    var ov = new DataView(out.buffer);
    for (var n = 0; n < 8; n++) ov.setUint32(n * 4, h[n], false);
    return out;
  }

  function hmacSha256Base64(key, message) {
    var blockSize = 64;
    var keyBytes = utf8Bytes(key);
    if (keyBytes.length > blockSize) keyBytes = sha256(keyBytes);
    var padded = new Uint8Array(blockSize);
    padded.set(keyBytes);

    var ipad = new Uint8Array(blockSize);
    var opad = new Uint8Array(blockSize);
    for (var i = 0; i < blockSize; i++) {
      ipad[i] = padded[i] ^ 0x36;
      opad[i] = padded[i] ^ 0x5c;
    }
    var inner = sha256(concatBytes(ipad, utf8Bytes(message)));
    return base64Encode(sha256(concatBytes(opad, inner)));
  }

  function concatBytes(a, b) {
    var out = new Uint8Array(a.length + b.length);
    out.set(a, 0);
    out.set(b, a.length);
    return out;
  }

  var B64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

  function base64Encode(bytes) {
    var out = '';
    for (var i = 0; i < bytes.length; i += 3) {
      var b0 = bytes[i];
      var b1 = i + 1 < bytes.length ? bytes[i + 1] : 0;
      var b2 = i + 2 < bytes.length ? bytes[i + 2] : 0;
      out += B64_CHARS[b0 >> 2];
      out += B64_CHARS[((b0 & 3) << 4) | (b1 >> 4)];
      out += i + 1 < bytes.length ? B64_CHARS[((b1 & 15) << 2) | (b2 >> 6)] : '=';
      out += i + 2 < bytes.length ? B64_CHARS[b2 & 63] : '=';
    }
    return out;
  }

  function base64Decode(str) {
    var clean = String(str).replace(/[^A-Za-z0-9+/]/g, '');
    var out = new Uint8Array(Math.floor((clean.length * 3) / 4));
    var p = 0;
    for (var i = 0; i < clean.length; i += 4) {
      var c0 = B64_CHARS.indexOf(clean[i]);
      var c1 = B64_CHARS.indexOf(clean[i + 1]);
      var c2 = B64_CHARS.indexOf(clean[i + 2]);
      var c3 = B64_CHARS.indexOf(clean[i + 3]);
      if (p < out.length) out[p++] = (c0 << 2) | (c1 >> 4);
      if (c2 >= 0 && p < out.length) out[p++] = ((c1 & 15) << 4) | (c2 >> 2);
      if (c3 >= 0 && p < out.length) out[p++] = ((c2 & 3) << 6) | c3;
    }
    return out.subarray(0, p);
  }

  /* ---------------- AES（128 / 192 / 256 + CBC + PKCS7） ---------------- */

  var AES_SBOX = hexToBytes(
    '637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0' +
    'b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275' +
    '09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf' +
    'd0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2' +
    'cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb' +
    'e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08' +
    'ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e' +
    'e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16'
  );

  var AES_INV_SBOX = (function () {
    var inv = new Uint8Array(256);
    for (var i = 0; i < 256; i++) inv[AES_SBOX[i]] = i;
    return inv;
  })();

  var AES_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36];

  function aesExpandKey(key) {
    var nk = key.length >> 2;
    var nr = nk + 6;
    var total = (nr + 1) << 4;
    var w = new Uint8Array(total);
    w.set(key);
    for (var i = nk; i < total >> 2; i++) {
      var t = [w[(i - 1) * 4], w[(i - 1) * 4 + 1], w[(i - 1) * 4 + 2], w[(i - 1) * 4 + 3]];
      if (i % nk === 0) {
        t = [AES_SBOX[t[1]] ^ AES_RCON[i / nk - 1], AES_SBOX[t[2]], AES_SBOX[t[3]], AES_SBOX[t[0]]];
      } else if (nk > 6 && i % nk === 4) {
        t = [AES_SBOX[t[0]], AES_SBOX[t[1]], AES_SBOX[t[2]], AES_SBOX[t[3]]];
      }
      for (var k = 0; k < 4; k++) w[i * 4 + k] = w[(i - nk) * 4 + k] ^ t[k];
    }
    return { w: w, nr: nr };
  }

  function aesAddRoundKey(s, w, offset) {
    for (var i = 0; i < 16; i++) s[i] ^= w[offset + i];
  }

  function aesSubBytes(s, box) {
    for (var i = 0; i < 16; i++) s[i] = box[s[i]];
  }

  function aesShiftRows(s, inverse) {
    var t = s.slice();
    for (var r = 1; r < 4; r++) {
      for (var c = 0; c < 4; c++) {
        var src = inverse ? (c - r + 4) % 4 : (c + r) % 4;
        s[r + 4 * c] = t[r + 4 * src];
      }
    }
  }

  function aesMixColumns(s, inverse) {
    for (var c = 0; c < 4; c++) {
      var i = c * 4;
      var a0 = s[i], a1 = s[i + 1], a2 = s[i + 2], a3 = s[i + 3];
      if (inverse) {
        s[i]     = aesMul(a0, 14) ^ aesMul(a1, 11) ^ aesMul(a2, 13) ^ aesMul(a3, 9);
        s[i + 1] = aesMul(a0, 9)  ^ aesMul(a1, 14) ^ aesMul(a2, 11) ^ aesMul(a3, 13);
        s[i + 2] = aesMul(a0, 13) ^ aesMul(a1, 9)  ^ aesMul(a2, 14) ^ aesMul(a3, 11);
        s[i + 3] = aesMul(a0, 11) ^ aesMul(a1, 13) ^ aesMul(a2, 9)  ^ aesMul(a3, 14);
      } else {
        var all = a0 ^ a1 ^ a2 ^ a3;
        s[i]     = a0 ^ all ^ aesMul(a0 ^ a1, 2);
        s[i + 1] = a1 ^ all ^ aesMul(a1 ^ a2, 2);
        s[i + 2] = a2 ^ all ^ aesMul(a2 ^ a3, 2);
        s[i + 3] = a3 ^ all ^ aesMul(a3 ^ a0, 2);
      }
    }
  }

  function aesEncryptBlock(block, key) {
    var s = block.slice();
    aesAddRoundKey(s, key.w, 0);
    for (var round = 1; round < key.nr; round++) {
      aesSubBytes(s, AES_SBOX);
      aesShiftRows(s, false);
      aesMixColumns(s, false);
      aesAddRoundKey(s, key.w, round * 16);
    }
    aesSubBytes(s, AES_SBOX);
    aesShiftRows(s, false);
    aesAddRoundKey(s, key.w, key.nr * 16);
    return s;
  }

  function aesDecryptBlock(block, key) {
    var s = block.slice();
    aesAddRoundKey(s, key.w, key.nr * 16);
    for (var round = key.nr - 1; round > 0; round--) {
      aesShiftRows(s, true);
      aesSubBytes(s, AES_INV_SBOX);
      aesAddRoundKey(s, key.w, round * 16);
      aesMixColumns(s, true);
    }
    aesShiftRows(s, true);
    aesSubBytes(s, AES_INV_SBOX);
    aesAddRoundKey(s, key.w, 0);
    return s;
  }

  function aesCbcEncrypt(keyBytes, ivBytes, dataBytes) {
    var key = aesExpandKey(keyBytes);
    var padLen = 16 - (dataBytes.length % 16);
    var padded = new Uint8Array(dataBytes.length + padLen);
    padded.set(dataBytes);
    for (var i = dataBytes.length; i < padded.length; i++) padded[i] = padLen;

    var out = new Uint8Array(padded.length);
    var prev = ivBytes.slice(0, 16);
    for (var off = 0; off < padded.length; off += 16) {
      var block = new Uint8Array(16);
      for (var k = 0; k < 16; k++) block[k] = padded[off + k] ^ prev[k];
      block = aesEncryptBlock(block, key);
      out.set(block, off);
      prev = block;
    }
    return out;
  }

  function aesCbcDecrypt(keyBytes, ivBytes, dataBytes) {
    var key = aesExpandKey(keyBytes);
    var out = new Uint8Array(dataBytes.length);
    var prev = ivBytes.slice(0, 16);
    for (var off = 0; off < dataBytes.length; off += 16) {
      var block = dataBytes.slice(off, off + 16);
      var dec = aesDecryptBlock(block, key);
      for (var k = 0; k < 16; k++) out[off + k] = dec[k] ^ prev[k];
      prev = block;
    }
    if (!out.length) return out;
    var padLen = out[out.length - 1];
    if (padLen >= 1 && padLen <= 16) return out.subarray(0, out.length - padLen);
    return out;
  }

  /* ---------------- 酷狗侧的 AES 封装（对齐原项目语义） ---------------- */

  function randomString(len) { return crypto.randomBytes(len).toString('hex').slice(0,len); }

  /** 显式 key/iv → 返回 hex；未给 key → 随机 key，返回 { str, key } */
  function cryptoAesEncrypt(data, opt) {
    var plain = utf8ToBytes(data);
    var keyStr, ivStr, tempKey = '';
    if (opt && opt.key && opt.iv) {
      keyStr = opt.key;
      ivStr = opt.iv;
    } else {
      tempKey = (opt && opt.key) || randomString(16).toLowerCase();
      keyStr = md5(tempKey).substring(0, 32);
      ivStr = keyStr.substring(keyStr.length - 16);
    }
    var hex = bytesToHex(aesCbcEncrypt(utf8Bytes(keyStr), utf8Bytes(ivStr), plain));
    if (opt && opt.key && opt.iv) return hex;
    return { str: hex, key: tempKey };
  }

  function cryptoAesDecrypt(data, key, iv) {
    if (!iv) key = md5(key).substring(0, 32);
    iv = iv || key.substring(key.length - 16);
    var plain = aesCbcDecrypt(utf8Bytes(key), utf8Bytes(iv), typeof data === 'string' ? hexToBytes(data) : data);
    var text = utf8Decode(plain);
    try { return JSON.parse(text); } catch (e) { return text; }
  }

  function utf8Decode(bytes) {
    if (typeof TextDecoder !== 'undefined') return new TextDecoder().decode(bytes);
    var out = '';
    for (var i = 0; i < bytes.length; i++) out += String.fromCharCode(bytes[i]);
    return out;
  }

  /* ---------------- RSA（BigInt 实现，对齐 node:crypto 的两种 padding） ---------------- */

  var RSA_PUBLIC_KEY = '-----BEGIN PUBLIC KEY-----\nMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDIAG7QOELSYoIJvTFJhMpe1s/gbjDJX51HBNnEl5HXqTW6lQ7LC8jr9fWZTwusknp+sVGzwd40MwP6U5yDE27M/X1+UR4tvOGOqp94TJtQ1EPnWGWXngpeIW5GxoQGao1rmYWAu6oi1z9XkChrsUdC6DJE5E221wf/4WLFxwAtRQIDAQAB\n-----END PUBLIC KEY-----';

  function derRead(bytes, pos) {
    var tag = bytes[pos++];
    var len = bytes[pos++];
    if (len & 0x80) {
      var n = len & 0x7f;
      len = 0;
      for (var i = 0; i < n; i++) len = (len << 8) | bytes[pos++];
    }
    return { tag: tag, len: len, start: pos, end: pos + len, next: pos + len };
  }

  function bytesToBigInt(bytes) {
    var v = 0n;
    for (var i = 0; i < bytes.length; i++) v = (v << 8n) | BigInt(bytes[i]);
    return v;
  }

  function bigIntToBytes(value, size) {
    var out = new Uint8Array(size);
    var v = value;
    for (var i = size - 1; i >= 0; i--) {
      out[i] = Number(v & 0xffn);
      v >>= 8n;
    }
    return out;
  }

  function modPow(base, exp, mod) {
    var result = 1n;
    var b = base % mod;
    var e = exp;
    while (e > 0n) {
      if (e & 1n) result = (result * b) % mod;
      b = (b * b) % mod;
      e >>= 1n;
    }
    return result;
  }

  var rsaKeyCache = null;

  function parseRsaPublicKey(pem) {
    if (rsaKeyCache && rsaKeyCache.pem === pem) return rsaKeyCache;
    var der = base64Decode(pem.replace(/-----[^-]+-----/g, ''));
    var outer = derRead(der, 0);
    var p = derRead(der, outer.start);       // AlgorithmIdentifier
    var bitStr = derRead(der, p.next);       // BIT STRING
    var inner = derRead(der, bitStr.start + 1);
    var nInt = derRead(der, inner.start);
    var eInt = derRead(der, nInt.next);
    var key = {
      pem: pem,
      n: bytesToBigInt(der.subarray(nInt.start, nInt.end)),
      e: bytesToBigInt(der.subarray(eInt.start, eInt.end)),
      size: inner.end - inner.start,
    };
    key.bytes = Math.ceil(key.n.toString(2).length / 8);
    rsaKeyCache = key;
    return key;
  }

  /** RSA_NO_PADDING：数据左对齐、右侧补零到密钥长度 */
  function cryptoRSAEncrypt(data, publicKey) {
    var key = parseRsaPublicKey(publicKey || RSA_PUBLIC_KEY);
    var bytes = utf8ToBytes(data);
    if (bytes.length > key.bytes) throw new Error('RSA 明文过长(' + bytes.length + ' > ' + key.bytes + ')');
    var buf = new Uint8Array(key.bytes);
    buf.set(bytes);
    var m = bytesToBigInt(buf);
    if (m >= key.n) throw new Error('RSA 明文超出模数');
    return bytesToHex(bigIntToBytes(modPow(m, key.e, key.n), key.bytes));
  }

  /** RSA_PKCS1_PADDING（加密块类型 2：00 || 02 || 非零填充 || 00 || 明文） */
  function rsaEncrypt2(data, publicKey) {
    var key = parseRsaPublicKey(publicKey || RSA_PUBLIC_KEY);
    var bytes = utf8ToBytes(data);
    if (bytes.length > key.bytes - 11) throw new Error('RSA 明文过长(' + bytes.length + ' > ' + (key.bytes - 11) + ')');
    var buf = new Uint8Array(key.bytes);
    buf[0] = 0x00;
    buf[1] = 0x02;
    var i = 2;
    while (i < key.bytes - bytes.length - 1) buf[i++] = 0xff;
    buf[i++] = 0x00;
    buf.set(bytes, i);
    var m = bytesToBigInt(buf);
    return bytesToHex(bigIntToBytes(modPow(m, key.e, key.n), key.bytes));
  }

  /* ---------------- 酷狗签名 ---------------- */

  var KA = { appid: 1005, clientver: 20489 };

  function signatureWebParams(params) {
    var str = 'NVPh5oo715z5DIWAeQlhMDsWXXQV4hwt';
    var paramsString = Object.keys(params)
      .map(function (key) { return key + '=' + params[key]; })
      .sort()
      .join('');
    return md5(str + paramsString + str);
  }

  function signatureAndroidParams(params, data) {
    var str = 'OIlwieks28dk2k092lksi2UIkp';
    var paramsString = Object.keys(params)
      .sort()
      .map(function (key) {
        var v = params[key];
        return key + '=' + (typeof v === 'object' ? JSON.stringify(v) : v);
      })
      .join('');
    return md5(str + paramsString + (data || '') + str);
  }

  function signatureRegisterParams(params) {
    var paramsString = Object.keys(params)
      .map(function (key) { return params[key]; })
      .sort()
      .join('');
    return md5('1014' + paramsString + '1014');
  }

  function signKey(hash, mid, userid, appid) {
    return md5(String(hash) + '57ae12eb6890223e355ccfcb74edf70d' + (appid || KA.appid) + mid + (userid || 0));
  }

  function signParamsKey(data, appid, clientver) {
    return md5((appid || KA.appid) + 'OIlwieks28dk2k092lksi2UIkp' + (clientver || KA.clientver) + data);
  }


async function gmRequest(opt) {
  if (DRY) throw fault('断网预演禁止网络请求');
  const url = new URL(opt.url);
  if (url.protocol !== 'https:') throw fault('拒绝非 HTTPS 请求');
  return new Promise((resolve,reject) => {
    const headers = Object.fromEntries(Object.entries(opt.headers || {}).filter(([,v])=>v!==undefined && v!==null).map(([k,v])=>[k.toLowerCase(),String(v)]));
    const req = https.request(url, {method: opt.method || 'GET', headers}, res => {
      let bytes=0; const chunks=[];
      res.on('data', chunk => { bytes+=chunk.length; if(bytes>1048576) req.destroy(fault('响应超过大小限制')); else chunks.push(chunk); });
      res.on('end',()=>resolve({status:res.statusCode, headers:res.headers, text:Buffer.concat(chunks).toString('utf8')}));
      res.on('error',()=>reject(fault('响应读取失败')));
    });
    const timer=setTimeout(()=>req.destroy(fault('请求超时')),opt.timeout || 15000);
    req.on('close',()=>clearTimeout(timer));
    req.on('error',e=>reject(e.safeMessage ? e : fault('网络请求失败')));
    if(opt.body!==undefined && opt.body!==null) req.write(opt.body);
    req.end();
  });
}
async function gmRequestWithFallback(opt) {
  // 保留登录域名，强制 TLS；不再回退明文传输凭据。
  return gmRequest({...opt, url:opt.url.replace(/^http:/,'https:')});
}
  function buildUrl(baseURL, url, params) {
    var full = baseURL ? baseURL + url : url;
    if (params) {
      var search = new URLSearchParams();
      Object.keys(params).forEach(function (key) {
        var v = params[key];
        if (v === undefined || v === null) return;
        search.append(key, typeof v === 'object' ? JSON.stringify(v) : String(v));
      });
      var qs = search.toString();
      if (qs) full += (full.indexOf('?') === -1 ? '?' : '&') + qs;
    }
    return full;
  }

  function parseBody(text) {
    if (typeof text !== 'string') return text;
    var t = text.replace(/^\uFEFF/, '');
    if (/^\s*[[{]/.test(t)) {
      try { return JSON.parse(t); } catch (e) { return text; }
    }
    return text;
  }

  /**
   * 对齐原项目 api/util/request.js 的 createRequest：
   * 负责拼默认参数、算 signature、发请求，并把业务失败 reject 成 { status, body }
   */
  async function useAxios(options) {
    var dfid = (options.cookie && options.cookie.dfid) || '-';
    var mid = md5(dfid) + md5(dfid).slice(0, 7);
    var uuid = md5(dfid + mid);
    var token = (options.cookie && options.cookie.token) || '';
    var userid = (options.cookie && options.cookie.userid) || 0;
    var clienttime = Math.floor(Date.now() / 1000);

    var defaultParams = {
      dfid: dfid,
      mid: mid,
      uuid: uuid,
      appid: KA.appid,
      clientver: KA.clientver,
      userid: userid,
      clienttime: clienttime,
    };
    if (token) defaultParams.token = token;

    var params = options.clearDefaultParams
      ? options.params || {}
      : Object.assign({}, defaultParams, options.params || {});

    if (options.encryptKey) {
      params.key = signKey(params.hash, params.mid, params.userid, params.appid);
    }

    var rawData = options.data;
    var dataString = typeof rawData === 'object' && rawData !== null ? JSON.stringify(rawData) : rawData || '';

    if (!params.signature && !options.notSignature) {
      if (options.encryptType === 'register') params.signature = signatureRegisterParams(params);
      else if (options.encryptType === 'web') params.signature = signatureWebParams(params);
      else params.signature = signatureAndroidParams(params, dataString);
    }

    var baseURL = options.baseURL || 'https://gateway.kugou.com';
    var headers = Object.assign(
      { 'User-Agent': 'Android15-1070-11083-46-0-DiscoveryDRADProtocol-wifi' },
      options.headers || {},
      { dfid: dfid, clienttime: params.clienttime, mid: mid }
    );

    var url = buildUrl(baseURL, options.url, params);
    var body = null;
    if (rawData !== undefined && rawData !== null) {
      body = typeof rawData === 'object' ? JSON.stringify(rawData) : String(rawData);
      var hasContentType = Object.keys(headers).some(function (k) { return k.toLowerCase() === 'content-type'; });
      if (!hasContentType) headers['content-type'] = 'application/json';
    }

    var answer = { status: 200, body: {}, cookie: [], headers: {} };

    var res;
    try {
      res = await gmRequestWithFallback({
        url: url,
        method: options.method || 'GET',
        headers: headers,
        body: body,
      });
    } catch (e) {
      answer.status = 502;
      answer.body = { status: 0, msg: e.message };
      throw answer;
    }

    var parsed = parseBody(res.text);
    answer.body = parsed;

    if (res.status < 200 || res.status >= 300) {
      answer.status = res.status;
      answer.body = Object.assign(
        { status: 0, msg: '请求失败', httpStatus: res.status },
        parsed && typeof parsed === 'object' ? parsed : {}
      );
      throw answer;
    }

    if (parsed && typeof parsed === 'object' &&
        (parsed.status === 0 || (parsed.error_code && parsed.error_code !== 0))) {
      answer.status = 502;
      throw answer;
    }

    return answer;
  }

  /* ================================================================== *
   *  3. 酷狗接口（移植自 api/module/*.js，语义保持不变）
   * ================================================================== */

  var MODULES = {
    /* 账号信息（用于校验 token 是否还有效） */
    user_detail: function (params, request) {
      var token = params.token || (params.cookie && params.cookie.token) || '';
      var userid = Number(params.userid || (params.cookie && params.cookie.userid) || '0');
      var clienttimeMs = Math.floor(Date.now() / 1000);
      var pk = cryptoRSAEncrypt({ token: token, clienttime: clienttimeMs }).toUpperCase();
      return request({
        url: '/v3/get_my_info',
        method: 'POST',
        data: { visit_time: clienttimeMs, usertype: 1, p: pk, userid: userid },
        params: { plat: 1 },
        encryptType: 'android',
        cookie: params.cookie || {},
        headers: { 'x-router': 'usercenter.kugou.com' },
      });
    },

    /* 听歌领 VIP */
    youth_listen_song: function (params, request) {
      return request({
        url: '/youth/v2/report/listen_song',
        data: { mixsongid: params.mixsongid || 666075191 },
        method: 'POST',
        encryptType: 'android',
        params: { clientver: 10566 },
        cookie: params.cookie,
        headers: {
          'user-agent': 'Android13-1070-10566-201-0-ReportPlaySongToServerProtocol-wifi',
          'content-type': 'application/json; charset=utf-8',
        },
      });
    },

    /* 看广告领 VIP */
    youth_vip: function (params, request) {
      var time = Date.now();
      return request({
        url: '/youth/v1/ad/play_report',
        encryptType: 'android',
        method: 'post',
        data: { ad_id: 12307537187, play_end: time, play_start: time - 30000 },
        cookie: params.cookie,
      });
    },

    /* VIP 到期时间 */
    user_vip_detail: function (params, request) {
      return request({
        baseURL: 'https://kugouvip.kugou.com',
        url: '/v1/get_union_vip',
        method: 'GET',
        params: { busi_type: 'concept' },
        encryptType: 'android',
        cookie: params.cookie || {},
      });
    },

    /* 刷新 token */
    login_token: function (params, request) {
      var key = '90b8382a1bb4ccdcf063102053fd75b8';
      var iv = 'f063102053fd75b8';
      var dateNow = Date.now();
      var token = params.token || (params.cookie && params.cookie.token) || '';
      var userid = params.userid || (params.cookie && params.cookie.userid) || '0';
      var encrypt = cryptoAesEncrypt({ clienttime: Math.floor(dateNow / 1000), token: token }, { key: key, iv: iv });
      var encryptParams = cryptoAesEncrypt({});
      var pk = cryptoRSAEncrypt({ clienttime_ms: dateNow, key: encryptParams.key });

      return request({
        baseURL: 'http://login.user.kugou.com',
        url: '/v5/login_by_token',
        method: 'POST',
        data: {
          dfid: (params.cookie && params.cookie.dfid) || '-',
          p3: encrypt,
          plat: 1,
          t1: 0,
          t2: 0,
          t3: 'MCwwLDAsMCwwLDAsMCwwLDA=',
          pk: pk,
          params: encryptParams.str,
          userid: userid,
          clienttime_ms: dateNow,
        },
        cookie: params.cookie,
        encryptType: 'android',
        headers: { 'x-router': 'login.user.kugou.com' },
      }).then(function (res) {
        var body = res.body;
        if (body && body.status === 1) {
          if (body.data && body.data.secu_params) {
            var got = cryptoAesDecrypt(body.data.secu_params, encryptParams.key);
            if (typeof got === 'object') res.body.data = Object.assign({}, body.data, got);
            else res.body.data.token = got;
          }
        }
        return res;
      });
    },

    /* 二维码 key */
    login_qr_key: function (params, request) {
      return request({
        baseURL: 'https://login-user.kugou.com',
        url: '/v2/qrcode',
        method: 'GET',
        params: {
          appid: params.type === 'web' ? 1014 : 1001,
          type: 1,
          plat: 4,
          qrcode_txt: 'https://h5.kugou.com/apps/loginQRCode/html/index.html?appid=' + KA.appid + '&',
          srcappid: 2919,
        },
        encryptType: 'web',
        cookie: params.cookie || {},
      });
    },

    /* 二维码状态：0 过期 / 1 待扫 / 2 待确认 / 4 成功 */
    login_qr_check: function (params, request) {
      return request({
        baseURL: 'https://login-user.kugou.com',
        url: '/v2/get_userinfo_qrcode',
        method: 'GET',
        params: { plat: 4, appid: KA.appid, srcappid: 2919, qrcode: params.key },
        encryptType: 'web',
        cookie: params.cookie || {},
      });
    },

    /* 发送短信验证码 */
    captcha_sent: function (params, request) {
      return request({
        baseURL: 'http://login.user.kugou.com',
        url: '/v7/send_mobile_code',
        method: 'POST',
        data: { businessid: 5, mobile: String(params.mobile), plat: 3 },
        encryptType: 'android',
        cookie: {},
      });
    },

    /* 手机号 + 验证码登录 */
    login_cellphone: function (params, request) {
      var dateTime = Date.now();
      var encrypt = cryptoAesEncrypt({ mobile: params.mobile || '', code: params.code || '' });
      var mobile = params.mobile && (String(params.mobile).substring(0, 2) + '*****' + String(params.mobile).substring(10, 11));
      var dataMap = {
        plat: 1,
        support_multi: 1,
        t1: 0,
        t2: 0,
        clienttime_ms: dateTime,
        mobile: mobile,
        key: signParamsKey(dateTime),
        t3: 'MCwwLDAsMCwwLDAsMCwwLDA=',
        params: encrypt.str,
        pk: cryptoRSAEncrypt({ clienttime_ms: dateTime, key: encrypt.key }).toUpperCase(),
      };

      return request({
        url: '/v7/login_by_verifycode',
        method: 'POST',
        data: dataMap,
        encryptType: 'android',
        cookie: params.cookie || {},
        headers: { 'x-router': 'login.user.kugou.com' },
      }).then(function (res) {
        var body = res.body;
        if (body && body.status === 1) {
          if (body.data && body.data.secu_params) {
            var got = cryptoAesDecrypt(body.data.secu_params, encrypt.key);
            if (typeof got === 'object') res.body.data = Object.assign({}, body.data, got);
            else res.body.data.token = got;
          }
        }
        return res;
      });
    },
  };

  async function callApi(name, params) {
    var mod = MODULES[name];
    if (!mod) throw new Error('未知接口：' + name);
    try {
      var res = await mod(params || {}, useAxios);
      return (res && res.body) || {};
    } catch (e) {
      // 业务失败时 request 会 reject 成 { status, body }，这里把 body 交回给调用方判断
      if (e && e.body) return e.body;
      throw e;
    }
  }

  function cookieOf(user) {
    return { token: String(user.token || ''), userid: String(user.userid || '') };
  }

  var QR_SPEC_M = {
    1: [1, 26, 16],
    2: [1, 44, 28],
    3: [1, 70, 44],
    4: [2, 50, 32],
    5: [2, 67, 43],
    6: [4, 43, 27],
    7: [4, 49, 31],
    8: [2, 60, 38, 2, 61, 39],
    9: [3, 58, 36, 2, 59, 37],
    10: [4, 69, 43, 1, 70, 44],
  };
  var QR_ALIGN_M = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 50],
  };

  (function verifyQrTables() {
    var totals = { 1: 26, 2: 44, 3: 70, 4: 100, 5: 134, 6: 172, 7: 196, 8: 242, 9: 292, 10: 346 };
    Object.keys(QR_SPEC_M).forEach(function (v) {
      var spec = QR_SPEC_M[v];
      var blocks = 0;
      var data = 0;
      for (var i = 0; i < spec.length; i += 3) {
        blocks += spec[i];
        data += spec[i] * spec[i + 2];
      }
      var ecPerBlock = spec[1] - spec[2];
      if (data + blocks * ecPerBlock !== totals[v]) {
        throw new Error('二维码版本表自检失败：version ' + v);
      }
    });
  })();

  function rsGenPoly(n) {
    var poly = [1];
    for (var i = 0; i < n; i++) {
      var next = new Array(poly.length + 1).fill(0);
      for (var a = 0; a < poly.length; a++) {
        next[a] ^= poly[a];
        next[a + 1] ^= gfMul(poly[a], QR_GF.exp[i]);
      }
      poly = next;
    }
    return poly;
  }

  function rsEncode(data, ecLen) {
    var gen = rsGenPoly(ecLen);
    var res = data.concat(new Array(ecLen).fill(0));
    for (var i = 0; i < data.length; i++) {
      var coef = res[i];
      if (coef !== 0) {
        for (var j = 1; j < gen.length; j++) res[i + j] ^= gfMul(gen[j], coef);
      }
    }
    return res.slice(data.length);
  }

  function qrCharCountBits(version) {
    return version < 10 ? 8 : 16;
  }

  function qrDataCodewords(version) {
    var spec = QR_SPEC_M[version];
    var total = 0;
    for (var i = 0; i < spec.length; i += 3) total += spec[i] * spec[i + 2];
    return total;
  }

  function qrBuildCodewords(bytes, version) {
    var buffer = [];
    function put(value, length) {
      for (var i = length - 1; i >= 0; i--) buffer.push((value >>> i) & 1);
    }

    put(4, 4); // 模式指示符：0100 = 8bit 字节模式
    put(bytes.length, qrCharCountBits(version));
    for (var i = 0; i < bytes.length; i++) put(bytes[i], 8);

    var capacityBits = qrDataCodewords(version) * 8;
    if (buffer.length > capacityBits) throw new Error('二维码数据超长');

    if (buffer.length + 4 <= capacityBits) put(0, 4);
    while (buffer.length % 8 !== 0) buffer.push(0);
    while (buffer.length < capacityBits) {
      put(0xec, 8);
      if (buffer.length >= capacityBits) break;
      put(0x11, 8);
    }

    var codewords = [];
    for (var b = 0; b < buffer.length; b += 8) {
      var value = 0;
      for (var k = 0; k < 8; k++) value = (value << 1) | buffer[b + k];
      codewords.push(value);
    }

    // 分块 + 纠错 + 交织
    var spec = QR_SPEC_M[version];
    var blocks = [];
    for (var g = 0; g < spec.length; g += 3) {
      for (var c = 0; c < spec[g]; c++) blocks.push(spec[g + 2]);
    }
    var ecLen = spec[1] - spec[2];
    var dcData = [];
    var ecData = [];
    var offset = 0;
    var maxDc = 0;
    for (var bi = 0; bi < blocks.length; bi++) {
      var dc = codewords.slice(offset, offset + blocks[bi]);
      offset += blocks[bi];
      dcData.push(dc);
      ecData.push(rsEncode(dc, ecLen));
      maxDc = Math.max(maxDc, dc.length);
    }

    var out = [];
    for (var di = 0; di < maxDc; di++) {
      for (var r = 0; r < blocks.length; r++) {
        if (di < dcData[r].length) out.push(dcData[r][di]);
      }
    }
    for (var ei = 0; ei < ecLen; ei++) {
      for (var r2 = 0; r2 < blocks.length; r2++) out.push(ecData[r2][ei]);
    }
    return out;
  }

  function qrBch(data, poly, bits) {
    function digit(value) {
      var n = 0;
      while (value !== 0) { n++; value >>>= 1; }
      return n;
    }
    var d = data << bits;
    while (digit(d) - digit(poly) >= 0) d ^= poly << (digit(d) - digit(poly));
    return d;
  }

  function qrFormatBits(mask) {
    var data = (0 << 3) | mask; // 纠错等级 M 对应 00
    var bits = ((data << 10) | qrBch(data, 0x537, 10)) ^ 0x5412;
    return bits;
  }

  function qrVersionBits(version) {
    return (version << 12) | qrBch(version, 0x1f25, 12);
  }

  function qrMaskFn(pattern, i, j) {
    switch (pattern) {
      case 0: return (i + j) % 2 === 0;
      case 1: return i % 2 === 0;
      case 2: return j % 3 === 0;
      case 3: return (i + j) % 3 === 0;
      case 4: return (Math.floor(i / 2) + Math.floor(j / 3)) % 2 === 0;
      case 5: return ((i * j) % 2) + ((i * j) % 3) === 0;
      case 6: return (((i * j) % 2) + ((i * j) % 3)) % 2 === 0;
      default: return (((i * j) % 3) + ((i + j) % 2)) % 2 === 0;
    }
  }

  function qrMatrix(version, codewords, mask) {
    var size = version * 4 + 17;
    var modules = [];
    for (var r = 0; r < size; r++) modules.push(new Array(size).fill(null));

    function setProbe(row, col) {
      for (var dr = -1; dr <= 7; dr++) {
        if (row + dr < 0 || row + dr >= size) continue;
        for (var dc = -1; dc <= 7; dc++) {
          if (col + dc < 0 || col + dc >= size) continue;
          var inRing = (dr >= 0 && dr <= 6 && (dc === 0 || dc === 6)) ||
                       (dc >= 0 && dc <= 6 && (dr === 0 || dr === 6)) ||
                       (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4);
          modules[row + dr][col + dc] = inRing;
        }
      }
    }
    setProbe(0, 0);
    setProbe(size - 7, 0);
    setProbe(0, size - 7);

    var align = QR_ALIGN_M[version];
    for (var a = 0; a < align.length; a++) {
      for (var b = 0; b < align.length; b++) {
        var ar = align[a];
        var ac = align[b];
        if (modules[ar][ac] !== null) continue;
        for (var r2 = -2; r2 <= 2; r2++) {
          for (var c2 = -2; c2 <= 2; c2++) {
            modules[ar + r2][ac + c2] = (r2 === -2 || r2 === 2 || c2 === -2 || c2 === 2 || (r2 === 0 && c2 === 0));
          }
        }
      }
    }

    for (var t = 8; t < size - 8; t++) {
      if (modules[t][6] === null) modules[t][6] = (t % 2 === 0);
      if (modules[6][t] === null) modules[6][t] = (t % 2 === 0);
    }

    // 格式信息占位（先写死值，mask 阶段会重写；这里只为占位，避免被数据覆盖）
    var bits = qrFormatBits(mask);
    for (var i = 0; i < 15; i++) {
      var mod = ((bits >> i) & 1) === 1;
      if (i < 6) modules[i][8] = mod;
      else if (i < 8) modules[i + 1][8] = mod;
      else modules[size - 15 + i][8] = mod;

      if (i < 8) modules[8][size - i - 1] = mod;
      else if (i < 9) modules[8][15 - i] = mod;
      else modules[8][15 - i - 1] = mod;
    }
    modules[size - 8][8] = true;

    if (version >= 7) {
      var vBits = qrVersionBits(version);
      for (var v = 0; v < 18; v++) {
        var vMod = ((vBits >> v) & 1) === 1;
        modules[Math.floor(v / 3)][(v % 3) + size - 11] = vMod;
        modules[(v % 3) + size - 11][Math.floor(v / 3)] = vMod;
      }
    }

    var bitIndex = 7;
    var byteIndex = 0;
    var inc = -1;
    var row = size - 1;
    for (var col = size - 1; col > 0; col -= 2) {
      if (col === 6) col--;
      while (true) {
        for (var cc = 0; cc < 2; cc++) {
          var target = col - cc;
          if (modules[row][target] === null) {
            var dark = false;
            if (byteIndex < codewords.length) dark = ((codewords[byteIndex] >>> bitIndex) & 1) === 1;
            if (qrMaskFn(mask, row, target)) dark = !dark;
            modules[row][target] = dark;
            bitIndex--;
            if (bitIndex === -1) { byteIndex++; bitIndex = 7; }
          }
        }
        row += inc;
        if (row < 0 || row >= size) { row -= inc; inc = -inc; break; }
      }
    }

    return modules;
  }

  function qrPenalty(modules) {
    var size = modules.length;
    var penalty = 0;

    // 规则 1：行/列中连续 5 个以上同色
    var container = new Array(size + 1).fill(0);
    for (var r = 0; r < size; r++) {
      var prev = modules[r][0];
      var len = 0;
      for (var c = 0; c < size; c++) {
        if (modules[r][c] === prev) len++;
        else { if (len >= 5) container[len]++; len = 1; prev = modules[r][c]; }
      }
      if (len >= 5) container[len]++;
    }
    for (var col = 0; col < size; col++) {
      var prevC = modules[0][col];
      var lenC = 0;
      for (var row = 0; row < size; row++) {
        if (modules[row][col] === prevC) lenC++;
        else { if (lenC >= 5) container[lenC]++; lenC = 1; prevC = modules[row][col]; }
      }
      if (lenC >= 5) container[lenC]++;
    }
    for (var n = 5; n <= size; n++) penalty += container[n] * (n - 2);

    // 规则 2：2x2 同色方块
    for (var r2 = 0; r2 < size - 1; r2++) {
      for (var c2 = 0; c2 < size - 1; c2++) {
        var v = modules[r2][c2];
        if (v === modules[r2][c2 + 1] && v === modules[r2 + 1][c2] && v === modules[r2 + 1][c2 + 1]) penalty += 3;
      }
    }

    // 规则 3：1:1:3:1:1 的类定位图案
    var pat = [true, false, true, true, true, false, true, false, false, false, false];
    var patRev = [false, false, false, false, true, false, true, true, true, false, true];
    function matchRow(rr, start, pattern) {
      for (var k = 0; k < 11; k++) if (modules[rr][start + k] !== pattern[k]) return false;
      return true;
    }
    function matchCol(cc, start, pattern) {
      for (var k = 0; k < 11; k++) if (modules[start + k][cc] !== pattern[k]) return false;
      return true;
    }
    for (var r3 = 0; r3 < size; r3++) {
      for (var c3 = 0; c3 + 11 <= size; c3++) {
        if (matchRow(r3, c3, pat) || matchRow(r3, c3, patRev)) penalty += 40;
      }
    }
    for (var c4 = 0; c4 < size; c4++) {
      for (var r4 = 0; r4 + 11 <= size; r4++) {
        if (matchCol(c4, r4, pat) || matchCol(c4, r4, patRev)) penalty += 40;
      }
    }

    // 规则 4：黑白比例偏离 50%
    var darkCount = 0;
    for (var r5 = 0; r5 < size; r5++) {
      for (var c5 = 0; c5 < size; c5++) if (modules[r5][c5]) darkCount++;
    }
    var ratio = (darkCount * 100) / (size * size);
    penalty += Math.floor(Math.abs(ratio - 50) / 5) * 10;

    return penalty;
  }

  /** 生成二维码矩阵（版本按长度自动选择，纠错等级 M） */
  function qrEncode(text, forcedVersion, forcedMask) {
    var bytes = utf8Bytes(String(text));
    var version = forcedVersion || 0;
    if (!version) {
      for (var v = 1; v <= 10; v++) {
        var needBits = 4 + qrCharCountBits(v) + bytes.length * 8;
        if (needBits <= qrDataCodewords(v) * 8) { version = v; break; }
      }
    }
    if (!version) throw new Error('二维码内容过长，超出支持范围');

    var codewords = qrBuildCodewords(bytes, version);

    if (forcedMask !== undefined && forcedMask !== null) {
      return { version: version, mask: forcedMask, modules: qrMatrix(version, codewords, forcedMask) };
    }

    var bestMask = 0;
    var bestPenalty = Infinity;
    var bestModules = null;
    for (var m = 0; m < 8; m++) {
      var mods = qrMatrix(version, codewords, m);
      var p = qrPenalty(mods);
      if (p < bestPenalty) { bestPenalty = p; bestMask = m; bestModules = mods; }
    }
    return { version: version, mask: bestMask, penalty: bestPenalty, modules: bestModules };
  }

  /** 渲染成半块字符二维码（终端 / 日志里可直接扫） */
  function qrToText(matrix, quiet) {
    var n = matrix.length;
    var q = quiet === undefined ? 2 : quiet;
    var size = n + q * 2;
    function get(r, c) {
      if (r < q || c < q || r >= q + n || c >= q + n) return false;
      return matrix[r - q][c - q];
    }
    var lines = [];
    for (var r = 0; r < size; r += 2) {
      var line = '';
      for (var c = 0; c < size; c++) {
        var top = get(r, c);
        var bottom = r + 1 < size ? get(r + 1, c) : false;
        line += top && bottom ? '\u2588' : top ? '\u2580' : bottom ? '\u2584' : ' ';
      }
      lines.push(line);
    }
    return lines.join('\n');
  }

  var DEFAULT_CONFIG = {
    '账号.USERINFO': '[]',
    '账号.KG_APPEND': true,
    '登录.KG_PHONE': '',
    '登录.KG_CODE': '',
    '登录.KG_QR_SECONDS': 150,
    '登录.KG_QR_ONLINE': false,
    '签到.KG_CLAIM_TIMES': 8,
    '签到.KG_CLAIM_INTERVAL': 30,
    '签到.KG_REFRESH_WEEKDAY': -1,
    '签到.KG_RANDOM_DELAY_MIN': 1,
    '签到.KG_RANDOM_DELAY_MAX': 60,
    '通知.KG_NOTIFY_SYSTEM': true,
    '通知.WECOM_BOT_KEY': '',
    '通知.DINGTALK_BOT_KEY': '',
    '通知.DINGTALK_SECRET': '',
    '通知.FEISHU_BOT_KEY': '',
    '通知.YUNHU_BOT_TOKEN': '',
    '通知.YUNHU_RECV_ID': '',
    '通知.YUNHU_RECV_TYPE': 'user',
    '通知.SERVERCHAN_SENDKEY': '',
    '通知.PUSHPLUS_TOKEN': '',
    '通知.PUSHPLUS_TOPIC': '',
    '通知.TG_BOT_TOKEN': '',
    '通知.TG_CHAT_ID': '',
    '通知.BARK_KEY': '',
    '通知.BARK_GROUP': '',
    '通知.DISCORD_WEBHOOK': '',
  };


function cfg(key) { const name=key.split('.').pop(); return process.env[name] === undefined ? DEFAULT_CONFIG[key] : process.env[name]; }
function cfgStr(key) { return String(cfg(key) ?? ''); }
function cfgBool(key) { return /^(1|true|yes|on|是)$/i.test(cfgStr(key)); }
function cfgInt(key, fallback) {
 const raw=cfgStr(key); const n=raw==='' ? fallback : Number(raw);
 if(!Number.isFinite(n) || !Number.isInteger(n)) throw fault('整数参数格式错误'); return n;
}
function numberEnv(name, def, min, max) {
 const n=Number(process.env[name] ?? def);
 if(!Number.isInteger(n) || n<min || n>max) throw fault(name+' 超出范围'); return n;
}
function parseAccounts(raw) {
 if(!raw.trim()) return [];
 if(raw.trim().startsWith('[')) { let x; try{x=JSON.parse(raw);}catch{throw fault('USERINFO JSON 格式错误');} if(!Array.isArray(x)) throw fault('账号配置须为数组'); return x; }
 return raw.split(/\r?\n/).filter(x=>x.trim()).map(line=>{
  if(line.trim().startsWith('{')) { try{return JSON.parse(line);}catch{return {invalid:true};} }
  const at=line.indexOf('#'); return at<1 ? {invalid:true} : {userid:line.slice(0,at).trim(),token:line.slice(at+1)};
 });
}
let users=[], sourceHash='';
function accountFile() { if(!process.env.KG_ACCOUNT_FILE) throw fault('此操作必须显式设置 KG_ACCOUNT_FILE'); return path.resolve(process.env.KG_ACCOUNT_FILE); }
function saveAccounts() {
 const file=accountFile(); const temp=file+'.'+process.pid+'.tmp';
 try { fs.writeFileSync(temp,JSON.stringify({sourceHash,users}),{mode:0o600,flag:'wx'}); fs.renameSync(temp,file); fs.chmodSync(file,0o600); }
 catch { try{fs.unlinkSync(temp);}catch{} throw fault('账号文件保存失败'); }
}
function loadAccounts() {
 const raw=process.env.KG_ACCOUNTS || process.env.USERINFO || '';
 sourceHash=crypto.createHash('sha256').update(raw).digest('hex');
 users=parseAccounts(raw);
 if(!DRY && process.env.KG_ACCOUNT_FILE && fs.existsSync(accountFile())) {
  let saved; try{saved=JSON.parse(fs.readFileSync(accountFile(),'utf8'));}catch{throw fault('账号文件读取失败');}
  if(!Array.isArray(saved.users)) throw fault('账号文件结构错误');
  if(!raw || saved.sourceHash===sourceHash) users=saved.users;
 }
 return users;
}
function validUser(u) { return u && /^\d+$/.test(String(u.userid || '')) && typeof u.token==='string' && u.token.trim()!=='' && !/[\r\n]/.test(u.token); }
  async function postJson(url, body, headers) {
    var res = await gmRequestWithFallback({
      url: url,
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, headers || {}),
      body: JSON.stringify(body),
      timeout: 15000,
    });
    if(res.status < 200 || res.status >= 300) throw fault('通知 HTTP 失败');
    return res;
  }

  async function postForm(url, form) {
    return gmRequestWithFallback({
      url: url,
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(form).toString(),
      timeout: 15000,
    });
  }

  /**
   * 收集所有已配置的通知渠道。
   *
   * 注意：每个渠道 key 必须用各自独立的变量名。
   * 这些闭包是延迟执行的（sendNotify 里统一 Promise.all），
   * 如果共用一个 var，回调跑的时候读到的会是最后一个值。
   */
  function notifyChannels(title, content) {
    var list = [];

    var wecomKey = cfgStr('通知.WECOM_BOT_KEY');
    if (wecomKey) list.push(['企业微信', async function () {
      var res = await postJson('https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=' + encodeURIComponent(wecomKey), {
        msgtype: 'text', text: { content: title + '\n\n' + content },
      });
      var data = parseBody(res.text) || {};
      if (data.errcode !== 0) throw new Error(data.errmsg || 'errcode=' + data.errcode);
    }]);

    var dingtalkKey = cfgStr('通知.DINGTALK_BOT_KEY');
    var dingtalkSecret = cfgStr('通知.DINGTALK_SECRET');
    if (dingtalkKey) list.push(['钉钉', async function () {
      var url = 'https://oapi.dingtalk.com/robot/send?access_token=' + encodeURIComponent(dingtalkKey);
      if (dingtalkSecret) {
        var timestamp = Date.now();
        var sign = hmacSha256Base64(dingtalkSecret, timestamp + '\n' + dingtalkSecret);
        url += '&timestamp=' + timestamp + '&sign=' + encodeURIComponent(sign);
      }
      var res = await postJson(url, { msgtype: 'markdown', markdown: { title: title, text: '### ' + title + '\n\n' + content } });
      var data = parseBody(res.text) || {};
      if (data.errcode !== 0) throw new Error(data.errmsg || 'errcode=' + data.errcode);
    }]);

    var feishuKey = cfgStr('通知.FEISHU_BOT_KEY');
    if (feishuKey) list.push(['飞书', async function () {
      var res = await postJson('https://open.feishu.cn/open-apis/bot/v2/hook/' + encodeURIComponent(feishuKey), {
        msg_type: 'text', content: { text: title + '\n\n' + content },
      });
      var data = parseBody(res.text) || {};
      if (data.code !== undefined && data.code !== 0) throw new Error(data.msg || 'code=' + data.code);
    }]);

    var yunhuToken = cfgStr('通知.YUNHU_BOT_TOKEN');
    if (yunhuToken) list.push(['云湖', async function () {
      var recvId = cfgStr('通知.YUNHU_RECV_ID');
      if (!recvId) throw new Error('未填写接收方 ID');
      var recvType = cfgStr('通知.YUNHU_RECV_TYPE') || 'user';
      if (recvType !== 'user' && recvType !== 'group') recvType = 'user';
      var res = await postJson('https://chat-go.jwzhd.com/open-apis/v1/bot/send?token=' + encodeURIComponent(yunhuToken), {
        recvId: String(recvId),
        recvType: recvType,
        contentType: 'text',
        content: { text: title + '\n\n' + content },
      });
      var data = parseBody(res.text) || {};
      if (res.status >= 400) throw new Error('HTTP ' + res.status);
      // 云湖成功时返回 {"code":1,"msg":"success"}，这里的 1 是成功而不是错误码，
      // 不能再按「code !== 0 即失败」判断，否则成功也会被记成失败。
      if (data.code !== undefined && data.code !== 1 && data.code !== 0) {
        throw new Error(data.msg || 'code=' + data.code);
      }
    }]);

    var serverchanKey = cfgStr('通知.SERVERCHAN_SENDKEY');
    if (serverchanKey) list.push(['Server酱', async function () {
      var res = await postForm('https://sctapi.ftqq.com/' + encodeURIComponent(serverchanKey) + '.send', { title: title, desp: content });
      if (res.status >= 400) throw new Error('HTTP ' + res.status);
    }]);

    var pushplusToken = cfgStr('通知.PUSHPLUS_TOKEN');
    var pushplusTopic = cfgStr('通知.PUSHPLUS_TOPIC');
    if (pushplusToken) list.push(['PushPlus', async function () {
      var body = { token: pushplusToken, title: title, content: content, template: 'txt' };
      if (pushplusTopic) body.topic = pushplusTopic;
      var res = await postJson('https://www.pushplus.plus/send', body);
      var data = parseBody(res.text) || {};
      if (data.code !== undefined && data.code !== 200) throw new Error(data.msg || 'code=' + data.code);
    }]);

    var tgToken = cfgStr('通知.TG_BOT_TOKEN');
    var tgChat = cfgStr('通知.TG_CHAT_ID');
    if (tgToken && tgChat) list.push(['Telegram', async function () {
      var res = await postJson('https://api.telegram.org/bot' + tgToken + '/sendMessage', {
        chat_id: tgChat, text: '*' + title + '*\n\n' + content, parse_mode: 'Markdown',
      });
      var data = parseBody(res.text) || {};
      if (!data.ok) throw new Error(data.description || 'Telegram 返回失败');
    }]);

    var barkKey = cfgStr('通知.BARK_KEY');
    var barkGroup = cfgStr('通知.BARK_GROUP');
    if (barkKey) list.push(['Bark', async function () {
      var base = barkKey.indexOf('http') === 0 ? barkKey : 'https://api.day.app/' + barkKey;
      var url = base.replace(/\/$/, '') + '/' + encodeURIComponent(title) + '/' + encodeURIComponent(content);
      if (barkGroup) url += '?group=' + encodeURIComponent(barkGroup);
      var res = await gmRequestWithFallback({ url: url, method: 'GET', timeout: 15000 });
      if (res.status >= 400) throw new Error('HTTP ' + res.status);
    }]);

    var discordWebhook = cfgStr('通知.DISCORD_WEBHOOK');
    if (discordWebhook) list.push(['Discord', async function () {
      var res = await postJson(discordWebhook, { content: ('**' + title + '**\n\n' + content).slice(0, 2000) });
      if (res.status >= 400) throw new Error('HTTP ' + res.status);
    }]);

    return list;
  }


const totals={total:0,success:0,alreadyComplete:0,skipped:0,failed:0};
const accountResults=[];
async function stage(stats, number, name, fn) {
 const at=Date.now(); stats.total++; log(`阶段 ${number}：${name} 开始`);
 try { const state=await fn() || 'success'; stats[state]++; log(`${state==='alreadyComplete'?'☑️':state==='skipped'?'⏭️':'✅'} 阶段 ${number}：${name} ${state}，耗时 ${Date.now()-at}ms`); return true; }
 catch(e) { stats.failed++; log(`❌ 阶段 ${number}：${name} 失败：${safeError(e)}，耗时 ${Date.now()-at}ms`); return false; }
}
function statsNew() { return {total:0,success:0,alreadyComplete:0,skipped:0,failed:0}; }
function checkResponse(r, label, already) {
 // 日限额是明确的已完成状态；不能把任意返回对象当成成功。
 if(r && already && Number(r.error_code)===already) return 'alreadyComplete';
 if(!r || r.status!==1 || (r.error_code && Number(r.error_code)!==0)) throw fault(label+'未获业务成功确认');
 return 'success';
}
async function signAccount(user,index,settings) {
 const at=Date.now(), stats=statsNew(); let authenticated=false;
 log(`========== 账号 ${index} ==========`);
 await stage(stats,1,'账号验证',async()=>{
  if(!validUser(user)) throw fault('账号格式错误：需要 userid#token');
  if(DRY) {log('断网预演：账号格式通过，不验证凭据有效性'); authenticated=true; return 'skipped';}
  const r=await callApi('user_detail',{cookie:cookieOf(user)}); checkResponse(r,'账号验证');
  if(!r.data || r.data.nickname===undefined || r.data.nickname===null) throw fault('账号验证缺少身份字段');
  log('官方昵称：'+String(r.data.nickname)); authenticated=true;
 });
 if(authenticated) {
  const cookie=cookieOf(user);
  await stage(stats,2,'令牌续期',async()=>{
   const day=Number(new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Shanghai',weekday:'short'}).format(new Date()).replace(/Sun|Mon|Tue|Wed|Thu|Fri|Sat/g, x=>({Sun:0,Mon:1,Tue:2,Wed:3,Thu:4,Fri:5,Sat:6})[x]));
   if(settings.refresh<0 || day!==settings.refresh) return 'skipped';
   if(!process.env.KG_ACCOUNT_FILE) throw fault('续期须设置 KG_ACCOUNT_FILE 以保存新令牌');
   if(DRY) return 'skipped';
   const r=await callApi('login_token',{cookie,token:user.token,userid:user.userid}); checkResponse(r,'令牌续期');
   if(!r.data || typeof r.data.token!=='string' || !r.data.token) throw fault('续期响应缺少令牌');
   user.token=r.data.token; cookie.token=user.token; saveAccounts();
  });
  await stage(stats,3,'听歌领 VIP',async()=>{
   if(!settings.tasks.includes('listen') || DRY) return 'skipped';
   return checkResponse(await callApi('youth_listen_song',{cookie}),'听歌领取',130012);
  });
  await stage(stats,4,'广告领 VIP',async()=>{
   if(!settings.tasks.includes('ad') || DRY) return 'skipped';
   for(let i=1;i<=settings.times;i++) {
    const state=checkResponse(await callApi('youth_vip',{cookie}),'广告领取',30002);
    log(`广告领取 ${i}/${settings.times}：${state==='alreadyComplete'?'今日已达上限':'业务成功'}`);
    if(state==='alreadyComplete') return i===1 ? state : 'success';
    if(i<settings.times) await delay(settings.interval*1000);
   }
  });
  await stage(stats,5,'VIP 到期查询',async()=>{
   if(!settings.tasks.includes('vip') || DRY) return 'skipped';
   const r=await callApi('user_vip_detail',{cookie}); checkResponse(r,'VIP 查询');
   if(!r.data || !Array.isArray(r.data.busi_vip) || !r.data.busi_vip.length || r.data.busi_vip[0].vip_end_time===undefined) throw fault('VIP 响应缺少到期字段');
   const expiry=r.data.busi_vip[0].vip_end_time;
   if(!/^[\d\s/:T.+-]{1,40}$/.test(String(expiry))) throw fault('VIP 到期字段格式异常');
   log('VIP 到期时间：'+expiry);
  });
 }
 const result={account:index,status:stats.failed?'failure':DRY?'dry-run':'success',...stats,durationMs:Date.now()-at};
 accountResults.push(result);
 for(const key of Object.keys(totals)) totals[key]+=stats[key];
 log(`账号 ${index} 统计：总任务 ${stats.total}，成功 ${stats.success}，已完成 ${stats.alreadyComplete}，跳过 ${stats.skipped}，失败 ${stats.failed}，耗时 ${result.durationMs}ms`);
}
function loginFields() { const raw=process.env.KG_LOGIN_ACCOUNT || ''; const at=raw.indexOf('#'); return raw ? {phone:at<0?raw:raw.slice(0,at),code:at<0?'':raw.slice(at+1)} : {phone:process.env.KG_PHONE || '',code:process.env.KG_CODE || ''}; }
function requirePhone() { const phone=loginFields().phone; if(!/^1\d{10}$/.test(phone)) throw fault('KG_PHONE 须为有效格式的 11 位手机号'); return phone; }
async function loginAction(action) {
 if(action==='list') {log(`当前账号数量：${users.length}；不显示凭据`); return;}
 if(action==='clear') {accountFile(); if(!DRY) {users=[];saveAccounts();} log('显式账号文件清空'+(DRY?'预演':'完成')+'；青龙环境变量不变');return;}
 if(action==='sms') {
  const phone=requirePhone(); if(DRY) {log('短信发送断网预演');return;}
  checkResponse(await callApi('captcha_sent',{mobile:phone}),'短信发送'); log('短信发送成功'); return;
 }
 accountFile();
 if(action==='qr' && !process.env.KG_QR_FILE) throw fault('扫码登录须设置 KG_QR_FILE 保存本地二维码 SVG');
 if(action==='phone') { requirePhone(); if(!/^\d{4,8}$/.test(loginFields().code)) throw fault('KG_CODE 须为短信验证码'); }
 if(DRY) {log('登录断网预演：不会请求、生成二维码或写入凭据');return;}
 let data;
 if(action==='phone') {
  const r=await callApi('login_cellphone',{mobile:requirePhone(),code:loginFields().code}); checkResponse(r,'短信登录'); data=r.data;
 } else {
  const r=await callApi('login_qr_key',{cookie:{}}); checkResponse(r,'二维码获取');
  if(!r.data || !r.data.qrcode) throw fault('二维码响应字段缺失');
  const url='https://h5.kugou.com/apps/loginQRCode/html/index.html?qrcode='+encodeURIComponent(r.data.qrcode);
  const qr=qrEncode(url), size=qr.modules.length+8;
  let svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}"><rect width="100%" height="100%" fill="white"/>`;
  qr.modules.forEach((row,y)=>row.forEach((v,x)=>{if(v) svg+=`<rect x="${x+4}" y="${y+4}" width="1" height="1"/>`;}));
  svg+='</svg>';
  const file=path.resolve(process.env.KG_QR_FILE);
  if(file===accountFile()) throw fault('二维码文件与账号文件不能相同');
  let created=false;
  try {
   fs.writeFileSync(file,svg,{mode:0o600,flag:'wx'});
   created=true;
   log('本地二维码已保存，请在所配置文件中查看并用酷狗 APP 扫描；登录链接不输出');
   const deadline=Date.now()+numberEnv('KG_QR_SECONDS',150,10,600)*1000;
   while(Date.now()<deadline) {
    const response=await callApi('login_qr_check',{cookie:{},key:r.data.qrcode}); checkResponse(response,'二维码状态查询');
    if(!response.data) throw fault('二维码状态响应缺失');
    if(response.data.status===4) {data=response.data;break;}
    if(response.data.status===0) throw fault('二维码已过期');
    await delay(3000);
   }
   if(!data) throw fault('扫码登录等待超时');
  } finally { if(created) try{fs.unlinkSync(file);}catch{} }
 }
 if(!validUser(data)) throw fault('登录响应缺少有效 userid 或 token');
 if(data.nickname!==undefined) log('官方昵称：'+String(data.nickname));
 if(!cfgBool('账号.KG_APPEND')) users=[];
 const index=users.findIndex(u=>String(u.userid)===String(data.userid));
 const user={userid:String(data.userid),token:data.token};
 if(index>=0) users[index]=user; else users.push(user);
 saveAccounts(); log('登录成功，凭据已保存到显式账号文件');
}
function notificationSelected() {
 const sw=(process.env.QINGLONG_NOTIFY || 'auto').toLowerCase();
 if(['0','false','no','off'].includes(sw)) return false;
 if(['1','true','yes','on'].includes(sw)) return true;
 if(process.env.QINGLONG_NOTIFY_SCRIPTS===undefined) return true;
 const names=['59cfee057c900f01','candidate.js',path.basename(__filename),'scripts/'+path.basename(__filename)];
 return process.env.QINGLONG_NOTIFY_SCRIPTS.split(/[,;\s]+/).filter(Boolean).some(pattern=>{
  const re=new RegExp('^'+pattern.split('*').map(x=>x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('.*')+'$');
  return names.some(n=>re.test(n));
 });
}
async function notifySummary(summary) {
 if(!notificationSelected()) {log('通知：全局开关或选择列表已关闭');return 'disabled';}
 const title='酷狗概念版 VIP 签到';
 const body=`状态：${summary.status}\n账号总数：${summary.accounts}，成功：${summary.succeeded}，失败：${summary.failed}\n子任务：成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`;
 if(DRY) {log('通知：断网预演，脱敏摘要已生成；不加载通知模块或发送网络请求');return 'dry-run';}
 let ok=0,failed=0;
 if(cfgBool('通知.KG_NOTIFY_SYSTEM')) {
  const paths=[process.env.QINGLONG_NOTIFY_DIR && path.join(process.env.QINGLONG_NOTIFY_DIR,'sendNotify.js'),'/ql/data/scripts/sendNotify.js','/ql/scripts/sendNotify.js'].filter(Boolean);
  const helper=paths.find(f=>fs.existsSync(f));
  if(helper) {
   const delivered=await new Promise(resolve=>execFile(process.execPath,['-e',"Promise.resolve().then(()=>require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(()=>process.exit(0),()=>process.exit(1))",helper,title,body],{timeout:20000,maxBuffer:32768},err=>resolve(!err)));
   if(delivered) ok++; else failed++;
  } else {failed++;log('通知：青龙 sendNotify.js 不可用，保留业务退出码');}
 }
 for(const [name,send] of notifyChannels(title,body)) {
  try {await send();ok++;log('通知：'+name+'发送完成');}catch {failed++;log('通知：'+name+'发送失败（响应已隐藏）');}
 }
 return failed ? ok?'partial-failure':'unavailable' : ok?'success':'unconfigured';
}
async function main() {
 let status='configuration-error',configError=false;
 log('========== 酷狗概念版 VIP 签到 ==========');
 log('开始时间：'+new Date().toISOString());log('运行模式：'+(DRY?'断网预演':'正式运行'));
 try {
  // 显式处理曾导致导入失败的契约变量；禁止登录凭据流向二维码第三方。
  if(cfgBool('登录.KG_QR_ONLINE')) throw fault('KG_QR_ONLINE 必须关闭：禁止向第三方外发登录链接');
  loadAccounts();
  const action=process.env.KG_ACTION || 'sign';
  if(!['sign','now','qr','sms','phone','list','clear'].includes(action)) throw fault('KG_ACTION 无效');
  log('账号数量：'+users.length);
  if(action==='sign' || action==='now') {
   if(!users.length) throw fault('未配置账号，请设置 KG_ACCOUNTS 或兼容 USERINFO');
   const tasks=(process.env.KG_TASKS || 'vip').split(',').map(x=>x.trim());
   if(!tasks.length || tasks.some(t=>!['listen','ad','vip'].includes(t))) throw fault('KG_TASKS 仅支持 listen,ad,vip');
   const settings={tasks,times:numberEnv('KG_CLAIM_TIMES',8,1,20),interval:numberEnv('KG_CLAIM_INTERVAL',30,0,600),refresh:numberEnv('KG_REFRESH_WEEKDAY',-1,-1,6)};
   let lo=numberEnv('KG_RANDOM_DELAY_MIN',1,0,720), hi=numberEnv('KG_RANDOM_DELAY_MAX',60,0,720);
   if(lo>hi) [lo,hi]=[hi,lo];
   if(action==='sign' && !DRY) {const minutes=crypto.randomInt(lo,hi+1);log('阶段 0：随机等待 '+minutes+' 分钟');await delay(minutes*60000);}
   else log('阶段 0：跳过随机等待');
   for(let i=0;i<users.length;i++) await signAccount(users[i],i+1,settings);
  } else {
   const stats=statsNew(); await stage(stats,1,'账号管理：'+action,()=>loginAction(action));
   for(const key of Object.keys(totals)) totals[key]+=stats[key];
   accountResults.push({account:1,status:stats.failed?'failure':DRY?'dry-run':'success',...stats});
  }
  const failures=accountResults.filter(r=>r.failed).length;
  status=failures ? failures===accountResults.length?'failure':'partial-failure' : DRY?'dry-run':'success';
 } catch(e) { configError=true;log('❌ 配置或执行错误：'+safeError(e)); }
 const failed=accountResults.filter(r=>r.failed).length;
 const summary={status,mode:DRY?'dry-run':'live',accounts:users.length,succeeded:DRY?0:accountResults.filter(r=>!r.failed).length,failed,configurationError:configError,tasks:totals,results:accountResults,durationMs:Date.now()-started};
 if(configError) log('账号数量：'+users.length);
 const exitCode=configError || failed ? 1 : 0;
 summary.notification=await notifySummary(summary).catch(()=>{log('通知失败，保留业务退出码');return 'failure';});
 log('----------------------------------------');
 log(`任务统计：账号 ${summary.accounts}，成功 ${summary.succeeded}，失败 ${failed}，总任务 ${totals.total}，成功 ${totals.success}，已完成 ${totals.alreadyComplete}，跳过 ${totals.skipped}，失败 ${totals.failed}`);
 log('总耗时：'+(Date.now()-started)+'ms；通知状态：'+summary.notification);
 log('完成时间：'+new Date().toISOString());log('最终状态：'+status);
 console.log('TASK_SUMMARY='+JSON.stringify(summary));
 process.exitCode=exitCode;
}
main().catch(()=>{process.exitCode=1;console.error('任务收尾异常（详情已隐藏）');});
