#!/usr/bin/env node

/**
 * sing-box-bot — 精简版 sing-box 节点生成器
 *
 * 仅支持 Hysteria2 + Reality 协议，端口 10280
 * 无 nezha、无 argo、无多余协议
 *
 * 流程:
 *   1. 下载对应架构的 sing-box 和 cloudflared(bot) 二进制
 *   2. 生成 reality keypair
 *   3. 生成 TLS 自签证书（hy2 使用）
 *   4. 生成 sing-box 配置（hy2-in + reality-in）
 *   5. 运行 sing-box
 *   6. 生成订阅节点并推送 Telegram
 *   7. 启动 Express 提供订阅链接
 */

const express = require("express");
const app = express();
const axios = require("axios");
const os = require('os');
const fs = require("fs");
const path = require("path");
require('dotenv').config();
const { promisify } = require('util');
const exec = promisify(require('child_process').exec);

// ── 环境变量 ──────────────────────────────────────────
const FILE_PATH     = process.env.FILE_PATH || '.npm';
const SUB_PATH      = process.env.SUB_PATH || 'sub';
const UUID          = process.env.UUID || require('crypto').randomUUID();
const PORT          = parseInt(process.env.PORT) || 3000;
const NODE_PORT     = parseInt(process.env.NODE_PORT) || 10280;
const NAME          = process.env.NAME || '';
const CHAT_ID       = process.env.CHAT_ID || '';
const BOT_TOKEN     = process.env.BOT_TOKEN || '';
const UPLOAD_URL    = process.env.UPLOAD_URL || '';
const CFIP          = process.env.CFIP || 'saas.sin.fan';
const CFPORT        = parseInt(process.env.CFPORT) || 443;
const DOWNLOAD_BASE = process.env.DOWNLOAD_BASE || 'https://amd64.ssss.nyc.mn';
const TG_TTL_MS     = (parseInt(process.env.TG_TTL_MINUTES) || 5) * 60 * 1000;
const TG_CLEAN_INT  = (parseInt(process.env.TG_CLEAN_INTERVAL) || 30) * 1000;

// 创建运行目录
if (!fs.existsSync(FILE_PATH)) {
  fs.mkdirSync(FILE_PATH, { recursive: true });
  console.log(`[DIR] ${FILE_PATH} created`);
}

// ── 随机文件名 ──────────────────────────────────────
function randName(len = 6) {
  const c = 'abcdefghijklmnopqrstuvwxyz';
  let r = '';
  for (let i = 0; i < len; i++) r += c.charAt(Math.floor(Math.random() * c.length));
  return r;
}

const RAND_SB = randName();
const RAND_BOT = randName();
const SB_PATH = path.join(FILE_PATH, RAND_SB);
const BOT_PATH = path.join(FILE_PATH, RAND_BOT);
const SUB_FILE = path.join(FILE_PATH, 'sub.txt');
const LIST_FILE = path.join(FILE_PATH, 'list.txt');
const KEY_FILE = path.join(FILE_PATH, 'key.txt');
const CONFIG_FILE = path.join(FILE_PATH, 'config.json');

// ════════════════════════════════════════════════════════
//  TG 消息追踪 & 自动删除
// ════════════════════════════════════════════════════════
const tgSent = new Map(); // Map<chatId, Map<messageId, timestamp>>

function tgTrack(chatId, messageId) {
  if (!tgSent.has(chatId)) tgSent.set(chatId, new Map());
  tgSent.get(chatId).set(messageId, Date.now());
  console.log('[TG-TRACK] chat:' + chatId + ' msg:' + messageId);
}

function tgUntrack(chatId, messageId) {
  const m = tgSent.get(chatId);
  if (m) { m.delete(messageId); if (m.size === 0) tgSent.delete(chatId); }
}

function tgCount() {
  let n = 0;
  for (const cm of tgSent.values()) n += cm.size;
  return n;
}

