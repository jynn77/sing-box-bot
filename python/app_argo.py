import os, re, json, time, uuid, base64, platform, subprocess, threading, requests, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# ── 环境变量 ──────────────────────────────────────────
FILE_PATH = os.environ.get('FILE_PATH') or '.cache'
UUID = os.environ.get('UUID') or (
    (lambda f: open(f).read().strip() if os.path.exists(f) else None)(os.path.join(FILE_PATH, 'uuid.txt'))
) or str(uuid.uuid4())
CHAT_ID = os.environ.get('CHAT_ID') or ''
BOT_TOKEN = os.environ.get('BOT_TOKEN') or ''
NAME = os.environ.get('NAME') or ''
KOMARI_SERVER = os.environ.get('KOMARI_SERVER') or ''
KOMARI_TOKEN = os.environ.get('KOMARI_TOKEN') or ''
ARGO_TOKEN = os.environ.get('ARGO_TOKEN') or ''
ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN') or ''
CFIP = os.environ.get('CFIP') or 'saas.sin.fan'
CFPORT = os.environ.get('CFPORT') or '443'

# ── 路径 ──────────────────────────────────────────────
sb_path = os.path.join(FILE_PATH, 'web')
cfd_path = os.path.join(FILE_PATH, 'cfd')
cfd_log = os.path.join(FILE_PATH, 'cfd.log')
config_path = os.path.join(FILE_PATH, 'config.json')

# ── HTTP 处理器 ──────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<h2>sing-box-bot running</h2>')
    def log_message(self, *a): pass

# ── 工具 ──────────────────────────────────────────────
def run(cmd):
    try: r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30); return r.stdout + r.stderr
    except: return ''

def get_arch():
    a = platform.machine().lower()
    return 'arm64' if ('arm' in a or 'aarch64' in a) else 'amd64'

def dl(name, url, retries=3):
    fp = os.path.join(FILE_PATH, name)
    if os.path.exists(fp): return True
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, stream=True, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
            r.raise_for_status()
            with open(fp, 'wb') as f:
                for c in r.iter_content(8192): f.write(c)
            os.chmod(fp, 0o775)
            return True
        except:
            try: os.remove(fp)
            except: pass
            if attempt < retries: time.sleep(5)
    return False

# ── 主流程 ────────────────────────────────────────────
def main():
    print('App starting...')
    os.makedirs(FILE_PATH, exist_ok=True)

    # UUID 持久化
    uf = os.path.join(FILE_PATH, 'uuid.txt')
    if not os.path.exists(uf):
        with open(uf, 'w') as f: f.write(UUID)

    # 下载 sing-box + cloudflared
    arch = get_arch()
    if not dl('web', f'https://{arch}.ssss.nyc.mn/sb'): print('[FATAL] sing-box download failed'); return
    if not dl('cfd', f'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}'): print('[FATAL] cloudflared download failed'); return

    # 配置（VMESS + WebSocket，适合走 CF 隧道）
    with open(config_path, 'w') as f:
        json.dump({
            "log": {"disabled": True},
            "inbounds": [{
                "tag": "vmess-ws", "type": "vmess", "listen": "::", "listen_port": 3001,
                "users": [{"uuid": UUID, "alterId": 0}],
                "transport": {"type": "ws", "path": "/vmess-argo"}
            }],
            "outbounds": [{"type": "direct", "tag": "direct"}]
        }, f, indent=2)

    # 启动 sing-box
    run(f'nohup {sb_path} run -c {config_path} >/dev/null 2>&1 &')
    print('[SB] sing-box started')
    time.sleep(3)

    # ── Cloudflare Tunnel ──────────────────────────────
    tunnel_host = ''
    if ARGO_TOKEN and ARGO_DOMAIN:
        print(f'[ARGO] Using fixed tunnel: {ARGO_DOMAIN}')
        run(f'nohup {cfd_path} tunnel run --token {ARGO_TOKEN} >{cfd_log} 2>&1 &')
        tunnel_host = ARGO_DOMAIN
    else:
        print('[ARGO] Starting temporary tunnel...')
        run(f'nohup {cfd_path} tunnel --url http://localhost:3001 >{cfd_log} 2>&1 &')
        for _ in range(30):
            time.sleep(1)
            try:
                with open(cfd_log) as f:
                    m = re.search(r'https://([a-zA-Z0-9-]+\.trycloudflare\.com)', f.read())
                    if m: tunnel_host = m.group(1); break
            except: pass
        if not tunnel_host:
            print('[FATAL] Failed to get tunnel URL')
            return
    print(f'[ARGO] Tunnel: {tunnel_host}')

    # 启动 komari
    if KOMARI_SERVER and KOMARI_TOKEN:
        threading.Timer(10, lambda: run_komari()).start()
        threading.Thread(target=lambda: (time.sleep(15), komari_watchdog()), daemon=True).start()

    # 获取 ISP
    isp = 'Unknown'
    try:
        d = requests.get('https://api.ip.sb/geoip', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        isp = f"{d.get('country_code', '')}-{d.get('isp', 'Unknown')}".replace(' ', '_')
    except:
        try:
            d = requests.get('http://ip-api.com/json/', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
            if d.get('status') == 'success': isp = f"{d['countryCode']}-{d.get('org', 'Unknown')}".replace(' ', '_')
        except: pass

    # 生成 VMESS 链接
    nn = f'{NAME}-{isp}-Argo' if NAME and NAME.strip() else f'{isp}-Argo'
    vmess_config = {
        "v": "2", "ps": nn, "add": CFIP, "port": CFPORT,
        "id": UUID, "aid": "0", "scy": "auto",
        "net": "ws", "type": "none",
        "host": tunnel_host, "path": "/vmess-argo?ed=2560",
        "tls": "tls", "sni": tunnel_host,
        "alpn": "", "fp": "firefox", "insecure": "0"
    }
    txt = 'vmess://' + base64.b64encode(json.dumps(vmess_config, ensure_ascii=False).encode()).decode()
    print(f'\n{txt}\n[INFO] CF IP: {CFIP}:{CFPORT} | Tunnel: {tunnel_host}')

    # TG 推送
    if BOT_TOKEN and CHAT_ID:
        try:
            requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                          params={'chat_id': CHAT_ID, 'text': f'✅ 节点已就绪 | {nn}\n🌐 Argo: {tunnel_host}\n\n<pre>{base64.b64encode(txt.encode()).decode()}</pre>', 'parse_mode': 'HTML'}, timeout=15)
        except: pass

    # HTTP 健康页
    s = HTTPServer(('0.0.0.0', int(os.environ.get('PORT') or '3000')), Handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()

    print('App running')
    while True: time.sleep(3600)

# ── komari ──────────────────────────────────────────────
def run_komari():
    if not KOMARI_SERVER or not KOMARI_TOKEN: return
    a = platform.machine().lower()
    m = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    ka = next((v for k, v in m.items() if k in a), None) or ('arm' if a.startswith('arm') else None)
    if not ka: return
    kp = os.path.join(FILE_PATH, 'komori')
    kl = os.path.join(FILE_PATH, 'komori.log')
    if not dl('komori', f'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{ka}'): return
    run(f'nohup {kp} -e {KOMARI_SERVER} --auto-discovery {KOMARI_TOKEN} >{kl} 2>&1 &')
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
            run_komari()

if __name__ == '__main__':
    main()