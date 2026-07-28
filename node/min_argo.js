#!/usr/bin/env node
/** sing-box-bot (min_argo) — 下载 sbsh 全能二进制，自带 argo 隧道 + komari */
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
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

// ── 配置 ────────────────────────────────────────────────
const FP = process.env.FILE_PATH || '.cache';
const UUID = process.env.UUID || crypto.randomUUID();
const NAME = process.env.NAME || '';
const CHAT_ID = process.env.CHAT_ID || '';
const BOT_TOKEN = process.env.BOT_TOKEN || '';
const PORT = parseInt(process.env.PORT) || 3000;
const KOMARI_SERVER = process.env.KOMARI_SERVER || '';
const KOMARI_TOKEN = process.env.KOMARI_TOKEN || '';

// ── 下载 ────────────────────────────────────────────────
function dl(name, url) {
  const fp = path.join(FP, name);
  if (fs.existsSync(fp)) return true;
  console.log(`[DL] Downloading ${name}...`);
  try {
    execSync(`curl -sLo "${fp}" "${url}" 2>/dev/null || wget -qO "${fp}" "${url}" 2>/dev/null`, { timeout: 60000, stdio: 'pipe' });
    fs.chmodSync(fp, 0o775); return true;
  } catch { console.error(`[FATAL] Download ${name} failed`); return false; }
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
function startKomari() {
  if (!KOMARI_SERVER || !KOMARI_TOKEN) return;
  const arch = getKomariArch();
  if (!arch) { console.log('[KOMARI] Unsupported arch, skip'); return; }
  const komPath = path.join(FP, 'komori');
  const komLog = path.join(FP, 'komori.log');
  if (!dl('komori', `https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-${arch}`)) return;
  execSync(`nohup ${komPath} -e ${KOMARI_SERVER} --auto-discovery ${KOMARI_TOKEN} >${komLog} 2>&1 &`, { timeout: 5000 });
  console.log('[KOMARI] Started');
}

// ── 主流程 ──────────────────────────────────────────────
async function main() {
  console.log('App starting...');
  fs.mkdirSync(FP, { recursive: true });

  // 下载 sbsh
  const arch = os.arch().toLowerCase().startsWith('arm') ? 'arm64' : 'amd64';
  const sbPath = path.join(FP, 'sbsh');
  const url = arch === 'arm64' ? 'https://arm64.eooce.com/sbsh' : 'https://amd64.eooce.com/sbsh';
  if (!dl('sbsh', url)) process.exit(1);

  // 构建环境变量
  const env = { ...process.env, FILE_PATH: FP, PORT: String(PORT) };
  if (!process.env.UUID) {
    const uf = path.join(FP, 'uuid.txt');
    if (fs.existsSync(uf)) env.UUID = fs.readFileSync(uf, 'utf8').trim();
    else { fs.writeFileSync(uf, UUID); env.UUID = UUID; }
  }

  // 启动 sbsh
  const child = spawn(sbPath, [], { env, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stdout.on('data', d => process.stdout.write(d));
  child.stderr.on('data', d => process.stderr.write(d));
  child.on('exit', code => { console.error(`[FATAL] sbsh exited with code ${code}`); process.exit(1); });

  // 启动 komari
  if (KOMARI_SERVER && KOMARI_TOKEN) {
    setTimeout(() => { startKomari(); }, 10000);
    setInterval(() => {
      if (!komariAlive()) { console.log('[KOMARI] Restarting...'); startKomari(); }
    }, 300000);
  }

  await new Promise(() => {});
}

main().catch(e => { console.error(e.message); process.exit(1); });