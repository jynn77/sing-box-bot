#!/usr/bin/env node
/** sing-box-bot (min) — 190MB 内存优化版，仅 hy2 + reality + TG 推送 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const os = require('os');
const http = require('http');
const https = require('https');
const { execSync } = require('child_process');

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

// ── 轻量 HTTP GET ──────────────────────────────────────
function httpGet(url) {
  return new Promise((res, rej) => {
    const mod = url.startsWith('https') ? https : http;
    mod.get(url, { timeout: 10000 }, r => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => res(d));
    }).on('error', rej);
  });
}

// ── 轻量 POST ──────────────────────────────────────────
function httpPost(url, data) {
  return new Promise((res, rej) => {
    const u = new URL(url);
    const b = JSON.stringify(data);
    const opt = { hostname: u.hostname, port: u.port || 443, path: u.pathname, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(b) },
      timeout: 15000 };
    const r = (u.protocol === 'https:' ? https : http).request(opt, rp => {
      let d = '';
      rp.on('data', c => d += c);
      rp.on('end', () => res(d));
    });
    r.on('error', rej);
    r.write(b);
    r.end();
  });
}

// ── 配置 ────────────────────────────────────────────────
const FP = process.env.FILE_PATH || '.cache';
const NP = parseInt(process.env.NODE_PORT) || (console.error('NODE_PORT required'), process.exit(1));
const UUID = process.env.UUID || (() => {
  const f = path.join(FP, 'uuid.txt');
  if (fs.existsSync(f)) return fs.readFileSync(f, 'utf8').trim();
  const u = crypto.randomUUID();
  fs.mkdirSync(FP, { recursive: true });
  fs.writeFileSync(f, u);
  return u;
})();
const BT = process.env.BOT_TOKEN || '';
const CI = process.env.CHAT_ID || '';

// ── 主流程 ──────────────────────────────────────────────
async function main() {
  console.log('App starting...');

  // 下载 sing-box
  const arch = os.arch().toLowerCase().startsWith('arm') ? 'arm' : 'amd';
  const base = arch === 'arm' ? 'https://arm64.ssss.nyc.mn' : 'https://amd64.ssss.nyc.mn';
  const sb = path.join(FP, 'web');
  const cfg = path.join(FP, 'config.json');
  const kp = path.join(FP, 'keypair.txt');
  if (!fs.existsSync(sb)) {
    console.log('[DL] Downloading sing-box...');
    const r = await httpGet(`${base}/sb`);
    if (!r) { console.error('[FATAL] Download failed'); process.exit(1); }
    fs.writeFileSync(sb, r);
    fs.chmodSync(sb, 0o775);
  }

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

  // 证书（用一行命令，不校验）
  execSync(`openssl ecparam -genkey -name prime256v1 -out "${FP}/private.key" 2>/dev/null`, { timeout: 10000 });
  execSync(`openssl req -new -x509 -days 3650 -key "${FP}/private.key" -out "${FP}/cert.pem" -subj "/CN=bing.com" 2>/dev/null`, { timeout: 10000 });

  // 配置
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

  // 启动
  execSync(`nohup ${sb} run -c ${cfg} >/dev/null 2>&1 &`, { timeout: 5000 });

  // 获取 IP
  let ip = '127.0.0.1';
  try { ip = (await httpGet('http://ipv4.ip.sb')).trim(); } catch {}

  // 节点链接
  const nn = process.env.NAME || 'Node';
  const txt = `hysteria2://${UUID}@${ip}:${NP}/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#${nn}\nvless://${UUID}@${ip}:${NP}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=chrome&pbk=${puk}&type=tcp&headerType=none#${nn}`;
  console.log(`\n${txt}\n[INFO] Port: ${NP}`);

  // TG 推送
  if (BT && CI) {
    try {
      await httpPost(`https://api.telegram.org/bot${BT}/sendMessage`,
        { chat_id: CI, text: `✅ 节点已就绪 | ${nn}\n🌍 IP: ${ip}\n\n<pre>${Buffer.from(txt).toString('base64')}</pre>`, parse_mode: 'HTML' });
    } catch {}
  }

  // 清理二进制
  setTimeout(() => {
    [cfg, sb].forEach(f => { try { fs.unlinkSync(f); } catch {} });
    console.log('App running');
  }, 90000);
}

main().catch(e => { console.error(e.message); process.exit(1); });