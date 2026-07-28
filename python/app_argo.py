#!/usr/bin/env python3
"""sing-box-bot (app_argo) — sbsh 全能二进制 + komari"""
import os, sys, signal, time, stat, subprocess, threading, platform, urllib.request, urllib.error, re
from pathlib import Path

# 从 .env 加载（如果存在）
_env = Path(__file__).parent / '.env'
if _env.exists():
    for l in _env.read_text().split('\n'):
        m = re.match(r'^\s*([^#=]+)=(.*)', l.strip())
        if m: os.environ.setdefault(m.group(1).strip(), m.group(2).strip().strip('"\''))

PORT = int(os.environ.get('PORT', 3000))
FILE_PATH = os.environ.get('FILE_PATH', '.cache')
UUID = os.environ.get('UUID', '')
NAME = os.environ.get('NAME', '')
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
KOMARI_SERVER = os.environ.get('KOMARI_SERVER', '')
KOMARI_TOKEN = os.environ.get('KOMARI_TOKEN', '')
ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN', '')
ARGO_AUTH = os.environ.get('ARGO_AUTH', '')
ARGO_PORT = os.environ.get('ARGO_PORT', '8001')
CFIP = os.environ.get('CFIP', 'saas.sin.fan')
CFPORT = os.environ.get('CFPORT', '443')
SUB_PATH = os.environ.get('SUB_PATH', 'sub')
DISABLE_ARGO = os.environ.get('DISABLE_ARGO', 'false').lower() in ('true', '1')
SHOW_LOG = os.environ.get('SHOW_LOG', 'true').lower() in ('true', 'yes', '1')

def get_arch():
    a = platform.machine().lower()
    if a in ('x86_64', 'amd64'): return 'amd64'
    if a in ('aarch64', 'arm64'): return 'arm64'
    raise Exception(f'Unsupported arch: {a}')

def download(url, dest):
    if os.path.exists(dest): return
    print(f'[DL] Downloading sbsh...')
    opener = urllib.request.build_opener()
    opener.addheaders = [
        ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
        ('Accept', '*/*'), ('Connection', 'keep-alive')]
    urllib.request.install_opener(opener)
    try:
        urllib.request.urlretrieve(url, dest)
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as e:
        if os.path.exists(dest): os.unlink(dest)
        print(f'[FATAL] Download failed: {e}'); sys.exit(1)

# ── komari ──────────────────────────────────────────────
def komari_arch():
    a = platform.machine().lower()
    m = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    return next((v for k, v in m.items() if k in a), None) or ('arm' if a.startswith('arm') else None)

def start_komari():
    if not KOMARI_SERVER or not KOMARI_TOKEN: return
    ka = komari_arch()
    if not ka: return
    kp = os.path.join(FILE_PATH, 'komori')
    kl = os.path.join(FILE_PATH, 'komori.log')
    url = f'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{ka}'
    if not os.path.exists(kp):
        print('[DL] Downloading komori...')
        download(url, kp)
    subprocess.Popen(f'nohup {kp} -e {KOMARI_SERVER} --auto-discovery {KOMARI_TOKEN} >{kl} 2>&1 &', shell=True)
    print('[KOMARI] Started')

def komari_alive():
    try:
        subprocess.run(['pgrep', '-f', 'komori'], capture_output=True, check=True, timeout=5)
        return True
    except: pass
    try:
        r = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
        return 'komori' in r.stdout
    except: return True

def komari_watchdog():
    while True:
        time.sleep(300)
        if not komari_alive():
            print('[KOMARI] Restarting...')
            start_komari()

# ── 主流程 ────────────────────────────────────────────
def main():
    print('App starting...')
    os.makedirs(FILE_PATH, exist_ok=True)

    # 下载 sbsh
    arch = get_arch()
    url = 'https://amd64.eooce.com/sbsh' if arch == 'amd64' else 'https://arm64.eooce.com/sbsh'
    binary = os.path.join(os.getcwd(), 'sbsh')
    download(url, binary)

    # 构建传给 sbsh 的环境变量
    env = os.environ.copy()
    cfg = {
        'UUID': UUID, 'NAME': NAME, 'CHAT_ID': CHAT_ID, 'BOT_TOKEN': BOT_TOKEN,
        'ARGO_DOMAIN': ARGO_DOMAIN, 'ARGO_AUTH': ARGO_AUTH, 'ARGO_PORT': ARGO_PORT,
        'CFIP': CFIP, 'CFPORT': CFPORT, 'SUB_PATH': SUB_PATH,
        'FILE_PATH': FILE_PATH, 'PORT': str(PORT),
        'DISABLE_ARGO': 'true' if DISABLE_ARGO else 'false',
        'SHOW_LOG': 'true' if SHOW_LOG else 'false',
    }
    env.update({k: str(v) for k, v in cfg.items()})

    # 启动 sbsh（自带 argo 隧道 + 节点生成）
    proc = subprocess.Popen([binary], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)

    def log_output():
        for line in proc.stdout:
            print(line, end='')
    threading.Thread(target=log_output, daemon=True).start()

    # 启动 komari
    if KOMARI_SERVER and KOMARI_TOKEN:
        threading.Timer(10, start_komari).start()
        threading.Thread(target=lambda: (time.sleep(15), komari_watchdog()), daemon=True).start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    print('[FATAL] sbsh exited')

if __name__ == '__main__':
    signal.signal(signal.SIGINT, lambda *a: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    main()