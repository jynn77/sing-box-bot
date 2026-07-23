#!/usr/bin/env node
/** sing-box-bot (Node.js) — hy2 + reality，UUID 持久化，komari 可选 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const os = require('os');
const http = require('http');
const { execSync } = require('child_process');
const axios = require('axios');
require('dotenv').config();

// ── 日志配置 ──────────────────────────────────────────
const LOG_ENABLED = process.env.LOG_ENABLED === 'true';
function log(...args) { if (LOG_ENABLED) console.log(...args); }
function error(...args) { console.error('[ERROR]', ...args); }

// ── 环境变量 ──────────────────────────────────────────
const FILE_PATH = process.env.FILE_PATH || '.cache';
const NODE_PORT = process.env.NODE_PORT ? parseInt(process.env.NODE_PORT) : null;
if (!NODE_PORT) {
  error('NODE_PORT environment variable is required');
  process.exit(1);
}
const UUID = process.env.UUID || loadUUID();
const UPLOAD_URL = process.env.UPLOAD_URL || '';
const NAME = process.env.NAME || '';
const CHAT_ID = process.env.CHAT_ID || '';
const BOT_TOKEN = process.env.BOT_TOKEN || '';
const DAILY_RESTART = process.env.DAILY_RESTART === 'true';
const KOMARI_ENABLED = process.env.KOMARI_ENABLED !== 'false';
const KOMARI_SERVER = process.env.KOMARI_SERVER || '';
const KOMARI_TOKEN = process.env.KOMARI_TOKEN || '';
const PORT = parseInt(process.env.PORT) || 3000;

// ── UUID 持久化 ──────────────────────────────────────
function loadUUID() {
  const f = path.join(FILE_PATH, 'uuid.txt');
  if (fs.existsSync(f)) { const u = fs.readFileSync(f, 'utf8').trim(); if (u) return u; }
  return crypto.randomUUID();
}
function saveUUID() {
  const f = path.join(FILE_PATH, 'uuid.txt');
  if (!fs.existsSync(f)) {
    fs.mkdirSync(FILE_PATH, { recursive: true });
    fs.writeFileSync(f, UUID);
    log(`[UUID] ${UUID} saved`);
  } else { log('[UUID] Loaded from file'); }
}

// ── 路径 ──────────────────────────────────────────────
const sbPath = path.join(FILE_PATH, 'web');
const komariPath = path.join(FILE_PATH, 'komori');
const configPath = path.join(FILE_PATH, 'config.json');
const komariLog = path.join(FILE_PATH, 'komori.log');

// ── 每日重启 ──────────────────────────────────────────
if (DAILY_RESTART) {
  setTimeout(() => { log('[DAILY] 24h reached, exiting'); process.exit(0); }, 86400000);
  log('[DAILY] Restart scheduled in 24h');
}

// ── 工具函数 ──────────────────────────────────────────
function sh(cmd) {
  try { return execSync(cmd, { shell: true, timeout: 30000, encoding: 'utf8' }); }
  catch (e) { return e.stdout || e.stderr || e.message; }
}
function shCheck(cmd) {
  try {
    execSync(cmd, { shell: true, timeout: 30000, encoding: 'utf8', stdio: 'pipe' });
    return true;
  } catch (e) {
    const msg = e.stderr || e.stdout || e.message;
    error(`Command failed: ${cmd}\n${msg}`);
    return false;
  }
}
function getArch() { return os.arch().toLowerCase().startsWith('arm') ? 'arm' : 'amd'; }
function getKomariArch() {
  const a = os.arch().toLowerCase();
  const map = { x64: 'amd64', amd64: 'amd64', arm64: 'arm64', aarch64: 'arm64' };
  return map[a] || (a.startsWith('arm') ? 'arm' : null);
}

// ── 下载（支持重试）───────────────────────────────────
async function download(name, url, retries = 3) {
  const fp = path.join(FILE_PATH, name);
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const r = await axios({ method: 'get', url, responseType: 'stream', timeout: 60000 });
      const w = fs.createWriteStream(fp);
      r.data.pipe(w);
      await new Promise((res, rej) => { w.on('finish', res); w.on('error', rej); });
      fs.chmodSync(fp, 0o775);
      log(`[DOWNLOAD] ${name} downloaded successfully`);
      return true;
    } catch (e) {
      error(`Download ${name} attempt ${attempt}/${retries} failed: ${e.message}`);
      try { fs.unlinkSync(fp); } catch {}
      if (attempt < retries) await new Promise(r => setTimeout(r, 5000));
    }
  }
  return false;
}

// ── 获取 IP ──────────────────────────────────────────
async function getIP() {
  for (const url of ['http://ipv4.ip.sb', 'https://api.ipify.org?format=json']) {
    try { return (await axios.get(url, { timeout: 5000 })).data.trim(); } catch {}
  }
  return '127.0.0.1';
}

// ── 获取 ISP ──────────────────────────────────────────
async function getISP() {
  try {
    const r = await axios.get('https://api.ip.sb/geoip', { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 5000 });
    if (r.data.country_code && r.data.isp) return `${r.data.country_code}-${r.data.isp}`.replace(/\s/g, '_');
  } catch {}
  try {
    const r = await axios.get('http://ip-api.com/json/', { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 5000 });
    if (r.data.status === 'success' && r.data.countryCode && r.data.org) return `${r.data.countryCode}-${r.data.org}`.replace(/\s/g, '_');
  } catch {}
  return 'Unknown';
}

// ── komari-agent ──────────────────────────────────────
async function runKomari() {
  const arch = getKomariArch();
  if (!arch) { error(`[KOMARI] Unsupported arch for komari-agent`); return; }
  const url = `https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-${arch}`;
  if (!await download('komori', url)) {
    error('[KOMARI] Download failed');
    return;
  }

  sh(`nohup ${komariPath} -e ${KOMARI_SERVER} --auto-discovery ${KOMARI_TOKEN} >${komariLog} 2>&1 &`);
  await new Promise(r => setTimeout(r, 2000));

  if (fs.existsSync(komariLog) && fs.statSync(komariLog).size > 0) {
    const lines = fs.readFileSync(komariLog, 'utf8').split('\n').slice(-3).join('\n');
    log(`[KOMARI] Started, log: ${komariLog}\n${lines}`);
  } else {
    log(`[KOMARI] No log yet: ${komariLog}`);
  }
}

// ── komari 进程检测 ──────────────────────────────────
function komariAlive() {
  try { return !!execSync('pgrep -f komori 2>/dev/null', { encoding: 'utf8', timeout: 5000 }).trim(); } catch {}
  try { return execSync('ps aux 2>/dev/null', { encoding: 'utf8', timeout: 5000 }).includes('komori'); } catch {}
  return false;
}

// ── 主流程 ──────────────────────────────────────────
async function main() {
  console.log('App starting...');

  log(`=== sing-box-bot (Node.js) === Port: ${NODE_PORT} (hy2 + reality)`);
  if (!fs.existsSync(FILE_PATH)) fs.mkdirSync(FILE_PATH, { recursive: true });
  saveUUID();

  const arch = getArch();
  const base = arch === 'arm' ? 'https://arm64.ssss.nyc.mn' : 'https://amd64.ssss.nyc.mn';
  if (!await download('web', `${base}/sb`)) {
    error('Failed to download sing-box binary after retries');
    process.exit(1);
  }

  // 加载或生成 reality keypair（持久化，重启不变）
  const keypairPath = path.join(FILE_PATH, 'keypair.txt');
  let privateKey, publicKey;
  if (fs.existsSync(keypairPath)) {
    const lines = fs.readFileSync(keypairPath, 'utf8').trim().split('\n');
    if (lines.length >= 2) {
      privateKey = lines[0]; publicKey = lines[1];
      log('[KEY] Loaded existing keypair');
    } else {
      fs.unlinkSync(keypairPath);
      error('[KEY] Invalid keypair file, regenerating');
    }
  }
  if (!privateKey || !publicKey) {
    const kp = sh(`${sbPath} generate reality-keypair`);
    const pm = kp.match(/PrivateKey:\s*(.*)/);
    const pum = kp.match(/PublicKey:\s*(.*)/);
    if (!(pm && pum)) {
      error('Failed to generate reality keypair, output:', kp);
      process.exit(1);
    }
    privateKey = pm[1].trim(); publicKey = pum[1].trim();
    fs.writeFileSync(keypairPath, `${privateKey}\n${publicKey}\n`);
    log('[KEY] Generated and saved');
  }
  log(`Private Key: ${privateKey}\nPublic Key: ${publicKey}`);

  // 生成证书（检查 openssl 是否成功）
  if (!shCheck(`openssl ecparam -genkey -name prime256v1 -out "${FILE_PATH}/private.key"`)) {
    error('openssl ecparam failed');
    process.exit(1);
  }
  if (!shCheck(`openssl req -new -x509 -days 3650 -key "${FILE_PATH}/private.key" -out "${FILE_PATH}/cert.pem" -subj "/CN=bing.com"`)) {
    error('openssl req failed');
    process.exit(1);
  }

  // 生成配置
  const config = {
    log: { disabled: true, level: 'info', timestamp: true },
    inbounds: [
      { tag: 'hysteria-in', type: 'hysteria2', listen: '::', listen_port: NODE_PORT, users: [{ password: UUID }], masquerade: 'https://bing.com',
        tls: { enabled: true, alpn: ['h3'], certificate_path: path.join(FILE_PATH, 'cert.pem'), key_path: path.join(FILE_PATH, 'private.key') } },
      { tag: 'vless-reality-in', type: 'vless', listen: '::', listen_port: NODE_PORT, users: [{ uuid: UUID, flow: 'xtls-rprx-vision' }],
        tls: { enabled: true, server_name: 'www.iij.ad.jp', reality: { enabled: true, handshake: { server: 'www.iij.ad.jp', server_port: 443 }, private_key: privateKey, short_id: [''] } } }
    ],
    outbounds: [{ type: 'direct', tag: 'direct' }]
  };
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  log('[CONFIG] Generated');

  // 启动 sing-box（后台运行）
  sh(`nohup ${sbPath} run -c ${configPath} >/dev/null 2>&1 &`);
  log('[SB] sing-box launched');
  await new Promise(r => setTimeout(r, 3000));

  // 启动 komari（若启用）
  if (KOMARI_ENABLED) {
    log('[KOMARI] Starting in 5s...');
    await new Promise(r => setTimeout(r, 5000));
    await runKomari();
    setInterval(() => {
      if (!komariAlive()) { log('[KOMARI] Process not found, restarting...'); sh(`nohup ${komariPath} -e ${KOMARI_SERVER} --auto-discovery ${KOMARI_TOKEN} >${komariLog} 2>&1 &`); }
    }, 300000);
    log('[KOMARI] Watchdog started (check every 5min)');
  }

  // 生成节点
  const [serverIP, isp] = await Promise.all([getIP(), getISP()]);
  const nodeName = NAME ? `${NAME}-${isp}` : isp;
  const subTxt = `hysteria2://${UUID}@${serverIP}:${NODE_PORT}/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#${nodeName}\nvless://${UUID}@${serverIP}:${NODE_PORT}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=chrome&pbk=${publicKey}&type=tcp&headerType=none#${nodeName}`;
  log(`\n${subTxt}\n[INFO] Port: ${NODE_PORT}`);

  // 推送通知
  if (BOT_TOKEN && CHAT_ID) {
    try {
      await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, null,
        { params: { chat_id: CHAT_ID, text: `✅ 节点已就绪 | ${nodeName}\n🌍 IP: ${serverIP}\n\n<pre>${Buffer.from(subTxt).toString('base64')}</pre>`, parse_mode: 'HTML' }, timeout: 15000 });
      log('[TG] Sent');
    } catch (e) { error(`[TG] Failed: ${e.message}`); }
  }
  if (UPLOAD_URL) {
    try {
      await axios.post(`${UPLOAD_URL}/api/add-nodes`, { nodes: subTxt.split('\n').filter(Boolean) },
        { headers: { 'Content-Type': 'application/json' }, timeout: 15000 });
      log('[UPLOAD] Nodes uploaded');
    } catch (e) { error(`[UPLOAD] Failed: ${e.message}`); }
  }

  // HTTP 服务（用于健康检查）
  http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(`<h2>sing-box-bot running</h2><p>hy2 + reality port: ${NODE_PORT}</p>`);
  }).listen(PORT, () => log(`[HTTP] Listening on :${PORT}`));

  // 90 秒后清理临时文件并输出运行完成标记
  setTimeout(() => {
    for (const f of [configPath, sbPath]) {
      try { if (fs.existsSync(f)) fs.unlinkSync(f); } catch (e) { error(`Cleanup remove ${f} failed: ${e.message}`); }
    }
    console.clear();
    console.log('App running');
    log('[CLEANUP] Temporary files removed, app is fully running');
  }, 90000);
}

main().catch(e => { error(e.message); process.exit(1); });