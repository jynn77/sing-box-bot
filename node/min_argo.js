#!/usr/bin/env node
/** sing-box-bot (min_argo) — 下载 sbsh 全能二进制，自带 argo 隧道 */
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

// ── 主流程 ──────────────────────────────────────────────
async function main() {
  console.log('App starting...');

  fs.mkdirSync(FP, { recursive: true });

  // 下载 sbsh 二进制
  const arch = os.arch().toLowerCase().startsWith('arm') ? 'arm64' : 'amd64';
  const sbPath = path.join(FP, 'sbsh');
  if (!fs.existsSync(sbPath)) {
    console.log('[DL] Downloading sbsh...');
    const url = arch === 'arm64' ? 'https://arm64.eooce.com/sbsh' : 'https://amd64.eooce.com/sbsh';
    try {
      execSync(`curl -sLo "${sbPath}" "${url}" 2>/dev/null || wget -qO "${sbPath}" "${url}" 2>/dev/null`, { timeout: 60000, stdio: 'pipe' });
      fs.chmodSync(sbPath, 0o775);
    } catch { console.error('[FATAL] Download failed'); process.exit(1); }
  }

  // 构建环境变量（传给 sbsh）
  const env = { ...process.env, FILE_PATH: FP, PORT: String(PORT) };
  // 如果没设 UUID，持久化到文件
  if (!process.env.UUID) {
    const uf = path.join(FP, 'uuid.txt');
    if (fs.existsSync(uf)) env.UUID = fs.readFileSync(uf, 'utf8').trim();
    else { fs.writeFileSync(uf, UUID); env.UUID = UUID; }
  }

  // 启动 sbsh（自带 argo 隧道 + 节点生成）
  const child = spawn(sbPath, [], { env, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stdout.on('data', d => process.stdout.write(d));
  child.stderr.on('data', d => process.stderr.write(d));
  child.on('exit', code => { console.error(`[FATAL] sbsh exited with code ${code}`); process.exit(1); });

  // 保持运行
  await new Promise(() => {});
}

main().catch(e => { console.error(e.message); process.exit(1); });