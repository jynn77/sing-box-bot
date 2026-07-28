#!/usr/bin/env node
/** sing-box-bot (min_argo) — sbsh 全能二进制 + komari */
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const https = require('https');
const { spawn } = require('child_process');

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

// ── 配置 ────────────────────────────────────────────────
const FP = process.env.FILE_PATH || '.cache';
const UUID = process.env.UUID || crypto.randomUUID();
const NAME = process.env.NAME || '';
const CHAT_ID = process.env.CHAT_ID || '';
const BOT_TOKEN = process.env.BOT_TOKEN || '';
const KOMARI_SERVER = process.env.KOMARI_SERVER || '';
const KOMARI_TOKEN = process.env.KOMARI_TOKEN || '';
const ARGO_DOMAIN = process.env.ARGO_DOMAIN || '';
const ARGO_AUTH = process.env.ARGO_AUTH || '';
const ARGO_PORT = process.env.ARGO_PORT || '8001';
const CFIP = process.env.CFIP || 'saas.sin.fan';
const CFPORT = process.env.CFPORT || '443';
const PORT = parseInt(process.env.PORT) || 3000;

// ── 下载 ────────────────────────────────────────────────
function dl(url, dest) {
  if (fs.existsSync(dest)) return Promise.resolve(true);
  console.log(`[DL] Downloading ${path.basename(dest)}...`);
  return new Promise(resolve => {
    const file = fs.createWriteStream(dest);
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 60000 }, res => {
      if (res.statusCode !== 200) { console.error(`[DL] failed: HTTP ${res.statusCode}`); file.close(); try { fs.unlinkSync(dest); } catch {} resolve(false); return; }
      res.pipe(file);
      file.on('finish', () => { file.close(); fs.chmodSync(dest, 0o775); resolve(true); });
    }).on('error', e => { console.error(`[DL] failed: ${e.message}`); file.close(); try { fs.unlinkSync(dest); } catch {} resolve(false); });
  });
}

// ── komari ──────────────────────────────────────────────
function getKomariArch() {
  const a = os.arch().toLowerCase();
  const map = { x64: 'amd64', amd64: 'amd64', arm64: 'arm64', aarch64: 'arm64' };
  return map[a] || (a.startsWith('arm') ? 'arm' : null);
}
function komariAlive() {
  const { execSync } = require('child_process');
  try { return !!execSync('pgrep -f komori 2>/dev/null', { encoding: 'utf8', timeout: 5000 }).trim(); } catch {}
  try { return execSync('ps aux 2>/dev/null', { encoding: 'utf8', timeout: 5000 }).includes('komori'); } catch {}
  return false;
}
async function startKomari() {
  if (!KOMARI_SERVER || !KOMARI_TOKEN) return;
  const arch = getKomariArch();
  if (!arch) return;
  const kp = path.join(FP, 'komori'), kl = path.join(FP, 'komori.log');
  const url = `https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-${arch}`;
  if (!fs.existsSync(kp)) { console.log('[DL] Downloading komori...'); if (!await dl(url, kp)) return; }
  const { execSync } = require('child_process');
  execSync(`nohup ${kp} -e ${KOMARI_SERVER} --auto-discovery ${KOMARI_TOKEN} >${kl} 2>&1 &`, { timeout: 5000 });
  console.log('[KOMARI] Started');
}

// ── 主流程 ──────────────────────────────────────────────
async function main() {
  console.log('App starting...');
  fs.mkdirSync(FP, { recursive: true });

  // 下载 sbsh
  const arch = os.arch().toLowerCase().startsWith('arm') ? 'arm64' : 'amd64';
  const binary = path.join(FP, 'sbsh');
  const url = arch === 'arm64' ? 'https://arm64.eooce.com/sbsh' : 'https://amd64.eooce.com/sbsh';
  if (!await dl(url, binary)) { console.error('[FATAL] Download failed'); process.exit(1); }

  // 构建环境变量
  const env = { ...process.env,
    UUID, NAME, CHAT_ID, BOT_TOKEN, FILE_PATH: FP, PORT: String(PORT),
    ARGO_DOMAIN, ARGO_AUTH, ARGO_PORT, CFIP, CFPORT
  };

  // 启动 sbsh
  const proc = spawn(binary, [], { env, stdio: ['ignore', 'pipe', 'pipe'] });
  proc.stdout.on('data', d => process.stdout.write(d));
  proc.stderr.on('data', d => process.stderr.write(d));
  proc.on('exit', code => { console.error(`[FATAL] sbsh exited with code ${code}`); process.exit(1); });

  // 启动 komari
  if (KOMARI_SERVER && KOMARI_TOKEN) {
    setTimeout(async () => { await startKomari(); }, 10000);
    setInterval(() => { if (!komariAlive()) { console.log('[KOMARI] Restarting...'); startKomari(); } }, 300000);
  }

  await new Promise(() => {});
}

main().catch(e => { console.error(e.message); process.exit(1); });