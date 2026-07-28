#!/usr/bin/env python3
"""sing-box-bot (app_argo) — 下载 sbsh 全能二进制，自带 argo 隧道"""
import os, sys, time, signal, stat, threading, platform, subprocess
from pathlib import Path

# ── 环境变量 ──────────────────────────────────────────
PORT = int(os.environ.get('PORT') or '3000')
FILE_PATH = os.environ.get('FILE_PATH') or '.cache'
UUID = os.environ.get('UUID') or ''
NAME = os.environ.get('NAME') or ''
CHAT_ID = os.environ.get('CHAT_ID') or ''
BOT_TOKEN = os.environ.get('BOT_TOKEN') or ''

# ── 工具 ──────────────────────────────────────────────
def get_arch():
    a = platform.machine().lower()
    return 'arm64' if ('arm' in a or 'aarch64' in a) else 'amd64'

def download(url, dest):
    import urllib.request
    if os.path.exists(dest): return
    print(f'[DL] Downloading sbsh...')
    try:
        urllib.request.urlretrieve(url, dest)
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as e:
        print(f'[FATAL] Download failed: {e}')
        sys.exit(1)

# ── 主流程 ────────────────────────────────────────────
def main():
    print('App starting...')
    os.makedirs(FILE_PATH, exist_ok=True)

    # 下载 sbsh
    arch = get_arch()
    url = 'https://arm64.eooce.com/sbsh' if arch == 'arm64' else 'https://amd64.eooce.com/sbsh'
    sb_path = os.path.join(FILE_PATH, 'sbsh')
    download(url, sb_path)

    # UUID 持久化
    if not UUID:
        uf = os.path.join(FILE_PATH, 'uuid.txt')
        if os.path.exists(uf):
            uuid_val = open(uf).read().strip()
        else:
            import uuid
            uuid_val = str(uuid.uuid4())
            with open(uf, 'w') as f: f.write(uuid_val)
    else:
        uuid_val = UUID

    # 构建环境变量
    env = os.environ.copy()
    env.update({'FILE_PATH': FILE_PATH, 'PORT': str(PORT), 'UUID': uuid_val})

    # 启动 sbsh（自带 argo 隧道）
    proc = subprocess.Popen([sb_path], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)

    def log_output():
        for line in proc.stdout:
            print(line, end='')
    threading.Thread(target=log_output, daemon=True).start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    print('[FATAL] sbsh exited')

if __name__ == '__main__':
    signal.signal(signal.SIGINT, lambda *a: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    main()