async function tgDelete(chatId, messageId) {
  try {
    await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/deleteMessage`, null, {
      params: { chat_id: chatId, message_id: messageId }
    });
    console.log('[TG-DEL] chat:' + chatId + ' msg:' + messageId + ' deleted');
    return true;
  } catch (e) {
    console.log('[TG-DEL] chat:' + chatId + ' msg:' + messageId + ' fail: ' + (e.response?.data?.description || e.message));
    return false;
  } finally {
    tgUntrack(chatId, messageId);
  }
}

async function tgCleanup() {
  const now = Date.now();
  let ck = 0, dl = 0, fl = 0;
  for (const [chatId, cm] of tgSent.entries()) {
    for (const [msgId, ts] of [...cm.entries()]) {
      ck++;
      if (now - ts >= TG_TTL_MS) {
        if (await tgDelete(chatId, msgId)) dl++; else fl++;
      }
    }
  }
  if (ck > 0) console.log('[TG-CLEAN] ck=' + ck + ' del=' + dl + ' fail=' + fl + ' remain=' + tgCount());
}

// ── 系统架构检测 ──────────────────────────────────
function getArch() {
  const a = os.arch();
  return (a === 'arm' || a === 'arm64' || a === 'aarch64') ? 'arm' : 'amd';
}

// ── 下载文件 ────────────────────────────────────────
function download(fileName, fileUrl) {
  return new Promise((resolve, reject) => {
    const fp = path.join(FILE_PATH, fileName);
    const w = fs.createWriteStream(fp);
    axios({ method: 'get', url: fileUrl, responseType: 'stream' })
      .then(r => {
        r.data.pipe(w);
        w.on('finish', () => { w.close(); console.log(`[DL] ${fileName}`); resolve(fp); });
        w.on('error', e => { fs.unlink(fp, () => {}); reject(e); });
      })
      .catch(reject);
  });
}

// ── 生成自签证书（hy2 需要） ──────────────────────
async function genCert() {
  const keyPath = path.join(FILE_PATH, 'private.key');
  const certPath = path.join(FILE_PATH, 'cert.pem');

  // 先尝试用 openssl 生成
  try {
    await exec(`openssl ecparam -genkey -name prime256v1 -out "${keyPath}"`);
    await exec(`openssl req -new -x509 -days 3650 -key "${keyPath}" -out "${certPath}" -subj "/CN=bing.com"`);
    console.log('[CERT] Generated with OpenSSL');
    return;
  } catch { /* fallback */ }

  // fallback：预定义证书
  const pk = `-----BEGIN EC PARAMETERS-----
BggqhkjOPQMBBw==
-----END EC PARAMETERS-----
-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIM4792SEtPqIt1ywqTd/0bYidBqpYV/++siNnfBYsdUYoAoGCCqGSM49
AwEHoUQDQgAE1kHafPj07rJG+HboH2ekAI4r+e6TL38GWASANnngZreoQDF16ARa
/TsyLyFoPkhLxSbehH/NBEjHtSZGaDhMqQ==
-----END EC PRIVATE KEY-----`;
  const cert = `-----BEGIN CERTIFICATE-----
MIIBejCCASGgAwIBAgIUfWeQL3556PNJLp/veCFxGNj9crkwCgYIKoZIzj0EAwIw
EzERMA8GA1UEAwwIYmluZy5jb20wHhcNMjUwOTE4MTgyMDIyWhcNMzUwOTE2MTgy
MDIyWjATMREwDwYDVQQDDAhiaW5nLmNvbTBZMBMGByqGSM49AgEGCCqGSM49AwEH
A0IABNZB2nz49O6yRvh26B9npACOK/nuky9/BlgEgDZ54Ga3qEAxdegEWv07Mi8h
aD5IS8Um3oR/zQRIx7UmRmg4TKmjUzBRMB0GA1UdDgQWBBTV1cFID7UISE7PLTBR
BfGbgkrMNzAfBgNVHSMEGDAWgBTV1cFID7UISE7PLTBRBfGbgkrMNzAPBgNVHRMB
Af8EBTADAQH/MAoGCCqGSM49BAMCA0cAMEQCIAIDAJvg0vd/ytrQVvEcSm6XTlB+
eQ6OFb9LbLYL9f+sAiAffoMbi4y/0YUSlTtz7as9S8/lciBF5VCUoVIKS+vX2g==
-----END CERTIFICATE-----`;
  fs.writeFileSync(keyPath, pk);
  fs.writeFileSync(certPath, cert);
  console.log('[CERT] Generated with fallback');
}

// ── 生成 reality keypair ──────────────────────────
let privateKey = '';
let publicKey = '';

async function genKeypair(sbPath) {
  if (fs.existsSync(KEY_FILE)) {
    const c = fs.readFileSync(KEY_FILE, 'utf8');
    const pm = c.match(/PrivateKey:\s*(.*)/);
    const pum = c.match(/PublicKey:\s*(.*)/);
    if (pm && pum) {
      privateKey = pm[1].trim();
      publicKey = pum[1].trim();
      console.log('[KEY] Loaded from file');
      return;
    }
  }
  return new Promise((resolve, reject) => {
    exec(`${sbPath} generate reality-keypair`, (err, stdout) => {
      if (err) { console.error('[KEY] Generate failed:', err.message); reject(err); return; }
      const pm = stdout.match(/PrivateKey:\s*(.*)/);
      const pum = stdout.match(/PublicKey:\s*(.*)/);
      if (pm && pum) {
        privateKey = pm[1].trim();
        publicKey = pum[1].trim();
        fs.writeFileSync(KEY_FILE, `PrivateKey: ${privateKey}\nPublicKey: ${publicKey}\n`);
        console.log('[KEY] Generated new keypair');
        resolve();
      } else {
        reject(new Error('Failed to parse keypair'));
      }
    });
  });
}

// ── 生成 sing-box 配置 ──────────────────────────
function genConfig() {
  const config = {
    log: { disabled: true, level: "error", timestamp: true },
    inbounds: [
      {
        tag: "hysteria-in",
        type: "hysteria2",
        listen: "::",
        listen_port: NODE_PORT,
        users: [{ password: UUID }],
        masquerade: "https://bing.com",
        tls: {
          enabled: true,
          alpn: ["h3"],
          certificate_path: path.join(FILE_PATH, "cert.pem"),
          key_path: path.join(FILE_PATH, "private.key")
        }
      },
      {
        tag: "vless-reality-in",
        type: "vless",
        listen: "::",
        listen_port: NODE_PORT,
        users: [{ uuid: UUID, flow: "xtls-rprx-vision" }],
        tls: {
          enabled: true,
          server_name: "www.iij.ad.jp",
          reality: {
            enabled: true,
            handshake: { server: "www.iij.ad.jp", server_port: 443 },
            private_key: privateKey,
            short_id: [""]
          }
        }
      }
    ],
    outbounds: [{ type: "direct", tag: "direct" }]
  };

  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
  console.log('[CONFIG] Generated');
}

// ── 获取 IP ────────────────────────────────────────
async function getIP() {
  try {
    const r = await axios.get('http://ipv4.ip.sb', { timeout: 5000 });
    return r.data.trim();
  } catch {
    try {
      const r = await axios.get('https://api.ipify.org?format=json', { timeout: 5000 });
      return r.data.ip;
    } catch {
      try {
        const { stdout } = await exec('curl -sm 3 ipv4.ip.sb');
        return stdout.trim();
      } catch {
        return '127.0.0.1';
      }
    }
  }
}

// ── 获取 ISP ──────────────────────────────────────
async function getISP() {
  try {
    const r = await axios.get('https://api.ip.sb/geoip', {
      headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 5000
    });
    if (r.data && r.data.country_code && r.data.isp)
      return `${r.data.country_code}-${r.data.isp}`.replace(/\s+/g, '_');
  } catch { /* fallback */ }
  try {
    const r = await axios.get('http://ip-api.com/json', {
      headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 5000
    });
    if (r.data && r.data.status === 'success' && r.data.countryCode && r.data.org)
      return `${r.data.countryCode}-${r.data.org}`.replace(/\s+/g, '_');
  } catch { /* ignore */ }
  return 'Unknown';
}

// ── 生成订阅节点 ──────────────────────────────────
async function generateNodes() {
  const SERVER_IP = await getIP();
  const ISP = await getISP();
  const nodeName = NAME ? `${NAME}-${ISP}` : ISP;
  let subTxt = '';

  // Hysteria2 节点
  subTxt += `hysteria2://${UUID}@${SERVER_IP}:${NODE_PORT}/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#${nodeName}`;

  // Reality(VLESS) 节点
  subTxt += `\nvless://${UUID}@${SERVER_IP}:${NODE_PORT}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=firefox&pbk=${publicKey}&type=tcp&headerType=none#${nodeName}`;

  // 打印到控制台（绿色）
  const b64 = Buffer.from(subTxt).toString('base64');
  console.log('\n\x1b[32m' + b64 + '\x1b[0m\n');

  // 写入文件
  fs.writeFileSync(SUB_FILE, b64);
  fs.writeFileSync(LIST_FILE, subTxt, 'utf8');
  console.log(`[SUB] ${SUB_FILE} saved`);

  // 设置订阅路由
  app.get(`/${SUB_PATH}`, (req, res) => {
    res.set('Content-Type', 'text/plain; charset=utf-8');
    res.send(b64);
  });

  // 推送到 Telegram
  await sendTG(subTxt, nodeName);

  // 推送到订阅器
  await uploadNodes();

  return subTxt;
}

// ── Telegram 推送（含自动删除追踪） ────────────────
async function sendTG(message, nodeName) {
  if (!BOT_TOKEN || !CHAT_ID) {
    console.log('[TG] BOT_TOKEN or CHAT_ID empty, skip');
    return;
  }
  try {
    const b64 = Buffer.from(message).toString('base64');
    const esc = (s) => s.replace(/[_*[\]()~`>#+=|{}.!-]/g, '\\$&');
    const text = `**${esc(nodeName)} \\- 节点已就绪**\n\`\`\`${b64}\`\`\``;
    const resp = await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, null, {
      params: { chat_id: CHAT_ID, text, parse_mode: 'MarkdownV2' }
    });
    // 追踪这条消息，将在 TG_TTL 后自动删除
    const msg = resp.data?.result;
    if (msg && msg.message_id) {
      tgTrack(msg.chat.id, msg.message_id);
      console.log('[TG] Sent, will auto-delete in ' + (TG_TTL_MS / 1000 / 60) + ' min');
    }
  } catch (e) {
    console.error('[TG] Send failed:', e.message);
  }
}

// ── 上传到订阅器 ──────────────────────────────────
async function uploadNodes() {
  if (!UPLOAD_URL) return;
  if (!fs.existsSync(LIST_FILE)) return;

  const content = fs.readFileSync(LIST_FILE, 'utf-8');
  const nodes = content.split('\n').filter(l => /(vless|hysteria2):\/\//.test(l));
  if (nodes.length === 0) return;

  try {
    await axios.post(`${UPLOAD_URL}/api/add-nodes`, { nodes }, {
      headers: { 'Content-Type': 'application/json' }
    });
    console.log('[UPLOAD] Nodes uploaded');
  } catch { /* ignore */ }
}

// ── 清理 ──────────────────────────────────────────
function cleanup() {
  setTimeout(() => {
    const files = [CONFIG_FILE, LIST_FILE, SB_PATH, BOT_PATH, KEY_FILE];
    const cmd = `rm -rf ${files.join(' ')} >/dev/null 2>&1`;
    exec(cmd, () => {
      console.clear();
      console.log('[DONE] App running, subscribe at /' + SUB_PATH);
    });
  }, 90000);
}

// ── 主流程 ────────────────────────────────────────
async function start() {
  console.log('=== sing-box-bot ===');
  console.log('Port: ' + NODE_PORT + ' (hy2 + reality)');

  const arch = getArch();
  const base = arch === 'arm' ? DOWNLOAD_BASE.replace('amd64', 'arm64') : DOWNLOAD_BASE;
  const sbUrl = `${base}/sb`;
  const botUrl = `${base}/bot`;

  // 下载二进制
  try {
    await Promise.all([
      download(RAND_SB, sbUrl),
      download(RAND_BOT, botUrl),
    ]);
  } catch (e) {
    console.error('[FATAL] Download failed:', e.message);
    process.exit(1);
  }

  // 授权
  fs.chmodSync(SB_PATH, 0o775);
  fs.chmodSync(BOT_PATH, 0o775);

  // 生成证书 + keypair
  await genCert();
  await genKeypair(SB_PATH);

  // 生成配置
  genConfig();

  // 运行 sing-box
  try {
    await exec(`nohup ${SB_PATH} run -c ${CONFIG_FILE} >/dev/null 2>&1 &`);
    console.log('[SB] sing-box running');
  } catch (e) {
    console.error('[SB] Failed:', e.message);
  }

  // 等 sing-box 启动，然后生成节点
  await new Promise(r => setTimeout(r, 3000));
  await generateNodes();

  // TG 消息自动清理定时器（每 TG_CLEAN_INT 扫描一次）
  setInterval(tgCleanup, TG_CLEAN_INT);
  console.log('[TG] Auto-clean timer started, TTL=' + (TG_TTL_MS / 1000 / 60) + 'min');

  // 定时清理
  cleanup();
}

// ── 根路由 ────────────────────────────────────────
app.get("/", (req, res) => {
  res.send(`sing-box-bot running<br><br>Subscribe: /${SUB_PATH}`);
});

// ── 启动 ──────────────────────────────────────────
start().catch(e => {
  console.error('[FATAL]', e.message);
  process.exit(1);
});

app.listen(PORT, () => console.log(`[HTTP] :${PORT}`));