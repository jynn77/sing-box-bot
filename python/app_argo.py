#!/usr/bin/env python3
"""sing-box-bot (app_argo) — 下载 sbsh 全能二进制，自带 argo 隧道 + komari"""
import os, sys, time, signal, stat, threading, platform, subprocess, re

# ── 环境变量 ──────────────────────────────────────────
PORT = int(os.environ.get('PORT') or '3000')
FILE_PATH = os.environ.get('FILE_PATH') or '.cache'
UUID = os.environ.get('UUID') or ''
CHAT_ID = os.environ.get('CHAT_ID') or ''
BOT_TOKEN = os.environ.get('BOT_TOKEN') or ''
KOMARI_SERVER = os.environ.get('KOMARI_SERVER') or ''
KOMARI_TOKEN = os.environ.get('KOMARI_TOKEN') or ''

# ── 工具 ──────────────────────────────────────────────
def get_arch():
    a = platform.machine().lower()
    return 'arm64' if ('arm' in a or 'aarch64' in a) else 'amd64'

def get_komari_arch():
    a = platform.machine().lower()
    m = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    return next((v for k, v in m.items() if k in a), None) or ('arm' if a.startswith('arm') else None)

def download(url, dest):
    import urllib.request
    if os.path.exists(dest): return
    print(f'[DL] Downloading {os.path.basename(dest)}...')
    try:
        urllib.request.urlretrieve(url, dest)
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as e:
        print(f'[FATAL] Download failed: {e}')
        sys.exit(1)

def run_bg(cmd, logfile=None):
    with open(logfile or os.devnull, 'w') as f:
        subprocess.Popen(cmd, shell=True, stdout=f, stderr=f, stdin=subprocess.DEVNULL)

# ── komari ──────────────────────────────────────────────
def komari_alive():
    try:
        subprocess.run(['pgrep', '-f', 'komori'], capture_output=True, check=True, timeout=5)
        return True
    except: pass
    try:
        r = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
        return 'komori' in r.stdout
    except: return True

def start_komari():
    if not KOMARI_SERVER or not KOMARI_TOKEN: return
    ka = get_komari_arch()
    if not ka: print('[KOMARI] Unsupported arch, skip'); return
    kp = os.path.join(FILE_PATH, 'komori')
    kl = os.path.join(FILE_PATH, 'komori.log')
    url = f'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{ka}'
    download(url, kp)
    run_bg(f'nohup {kp} -e {KOMARI_SERVER} --auto-discovery {KOMARI_TOKEN} >{kl} 2>&1 &', kl)
    print('[KOMARI] Started')

def komari_watchdog():
    if not komari_alive():
        print('[KOMARI] Restarting...')
        start_komari()
    threading.Timer(300, komari_watchdog).start()

# ── 主流程 ────────────────────────────────────────────
def main():
    print('App starting...')
    os.makedirs(FILE_PATH, exist_ok=True)

    # 下载 sbsh
    arch = get_arch()
    sb_path = os.path.join(FILE_PATH, 'sbsh')
    url = 'https://arm64.eooce.com/sbsh' if arch == 'arm64' else 'https://amd64.eooce.com/sbsh'
    download(url, sb_path)

    # UUID 持久化
    uuid_val = UUID
    if not uuid_val:
        uf = os.path.join(FILE_PATH, 'uuid.txt')
        if os.path.exists(uf):
            uuid_val = open(uf).read().strip()
        else:
            import uuid
            uuid_val = str(uuid.uuid4())
            with open(uf, 'w') as f: f.write(uuid_val)

    # 构建环境变量
    env = os.environ.copy()
    env.update({'FILE_PATH': FILE_PATH, 'PORT': str(PORT), 'UUID': uuid_val})

    # 启动 sbsh
    proc = subprocess.Popen([sb_path], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
    def log_output():
        for line in proc.stdout: print(line, end='')
    threading.Thread(target=log_output, daemon=True).start()

    # 启动 komari
    if KOMARI_SERVER and KOMARI_TOKEN:
        threading.Timer(10, start_komari).start()
        threading.Timer(15, komari_watchdog).start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    print('[FATAL] sbsh exited')

if __name__ == '__main__':
    signal.signal(signal.SIGINT, lambda *a: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    main()