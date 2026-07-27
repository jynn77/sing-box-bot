#!/usr/bin/env node
/** sing-box-bot (min_argo) — hy2 + reality + Cloudflare Tunnel 临时隧道 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const os = require('os');
const http = require('http');
const https = require('https');
const { execSync, spawn } = require('child_process');

// ── 手动解析 .env ──────────────────────────────────────
function loadEnv() {
  const p = path.join(__dirname, '.env');
  if (!fs.existsSync(p)) return;
  for (const l of fs.readFileSync(p, 'utf8').split('\n')) {
    const m = l.match(/^\s*([^#=]+)=(.*)/);
    if (m) process.env[m[1].trim()] = m[2].trim().replace(/^["']|["']$/g, '');
  }
}
loadEnv();

// ── 轻量 HTTP ──────────────────────────────────────────
function httpGet(url) {
  return new Promise((res, rej) => {
    (url.startsWith('https') ? https : http).get(url, { timeout: 10000 }, r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => res(d));
    }).on('error', rej);
  });
}
function httpPost(url, data) {
  return new Promise((res, rej) => {
    const u = new URL(url);
    const b = JSON.stringify(data);
    const opt = { hostname: u.hostname, port: u.port || 443, path: u.pathname, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(b) }, timeout: 15000 };
    const r = (u.protocol === 'https:' ? https : http).request(opt, rp => {
      let d = ''; rp.on('data', c => d += c); rp.on('end', () => res(d));
    });
    r.on('error', rej); r.write(b); r.end();
  });
}

// ── 配置 ────────────────────────────────────────────────
const FP = process.env.FILE_PATH || '.cache';
const NP = parseInt(process.env.NODE_PORT) || (console.error('NODE_PORT required'), process.exit(1));
const UUID = process.env.UUID || (() => {
  const f = path.join(FP, 'uuid.txt');
  if (fs.existsSync(f)) return fs.readFileSync(f, 'utf8').trim();
  const u = crypto.randomUUID();
  fs.mkdirSync(FP, { recursive: true }); fs.writeFileSync(f, u); return u;
})();
const BT = process.env.BOT_TOKEN || '';
const CI = process.env.CHAT_ID || '';
const ARGO_TOKEN = process.env.ARGO_TOKEN || ''; // 设此值则用长期隧道，否则临时隧道

// ── 下载二进制 ──────────────────────────────────────────
function dl(name, url) {
  const fp = path.join(FP, name);
  if (fs.existsSync(fp)) return true;
  console.log(`[DL] Downloading ${name}...`);
  try {
    execSync(`curl -sLo "${fp}" "${url}" 2>/dev/null || wget -qO "${fp}" "${url}" 2>/dev/null`, { timeout: 60000, stdio: 'pipe' });
    fs.chmodSync(fp, 0o775); return true;
  } catch { console.error(`[FATAL] Download ${name} failed`); return false; }
}

// ── 主流程 ──────────────────────────────────────────────
async function main() {
  console.log('App starting...');

  const arch = os.arch().toLowerCase().startsWith('arm') ? 'arm64' : 'amd64';
  const sb = path.join(FP, 'web');
  const cfd = path.join(FP, 'cfd');
  const cfg = path.join(FP, 'config.json');
  const kp = path.join(FP, 'keypair.txt');
  const cfdLog = path.join(FP, 'cfd.log');

  // 下载 sing-box + cloudflared
  if (!dl('web', `https://${arch}.ssss.nyc.mn/sb`)) process.exit(1);
  if (!dl('cfd', `https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}`)) process.exit(1);

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

  // 配置（hy2 + reality，同原版）
  fs.writeFileSync(cfg, JSON.stringify({
    log: { disabled: true },
    inbounds: [
      { tag: 'hy2', type: 'hysteria2', listen: '::', listen_port: NP, users: [{ password: UUID }],
        masquerade: 'https://bing.com', tls: { enabled: true, alpn: ['h3'],
          certificate_path: `${FP}/cert.pem`, key_path: `${FP}/private.key` } },
      { tag: 'vless', type: 'vless', listen: '::', listen_port: NP, users: [{ uuid: UUID, flow: 'xtls-rprx-vision' }],
        tls: { enabled: true, server_name: 'www.iij.ad.jp', reality: { enabled: true,
          handshake: { server: 'www.iij.ad.jp', server_port: 443 }, private_key: pk, short_id: [''] } } }
    ],
    outbounds: [{ type: 'direct', tag: 'direct' }]
  }));

  // 启动 sing-box
  execSync(`nohup ${sb} run -c ${cfg} >/dev/null 2>&1 &`, { timeout: 5000 });
  console.log('[SB] sing-box started');

  // ── 启动 Cloudflare Tunnel ──────────────────────────────
  let tunnelUrl = '';
  if (ARGO_TOKEN) {
    // 长期隧道（用 token）
    console.log('[ARGO] Starting permanent tunnel...');
    const p = spawn(cfd, ['tunnel', 'run', '--token', ARGO_TOKEN], { stdio: ['ignore', 'pipe', 'pipe'] });
    const out = fs.createWriteStream(cfdLog);
    p.stdout.pipe(out); p.stderr.pipe(out);
    // 长期隧道域名需从 ARGO_DOMAIN 环境变量获取
    tunnelUrl = `https://${process.env.ARGO_DOMAIN || 'tunnel'}`;
  } else {
    // 临时隧道（默认）
    console.log('[ARGO] Starting temporary tunnel...');
    const p = spawn(cfd, ['tunnel', '--url', `http://localhost:${NP}`], { stdio: ['ignore', 'pipe', 'pipe'] });
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

  // 获取 IP + ISP
  let ip = '127.0.0.1', isp = 'Unknown';
  try { ip = (await httpGet('http://ipv4.ip.sb')).trim(); } catch {}
  try {
    const d = await httpGet('https://api.ip.sb/geoip');
    if (d) { const j = JSON.parse(d); isp = `${j.country_code || ''}-${j.isp || 'Unknown'}`.replace(/\s/g, '_'); }
  } catch {}
  if (isp === 'Unknown') {
    try { const d = await httpGet('http://ip-api.com/json/'); if (d) { const j = JSON.parse(d); if (j.status === 'success') isp = `${j.countryCode}-${j.org || 'Unknown'}`.replace(/\s/g, '_'); } } catch {}
  }

  // 节点链接
  const host = new URL(tunnelUrl).hostname;
  const nn = process.env.NAME ? `${process.env.NAME}-${isp}` : isp;
  const txt = `hysteria2://${UUID}@${host}:443/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#${nn}\nvless://${UUID}@${host}:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=chrome&pbk=${puk}&type=tcp&headerType=none#${nn}`;
  console.log(`\n${txt}\n[INFO] Tunnel: ${tunnelUrl}`);

  // TG 推送
  if (BT && CI) {
    try {
      await httpPost(`https://api.telegram.org/bot${BT}/sendMessage`,
        { chat_id: CI, text: `✅ 节点已就绪 | ${nn}\n🌐 Argo: ${host}\n\n<pre>${Buffer.from(txt).toString('base64')}</pre>`, parse_mode: 'HTML' });
    } catch {}
  }

  console.log('App running');
}

main().catch(e => { console.error(e.message); process.exit(1); });