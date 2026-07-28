#!/usr/bin/env node
/** sing-box-bot (min_argo) — VMESS+WS + Cloudflare Tunnel */
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
const CFIP = process.env.CFIP || 'saas.sin.fan';
const CFPORT = process.env.CFPORT || '443';

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
  const kp = path.join(FP, 'komori'), kl = path.join(FP, 'komori.log');
  if (!await dl('komori', `https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-${arch}`)) return;
  execSync(`nohup ${kp} -e ${KOMARI_SERVER} --auto-discovery ${KOMARI_TOKEN} >${kl} 2>&1 &`, { timeout: 5000 });
  console.log('[KOMARI] Started');
}

async function main() {
  console.log('App starting...');
  fs.mkdirSync(FP, { recursive: true });

  const arch = os.arch().toLowerCase().startsWith('arm') ? 'arm64' : 'amd64';
  const sb = path.join(FP, 'web'), cfd = path.join(FP, 'cfd');
  const cfg = path.join(FP, 'config.json'), cfdLog = path.join(FP, 'cfd.log');

  if (!await dl('web', `https://${arch}.ssss.nyc.mn/sb`)) { console.error('[FATAL] sing-box download failed'); process.exit(1); }
  if (!await dl('cfd', `https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}`)) { console.error('[FATAL] cloudflared download failed'); process.exit(1); }

  const uf = path.join(FP, 'uuid.txt');
  if (!fs.existsSync(uf)) fs.writeFileSync(uf, UUID);

  // VMESS + WS 配置
  fs.writeFileSync(cfg, JSON.stringify({
    log: { disabled: true },
    inbounds: [{
      tag: 'vmess-ws', type: 'vmess', listen: '::', listen_port: 3001,
      users: [{ uuid: UUID, alterId: 0 }],
      transport: { type: 'ws', path: '/vmess-argo' }
    }],
    outbounds: [{ type: 'direct', tag: 'direct' }]
  }));

  execSync(`nohup ${sb} run -c ${cfg} >/dev/null 2>&1 &`, { timeout: 5000 });
  console.log('[SB] sing-box started');

  // ── Cloudflare Tunnel ──────────────────────────────
  let tunnelHost = '';
  if (ARGO_TOKEN && ARGO_DOMAIN) {
    console.log(`[ARGO] Using fixed tunnel: ${ARGO_DOMAIN}`);
    execSync(`nohup ${cfd} tunnel run --token ${ARGO_TOKEN} >${cfdLog} 2>&1 &`, { timeout: 5000 });
    tunnelHost = ARGO_DOMAIN;
  } else {
    console.log('[ARGO] Starting temporary tunnel...');
    const p = spawn(cfd, ['tunnel', '--url', 'http://localhost:3001'], { stdio: ['ignore', 'pipe', 'pipe'] });
    p.stdout.pipe(fs.createWriteStream(cfdLog));
    p.stderr.pipe(fs.createWriteStream(cfdLog, { flags: 'a' }));
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000));
      try {
        const log = fs.readFileSync(cfdLog, 'utf8');
        const m = log.match(/https:\/\/([a-zA-Z0-9-]+\.trycloudflare\.com)/);
        if (m) { tunnelHost = m[1]; break; }
      } catch {}
    }
    if (!tunnelHost) { console.error('[FATAL] Failed to get tunnel URL'); process.exit(1); }
  }
  console.log(`[ARGO] Tunnel: ${tunnelHost}`);

  // komari
  if (KOMARI_SERVER && KOMARI_TOKEN) {
    setTimeout(async () => { await startKomari(); }, 10000);
    setInterval(() => { if (!komariAlive()) { console.log('[KOMARI] Restarting...'); startKomari(); } }, 300000);
  }

  // ISP
  let isp = 'Unknown';
  try {
    const d = await new Promise((res, rej) => https.get('https://api.ip.sb/geoip', { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 5000 }, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(d)); }).on('error', rej));
    const j = JSON.parse(d);
    if (j.country_code && j.isp) isp = `${j.country_code}-${j.isp}`.replace(/\s/g, '_');
  } catch {}

  // VMESS 链接
  const nn = NAME ? `${NAME}-${isp}-Argo` : `${isp}-Argo`;
  const vmess = {
    v: '2', ps: nn, add: CFIP, port: CFPORT,
    id: UUID, aid: '0', scy: 'auto',
    net: 'ws', type: 'none',
    host: tunnelHost, path: '/vmess-argo?ed=2560',
    tls: 'tls', sni: tunnelHost,
    alpn: '', fp: 'firefox', insecure: '0'
  };
  const txt = 'vmess://' + Buffer.from(JSON.stringify(vmess)).toString('base64');
  console.log(`\n${txt}\n[INFO] CF IP: ${CFIP}:${CFPORT} | Tunnel: ${tunnelHost}`);

  // TG
  if (BOT_TOKEN && CHAT_ID) {
    try {
      const b = JSON.stringify({ chat_id: CHAT_ID, text: `✅ 节点已就绪 | ${nn}\n🌐 Argo: ${tunnelHost}\n\n<pre>${Buffer.from(txt).toString('base64')}</pre>`, parse_mode: 'HTML' });
      const u = new URL(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`);
      const r = https.request({ hostname: u.hostname, path: u.pathname, method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(b) }, timeout: 15000 });
      r.write(b); r.end();
    } catch {}
  }

  console.log('App running');
  await new Promise(() => {});
}

main().catch(e => { console.error(e.message); process.exit(1); });