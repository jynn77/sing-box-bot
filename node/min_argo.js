#!/usr/bin/env node
/** sing-box-bot (min_argo) — hy2 + reality + Cloudflare Tunnel */
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const http = require('http');
const https = require('https');
const { execSync, spawn } = require('child_process');

function loadEnv() {
  const p = path.join(__dirname, '.env');
  if (!fs.existsSync(p)) return;
  for (const l of fs.readFileSync(p, 'utf8').split('\n')) {
    const m = l.match(/^\s*([^#=]+)=(.*)/);
    if (m) process.env[m[1].trim()] = m[2].trim().replace(/^["']|["']$/g, '');
  }
}
loadEnv();

const FP = process.env.FILE_PATH || '.cache';
const UUID = process.env.UUID || crypto.randomUUID();
const NAME = process.env.NAME || '';
const CHAT_ID = process.env.CHAT_ID || '';
const BOT_TOKEN = process.env.BOT_TOKEN || '';
const KOMARI_SERVER = process.env.KOMARI_SERVER || '';
const KOMARI_TOKEN = process.env.KOMARI_TOKEN || '';
const ARGO_TOKEN = process.env.ARGO_TOKEN || '';
const ARGO_DOMAIN = process.env.ARGO_DOMAIN || '';

// ── 下载 ────────────────────────────────────────────────
function dl(name, url) {
  const fp = path.join(FP, name);
  if (fs.existsSync(fp)) return true;
  console.log(`[DL] Downloading ${name}...`);
  return new Promise(resolve => {
    const file = fs.createWriteStream(fp);
    const mod = url.startsWith('https') ? https : http;
    mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 60000 }, res => {
      if (res.statusCode !== 200) { console.error(`[DL] ${name} failed: HTTP ${res.statusCode}`); file.close(); try { fs.unlinkSync(fp); } catch {} resolve(false); return; }
      res.pipe(file);
      file.on('finish', () => { file.close(); fs.chmodSync(fp, 0o775); resolve(true); });
    }).on('error', e => { console.error(`[DL] ${name} failed: ${e.message}`); file.close(); try { fs.unlinkSync(fp); } catch {} resolve(false); });
  });
}

// ── komari ──────────────────────────────────────────────
function getKomariArch() {
  const a = os.arch().toLowerCase();
  const map = { x64: 'amd64', amd64: 'amd64', arm64: 'arm64', aarch64: 'arm64' };
  return map[a] || (a.startsWith('arm') ? 'arm' : null);
}
function komariAlive() {
  try { return !!execSync('pgrep -f komori 2>/dev/null', { encoding: 'utf8', timeout: 5000 }).trim(); } catch {}
  try { return execSync('ps aux 2>/dev/null', { encoding: 'utf8', timeout: 5000 }).includes('komori'); } catch {}
  return false;
}
async function startKomari() {
  if (!KOMARI_SERVER || !KOMARI_TOKEN) return;
  const arch = getKomariArch();
  if (!arch) return;
  const komPath = path.join(FP, 'komori');
  const komLog = path.join(FP, 'komori.log');
  if (!await dl('komori', `https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-${arch}`)) return;
  execSync(`nohup ${komPath} -e ${KOMARI_SERVER} --auto-discovery ${KOMARI_TOKEN} >${komLog} 2>&1 &`, { timeout: 5000 });
  console.log('[KOMARI] Started');
}

// ── 主流程 ──────────────────────────────────────────────
async function main() {
  console.log('App starting...');
  fs.mkdirSync(FP, { recursive: true });

  const arch = os.arch().toLowerCase().startsWith('arm') ? 'arm64' : 'amd64';
  const sb = path.join(FP, 'web');
  const cfd = path.join(FP, 'cfd');
  const cfg = path.join(FP, 'config.json');
  const kp = path.join(FP, 'keypair.txt');
  const cfdLog = path.join(FP, 'cfd.log');

  // 下载 sing-box + cloudflared
  if (!await dl('web', `https://${arch}.ssss.nyc.mn/sb`)) { console.error('[FATAL] sing-box download failed'); process.exit(1); }
  if (!await dl('cfd', `https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}`)) { console.error('[FATAL] cloudflared download failed'); process.exit(1); }

  // UUID 持久化
  const uf = path.join(FP, 'uuid.txt');
  if (!fs.existsSync(uf)) fs.writeFileSync(uf, UUID);

  // Keypair
  let pk, puk;
  if (fs.existsSync(kp)) {
    const l = fs.readFileSync(kp, 'utf8').trim().split('\n');
    if (l.length >= 2) { pk = l[0]; puk = l[1]; }
  }
  if (!pk || !puk) {
    const o = execSync(`${sb} generate reality-keypair`, { encoding: 'utf8', timeout: 10000 });
    const pm = o.match(/PrivateKey:\s*(.*)/);
    const pum = o.match(/PublicKey:\s*(.*)/);
    if (!pm || !pum) { console.error('[FATAL] Keypair failed'); process.exit(1); }
    pk = pm[1].trim(); puk = pum[1].trim();
    fs.writeFileSync(kp, `${pk}\n${puk}\n`);
  }

  // 证书
  execSync(`openssl ecparam -genkey -name prime256v1 -out "${FP}/private.key" 2>/dev/null`, { timeout: 10000 });
  execSync(`openssl req -new -x509 -days 3650 -key "${FP}/private.key" -out "${FP}/cert.pem" -subj "/CN=bing.com" 2>/dev/null`, { timeout: 10000 });

  // 配置
  fs.writeFileSync(cfg, JSON.stringify({
    log: { disabled: true },
    inbounds: [
      { tag: 'hy2', type: 'hysteria2', listen: '::', listen_port: 3001, users: [{ password: UUID }],
        masquerade: 'https://bing.com', tls: { enabled: true, alpn: ['h3'],
          certificate_path: `${FP}/cert.pem`, key_path: `${FP}/private.key` } },
      { tag: 'vless', type: 'vless', listen: '::', listen_port: 3001, users: [{ uuid: UUID, flow: 'xtls-rprx-vision' }],
        tls: { enabled: true, server_name: 'www.iij.ad.jp', reality: { enabled: true,
          handshake: { server: 'www.iij.ad.jp', server_port: 443 }, private_key: pk, short_id: [''] } } }
    ],
    outbounds: [{ type: 'direct', tag: 'direct' }]
  }));

  // 启动 sing-box
  execSync(`nohup ${sb} run -c ${cfg} >/dev/null 2>&1 &`, { timeout: 5000 });
  console.log('[SB] sing-box started');

  // ── Cloudflare Tunnel ──────────────────────────────
  let tunnelUrl = '';
  if (ARGO_TOKEN && ARGO_DOMAIN) {
    console.log('[ARGO] Starting fixed tunnel...');
    execSync(`nohup ${cfd} tunnel run --token ${ARGO_TOKEN} >${cfdLog} 2>&1 &`, { timeout: 5000 });
    tunnelUrl = `https://${ARGO_DOMAIN}`;
  } else {
    console.log('[ARGO] Starting temporary tunnel...');
    const p = spawn(cfd, ['tunnel', '--url', 'http://localhost:3001'], { stdio: ['ignore', 'pipe', 'pipe'] });
    const out = fs.createWriteStream(cfdLog);
    p.stdout.pipe(out); p.stderr.pipe(out);
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000));
      try {
        const log = fs.readFileSync(cfdLog, 'utf8');
        const m = log.match(/https:\/\/[a-zA-Z0-9-]+\.trycloudflare\.com/);
        if (m) { tunnelUrl = m[0]; break; }
      } catch {}
    }
    if (!tunnelUrl) { console.error('[FATAL] Failed to get tunnel URL'); process.exit(1); }
  }
  console.log(`[ARGO] Tunnel: ${tunnelUrl}`);

  // 启动 komari
  if (KOMARI_SERVER && KOMARI_TOKEN) {
    setTimeout(async () => { await startKomari(); }, 10000);
    setInterval(() => { if (!komariAlive()) { console.log('[KOMARI] Restarting...'); startKomari(); } }, 300000);
  }

  // 获取 ISP
  let isp = 'Unknown';
  try {
    const d = await new Promise((res, rej) => https.get('https://api.ip.sb/geoip', { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 5000 }, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(d)); }).on('error', rej));
    const j = JSON.parse(d);
    if (j.country_code && j.isp) isp = `${j.country_code}-${j.isp}`.replace(/\s/g, '_');
  } catch {}

  // 节点链接
  const host = new URL(tunnelUrl).hostname;
  const nn = NAME ? `${NAME}-${isp}` : isp;
  const txt = `hysteria2://${UUID}@${host}:443/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#${nn}\nvless://${UUID}@${host}:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=chrome&pbk=${puk}&type=tcp&headerType=none#${nn}`;
  console.log(`\n${txt}\n[INFO] Tunnel: ${tunnelUrl}`);

  // TG 推送
  if (BOT_TOKEN && CHAT_ID) {
    try {
      const b = JSON.stringify({ chat_id: CHAT_ID, text: `✅ 节点已就绪 | ${nn}\n🌐 Argo: ${host}\n\n<pre>${Buffer.from(txt).toString('base64')}</pre>`, parse_mode: 'HTML' });
      const u = new URL(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`);
      const r = https.request({ hostname: u.hostname, path: u.pathname, method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(b) }, timeout: 15000 });
      r.write(b); r.end();
    } catch {}
  }

  console.log('App running');
  await new Promise(() => {});
}

main().catch(e => { console.error(e.message); process.exit(1); });